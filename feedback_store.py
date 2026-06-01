"""
Almacén de feedback para aprendizaje iterativo del reconocedor de símbolos.

Persiste:
  - Cada predicción del modelo (con su ROI) en `training_samples`
  - Cada corrección del profesor en `correction_events` (vinculada al sample)
  - Versionado de modelos entrenados en `model_versions`

Las ROIs se guardan como PNG comprimido dentro de un BLOB SQLite.
Para 100x100 grises rondan 1-3 KB, así que miles de muestras siguen siendo
ligeras y no requieren gestión de archivos en disco.

Las muestras quedan disponibles para `training_scheduler` y `ml_classifier`.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, List, Optional, Tuple

import cv2
import numpy as np

from symbol_recognizer import CorrectionSymbol


# ---------------------------------------------------------------------------- #
# Modelo de datos                                                              #
# ---------------------------------------------------------------------------- #

@dataclass
class TrainingSample:
    """Una muestra etiquetada lista para entrenar."""
    sample_id: int
    roi: np.ndarray              # imagen recortada (BGR o gris)
    predicted_symbol: CorrectionSymbol
    predicted_confidence: float
    true_symbol: CorrectionSymbol
    source: str                  # "auto_confirmed" | "manual_correction" | "manual_confirm"
    created_at: str


# ---------------------------------------------------------------------------- #
# Almacén                                                                       #
# ---------------------------------------------------------------------------- #

class FeedbackStore:
    """
    Capa de persistencia para feedback de corrección.

    Concurrencia: SQLite admite múltiples lectores y un escritor.
    Usamos un `threading.Lock` propio porque el scheduler entrenará en otro hilo.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str = "examenes.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._create_tables()

    # ---- creación de tablas -------------------------------------------------

    def _create_tables(self) -> None:
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS training_samples (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    roi_hash              TEXT NOT NULL,
                    roi_png               BLOB NOT NULL,
                    predicted_symbol      TEXT NOT NULL,
                    predicted_confidence  REAL NOT NULL,
                    true_symbol           TEXT,
                    source                TEXT NOT NULL,
                    exam_id               INTEGER,
                    item_number           INTEGER,
                    used_in_model_id      INTEGER,
                    created_at            TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_samples_label
                    ON training_samples (true_symbol)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_samples_unused
                    ON training_samples (used_in_model_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS correction_events (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id         INTEGER NOT NULL,
                    predicted_symbol  TEXT NOT NULL,
                    corrected_symbol  TEXT NOT NULL,
                    confidence        REAL,
                    created_at        TEXT NOT NULL,
                    FOREIGN KEY (sample_id) REFERENCES training_samples (id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS model_versions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_path      TEXT NOT NULL,
                    trained_at      TEXT NOT NULL,
                    n_samples       INTEGER NOT NULL,
                    accuracy        REAL NOT NULL,
                    per_class_json  TEXT,
                    is_active       INTEGER NOT NULL DEFAULT 0,
                    notes           TEXT
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_active
                    ON model_versions (is_active)
            """)
            conn.commit()

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager con cierre garantizado.

        `sqlite3.Connection` admite `with` para transacciones (auto-commit/rollback)
        pero NO cierra la conexión al salir. Aquí encadenamos `with conn:` (commit)
        y `try/finally` (close) para que cada llamada deje el handle limpio y
        no genere `ResourceWarning: unclosed database`.
        """
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # ---- ingreso de datos ---------------------------------------------------

    def record_prediction(
        self,
        roi: np.ndarray,
        predicted: CorrectionSymbol,
        confidence: float,
        exam_id: Optional[int] = None,
        item_number: Optional[int] = None,
    ) -> int:
        """
        Persiste una ROI y la predicción del modelo, sin etiqueta aún.

        Devuelve el `sample_id` para luego vincularlo con una corrección
        cuando el profesor confirme o cambie el símbolo.
        """
        roi_png = self._encode_png(roi)
        roi_hash = hashlib.sha1(roi_png).hexdigest()
        now = datetime.now().isoformat()

        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO training_samples
                    (roi_hash, roi_png, predicted_symbol, predicted_confidence,
                     source, exam_id, item_number, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                roi_hash, roi_png, predicted.value, float(confidence),
                "pending", exam_id, item_number, now,
            ))
            sample_id = cur.lastrowid
            conn.commit()
            return sample_id

    def record_correction(
        self,
        sample_id: int,
        corrected: CorrectionSymbol,
        source: str = "manual_correction",
    ) -> None:
        """
        Marca la etiqueta verdadera de una muestra y registra el evento.

        `source` admite: "manual_correction" (cambió), "manual_confirm" (igual),
        "auto_confirmed" (alta confianza y profesor confirmó sin tocar).
        """
        now = datetime.now().isoformat()
        assert source in {"manual_correction", "manual_confirm", "auto_confirmed"}, \
            f"source inválido: {source}"

        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT predicted_symbol, predicted_confidence FROM training_samples WHERE id = ?",
                (sample_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"sample_id {sample_id} no existe")
            predicted_value, predicted_conf = row

            cur.execute(
                "UPDATE training_samples SET true_symbol = ?, source = ? WHERE id = ?",
                (corrected.value, source, sample_id),
            )
            cur.execute("""
                INSERT INTO correction_events
                    (sample_id, predicted_symbol, corrected_symbol, confidence, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (sample_id, predicted_value, corrected.value, predicted_conf, now))
            conn.commit()

    # ---- consultas ----------------------------------------------------------

    def count_labeled_unused(self) -> int:
        """Muestras con etiqueta verdadera no usadas en el modelo activo aún."""
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM training_samples
                WHERE true_symbol IS NOT NULL
                  AND (used_in_model_id IS NULL OR used_in_model_id < (
                      SELECT COALESCE(MAX(id), 0) FROM model_versions
                  ))
            """)
            return int(cur.fetchone()[0])

    def count_labeled_total(self) -> int:
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM training_samples WHERE true_symbol IS NOT NULL")
            return int(cur.fetchone()[0])

    def fetch_labeled_samples(
        self,
        include_unknown: bool = False,
        limit: Optional[int] = None,
    ) -> List[TrainingSample]:
        """Devuelve muestras con etiqueta verdadera, listas para entrenar."""
        q = """
            SELECT id, roi_png, predicted_symbol, predicted_confidence,
                   true_symbol, source, created_at
            FROM training_samples
            WHERE true_symbol IS NOT NULL
        """
        if not include_unknown:
            q += f" AND true_symbol != '{CorrectionSymbol.UNKNOWN.value}'"
        q += " ORDER BY id ASC"
        if limit:
            q += f" LIMIT {int(limit)}"

        with self._lock, self._session() as conn:
            rows = conn.execute(q).fetchall()

        samples: List[TrainingSample] = []
        for r in rows:
            sid, roi_png, pred, pred_conf, true, src, created = r
            roi = self._decode_png(roi_png)
            samples.append(TrainingSample(
                sample_id=sid,
                roi=roi,
                predicted_symbol=CorrectionSymbol(pred),
                predicted_confidence=float(pred_conf),
                true_symbol=CorrectionSymbol(true),
                source=src,
                created_at=created,
            ))
        return samples

    def mark_samples_used_by_model(self, sample_ids: List[int], model_id: int) -> None:
        if not sample_ids:
            return
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.executemany(
                "UPDATE training_samples SET used_in_model_id = ? WHERE id = ?",
                [(model_id, sid) for sid in sample_ids],
            )
            conn.commit()

    # ---- versionado de modelos ---------------------------------------------

    def register_model_version(
        self,
        model_path: str,
        n_samples: int,
        accuracy: float,
        per_class_json: Optional[str] = None,
        notes: Optional[str] = None,
        activate: bool = True,
    ) -> int:
        """Registra un nuevo modelo y opcionalmente lo activa (desactivando el previo)."""
        now = datetime.now().isoformat()
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            if activate:
                cur.execute("UPDATE model_versions SET is_active = 0")
            cur.execute("""
                INSERT INTO model_versions
                    (model_path, trained_at, n_samples, accuracy, per_class_json, is_active, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (model_path, now, n_samples, accuracy, per_class_json,
                  1 if activate else 0, notes))
            mid = cur.lastrowid
            conn.commit()
            return mid

    def get_active_model(self) -> Optional[dict]:
        """Devuelve metadata del modelo activo o None si todavía no hay ninguno."""
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, model_path, trained_at, n_samples, accuracy, per_class_json, notes
                FROM model_versions
                WHERE is_active = 1
                ORDER BY id DESC LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "model_path": row[1],
                "trained_at": row[2],
                "n_samples": row[3],
                "accuracy": row[4],
                "per_class_json": row[5],
                "notes": row[6],
            }

    def list_model_versions(self) -> List[dict]:
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, model_path, trained_at, n_samples, accuracy, is_active, notes
                FROM model_versions
                ORDER BY id DESC
            """)
            return [
                {
                    "id": r[0], "model_path": r[1], "trained_at": r[2],
                    "n_samples": r[3], "accuracy": r[4],
                    "is_active": bool(r[5]), "notes": r[6],
                }
                for r in cur.fetchall()
            ]

    def get_confusion_summary(self) -> dict:
        """
        Resumen rápido de errores recientes para inspección del profesor.
        Devuelve dict con totales por (predicted -> corrected).
        """
        with self._lock, self._session() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT predicted_symbol, corrected_symbol, COUNT(*)
                FROM correction_events
                WHERE predicted_symbol != corrected_symbol
                GROUP BY predicted_symbol, corrected_symbol
                ORDER BY COUNT(*) DESC
            """)
            return {
                f"{r[0]}->{r[1]}": int(r[2]) for r in cur.fetchall()
            }

    # ---- helpers de codificación -------------------------------------------

    @staticmethod
    def _encode_png(roi: np.ndarray) -> bytes:
        if roi is None or roi.size == 0:
            raise ValueError("ROI vacía no se puede persistir")
        ok, buf = cv2.imencode(".png", roi)
        if not ok:
            raise RuntimeError("cv2.imencode falló al codificar ROI a PNG")
        return buf.tobytes()

    @staticmethod
    def _decode_png(blob: bytes) -> np.ndarray:
        arr = np.frombuffer(blob, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise RuntimeError("cv2.imdecode devolvió None — BLOB corrupto")
        return img
