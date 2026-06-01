"""
Tests de integración del subsistema de estudiantes + base de datos de exámenes.

Cubre:
  - Carga del CSV de alumnos.
  - Búsqueda fuzzy con/sin acentos y con typos.
  - Persistencia de correcciones con `student_id` y `exam_identifier`.
  - Recuperación por identificador de examen y por histórico de estudiante.
  - Migración de esquema en BD legacy (sin `student_id`/`exam_identifier`).
  - Exportación a Excel (opcional, requiere pandas).

Ejecutar:
    python3 -m unittest test_student_integration.py -v
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from correction_modes import (
    CorrectionResult,
    ExamCorrection,
    ExamItem,
)
from exam_database import ExamDatabase
from student_database import StudentDatabase
from symbol_recognizer import CorrectionSymbol


# ---------------------------------------------------------------------------- #
# Helpers                                                                      #
# ---------------------------------------------------------------------------- #

def make_correction(
    student_name: str = "GARCIA VELA, CARLA",
    confidence: float = 92.5,
) -> ExamCorrection:
    """Construye una ExamCorrection mínima válida para insertar en BD."""
    items = [
        ExamItem(item_number=1, weight=1.0, description="Pregunta 1"),
        ExamItem(item_number=2, weight=1.5, description="Pregunta 2"),
    ]
    results = [
        CorrectionResult(item=items[0], symbol=CorrectionSymbol.CHECK,
                         confidence=0.95, score=1.0),
        CorrectionResult(item=items[1], symbol=CorrectionSymbol.CROSS,
                         confidence=0.85, score=0.0),
    ]
    total = sum(r.score for r in results)
    max_score = sum(i.weight for i in items)
    return ExamCorrection(
        student_name=student_name,
        student_name_confidence=confidence,
        results=results,
        total_score=total,
        max_score=max_score,
        percentage=(total / max_score) * 100.0,
        needs_verification=[],
    )


# ---------------------------------------------------------------------------- #
# Tests                                                                        #
# ---------------------------------------------------------------------------- #

class TestStudentDatabase(unittest.TestCase):
    """La búsqueda fuzzy debe ser robusta a typos, acentos y nombres parciales."""

    @classmethod
    def setUpClass(cls):
        # Usa el CSV real del proyecto (existe en /workspace/alumnos.csv)
        cls.db = StudentDatabase("alumnos.csv")
        if not cls.db.students:
            raise unittest.SkipTest("alumnos.csv vacío o no encontrado")

    def test_exact_full_name(self):
        student, conf = self.db.find_student_by_name("GARCIA VELA, CARLA")
        self.assertIsNotNone(student)
        self.assertGreater(conf, 90)
        self.assertEqual(student.get("ALUMNO"), "GARCIA VELA, CARLA")

    def test_partial_lastname_only(self):
        student, conf = self.db.find_student_by_name("GARCIA VELA")
        self.assertIsNotNone(student)
        self.assertEqual(student.get("ALUMNO"), "GARCIA VELA, CARLA")
        self.assertGreater(conf, 70)

    def test_typo_tolerance(self):
        # 'GARSIA' en lugar de 'GARCIA' debe seguir matcheando
        student, conf = self.db.find_student_by_name("GARSIA VELA")
        self.assertIsNotNone(student, f"No matcheó (conf={conf})")
        self.assertIn("GARCIA VELA", student.get("ALUMNO", ""))

    def test_diacritics_ignored(self):
        # 'MARTINEZ' vs. 'MARTÍNEZ' (CSV trae el acento) deben matchear
        student, conf = self.db.find_student_by_name("MARTINEZ RIVERO")
        self.assertIsNotNone(student)
        self.assertIn("MART", student.get("ALUMNO", "").upper())

    def test_unknown_name_returns_none(self):
        student, conf = self.db.find_student_by_name("NOMBRE QUE NO EXISTE XYZ")
        # Cuando confianza < min_similarity, devuelve None
        self.assertIsNone(student)
        self.assertEqual(conf, 0.0)

    def test_get_by_id(self):
        student = self.db.get_student_by_id(10)
        self.assertIsNotNone(student)
        self.assertEqual(student.get("ALUMNO"), "GARCIA VELA, CARLA")


class TestResolveLink(unittest.TestCase):
    """
    `StudentDatabase.resolve_link` es el dispatcher que usa la GUI en
    `MainApplication._save_correction` para decidir qué hacer con la
    vinculación. Tiene cuatro estados — los cubrimos todos.
    """

    @classmethod
    def setUpClass(cls):
        cls.db = StudentDatabase("alumnos.csv")
        if not cls.db.students:
            raise unittest.SkipTest("alumnos.csv vacío o no encontrado")

    def test_matched_high_confidence(self):
        status, student, conf = self.db.resolve_link("GARCIA VELA, CARLA",
                                                    threshold=75.0)
        self.assertEqual(status, "matched")
        self.assertIsNotNone(student)
        self.assertGreaterEqual(conf, 75.0)
        self.assertEqual(student.get("ALUMNO"), "GARCIA VELA, CARLA")

    def test_low_confidence_returns_candidate(self):
        # "JU PEREZ" matchea parcialmente algunos alumnos del CSV con score
        # ~65-70%, por debajo del umbral por defecto de 75 → estado "low".
        status, student, conf = self.db.resolve_link("JU PEREZ", threshold=75.0)
        self.assertEqual(status, "low")
        self.assertIsNotNone(student)
        self.assertLess(conf, 75.0)
        self.assertGreaterEqual(conf, 55.0)

    def test_no_candidate(self):
        # Nombre completamente fuera del CSV — ni para un match laxo.
        status, student, conf = self.db.resolve_link("ZZZ INEXISTENTE QWERTY",
                                                    threshold=75.0)
        self.assertEqual(status, "none")
        self.assertIsNone(student)
        self.assertEqual(conf, 0.0)

    def test_empty_name_is_none(self):
        for empty in ("", "   ", None):
            status, student, conf = self.db.resolve_link(empty, threshold=75.0)
            self.assertEqual(status, "none", f"falló con {empty!r}")
            self.assertIsNone(student)

    def test_unavailable_when_csv_missing(self):
        empty_db = StudentDatabase.__new__(StudentDatabase)
        empty_db.students = []
        empty_db.csv_path = "no-existe.csv"
        status, student, conf = empty_db.resolve_link("CUALQUIERA",
                                                     threshold=75.0)
        self.assertEqual(status, "unavailable")
        self.assertIsNone(student)


class TestExamDatabase(unittest.TestCase):
    """Persistencia, consulta por identificador e histórico por alumno."""

    def setUp(self):
        # BD efímera por test → aislamiento total
        fd, self.db_path = tempfile.mkstemp(suffix=".db", prefix="examenes_")
        os.close(fd)
        os.remove(self.db_path)  # ExamDatabase la creará vacía
        self.db = ExamDatabase(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_and_fetch_roundtrip(self):
        correction = make_correction()
        exam_id = self.db.save_correction(
            correction=correction,
            exam_template="plantilla_ejemplo.json",
            mode=1,
            grade_info={"scaled_score": 4.0, "literal_grade": "Suspenso"},
            student_id="10",
            exam_identifier="Matematicas_Tema1",
        )
        self.assertGreater(exam_id, 0)

        fetched = self.db.get_exam_by_id(exam_id)
        self.assertEqual(fetched["student_id"], "10")
        self.assertEqual(fetched["exam_identifier"], "Matematicas_Tema1")
        self.assertEqual(fetched["literal_grade"], "Suspenso")
        self.assertAlmostEqual(fetched["scaled_score"], 4.0, places=2)
        self.assertEqual(len(fetched["items"]), 2)

    def test_get_exams_by_identifier(self):
        for name in ("A. ALUMNO", "B. ALUMNO", "C. ALUMNO"):
            self.db.save_correction(
                make_correction(student_name=name),
                exam_identifier="Fisica_Parcial2",
                grade_info={"scaled_score": 6.0, "literal_grade": "Aprobado"},
            )
        # Otro identificador para asegurar que filtra
        self.db.save_correction(
            make_correction(student_name="OTRO"),
            exam_identifier="Mates_Tema3",
            grade_info={"scaled_score": 7.0, "literal_grade": "Notable"},
        )

        same = self.db.get_exams_by_identifier("Fisica_Parcial2")
        self.assertEqual(len(same), 3)
        # Debe venir ordenado por nombre
        self.assertEqual([e["student_name"] for e in same],
                         sorted(["A. ALUMNO", "B. ALUMNO", "C. ALUMNO"]))

    def test_get_student_history(self):
        # Mismo student_id, dos identificadores → ambos deben aparecer
        for ident in ("Mates_Tema1", "Mates_Tema2"):
            self.db.save_correction(
                make_correction(),
                exam_identifier=ident,
                student_id="42",
                grade_info={"scaled_score": 5.5, "literal_grade": "Aprobado"},
            )
        history = self.db.get_student_history("42")
        self.assertEqual(len(history), 2)
        identifiers = {e["exam_identifier"] for e in history}
        self.assertSetEqual(identifiers, {"Mates_Tema1", "Mates_Tema2"})

    def test_search_by_partial_name(self):
        self.db.save_correction(make_correction("ALONSO VIQUE, NOELIA"),
                                exam_identifier="X")
        self.db.save_correction(make_correction("LOPEZ LOPEZ, ANTONIO"),
                                exam_identifier="X")
        results = self.db.search_exams(student_name="LOPEZ")
        self.assertEqual(len(results), 1)
        self.assertIn("LOPEZ", results[0]["student_name"])

    def test_delete_exam_removes_items(self):
        exam_id = self.db.save_correction(make_correction())
        self.assertTrue(self.db.delete_exam(exam_id))
        self.assertIsNone(self.db.get_exam_by_id(exam_id))
        # Verifica que los ítems quedaron huérfanos limpiados
        conn = sqlite3.connect(self.db_path)
        n = conn.execute("SELECT COUNT(*) FROM exam_items WHERE exam_id = ?",
                         (exam_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(n, 0)

    def test_set_student_id_updates_existing_exam(self):
        exam_id = self.db.save_correction(make_correction(), student_id=None)
        self.assertIsNone(self.db.get_exam_by_id(exam_id)["student_id"])

        ok = self.db.set_student_id(exam_id, "42")
        self.assertTrue(ok)
        self.assertEqual(self.db.get_exam_by_id(exam_id)["student_id"], "42")

        # Re-asignar a otro alumno también funciona (sobrescribe)
        self.assertTrue(self.db.set_student_id(exam_id, "99"))
        self.assertEqual(self.db.get_exam_by_id(exam_id)["student_id"], "99")

    def test_set_student_id_can_unlink(self):
        exam_id = self.db.save_correction(make_correction(), student_id="7")
        self.assertEqual(self.db.get_exam_by_id(exam_id)["student_id"], "7")

        self.assertTrue(self.db.set_student_id(exam_id, None))
        self.assertIsNone(self.db.get_exam_by_id(exam_id)["student_id"])

    def test_set_student_id_returns_false_for_missing_exam(self):
        # rowcount==0 cuando el id no existe
        self.assertFalse(self.db.set_student_id(99999, "1"))


class TestSchemaMigration(unittest.TestCase):
    """
    Una BD legacy (creada antes de añadir `student_id` y `exam_identifier`)
    debe migrarse silenciosamente al instanciar `ExamDatabase`.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db", prefix="legacy_")
        os.close(fd)
        os.remove(self.db_path)

        # Crea esquema antiguo a mano (sin las dos columnas nuevas)
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_name_confidence REAL,
                total_score REAL NOT NULL,
                max_score REAL NOT NULL,
                percentage REAL NOT NULL,
                scaled_score REAL,
                literal_grade TEXT,
                correction_date TEXT NOT NULL,
                exam_template TEXT,
                mode INTEGER NOT NULL
            );
            CREATE TABLE exam_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                item_number INTEGER NOT NULL,
                weight REAL NOT NULL,
                description TEXT,
                symbol TEXT NOT NULL,
                confidence REAL NOT NULL,
                score REAL NOT NULL
            );
            INSERT INTO exams (student_name, total_score, max_score, percentage,
                               correction_date, mode)
            VALUES ('LEGACY USER', 5.0, 10.0, 50.0, '2024-01-01T00:00:00', 1);
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_migration_adds_missing_columns(self):
        db = ExamDatabase(self.db_path)  # dispara migración

        conn = sqlite3.connect(self.db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(exams)")}
        conn.close()
        self.assertIn("student_id", cols)
        self.assertIn("exam_identifier", cols)

        # Y el dato legacy sigue accesible — esto antes lanzaba OperationalError
        exams = db.get_all_exams()
        self.assertEqual(len(exams), 1)
        self.assertEqual(exams[0]["student_name"], "LEGACY USER")
        self.assertIsNone(exams[0]["student_id"])
        self.assertIsNone(exams[0]["exam_identifier"])

    def test_migration_is_idempotent(self):
        ExamDatabase(self.db_path)
        # Segunda instancia: no debe romper ni duplicar columnas
        db = ExamDatabase(self.db_path)
        # Inserta sin errores
        exam_id = db.save_correction(
            make_correction(),
            exam_identifier="NUEVO_TEMA",
            student_id="99",
        )
        self.assertGreater(exam_id, 0)


class TestExcelExport(unittest.TestCase):
    """La exportación a xlsx debe filtrar por identificador y respetar columnas."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db", prefix="exp_")
        os.close(fd)
        os.remove(self.db_path)
        self.db = ExamDatabase(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_export_creates_xlsx(self):
        try:
            import pandas  # noqa: F401
        except ImportError:
            self.skipTest("pandas no disponible")

        for name in ("ALUM A", "ALUM B"):
            self.db.save_correction(
                make_correction(student_name=name),
                exam_identifier="Quimica_T1",
                grade_info={"scaled_score": 7.0, "literal_grade": "Notable"},
                student_id="X",
            )

        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.xlsx")
            ok = self.db.export_exam_grades("Quimica_T1", out)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(out))
            self.assertGreater(os.path.getsize(out), 0)

    def test_export_returns_false_when_no_matches(self):
        try:
            import pandas  # noqa: F401
        except ImportError:
            self.skipTest("pandas no disponible")
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.xlsx")
            ok = self.db.export_exam_grades("NO_EXISTE", out)
            self.assertFalse(ok)
            self.assertFalse(os.path.exists(out))


class TestDbAdminCli(unittest.TestCase):
    """Smoke tests del CLI: dispara cada subcomando contra una BD efímera."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db", prefix="cli_")
        os.close(fd)
        os.remove(self.db_path)
        self.db = ExamDatabase(self.db_path)
        # Tres exámenes huérfanos: dos matcheables, uno no
        for name in ("GARCIA VELA, CARLA",
                     "LOPEZ LOPEZ, ANTONIO JOSE",
                     "INEXISTENTE NOMBRE ZZZ"):
            self.db.save_correction(
                make_correction(student_name=name),
                exam_identifier="Quimica_T1",
                grade_info={"scaled_score": 5.0, "literal_grade": "Aprobado"},
            )

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_info_runs(self):
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "info"])
        self.assertEqual(rc, 0)

    def test_relink_marks_matched_exams(self):
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv"])
        self.assertEqual(rc, 0)
        conn = sqlite3.connect(self.db_path)
        linked = conn.execute(
            "SELECT COUNT(*) FROM exams WHERE student_id IS NOT NULL"
        ).fetchone()[0]
        unlinked = conn.execute(
            "SELECT student_name FROM exams WHERE student_id IS NULL"
        ).fetchall()
        conn.close()
        self.assertEqual(linked, 2)
        self.assertEqual(len(unlinked), 1)
        self.assertIn("INEXISTENTE", unlinked[0][0])

    def test_relink_dry_run_does_not_persist(self):
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--dry-run"])
        self.assertEqual(rc, 0)
        conn = sqlite3.connect(self.db_path)
        linked = conn.execute(
            "SELECT COUNT(*) FROM exams WHERE student_id IS NOT NULL"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(linked, 0, "dry-run no debería persistir cambios")

    # --- relink --only-id ------------------------------------------------ #

    def _get_sid(self, exam_id: int):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT student_id FROM exams WHERE id = ?", (exam_id,)
        ).fetchone()
        conn.close()
        return row[0] if row else None

    def test_relink_only_id_with_fuzzy_match(self):
        import db_admin
        # Examen #1 corresponde a "GARCIA VELA, CARLA" → debe matchear
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--only-id", "1"])
        self.assertEqual(rc, 0)
        # Y los otros exámenes siguen huérfanos (no toca los demás)
        self.assertIsNotNone(self._get_sid(1))
        self.assertIsNone(self._get_sid(2))
        self.assertIsNone(self._get_sid(3))

    def test_relink_only_id_dry_run_does_not_persist(self):
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--only-id", "1",
                            "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIsNone(self._get_sid(1))

    def test_relink_only_id_with_manual_id_overrides_match(self):
        import db_admin
        # Asignar manualmente ID 999 al examen #3 (que no matcheaba)
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--only-id", "3",
                            "--manual-id", "999"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._get_sid(3), "999")

    def test_relink_only_id_manual_id_can_unlink_with_empty_string(self):
        import db_admin
        # Primero vincular el examen #1
        db_admin.main(["--db", self.db_path, "relink", "--csv", "alumnos.csv",
                       "--only-id", "1"])
        self.assertIsNotNone(self._get_sid(1))
        # Ahora des-vincular con --manual-id ""
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--only-id", "1",
                            "--manual-id", ""])
        self.assertEqual(rc, 0)
        self.assertIsNone(self._get_sid(1))

    def test_relink_only_id_missing_exam_returns_error(self):
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--only-id", "99999"])
        self.assertEqual(rc, 4)

    def test_relink_only_id_no_match_returns_specific_error(self):
        import db_admin
        # Examen #3 ("INEXISTENTE NOMBRE ZZZ") no matchea con --min-confidence alto
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv", "--only-id", "3",
                            "--min-confidence", "95"])
        self.assertEqual(rc, 5)
        self.assertIsNone(self._get_sid(3))

    # --- relink --only-id repetido (multi-id) ---------------------------- #

    def test_relink_multiple_only_ids_fuzzy(self):
        """Dos --only-id se vinculan por fuzzy match en una sola invocación."""
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv",
                            "--only-id", "1", "--only-id", "2"])
        self.assertEqual(rc, 0)
        self.assertIsNotNone(self._get_sid(1))
        self.assertIsNotNone(self._get_sid(2))
        # El tercero queda intacto (no estaba en --only-id)
        self.assertIsNone(self._get_sid(3))

    def test_relink_multiple_only_ids_with_single_manual_id_broadcasts(self):
        """Un solo --manual-id se aplica a todos los --only-id."""
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv",
                            "--only-id", "1", "--only-id", "2",
                            "--manual-id", "777"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._get_sid(1), "777")
        self.assertEqual(self._get_sid(2), "777")

    def test_relink_multiple_only_ids_with_positional_manual_ids(self):
        """N --manual-id con N --only-id se emparejan posicionalmente."""
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv",
                            "--only-id", "1", "--only-id", "2",
                            "--manual-id", "100", "--manual-id", "200"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._get_sid(1), "100")
        self.assertEqual(self._get_sid(2), "200")

    def test_relink_multiple_only_ids_cardinality_mismatch_returns_6(self):
        """Cardinalidad inválida (3 manual-id para 2 only-id) → rc=6."""
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv",
                            "--only-id", "1", "--only-id", "2",
                            "--manual-id", "100", "--manual-id", "200",
                            "--manual-id", "300"])
        self.assertEqual(rc, 6)
        # No tocó nada
        self.assertIsNone(self._get_sid(1))
        self.assertIsNone(self._get_sid(2))

    def test_relink_multiple_only_ids_partial_failure_returns_first_error(self):
        """Si un id existe y otro no, devuelve el primer rc!=0 (4) pero
        sigue procesando los demás (el que sí existe queda vinculado)."""
        import db_admin
        rc = db_admin.main(["--db", self.db_path, "relink",
                            "--csv", "alumnos.csv",
                            "--only-id", "99999", "--only-id", "1"])
        # 99999 no existe → rc=4; #1 sí matchea
        self.assertEqual(rc, 4)
        self.assertIsNotNone(self._get_sid(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
