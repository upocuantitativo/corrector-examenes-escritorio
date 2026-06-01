"""
Tests de las decisiones puras de vinculacion (link_decisions.py).

Estas pruebas cubren las cuatro ramas que `MainApplication._save_correction`
ejerce al guardar una correccion, y los tres caminos que
`HistoryWindow._relink_student` ejerce sobre el historico. Antes solo se
podian verificar a mano en Windows con la GUI viva; ahora son determinismas
y corren en CI sin tkinter.

Ejecutar:
    python3 -m unittest test_link_decisions -v
"""
from __future__ import annotations

import unittest
import unittest.mock

from link_decisions import (
    LinkAction,
    decide_link_on_save,
    decide_relink,
)


# ---------------------------------------------------------------------------- #
# Helpers                                                                      #
# ---------------------------------------------------------------------------- #

def make_student(sid="10", name="GARCIA VELA, CARLA"):
    """Construye una fila de alumno tal cual la devuelve StudentDatabase."""
    return {"Id": sid, "ALUMNO": name, "DNI": "00000000A"}


def make_exam(exam_id=1, name="GARCIA VELA, CARLA", sid=None):
    """Construye una fila de examen tal cual la devuelve get_exam_by_id."""
    return {"id": exam_id, "student_name": name, "student_id": sid}


# ---------------------------------------------------------------------------- #
# decide_link_on_save — 4 ramas                                                #
# ---------------------------------------------------------------------------- #

class TestDecideLinkOnSaveMatched(unittest.TestCase):
    """Match automatico con confianza alta — sin preguntar nada al profesor."""

    def test_matched_sets_sid_and_message(self):
        # 92.7 → 93 al formatear con {:.0f}. Evitamos 92.5 porque Python usa
        # banker's rounding y formatea 92.5 como "92", no como "93".
        student = make_student(sid="10", name="GARCIA VELA, CARLA")
        action = decide_link_on_save(
            detected_name="GARCIA VELA, CARLA",
            resolve_result=("matched", student, 92.7),
        )
        self.assertEqual(action.kind, "matched")
        self.assertEqual(action.student_id, "10")
        self.assertIn("GARCIA VELA, CARLA", action.link_note)
        self.assertIn("ID 10", action.link_note)
        self.assertIn("93%", action.link_note)

    def test_matched_normalises_integer_id_to_str(self):
        # Defensivo: si por error llega int, devolvemos str para que la
        # columna TEXT de SQLite no haga conversion implicita.
        student = make_student(sid=42)
        action = decide_link_on_save(
            detected_name="X",
            resolve_result=("matched", student, 100.0),
        )
        self.assertEqual(action.student_id, "42")
        self.assertIsInstance(action.student_id, str)

    def test_matched_does_not_call_prompts(self):
        sentinel = unittest.mock.MagicMock(side_effect=AssertionError(
            "matched no debe llamar a ningun prompt"
        ))
        action = decide_link_on_save(
            detected_name="X",
            resolve_result=("matched", make_student(), 90.0),
            low_confidence_prompt=sentinel,
            manual_picker_prompt=sentinel,
        )
        self.assertEqual(action.kind, "matched")


