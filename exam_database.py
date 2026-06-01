"""
Base de datos para almacenar histórico de exámenes corregidos
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import sqlite3
import json
from typing import List, Optional, Dict
from datetime import datetime
from correction_modes import ExamCorrection, CorrectionResult
import os


class ExamDatabase:
    """Maneja el almacenamiento y recuperación de exámenes corregidos"""

    def __init__(self, db_path: str = "examenes.db"):
        """
        Inicializa la base de datos

        Args:
            db_path: Ruta del archivo de base de datos
        """
        self.db_path = db_path
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self):
        """Crea las tablas necesarias si no existen"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de exámenes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                student_name TEXT NOT NULL,
                student_name_confidence REAL,
                total_score REAL NOT NULL,
                max_score REAL NOT NULL,
                percentage REAL NOT NULL,
                scaled_score REAL,
                literal_grade TEXT,
                correction_date TEXT NOT NULL,
                exam_template TEXT,
                exam_identifier TEXT,
                mode INTEGER NOT NULL
            )
        """)

        # Tabla de resultados por ítem
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exam_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                item_number INTEGER NOT NULL,
                weight REAL NOT NULL,
                description TEXT,
                symbol TEXT NOT NULL,
                confidence REAL NOT NULL,
                score REAL NOT NULL,
                FOREIGN KEY (exam_id) REFERENCES exams (id)
            )
        """)

        conn.commit()
        conn.close()

    def _migrate_schema(self):
        """
        Migra esquemas de BD antiguas: añade columnas que se incorporaron
        después de la creación inicial (`student_id`, `exam_identifier`).

        `CREATE TABLE IF NOT EXISTS` no altera tablas ya existentes, por lo
        que sin esta migración los `INSERT/SELECT` con esas columnas fallan
        en instalaciones que tienen `examenes.db` de versiones previas.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            existing_cols = {
                row[1] for row in cursor.execute("PRAGMA table_info(exams)")
            }

            migrations = [
                ("student_id", "ALTER TABLE exams ADD COLUMN student_id TEXT"),
                ("exam_identifier", "ALTER TABLE exams ADD COLUMN exam_identifier TEXT"),
            ]

            for column, ddl in migrations:
                if column not in existing_cols:
                    cursor.execute(ddl)
                    print(f"[ExamDatabase] Migración: añadida columna '{column}'")

            # Índices útiles para consultas frecuentes (idempotentes)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_exams_identifier ON exams (exam_identifier)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_exams_student_id ON exams (student_id)"
            )
            conn.commit()
        finally:
            conn.close()

    def save_correction(self, correction: ExamCorrection, exam_template: str = "",
                       mode: int = 1, grade_info: Optional[Dict] = None,
                       student_id: Optional[str] = None,
                       exam_identifier: Optional[str] = None) -> int:
        """
        Guarda una corrección en la base de datos

        Args:
            correction: Corrección del examen
            exam_template: Nombre de la plantilla utilizada
            mode: Modo de corrección (1 o 2)
            grade_info: Información de calificación calculada
            student_id: ID del estudiante de la base de datos
            exam_identifier: Identificador del examen (Asignatura_Tema)

        Returns:
            ID del examen guardado
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insertar examen
        cursor.execute("""
            INSERT INTO exams (
                student_id, student_name, student_name_confidence, total_score, max_score,
                percentage, scaled_score, literal_grade, correction_date,
                exam_template, exam_identifier, mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            student_id,
            correction.student_name,
            correction.student_name_confidence,
            correction.total_score,
            correction.max_score,
            correction.percentage,
            grade_info['scaled_score'] if grade_info else None,
            grade_info['literal_grade'] if grade_info else None,
            datetime.now().isoformat(),
            exam_template,
            exam_identifier,
            mode
        ))

        exam_id = cursor.lastrowid

        # Insertar ítems
        for result in correction.results:
            cursor.execute("""
                INSERT INTO exam_items (
                    exam_id, item_number, weight, description, symbol,
                    confidence, score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                exam_id,
                result.item.item_number,
                result.item.weight,
                result.item.description,
                result.symbol.value,
                result.confidence,
                result.score
            ))

        conn.commit()
        conn.close()

        return exam_id

    def get_all_exams(self, limit: int = 100) -> List[Dict]:
        """
        Obtiene todos los exámenes

        Args:
            limit: Número máximo de exámenes a obtener

        Returns:
            Lista de diccionarios con información de exámenes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, student_id, student_name, total_score, max_score, percentage,
                   scaled_score, literal_grade, correction_date, exam_template, exam_identifier, mode
            FROM exams
            ORDER BY correction_date DESC
            LIMIT ?
        """, (limit,))

        columns = [desc[0] for desc in cursor.description]
        exams = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return exams

    def get_exam_by_id(self, exam_id: int) -> Optional[Dict]:
        """
        Obtiene un examen por su ID con todos sus ítems

        Args:
            exam_id: ID del examen

        Returns:
            Diccionario con la información completa del examen
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Obtener examen
        cursor.execute("""
            SELECT id, student_id, student_name, student_name_confidence, total_score, max_score,
                   percentage, scaled_score, literal_grade, correction_date,
                   exam_template, exam_identifier, mode
            FROM exams
            WHERE id = ?
        """, (exam_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        columns = [desc[0] for desc in cursor.description]
        exam = dict(zip(columns, row))

        # Obtener ítems
        cursor.execute("""
            SELECT item_number, weight, description, symbol, confidence, score
            FROM exam_items
            WHERE exam_id = ?
            ORDER BY item_number
        """, (exam_id,))

        item_columns = [desc[0] for desc in cursor.description]
        exam['items'] = [dict(zip(item_columns, item_row)) for item_row in cursor.fetchall()]

        conn.close()
        return exam

    def search_exams(self, student_name: Optional[str] = None,
                     min_percentage: Optional[float] = None,
                     max_percentage: Optional[float] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> List[Dict]:
        """
        Busca exámenes con filtros

        Args:
            student_name: Nombre del estudiante (búsqueda parcial)
            min_percentage: Porcentaje mínimo
            max_percentage: Porcentaje máximo
            start_date: Fecha de inicio (ISO format)
            end_date: Fecha de fin (ISO format)

        Returns:
            Lista de exámenes que cumplen los criterios
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT id, student_id, student_name, total_score, max_score, percentage,
                   scaled_score, literal_grade, correction_date, exam_template, exam_identifier, mode
            FROM exams
            WHERE 1=1
        """
        params = []

        if student_name:
            query += " AND student_name LIKE ?"
            params.append(f"%{student_name}%")

        if min_percentage is not None:
            query += " AND percentage >= ?"
            params.append(min_percentage)

        if max_percentage is not None:
            query += " AND percentage <= ?"
            params.append(max_percentage)

        if start_date:
            query += " AND correction_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND correction_date <= ?"
            params.append(end_date)

        query += " ORDER BY correction_date DESC"

        cursor.execute(query, params)

        columns = [desc[0] for desc in cursor.description]
        exams = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return exams

    def get_statistics(self) -> Dict:
        """
        Obtiene estadísticas generales

        Returns:
            Diccionario con estadísticas
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total de exámenes
        cursor.execute("SELECT COUNT(*) FROM exams")
        stats['total_exams'] = cursor.fetchone()[0]

        # Promedio general
        cursor.execute("SELECT AVG(percentage) FROM exams")
        result = cursor.fetchone()[0]
        stats['average_percentage'] = result if result else 0.0

        # Aprobados vs Suspensos (asumiendo 50% para aprobar)
        cursor.execute("SELECT COUNT(*) FROM exams WHERE percentage >= 50")
        stats['passed'] = cursor.fetchone()[0]
        stats['failed'] = stats['total_exams'] - stats['passed']

        # Distribución de calificaciones
        cursor.execute("""
            SELECT literal_grade, COUNT(*) as count
            FROM exams
            WHERE literal_grade IS NOT NULL
            GROUP BY literal_grade
        """)
        stats['grade_distribution'] = dict(cursor.fetchall())

        conn.close()
        return stats

    def set_student_id(self, exam_id: int, student_id: Optional[str]) -> bool:
        """
        Actualiza el `student_id` de un único examen.

        Pasa `None` para des-vincular (deja el examen huérfano). El nombre
        del estudiante en el campo `student_name` queda intacto a propósito:
        es lo que detectó OCR y conviene conservarlo para auditoría futura.

        Devuelve True si el examen existía (se actualizó), False si no.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE exams SET student_id = ? WHERE id = ?",
                (student_id, exam_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_exam(self, exam_id: int) -> bool:
        """
        Elimina un examen y sus ítems

        Args:
            exam_id: ID del examen

        Returns:
            True si se eliminó correctamente
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM exam_items WHERE exam_id = ?", (exam_id,))
            cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
            conn.commit()
            success = cursor.rowcount > 0
        except Exception as e:
            print(f"Error al eliminar examen: {e}")
            success = False

        conn.close()
        return success

    def get_exams_by_identifier(self, exam_identifier: str) -> List[Dict]:
        """
        Obtiene todos los exámenes de un identificador específico (Asignatura_Tema)

        Args:
            exam_identifier: Identificador del examen

        Returns:
            Lista de exámenes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, student_id, student_name, total_score, max_score, percentage,
                   scaled_score, literal_grade, correction_date, exam_template, exam_identifier, mode
            FROM exams
            WHERE exam_identifier = ?
            ORDER BY student_name
        """, (exam_identifier,))

        columns = [desc[0] for desc in cursor.description]
        exams = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return exams

    def get_student_history(self, student_id: str) -> List[Dict]:
        """
        Obtiene todo el histórico de un estudiante por ID

        Args:
            student_id: ID del estudiante

        Returns:
            Lista de exámenes del estudiante
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, student_id, student_name, total_score, max_score, percentage,
                   scaled_score, literal_grade, correction_date, exam_template, exam_identifier, mode
            FROM exams
            WHERE student_id = ?
            ORDER BY correction_date DESC
        """, (student_id,))

        columns = [desc[0] for desc in cursor.description]
        exams = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return exams

    def export_exam_grades(self, exam_identifier: str, filepath: str) -> bool:
        """
        Exporta todas las notas de un examen específico a Excel

        Args:
            exam_identifier: Identificador del examen (Asignatura_Tema)
            filepath: Ruta del archivo Excel (.xlsx)

        Returns:
            True si se exportó correctamente
        """
        try:
            import pandas as pd
        except ImportError:
            print("ERROR: pandas no está instalado. Por favor ejecuta: pip install pandas openpyxl")
            return False

        exams = self.get_exams_by_identifier(exam_identifier)

        if not exams:
            print(f"No se encontraron exámenes con identificador '{exam_identifier}'")
            return False

        try:
            # Crear DataFrame
            df = pd.DataFrame(exams)

            # Renombrar columnas para mejor legibilidad
            column_names = {
                'id': 'ID',
                'student_id': 'ID Estudiante',
                'student_name': 'Estudiante',
                'total_score': 'Puntuación',
                'max_score': 'Máximo',
                'percentage': 'Porcentaje',
                'scaled_score': 'Nota',
                'literal_grade': 'Calificación',
                'correction_date': 'Fecha Corrección',
                'exam_template': 'Plantilla',
                'exam_identifier': 'Examen',
                'mode': 'Modo'
            }
            df = df.rename(columns=column_names)

            # Seleccionar solo columnas relevantes
            relevant_cols = ['ID Estudiante', 'Estudiante', 'Nota', 'Calificación',
                           'Puntuación', 'Porcentaje', 'Fecha Corrección']
            df = df[[col for col in relevant_cols if col in df.columns]]

            # Formatear fecha
            if 'Fecha Corrección' in df.columns:
                df['Fecha Corrección'] = pd.to_datetime(df['Fecha Corrección']).dt.strftime('%Y-%m-%d %H:%M')

            # Redondear números
            if 'Puntuación' in df.columns:
                df['Puntuación'] = df['Puntuación'].round(2)
            if 'Porcentaje' in df.columns:
                df['Porcentaje'] = df['Porcentaje'].round(2)
            if 'Nota' in df.columns:
                df['Nota'] = df['Nota'].round(2)

            # Guardar a Excel
            df.to_excel(filepath, index=False, engine='openpyxl')

            print(f"✅ Exportadas {len(exams)} notas a {filepath}")
            return True
        except Exception as e:
            print(f"Error al exportar a Excel: {e}")
            return False

    def export_to_excel(self, filepath: str) -> bool:
        """
        Exporta todos los exámenes a Excel

        Args:
            filepath: Ruta del archivo Excel (.xlsx)

        Returns:
            True si se exportó correctamente
        """
        try:
            import pandas as pd
        except ImportError:
            print("ERROR: pandas no está instalado. Por favor ejecuta: pip install pandas openpyxl")
            return False

        exams = self.get_all_exams(limit=10000)

        if not exams:
            return False

        try:
            # Crear DataFrame
            df = pd.DataFrame(exams)

            # Renombrar columnas para mejor legibilidad
            column_names = {
                'student_name': 'Estudiante',
                'total_score': 'Puntuación',
                'max_score': 'Máximo',
                'percentage': 'Porcentaje',
                'scaled_score': 'Nota',
                'literal_grade': 'Calificación',
                'correction_date': 'Fecha',
                'exam_template': 'Plantilla',
                'mode': 'Modo'
            }
            df = df.rename(columns=column_names)

            # Formatear fecha
            if 'Fecha' in df.columns:
                df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d %H:%M')

            # Redondear números
            if 'Puntuación' in df.columns:
                df['Puntuación'] = df['Puntuación'].round(2)
            if 'Porcentaje' in df.columns:
                df['Porcentaje'] = df['Porcentaje'].round(2)
            if 'Nota' in df.columns:
                df['Nota'] = df['Nota'].round(2)

            # Guardar a Excel
            df.to_excel(filepath, index=False, engine='openpyxl')

            return True
        except Exception as e:
            print(f"Error al exportar a Excel: {e}")
            return False
