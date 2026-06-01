"""
Tests del pipeline de aprendizaje iterativo:
    feedback_store → ml_classifier → hybrid_recognizer → training_scheduler

Ejecutar: python -m unittest test_learning_pipeline.py -v

Diseño: tests aislados de Tkinter y de la cámara. Cada test usa una base de
datos temporal nueva (`tempfile.mkdtemp()`) que se limpia al terminar.
"""
import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from feedback_store import FeedbackStore
from hybrid_recognizer import HybridSymbolRecognizer
from ml_classifier import MLSymbolClassifier
from symbol_recognizer import CorrectionSymbol, SymbolRecognizer
from training_scheduler import TrainingScheduler


# ---------------------------------------------------------------------------- #
# Helpers: sintetizan ROIs reconocibles para cada clase                         #
# ---------------------------------------------------------------------------- #

def make_check(size: int = 100, jitter: int = 0) -> np.ndarray:
    img = np.full((size, size, 3), 255, dtype=np.uint8)
    rng = np.random.default_rng(jitter or 0)
    j = lambda: int(rng.integers(-3, 4))
    cv2.line(img, (15 + j(), size // 2 + j()), (size // 2 + j(), size - 15 + j()),
             (0, 0, 0), 4)
    cv2.line(img, (size // 2 + j(), size - 15 + j()), (size - 10 + j(), 10 + j()),
             (0, 0, 0), 4)
    return img


def make_cross(size: int = 100, jitter: int = 0) -> np.ndarray:
    img = np.full((size, size, 3), 255, dtype=np.uint8)
    rng = np.random.default_rng(jitter or 0)
    j = lambda: int(rng.integers(-3, 4))
    cv2.line(img, (15 + j(), 15 + j()), (size - 15 + j(), size - 15 + j()),
             (0, 0, 0), 4)
    cv2.line(img, (size - 15 + j(), 15 + j()), (15 + j(), size - 15 + j()),
             (0, 0, 0), 4)
    return img


def make_tilde(size: int = 100, jitter: int = 0) -> np.ndarray:
    img = np.full((size, size, 3), 255, dtype=np.uint8)
    rng = np.random.default_rng(jitter or 0)
    j = lambda: int(rng.integers(-2, 3))
    pts = np.array([
        [15 + j(), size // 2 + j()],
        [size // 3 + j(), size // 2 - 12 + j()],
        [2 * size // 3 + j(), size // 2 + 12 + j()],
        [size - 15 + j(), size // 2 + j()],
    ], dtype=np.int32)
    cv2.polylines(img, [pts], False, (0, 0, 0), 4)
    return img


def synthetic_dataset(per_class: int = 8):
    rois, labels = [], []
    for i in range(per_class):
        rois.append(make_check(jitter=i + 1)); labels.append(CorrectionSymbol.CHECK)
        rois.append(make_cross(jitter=i + 11)); labels.append(CorrectionSymbol.CROSS)
        rois.append(make_tilde(jitter=i + 21)); labels.append(CorrectionSymbol.TILDE)
    return rois, labels


# ---------------------------------------------------------------------------- #
# Tests                                                                         #
# ---------------------------------------------------------------------------- #

class TempDbMixin:
    """Mixin: crea un directorio temporal con su propia BD para aislar tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="examenes_test_")
        self.db_path = os.path.join(self.tmp, "test.db")
        self.models_dir = os.path.join(self.tmp, "models")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestFeedbackStore(TempDbMixin, unittest.TestCase):

    def test_record_prediction_and_correction_roundtrip(self):
        store = FeedbackStore(self.db_path)
        roi = make_check()

        sid = store.record_prediction(roi, CorrectionSymbol.CHECK, 0.8)
        self.assertGreater(sid, 0)
        self.assertEqual(store.count_labeled_total(), 0)

        store.record_correction(sid, CorrectionSymbol.CHECK, source="manual_confirm")
        self.assertEqual(store.count_labeled_total(), 1)

        samples = store.fetch_labeled_samples()
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].true_symbol, CorrectionSymbol.CHECK)
        self.assertEqual(samples[0].roi.shape[:2], roi.shape[:2])

    def test_confusion_summary_only_counts_changes(self):
        store = FeedbackStore(self.db_path)
        sid1 = store.record_prediction(make_check(), CorrectionSymbol.CROSS, 0.4)
        store.record_correction(sid1, CorrectionSymbol.CHECK, source="manual_correction")

        sid2 = store.record_prediction(make_cross(), CorrectionSymbol.CROSS, 0.9)
        store.record_correction(sid2, CorrectionSymbol.CROSS, source="manual_confirm")

        summary = store.get_confusion_summary()
        self.assertIn("cross->check", summary)
        self.assertEqual(summary["cross->check"], 1)
        # Las confirmaciones (sin cambio) no aparecen en confusión
        self.assertNotIn("cross->cross", summary)


class TestMLClassifier(unittest.TestCase):

    def test_predicts_with_acceptable_accuracy_on_synthetic(self):
        rois, labels = synthetic_dataset(per_class=10)
        clf = MLSymbolClassifier()
        metrics = clf.train(rois, labels, val_split=0.25, random_state=0)
        self.assertGreaterEqual(metrics["accuracy"], 0.75)
        self.assertTrue(clf.is_ready)

        # Predicción puntual sobre una ROI nueva
        sym, conf = clf.predict(make_check(jitter=999))
        self.assertIsInstance(sym, CorrectionSymbol)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    def test_save_load_roundtrip(self):
        import tempfile, os
        rois, labels = synthetic_dataset(per_class=6)
        clf = MLSymbolClassifier()
        clf.train(rois, labels, val_split=0.25, random_state=1)

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "m.pkl")
            clf.save(path)
            clf2 = MLSymbolClassifier()
            clf2.load(path)
            self.assertTrue(clf2.is_ready)
            sym_a, _ = clf.predict(make_cross(jitter=42))
            sym_b, _ = clf2.predict(make_cross(jitter=42))
            self.assertEqual(sym_a, sym_b)


class TestHybridFusion(TempDbMixin, unittest.TestCase):

    def test_falls_back_to_heuristic_without_ml(self):
        store = FeedbackStore(self.db_path)
        hybrid = HybridSymbolRecognizer(feedback_store=store)
        # Sin ML cargado: la decisión debe igualar a la heurística pura
        roi = make_check()
        heuristic_only = SymbolRecognizer().recognize_symbol(roi)
        sym, _ = hybrid.recognize_symbol(roi)
        self.assertEqual(sym, heuristic_only[0])

    def test_records_predictions_in_store(self):
        store = FeedbackStore(self.db_path)
        hybrid = HybridSymbolRecognizer(feedback_store=store)
        hybrid.recognize_symbol(make_check())
        ids = hybrid.pop_pending_sample_ids()
        self.assertEqual(len(ids), 1)

    def test_ml_override_when_very_confident_and_heuristic_unknown(self):
        from hybrid_recognizer import ML_OVERRIDE_THRESHOLD
        # Stub de ML: muy seguro de CHECK
        class StubML:
            is_ready = True
            def predict(self, roi):
                return CorrectionSymbol.CHECK, 0.95

        store = FeedbackStore(self.db_path)
        hybrid = HybridSymbolRecognizer(
            feedback_store=store, ml_classifier=StubML(),
        )
        # ROI vacía → heurística devuelve UNKNOWN; ML manda
        roi = np.full((100, 100, 3), 255, dtype=np.uint8)
        sym, conf = hybrid.recognize_symbol(roi)
        self.assertEqual(sym, CorrectionSymbol.CHECK)
        # Confianza penalizada al ser override
        self.assertLess(conf, 0.95)


class TestSchedulerTriggers(TempDbMixin, unittest.TestCase):

    def test_does_not_train_below_threshold(self):
        store = FeedbackStore(self.db_path)
        sched = TrainingScheduler(
            store=store, models_dir=self.models_dir, retrain_every_n_new=999,
        )
        # Solo 1 muestra → no entrena
        sid = store.record_prediction(make_check(), CorrectionSymbol.CHECK, 0.7)
        store.record_correction(sid, CorrectionSymbol.CHECK)
        launched = sched.notify_correction_committed()
        self.assertFalse(launched)

    def test_force_retrain_produces_active_model(self):
        store = FeedbackStore(self.db_path)
        sched = TrainingScheduler(
            store=store, models_dir=self.models_dir, retrain_every_n_new=999,
        )
        # Cargamos muestras sintéticas suficientes
        rois, labels = synthetic_dataset(per_class=6)
        for r, lbl in zip(rois, labels):
            sid = store.record_prediction(r, lbl, 0.6)
            store.record_correction(sid, lbl, source="manual_confirm")

        # Force retrain → corre síncronamente en otro hilo, esperamos
        launched = sched.force_retrain()
        self.assertTrue(launched)
        # Esperar el hilo
        import time
        for _ in range(50):
            if not sched.is_training:
                break
            time.sleep(0.1)
        self.assertFalse(sched.is_training, "El entrenamiento no terminó a tiempo")

        active = store.get_active_model()
        self.assertIsNotNone(active, "No se promovió ningún modelo")
        self.assertTrue(os.path.exists(active["model_path"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
