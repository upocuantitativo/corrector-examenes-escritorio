"""
Ventana para inspeccionar y gestionar el modelo ML de reconocimiento de símbolos.

Muestra:
  - Modelo activo (versión, accuracy, número de muestras de entrenamiento)
  - Histórico de versiones entrenadas
  - Resumen de errores (matriz de confusión a partir de correction_events)
  - Conteo de muestras etiquetadas disponibles

Permite:
  - Forzar un reentrenamiento inmediato (útil tras corregir varios exámenes)
  - Refrescar la vista sin reiniciar la app
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from feedback_store import FeedbackStore
from training_scheduler import (
    MIN_SAMPLES_FIRST_TRAIN,
    MIN_SAMPLES_PER_CLASS,
    TrainingScheduler,
)


class MLModelWindow:
    """Ventana modal de gestión del modelo ML."""

    def __init__(
        self,
        parent: tk.Tk,
        feedback_store: FeedbackStore,
        training_scheduler: TrainingScheduler,
    ):
        self.parent = parent
        self.store = feedback_store
        self.scheduler = training_scheduler

        self.window = tk.Toplevel(parent)
        self.window.title("Modelo ML — Aprendizaje iterativo")
        self.window.geometry("700x620")
        self.window.grab_set()

        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------ #
    # UI                                                                   #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.window, padding="15")
        header.pack(fill=tk.X)
        ttk.Label(header, text="🧠 Modelo ML de Reconocimiento",
                  font=("Arial", 16, "bold")).pack()
        ttk.Label(header,
                  text="Las correcciones que confirmas alimentan al modelo "
                       "para que mejore con cada examen.",
                  font=("Arial", 9), foreground="gray").pack(pady=4)

        # Estado actual
        active_frame = ttk.LabelFrame(self.window, text="Estado actual",
                                       padding="10")
        active_frame.pack(fill=tk.X, padx=15, pady=8)
        self.active_label = ttk.Label(active_frame, font=("Arial", 10),
                                       justify=tk.LEFT)
        self.active_label.pack(anchor=tk.W)

        # Muestras
        samples_frame = ttk.LabelFrame(self.window, text="Muestras de entrenamiento",
                                        padding="10")
        samples_frame.pack(fill=tk.X, padx=15, pady=8)
        self.samples_label = ttk.Label(samples_frame, font=("Arial", 10),
                                        justify=tk.LEFT)
        self.samples_label.pack(anchor=tk.W)

        # Histórico de versiones
        history_frame = ttk.LabelFrame(self.window, text="Histórico de versiones",
                                        padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)

        cols = ("v", "acc", "n", "fecha", "estado")
        self.tree = ttk.Treeview(history_frame, columns=cols, show="headings",
                                  height=6)
        self.tree.heading("v", text="Versión")
        self.tree.heading("acc", text="Accuracy")
        self.tree.heading("n", text="Muestras")
        self.tree.heading("fecha", text="Fecha")
        self.tree.heading("estado", text="Estado")
        self.tree.column("v", width=70, anchor="center")
        self.tree.column("acc", width=90, anchor="center")
        self.tree.column("n", width=90, anchor="center")
        self.tree.column("fecha", width=180, anchor="center")
        self.tree.column("estado", width=110, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(history_frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Resumen de errores
        confusion_frame = ttk.LabelFrame(self.window, text="Errores frecuentes recientes",
                                          padding="10")
        confusion_frame.pack(fill=tk.X, padx=15, pady=8)
        self.confusion_label = ttk.Label(confusion_frame, font=("Arial", 10),
                                          justify=tk.LEFT)
        self.confusion_label.pack(anchor=tk.W)

        # Acciones
        actions = ttk.Frame(self.window, padding="15")
        actions.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(actions, font=("Arial", 9),
                                       foreground="gray")
        self.status_label.pack(side=tk.LEFT)
        ttk.Button(actions, text="🔄 Refrescar",
                   command=self._refresh).pack(side=tk.RIGHT, padx=5)
        self.retrain_btn = ttk.Button(
            actions, text="🚀 Reentrenar ahora",
            command=self._force_retrain,
        )
        self.retrain_btn.pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions, text="Cerrar",
                   command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    # ------------------------------------------------------------------ #
    # Datos                                                                #
    # ------------------------------------------------------------------ #

    def _refresh(self):
        # Estado activo
        active = self.store.get_active_model()
        if active:
            txt = (
                f"Versión activa: v{active['id']}\n"
                f"Accuracy:       {active['accuracy']:.1%}\n"
                f"Entrenado con:  {active['n_samples']} muestras\n"
                f"Fecha:          {active['trained_at'][:19].replace('T', ' ')}"
            )
        else:
            txt = ("Aún no hay modelo entrenado.\n"
                   f"Necesitas al menos {MIN_SAMPLES_FIRST_TRAIN} muestras totales "
                   f"y {MIN_SAMPLES_PER_CLASS} por clase para crear el primero.")
        self.active_label.config(text=txt)

        # Muestras
        total = self.store.count_labeled_total()
        self.samples_label.config(
            text=f"Etiquetadas totales:        {total}\n"
                 f"Umbral próximo reentreno:  cada "
                 f"{self.scheduler.retrain_every_n_new} correcciones nuevas"
        )

        # Histórico
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)
        for v in self.store.list_model_versions():
            self.tree.insert("", tk.END, values=(
                f"v{v['id']}",
                f"{v['accuracy']:.1%}",
                v['n_samples'],
                v['trained_at'][:19].replace('T', ' '),
                "activo" if v['is_active'] else "inactivo",
            ))

        # Confusión
        confusion = self.store.get_confusion_summary()
        if confusion:
            top = sorted(confusion.items(), key=lambda kv: kv[1], reverse=True)[:6]
            lines = [f"  · {k}:  {v}" for k, v in top]
            self.confusion_label.config(
                text="Predicción del modelo → corrección del profesor:\n"
                     + "\n".join(lines)
            )
        else:
            self.confusion_label.config(
                text="Aún no se han registrado correcciones manuales discrepantes."
            )

        self._update_status()

    def _update_status(self):
        if self.scheduler.is_training:
            self.status_label.config(text="⏳ Entrenamiento en curso…",
                                      foreground="darkorange")
            self.retrain_btn.config(state=tk.DISABLED)
            # Reintenta refrescar el estado mientras dura el entrenamiento
            self.window.after(800, self._update_status_tick)
        else:
            self.status_label.config(text="", foreground="gray")
            self.retrain_btn.config(state=tk.NORMAL)

    def _update_status_tick(self):
        """Polling ligero para detectar fin del entrenamiento sin bloquear UI."""
        if self.scheduler.is_training:
            self.window.after(800, self._update_status_tick)
            return
        # Acabó: refrescamos métricas completas
        self._refresh()
        messagebox.showinfo(
            "Entrenamiento finalizado",
            "El entrenamiento terminó. Revisa la nueva versión en el histórico."
        )

    # ------------------------------------------------------------------ #
    # Acciones                                                             #
    # ------------------------------------------------------------------ #

    def _force_retrain(self):
        total = self.store.count_labeled_total()
        if total < MIN_SAMPLES_FIRST_TRAIN:
            messagebox.showwarning(
                "Muestras insuficientes",
                f"Necesitas al menos {MIN_SAMPLES_FIRST_TRAIN} muestras etiquetadas "
                f"(actualmente hay {total}).\n\n"
                "Corrige unos cuantos exámenes más y vuelve a intentarlo."
            )
            return
        if not messagebox.askyesno(
            "Reentrenar modelo",
            f"Se va a reentrenar el modelo ML con las {total} muestras disponibles.\n"
            "Esto sucederá en segundo plano (no bloquea la app).\n\n¿Continuar?"
        ):
            return
        launched = self.scheduler.force_retrain()
        if not launched:
            messagebox.showinfo(
                "Sin cambios",
                "Ya hay un entrenamiento en curso o no se cumplieron las "
                "condiciones mínimas (≥2 clases con ejemplos suficientes)."
            )
            return
        self._update_status()