class TestDecideLinkOnSaveLowConfidence(unittest.TestCase):
    """Match dudoso — Si confirma, No abre picker, Cancel guarda sin vincular."""

    def test_low_user_says_yes(self):
        candidate = make_student(sid="10", name="GARCIA VELA, CARLA")
        action = decide_link_on_save(
            detected_name="garci vela",
            resolve_result=("low", candidate, 68.0),
            low_confidence_prompt=lambda n, c, cf: True,  # acepta
        )
        self.assertEqual(action.kind, "confirmed")
        self.assertEqual(action.student_id, "10")
        self.assertIn("Alumno vinculado manualmente", action.link_note)
        self.assertIn("68%", action.link_note)

    def test_low_user_says_no_then_picks_manually(self):
        candidate = make_student(sid="10", name="GARCIA VELA, CARLA")
        chosen = make_student(sid="33", name="OTRA, ALUMNA")

        captured = {}
        def picker(detected, reason):
            captured["detected"] = detected
            captured["reason"] = reason
            return chosen

        action = decide_link_on_save(
            detected_name="garci vela",
            resolve_result=("low", candidate, 65.0),
            low_confidence_prompt=lambda n, c, cf: False,  # rechaza
            manual_picker_prompt=picker,
        )
        self.assertEqual(action.kind, "manual")
        self.assertEqual(action.student_id, "33")
        # La razon que viaja al picker debe mencionar al candidato rechazado
        self.assertIn("GARCIA VELA, CARLA", captured["reason"])
        self.assertEqual(captured["detected"], "garci vela")

    def test_low_user_says_no_and_cancels_picker(self):
        action = decide_link_on_save(
            detected_name="garci vela",
            resolve_result=("low", make_student(), 65.0),
            low_confidence_prompt=lambda n, c, cf: False,
            manual_picker_prompt=lambda n, r: None,  # cancela picker
        )
        self.assertEqual(action.kind, "cancelled")
        self.assertIsNone(action.student_id)

    def test_low_user_cancels(self):
        action = decide_link_on_save(
            detected_name="garci vela",
            resolve_result=("low", make_student(), 65.0),
            low_confidence_prompt=lambda n, c, cf: None,  # Cancel
        )
        self.assertEqual(action.kind, "cancelled")
        self.assertIsNone(action.student_id)
        self.assertIn("decision del profesor", action.link_note)

    def test_low_without_prompt_defaults_to_cancel(self):
        # Sin prompt inyectado, equivale a "Cancel" — comportamiento de un
        # messagebox cerrado con la X. No debe romper.
        action = decide_link_on_save(
            detected_name="garci vela",
            resolve_result=("low", make_student(), 65.0),
        )
        self.assertEqual(action.kind, "cancelled")
        self.assertIsNone(action.student_id)


class TestDecideLinkOnSaveNoCandidate(unittest.TestCase):
    """Sin candidato — abre directamente el picker manual."""

    def test_none_picker_returns_student(self):
        chosen = make_student(sid="77", name="ELEGIDA, MANUAL")
        action = decide_link_on_save(
            detected_name="ZZZ INEXISTENTE",
            resolve_result=("none", None, 0.0),
            manual_picker_prompt=lambda n, r: chosen,
        )
        self.assertEqual(action.kind, "manual")
        self.assertEqual(action.student_id, "77")
        self.assertIn("ELEGIDA, MANUAL", action.link_note)

    def test_none_picker_cancelled(self):
        action = decide_link_on_save(
            detected_name="ZZZ",
            resolve_result=("none", None, 0.0),
            manual_picker_prompt=lambda n, r: None,
        )
        self.assertEqual(action.kind, "cancelled")
        self.assertIsNone(action.student_id)
        self.assertIn("no se eligio", action.link_note.lower())

    def test_none_without_picker_returns_cancelled(self):
        action = decide_link_on_save(
            detected_name="ZZZ",
            resolve_result=("none", None, 0.0),
        )
        self.assertEqual(action.kind, "cancelled")
        self.assertIsNone(action.student_id)


class TestDecideLinkOnSaveUnavailable(unittest.TestCase):
    """Sin CSV cargado — no debe llamar a ningun prompt, ni guardar id."""

    def test_unavailable_returns_no_id(self):
        prompt = unittest.mock.MagicMock(side_effect=AssertionError(
            "unavailable no debe llamar a prompts"
        ))
        action = decide_link_on_save(
            detected_name="X",
            resolve_result=("unavailable", None, 0.0),
            low_confidence_prompt=prompt,
            manual_picker_prompt=prompt,
        )
        self.assertEqual(action.kind, "unavailable")
        self.assertIsNone(action.student_id)
        self.assertIn("alumnos.csv", action.link_note.lower())


# ---------------------------------------------------------------------------- #
# decide_relink — 3 caminos                                                    #
# ---------------------------------------------------------------------------- #

