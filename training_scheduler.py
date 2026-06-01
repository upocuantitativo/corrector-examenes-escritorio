"""
Planificador de reentrenamiento en background.

Responsabilidades:
  - Comprobar periódicamente (o bajo demanda) si hay suficientes muestras
    etiquetadas nuevas para reentrenar.
  - Lanzar `MLSymbolClassifier.train(...)` en un hilo separado para no bloquear
    la UI Tkinter.
  - Comparar el modelo nuevo con el activo y promoverlo solo si mejora.
  - Persistir el modelo en `models/symbol_clf_vN.pkl` y registrar la versión
    en `model_versions` vía `FeedbackStore`.

Política de promoción (conservadora — evita degradar):
  - Si no hay modelo activo: promueve siempre que accuracy ≥ MIN_ACCURACY_PROMOTE.
  - Si hay activo: promueve si new_accuracy ≥ active_accuracy - PROMOTE_TOLERANCE.
    Esto permite que el modelo "se adapte" sin requerir mejora estricta en cada
    iteración (las primeras versiones tienen alta varianza con pocos datos).

Recarga en caliente
-------------------
Tras promover, el scheduler llama a `on_model_promoted(model_path)` (callback
opcional). El llamador típico es `MainApplication`, que reasigna el clasificador
ML del `HybridSymbolRecognizer` activo para que las siguientes correcciones
usen ya el modelo nuevo sin reiniciar la app.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from feedback_store import FeedbackStore
from ml_classifier import MLSymbolClassifier


MIN_SAMPLES_FIRST_TRAIN = 15      # mínimo para considerar entrenar el primer modelo
MIN_SAMPLES_PER_CLASS = 3         # se necesitan al menos N por clase
RETRAIN_EVERY_N_NEW = 20          # cada N correcciones nuevas → reentrenar
MIN_ACCURACY_PROMOTE = 0.60       # mínimo absoluto para activar primer modelo
PROMOTE_TOLERANCE = 0.03          # tolerancia para no degradar


class TrainingScheduler:
    """
    Orquesta reentrenamiento sin bloquear la UI.

    Uso típico desde la app principal:

        store = FeedbackStore("examenes.db")
        scheduler = TrainingScheduler(
            store=store,
            models_dir="models",
            on_model_promoted=app.reload_active_model,
        )
        scheduler.try_load_active_into(hybrid_recognizer.ml)
        # ...cada vez que el profesor confirma/corrige un examen:
        scheduler.notify_correction_committed()
    """

    def __init__(
        self,
        store: FeedbackStore,
        models_dir: str = "models",
        on_model_promoted: Optional[Callable[[str], None]] = None,
        retrain_every_n_new: int = RETRAIN_EVERY_N_NEW,
    ):
        self.store = store
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.on_model_promoted = on_model_promoted
        self.retrain_every_n_new = retrain_every_n_new

        self._training_lock = threading.Lock()
        self._is_training = False
        self._last_train_count = self._count_labeled()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def is_training(self) -> bool:
        return self._is_training

    def try_load_active_into(self, classifier: MLSymbolClassifier) -> bool:
        """
        Si hay un modelo activo en BD, lo carga en `classifier`.
        Devuelve True si se cargó.
        """
        active = self.store.get_active_model()
        if not active:
            return False
        model_path = active["model_path"]
        if not Path(model_path).exists():
            print(f"[Scheduler] Modelo activo en BD pero archivo no existe: {model_path}")
            return False
        try:
            classifier.load(model_path)
            print(f"[Scheduler] Modelo activo cargado: v{active['id']} "
                  f"(acc={active['accuracy']:.3f}, n={active['n_samples']})")
            return True
        except Exception as e:
            print(f"[Scheduler] Error cargando modelo activo: {e}")
            return False

    def notify_correction_committed(self, force: bool = False) -> bool:
        """
        Llámese cuando el profesor confirma/corrige un examen. Decide si
        toca reentrenar y lanza el job en background.

        `force=True` reentrena aunque no se haya alcanzado el umbral.

        Devuelve True si se ha lanzado un entrenamiento.
        """
        if self._is_training:
            return False

        total = self._count_labeled()
        new_since_last = total - self._last_train_count

        if not force:
            if total < MIN_SAMPLES_FIRST_TRAIN:
                return False
            if new_since_last < self.retrain_every_n_new:
                return False

        return self._launch_training_thread()

    def force_retrain(self) -> bool:
        """Atajo para el botón de UI 'reentrenar ahora'."""
        return self.notify_correction_committed(force=True)

    # ------------------------------------------------------------------ #
    # Entrenamiento (background)                                          #
    # ------------------------------------------------------------------ #

    def _launch_training_thread(self) -> bool:
        with self._training_lock:
            if self._is_training:
                return False
            self._is_training = True

        t = threading.Thread(target=self._train_safely, daemon=True, name="ml-retrainer")
        t.start()
        return True

    def _train_safely(self) -> None:
        try:
            self._train()
        except Exception as e:
            print(f"[Scheduler] Entrenamiento falló: {e}")
        finally:
            with self._training_lock:
                self._is_training = False

    def _train(self) -> None:
        samples = self.store.fetch_labeled_samples(include_unknown=False)
        if not self._has_enough_per_class(samples):
            print("[Scheduler] No hay muestras suficientes por clase aún. Saltando.")
            return

        rois = [s.roi for s in samples]
        labels = [s.true_symbol for s in samples]
        sample_ids = [s.sample_id for s in samples]

        clf = MLSymbolClassifier()
        try:
            metrics = clf.train(rois, labels)
        except ValueError as e:
            print(f"[Scheduler] train() rechazó los datos: {e}")
            return

        accuracy = metrics["accuracy"]
        print(f"[Scheduler] Modelo entrenado: acc={accuracy:.3f} "
              f"(n_train={metrics['n_train']}, n_val={metrics['n_val']})")

        active = self.store.get_active_model()
        if not self._should_promote(accuracy, active):
            print(f"[Scheduler] No se promueve (acc={accuracy:.3f}, "
                  f"activo={active['accuracy'] if active else None}).")
            return

        # Persistir y registrar
        next_version = self._next_version_number()
        model_path = str(self.models_dir / f"symbol_clf_v{next_version}.pkl")
        clf.save(model_path)
        model_id = self.store.register_model_version(
            model_path=model_path,
            n_samples=len(samples),
            accuracy=accuracy,
            per_class_json=MLSymbolClassifier.metrics_to_json(metrics),
            notes=f"Auto-train tras {self.retrain_every_n_new} correcciones nuevas",
            activate=True,
        )
        self.store.mark_samples_used_by_model(sample_ids, model_id)
        self._last_train_count = self._count_labeled()
        print(f"[Scheduler] Promovido a v{model_id} -> {model_path}")

        if self.on_model_promoted:
            try:
                self.on_model_promoted(model_path)
            except Exception as e:
                print(f"[Scheduler] on_model_promoted falló: {e}")

    # ------------------------------------------------------------------ #
    # Heurísticas                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _should_promote(new_acc: float, active: Optional[dict]) -> bool:
        if active is None:
            return new_acc >= MIN_ACCURACY_PROMOTE
        return new_acc >= float(active["accuracy"]) - PROMOTE_TOLERANCE

    @staticmethod
    def _has_enough_per_class(samples) -> bool:
        from collections import Counter
        counts = Counter(s.true_symbol for s in samples)
        non_unknown = {k: v for k, v in counts.items() if k.value != "unknown"}
        if len(non_unknown) < 2:
            return False
        return all(v >= MIN_SAMPLES_PER_CLASS for v in non_unknown.values())

    def _count_labeled(self) -> int:
        return self.store.count_labeled_total()

    def _next_version_number(self) -> int:
        existing = self.store.list_model_versions()
        return (existing[0]["id"] + 1) if existing else 1
