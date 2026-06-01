"""
Modos de corrección mejorados con detección automática.
Bugs corregidos: enums incorrectos, acceso a tupla como dict, escala de confianza.
Nuevo: Mode4FileCorrector para corregir desde imagen de archivo (sin cámara).
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import cv2
import numpy as np
from typing import List, Dict, Optional
from correction_modes import ExamItem, ExamCorrection, CorrectionResult
from camera_handler import CameraHandler
from symbol_recognizer import SymbolRecognizer, CorrectionSymbol
from name_detector import NameDetector
from full_sheet_detector import FullSheetDetector


# ------------------------------------------------------------------ #
# Función compartida de conversión                                    #
# ------------------------------------------------------------------ #

def _convert_detection_to_correction(detection_result: Dict,
                                      items: List[ExamItem]) -> ExamCorrection:
    """
    Convierte el resultado de FullSheetDetector a ExamCorrection.
    Usada por Mode3 y Mode4.
    """
    results = []

    for item_data in detection_result['items']:
        item_number = item_data['item_number']
        exam_item = next(
            (item for item in items if item.item_number == item_number), None
        )
        if not exam_item:
            continue

        symbol = item_data['symbol']        # ya es CorrectionSymbol
        confidence = item_data['confidence']

        if symbol == CorrectionSymbol.CHECK:
            score = exam_item.weight
        elif symbol == CorrectionSymbol.TILDE:
            score = exam_item.weight * 0.5
        else:
            score = 0.0

        results.append(CorrectionResult(
            item=exam_item,
            symbol=symbol,
            confidence=confidence,
            score=score,
            roi_image=item_data.get('roi'),
            sample_id=item_data.get('sample_id'),
        ))

    total_score = sum(r.score for r in results)
    max_score = sum(r.item.weight for r in results)
    needs_verification = [
        i for i, r in enumerate(results)
        if r.confidence < 0.7 or r.symbol == CorrectionSymbol.UNKNOWN
    ]

    return ExamCorrection(
        student_name=detection_result['student_name'],
        student_name_confidence=detection_result['name_confidence'],
        results=results,
        total_score=total_score,
        max_score=max_score,
        percentage=(total_score / max_score * 100) if max_score > 0 else 0,
        needs_verification=needs_verification
    )


# ------------------------------------------------------------------ #
# Modo 1 Mejorado                                                     #
# ------------------------------------------------------------------ #

class Mode1ImprovedCorrector:
    """
    Modo 1 Mejorado: Detección continua sin salir de cámara.

    Flujo:
    1. Detecta nombre automáticamente (confianza OCR > 70%)
    2. Para cada ítem, profesor muestra símbolo a la cámara
    3. Presiona ESPACIO para capturar
    4. Muestra símbolo detectado y confianza sin cerrar cámara
    5. Al final muestra resumen para verificación
    """

    def __init__(self, camera: CameraHandler, items: List[ExamItem],
                 symbol_recognizer=None):
        self.camera = camera
        self.items = items
        self.name_detector = NameDetector()
        # Si no se inyecta, fallback a la heurística pura (compatible con tests antiguos).
        self.symbol_recognizer = symbol_recognizer or SymbolRecognizer()
        self.window_name = "Corrección - Modo 1 Mejorado"

    def correct_exam(self) -> ExamCorrection:
        """Ejecuta el proceso de corrección completo"""
        student_name, name_conf = self._detect_name_automatically()

        if not student_name:
            return self._create_empty_correction("Cancelado")

        results = self._capture_symbols_continuously(student_name)

        if not results:
            return self._create_empty_correction("Cancelado")

        total_score, max_score, needs_verification = self._calculate_scores(results)

        cv2.destroyAllWindows()
        return ExamCorrection(
            student_name=student_name,
            student_name_confidence=name_conf,
            results=results,
            total_score=total_score,
            max_score=max_score,
            percentage=(total_score / max_score * 100) if max_score > 0 else 0,
            needs_verification=needs_verification
        )

    def _detect_name_automatically(self):
        """Detecta el nombre automáticamente cuando confianza OCR > 70%"""
        print("\n=== DETECCIÓN DE NOMBRE ===")
        print("Muestra el nombre del estudiante a la cámara...")
        print("Presiona ESC para cancelar\n")

        detected_name = None
        name_confidence = 0.0

        while True:
            frame, key = self.camera.show_preview(self.window_name)
            if frame is None:
                break

            name, confidence, is_ready = self.name_detector.detect_name_continuously(frame)
            display_frame = self._draw_name_detection_overlay(frame, name, confidence, is_ready)
            cv2.imshow(self.window_name, display_frame)
            key = cv2.waitKey(1) & 0xFF

            if is_ready:
                detected_name = name
                name_confidence = confidence
                print(f"\n✓ Nombre detectado: {name} (Confianza: {confidence:.1f}%)")
                cv2.waitKey(1000)
                break

            if key == 27:
                print("\nDetección cancelada")
                break

        return detected_name, name_confidence

    def _capture_symbols_continuously(self, student_name: str) -> List[CorrectionResult]:
        """Captura símbolos secuencialmente sin cerrar la cámara"""
        results = []
        current_item_idx = 0

        print(f"\n=== CORRECCIÓN: {student_name} ===")
        print("Muestra cada símbolo y presiona ESPACIO para capturar")
        print("Presiona ESC para cancelar\n")

        self.symbol_recognizer.reset_history()

        while current_item_idx < len(self.items):
            frame, _ = self.camera.show_preview(self.window_name)
            if frame is None:
                break

            current_item = self.items[current_item_idx]
            display_frame = self._draw_correction_overlay(frame, student_name, current_item, results)
            cv2.imshow(self.window_name, display_frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                # Si es híbrido, capturamos sample_id para feedback iterativo
                sample_id = None
                if hasattr(self.symbol_recognizer, 'decide'):
                    decision = self.symbol_recognizer.decide(
                        frame, item_number=current_item.item_number,
                    )
                    symbol, confidence = decision.symbol, decision.confidence
                    sample_id = decision.sample_id
                else:
                    symbol, confidence = self.symbol_recognizer.recognize_symbol(frame)
                score = self._calculate_item_score(symbol, current_item.weight)

                results.append(CorrectionResult(
                    item=current_item,
                    symbol=symbol,
                    confidence=confidence,
                    score=score,
                    roi_image=frame.copy(),
                    sample_id=sample_id,
                ))

                print(f"Ítem {current_item.item_number}: {symbol.value} "
                      f"(conf={confidence:.2f}) → {score:.2f}/{current_item.weight:.2f}")

                current_item_idx += 1
                feedback = self._draw_capture_feedback(display_frame, symbol, confidence)
                cv2.imshow(self.window_name, feedback)
                cv2.waitKey(500)

            elif key == 27:
                print("\nCorrección cancelada")
                return []

        return results

    def _draw_name_detection_overlay(self, frame: np.ndarray, name: str,
                                     confidence: float, is_ready: bool) -> np.ndarray:
        overlay = frame.copy()
        height, width = frame.shape[:2]

        cv2.rectangle(overlay, (0, 0), (width, 120), (0, 0, 0), -1)
        cv2.putText(overlay, "DETECCION DE NOMBRE", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        if name:
            color = (0, 255, 0) if is_ready else (255, 255, 0)
            cv2.putText(overlay, f"Nombre: {name}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        else:
            cv2.putText(overlay, "Esperando nombre...", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (128, 128, 128), 2)

        bar_width = int((width - 40) * (confidence / 100))
        bar_color = (0, 255, 0) if confidence >= 70 else (0, 165, 255)
        cv2.rectangle(overlay, (20, 100), (20 + bar_width, 115), bar_color, -1)
        cv2.rectangle(overlay, (20, 100), (width - 20, 115), (255, 255, 255), 2)
        cv2.putText(overlay, f"{confidence:.0f}%", (width - 100, 112),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)

    def _draw_correction_overlay(self, frame: np.ndarray, student_name: str,
                                  current_item: ExamItem,
                                  results: List[CorrectionResult]) -> np.ndarray:
        overlay = frame.copy()
        height, width = frame.shape[:2]

        cv2.rectangle(overlay, (0, 0), (width, 150), (0, 0, 0), -1)
        cv2.putText(overlay, f"Estudiante: {student_name}", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(overlay, f"Item {current_item.item_number}/{len(self.items)}: {current_item.description}",
                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(overlay, f"Peso: {current_item.weight:.1f} puntos", (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(overlay, "ESPACIO: Capturar | ESC: Cancelar", (20, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)

        if results:
            cv2.putText(overlay, "Capturados:", (10, 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            for i, result in enumerate(results[-5:]):
                y_pos = 200 + (i * 30)
                symbol_text = result.symbol.value
                color = (0, 255, 0) if result.confidence > 0.7 else (0, 255, 255)
                cv2.putText(overlay, f"{result.item.item_number}. {symbol_text}",
                            (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

    def _draw_capture_feedback(self, frame: np.ndarray,
                                symbol: CorrectionSymbol, confidence: float) -> np.ndarray:
        overlay = frame.copy()
        height, width = frame.shape[:2]

        cv2.rectangle(overlay, (width // 4, height // 3),
                      (3 * width // 4, 2 * height // 3), (0, 0, 0), -1)
        cv2.putText(overlay, symbol.value, (width // 2 - 50, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 255, 0), 5)
        cv2.putText(overlay, f"Conf: {confidence:.2f}",
                    (width // 2 - 100, height // 2 + 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        return cv2.addWeighted(frame, 0.4, overlay, 0.6, 0)

    def _calculate_item_score(self, symbol: CorrectionSymbol, weight: float) -> float:
        if symbol == CorrectionSymbol.CHECK:
            return weight
        elif symbol == CorrectionSymbol.TILDE:
            return weight * 0.5
        else:
            return 0.0

    def _calculate_scores(self, results: List[CorrectionResult]):
        total_score = sum(r.score for r in results)
        max_score = sum(r.item.weight for r in results)
        needs_verification = [
            i for i, r in enumerate(results)
            if r.confidence < 0.7 or r.symbol == CorrectionSymbol.UNKNOWN
        ]
        return total_score, max_score, needs_verification

    def _create_empty_correction(self, student_name: str = "") -> ExamCorrection:
        return ExamCorrection(
            student_name=student_name,
            student_name_confidence=0.0,
            results=[],
            total_score=0.0,
            max_score=0.0,
            percentage=0.0,
            needs_verification=[]
        )


# ------------------------------------------------------------------ #
# Modo 3: Foto completa                                               #
# ------------------------------------------------------------------ #

class Mode3FullSheetCorrector:
    """
    Modo 3: Una foto de toda la hoja con detección automática completa.
    """

    def __init__(self, camera: CameraHandler, items: List[ExamItem],
                 symbol_recognizer=None):
        self.camera = camera
        self.items = items
        self.detector = FullSheetDetector(symbol_recognizer=symbol_recognizer)
        self.window_name = "Corrección - Foto Completa"

    def correct_exam(self) -> ExamCorrection:
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 900, 700)

        print("\n=== MODO 3: FOTO COMPLETA ===")
        print("Presiona ESPACIO para capturar | ESC para cancelar\n")

        captured_frame = None

        while True:
            frame, key = self.camera.show_preview(self.window_name)
            if frame is None:
                break

            display_frame = self._draw_capture_guide(frame)
            cv2.imshow(self.window_name, display_frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                captured_frame = frame.copy()
                print("\n📸 Foto capturada! Procesando...")
                break
            elif key == 27:
                cv2.destroyAllWindows()
                return self._create_empty_correction("Cancelado")

        if captured_frame is None:
            cv2.destroyAllWindows()
            return self._create_empty_correction("Cancelado")

        detection_result = self.detector.detect_full_sheet(captured_frame, len(self.items))
        result_frame = self.detector.draw_detection_overlay(captured_frame, detection_result)
        cv2.imshow(self.window_name, result_frame)
        cv2.waitKey(2000)
        cv2.destroyAllWindows()

        return _convert_detection_to_correction(detection_result, self.items)

    def _draw_capture_guide(self, frame: np.ndarray) -> np.ndarray:
        overlay = frame.copy()
        height, width = frame.shape[:2]

        cv2.rectangle(overlay, (0, 0), (width, 100), (0, 0, 0), -1)
        cv2.putText(overlay, "Posiciona la hoja completa en el cuadro",
                    (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(overlay, "ESPACIO: Capturar | ESC: Cancelar",
                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 200, 255), 1)

        margin = 50
        cv2.rectangle(overlay, (margin, margin + 100),
                      (width - margin, height - margin), (0, 255, 0), 2)

        name_line_y = margin + 100 + (height - margin - 100) // 3
        cv2.line(overlay, (margin, name_line_y), (width - margin, name_line_y), (255, 255, 0), 1)
        cv2.putText(overlay, "NOMBRE", (margin + 10, name_line_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        cv2.putText(overlay, "SIMBOLOS", (margin + 10, name_line_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        return cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

    def _create_empty_correction(self, student_name: str = "") -> ExamCorrection:
        return ExamCorrection(
            student_name=student_name,
            student_name_confidence=0.0,
            results=[],
            total_score=0.0,
            max_score=0.0,
            percentage=0.0,
            needs_verification=[]
        )


# ------------------------------------------------------------------ #
# Modo 4: Imagen desde archivo (sin cámara)                          #
# ------------------------------------------------------------------ #

class Mode4FileCorrector:
    """
    Modo 4: Corrección desde imagen de archivo (foto o escaneo).

    Permite procesar exámenes sin cámara usando el mismo pipeline
    de detección que el Modo 3 (FullSheetDetector).
    Inspirado en el flujo de procesamiento por lotes del repo de referencia.
    """

    def __init__(self, items: List[ExamItem], image_path: str,
                 symbol_recognizer=None):
        self.items = items
        self.image_path = image_path
        self.detector = FullSheetDetector(symbol_recognizer=symbol_recognizer)

    def correct_exam(self) -> ExamCorrection:
        """Carga la imagen y ejecuta la detección completa"""
        image = cv2.imread(self.image_path)
        if image is None:
            print(f"Error: No se pudo cargar la imagen: {self.image_path}")
            return self._create_empty_correction("Error al cargar imagen")

        print(f"\n=== MODO 4: IMAGEN DE ARCHIVO ===")
        print(f"Procesando: {self.image_path}")

        detection_result = self.detector.detect_full_sheet(image, len(self.items))

        result_frame = self.detector.draw_detection_overlay(image, detection_result)
        window_name = "Detección - Imagen de Archivo"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 900, 700)
        cv2.imshow(window_name, result_frame)
        print("Mostrando resultado 2 segundos...")
        cv2.waitKey(2000)
        cv2.destroyWindow(window_name)

        correction = _convert_detection_to_correction(detection_result, self.items)

        if not correction.student_name:
            correction = ExamCorrection(
                student_name="Desconocido",
                student_name_confidence=0.0,
                results=correction.results,
                total_score=correction.total_score,
                max_score=correction.max_score,
                percentage=correction.percentage,
                needs_verification=correction.needs_verification
            )

        return correction

    def _create_empty_correction(self, student_name: str = "") -> ExamCorrection:
        return ExamCorrection(
            student_name=student_name,
            student_name_confidence=0.0,
            results=[],
            total_score=0.0,
            max_score=0.0,
            percentage=0.0,
            needs_verification=[]
        )
