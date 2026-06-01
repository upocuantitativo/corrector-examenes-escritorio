"""
Interface de usuario para verificar correcciones con baja confianza
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Callable
import cv2
from PIL import Image, ImageTk
import numpy as np
from correction_modes import CorrectionResult, ExamCorrection
from symbol_recognizer import CorrectionSymbol


class VerificationWindow:
    """Ventana para verificar y corregir resultados con baja confianza"""

    def __init__(self, parent: tk.Tk, correction: ExamCorrection,
                 on_verification_complete: Callable[[ExamCorrection], None]):
        """
        Inicializa la ventana de verificación

        Args:
            parent: Ventana padre
            correction: Corrección del examen a verificar
            on_verification_complete: Callback cuando se complete la verificación
        """
        self.parent = parent
        self.correction = correction
        self.on_complete = on_verification_complete

        self.current_index = 0
        self.items_to_verify = [correction.results[i] for i in correction.needs_verification]

        if not self.items_to_verify:
            # No hay nada que verificar
            self.on_complete(self.correction)
            return

        self.window = tk.Toplevel(parent)
        self.window.title("Verificación de Correcciones")
        self.window.geometry("800x600")

        self._create_widgets()
        self._show_current_item()

    def _create_widgets(self):
        """Crea los widgets de la interfaz"""
        # Frame superior: información del estudiante
        info_frame = ttk.Frame(self.window, padding="10")
        info_frame.pack(fill=tk.X)

        ttk.Label(info_frame, text=f"Estudiante: {self.correction.student_name}",
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        # Frame central: imagen y controles
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame de imagen con indicador de confianza
        image_container = tk.Frame(main_frame, relief=tk.RIDGE, borderwidth=3)
        image_container.pack(pady=10)

        self.image_label = ttk.Label(image_container)
        self.image_label.pack(padx=5, pady=5)

        # Información del ítem
        self.item_info_label = ttk.Label(main_frame, font=("Arial", 11))
        self.item_info_label.pack(pady=5)

        # Detección automática con barra de confianza
        detection_frame = ttk.Frame(main_frame)
        detection_frame.pack(pady=5)

        self.detection_label = ttk.Label(detection_frame, font=("Arial", 10))
        self.detection_label.pack()

        # Barra de confianza visual
        self.confidence_canvas = tk.Canvas(detection_frame, width=400, height=30)
        self.confidence_canvas.pack(pady=5)

        # Frame de botones de corrección
        correction_frame = ttk.LabelFrame(main_frame, text="Corrección Manual", padding="10")
        correction_frame.pack(pady=10)

        self.correction_var = tk.StringVar(value="check")

        options = [
            ("✓ Bien", "check", CorrectionSymbol.CHECK),
            ("~ Regular", "tilde", CorrectionSymbol.TILDE),
            ("X Mal", "cross", CorrectionSymbol.CROSS)
        ]

        for text, value, _ in options:
            ttk.Radiobutton(correction_frame, text=text, variable=self.correction_var,
                          value=value).pack(side=tk.LEFT, padx=10)

        # Frame inferior: navegación
        nav_frame = ttk.Frame(self.window, padding="10")
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.progress_label = ttk.Label(nav_frame, text="")
        self.progress_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(nav_frame, text="Anterior", command=self._previous_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Siguiente", command=self._next_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Finalizar Verificación", command=self._finish,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)

    def _show_current_item(self):
        """Muestra el ítem actual para verificación"""
        if self.current_index >= len(self.items_to_verify):
            self._finish()
            return

        result = self.items_to_verify[self.current_index]

        # Actualizar información del ítem
        self.item_info_label.config(
            text=f"Ítem {result.item.item_number}: {result.item.description}\n"
                 f"Peso: {result.item.weight:.2f} puntos"
        )

        # Actualizar detección automática
        detection_text = f"Detección automática: {self._symbol_to_text(result.symbol)}\n" \
                        f"Confianza: {result.confidence:.1%}"

        if result.confidence < 0.5:
            detection_text += " (BAJA - requiere verificación)"

        self.detection_label.config(text=detection_text)

        # Establecer valor predeterminado basado en la detección
        self.correction_var.set(result.symbol.value)

        # Mostrar imagen del ROI
        if result.roi_image is not None:
            self._show_image(result.roi_image)

        # Actualizar progreso
        self.progress_label.config(
            text=f"Verificando {self.current_index + 1} de {len(self.items_to_verify)}"
        )

    def _show_image(self, cv_image: np.ndarray):
        """
        Muestra una imagen de OpenCV en el label

        Args:
            cv_image: Imagen en formato OpenCV (BGR)
        """
        # Convertir de BGR a RGB
        if len(cv_image.shape) == 3:
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        else:
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2RGB)

        # Redimensionar si es necesario
        max_size = 400
        h, w = rgb_image.shape[:2]
        if h > max_size or w > max_size:
            scale = min(max_size / h, max_size / w)
            new_h, new_w = int(h * scale), int(w * scale)
            rgb_image = cv2.resize(rgb_image, (new_w, new_h))

        # Convertir a PhotoImage
        pil_image = Image.fromarray(rgb_image)
        photo = ImageTk.PhotoImage(pil_image)

        self.image_label.config(image=photo)
        self.image_label.image = photo  # Mantener referencia

    def _symbol_to_text(self, symbol: CorrectionSymbol) -> str:
        """Convierte un símbolo a texto"""
        mapping = {
            CorrectionSymbol.CHECK: "✓ Bien",
            CorrectionSymbol.TILDE: "~ Regular",
            CorrectionSymbol.CROSS: "X Mal",
            CorrectionSymbol.UNKNOWN: "? Desconocido"
        }
        return mapping.get(symbol, "?")

    def _text_to_symbol(self, text: str) -> CorrectionSymbol:
        """Convierte texto a símbolo"""
        mapping = {
            "check": CorrectionSymbol.CHECK,
            "tilde": CorrectionSymbol.TILDE,
            "cross": CorrectionSymbol.CROSS
        }
        return mapping.get(text, CorrectionSymbol.UNKNOWN)

    def _apply_correction(self):
        """Aplica la corrección manual al ítem actual"""
        result = self.items_to_verify[self.current_index]
        selected_symbol = self._text_to_symbol(self.correction_var.get())

        # Actualizar el resultado
        result.symbol = selected_symbol
        result.confidence = 1.0  # Corrección manual = 100% confianza

        # Recalcular puntuación
        symbol_values = {
            CorrectionSymbol.CHECK: 1.0,
            CorrectionSymbol.TILDE: 0.5,
            CorrectionSymbol.CROSS: 0.0
        }
        result.score = symbol_values.get(selected_symbol, 0.0) * result.item.weight

    def _next_item(self):
        """Avanza al siguiente ítem"""
        self._apply_correction()

        if self.current_index < len(self.items_to_verify) - 1:
            self.current_index += 1
            self._show_current_item()
        else:
            self._finish()

    def _previous_item(self):
        """Retrocede al ítem anterior"""
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current_item()

    def _finish(self):
        """Finaliza la verificación"""
        # Aplicar la última corrección
        if self.current_index < len(self.items_to_verify):
            self._apply_correction()

        # Recalcular puntuación total
        total_score = sum(r.score for r in self.correction.results)
        self.correction.total_score = total_score
        self.correction.percentage = (total_score / self.correction.max_score * 100) \
            if self.correction.max_score > 0 else 0

        # Limpiar la lista de verificación
        self.correction.needs_verification = []

        # Cerrar ventana y llamar callback
        self.window.destroy()
        self.on_complete(self.correction)


class ResultsWindow:
    """Ventana para mostrar los resultados finales de la corrección"""

    def __init__(self, parent: tk.Tk, correction: ExamCorrection,
                 on_save: Callable[[ExamCorrection], None]):
        """
        Inicializa la ventana de resultados

        Args:
            parent: Ventana padre
            correction: Corrección completada
            on_save: Callback para guardar los resultados
        """
        self.parent = parent
        self.correction = correction
        self.on_save = on_save

        self.window = tk.Toplevel(parent)
        self.window.title("Resultados de la Corrección")
        self.window.geometry("700x600")

        self._create_widgets()

    def _create_widgets(self):
        """Crea los widgets de la interfaz"""
        # Frame superior: información del estudiante
        header_frame = ttk.Frame(self.window, padding="10")
        header_frame.pack(fill=tk.X)

        ttk.Label(header_frame, text=f"Estudiante: {self.correction.student_name}",
                 font=("Arial", 14, "bold")).pack()

        # Frame de puntuación
        score_frame = ttk.LabelFrame(self.window, text="Puntuación Final", padding="10")
        score_frame.pack(fill=tk.X, padx=10, pady=10)

        score_text = f"Puntuación: {self.correction.total_score:.2f} / {self.correction.max_score:.2f}\n" \
                     f"Porcentaje: {self.correction.percentage:.1f}%"

        ttk.Label(score_frame, text=score_text, font=("Arial", 12)).pack()

        # Determinar calificación
        grade = self._calculate_grade(self.correction.percentage)
        ttk.Label(score_frame, text=f"Calificación: {grade}",
                 font=("Arial", 13, "bold")).pack(pady=5)

        # Frame de detalles
        details_frame = ttk.LabelFrame(self.window, text="Detalle por Ítem", padding="10")
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Crear tabla de resultados
        columns = ("Ítem", "Peso", "Símbolo", "Puntuación")
        tree = ttk.Treeview(details_frame, columns=columns, show="headings", height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor=tk.CENTER)

        # Añadir datos
        for result in self.correction.results:
            symbol_text = self._symbol_to_text(result.symbol)
            tree.insert("", tk.END, values=(
                result.item.item_number,
                f"{result.item.weight:.2f}",
                symbol_text,
                f"{result.score:.2f}"
            ))

        tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Botones
        button_frame = ttk.Frame(self.window, padding="10")
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(button_frame, text="Guardar Resultados", command=self._save_results,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cerrar", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def _symbol_to_text(self, symbol: CorrectionSymbol) -> str:
        """Convierte un símbolo a texto"""
        mapping = {
            CorrectionSymbol.CHECK: "✓ Bien",
            CorrectionSymbol.TILDE: "~ Regular",
            CorrectionSymbol.CROSS: "X Mal",
            CorrectionSymbol.UNKNOWN: "?"
        }
        return mapping.get(symbol, "?")

    def _calculate_grade(self, percentage: float) -> str:
        """
        Calcula la calificación basada en el porcentaje

        Args:
            percentage: Porcentaje obtenido

        Returns:
            Calificación en texto
        """
        if percentage >= 90:
            return "Sobresaliente"
        elif percentage >= 70:
            return "Notable"
        elif percentage >= 50:
            return "Aprobado"
        else:
            return "Suspenso"

    def _save_results(self):
        """Guarda los resultados"""
        self.on_save(self.correction)
        messagebox.showinfo("Guardado", "Los resultados se han guardado correctamente")
        self.window.destroy()
