"""
Detector de nombres con OCR y confianza
Integrado con base de datos de estudiantes para asignación automática de ID
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import cv2
import numpy as np
import pytesseract
from typing import Optional, Tuple, Dict
import re
from student_database import StudentDatabase


class NameDetector:
    """Detecta nombres escritos a mano con nivel de confianza y los vincula con la BD de estudiantes"""

    def __init__(self, student_db_path: str = "alumnos.csv"):
        # Configurar Tesseract si está en Windows
        try:
            import platform
            if platform.system() == 'Windows':
                pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        except:
            pass

        # Cargar base de datos de estudiantes
        self.student_db = StudentDatabase(student_db_path)
        self.last_matched_student: Optional[Dict] = None

    def detect_name(self, frame: np.ndarray, confidence_threshold: float = 70.0) -> Tuple[Optional[str], float]:
        """
        Detecta el nombre en un frame de la cámara

        Args:
            frame: Frame de la cámara
            confidence_threshold: Umbral mínimo de confianza (0-100)

        Returns:
            Tuple (nombre_detectado, confianza)
            Si confianza < threshold, nombre_detectado será None
        """
        if frame is None:
            return None, 0.0

        # Preprocesar imagen
        processed = self._preprocess_for_name(frame)

        # Intentar detectar nombre con confianza
        try:
            # Usar tesseract con datos de confianza
            data = pytesseract.image_to_data(processed, lang='spa+eng', output_type=pytesseract.Output.DICT)

            # Extraer texto con mayor confianza
            text_parts = []
            confidences = []

            for i, word in enumerate(data['text']):
                if word.strip():
                    conf = float(data['conf'][i])
                    if conf > 0:  # Solo palabras con confianza positiva
                        text_parts.append(word.strip())
                        confidences.append(conf)

            if not text_parts:
                return None, 0.0

            # Combinar texto
            full_text = ' '.join(text_parts)

            # Calcular confianza promedio
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Limpiar y validar nombre
            cleaned_name = self._clean_name(full_text)

            if not cleaned_name or len(cleaned_name) < 3:
                return None, 0.0

            # Si la confianza es suficiente, devolver nombre
            if avg_confidence >= confidence_threshold:
                return cleaned_name, avg_confidence
            else:
                return None, avg_confidence

        except Exception as e:
            print(f"Error en detección de nombre: {e}")
            return None, 0.0

    def _preprocess_for_name(self, frame: np.ndarray) -> np.ndarray:
        """Preprocesa la región del nombre con upscaling + CLAHE + umbral adaptativo."""
        height = frame.shape[0]
        name_region = frame[0:height // 3, :]

        gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY)

        # Upscaling ayuda a Tesseract con texto pequeño o borroso
        scale = 2
        upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(upscaled)

        denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)

        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Tesseract funciona mejor con texto negro sobre fondo blanco
        if np.mean(binary) < 127:
            binary = cv2.bitwise_not(binary)

        return binary

    def _clean_name(self, text: str) -> str:
        """Limpia y valida el nombre detectado"""
        # Eliminar caracteres especiales comunes en OCR
        text = re.sub(r'[^\w\s\-áéíóúñÁÉÍÓÚÑ]', '', text)

        # Eliminar números sueltos
        words = text.split()
        words = [w for w in words if not w.isdigit()]

        # Capitalizar primera letra de cada palabra
        cleaned = ' '.join(word.capitalize() for word in words if len(word) > 1)

        return cleaned.strip()

    def detect_name_continuously(self, frame: np.ndarray) -> Tuple[str, float, bool]:
        """
        Detecta nombre continuamente hasta alcanzar confianza suficiente

        Returns:
            Tuple (nombre, confianza, está_listo)
        """
        name, confidence = self.detect_name(frame, confidence_threshold=70.0)

        if name:
            return name, confidence, True
        else:
            # Intentar detección con umbral más bajo para mostrar progreso
            name_low, conf_low = self.detect_name(frame, confidence_threshold=0.0)
            return name_low if name_low else "", conf_low, False

    def detect_name_with_student_match(self, frame: np.ndarray,
                                      confidence_threshold: float = 70.0) -> Tuple[Optional[str], Optional[Dict], float]:
        """
        Detecta nombre y lo vincula con estudiante de la base de datos

        Returns:
            Tuple (nombre_detectado, student_dict, confianza_total)
            - nombre_detectado: Nombre completo del estudiante de la BD (si se encuentra) o nombre OCR
            - student_dict: Diccionario con datos del estudiante (ID, DNI, etc.) o None
            - confianza_total: Confianza combinada de OCR + matching
        """
        # 1. Detectar nombre con OCR
        detected_name, ocr_confidence = self.detect_name(frame, confidence_threshold=0.0)

        if not detected_name:
            self.last_matched_student = None
            return None, None, 0.0

        # 2. Buscar estudiante en base de datos
        student, match_confidence = self.student_db.find_student_by_name(detected_name, min_similarity=60.0)

        if student:
            # Confianza combinada: promedio ponderado
            # OCR 60%, Match 40%
            combined_confidence = (ocr_confidence * 0.6) + (match_confidence * 0.4)

            # Guardar último estudiante encontrado
            self.last_matched_student = student

            # Retornar nombre completo de la BD
            full_name = student.get('ALUMNO', detected_name)

            print(f"✅ Estudiante identificado: {full_name} (ID: {student.get('Id', 'N/A')})")
            print(f"   Confianza OCR: {ocr_confidence:.1f}% | Match: {match_confidence:.1f}% | Total: {combined_confidence:.1f}%")

            return full_name, student, combined_confidence
        else:
            # No se encontró en BD, usar nombre OCR
            self.last_matched_student = None
            print(f"⚠️ Nombre detectado pero no encontrado en BD: '{detected_name}'")
            return detected_name, None, ocr_confidence

    def get_student_id(self) -> Optional[str]:
        """Obtiene el ID del último estudiante identificado"""
        if self.last_matched_student:
            # Clave normalizada por StudentDatabase.load_students (sin espacio final)
            return self.last_matched_student.get('Id', None)
        return None

    def get_student_info(self) -> str:
        """Obtiene información formateada del último estudiante identificado"""
        if self.last_matched_student:
            return self.student_db.get_student_info(self.last_matched_student)
        return "No hay estudiante identificado"
