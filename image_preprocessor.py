"""
Módulo de preprocesamiento de imágenes.
Técnicas CLAHE, Otsu, deskewing y eliminación de ruido inspiradas en
mrzaizai2k/Automated-scoring-of-handwritten-test-papers (Preprocessing.py).
"""
import cv2
import numpy as np
from typing import Optional


class ImagePreprocessor:
    """Pipeline de preprocesamiento para OCR y reconocimiento de símbolos"""

    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """CLAHE sobre escala de grises."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    @staticmethod
    def binarize_otsu(image: np.ndarray) -> np.ndarray:
        """Umbralización de Otsu (fondo blanco → tinta en primer plano)."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return binary

    @staticmethod
    def remove_noise(image: np.ndarray, strength: int = 10) -> np.ndarray:
        """Non-Local Means Denoising."""
        if image.ndim == 3:
            return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
        return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)

    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """
        Endereza la imagen usando análisis de momentos.
        Útil para hojas de examen fotografiadas con ligera inclinación.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        coords = np.column_stack(np.where(binary > 0))
        if len(coords) < 100:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            return image

        h, w = image.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(image, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def crop_to_content(image: np.ndarray, padding: int = 10) -> np.ndarray:
        """Recorta la imagen al área con contenido útil."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        coords = cv2.findNonZero(binary)
        if coords is None:
            return image

        x, y, w, h = cv2.boundingRect(coords)
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        return image[y:y + h, x:x + w]

    @staticmethod
    def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
        """
        Pipeline completo para mejorar OCR de texto manuscrito:
        CLAHE → denoising → umbral adaptativo → limpieza morfológica.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()

        # Upscaling ayuda a Tesseract con texto pequeño
        scale = 2
        upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(upscaled)

        denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)

        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Asegurar texto negro sobre blanco (Tesseract lo prefiere así)
        if np.mean(binary) < 127:
            binary = cv2.bitwise_not(binary)

        k = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)

    @staticmethod
    def preprocess_for_symbol(image: np.ndarray) -> np.ndarray:
        """
        Pipeline para preprocesar ROI de símbolo antes de clasificar:
        CLAHE → Otsu → morfología.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        resized = cv2.resize(gray, (100, 100))

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(resized)

        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        k = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k)
        return cv2.morphologyEx(binary, cv2.MORPH_OPEN, k)
