"""
Módulo para manejar la captura de imágenes desde la cámara
"""
import cv2
import numpy as np
from typing import Optional, Tuple


class CameraHandler:
    """Maneja la captura de video y extracción de frames"""

    def __init__(self, camera_index: int = 0):
        """
        Inicializa el manejador de cámara

        Args:
            camera_index: Índice de la cámara a usar (0 por defecto)
        """
        self.camera_index = camera_index
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_active = False

    def start(self) -> bool:
        """
        Inicia la cámara

        Returns:
            True si se inició correctamente, False en caso contrario
        """
        self.cap = cv2.VideoCapture(self.camera_index)
        if self.cap.isOpened():
            self.is_active = True
            return True
        return False

    def stop(self):
        """Detiene la cámara y libera recursos"""
        if self.cap is not None:
            self.cap.release()
            self.is_active = False
        cv2.destroyAllWindows()

    def capture_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Captura un frame de la cámara

        Returns:
            Tuple (success, frame) donde success indica si la captura fue exitosa
        """
        if not self.is_active or self.cap is None:
            return False, None

        ret, frame = self.cap.read()
        return ret, frame if ret else None

    def show_preview(self, window_name: str = "Vista Previa"):
        """
        Muestra vista previa de la cámara

        Args:
            window_name: Nombre de la ventana

        Returns:
            Tuple (frame, key_pressed) donde key_pressed es la tecla presionada
        """
        ret, frame = self.capture_frame()
        if ret and frame is not None:
            # Mostrar instrucciones
            display_frame = frame.copy()
            cv2.putText(display_frame, "Presiona ESPACIO para capturar, ESC para salir",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow(window_name, display_frame)
            key = cv2.waitKey(1) & 0xFF
            return frame, key
        return None, -1

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocesa la imagen para mejorar el reconocimiento

        Args:
            image: Imagen a preprocesar

        Returns:
            Imagen preprocesada
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Aplicar desenfoque para reducir ruido
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Binarización adaptativa
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        return binary

    def detect_red_marks(self, image: np.ndarray, min_area: int = 100) -> list:
        """
        Detecta marcas rojas en la imagen (correcciones del profesor)

        Args:
            image: Imagen a analizar
            min_area: Área mínima para considerar una marca

        Returns:
            Lista de contornos detectados con sus bounding boxes
        """
        # Convertir a HSV para detectar mejor el color rojo
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Rangos para detectar rojo (dos rangos porque el rojo está en los extremos)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        # Crear máscaras
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        # Aplicar operaciones morfológicas para limpiar la máscara
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Encontrar contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos por área y obtener bounding boxes
        detected_marks = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                detected_marks.append({
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'center': (x + w//2, y + h//2)
                })

        # Ordenar de izquierda a derecha y arriba a abajo
        detected_marks.sort(key=lambda m: (m['center'][1]//50, m['center'][0]))

        return detected_marks

    def extract_roi(self, image: np.ndarray, bbox: Tuple[int, int, int, int],
                    padding: int = 10) -> np.ndarray:
        """
        Extrae una región de interés (ROI) de la imagen

        Args:
            image: Imagen original
            bbox: Bounding box (x, y, w, h)
            padding: Píxeles de padding alrededor de la ROI

        Returns:
            Imagen recortada de la ROI
        """
        x, y, w, h = bbox

        # Añadir padding
        x_start = max(0, x - padding)
        y_start = max(0, y - padding)
        x_end = min(image.shape[1], x + w + padding)
        y_end = min(image.shape[0], y + h + padding)

        roi = image[y_start:y_end, x_start:x_end]
        return roi
