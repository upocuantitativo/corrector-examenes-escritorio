"""
Módulo para reconocimiento de texto (nombres, apellidos, números) usando EasyOCR
"""
import cv2
import numpy as np
from typing import Optional, List, Tuple
import re


class OCRHandler:
    """Maneja el reconocimiento de texto con EasyOCR"""

    def __init__(self, languages: List[str] = ['es', 'en']):
        """
        Inicializa el manejador OCR

        Args:
            languages: Lista de idiomas para reconocimiento
        """
        self.languages = languages
        self.reader = None
        self._initialize_reader()

    def _initialize_reader(self):
        """Inicializa el lector de EasyOCR (lazy loading)"""
        try:
            import easyocr
            self.reader = easyocr.Reader(self.languages, gpu=False)
        except ImportError:
            print("ERROR: EasyOCR no está instalado. Instalando...")
            print("Por favor ejecuta: pip install easyocr")
            self.reader = None
        except Exception as e:
            print(f"Error al inicializar EasyOCR: {e}")
            self.reader = None

    def extract_text(self, image: np.ndarray, detail: int = 0) -> List[Tuple[str, float]]:
        """
        Extrae texto de una imagen

        Args:
            image: Imagen de entrada
            detail: Nivel de detalle (0 = solo texto, 1 = con coordenadas)

        Returns:
            Lista de tuplas (texto, confianza)
        """
        if self.reader is None:
            return []

        try:
            results = self.reader.readtext(image, detail=detail)

            # Formato: [(bbox, text, confidence), ...]
            if detail == 1:
                return [(text, conf) for (bbox, text, conf) in results]
            else:
                # Si detail=0, devuelve directamente el texto
                return [(text, 1.0) for text in results]

        except Exception as e:
            print(f"Error en extracción de texto: {e}")
            return []

    def extract_student_name(self, image: np.ndarray, roi: Optional[Tuple[int, int, int, int]] = None) -> Tuple[str, float]:
        """
        Extrae el nombre del estudiante de la imagen

        Args:
            image: Imagen del examen
            roi: Región de interés (x, y, w, h) donde buscar el nombre.
                 Si es None, busca en el tercio superior de la imagen

        Returns:
            Tupla (nombre_completo, confianza)
        """
        # Si no se especifica ROI, usar el tercio superior de la imagen
        if roi is None:
            h, w = image.shape[:2]
            roi_image = image[0:h//3, :]
        else:
            x, y, w, h = roi
            roi_image = image[y:y+h, x:x+w]

        # Preprocesar para mejorar OCR
        preprocessed = self._preprocess_for_text(roi_image)

        # Extraer texto
        results = self.extract_text(preprocessed, detail=1)

        if not results:
            return "Nombre no detectado", 0.0

        # Buscar el texto más largo (probablemente el nombre completo)
        # Filtrar resultados que parezcan nombres (letras principalmente)
        name_candidates = []
        for text, conf in results:
            # Limpiar y validar
            cleaned = self._clean_name(text)
            if len(cleaned) > 3 and self._is_likely_name(cleaned):
                name_candidates.append((cleaned, conf))

        if not name_candidates:
            # Si no hay candidatos, tomar el texto más largo
            longest = max(results, key=lambda x: len(x[0]))
            return self._clean_name(longest[0]), longest[1]

        # Retornar el candidato con mayor confianza
        best_candidate = max(name_candidates, key=lambda x: x[1])
        return best_candidate

    def extract_numbers(self, image: np.ndarray) -> List[Tuple[float, float]]:
        """
        Extrae números de una imagen (para puntuaciones en cuadrículas)

        Args:
            image: Imagen con números

        Returns:
            Lista de tuplas (número, confianza)
        """
        preprocessed = self._preprocess_for_numbers(image)
        results = self.extract_text(preprocessed, detail=1)

        numbers = []
        for text, conf in results:
            # Intentar extraer números del texto
            number = self._extract_number_from_text(text)
            if number is not None:
                numbers.append((number, conf))

        return numbers

    def _preprocess_for_text(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocesa imagen para mejorar reconocimiento de texto

        Args:
            image: Imagen original

        Returns:
            Imagen preprocesada
        """
        # Convertir a escala de grises si es necesario
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Aumentar contraste
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Binarización
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary

    def _preprocess_for_numbers(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocesa imagen específicamente para números

        Args:
            image: Imagen original

        Returns:
            Imagen preprocesada
        """
        # Similar al preprocesamiento de texto pero con parámetros optimizados para números
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Desenfoque para reducir ruido
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Binarización adaptativa (mejor para números escritos a mano)
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        return binary

    def _clean_name(self, text: str) -> str:
        """
        Limpia y formatea el nombre extraído

        Args:
            text: Texto crudo

        Returns:
            Texto limpio
        """
        # Eliminar caracteres especiales y números
        cleaned = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]', '', text)

        # Normalizar espacios
        cleaned = ' '.join(cleaned.split())

        # Capitalizar cada palabra
        cleaned = cleaned.title()

        return cleaned.strip()

    def _is_likely_name(self, text: str) -> bool:
        """
        Verifica si un texto es probable que sea un nombre

        Args:
            text: Texto a verificar

        Returns:
            True si parece un nombre
        """
        # Un nombre típicamente:
        # - Tiene al menos 2 palabras (nombre y apellido)
        # - No tiene muchos números
        # - Tiene longitud razonable

        words = text.split()

        # Al menos una palabra
        if len(words) < 1:
            return False

        # No debe tener muchos caracteres raros
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in text) / len(text)
        if alpha_ratio < 0.8:
            return False

        return True

    def _extract_number_from_text(self, text: str) -> Optional[float]:
        """
        Extrae un número del texto

        Args:
            text: Texto que puede contener un número

        Returns:
            Número extraído o None
        """
        # Limpiar texto
        cleaned = text.strip()

        # Intentar encontrar números decimales
        # Patrones comunes: "5.5", "5,5", "5", "10.0"
        patterns = [
            r'^(\d+[.,]\d+)$',  # Decimal con punto o coma
            r'^(\d+)$',  # Entero
            r'(\d+[.,]\d+)',  # Decimal en cualquier parte
            r'(\d+)',  # Entero en cualquier parte
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                num_str = match.group(1).replace(',', '.')
                try:
                    return float(num_str)
                except ValueError:
                    continue

        return None
