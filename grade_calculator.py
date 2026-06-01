"""
Sistema de cálculo de calificaciones con configuración personalizable
"""
from typing import Dict, Optional
from dataclasses import dataclass
import json
import os


@dataclass
class GradeScale:
    """Escala de calificación"""
    max_score: float = 10.0  # Puntuación máxima (por defecto sobre 10)
    passing_score: float = 5.0  # Puntuación mínima para aprobar

    # Umbrales de calificación (en porcentaje 0-100)
    excellent_threshold: float = 90.0  # Sobresaliente
    good_threshold: float = 70.0  # Notable
    pass_threshold: float = 50.0  # Aprobado
    # Por debajo = Suspenso


class GradeCalculator:
    """Calcula calificaciones finales con escala configurable"""

    def __init__(self, scale: Optional[GradeScale] = None):
        """
        Inicializa el calculador de calificaciones

        Args:
            scale: Escala de calificación personalizada
        """
        self.scale = scale or GradeScale()

    def calculate_final_grade(self, obtained_score: float, max_possible_score: float) -> Dict:
        """
        Calcula la calificación final

        Args:
            obtained_score: Puntuación obtenida
            max_possible_score: Puntuación máxima posible del examen

        Returns:
            Diccionario con información de la calificación
        """
        # Calcular porcentaje
        percentage = (obtained_score / max_possible_score * 100) if max_possible_score > 0 else 0

        # Convertir a la escala configurada
        scaled_score = (obtained_score / max_possible_score * self.scale.max_score) \
            if max_possible_score > 0 else 0

        # Determinar calificación literal
        literal_grade = self._get_literal_grade(percentage)

        # Determinar si aprueba
        passes = scaled_score >= self.scale.passing_score

        return {
            'obtained_score': obtained_score,
            'max_possible_score': max_possible_score,
            'percentage': percentage,
            'scaled_score': scaled_score,
            'max_scale': self.scale.max_score,
            'literal_grade': literal_grade,
            'passes': passes,
            'formatted': self._format_grade(scaled_score, literal_grade, passes)
        }

    def _get_literal_grade(self, percentage: float) -> str:
        """
        Obtiene la calificación literal basada en el porcentaje

        Args:
            percentage: Porcentaje obtenido (0-100)

        Returns:
            Calificación literal
        """
        if percentage >= self.scale.excellent_threshold:
            return "Sobresaliente"
        elif percentage >= self.scale.good_threshold:
            return "Notable"
        elif percentage >= self.scale.pass_threshold:
            return "Aprobado"
        else:
            return "Suspenso"

    def _format_grade(self, score: float, literal: str, passes: bool) -> str:
        """
        Formatea la calificación para mostrar

        Args:
            score: Puntuación en la escala
            literal: Calificación literal
            passes: Si aprueba o no

        Returns:
            String formateado
        """
        status = "✓" if passes else "✗"
        return f"{status} {score:.2f}/{self.scale.max_score} - {literal}"

    def set_scale(self, max_score: float = 10.0, passing_score: Optional[float] = None,
                  excellent: float = 90.0, good: float = 70.0, pass_: float = 50.0):
        """
        Configura la escala de calificación

        Args:
            max_score: Puntuación máxima
            passing_score: Puntuación mínima para aprobar (por defecto 50% del max)
            excellent: Umbral para sobresaliente (%)
            good: Umbral para notable (%)
            pass_: Umbral para aprobado (%)
        """
        self.scale.max_score = max_score
        self.scale.passing_score = passing_score if passing_score is not None else max_score / 2
        self.scale.excellent_threshold = excellent
        self.scale.good_threshold = good
        self.scale.pass_threshold = pass_

    def save_scale(self, filepath: str):
        """
        Guarda la escala de calificación en un archivo

        Args:
            filepath: Ruta del archivo
        """
        data = {
            'max_score': self.scale.max_score,
            'passing_score': self.scale.passing_score,
            'excellent_threshold': self.scale.excellent_threshold,
            'good_threshold': self.scale.good_threshold,
            'pass_threshold': self.scale.pass_threshold
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load_scale(self, filepath: str) -> bool:
        """
        Carga la escala de calificación desde un archivo

        Args:
            filepath: Ruta del archivo

        Returns:
            True si se cargó correctamente, False en caso contrario
        """
        if not os.path.exists(filepath):
            return False

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.scale.max_score = data.get('max_score', 10.0)
            self.scale.passing_score = data.get('passing_score', 5.0)
            self.scale.excellent_threshold = data.get('excellent_threshold', 90.0)
            self.scale.good_threshold = data.get('good_threshold', 70.0)
            self.scale.pass_threshold = data.get('pass_threshold', 50.0)

            return True
        except Exception as e:
            print(f"Error al cargar escala: {e}")
            return False


class ExamTemplate:
    """Plantilla de examen con ítems y pesos configurables"""

    def __init__(self, name: str, max_score_scale: float = 10.0):
        """
        Inicializa una plantilla de examen

        Args:
            name: Nombre de la plantilla
            max_score_scale: Escala final del examen (por defecto sobre 10)
        """
        self.name = name
        self.max_score_scale = max_score_scale
        self.items = []

    def add_item(self, item_number: int, weight: float, description: str = ""):
        """
        Añade un ítem a la plantilla

        Args:
            item_number: Número del ítem
            weight: Peso/puntuación del ítem
            description: Descripción opcional
        """
        self.items.append({
            'item_number': item_number,
            'weight': weight,
            'description': description
        })

    def get_total_weight(self) -> float:
        """Obtiene el peso total de todos los ítems"""
        return sum(item['weight'] for item in self.items)

    def save(self, filepath: str):
        """
        Guarda la plantilla en un archivo

        Args:
            filepath: Ruta del archivo
        """
        data = {
            'name': self.name,
            'max_score_scale': self.max_score_scale,
            'items': self.items
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(filepath: str) -> Optional['ExamTemplate']:
        """
        Carga una plantilla desde un archivo

        Args:
            filepath: Ruta del archivo

        Returns:
            ExamTemplate o None si hay error
        """
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            template = ExamTemplate(
                name=data.get('name', 'Sin nombre'),
                max_score_scale=data.get('max_score_scale', 10.0)
            )

            for item_data in data.get('items', []):
                template.add_item(
                    item_number=item_data['item_number'],
                    weight=item_data['weight'],
                    description=item_data.get('description', '')
                )

            return template
        except Exception as e:
            print(f"Error al cargar plantilla: {e}")
            return None

    def get_items_for_correction(self):
        """Obtiene los ítems en formato para corrección"""
        from correction_modes import ExamItem
        return [ExamItem(
            item_number=item['item_number'],
            weight=item['weight'],
            description=item['description']
        ) for item in self.items]
