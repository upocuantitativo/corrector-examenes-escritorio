"""
Detector de hoja completa con símbolos organizados
Detecta nombre + símbolos en una sola foto
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from symbol_recognizer import SymbolRecognizer, CorrectionSymbol
from name_detector import NameDetector


class FullSheetDetector:
    """
    Detecta una hoja completa de examen con:
    - Nombre en la parte superior
    - Símbolos (✓, X, ~) organizados de izquierda a derecha, arriba a abajo

    Si se inyecta un `symbol_recognizer` externo (típicamente HybridSymbolRecognizer)
    se usa éste para reconocimiento y trazabilidad de muestras de aprendizaje.
    """

    def __init__(self, symbol_recognizer=None):
        # Acepta cualquier objeto con .recognize_symbol(roi) -> (CorrectionSymbol, float).
        # Si además expone .decide(roi) (HybridSymbolRecognizer) recogemos el sample_id.
        self.symbol_recognizer = symbol_recognizer or SymbolRecognizer()
        self.name_detector = NameDetector()

    def detect_full_sheet(self, frame: np.ndarray, num_items: int) -> Dict:
        """
        Detecta nombre + todos los símbolos en una sola imagen

        Args:
            frame: Imagen capturada de la hoja completa
            num_items: Número de ítems esperados

        Returns:
            Dict con:
                - student_name: str
                - name_confidence: float
                - items: List[Dict] con item_number, symbol, confidence
                - success: bool
        """
        result = {
            'student_name': '',
            'name_confidence': 0.0,
            'items': [],
            'success': False
        }

        if frame is None:
            return result

        # 1. Detectar nombre en la parte superior
        name, name_conf = self.name_detector.detect_name(frame, confidence_threshold=70.0)

        result['student_name'] = name if name else ''
        result['name_confidence'] = name_conf

        # 2. Detectar símbolos en orden
        symbols = self._detect_symbols_ordered(frame, num_items)

        result['items'] = symbols
        result['success'] = len(symbols) > 0

        return result

    def _detect_symbols_ordered(self, frame: np.ndarray, num_items: int) -> List[Dict]:
        """
        Detecta símbolos en orden de izquierda a derecha, arriba a abajo

        Asume que los símbolos están organizados en una cuadrícula
        """
        # Tomar región inferior (excluyendo área del nombre)
        height, width = frame.shape[:2]
        symbols_region = frame[height//3:, :]  # Desde 1/3 hacia abajo

        # Encontrar contornos de símbolos
        symbol_contours = self._find_symbol_contours(symbols_region)

        if not symbol_contours:
            return []

        # Ordenar contornos de izquierda a derecha, arriba a abajo
        sorted_contours = self._sort_contours_grid(symbol_contours)

        # Reconocer cada símbolo
        detected_items = []
        for idx, contour_info in enumerate(sorted_contours[:num_items]):
            x, y, w, h = contour_info['bbox']

            # Extraer región del símbolo
            symbol_roi = symbols_region[y:y+h, x:x+w]

            # Si el reconocedor es híbrido, usamos .decide() para obtener sample_id;
            # si no, mantenemos la API clásica.
            sample_id = None
            if hasattr(self.symbol_recognizer, 'decide'):
                decision = self.symbol_recognizer.decide(symbol_roi, item_number=idx + 1)
                detected_symbol, confidence = decision.symbol, decision.confidence
                sample_id = decision.sample_id
            else:
                detected_symbol, confidence = self.symbol_recognizer.recognize_symbol(symbol_roi)

            detected_items.append({
                'item_number': idx + 1,
                'symbol': detected_symbol,
                'confidence': confidence,
                'position': (x, y),
                'roi': symbol_roi,
                'sample_id': sample_id,
            })

        return detected_items

    def _find_symbol_contours(self, region: np.ndarray) -> List[Dict]:
        """Encuentra contornos de símbolos en la región"""
        # Convertir a escala de grises
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # Umbralización adaptativa
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 21, 10
        )

        # Operaciones morfológicas para limpiar
        kernel = np.ones((3, 3), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Encontrar contornos
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos por tamaño
        valid_contours = []
        height, width = region.shape[:2]
        min_area = (width * height) * 0.001  # Mínimo 0.1% del área total
        max_area = (width * height) * 0.15   # Máximo 15% del área total

        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0

                # Filtrar por aspect ratio razonable para símbolos
                if 0.3 < aspect_ratio < 3.0:
                    valid_contours.append({
                        'contour': contour,
                        'bbox': (x, y, w, h),
                        'area': area
                    })

        return valid_contours

    def _sort_contours_grid(self, contours: List[Dict]) -> List[Dict]:
        """
        Ordena contornos en orden de lectura (izquierda a derecha, arriba a abajo)
        """
        if not contours:
            return []

        # Agrupar por filas (tolerancia de altura)
        sorted_by_y = sorted(contours, key=lambda c: c['bbox'][1])

        rows = []
        current_row = [sorted_by_y[0]]
        row_y = sorted_by_y[0]['bbox'][1]
        tolerance = 50  # Píxeles de tolerancia para considerar misma fila

        for contour in sorted_by_y[1:]:
            y = contour['bbox'][1]
            if abs(y - row_y) < tolerance:
                current_row.append(contour)
            else:
                rows.append(current_row)
                current_row = [contour]
                row_y = y

        if current_row:
            rows.append(current_row)

        # Ordenar cada fila por X (izquierda a derecha)
        ordered_contours = []
        for row in rows:
            row_sorted = sorted(row, key=lambda c: c['bbox'][0])
            ordered_contours.extend(row_sorted)

        return ordered_contours

    def draw_detection_overlay(self, frame: np.ndarray, detection_result: Dict) -> np.ndarray:
        """
        Dibuja overlay con los resultados de la detección

        Args:
            frame: Frame original
            detection_result: Resultado de detect_full_sheet

        Returns:
            Frame con overlay dibujado
        """
        overlay = frame.copy()
        height, width = frame.shape[:2]

        # Dibujar nombre detectado
        if detection_result['student_name']:
            name = detection_result['student_name']
            conf = detection_result['name_confidence']

            # Fondo semi-transparente para el texto
            cv2.rectangle(overlay, (10, 10), (width - 10, 80), (0, 0, 0), -1)

            # Texto del nombre
            cv2.putText(overlay, f"Nombre: {name}", (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(overlay, f"Confianza: {conf:.1f}%", (20, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Dibujar símbolos detectados
        symbols_region_start = height // 3

        for item in detection_result['items']:
            x, y = item['position']
            # Ajustar Y porque la región de símbolos empieza en 1/3
            y_adjusted = y + symbols_region_start

            # Color según confianza (0-1)
            if item['confidence'] > 0.7:
                color = (0, 255, 0)
            elif item['confidence'] > 0.4:
                color = (0, 255, 255)
            else:
                color = (0, 0, 255)

            cv2.circle(overlay, (x, y_adjusted), 20, color, 2)

            _sym_chars = {
                CorrectionSymbol.CHECK: '✓',
                CorrectionSymbol.CROSS: 'X',
                CorrectionSymbol.TILDE: '~',
                CorrectionSymbol.UNKNOWN: '?',
            }
            symbol_char = _sym_chars.get(item['symbol'], '?')
            text = f"{item['item_number']}: {symbol_char}"
            cv2.putText(overlay, text, (x - 10, y_adjusted - 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Mezclar overlay con frame original
        result = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

        return result
