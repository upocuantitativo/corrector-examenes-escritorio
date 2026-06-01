"""
Reconocedor híbrido: combina la heurística geométrica existente (`SymbolRecognizer`)
con un clasificador ML opcional entrenado a partir de las correcciones del profesor.

Compatibilidad: expone exactamente las mismas firmas públicas que `SymbolRecognizer`
(`recognize_symbol`, `recognize_with_smoothing`, `reset_history`, `get_symbol_value`,
`symbol_to_string`), por lo que puede sustituirlo sin cambios en los llamadores.

Fusión de confianza
-------------------
Cuando ambos motores están disponibles:

  · acuerdo (mismo símbolo) → confianza = max(h, m) ponderando hacia el más fiable;
    el ML aporta evidencia: confianza_final ≈ h_conf + (1 - h_conf) * m_conf * w_m

  · desacuerdo y ML muy seguro (≥ ML_OVERRIDE_THRESHOLD) → usa ML
    pero penaliza la confianza para que pase por revisión humana.

  · desacuerdo con ML poco seguro → usa heurística (criterio conservador:
    nuestro modelo aprende del profesor, no al revés).

  · sin ML cargado → comportamiento idéntico a `SymbolRecognizer`.

Captura de feedback
-------------------
`recognize_symbol(roi)` registra la predicción en `FeedbackStore` y devuelve
también el `sample_id` cuando se usa `recognize_and_track(...)`. La UI de
verificación llamará luego a `feedback_store.record_correction(sample_id, ...)`
con el símbolo definitivo elegido por el profesor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from feedback_store import FeedbackStore
from ml_classifier import MLSymbolClassifier
from symbol_recognizer import CorrectionSymbol, SymbolRecognizer


ML_OVERRIDE_THRESHOLD = 0.85   # ML necesita esto para sobrescribir a la heurística
ML_WEIGHT_ON_AGREEMENT = 0.4   # peso del ML cuando ambos coinciden
DISAGREE_PENALTY = 0.7         # multiplicador a la confianza si hay desacuerdo


@dataclass
class HybridDecision:
    """Resultado detallado de una predicción híbrida (útil para diagnóstico)."""
    symbol: CorrectionSymbol
    confidence: float
    heuristic_symbol: CorrectionSymbol
    heuristic_confidence: float
    ml_symbol: Optional[CorrectionSymbol]
    ml_confidence: Optional[float]
    agreement: bool
    used_ml: bool
    sample_id: Optional[int] = None


class HybridSymbolRecognizer:
    """
    Drop-in para SymbolRecognizer con clasificador ML + persistencia de feedback.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.55,
        feedback_store: Optional[FeedbackStore] = None,
        ml_classifier: Optional[MLSymbolClassifier] = None,
        record_predictions: bool = True,
    ):
        self.confidence_threshold = confidence_threshold
        self.heuristic = SymbolRecognizer(confidence_threshold=confidence_threshold)
        self.ml = ml_classifier if ml_classifier is not None else MLSymbolClassifier()
        self.feedback_store = feedback_store
        self.record_predictions = record_predictions and feedback_store is not None
        self._last_sample_ids: list[int] = []

    # ------------------------------------------------------------------ #
    # API compatible con SymbolRecognizer                                 #
    # ------------------------------------------------------------------ #

    def recognize_symbol(self, roi: np.ndarray) -> Tuple[CorrectionSymbol, float]:
        decision = self.decide(roi)
        if decision.sample_id is not None:
            self._last_sample_ids.append(decision.sample_id)
        return decision.symbol, decision.confidence

    def recognize_with_smoothing(self, roi: np.ndarray) -> Tuple[CorrectionSymbol, float]:
        """Conserva el smoothing de la heurística (no aplicable al ML)."""
        sym, conf = self.heuristic.recognize_with_smoothing(roi)
        if not self.ml.is_ready or roi is None or roi.size == 0:
            return sym, conf
        # Aporte ML como segunda opinión al voto suavizado
        ml_sym, ml_conf = self.ml.predict(roi)
        if ml_sym == sym:
            return sym, min(1.0, conf + (1.0 - conf) * ml_conf * ML_WEIGHT_ON_AGREEMENT)
        return sym, conf  # smoothing manda en caso de desacuerdo

    def reset_history(self) -> None:
        self.heuristic.reset_history()
        self._last_sample_ids.clear()

    def get_symbol_value(self, symbol: CorrectionSymbol) -> float:
        return self.heuristic.get_symbol_value(symbol)

    def symbol_to_string(self, symbol: CorrectionSymbol) -> str:
        return self.heuristic.symbol_to_string(symbol)

    # ------------------------------------------------------------------ #
    # API extendida: trazabilidad de muestras                              #
    # ------------------------------------------------------------------ #

    def decide(
        self,
        roi: np.ndarray,
        exam_id: Optional[int] = None,
        item_number: Optional[int] = None,
    ) -> HybridDecision:
        """
        Versión detallada de `recognize_symbol`. Devuelve HybridDecision con
        ambas opiniones + sample_id (si se persistió en FeedbackStore).
        """
        h_sym, h_conf = self.heuristic.recognize_symbol(roi)

        if self.ml.is_ready and roi is not None and roi.size > 0:
            m_sym, m_conf = self.ml.predict(roi)
        else:
            m_sym, m_conf = None, None

        symbol, confidence, used_ml, agreement = self._fuse(h_sym, h_conf, m_sym, m_conf)

        sample_id = None
        if self.record_predictions and roi is not None and roi.size > 0:
            try:
                sample_id = self.feedback_store.record_prediction(
                    roi=roi,
                    predicted=symbol,
                    confidence=confidence,
                    exam_id=exam_id,
                    item_number=item_number,
                )
            except Exception as e:
                # No bloquear el flujo de corrección si la BD falla
                print(f"[HybridRecognizer] No se pudo registrar predicción: {e}")

        return HybridDecision(
            symbol=symbol,
            confidence=confidence,
            heuristic_symbol=h_sym,
            heuristic_confidence=h_conf,
            ml_symbol=m_sym,
            ml_confidence=m_conf,
            agreement=agreement,
            used_ml=used_ml,
            sample_id=sample_id,
        )

    def pop_pending_sample_ids(self) -> list[int]:
        """
        Devuelve y limpia la lista de sample_ids generados desde el último pop.
        El llamador (UI de verificación) los usa para vincular correcciones.
        """
        ids = self._last_sample_ids
        self._last_sample_ids = []
        return ids

    # ------------------------------------------------------------------ #
    # Lógica de fusión                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fuse(
        h_sym: CorrectionSymbol,
        h_conf: float,
        m_sym: Optional[CorrectionSymbol],
        m_conf: Optional[float],
    ) -> Tuple[CorrectionSymbol, float, bool, bool]:
        # Sin ML disponible: pasa la heurística directamente
        if m_sym is None or m_conf is None:
            return h_sym, h_conf, False, False

        if h_sym == m_sym and h_sym != CorrectionSymbol.UNKNOWN:
            fused = min(1.0, h_conf + (1.0 - h_conf) * m_conf * ML_WEIGHT_ON_AGREEMENT)
            return h_sym, fused, False, True

        # Desacuerdo o heurística incierta
        if h_sym == CorrectionSymbol.UNKNOWN and m_sym != CorrectionSymbol.UNKNOWN:
            # La heurística no se compromete → confía en ML pero suaviza
            return m_sym, m_conf * DISAGREE_PENALTY, True, False

        if m_conf >= ML_OVERRIDE_THRESHOLD:
            # ML muy seguro → cambia decisión y marca para revisión humana
            return m_sym, m_conf * DISAGREE_PENALTY, True, False

        # Heurística manda con confianza penalizada (señala incertidumbre)
        return h_sym, h_conf * DISAGREE_PENALTY, False, False
