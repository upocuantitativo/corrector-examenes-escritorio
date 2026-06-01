"""
test_corrector_core.py
=======================
Núcleo lógico (sin GUI) del corrector de exámenes TIPO TEST al que ha
convergido el proyecto, alineado con la app móvil/PWA
(https://upocuantitativo.github.io/corrector-examenes/).

Prototipo de examen
-------------------
- Test de N preguntas (por defecto 10) con 3 opciones a) b) c).
- El alumno rodea con un círculo la letra elegida.
- Puede haber 1 ó 2 páginas (p. ej. preguntas 1-4 en la página 1 y 5-10 en
  la 2).
- Modelos precargados del profesor:
    Modelo 1 (Duración subrayada):      a,a,b,a,a,a,c,b,a,a
    Modelo 2 (Duración sin subrayar):   b,a,a,c,b,c,a,c,b,b

Forma de corregir (idéntica a la PWA)
-------------------------------------
- Acierto      = +0.30
- Fallo        = -0.10
- No contestada =  0
- DUDA (2+ opciones marcadas) = 0, EXCLUIDA del total (símbolo ? amarillo).
- Nota /10 = puntos / (N*0.30) * 10.
  Literal: Sobresaliente >=9, Notable >=7, Aprobado >=5, Suspenso < 5.

Este módulo no depende de tkinter. La detección por imagen usa numpy/PIL
(mismo algoritmo de densidad de tinta que la PWA) y es opcional: el núcleo
de puntuación funciona sin imágenes.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence, Tuple

OPTS = ("a", "b", "c")
POINTS_OK = 0.3
POINTS_BAD = -0.1

DOUBT = "doubt"          # respuesta = 2+ opciones marcadas
BLANK = None            # respuesta = sin marcar

DEFAULT_KEYS = {
    "Modelo 1 (Duración subrayada)": ["a", "a", "b", "a", "a", "a", "c", "b", "a", "a"],
    "Modelo 2 (Duración sin subrayar)": ["b", "a", "a", "c", "b", "c", "a", "c", "b", "b"],
}


# --------------------------------------------------------------------------- #
#  Puntuación
# --------------------------------------------------------------------------- #
def classify(answer: Optional[str], key: str) -> str:
    """Clasifica una respuesta: 'ok' | 'mal' | 'duda' | 'blanco'."""
    if answer == DOUBT:
        return "duda"
    if answer is None:
        return "blanco"
    return "ok" if answer == key else "mal"


def literal_grade(nota10: float) -> str:
    if nota10 >= 9:
        return "Sobresaliente"
    if nota10 >= 7:
        return "Notable"
    if nota10 >= 5:
        return "Aprobado"
    return "Suspenso"


@dataclass
class GradeResult:
    aciertos: int
    fallos: int
    dudas: int
    blancos: int
    puntos: float
    max_puntos: float
    nota10: float
    literal: str
    detalle: List[str]          # 'ok'/'mal'/'duda'/'blanco' por pregunta

    def formatted(self) -> str:
        return (f"{self.puntos:.2f} / {self.max_puntos:.2f} puntos  ·  "
                f"Nota {self.nota10:.2f}/10  ·  {self.literal}\n"
                f"Aciertos {self.aciertos} · Fallos {self.fallos} · "
                f"Dudas {self.dudas} · En blanco {self.blancos}")


def grade(answers: Sequence[Optional[str]], keys: Sequence[str]) -> GradeResult:
    """Aplica el algoritmo de corrección. answers y keys de igual longitud."""
    if len(answers) != len(keys):
        raise ValueError("answers y keys deben tener la misma longitud")
    ac = fa = du = bl = 0
    detalle: List[str] = []
    for a, k in zip(answers, keys):
        c = classify(a, k)
        detalle.append(c)
        if c == "ok":
            ac += 1
        elif c == "mal":
            fa += 1
        elif c == "duda":
            du += 1
        else:
            bl += 1
    puntos = round(ac * POINTS_OK + fa * POINTS_BAD, 2)   # dudas y blancos no puntúan
    max_puntos = round(len(keys) * POINTS_OK, 2)
    nota10 = (puntos / max_puntos * 10) if max_puntos > 0 else 0.0
    return GradeResult(ac, fa, du, bl, puntos, max_puntos, nota10,
                       literal_grade(nota10), detalle)


# --------------------------------------------------------------------------- #
#  Biblioteca de exámenes (persistencia JSON)
# --------------------------------------------------------------------------- #
@dataclass
class Exam:
    name: str
    keys: List[str]
    page_mode: int = 1                                  # 1 ó 2 páginas
    # calib[pagina] = {"rel": [[t,s], ...], "r": float}
    calib: Dict[str, dict] = field(default_factory=dict)
    master_photos: Dict[str, str] = field(default_factory=dict)

    @property
    def nq(self) -> int:
        return len(self.keys)

    def page_questions(self, page: int) -> List[int]:
        """Índices 0-based de las preguntas de una página."""
        if self.page_mode == 1:
            return list(range(self.nq))
        # 2 páginas: 1-4 en la página 1, resto en la 2 (como el examen de Estadística)
        return [0, 1, 2, 3] if page == 1 else list(range(4, self.nq))


class ExamLibrary:
    """Colección de exámenes con guardado/carga en un JSON."""

    def __init__(self, exams: Optional[Dict[str, Exam]] = None,
                 order: Optional[List[str]] = None, cur: Optional[str] = None):
        self.exams: Dict[str, Exam] = exams or {}
        self.order: List[str] = order or list(self.exams.keys())
        self.cur: Optional[str] = cur or (self.order[0] if self.order else None)

    # --- fábricas ---
    @classmethod
    def with_defaults(cls) -> "ExamLibrary":
        exams = {name: Exam(name=name, keys=list(k)) for name, k in DEFAULT_KEYS.items()}
        order = list(DEFAULT_KEYS.keys())
        return cls(exams, order, order[0])

    @classmethod
    def load(cls, path: str) -> "ExamLibrary":
        if not os.path.exists(path):
            lib = cls.with_defaults()
            lib.save(path)
            return lib
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        exams = {name: Exam(**e) for name, e in data.get("exams", {}).items()}
        return cls(exams, data.get("order", list(exams.keys())), data.get("cur"))

    def save(self, path: str) -> None:
        data = {
            "exams": {name: asdict(e) for name, e in self.exams.items()},
            "order": self.order,
            "cur": self.cur,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # --- operaciones ---
    def current(self) -> Optional[Exam]:
        return self.exams.get(self.cur) if self.cur else None

    def add(self, name: str, nq: int = 10) -> Exam:
        if name in self.exams:
            raise ValueError(f"Ya existe un examen llamado «{name}»")
        ex = Exam(name=name, keys=["a"] * nq)
        self.exams[name] = ex
        self.order.append(name)
        self.cur = name
        return ex

    def rename(self, old: str, new: str) -> None:
        if old not in self.exams:
            raise KeyError(old)
        if new in self.exams and new != old:
            raise ValueError(f"Ya existe «{new}»")
        ex = self.exams.pop(old)
        ex.name = new
        self.exams[new] = ex
        self.order = [new if x == old else x for x in self.order]
        if self.cur == old:
            self.cur = new

    def delete(self, name: str) -> None:
        if len(self.order) <= 1:
            raise ValueError("Debe quedar al menos un examen")
        self.exams.pop(name, None)
        self.order = [x for x in self.order if x != name]
        if self.cur == name:
            self.cur = self.order[0]


# --------------------------------------------------------------------------- #
#  Geometría de calibración (idéntica a la PWA)
#  Las posiciones de las letras se guardan relativas a 2 anclas: A = primera
#  letra de la página (p.ej. Q1·a) y B = última (p.ej. Q10·c). Cada examen se
#  calibra una vez; en cada foto basta con marcar las 2 anclas.
# --------------------------------------------------------------------------- #
Point = Tuple[float, float]


def points_from_taps(taps: Sequence[Point]) -> dict:
    """taps en orden Q?a,Q?b,Q?c,...; A=taps[0], B=taps[-1]."""
    ax, ay = taps[0]
    bx, by = taps[-1]
    vx, vy = bx - ax, by - ay
    L = math.hypot(vx, vy) or 1.0
    ux, uy = vx / L, vy / L
    px, py = -uy, ux
    rel = []
    for (x, y) in taps:
        dx, dy = x - ax, y - ay
        rel.append([(dx * ux + dy * uy) / L, (dx * px + dy * py) / L])
    return {"rel": rel, "r": 0.022}


def mapped_points(cal: dict, anchors: Sequence[Point]) -> List[Tuple[float, float, float]]:
    """Devuelve (x, y, r) en píxeles para cada letra usando las 2 anclas."""
    (ax, ay), (bx, by) = anchors[0], anchors[1]
    vx, vy = bx - ax, by - ay
    L = math.hypot(vx, vy) or 1.0
    ux, uy = vx / L, vy / L
    px, py = -uy, ux
    r = cal["r"] * L
    out = []
    for t, s in cal["rel"]:
        out.append((ax + (t * ux + s * px) * L,
                    ay + (t * uy + s * py) * L, r))
    return out


# --------------------------------------------------------------------------- #
#  Detección de marcas por densidad de tinta (numpy, igual que la PWA)
# --------------------------------------------------------------------------- #
def _to_gray(image) -> "np.ndarray":
    import numpy as np
    arr = np.asarray(image)
    if arr.ndim == 2:
        return arr.astype(np.float32)
    rgb = arr[:, :, :3].astype(np.float32)
    return 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]


def ink_score(gray, cx: float, cy: float, r: float) -> float:
    """Fracción de píxeles oscuros en el disco (cx,cy,r). Umbral = 72% de la
    luminancia media local (cuenta texto + círculo a mano)."""
    import numpy as np
    h, w = gray.shape
    x0, x1 = max(0, int(cx - r)), min(w - 1, int(cx + r))
    y0, y1 = max(0, int(cy - r)), min(h - 1, int(cy + r))
    if x1 < x0 or y1 < y0:
        return 0.0
    ys, xs = np.ogrid[y0:y1 + 1, x0:x1 + 1]
    mask = (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
    vals = gray[y0:y1 + 1, x0:x1 + 1][mask]
    if vals.size == 0:
        return 0.0
    thr = float(vals.mean()) * 0.72
    return float((vals < thr).sum()) / float(vals.size)


def detect_answers(gray, points: Sequence[Tuple[float, float, float]],
                   questions: Sequence[int], sens: float = 1.6,
                   floor: float = 0.14) -> Dict[int, Optional[str]]:
    """Detecta la respuesta de cada pregunta de una página.

    points: lista (x,y,r) en orden a,b,c,a,b,c,... para las `questions`.
    Devuelve {indice_pregunta: 'a'|'b'|'c'|None|'doubt'}.
    """
    res: Dict[int, Optional[str]] = {}
    for lq, q in enumerate(questions):
        sc = [ink_score(gray, *points[lq * 3 + k]) for k in range(3)]
        order = sorted(range(3), key=lambda k: sc[k], reverse=True)
        best, second = sc[order[0]], sc[order[1]]
        if best < floor:
            res[q] = BLANK
        elif second >= floor and best < second * sens:
            res[q] = DOUBT
        else:
            res[q] = OPTS[order[0]]
    return res