class TestDecideRelinkBindsToChosen(unittest.TestCase):
    """Profesor elige un alumno → kind=manual."""

    def test_relink_orphan_picks_student(self):
        exam = make_exam(exam_id=7, name="GARCIA VELA, CARLA", sid=None)
        chosen = make_student(sid="10", name="GARCIA VELA, CARLA")

        captured = {}
        def picker(detected, reason):
            captured["detected"] = detected
            captured["reason"] = reason
            return chosen

        action = decide_relink(exam=exam, manual_picker_prompt=picker)
        self.assertEqual(action.kind, "manual")
        self.assertEqual(action.student_id, "10")
        self.assertIn("#7", action.link_note)
        self.assertEqual(captured["detected"], "GARCIA VELA, CARLA")
        self.assertIn("sin vincular", captured["reason"])

    def test_relink_already_linked_reflects_in_reason(self):
        exam = make_exam(exam_id=3, sid="42")
        captured = {}
        def picker(detected, reason):
            captured["reason"] = reason
            return make_student(sid="55", name="OTRO ALUMNO")

        action = decide_relink(exam=exam, manual_picker_prompt=picker)
        self.assertEqual(action.kind, "manual")
        self.assertEqual(action.student_id, "55")
        self.assertIn("student_id=42", captured["reason"])

    def test_relink_normalises_int_id_to_str(self):
        exam = make_exam(exam_id=1)
        action = decide_relink(
            exam=exam,
            manual_picker_prompt=lambda n, r: make_student(sid=99),
        )
        self.assertEqual(action.student_id, "99")


class TestDecideRelinkUnlink(unittest.TestCase):
    """Profesor cancela el picker en un examen ya vinculado → ofrece unlink."""

    def test_cancel_then_confirm_unlink(self):
        exam = make_exam(exam_id=5, sid="42")
        action = decide_relink(
            exam=exam,
            manual_picker_prompt=lambda n, r: None,
            confirm_unlink_prompt=lambda sid: True,
        )
        self.assertEqual(action.kind, "unlinked")
        self.assertIsNone(action.student_id)
        self.assertIn("des-vinculado", action.link_note)

    def test_cancel_then_decline_unlink(self):
        exam = make_exam(exam_id=5, sid="42")
        action = decide_relink(
            exam=exam,
            manual_picker_prompt=lambda n, r: None,
            confirm_unlink_prompt=lambda sid: False,
        )
        self.assertEqual(action.kind, "noop")
        # No-op no debe alterar el sid actual (la GUI no recarga la fila).
        self.assertEqual(action.student_id, "42")

    def test_cancel_passes_current_sid_to_confirm(self):
        exam = make_exam(exam_id=9, sid="123")
        captured = {}
        def confirm(sid):
            captured["sid"] = sid
            return True
        decide_relink(
            exam=exam,
            manual_picker_prompt=lambda n, r: None,
            confirm_unlink_prompt=confirm,
        )
        self.assertEqual(captured["sid"], "123")


class TestDecideRelinkNoop(unittest.TestCase):
    """Cancela picker sobre examen huerfano → no-op silencioso, sin preguntar."""

    def test_cancel_on_orphan_is_noop(self):
        exam = make_exam(exam_id=7, sid=None)
        confirm = unittest.mock.MagicMock(side_effect=AssertionError(
            "no debe preguntar si no habia vinculo previo"
        ))
        action = decide_relink(
            exam=exam,
            manual_picker_prompt=lambda n, r: None,
            confirm_unlink_prompt=confirm,
        )
        self.assertEqual(action.kind, "noop")
        self.assertIsNone(action.student_id)

    def test_cancel_without_confirm_callback_is_noop(self):
        # Si la GUI no inyecta el callback de confirmar unlink, el flujo no
        # debe explotar — simplemente se queda en noop aunque hubiera vinculo.
        exam = make_exam(exam_id=7, sid="42")
        action = decide_relink(
            exam=exam,
            manual_picker_prompt=lambda n, r: None,
        )
        self.assertEqual(action.kind, "noop")


# ---------------------------------------------------------------------------- #
# LinkAction dataclass                                                         #
# ---------------------------------------------------------------------------- #

class TestLinkActionShape(unittest.TestCase):
    """Smoke test del dataclass: campos y tipos."""

    def test_fields_present(self):
        a = LinkAction(student_id="1", link_note="x", kind="matched")
        self.assertEqual(a.student_id, "1")
        self.assertEqual(a.link_note, "x")
        self.assertEqual(a.kind, "matched")


if __name__ == "__main__":
    unittest.main(verbosity=2)
