"""
Módulo para reconocer símbolos de corrección: ✓ (bien), X (mal), ~ (regular)
Preprocesamiento CLAHE+Otsu inspirado en mrzaizai2k/Automated-scoring-of-handwritten-test-papers
"""
import cv2
import numpy as np
from typing import Tuple, List
from enum import Enum


class CorrectionSymbol(Enum):
    """Tipos de símbolos de corrección"""
    CHECK = "check"
    CROSS = "cross"
    TILDE = "tilde"
    UNKNOWN = "unknown"


class SymbolRecognizer:
    """Reconoce símbolos de corrección mediante análisis geométrico con CLAHE+Otsu"""

    def __init__(self, confidence_threshold: float = 0.55):
        self.confidence_threshold = confidence_threshold
        self._history: List[Tuple[CorrectionSymbol, float]] = []

    def recognize_symbol(self, roi: np.ndarray) -> Tuple[CorrectionSymbol, float]:
        """
        Reconoce el símbolo en una región de interés.
        Retorna (símbolo, confianza) con confianza en rango 0-1.
        """
        if roi is None or roi.size == 0:
            return CorrectionSymbol.UNKNOWN, 0.0

        binary = self._preprocess(roi)
        if np.sum(binary > 0) < 30:
            return CorrectionSymbol.UNKNOWN, 0.0

        scores = {
            CorrectionSymbol.CHECK: self._score_check(binary),
            CorrectionSymbol.CROSS: self._score_cross(binary),
            CorrectionSymbol.TILDE: self._score_tilde(binary),
        }

        best = max(scores, key=scores.get)
        best_conf = scores[best]

        if best_conf < self.confidence_threshold:
            return CorrectionSymbol.UNKNOWN, best_conf

        return best, best_conf

    def recognize_with_smoothing(self, roi: np.ndarray) -> Tuple[CorrectionSymbol, float]:
        """Reconoce con validación triple acumulada (triple-confirmation del repo de referencia)."""
        symbol, conf = self.recognize_symbol(roi)
        self._history.append((symbol, conf))
        if len(self._history) > 5:
            self._history.pop(0)

        if len(self._history) < 3:
            return symbol, conf

        recent = self._history[-3:]
        votes: dict = {}
        for s, c in recent:
            votes.setdefault(s, []).append(c)

        winner = max(votes, key=lambda s: len(votes[s]))
        avg_conf = sum(votes[winner]) / len(votes[winner])
        return winner, avg_conf

    def reset_history(self):
        """Resetea el historial para un nuevo ítem/examen."""
        self._history.clear()

    # ------------------------------------------------------------------ #
    # Preprocesamiento                                                     #
    # ------------------------------------------------------------------ #

    def _preprocess(self, roi: np.ndarray) -> np.ndarray:
        """CLAHE + Otsu thresholding, imagen normalizada a 100×100."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi.copy()
        resized = cv2.resize(gray, (100, 100))

        # CLAHE para maximizar contraste local (técnica central del repo de referencia)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(resized)

        # Otsu: umbral automático óptimo
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Cierre morfológico para unir trazos finos
        k = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)

    # ------------------------------------------------------------------ #
    # Puntuadores                                                          #
    # ------------------------------------------------------------------ #

    def _score_check(self, binary: np.ndarray) -> float:
        """✓: trazo en V — cuadrante inferior-izquierdo + superior-derecho, dos ángulos opuestos."""
        h, w = binary.shape
        total = int(np.sum(binary > 0))
        if total == 0:
            return 0.0

        # Cuadrantes clave de un check
        lb = int(np.sum(binary[h // 2:, :w // 2] > 0))
        rt = int(np.sum(binary[:h // 2, w // 2:] > 0))
        quadrant_score = min((lb + rt) / total, 1.0)

        # Dos segmentos de línea con ángulos opuestos
        edges = cv2.Canny(binary, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 20, minLineLength=15, maxLineGap=8)
        line_score = 0.0
        if lines is not None:
            angles = [
                np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))
                for x1, y1, x2, y2 in lines[:, 0]
            ]
            has_neg = any(-80 < a < -10 for a in angles)
            has_pos = any(20 < a < 80 for a in angles)
            line_score = 0.6 if (has_neg and has_pos) else (0.3 if (has_neg or has_pos) else 0.0)

        # Centro de masa vertical: debe estar en mitad inferior (fondo del V)
        moments = cv2.moments(binary)
        vert_score = 0.0
        if moments["m00"] > 0:
            cy = moments["m01"] / moments["m00"]
            vert_score = min(cy / h * 1.5, 1.0)

        return line_score * 0.45 + quadrant_score * 0.35 + vert_score * 0.20

    def _score_cross(self, binary: np.ndarray) -> float:
        """X: densidad en ambas diagonales + simetría + contenido en 4 esquinas."""
        h, w = binary.shape
        size = min(h, w)
        total = int(np.sum(binary > 0))
        if total == 0:
            return 0.0

        hits1 = hits2 = 0
        for i in range(size):
            row_s = slice(max(0, i - 1), min(h, i + 2))
            col_s1 = slice(max(0, i - 1), min(w, i + 2))
            if binary[row_s, col_s1].max() > 0:
                hits1 += 1
            j2 = w - 1 - i
            col_s2 = slice(max(0, j2 - 1), min(w, j2 + 2))
            if binary[row_s, col_s2].max() > 0:
                hits2 += 1

        diag_score = (hits1 + hits2) / (2 * size)

        sym_h = float(np.mean(binary == cv2.flip(binary, 0)))
        sym_v = float(np.mean(binary == cv2.flip(binary, 1)))
        sym_score = (sym_h + sym_v) / 2

        qh, qw = max(h // 4, 5), max(w // 4, 5)
        corner_pixels = int(
            np.sum(binary[:qh, :qw] > 0) +
            np.sum(binary[:qh, -qw:] > 0) +
            np.sum(binary[-qh:, :qw] > 0) +
            np.sum(binary[-qh:, -qw:] > 0)
        )
        corner_score = min(corner_pixels / (total + 1), 1.0)

        return diag_score * 0.45 + sym_score * 0.25 + corner_score * 0.30

    def _score_tilde(self, binary: np.ndarray) -> float:
        """~: concentración en banda central, aspect ratio > 1, ondulación horizontal."""
        h, w = binary.shape
        total = int(np.sum(binary > 0))
        if total == 0:
            return 0.0

        band = binary[h // 4: 3 * h // 4, :]
        band_score = np.sum(band > 0) / total

        coords = cv2.findNonZero(binary)
        if coords is None:
            return 0.0
        _, _, bw, bh = cv2.boundingRect(coords)
        aspect_score = min((bw / bh if bh > 0 else 0) / 3.0, 1.0)

        proj = np.sum(band, axis=1).astype(float)
        wave_score = 0.0
        if proj.max() > 0:
            pn = proj / proj.max()
            sign_changes = int(np.sum(np.diff(np.sign(np.diff(pn))) != 0))
            wave_score = min(sign_changes / 4.0, 1.0)

        q = max(h // 4, 5)
        corner_pixels = int(
            np.sum(binary[:q, :q] > 0) +
            np.sum(binary[:q, -q:] > 0) +
            np.sum(binary[-q:, :q] > 0) +
            np.sum(binary[-q:, -q:] > 0)
        )
        no_corner = 1.0 - min(corner_pixels / (total + 1), 1.0)

        return band_score * 0.35 + aspect_score * 0.30 + wave_score * 0.20 + no_corner * 0.15

    # ------------------------------------------------------------------ #
    # Utilidades                                                           #
    # ------------------------------------------------------------------ #

    def get_symbol_value(self, symbol: CorrectionSymbol) -> float:
        return {
            CorrectionSymbol.CHECK: 1.0,
            CorrectionSymbol.TILDE: 0.5,
            CorrectionSymbol.CROSS: 0.0,
            CorrectionSymbol.UNKNOWN: 0.5,
        }.get(symbol, 0.5)

    def symbol_to_string(self, symbol: CorrectionSymbol) -> str:
        return {
            CorrectionSymbol.CHECK: "✓ (Bien)",
            CorrectionSymbol.TILDE: "~ (Regular)",
            CorrectionSymbol.CROSS: "X (Mal)",
            CorrectionSymbol.UNKNOWN: "? (Desconocido)",
        }.get(symbol, "?")
