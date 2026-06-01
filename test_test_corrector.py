"""
Tests del núcleo del corrector tipo test (test_corrector_core.py).
Ejecutar:  python -m unittest test_test_corrector -v
"""
import json
import os
import tempfile
import unittest

import numpy as np

import test_corrector_core as core


class TestScoring(unittest.TestCase):
    def test_all_correct(self):
        keys = ["a"] * 10
        r = core.grade(keys, keys)
        self.assertEqual((r.aciertos, r.fallos, r.dudas, r.blancos), (10, 0, 0, 0))
        self.assertAlmostEqual(r.puntos, 3.0)
        self.assertAlmostEqual(r.nota10, 10.0)
        self.assertEqual(r.literal, "Sobresaliente")

    def test_doubt_and_blank_excluded(self):
        keys = ["a"] * 10
        ans = ["a", "a", core.DOUBT, None, "a", "a", "a", "a", "a", "a"]  # 8 ok, 1 duda, 1 blanco
        r = core.grade(ans, keys)
        self.assertEqual((r.aciertos, r.fallos, r.dudas, r.blancos), (8, 0, 1, 1))
        self.assertAlmostEqual(r.puntos, round(8 * 0.3, 2))   # duda/blanco no puntúan
        self.assertEqual(r.detalle[2], "duda")
        self.assertEqual(r.detalle[3], "blanco")

    def test_wrong_penalizes(self):
        keys = ["a"] * 10
        ans = ["b"] * 10
        r = core.grade(ans, keys)
        self.assertEqual(r.fallos, 10)
        self.assertAlmostEqual(r.puntos, round(10 * -0.1, 2))  # -1.0

    def test_real_exam_modelo1(self):
        # Caso leído de las fotos del alumno (Modelo 1)
        keys = core.DEFAULT_KEYS["Modelo 1 (Duración subrayada)"]
        ans = ["b", "a", "a", "c", "a", "c", "a", "a", "a", "b"]   # 3 ok / 7 mal
        r = core.grade(ans, keys)
        self.assertEqual((r.aciertos, r.fallos), (3, 7))
        self.assertAlmostEqual(r.puntos, round(3 * 0.3 + 7 * -0.1, 2))  # 0.20
        self.assertEqual(r.literal, "Suspenso")

    def test_literal_thresholds(self):
        self.assertEqual(core.literal_grade(9.0), "Sobresaliente")
        self.assertEqual(core.literal_grade(7.0), "Notable")
        self.assertEqual(core.literal_grade(5.0), "Aprobado")
        self.assertEqual(core.literal_grade(4.99), "Suspenso")

    def test_length_mismatch(self):
        with self.assertRaises(ValueError):
            core.grade(["a"], ["a", "b"])


class TestLibrary(unittest.TestCase):
    def test_defaults_keys(self):
        lib = core.ExamLibrary.with_defaults()
        self.assertEqual(lib.exams["Modelo 1 (Duración subrayada)"].keys,
                         ["a", "a", "b", "a", "a", "a", "c", "b", "a", "a"])
        self.assertEqual(lib.exams["Modelo 2 (Duración sin subrayar)"].keys,
                         ["b", "a", "a", "c", "b", "c", "a", "c", "b", "b"])

    def test_add_rename_delete_persist(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "exams.json")
            lib = core.ExamLibrary.load(p)            # crea defaults
            ex = lib.add("Matemáticas Junio")
            self.assertEqual(ex.keys, ["a"] * 10)
            self.assertEqual(lib.cur, "Matemáticas Junio")
            lib.exams["Matemáticas Junio"].keys[0] = "c"
            lib.rename("Matemáticas Junio", "Mates Junio")
            lib.save(p)
            # recargar y comprobar persistencia
            lib2 = core.ExamLibrary.load(p)
            self.assertIn("Mates Junio", lib2.exams)
            self.assertEqual(lib2.exams["Mates Junio"].keys[0], "c")
            self.assertEqual(len(lib2.order), 3)
            # borrar
            lib2.delete("Mates Junio")
            self.assertNotIn("Mates Junio", lib2.exams)
            self.assertEqual(len(lib2.order), 2)

    def test_cannot_delete_last(self):
        lib = core.ExamLibrary(exams={"X": core.Exam("X", ["a"] * 3)}, order=["X"], cur="X")
        with self.assertRaises(ValueError):
            lib.delete("X")

    def test_page_questions(self):
        ex = core.Exam("E", ["a"] * 10, page_mode=2)
        self.assertEqual(ex.page_questions(1), [0, 1, 2, 3])
        self.assertEqual(ex.page_questions(2), [4, 5, 6, 7, 8, 9])
        ex1 = core.Exam("E", ["a"] * 10, page_mode=1)
        self.assertEqual(ex1.page_questions(1), list(range(10)))


class TestGeometryAndDetection(unittest.TestCase):
    def test_points_from_taps_and_mapping(self):
        # 6 letras (2 preguntas) en una columna vertical
        taps = [(100, 100 + i * 40) for i in range(6)]
        cal = core.points_from_taps(taps)
        self.assertEqual(len(cal["rel"]), 6)
        # remapear con las mismas anclas debe reproducir las posiciones
        pts = core.mapped_points(cal, [taps[0], taps[-1]])
        for (x, y, r), (tx, ty) in zip(pts, taps):
            self.assertAlmostEqual(x, tx, places=3)
            self.assertAlmostEqual(y, ty, places=3)

    # Geometría realista: 3 letras separadas (como en un examen real), de modo
    # que el radio del ROI (0.022·L) sea apreciable. L = 800 → r ≈ 17.6 px.
    CENTERS = [(100, 100), (100, 500), (100, 900)]   # a, b, c

    def _ring(self, img, cx, cy, inner=8, outer=16):
        yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
        d2 = (yy - cy) ** 2 + (xx - cx) ** 2
        img[(d2 <= outer ** 2) & (d2 >= inner ** 2)] = 0

    def test_detect_marked_option(self):
        img = np.full((1000, 200), 255, dtype=np.uint8)
        self._ring(img, 100, 500)                        # marca b)
        cal = core.points_from_taps(self.CENTERS)
        pts = core.mapped_points(cal, [self.CENTERS[0], self.CENTERS[-1]])
        res = core.detect_answers(img, pts, [0], sens=1.6)
        self.assertEqual(res[0], "b")

    def test_detect_blank(self):
        img = np.full((1000, 200), 255, dtype=np.uint8)
        cal = core.points_from_taps(self.CENTERS)
        pts = core.mapped_points(cal, [self.CENTERS[0], self.CENTERS[-1]])
        res = core.detect_answers(img, pts, [0])
        self.assertIsNone(res[0])

    def test_detect_doubt(self):
        img = np.full((1000, 200), 255, dtype=np.uint8)
        self._ring(img, 100, 100)                        # marca a)
        self._ring(img, 100, 500)                        # y b) → duda
        cal = core.points_from_taps(self.CENTERS)
        pts = core.mapped_points(cal, [self.CENTERS[0], self.CENTERS[-1]])
        res = core.detect_answers(img, pts, [0], sens=1.6)
        self.assertEqual(res[0], "doubt")


if __name__ == "__main__":
    unittest.main()
