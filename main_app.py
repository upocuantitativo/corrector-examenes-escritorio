"""
Aplicación principal - Sistema de Corrección de Exámenes con Reconocimiento de Imagen
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from typing import Optional, List
from datetime import datetime

from camera_handler import CameraHandler
from correction_modes import Mode1Corrector, Mode2Corrector, ExamItem, ExamCorrection
from correction_modes_improved import Mode1ImprovedCorrector, Mode3FullSheetCorrector, Mode4FileCorrector
from grade_calculator import GradeCalculator, GradeScale, ExamTemplate
from exam_database import ExamDatabase
from verification_ui import VerificationWindow, ResultsWindow
from verification_ui_improved import ImprovedVerificationWindow
from feedback_store import FeedbackStore
from hybrid_recognizer import HybridSymbolRecognizer
from ml_classifier import MLSymbolClassifier
from ml_model_window import MLModelWindow
from training_scheduler import TrainingScheduler
from student_database import StudentDatabase
from link_decisions import decide_link_on_save, decide_relink


class TemplateConfigWindow:
    """Ventana para configurar plantillas de examen (diseño de pesos)"""

    def __init__(self, parent: tk.Tk, on_save: callable):
        self.parent = parent
        self.on_save = on_save

        self.window = tk.Toplevel(parent)
        self.window.title("Configuración de Plantilla de Examen")
        self.window.geometry("700x600")

        self.template = ExamTemplate("Nueva Plantilla", max_score_scale=10.0)
        self.item_entries = []

        self._create_widgets()

    def _create_widgets(self):
        """Crea los widgets de la interfaz"""
        # Frame superior: información de la plantilla
        header_frame = ttk.LabelFrame(self.window, text="Información de la Plantilla", padding="10")
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Nombre:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.name_entry = ttk.Entry(header_frame, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        self.name_entry.insert(0, "Nueva Plantilla")

        ttk.Label(header_frame, text="Nota sobre:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.scale_entry = ttk.Entry(header_frame, width=10)
        self.scale_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.scale_entry.insert(0, "10")

        # Frame de ítems
        items_frame = ttk.LabelFrame(self.window, text="Ítems del Examen", padding="10")
        items_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollable frame
        canvas = tk.Canvas(items_frame)
        scrollbar = ttk.Scrollbar(items_frame, orient="vertical", command=canvas.yview)
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
        ttk.Label(self.scrollable_frame, text="Nº", font=("Arial", 10, "bold")).grid(
            row=0, column=0, padx=5, pady=5)
        ttk.Label(self.scrollable_frame, text="Descripción", font=("Arial", 10, "bold")).grid(
            row=0, column=1, padx=5, pady=5)
        ttk.Label(self.scrollable_frame, text="Peso", font=("Arial", 10, "bold")).grid(
            row=0, column=2, padx=5, pady=5)

        # Añadir 10 ítems por defecto
        for i in range(10):
            self._add_item_row(i + 1)

        # Botones
        button_frame = ttk.Frame(items_frame)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="+ Añadir Ítem", command=self._add_item).pack(side=tk.LEFT, padx=5)

        # Frame inferior: acciones
        action_frame = ttk.Frame(self.window, padding="10")
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.total_label = ttk.Label(action_frame, text="Peso total: 0.00", font=("Arial", 10, "bold"))
        self.total_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(action_frame, text="Calcular Total", command=self._update_total).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Guardar Plantilla", command=self._save_template,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_frame, text="Cargar Plantilla", command=self._load_template).pack(side=tk.RIGHT, padx=5)

    def _add_item_row(self, item_number: int):
        """Añade una fila para un ítem"""
        row = len(self.item_entries) + 1

        num_label = ttk.Label(self.scrollable_frame, text=str(item_number))
        num_label.grid(row=row, column=0, padx=5, pady=2)

        desc_entry = ttk.Entry(self.scrollable_frame, width=40)
        desc_entry.grid(row=row, column=1, padx=5, pady=2)

        weight_entry = ttk.Entry(self.scrollable_frame, width=10)
        weight_entry.grid(row=row, column=2, padx=5, pady=2)
        weight_entry.insert(0, "1.0")

        self.item_entries.append({
            'number': item_number,
            'label': num_label,
            'desc': desc_entry,
            'weight': weight_entry
        })

    def _add_item(self):
        """Añade un nuevo ítem"""
        next_number = len(self.item_entries) + 1
        self._add_item_row(next_number)

    def _update_total(self):
        """Actualiza el peso total"""
        total = 0.0
        for entry in self.item_entries:
            try:
                weight = float(entry['weight'].get())
                total += weight
            except ValueError:
                pass

        self.total_label.config(text=f"Peso total: {total:.2f}")

    def _save_template(self):
        """Guarda la plantilla"""
        try:
            name = self.name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Debes especificar un nombre para la plantilla")
                return

            scale = float(self.scale_entry.get())
            if scale <= 0:
                messagebox.showerror("Error", "La escala debe ser mayor que 0")
                return

            self.template = ExamTemplate(name, max_score_scale=scale)

            for entry in self.item_entries:
                try:
                    weight = float(entry['weight'].get())
                    if weight > 0:
                        self.template.add_item(
                            item_number=entry['number'],
                            weight=weight,
                            description=entry['desc'].get().strip()
                        )
                except ValueError:
                    continue

            if len(self.template.items) == 0:
                messagebox.showerror("Error", "Debes añadir al menos un ítem con peso válido")
                return

            # Guardar en archivo
            filepath = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=f"{name}.json"
            )

            if filepath:
                self.template.save(filepath)
                messagebox.showinfo("Éxito", f"Plantilla guardada en {filepath}")
                self.on_save(self.template)

        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar plantilla: {e}")

    def _load_template(self):
        """Carga una plantilla existente"""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not filepath:
            return

        template = ExamTemplate.load(filepath)
        if template:
            self.template = template
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, template.name)

            self.scale_entry.delete(0, tk.END)
            self.scale_entry.insert(0, str(template.max_score_scale))

            # Limpiar ítems actuales
            for entry in self.item_entries:
                entry['label'].destroy()
                entry['desc'].destroy()
                entry['weight'].destroy()
            self.item_entries.clear()

            # Cargar ítems de la plantilla
            for item in template.items:
                self._add_item_row(item['item_number'])
                self.item_entries[-1]['desc'].insert(0, item.get('description', ''))
                self.item_entries[-1]['weight'].delete(0, tk.END)
                self.item_entries[-1]['weight'].insert(0, str(item['weight']))

            self._update_total()
            messagebox.showinfo("Éxito", "Plantilla cargada correctamente")
        else:
            messagebox.showerror("Error", "No se pudo cargar la plantilla")


class ManualStudentPickerDialog:
    """
    Diálogo modal para que el profesor seleccione manualmente un alumno cuando
    el matching automático no encontró candidato (o fue rechazado).

    El resultado queda en `self.result`: dict del alumno elegido o None.
    """

    def __init__(self, parent: tk.Tk, student_db: "StudentDatabase",
                 detected_name: str, reason: str = ""):
        self.parent = parent
        self.student_db = student_db
        self.detected_name = detected_name
        self.result = None

        self.window = tk.Toplevel(parent)
        self.window.title("Vincular alumno manualmente")
        self.window.geometry("640x520")
        self.window.transient(parent)
        self.window.grab_set()

        header = ttk.Frame(self.window, padding="10")
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text="No se pudo vincular automáticamente el examen",
            font=("Arial", 12, "bold"),
        ).pack(anchor=tk.W)

        if reason:
            ttk.Label(header, text=reason, font=("Arial", 9), foreground="gray",
                     wraplength=600).pack(anchor=tk.W, pady=(2, 6))

        ttk.Label(header, text=f"Nombre detectado: {detected_name or '(vacío)'}",
                 font=("Arial", 10)).pack(anchor=tk.W)

        # Cuadro de búsqueda
        search_frame = ttk.Frame(self.window, padding="10")
        search_frame.pack(fill=tk.X)
        ttk.Label(search_frame, text="Buscar:").pack(side=tk.LEFT)
        self.query_var = tk.StringVar(value=detected_name or "")
        entry = ttk.Entry(search_frame, textvariable=self.query_var, width=50)
        entry.pack(side=tk.LEFT, padx=6)
        entry.focus_set()
        ttk.Button(search_frame, text="Buscar", command=self._search).pack(side=tk.LEFT)

        # Lista de resultados
        list_frame = ttk.Frame(self.window, padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("score", "id", "alumno", "dni"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("score", text="%")
        self.tree.heading("id", text="ID")
        self.tree.heading("alumno", text="Alumno")
        self.tree.heading("dni", text="DNI")
        self.tree.column("score", width=60, anchor=tk.CENTER)
        self.tree.column("id", width=80, anchor=tk.CENTER)
        self.tree.column("alumno", width=320, anchor=tk.W)
        self.tree.column("dni", width=100, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._accept())

        # Botones
        btn_frame = ttk.Frame(self.window, padding="10")
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Vincular", command=self._accept).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancelar (sin vincular)",
                  command=self._cancel).pack(side=tk.RIGHT)

        self._search()  # primer poblado con el nombre detectado
        self.window.wait_window()

    def _search(self):
        query = (self.query_var.get() or "").strip()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not query:
            return
        results = self.student_db.search_students(query)[:25]
        self._results_cache = results
        for student, score in results:
            self.tree.insert(
                "", tk.END,
                values=(
                    f"{score:.0f}",
                    student.get('Id', ''),
                    student.get('ALUMNO', ''),
                    student.get('DNI', ''),
                ),
            )

    def _accept(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona un alumno de la lista.")
            return
        idx = self.tree.index(sel[0])
        try:
            self.result = self._results_cache[idx][0]
        except (IndexError, AttributeError):
            self.result = None
        self.window.destroy()

    def _cancel(self):
        self.result = None
        self.window.destroy()


class HistoryWindow:
    """Ventana para ver el histórico de exámenes"""

    def __init__(self, parent: tk.Tk, database: ExamDatabase,
                 student_db: Optional["StudentDatabase"] = None):
        """
        `student_db` es opcional: si no se pasa, el botón "Re-vincular
        alumno" queda desactivado (no se puede buscar sin CSV).
        """
        self.parent = parent
        self.database = database
        self.student_db = student_db

        self.window = tk.Toplevel(parent)
        self.window.title("Histórico de Exámenes")
        self.window.geometry("980x600")

        self._create_widgets()
        self._load_exams()

    def _create_widgets(self):
        """Crea los widgets de la interfaz"""
        # Frame de búsqueda
        search_frame = ttk.LabelFrame(self.window, text="Búsqueda", padding="10")
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="Estudiante:").grid(row=0, column=0, padx=5, pady=5)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(search_frame, text="Buscar", command=self._search).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(search_frame, text="Ver Todos", command=self._load_exams).grid(row=0, column=3, padx=5, pady=5)

        # Frame de estadísticas
        stats_frame = ttk.LabelFrame(self.window, text="Estadísticas", padding="10")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.stats_label = ttk.Label(stats_frame, text="")
        self.stats_label.pack()

        # Tabla de exámenes
        table_frame = ttk.Frame(self.window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("ID", "Sid", "Estudiante", "Nota", "Calificación", "Fecha")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.column("ID", width=50, anchor=tk.CENTER)
        self.tree.column("Sid", width=70, anchor=tk.CENTER)
        self.tree.column("Estudiante", width=240)
        self.tree.column("Nota", width=80, anchor=tk.CENTER)
        self.tree.column("Calificación", width=140)
        self.tree.column("Fecha", width=140)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Botones
        button_frame = ttk.Frame(self.window, padding="10")
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(button_frame, text="Ver Detalles", command=self._view_details).pack(side=tk.LEFT, padx=5)
        self._relink_btn = ttk.Button(button_frame, text="Re-vincular alumno (Ctrl+R)",
                                      command=self._relink_student)
        self._relink_btn.pack(side=tk.LEFT, padx=5)
        if self.student_db is None:
            # Sin CSV no hay nada que buscar.
            self._relink_btn.state(["disabled"])
        else:
            # Atajo de teclado: Ctrl+R lanza el mismo flujo que el botón.
            # Solo se registra cuando el botón está activo para no engañar
            # al profesor con una tecla que no hace nada.
            self.window.bind("<Control-r>", self._on_relink_shortcut)
            self.window.bind("<Control-R>", self._on_relink_shortcut)
        ttk.Button(button_frame, text="Eliminar", command=self._delete_exam).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exportar a Excel", command=self._export).pack(side=tk.RIGHT, padx=5)

        self._update_statistics()

    def _load_exams(self):
        """Carga todos los exámenes"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        exams = self.database.get_all_exams()
        for exam in exams:
            date_str = exam['correction_date'][:16].replace('T', ' ')
            note = f"{exam['scaled_score']:.2f}" if exam['scaled_score'] else "-"
            grade = exam['literal_grade'] if exam['literal_grade'] else "-"
            sid = exam.get('student_id') or "-"

            self.tree.insert("", tk.END, values=(
                exam['id'],
                sid,
                exam['student_name'],
                note,
                grade,
                date_str
            ))

    def _search(self):
        """Busca exámenes por nombre"""
        search_term = self.search_entry.get().strip()

        for item in self.tree.get_children():
            self.tree.delete(item)

        exams = self.database.search_exams(student_name=search_term if search_term else None)
        for exam in exams:
            date_str = exam['correction_date'][:16].replace('T', ' ')
            note = f"{exam['scaled_score']:.2f}" if exam['scaled_score'] else "-"
            grade = exam['literal_grade'] if exam['literal_grade'] else "-"
            sid = exam.get('student_id') or "-"

            self.tree.insert("", tk.END, values=(
                exam['id'],
                sid,
                exam['student_name'],
                note,
                grade,
                date_str
            ))

    def _update_statistics(self):
        """Actualiza las estadísticas"""
        stats = self.database.get_statistics()
        text = f"Total: {stats['total_exams']} | " \
               f"Promedio: {stats['average_percentage']:.1f}% | " \
               f"Aprobados: {stats['passed']} | " \
               f"Suspensos: {stats['failed']}"
        self.stats_label.config(text=text)

    def _view_details(self):
        """Ver detalles de un examen"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecciona un examen")
            return

        exam_id = self.tree.item(selection[0])['values'][0]
        exam = self.database.get_exam_by_id(exam_id)

        if exam:
            details = f"Estudiante: {exam['student_name']}\n"
            details += f"Puntuación: {exam['total_score']:.2f} / {exam['max_score']:.2f}\n"
            details += f"Nota: {exam['scaled_score']:.2f}\n"
            details += f"Calificación: {exam['literal_grade']}\n"
            details += f"Fecha: {exam['correction_date'][:16].replace('T', ' ')}\n\n"
            details += "Detalles por ítem:\n"

            for item in exam['items']:
                details += f"  Ítem {item['item_number']}: {item['score']:.2f}/{item['weight']:.2f} ({item['symbol']})\n"

            messagebox.showinfo("Detalles del Examen", details)

    def _delete_exam(self):
        """Elimina un examen"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecciona un examen")
            return

        if not messagebox.askyesno("Confirmar", "¿Estás seguro de eliminar este examen?"):
            return

        exam_id = self.tree.item(selection[0])['values'][0]
        if self.database.delete_exam(exam_id):
            messagebox.showinfo("Éxito", "Examen eliminado")
            self._load_exams()
            self._update_statistics()
        else:
            messagebox.showerror("Error", "No se pudo eliminar el examen")

    def _on_relink_shortcut(self, event=None):
        """
        Handler de Ctrl+R. Solo dispara si el botón está habilitado
        (es decir, si hay `student_db`). Devuelve "break" para evitar
        que tkinter siga propagando el evento a otros widgets.
        """
        if self.student_db is None:
            return "break"
        self._relink_student()
        return "break"

    def _relink_student(self):
        """
        Re-vincula el alumno de un examen ya guardado.

        La parte deciscional la resuelve `link_decisions.decide_relink`;
        aquí solo manejamos:
          - Las validaciones tkinter previas (sin CSV / sin selección).
          - Los diálogos como callbacks puros que la decisión consume.
          - Aplicar la acción sobre `ExamDatabase.set_student_id` cuando la
            decisión así lo indica.
        """
        if self.student_db is None:
            messagebox.showwarning(
                "Sin BD de alumnos",
                "No hay alumnos.csv cargado, así que no se puede buscar."
            )
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecciona un examen")
            return

        exam_id = self.tree.item(selection[0])['values'][0]
        exam = self.database.get_exam_by_id(exam_id)
        if not exam:
            messagebox.showerror("Error", f"No se pudo recuperar el examen #{exam_id}")
            return

        action = decide_relink(
            exam=exam,
            manual_picker_prompt=self._relink_picker_dialog,
            confirm_unlink_prompt=self._confirm_unlink_dialog,
        )

        if action.kind == "manual":
            if self.database.set_student_id(exam_id, action.student_id):
                messagebox.showinfo("Re-vinculado", action.link_note)
                self._load_exams()
            else:
                messagebox.showerror("Error", "No se pudo actualizar la BD.")
        elif action.kind == "unlinked":
            if self.database.set_student_id(exam_id, None):
                messagebox.showinfo("Hecho", action.link_note)
                self._load_exams()
            else:
                messagebox.showerror("Error", "No se pudo actualizar la BD.")
        # kind == "noop" → nada que hacer, ni mensaje ni recarga.

    def _relink_picker_dialog(self, detected_name, reason):
        """Callback que abre el picker manual sobre la ventana de histórico."""
        picker = ManualStudentPickerDialog(
            self.window, self.student_db, detected_name, reason
        )
        return picker.result

    def _confirm_unlink_dialog(self, current_sid):
        """Callback Sí/No para confirmar desvinculación tras Cancel del picker."""
        return messagebox.askyesno(
            "Des-vincular alumno",
            f"¿Quieres des-vincular el examen (dejar student_id NULL)?\n"
            f"Estaba vinculado a {current_sid}."
        )

    def _export(self):
        """Exporta los exámenes a Excel"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"examenes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if filepath:
            if self.database.export_to_excel(filepath):
                messagebox.showinfo("Éxito", f"Exámenes exportados a {filepath}")
            else:
                messagebox.showerror("Error", "No se pudo exportar a Excel")


class MainApplication:
    """Aplicación principal"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Corrección de Exámenes")
        self.root.geometry("600x500")

        self.camera = None
        self.database = ExamDatabase()
        self.grade_calculator = GradeCalculator()
        self.current_template: Optional[ExamTemplate] = None

        # Cargar BD de alumnos una vez y compartirla en todas las correcciones.
        # Antes se reinstanciaba en cada _save_correction, leyendo el CSV.
        try:
            self.student_db: Optional[StudentDatabase] = StudentDatabase("alumnos.csv")
        except Exception as e:
            print(f"⚠️ No se pudo cargar alumnos.csv: {e}")
            self.student_db = None

        # Umbral mínimo de confianza para considerar la vinculación automática.
        # Por debajo, _save_correction pide confirmación manual al profesor.
        self.student_match_threshold: float = 75.0

        # --- Pipeline de aprendizaje iterativo ------------------------------
        # FeedbackStore comparte el mismo archivo SQLite que ExamDatabase, así
        # se conservan las tablas existentes y se añaden las nuevas en paralelo.
        self.feedback_store = FeedbackStore(db_path="examenes.db")
        self.ml_classifier = MLSymbolClassifier()
        self.training_scheduler = TrainingScheduler(
            store=self.feedback_store,
            models_dir="models",
            on_model_promoted=self._on_model_promoted,
        )
        # Si ya hay un modelo activo de sesiones anteriores, cárgalo.
        self.training_scheduler.try_load_active_into(self.ml_classifier)

        # Reconocedor híbrido único y compartido entre modos.
        self.recognizer = HybridSymbolRecognizer(
            feedback_store=self.feedback_store,
            ml_classifier=self.ml_classifier,
        )

        self._create_widgets()

    def _create_widgets(self):
        """Crea la interfaz principal"""
        # Header
        header_frame = ttk.Frame(self.root, padding="20")
        header_frame.pack(fill=tk.X)

        title = ttk.Label(header_frame, text="📝 Sistema de Corrección de Exámenes",
                         font=("Arial", 18, "bold"))
        title.pack()

        subtitle = ttk.Label(header_frame,
                            text="Reconocimiento automático con cámara",
                            font=("Arial", 11))
        subtitle.pack()

        # Main menu buttons
        menu_frame = ttk.Frame(self.root, padding="20")
        menu_frame.pack(expand=True)

        buttons = [
            ("📋 Diseño de Pesos", self._open_template_config, "Configurar plantillas de examen"),
            ("✏️ Corregir Examen", self._open_correction, "Corregir un examen con la cámara"),
            ("📊 Histórico", self._open_history, "Ver histórico de exámenes corregidos"),
            ("📤 Exportar Notas", self._export_grades, "Exportar notas de un examen a Excel"),
            ("🧠 Modelo ML", self._open_ml_model, "Inspeccionar y reentrenar el modelo de reconocimiento"),
            ("⚙️ Configuración", self._open_settings, "Configurar escala de calificación")
        ]

        for text, command, tooltip in buttons:
            btn = ttk.Button(menu_frame, text=text, command=command, width=30)
            btn.pack(pady=10)

            # Tooltip
            ttk.Label(menu_frame, text=tooltip, font=("Arial", 9), foreground="gray").pack()

        # Footer
        footer_frame = ttk.Frame(self.root, padding="10")
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(footer_frame, text="v1.0 - Sistema de Corrección Automática",
                 font=("Arial", 8), foreground="gray").pack()

    def _open_template_config(self):
        """Abre la configuración de plantillas"""
        TemplateConfigWindow(self.root, self._on_template_saved)

    def _on_template_saved(self, template: ExamTemplate):
        """Callback cuando se guarda una plantilla"""
        self.current_template = template
        messagebox.showinfo("Plantilla", f"Plantilla '{template.name}' lista para usar")

    def _open_correction(self):
        """Abre el proceso de corrección"""
        if not self.current_template:
            response = messagebox.askyesno(
                "Sin Plantilla",
                "No has cargado ninguna plantilla. ¿Deseas cargar una ahora?"
            )
            if response:
                filepath = filedialog.askopenfilename(
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                if filepath:
                    self.current_template = ExamTemplate.load(filepath)
                    if not self.current_template:
                        messagebox.showerror("Error", "No se pudo cargar la plantilla")
                        return
                else:
                    return
            else:
                return

        # Preguntar modo de corrección
        mode_window = tk.Toplevel(self.root)
        mode_window.title("Seleccionar Modo de Corrección")
        mode_window.geometry("600x550")

        ttk.Label(mode_window, text="Selecciona el modo de corrección:",
                 font=("Arial", 12, "bold")).pack(pady=20)

        selected_mode = tk.IntVar(value=1)

        # Modo 1 Mejorado (recomendado)
        frame1 = ttk.Frame(mode_window)
        frame1.pack(pady=5, padx=20, fill=tk.X)

        ttk.Radiobutton(frame1,
                       text="Modo 1 Mejorado: Detección continua (RECOMENDADO)",
                       variable=selected_mode,
                       value=1).pack(anchor=tk.W)
        ttk.Label(frame1, text="  • Detecta nombre automáticamente\n  • Captura símbolos sin salir de cámara\n  • Muestra feedback visual en tiempo real",
                 font=("Arial", 8), foreground="gray").pack(anchor=tk.W, padx=20)

        # Modo 2 Original (con cuadrícula)
        frame2 = ttk.Frame(mode_window)
        frame2.pack(pady=5, padx=20, fill=tk.X)

        ttk.Radiobutton(frame2,
                       text="Modo 2: Cuadrícula completa",
                       variable=selected_mode,
                       value=2).pack(anchor=tk.W)
        ttk.Label(frame2, text="  • Una foto de cuadrícula completa\n  • Detección automática por orden (izq→der, arriba→abajo)",
                 font=("Arial", 8), foreground="gray").pack(anchor=tk.W, padx=20)

        # Modo 3 Foto Completa (más rápido)
        frame3 = ttk.Frame(mode_window)
        frame3.pack(pady=5, padx=20, fill=tk.X)

        ttk.Radiobutton(frame3,
                       text="Modo 3: Foto completa con nombre (MÁS RÁPIDO)",
                       variable=selected_mode,
                       value=3).pack(anchor=tk.W)
        ttk.Label(frame3, text="  • Una sola foto de toda la hoja\n  • Detección automática de nombre y símbolos\n  • Ideal para corrección masiva",
                 font=("Arial", 8), foreground="gray").pack(anchor=tk.W, padx=20)

        # Modo 4 Imagen de archivo (sin cámara)
        frame4 = ttk.Frame(mode_window)
        frame4.pack(pady=5, padx=20, fill=tk.X)

        ttk.Radiobutton(frame4,
                       text="Modo 4: Cargar imagen de archivo (SIN CÁMARA)",
                       variable=selected_mode,
                       value=4).pack(anchor=tk.W)
        ttk.Label(frame4, text="  • Selecciona una foto o escaneo desde el disco\n  • No requiere cámara\n  • Mismo procesamiento que Modo 3",
                 font=("Arial", 8), foreground="gray").pack(anchor=tk.W, padx=20)

        # Campo para identificador del examen
        ttk.Label(mode_window, text="Identificador del Examen (Asignatura_Tema):",
                 font=("Arial", 10, "bold")).pack(pady=(10, 5))

        id_frame = ttk.Frame(mode_window)
        id_frame.pack(pady=5)

        exam_id_entry = ttk.Entry(id_frame, width=40, font=("Arial", 10))
        exam_id_entry.pack(side=tk.LEFT, padx=5)
        exam_id_entry.insert(0, "Matematicas_Tema1")  # Ejemplo por defecto

        ttk.Label(mode_window, text="Ejemplo: Matematicas_Tema1, Fisica_Parcial2, etc.",
                 font=("Arial", 8), foreground="gray").pack()

        def start_correction():
            mode = selected_mode.get()
            exam_identifier = exam_id_entry.get().strip()

            if not exam_identifier:
                messagebox.showwarning("Atención", "Por favor ingresa un identificador para el examen")
                return

            mode_window.destroy()
            self._start_correction_process(mode, exam_identifier)

        ttk.Button(mode_window, text="Iniciar Corrección", command=start_correction,
                  style="Accent.TButton").pack(pady=20)

    def _start_correction_process(self, mode: int, exam_identifier: str):
        """Inicia el proceso de corrección"""
        self.current_exam_identifier = exam_identifier
        items = self.current_template.get_items_for_correction()

        # Modo 4: imagen desde archivo, no necesita cámara
        if mode == 4:
            filepath = filedialog.askopenfilename(
                title="Seleccionar imagen del examen",
                filetypes=[
                    ("Imágenes", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif"),
                    ("JPEG", "*.jpg *.jpeg"),
                    ("PNG", "*.png"),
                    ("Todos los archivos", "*.*")
                ]
            )
            if not filepath:
                return

            corrector = Mode4FileCorrector(
                items, filepath, symbol_recognizer=self.recognizer,
            )
            correction = corrector.correct_exam()

            if correction.student_name in ("Cancelado", "Error al cargar imagen"):
                messagebox.showerror("Error", f"No se pudo procesar la imagen:\n{filepath}")
                return

            self._open_verification_window(correction, mode)
            return

        # Modos 1, 2, 3: necesitan cámara
        self.camera = CameraHandler(camera_index=0)
        if not self.camera.start():
            messagebox.showerror("Error", "No se pudo iniciar la cámara")
            return

        # Crear corrector según el modo (todos comparten el reconocedor híbrido)
        if mode == 1:
            corrector = Mode1ImprovedCorrector(
                self.camera, items, symbol_recognizer=self.recognizer,
            )
        elif mode == 3:
            corrector = Mode3FullSheetCorrector(
                self.camera, items, symbol_recognizer=self.recognizer,
            )
        else:  # mode == 2 — sin soporte de hybrid aún; usa heurística clásica
            num_items = len(items)
            cols = min(5, num_items)
            rows = (num_items + cols - 1) // cols
            corrector = Mode2Corrector(self.camera, items, grid_rows=rows, grid_cols=cols)

        correction = corrector.correct_exam()
        self.camera.stop()

        if correction.student_name == "Cancelado":
            return

        self._open_verification_window(correction, mode)

    def _open_verification_window(self, correction: ExamCorrection, mode: int):
        """Crea la ventana de verificación con el contexto de aprendizaje."""
        ImprovedVerificationWindow(
            self.root, correction,
            on_complete=lambda c: self._on_verification_complete(c, mode),
            feedback_store=self.feedback_store,
            training_scheduler=self.training_scheduler,
            active_model_info=self.feedback_store.get_active_model(),
        )

    def _on_model_promoted(self, model_path: str):
        """
        Callback del TrainingScheduler tras promover un modelo nuevo.
        Carga los pesos en el clasificador ML compartido — la siguiente corrección
        usará ya el modelo actualizado sin reiniciar la app.
        """
        try:
            self.ml_classifier.load(model_path)
            print(f"[MainApp] Modelo recargado en caliente: {model_path}")
        except Exception as e:
            print(f"[MainApp] Error recargando modelo: {e}")

    def _on_verification_complete(self, correction: ExamCorrection, mode: int):
        """Callback cuando se completa la verificación"""
        # Calcular calificación
        grade_info = self.grade_calculator.calculate_final_grade(
            correction.total_score,
            correction.max_score
        )

        # Mostrar resultados
        ResultsWindow(self.root, correction,
                     lambda c: self._save_correction(c, mode, grade_info))

    def _save_correction(self, correction: ExamCorrection, mode: int, grade_info: dict):
        """Guarda la corrección en la base de datos.

        La decisión de qué `student_id` queda y qué mensaje mostrar la toma
        `link_decisions.decide_link_on_save`. Aquí solo:
          1. Resolvemos el match contra `alumnos.csv`.
          2. Inyectamos los diálogos tkinter como callbacks puros.
          3. Persistimos lo que la decisión nos diga.
          4. Mostramos el mensaje de confirmación al profesor.
        """
        template_name = self.current_template.name if self.current_template else ""
        exam_identifier = getattr(self, 'current_exam_identifier', None)

        if self.student_db is None:
            resolve_result = ("unavailable", None, 0.0)
        else:
            resolve_result = self.student_db.resolve_link(
                correction.student_name, self.student_match_threshold
            )

        action = decide_link_on_save(
            detected_name=correction.student_name,
            resolve_result=resolve_result,
            low_confidence_prompt=self._low_confidence_dialog,
            manual_picker_prompt=self._manual_picker_dialog,
        )

        if action.kind == "matched":
            print(f"✅ {action.link_note}")
        elif action.kind == "unavailable":
            print(f"⚠️ {action.link_note}")

        self.database.save_correction(correction, template_name, mode, grade_info,
                                     student_id=action.student_id,
                                     exam_identifier=exam_identifier)

        msg = "Examen guardado en la base de datos\n"
        if exam_identifier:
            msg += f"Identificador: {exam_identifier}\n"
        if action.student_id:
            msg += f"ID Estudiante: {action.student_id}\n"
        else:
            msg += "⚠️ Sin alumno vinculado — el examen queda sin Id de alumno\n"
        if action.link_note:
            msg += action.link_note

        messagebox.showinfo("Guardado", msg)

    # --- Diálogos tkinter inyectables en decide_link_on_save / decide_relink #

    def _low_confidence_dialog(self, detected_name, candidate, confidence):
        """Pinta el messagebox Sí/No/Cancelar de baja confianza.

        Es el callback que `decide_link_on_save` invoca cuando el match cae
        en la rama "low". Devuelve True / False / None tal cual lo espera la
        firma `LowConfidencePrompt`.
        """
        suggested = candidate.get('ALUMNO', '?')
        suggested_id = candidate.get('Id', '?')
        prompt = (
            f"Nombre detectado en el examen:\n  '{detected_name}'\n\n"
            f"Mejor candidato encontrado (confianza {confidence:.0f}%):\n"
            f"  {suggested}  (ID {suggested_id})\n\n"
            "¿Aceptas vincular el examen con este alumno?\n\n"
            "• Sí → usar este candidato\n"
            "• No → buscar otro alumno manualmente\n"
            "• Cancelar → guardar sin alumno vinculado"
        )
        return messagebox.askyesnocancel("Confianza baja en el alumno", prompt)

    def _manual_picker_dialog(self, detected_name, reason):
        """Abre el `ManualStudentPickerDialog` y devuelve el alumno elegido.

        Si no hay CSV cargado, avisa y devuelve None — la decisión pura
        ya considera ese None como "sin alumno vinculado".
        """
        if self.student_db is None:
            messagebox.showwarning(
                "Sin alumno vinculado",
                f"{reason}\n\nNo hay alumnos.csv cargado, así que el examen "
                "queda sin Id de alumno."
            )
            return None

        picker = ManualStudentPickerDialog(
            self.root, self.student_db, detected_name, reason
        )
        return picker.result

    def _open_history(self):
        """Abre el histórico de exámenes"""
        HistoryWindow(self.root, self.database, student_db=self.student_db)

    def _open_ml_model(self):
        """Abre la ventana de gestión del modelo ML de reconocimiento de símbolos."""
        MLModelWindow(self.root, self.feedback_store, self.training_scheduler)

    def _export_grades(self):
        """Exporta las notas de un examen específico"""
        # Crear ventana de diálogo
        export_window = tk.Toplevel(self.root)
        export_window.title("Exportar Notas")
        export_window.geometry("500x300")

        ttk.Label(export_window, text="Exportar Notas a Excel",
                 font=("Arial", 14, "bold")).pack(pady=20)

        # Campo para identificador del examen
        ttk.Label(export_window, text="Identificador del Examen:",
                 font=("Arial", 10)).pack(pady=5)

        id_entry = ttk.Entry(export_window, width=40, font=("Arial", 10))
        id_entry.pack(pady=5)

        # Si hay un examen actual, pre-llenar
        if hasattr(self, 'current_exam_identifier') and self.current_exam_identifier:
            id_entry.insert(0, self.current_exam_identifier)

        # Información de ayuda
        ttk.Label(export_window, text="Ejemplos: Matematicas_Tema1, Fisica_Parcial2",
                 font=("Arial", 8), foreground="gray").pack()

        # Vista previa de cantidad
        preview_label = ttk.Label(export_window, text="",
                                 font=("Arial", 9), foreground="blue")
        preview_label.pack(pady=10)

        def update_preview(*args):
            exam_id = id_entry.get().strip()
            if exam_id:
                try:
                    exams = self.database.get_exams_by_identifier(exam_id)
                    count = len(exams)
                    if count > 0:
                        preview_label.config(
                            text=f"✅ Se encontraron {count} examen(es) con este identificador",
                            foreground="green"
                        )
                    else:
                        preview_label.config(
                            text=f"⚠️ No se encontraron exámenes con este identificador",
                            foreground="orange"
                        )
                except Exception as e:
                    preview_label.config(text=f"❌ Error: {e}", foreground="red")
            else:
                preview_label.config(text="")

        id_entry.bind('<KeyRelease>', update_preview)
        update_preview()  # Llamar inicialmente

        def do_export():
            exam_id = id_entry.get().strip()

            if not exam_id:
                messagebox.showwarning("Atención", "Por favor ingresa el identificador del examen")
                return

            # Pedir ubicación de archivo
            from tkinter import filedialog
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=f"{exam_id}_notas.xlsx"
            )

            if filepath:
                success = self.database.export_exam_grades(exam_id, filepath)
                if success:
                    messagebox.showinfo("Éxito",
                                      f"Notas exportadas correctamente a:\n{filepath}")
                    export_window.destroy()
                else:
                    messagebox.showerror("Error",
                                       "No se pudo exportar. Verifica que pandas esté instalado\n"
                                       "y que existan exámenes con ese identificador.")

        ttk.Button(export_window, text="Exportar a Excel", command=do_export,
                  style="Accent.TButton").pack(pady=20)

        ttk.Button(export_window, text="Cancelar",
                  command=export_window.destroy).pack()

    def _open_settings(self):
        """Abre la configuración de la escala de calificación"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Configuración de Calificación")
        settings_window.geometry("400x350")

        ttk.Label(settings_window, text="Escala de Calificación",
                 font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(settings_window, padding="20")
        frame.pack()

        # Puntuación máxima
        ttk.Label(frame, text="Nota sobre:").grid(row=0, column=0, sticky=tk.W, pady=5)
        max_scale_entry = ttk.Entry(frame, width=10)
        max_scale_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        max_scale_entry.insert(0, str(self.grade_calculator.scale.max_score))

        # Nota mínima para aprobar
        ttk.Label(frame, text="Nota mínima aprobado:").grid(row=1, column=0, sticky=tk.W, pady=5)
        pass_entry = ttk.Entry(frame, width=10)
        pass_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        pass_entry.insert(0, str(self.grade_calculator.scale.passing_score))

        # Umbrales (en %)
        ttk.Label(frame, text="Sobresaliente (%):").grid(row=2, column=0, sticky=tk.W, pady=5)
        excellent_entry = ttk.Entry(frame, width=10)
        excellent_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        excellent_entry.insert(0, str(self.grade_calculator.scale.excellent_threshold))

        ttk.Label(frame, text="Notable (%):").grid(row=3, column=0, sticky=tk.W, pady=5)
        good_entry = ttk.Entry(frame, width=10)
        good_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
        good_entry.insert(0, str(self.grade_calculator.scale.good_threshold))

        ttk.Label(frame, text="Aprobado (%):").grid(row=4, column=0, sticky=tk.W, pady=5)
        pass_pct_entry = ttk.Entry(frame, width=10)
        pass_pct_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        pass_pct_entry.insert(0, str(self.grade_calculator.scale.pass_threshold))

        def save_settings():
            try:
                max_score = float(max_scale_entry.get())
                passing_score = float(pass_entry.get())
                excellent = float(excellent_entry.get())
                good = float(good_entry.get())
                pass_pct = float(pass_pct_entry.get())

                self.grade_calculator.set_scale(max_score, passing_score, excellent, good, pass_pct)
                messagebox.showinfo("Éxito", "Configuración guardada")
                settings_window.destroy()
            except ValueError:
                messagebox.showerror("Error", "Valores inválidos")

        ttk.Button(frame, text="Guardar", command=save_settings,
                  style="Accent.TButton").grid(row=5, column=0, columnspan=2, pady=20)

    def run(self):
        """Ejecuta la aplicación"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MainApplication()
    app.run()
