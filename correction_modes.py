"""
Módulos para los diferentes modos de corrección de exámenes
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from camera_handler import CameraHandler
from symbol_recognizer import SymbolRecognizer, CorrectionSymbol
from ocr_handler import OCRHandler


@dataclass
class ExamItem:
    """Representa un ítem del examen"""
    item_number: int
    weight: float
    description: str = ""


@dataclass
class CorrectionResult:
    """Resultado de la corrección de un ítem"""
    item: ExamItem
    symbol: CorrectionSymbol
    confidence: float
    score: float  # Puntuación obtenida (0-weight)
    roi_image: Optional[np.ndarray] = None  # Imagen del ROI para verificación
    sample_id: Optional[int] = None  # Vinculación con feedback_store.training_samples


@dataclass
class ExamCorrection:
    """Corrección completa de un examen"""
    student_name: str
    student_name_confidence: float
    results: List[CorrectionResult]
    total_score: float
    max_score: float
    percentage: float
    needs_verification: List[int]  # Índices de resultados que necesitan verificación


class Mode1Corrector:
    """
    Modo 1: Corrección secuencial de ítems con símbolos (✓, X, ~)
    El profesor muestra el examen y la cámara detecta las marcas rojas en orden
    """

    def __init__(self, camera: CameraHandler, items: List[ExamItem],
                 confidence_threshold: float = 0.7):
        """
        Inicializa el corrector en modo 1

        Args:
            camera: Manejador de cámara
            items: Lista de ítems del examen con pesos
            confidence_threshold: Umbral de confianza para aceptar automáticamente
        """
        self.camera = camera
        self.items = items
        self.confidence_threshold = confidence_threshold
        self.symbol_recognizer = SymbolRecognizer(confidence_threshold=0.6)
        self.ocr = OCRHandler()

    def correct_exam(self) -> ExamCorrection:
        """
        Realiza la corrección completa del examen

        Returns:
            ExamCorrection con todos los resultados
        """
        print("\n=== MODO 1: CORRECCIÓN SECUENCIAL ===")
        print("Muestra el examen a la cámara cuando esté listo...")
        print("Presiona ESPACIO para capturar, ESC para cancelar\n")

        # Paso 1: Capturar imagen del examen
        exam_image = self._capture_exam_image()
        if exam_image is None:
            return self._create_empty_correction()

        # Paso 2: Extraer nombre del estudiante
        print("\nExtrayendo nombre del estudiante...")
        student_name, name_confidence = self.ocr.extract_student_name(exam_image)
        print(f"Nombre detectado: {student_name} (confianza: {name_confidence:.2%})")

        # Paso 3: Detectar marcas rojas
        print("\nDetectando correcciones en rojo...")
        marks = self.camera.detect_red_marks(exam_image, min_area=100)
        print(f"Se detectaron {len(marks)} marcas rojas")

        # Paso 4: Reconocer símbolos en cada marca
        results = []
        needs_verification = []

        for idx, mark in enumerate(marks):
            if idx >= len(self.items):
                print(f"Advertencia: Se encontraron más marcas ({len(marks)}) que ítems ({len(self.items)})")
                break

            item = self.items[idx]
            roi = self.camera.extract_roi(exam_image, mark['bbox'], padding=5)

            # Reconocer símbolo
            symbol, confidence = self.symbol_recognizer.recognize_symbol(roi)

            # Calcular puntuación
            symbol_value = self.symbol_recognizer.get_symbol_value(symbol)
            score = symbol_value * item.weight

            result = CorrectionResult(
                item=item,
                symbol=symbol,
                confidence=confidence,
                score=score,
                roi_image=roi
            )
            results.append(result)

            # Marcar para verificación si la confianza es baja
            if confidence < self.confidence_threshold or symbol == CorrectionSymbol.UNKNOWN:
                needs_verification.append(idx)

            print(f"Ítem {item.item_number}: {self.symbol_recognizer.symbol_to_string(symbol)} "
                  f"[Confianza: {confidence:.2%}] -> {score:.2f}/{item.weight:.2f} puntos")

        # Si hay menos marcas que ítems, marcar los faltantes como no encontrados
        if len(marks) < len(self.items):
            print(f"\nAdvertencia: Solo se detectaron {len(marks)} marcas de {len(self.items)} ítems")
            for idx in range(len(marks), len(self.items)):
                item = self.items[idx]
                result = CorrectionResult(
                    item=item,
                    symbol=CorrectionSymbol.UNKNOWN,
                    confidence=0.0,
                    score=0.0,
                    roi_image=None
                )
                results.append(result)
                needs_verification.append(idx)

        # Calcular puntuación total
        total_score = sum(r.score for r in results)
        max_score = sum(item.weight for item in self.items)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        correction = ExamCorrection(
            student_name=student_name,
            student_name_confidence=name_confidence,
            results=results,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            needs_verification=needs_verification
        )

        return correction

    def _capture_exam_image(self) -> Optional[np.ndarray]:
        """
        Captura una imagen del examen desde la cámara

        Returns:
            Imagen capturada o None si se cancela
        """
        while True:
            frame, key = self.camera.show_preview("Muestra el examen - ESPACIO para capturar")

            if key == 27:  # ESC
                print("Captura cancelada")
                return None
            elif key == 32:  # ESPACIO
                print("Imagen capturada!")
                cv2.destroyAllWindows()
                return frame

    def _create_empty_correction(self) -> ExamCorrection:
        """Crea una corrección vacía en caso de cancelación"""
        return ExamCorrection(
            student_name="Cancelado",
            student_name_confidence=0.0,
            results=[],
            total_score=0.0,
            max_score=0.0,
            percentage=0.0,
            needs_verification=[]
        )


class Mode2Corrector:
    """
    Modo 2: Corrección con cuadrícula de puntuaciones numéricas
    Los ítems están en una cuadrícula ordenada (izquierda a derecha, arriba a abajo)
    """

    def __init__(self, camera: CameraHandler, items: List[ExamItem],
                 grid_rows: int, grid_cols: int, confidence_threshold: float = 0.7):
        """
        Inicializa el corrector en modo 2

        Args:
            camera: Manejador de cámara
            items: Lista de ítems del examen con pesos máximos
            grid_rows: Número de filas en la cuadrícula
            grid_cols: Número de columnas en la cuadrícula
            confidence_threshold: Umbral de confianza
        """
        self.camera = camera
        self.items = items
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.confidence_threshold = confidence_threshold
        self.ocr = OCRHandler()

    def correct_exam(self) -> ExamCorrection:
        """
        Realiza la corrección completa del examen con cuadrícula
        Captura UNA foto de la cuadrícula completa y detecta símbolos (✓, X, ~)
        en orden de izquierda a derecha, arriba a abajo

        Returns:
            ExamCorrection con todos los resultados
        """
        print("\n=== MODO 2: CORRECCIÓN CON CUADRÍCULA COMPLETA ===")
        print("Prepara la hoja con la cuadrícula de símbolos (✓, X, ~)")
        print("Organizada de izquierda a derecha, arriba a abajo")
        print("Presiona ESPACIO para capturar, ESC para cancelar\n")

        # Inicializar reconocedor de símbolos
        from symbol_recognizer import SymbolRecognizer
        symbol_recognizer = SymbolRecognizer()

        # Paso 1: Capturar imagen de la cuadrícula completa
        exam_image = self._capture_exam_image()
        if exam_image is None:
            return self._create_empty_correction()

        # Paso 2: Extraer nombre del estudiante (parte superior de la imagen)
        print("\nExtrayendo nombre del estudiante...")
        student_name, name_confidence = self.ocr.extract_student_name(exam_image)
        print(f"Nombre detectado: {student_name} (confianza: {name_confidence:.2%})")

        # Paso 3: Detectar símbolos en la cuadrícula
        print("\nDetectando símbolos en la cuadrícula...")
        detected_symbols = self._detect_grid_symbols(exam_image, len(self.items))

        if not detected_symbols:
            print("⚠️ No se detectaron símbolos. Verifica la imagen.")
            return self._create_empty_correction()

        print(f"✅ Se detectaron {len(detected_symbols)} símbolos")

        # Paso 4: Reconocer cada símbolo
        results = []
        needs_verification = []

        for idx, symbol_info in enumerate(detected_symbols):
            if idx >= len(self.items):
                break

            item = self.items[idx]
            symbol_roi = symbol_info['roi']

            # Reconocer símbolo
            detected_symbol, confidence = symbol_recognizer.recognize_symbol(symbol_roi)

            # Calcular puntuación según el símbolo
            if detected_symbol == CorrectionSymbol.CHECK:
                score = item.weight
            elif detected_symbol == CorrectionSymbol.TILDE:
                score = item.weight * 0.5
            elif detected_symbol == CorrectionSymbol.CROSS:
                score = 0.0
            else:
                score = 0.0
                needs_verification.append(idx)

            result = CorrectionResult(
                item=item,
                symbol=detected_symbol,
                confidence=confidence,
                score=score,
                roi_image=symbol_roi
            )
            results.append(result)

            # Marcar para verificación si la confianza es baja
            if confidence < self.confidence_threshold:
                needs_verification.append(idx)

            symbol_str = "✓" if detected_symbol == CorrectionSymbol.CHECK else \
                        "~" if detected_symbol == CorrectionSymbol.TILDE else \
                        "X" if detected_symbol == CorrectionSymbol.CROSS else "?"

            print(f"Ítem {item.item_number}: {symbol_str} → {score:.2f}/{item.weight:.2f} puntos "
                  f"[Confianza: {confidence:.1f}%]")

        # Calcular puntuación total
        total_score = sum(r.score for r in results)
        max_score = sum(item.weight for item in self.items)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        correction = ExamCorrection(
            student_name=student_name,
            student_name_confidence=name_confidence,
            results=results,
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            needs_verification=list(set(needs_verification))  # Eliminar duplicados
        )

        print(f"\n📊 Puntuación total: {total_score:.2f}/{max_score:.2f} ({percentage:.1f}%)")

        return correction

    def _detect_grid_symbols(self, image: np.ndarray, num_symbols: int) -> List[Dict]:
        """
        Detecta símbolos en la cuadrícula, ordenados de izquierda a derecha y arriba a abajo

        Args:
            image: Imagen con la cuadrícula de símbolos
            num_symbols: Número de símbolos esperados

        Returns:
            Lista de diccionarios con 'roi' (imagen del símbolo) y 'position' (x, y)
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Umbralización adaptativa para resaltar símbolos
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 21, 10
        )

        # Operaciones morfológicas para limpiar
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # Encontrar contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos por área (símbolos deben tener cierto tamaño)
        min_area = 200  # Área mínima del símbolo
        max_area = 50000  # Área máxima (para excluir marcos grandes)

        symbol_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Filtrar por aspect ratio razonable
                aspect_ratio = w / float(h)
                if 0.3 < aspect_ratio < 3.0:  # Símbolos no deben ser muy alargados
                    symbol_contours.append({
                        'bbox': (x, y, w, h),
                        'center': (x + w//2, y + h//2),
                        'area': area
                    })

        # Ordenar de izquierda a derecha, arriba a abajo
        # Agrupar por filas (símbolos con Y similar están en la misma fila)
        def sort_key(contour_info):
            x, y = contour_info['center']
            # Agrupar por fila con tolerancia de ±30 píxeles
            row = y // 50
            return (row, x)

        symbol_contours.sort(key=sort_key)

        # Tomar solo los primeros num_symbols
        symbol_contours = symbol_contours[:num_symbols]

        # Extraer ROIs de los símbolos
        detected_symbols = []
        for info in symbol_contours:
            x, y, w, h = info['bbox']
            # Añadir padding
            padding = 10
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(image.shape[1], x + w + padding)
            y2 = min(image.shape[0], y + h + padding)

            symbol_roi = image[y1:y2, x1:x2]

            detected_symbols.append({
                'roi': symbol_roi,
                'position': (x, y)
            })

        return detected_symbols

    def _detect_grid(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Detecta la cuadrícula en la imagen y extrae las celdas

        Args:
            image: Imagen con la cuadrícula

        Returns:
            Lista de imágenes de celdas ordenadas
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Detectar líneas horizontales y verticales
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

        horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

        # Combinar líneas
        grid_mask = cv2.add(horizontal_lines, vertical_lines)

        # Encontrar contornos de celdas
        contours, _ = cv2.findContours(grid_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar y ordenar celdas
        cells = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # Filtrar áreas pequeñas
                x, y, w, h = cv2.boundingRect(contour)
                cells.append({'bbox': (x, y, w, h), 'center': (x + w//2, y + h//2)})

        # Ordenar de izquierda a derecha y arriba a abajo
        cells.sort(key=lambda c: (c['center'][1]//50, c['center'][0]))

        # Extraer imágenes de celdas
        cell_images = [self.camera.extract_roi(image, cell['bbox'], padding=5)
                      for cell in cells[:self.grid_rows * self.grid_cols]]

        return cell_images

    def _score_to_symbol(self, score: float, max_score: float) -> CorrectionSymbol:
        """Convierte una puntuación a símbolo equivalente"""
        if max_score == 0:
            return CorrectionSymbol.UNKNOWN

        ratio = score / max_score
        if ratio >= 0.8:
            return CorrectionSymbol.CHECK
        elif ratio >= 0.4:
            return CorrectionSymbol.TILDE
        else:
            return CorrectionSymbol.CROSS

    def _capture_exam_image(self) -> Optional[np.ndarray]:
        """Captura una imagen del examen desde la cámara"""
        while True:
            frame, key = self.camera.show_preview("Muestra la cuadrícula - ESPACIO para capturar")

            if key == 27:  # ESC
                print("Captura cancelada")
                return None
            elif key == 32:  # ESPACIO
                print("Imagen capturada!")
                cv2.destroyAllWindows()
                return frame

    def _create_empty_correction(self) -> ExamCorrection:
        """Crea una corrección vacía en caso de cancelación"""
        return ExamCorrection(
            student_name="Cancelado",
            student_name_confidence=0.0,
            results=[],
            total_score=0.0,
            max_score=0.0,
            percentage=0.0,
            needs_verification=[]
        )
