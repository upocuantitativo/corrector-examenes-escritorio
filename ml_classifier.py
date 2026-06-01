"""
Clasificador ML entrenable para símbolos de corrección.

Pipeline:
  ROI (cualquier tamaño) → preprocesado (gris, 100×100, CLAHE+Otsu)
                        → features (HOG + estadísticas geométricas)
                        → HistGradientBoosting (sklearn)
                        → (CorrectionSymbol, probabilidad calibrada)

Diseño deliberadamente clásico (no DL) por:
  - Funciona bien con pocas muestras (decenas a cientos)
  - Sin dependencia de GPU ni PyTorch
  - Persistencia con joblib (un archivo .pkl pequeño)
  - Inferencia en milisegundos

El features.py inline aquí evita un módulo extra; la lógica es la misma
que ya usa `SymbolRecognizer._preprocess` para mantener consistencia visual
entre la heurística y el ML.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from symbol_recognizer import CorrectionSymbol


# Clases que el ML aprende. UNKNOWN se excluye del entrenamiento porque
# no es una clase real, sino la ausencia de confianza.
TRAINABLE_CLASSES: List[CorrectionSymbol] = [
    CorrectionSymbol.CHECK,
    CorrectionSymbol.CROSS,
    CorrectionSymbol.TILDE,
]

_CLASS_TO_IDX = {s: i for i, s in enumerate(TRAINABLE_CLASSES)}
_IDX_TO_CLASS = {i: s for s, i in _CLASS_TO_IDX.items()}


# ---------------------------------------------------------------------------- #
# Feature extraction                                                           #
# ---------------------------------------------------------------------------- #

def preprocess_for_features(roi: np.ndarray) -> np.ndarray:
    """
    Normaliza ROI a 100×100 binario invertido (símbolo = blanco, fondo = negro).

    Misma cadena CLAHE+Otsu que `SymbolRecognizer._preprocess` para que ML y
    heurística vean la misma imagen y sus señales sean comparables.
    """
    if roi is None or roi.size == 0:
        raise ValueError("ROI vacía en preprocess_for_features")

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi.copy()
    resized = cv2.resize(gray, (100, 100))
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(resized)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k = np.ones((2, 2), np.uint8)
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)


def extract_features(roi: np.ndarray) -> np.ndarray:
    """
    Devuelve un vector de características de tamaño fijo.

    Combina:
      - HOG manual sobre la binaria 100×100 (descriptores geométricos densos)
      - Estadísticas globales (densidad, dispersión, momentos centrales)
      - Histograma de orientaciones de líneas (Hough)

    Total: ~ 200 features. Suficientes para HistGradientBoosting con pocas muestras.
    """
    binary = preprocess_for_features(roi)
    return np.concatenate([
        _hog_features(binary),
        _global_stats(binary),
        _line_orientation_features(binary),
    ]).astype(np.float32)


def _hog_features(binary: np.ndarray) -> np.ndarray:
    """HOG simple sobre 5×5 celdas con 9 bins de orientación = 225 features."""
    # gradientes
    gx = cv2.Sobel(binary, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(binary, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ang = (np.degrees(np.arctan2(gy, gx)) % 180)  # 0..180

    cells_per_side = 5
    bins = 9
    cell_h = binary.shape[0] // cells_per_side
    cell_w = binary.shape[1] // cells_per_side

    feat = np.zeros((cells_per_side, cells_per_side, bins), dtype=np.float32)
    for r in range(cells_per_side):
        for c in range(cells_per_side):
            y0, y1 = r * cell_h, (r + 1) * cell_h
            x0, x1 = c * cell_w, (c + 1) * cell_w
            cell_mag = mag[y0:y1, x0:x1].ravel()
            cell_ang = ang[y0:y1, x0:x1].ravel()
            hist, _ = np.histogram(
                cell_ang, bins=bins, range=(0, 180), weights=cell_mag
            )
            feat[r, c] = hist

    # Normalización L2 por celda para invarianza ligera al contraste
    norm = np.linalg.norm(feat.reshape(-1, bins), axis=1, keepdims=True) + 1e-6
    feat = (feat.reshape(-1, bins) / norm).ravel()
    return feat


def _global_stats(binary: np.ndarray) -> np.ndarray:
    """Densidad por cuadrantes + momentos de Hu + bbox + simetrías."""
    h, w = binary.shape
    total = float(np.sum(binary > 0))
    if total == 0:
        return np.zeros(14, dtype=np.float32)

    # Densidad por cuadrantes
    q_tl = float(np.sum(binary[:h // 2, :w // 2] > 0)) / total
    q_tr = float(np.sum(binary[:h // 2, w // 2:] > 0)) / total
    q_bl = float(np.sum(binary[h // 2:, :w // 2] > 0)) / total
    q_br = float(np.sum(binary[h // 2:, w // 2:] > 0)) / total

    # Banda central horizontal y vertical
    band_h = float(np.sum(binary[h // 4: 3 * h // 4, :] > 0)) / total
    band_v = float(np.sum(binary[:, w // 4: 3 * w // 4] > 0)) / total

    # Bounding box del símbolo
    coords = cv2.findNonZero(binary)
    if coords is None:
        bx, by, bw, bh = 0, 0, 0, 0
    else:
        bx, by, bw, bh = cv2.boundingRect(coords)
    aspect = bw / bh if bh > 0 else 0.0

    # Simetrías
    sym_h = float(np.mean(binary == cv2.flip(binary, 0)))
    sym_v = float(np.mean(binary == cv2.flip(binary, 1)))

    # Centro de masa relativo
    m = cv2.moments(binary)
    cy_rel = (m["m01"] / m["m00"]) / h if m["m00"] > 0 else 0.0
    cx_rel = (m["m10"] / m["m00"]) / w if m["m00"] > 0 else 0.0

    return np.array([
        q_tl, q_tr, q_bl, q_br,
        band_h, band_v,
        aspect, bw / w, bh / h,
        sym_h, sym_v,
        cx_rel, cy_rel,
        total / (h * w),  # densidad global
    ], dtype=np.float32)


def _line_orientation_features(binary: np.ndarray) -> np.ndarray:
    """Histograma 12-bin de orientaciones detectadas por Hough."""
    edges = cv2.Canny(binary, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 15, minLineLength=10, maxLineGap=8)
    bins = 12
    hist = np.zeros(bins, dtype=np.float32)
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            angle = (np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1))) + 180) % 180
            idx = min(int(angle / (180 / bins)), bins - 1)
            length = float(np.hypot(x2 - x1, y2 - y1))
            hist[idx] += length
    s = hist.sum()
    if s > 0:
        hist /= s
    return hist


# ---------------------------------------------------------------------------- #
# Clasificador                                                                  #
# ---------------------------------------------------------------------------- #

class MLSymbolClassifier:
    """
    Clasificador HistGradientBoosting sobre los features de `extract_features`.

    No carga sklearn en import: lo hace en `train` / `load`. Esto evita coste
    de arranque si la app se ejecuta antes de tener modelo entrenado.
    """

    def __init__(self) -> None:
        self._model = None
        self._n_samples_trained = 0

    # ---- predicción --------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, roi: np.ndarray) -> Tuple[CorrectionSymbol, float]:
        """
        Devuelve (símbolo, probabilidad). Si no hay modelo cargado o la ROI
        es inválida, devuelve (UNKNOWN, 0.0).
        """
        if not self.is_ready:
            return CorrectionSymbol.UNKNOWN, 0.0
        try:
            feats = extract_features(roi).reshape(1, -1)
        except ValueError:
            return CorrectionSymbol.UNKNOWN, 0.0
        proba = self._model.predict_proba(feats)[0]
        idx = int(np.argmax(proba))
        return _IDX_TO_CLASS[idx], float(proba[idx])

    def predict_proba_dict(self, roi: np.ndarray) -> dict:
        """Útil para diagnóstico: probabilidad por clase."""
        if not self.is_ready:
            return {s: 0.0 for s in TRAINABLE_CLASSES}
        feats = extract_features(roi).reshape(1, -1)
        proba = self._model.predict_proba(feats)[0]
        return {_IDX_TO_CLASS[i]: float(p) for i, p in enumerate(proba)}

    # ---- entrenamiento -----------------------------------------------------

    def train(
        self,
        rois: List[np.ndarray],
        labels: List[CorrectionSymbol],
        val_split: float = 0.2,
        random_state: int = 42,
    ) -> dict:
        """
        Entrena con (rois, labels). Excluye automáticamente labels UNKNOWN.

        Devuelve dict con métricas: {accuracy, per_class, n_train, n_val}.
        """
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, classification_report

        X, y = [], []
        for roi, lbl in zip(rois, labels):
            if lbl not in _CLASS_TO_IDX:
                continue
            try:
                X.append(extract_features(roi))
            except ValueError:
                continue
            y.append(_CLASS_TO_IDX[lbl])

        if len(set(y)) < 2:
            raise ValueError(
                f"Se necesitan al menos 2 clases con datos para entrenar; "
                f"recibidas: {set(_IDX_TO_CLASS[i].value for i in set(y))}"
            )

        X_arr = np.asarray(X, dtype=np.float32)
        y_arr = np.asarray(y, dtype=np.int32)

        # Stratified split si hay suficientes muestras por clase
        try:
            X_tr, X_va, y_tr, y_va = train_test_split(
                X_arr, y_arr, test_size=val_split,
                stratify=y_arr, random_state=random_state,
            )
        except ValueError:
            # alguna clase con 1 ejemplo → no estratificamos
            X_tr, X_va, y_tr, y_va = train_test_split(
                X_arr, y_arr, test_size=val_split, random_state=random_state,
            )

        model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.08,
            max_depth=6,
            min_samples_leaf=3,
            l2_regularization=0.05,
            random_state=random_state,
        )
        model.fit(X_tr, y_tr)

        y_pred = model.predict(X_va)
        acc = float(accuracy_score(y_va, y_pred))
        per_class = classification_report(
            y_va, y_pred,
            labels=list(range(len(TRAINABLE_CLASSES))),
            target_names=[s.value for s in TRAINABLE_CLASSES],
            output_dict=True,
            zero_division=0,
        )

        self._model = model
        self._n_samples_trained = len(X_arr)

        return {
            "accuracy": acc,
            "per_class": per_class,
            "n_train": len(X_tr),
            "n_val": len(X_va),
            "n_total": len(X_arr),
        }

    # ---- persistencia ------------------------------------------------------

    def save(self, path: str) -> None:
        if self._model is None:
            raise RuntimeError("No hay modelo entrenado para guardar")
        import joblib
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self._model, "n_samples": self._n_samples_trained, "version": 1},
            path,
        )

    def load(self, path: str) -> None:
        import joblib
        payload = joblib.load(path)
        self._model = payload["model"]
        self._n_samples_trained = int(payload.get("n_samples", 0))

    # ---- utilidades para serializar métricas a la BD -----------------------

    @staticmethod
    def metrics_to_json(metrics: dict) -> str:
        return json.dumps({
            "accuracy": metrics.get("accuracy"),
            "n_train": metrics.get("n_train"),
            "n_val": metrics.get("n_val"),
            "n_total": metrics.get("n_total"),
            "per_class": {
                k: {kk: round(vv, 4) if isinstance(vv, float) else vv
                    for kk, vv in v.items()}
                for k, v in metrics.get("per_class", {}).items()
                if isinstance(v, dict)
            },
        }, ensure_ascii=False)
