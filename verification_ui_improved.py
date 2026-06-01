"""
Ventana de verificación y edición mejorada.

Cambios respecto a la versión previa:
  - Bug fix: los enums correctos son CHECK / TILDE / CROSS (no CORRECT / PARTIAL / INCORRECT).
  - Escala de confianza correcta: 0-1 internamente, se muestra como %.
  - Captura de feedback iterativo: cuando el profesor confirma o cambia un símbolo,
    se persiste en `FeedbackStore` y se notifica al `TrainingScheduler` (si se inyectan).
  - Indicador del modelo ML activo en la barra inferior.
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, List, Optional

from correction_modes import CorrectionResult, ExamCorrection
from symbol_recognizer import CorrectionSymbol


# Mapeo único símbolo ↔ etiqueta interna para los radio buttons
_SYMBOL_BUTTONS = [
    (CorrectionSymbol.CHECK, "✓", "Bien", "green"),
    (CorrectionSymbol.TILDE, "~", "Regular", "orange"),
    (CorrectionSymbol.CROSS, "X", "Mal", "red"),
]


class ImprovedVerificationWindow:
    """
    Ventana para verificar y editar TODOS los resultados.
    Cada cambio del profesor alimenta el feedback store (si está inyectado),
    permitiendo el reentrenamiento iterativo del modelo ML.
    """

    def __init__(
        self,
        parent: tk.Tk,
        correction: ExamCorrection,
        on_complete: Callable[[ExamCorrection], None],
        feedback_store=None,
        training_scheduler=None,
        active_model_info: Optional[dict] = None,
    ):
        self.parent = parent
        self.correction = correction
        self.on_complete = on_complete
        self.feedback_store = feedback_store
        self.training_scheduler = training_scheduler
        self.active_model_info = active_model_info

        # Snapshot de los símbolos originales (para detectar cambios al confirmar)
        self._original_symbols: List[CorrectionSymbol] = [
            r.symbol for r in correction.results
        ]

        self.window = tk.Toplevel(parent)
        self.window.title("Verificación y Edición de Resultados")
        self.window.geometry("950x720")
        self.window.grab_set()

        self._row_buttons: List[dict] = []  # botones por fila, para refrescar estilo

        self._create_widgets()
        self._load_results()

    # ------------------------------------------------------------------ #
    # Layout                                                              #
    # ------------------------------------------------------------------ #

    def _create_widgets(self):
        # Header
        header = ttk.Frame(self.window, padding="15")
        header.pack(fill=tk.X)
        ttk.Label(header, text="📋 Verificación de Examen",
                  font=("Arial", 16, "bold")).pack()
        ttk.Label(header, text=f"Estudiante: {self.correction.student_name}",
                  font=("Arial", 12)).pack(pady=5)

        # Tabla scrollable
        table_frame = ttk.Frame(self.window, padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(table_frame, bg="white")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Encabezados
        headers = ["#", "Ítem", "Peso", "Detectado", "Confianza", "Editar"]
        header_row = ttk.Frame(self.scrollable_frame)
        header_row.pack(fill=tk.X, pady=(0, 10))
        for h in headers:
            ttk.Label(header_row, text=h, font=("Arial", 10, "bold"),
                      width=14, anchor="center").pack(side=tk.LEFT, padx=5)
        ttk.Separator(self.scrollable_frame, orient="horizontal").pack(fill=tk.X, pady=5)

        # Footer
        footer = ttk.Frame(self.window, padding="15")
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        summary_row = ttk.Frame(footer)
        summary_row.pack(fill=tk.X, pady=(0, 6))
        self.summary_label = ttk.Label(summary_row, font=("Arial", 11, "bold"))
        self.summary_label.pack(side=tk.LEFT)
        self.grade_label = ttk.Label(summary_row, font=("Arial", 12, "bold"),
                                     foreground="blue")
        self.grade_label.pack(side=tk.RIGHT)

        # Línea de estado del modelo
        self.model_label = ttk.Label(footer, font=("Arial", 9), foreground="gray")
        self.model_label.pack(fill=tk.X, pady=(0, 8))
        self._update_model_status_label()

        # Botones
        btns = ttk.Frame(footer)
        btns.pack()
        ttk.Button(btns, text="🔄 Recalcular",
                   command=self._recalculate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="✅ Confirmar y Guardar",
                   command=self._confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="❌ Cancelar",
                   command=self._cancel).pack(side=tk.LEFT, padx=5)

    def _update_model_status_label(self):
        if not self.active_model_info:
            self.model_label.config(
                text="🧠 Modelo ML: aún sin entrenar — cada corrección que confirmes "
                     "alimentará el primer entrenamiento."
            )
            return
        info = self.active_model_info
        acc = info.get("accuracy", 0.0)
        n = info.get("n_samples", 0)
        self.model_label.config(
            text=f"🧠 Modelo ML activo: v{info.get('id')}  •  "
                 f"accuracy={acc:.1%}  •  entrenado con {n} muestras"
        )

    # ------------------------------------------------------------------ #
    # Filas                                                                #
    # ------------------------------------------------------------------ #

    def _load_results(self):
        for idx, result in enumerate(self.correction.results):
            self._create_result_row(idx, result)
        self._update_summary()

    def _create_result_row(self, idx: int, result: CorrectionResult):
        row = ttk.Frame(self.scrollable_frame)
        row.pack(fill=tk.X, pady=3)
        bg = "#f0f0f0" if idx % 2 == 0 else "#ffffff"

        tk.Label(row, text=str(result.item.item_number),
                 width=6, anchor="center", bg=bg).pack(side=tk.LEFT, padx=5)

        desc = result.item.description or f"Pregunta {result.item.item_number}"
        tk.Label(row, text=desc[:30],
                 width=32, anchor="w", bg=bg).pack(side=tk.LEFT, padx=5)

        tk.Label(row, text=f"{result.item.weight:.1f}",
                 width=10, anchor="center", bg=bg).pack(side=tk.LEFT, padx=5)

        tk.Label(row, text=self._symbol_display(result.symbol),
                 width=15, anchor="center", bg=bg,
                 font=("Arial", 11)).pack(side=tk.LEFT, padx=5)

        # Confianza con color por umbral (escala 0-1)
        conf = float(result.confidence)
        if conf >= 0.7:
            conf_color = "green"
        elif conf >= 0.4:
            conf_color = "orange"
        else:
            conf_color = "red"
        tk.Label(row, text=f"{conf * 100:.0f}%",
                 width=12, anchor="center", bg=bg,
                 fg=conf_color, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # Botones de edición
        edit = tk.Frame(row, bg=bg)
        edit.pack(side=tk.LEFT, padx=5)
        button_refs = {}
        for sym, char, _label, color in _SYMBOL_BUTTONS:
            is_selected = (result.symbol == sym)
            btn = tk.Button(
                edit, text=char, width=3, height=1,
                bg=color if is_selected else "lightgray",
                fg="white" if is_selected else "black",
                font=("Arial", 10, "bold"),
                command=lambda s=sym, i=idx: self._change_symbol(i, s),
            )
            btn.pack(side=tk.LEFT, padx=2)
            button_refs[sym] = (btn, color)

        self._row_buttons.append(button_refs)

    # ------------------------------------------------------------------ #
    # Mutaciones                                                           #
    # ------------------------------------------------------------------ #

    def _change_symbol(self, idx: int, new_symbol: CorrectionSymbol):
        result = self.correction.results[idx]
        result.symbol = new_symbol
        result.score = self._score_for(new_symbol, result.item.weight)
        self._refresh_row_buttons(idx)
        self._update_summary()

    def _refresh_row_buttons(self, idx: int):
        if idx >= len(self._row_buttons):
            return
        current = self.correction.results[idx].symbol
        for sym, (btn, color) in self._row_buttons[idx].items():
            selected = (sym == current)
            btn.config(
                bg=color if selected else "lightgray",
                fg="white" if selected else "black",
            )

    @staticmethod
    def _score_for(symbol: CorrectionSymbol, weight: float) -> float:
        if symbol == CorrectionSymbol.CHECK:
            return weight
        if symbol == CorrectionSymbol.TILDE:
            return weight * 0.5
        return 0.0

    @staticmethod
    def _symbol_display(symbol: CorrectionSymbol) -> str:
        return {
            CorrectionSymbol.CHECK: "✓ (Bien)",
            CorrectionSymbol.TILDE: "~ (Regular)",
            CorrectionSymbol.CROSS: "X (Mal)",
        }.get(symbol, "? (Desconocido)")

    # ------------------------------------------------------------------ #
    # Resumen                                                              #
    # ------------------------------------------------------------------ #

    def _update_summary(self):
        total = sum(r.score for r in self.correction.results)
        max_score = sum(r.item.weight for r in self.correction.results)
        pct = (total / max_score * 100) if max_score > 0 else 0
        self.correction.total_score = total
        self.correction.max_score = max_score
        self.correction.percentage = pct
        self.summary_label.config(
            text=f"Puntuación: {total:.2f} / {max_score:.2f} ({pct:.1f}%)"
        )
        if pct >= 90:
            grade, color = "Sobresaliente", "darkgreen"
        elif pct >= 70:
            grade, color = "Notable", "green"
        elif pct >= 50:
            grade, color = "Aprobado", "blue"
        else:
            grade, color = "Suspenso", "red"
        self.grade_label.config(text=f"Calificación: {grade}", foreground=color)

    # ------------------------------------------------------------------ #
    # Acciones de botón                                                    #
    # ------------------------------------------------------------------ #

    def _recalculate(self):
        self._update_summary()
        messagebox.showinfo("Recalculado", "Puntuaciones recalculadas correctamente")

    def _confirm(self):
        ok = messagebox.askyesno(
            "Confirmar",
            f"¿Confirmar resultados?\n\n"
            f"Estudiante: {self.correction.student_name}\n"
            f"Puntuación: {self.correction.total_score:.2f}/{self.correction.max_score:.2f}\n"
            f"Porcentaje: {self.correction.percentage:.1f}%"
        )
        if not ok:
            return
        self._persist_feedback()
        self.window.destroy()
        self.on_complete(self.correction)

    def _cancel(self):
        if messagebox.askyesno("Cancelar", "¿Seguro que deseas cancelar?"):
            self.window.destroy()

    # ------------------------------------------------------------------ #
    # Feedback iterativo                                                   #
    # ------------------------------------------------------------------ #

    def _persist_feedback(self):
        """
        Para cada ítem con `sample_id`, marca el símbolo definitivo en la BD.
        - Si el profesor cambió la predicción → source="manual_correction"
        - Si la mantuvo (independientemente de la confianza) → "manual_confirm"
        Luego notifica al scheduler para que evalúe reentrenar.
        """
        if self.feedback_store is None:
            return

        recorded = 0
        for idx, result in enumerate(self.correction.results):
            if result.sample_id is None:
                continue
            try:
                if idx < len(self._original_symbols) and \
                        result.symbol != self._original_symbols[idx]:
                    source = "manual_correction"
                else:
                    source = "manual_confirm"
                self.feedback_store.record_correction(
                    sample_id=result.sample_id,
                    corrected=result.symbol,
                    source=source,
                )
                recorded += 1
            except Exception as e:
                print(f"[VerificationUI] No se pudo persistir feedback "
                      f"para sample {result.sample_id}: {e}")

        if recorded and self.training_scheduler is not None:
            launched = self.training_scheduler.notify_correction_committed()
            if launched:
                print(f"[VerificationUI] {recorded} feedbacks guardados → "
                      f"reentrenamiento ML iniciado en background.")
            else:
                print(f"[VerificationUI] {recorded} feedbacks guardados "
                      f"(aún sin alcanzar el umbral de reentrenamiento).")
