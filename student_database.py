"""
Gestión de base de datos de estudiantes
Carga CSV con lista de alumnos y permite búsqueda fuzzy por nombre
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import csv
from typing import Optional, List, Dict, Tuple
from difflib import SequenceMatcher
import unicodedata
import re


class StudentDatabase:
    """Gestiona la base de datos de estudiantes cargada desde CSV"""

    def __init__(self, csv_path: str = "alumnos.csv"):
        self.students: List[Dict[str, str]] = []
        self.csv_path = csv_path
        self.load_students()

    def load_students(self) -> bool:
        """Carga la lista de estudiantes desde el CSV"""
        try:
            with open(self.csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')

                for row in reader:
                    # Limpiar espacios en blanco
                    student = {k.strip(): v.strip() for k, v in row.items()}
                    self.students.append(student)

            print(f"✅ Cargados {len(self.students)} estudiantes desde {self.csv_path}")
            return True

        except FileNotFoundError:
            print(f"⚠️ Archivo {self.csv_path} no encontrado")
            return False
        except Exception as e:
            print(f"❌ Error cargando estudiantes: {e}")
            return False

    def normalize_text(self, text: str) -> str:
        """
        Normaliza texto para comparación:
        - Elimina acentos
        - Convierte a minúsculas
        - Elimina caracteres especiales
        """
        if not text:
            return ""

        # Eliminar acentos
        text = ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )

        # Minúsculas
        text = text.lower()

        # Solo letras y espacios
        text = re.sub(r'[^a-z\s]', '', text)

        # Espacios múltiples a uno solo
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def similarity(self, text1: str, text2: str) -> float:
        """Calcula similitud entre dos textos (0-100)"""
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)

        return SequenceMatcher(None, norm1, norm2).ratio() * 100

    def find_student_by_name(self, detected_name: str,
                            min_similarity: float = 60.0) -> Tuple[Optional[Dict], float]:
        """
        Busca estudiante por nombre usando fuzzy matching

        Returns:
            (student_dict, confidence) o (None, 0) si no hay match suficiente
        """
        if not detected_name or not self.students:
            return None, 0.0

        best_match = None
        best_score = 0.0

        for student in self.students:
            full_name = student.get('ALUMNO', '')
            short_name = student.get('ACORTADO', '')

            # Comparar con nombre completo
            score_full = self.similarity(detected_name, full_name)

            # Comparar con nombre abreviado
            score_short = self.similarity(detected_name, short_name)

            # Tomar el mejor score
            score = max(score_full, score_short)

            # Comparar partes del nombre (apellidos)
            # Si detecta "GARCIA VELA" debería matchear con "GARCIA VELA, CARLA"
            name_parts = self.normalize_text(detected_name).split()
            full_name_norm = self.normalize_text(full_name)

            # Bonus si todas las partes detectadas están en el nombre completo
            if name_parts:
                parts_found = sum(1 for part in name_parts if part in full_name_norm)
                parts_bonus = (parts_found / len(name_parts)) * 20
                score = min(100, score + parts_bonus)

            if score > best_score:
                best_score = score
                best_match = student

        if best_score >= min_similarity:
            return best_match, best_score

        return None, 0.0

    def get_student_by_id(self, student_id) -> Optional[Dict]:
        """
        Obtiene estudiante por ID.

        Las claves del CSV se normalizan con `.strip()` al cargar (`Id ` → `Id`),
        así que aquí busca por la clave normalizada. Acepta `student_id` como
        int o str para evitar errores en el llamador.
        """
        target = str(student_id).strip()
        for student in self.students:
            if str(student.get('Id', '')).strip() == target:
                return student
        return None

    def get_student_info(self, student: Dict) -> str:
        """Formatea información del estudiante para mostrar"""
        if not student:
            return "Estudiante no encontrado"

        return (
            f"ID: {student.get('Id', 'N/A')}\n"
            f"Nombre: {student.get('ALUMNO', 'N/A')}\n"
            f"DNI: {student.get('DNI', 'N/A')}\n"
            f"Plan: {student.get('PLAN', 'N/A')} - Grupo {student.get('EPD', 'N/A')}\n"
            f"Código: {student.get('IDE', 'N/A')}"
        )

    def resolve_link(self, detected_name: str,
                     threshold: float = 75.0) -> Tuple[str, Optional[Dict], float]:
        """
        Resuelve la vinculación con un alumno para un nombre detectado.

        Devuelve una tupla con cuatro estados posibles que la GUI/CLI puede
        consumir para decidir qué hacer:

            ("matched",     student_dict, confidence)  → confidence ≥ threshold
            ("low",         student_dict, confidence)  → hay candidato, pero
                                                          por debajo del umbral
            ("none",        None,         0.0)         → sin candidato
            ("unavailable", None,         0.0)         → CSV no cargado

        Esta función es pura (sin GUI) y por tanto testeable sin tkinter.
        """
        if not self.students:
            return ("unavailable", None, 0.0)

        if not detected_name or not detected_name.strip():
            return ("none", None, 0.0)

        # Buscar con threshold intermedio para distinguir "low" de "none":
        # por debajo de 55 lo consideramos "no hay candidato razonable".
        # Por encima, lo mostramos como candidato y dejamos que la GUI
        # decida (matched si supera el umbral del llamador, low si no).
        student, confidence = self.find_student_by_name(
            detected_name, min_similarity=55.0
        )

        if not student:
            return ("none", None, 0.0)

        if confidence >= threshold:
            return ("matched", student, confidence)

        return ("low", student, confidence)

    def search_students(self, query: str) -> List[Tuple[Dict, float]]:
        """
        Busca estudiantes que coincidan con la query
        Retorna lista de (student, similarity_score) ordenada por score
        """
        results = []

        for student in self.students:
            full_name = student.get('ALUMNO', '')
            score = self.similarity(query, full_name)

            if score > 30:  # Threshold bajo para búsqueda
                results.append((student, score))

        # Ordenar por score descendente
        results.sort(key=lambda x: x[1], reverse=True)

        return results


# Test básico
if __name__ == "__main__":
    print("=== TEST STUDENT DATABASE ===\n")

    db = StudentDatabase("alumnos.csv")

    # Test 1: Buscar por nombre completo
    print("\n1. Búsqueda por nombre completo:")
    student, confidence = db.find_student_by_name("GARCIA VELA, CARLA")
    if student:
        print(f"✅ Encontrado con {confidence:.1f}% confianza:")
        print(db.get_student_info(student))

    # Test 2: Buscar por apellidos
    print("\n2. Búsqueda por apellidos:")
    student, confidence = db.find_student_by_name("GARCIA VELA")
    if student:
        print(f"✅ Encontrado con {confidence:.1f}% confianza:")
        print(db.get_student_info(student))

    # Test 3: Buscar con nombre mal escrito
    print("\n3. Búsqueda con typo:")
    student, confidence = db.find_student_by_name("GARSIA VELA")
    if student:
        print(f"✅ Encontrado con {confidence:.1f}% confianza:")
        print(db.get_student_info(student))

    # Test 4: Buscar sin acentos
    print("\n4. Búsqueda sin acentos:")
    student, confidence = db.find_student_by_name("MARTINEZ RIVERO")
    if student:
        print(f"✅ Encontrado con {confidence:.1f}% confianza:")
        print(db.get_student_info(student))

    # Test 5: Búsqueda múltiple
    print("\n5. Búsqueda múltiple (todos los 'GARCIA'):")
    results = db.search_students("GARCIA")
    for i, (student, score) in enumerate(results[:5], 1):
        print(f"\n{i}. {student.get('ALUMNO')} - {score:.1f}%")
