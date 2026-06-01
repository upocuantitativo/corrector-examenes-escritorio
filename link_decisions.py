"""
Logica pura de decision para los flujos de vinculacion examen-alumno.

Estos helpers extraen la parte deciscional (que `student_id` queda, que mensaje
mostrar, que efecto tiene cancelar) del codigo tkinter en `main_app.py`. El
resultado es una capa testeable sin GUI: la GUI solo tiene que llamar a la
funcion correspondiente, mostrar dialogos y aplicar el `LinkAction` resultante
sobre la BD.

Cubre dos flujos:

* `decide_link_on_save` — la que dispara
  `MainApplication._save_correction` cada vez que el profesor guarda una
  correccion nueva. Entra el `(status, student, confidence)` que devuelve
  `StudentDatabase.resolve_link`, mas el resultado del dialogo de baja
  confianza y del picker manual (si la GUI los abrio). Sale una accion
  estructurada que dice si se vincula, a que `student_id`, y con que mensaje.

* `decide_link_on_relink` — la que dispara
  `HistoryWindow._relink_student` cuando el profesor pulsa el boton
  "Re-vincular alumno (Ctrl+R)". Entra el examen y el resultado del picker
  (mas la respuesta a "Quieres des-vincular?" si se cancelo). Sale la
  accion: vincular a id nuevo, desvincular, o no-op.

Diseno:

* Las dos funciones son puras: no importan tkinter ni tocan BD. Los dialogos
  (de confianza baja, picker manual, confirmacion de unlink) los inyecta la
  GUI a traves de callbacks opcionales. Eso permite los cuatro tests que la
  GUI hace pero sin levantar `tkinter.Tk()`.
* La GUI sigue siendo responsable de aplicar la accion (llamada a
  `database.set_student_id` o `database.save_correction`) y de mostrar el
  `link_note` resultante. No se mete logica de BD aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


# ---------------------------------------------------------------------------- #
# Tipos de salida                                                              #
# ---------------------------------------------------------------------------- #

@dataclass
class LinkAction:
    """
    Decision estructurada sobre como vincular un examen.

    Atributos:
      student_id: ID a persistir en la columna `exams.student_id`. `None`
        significa "dejar sin vincular" (o desvincular si ya estaba).
      link_note: Texto humano que la GUI mostrara al profesor describiendo
        que decision se tomo y por que.
      kind: Etiqueta corta para tests/log; uno de:
        "matched"     → vinculado por match automatico (confianza >= umbral).
        "confirmed"   → confianza baja pero el profesor confirmo.
        "manual"      → el profesor lo eligio en el picker manual.
        "cancelled"   → el profesor cancelo; queda sin vincular.
        "unlinked"    → el profesor explicitamente desvinculo un examen
                         que ya tenia `student_id`.
        "noop"        → no se aplica ningun cambio (la GUI no toca BD).
        "unavailable" → no hay CSV cargado, ni se intento vincular.
    """
    student_id: Optional[str]
    link_note: str
    kind: str


# Callbacks que la GUI inyecta para los dialogos. Devuelven None si el
# profesor cancelo, o el dict del alumno elegido (para el picker) / True/False
# (para los messageboxes).
LowConfidencePrompt = Callable[[str, Dict, float], Optional[bool]]
"""Args: (detected_name, candidate, confidence) → True acepta / False rechaza
candidato y abre picker / None cancela y guarda sin vincular."""

ManualPickerPrompt = Callable[[str, str], Optional[Dict]]
"""Args: (detected_name, reason) → dict del alumno elegido o None si cancela."""

ConfirmUnlinkPrompt = Callable[[str], bool]
"""Args: (current_sid) → True si el profesor confirma desvincular."""


# ---------------------------------------------------------------------------- #
# Helpers privados                                                             #
# ---------------------------------------------------------------------------- #

def _student_id_as_str(student: Dict) -> Optional[str]:
    """
    Normaliza el `Id` del CSV a `str` (o `None` si esta vacio).

    El CSV de alumnos guarda `Id` como cadena; la BD de examenes la columna
    `student_id` es TEXT. Asi que normalizamos a str aqui para que la GUI no
    tenga que repetir el `str(...) if ... else None` cuatro veces.
    """
    sid = student.get("Id") if student else None
    if sid is None:
        return None
    sid_str = str(sid).strip()
    return sid_str or None


# ---------------------------------------------------------------------------- #
# Flujo 1: vinculacion al guardar una correccion nueva                         #
# ---------------------------------------------------------------------------- #

def decide_link_on_save(
    detected_name: str,
    resolve_result: tuple,
    low_confidence_prompt: Optional[LowConfidencePrompt] = None,
    manual_picker_prompt: Optional[ManualPickerPrompt] = None,
) -> LinkAction:
    """
    Decide como vincular un examen recien corregido.

    Args:
        detected_name: nombre tal cual lo extrajo el OCR (puede ir vacio).
        resolve_result: la tupla `(status, student, confidence)` que
            devuelve `StudentDatabase.resolve_link`. Cada status dispara una
            rama distinta:
              "matched"     → vincula directamente.
              "low"         → llama al `low_confidence_prompt` (Si/No/Cancel).
              "none"        → llama al `manual_picker_prompt`.
              "unavailable" → no hace nada, deja `student_id = None`.
        low_confidence_prompt: callback que pinta el messagebox Si/No/Cancel.
            Si la GUI no lo pasa, el flujo asume "Cancel" (guarda sin
            vincular) — util para tests deterministas.
        manual_picker_prompt: callback que abre el picker manual. Si no se
            pasa, el flujo asume "no se eligio nadie".

    Returns:
        `LinkAction` con el `student_id` final y el mensaje a mostrar.
    """
    status, student, confidence = resolve_result

    if status == "matched":
        sid = _student_id_as_str(student)
        name = student.get("ALUMNO", "?")
        return LinkAction(
            student_id=sid,
            link_note=(
                f"Alumno vinculado: {name} (ID {sid}, "
                f"confianza {confidence:.0f}%)"
            ),
            kind="matched",
        )

    if status == "low":
        # Si la GUI no inyecta un prompt, tratamos como "Cancel" (igual que
        # hace el messagebox tradicional cuando se cierra con la X). Esto
        # ademas hace los tests deterministas sin tener que mockear tkinter.
        choice = (low_confidence_prompt(detected_name, student, confidence)
                  if low_confidence_prompt else None)

        if choice is True:
            sid = _student_id_as_str(student)
            name = student.get("ALUMNO", "?")
            return LinkAction(
                student_id=sid,
                link_note=(
                    f"Alumno vinculado manualmente: {name} (ID {sid}, "
                    f"confianza {confidence:.0f}%)"
                ),
                kind="confirmed",
            )
        if choice is False:
            # Rechazo el candidato y pidio buscar a mano.
            return _run_manual_picker(
                detected_name,
                reason=(
                    f"Confianza demasiado baja con "
                    f"'{student.get('ALUMNO', '?')}' ({confidence:.0f}%)."
                ),
                manual_picker_prompt=manual_picker_prompt,
            )
        # Cancelar (None) → guarda sin vincular.
        return LinkAction(
            student_id=None,
            link_note="Guardado sin alumno vinculado (decision del profesor)",
            kind="cancelled",
        )

    if status == "none":
        return _run_manual_picker(
            detected_name,
            reason=f"No se encontro ningun alumno parecido a '{detected_name}'.",
            manual_picker_prompt=manual_picker_prompt,
        )

    # status == "unavailable" (o cualquier otro fallback)
    return LinkAction(
        student_id=None,
        link_note="Sin BD de alumnos cargada (alumnos.csv ausente)",
        kind="unavailable",
    )


def _run_manual_picker(
    detected_name: str,
    reason: str,
    manual_picker_prompt: Optional[ManualPickerPrompt],
) -> LinkAction:
    """Lanza el picker manual y traduce su resultado a un `LinkAction`."""
    chosen = (manual_picker_prompt(detected_name, reason)
              if manual_picker_prompt else None)
    if chosen is None:
        return LinkAction(
            student_id=None,
            link_note="Sin alumno vinculado (no se eligio ninguno)",
            kind="cancelled",
        )
    sid = _student_id_as_str(chosen)
    name = chosen.get("ALUMNO", "?")
    return LinkAction(
        student_id=sid,
        link_note=f"Alumno vinculado manualmente: {name} (ID {sid})",
        kind="manual",
    )


# ---------------------------------------------------------------------------- #
# Flujo 2: re-vinculacion desde el historico (Ctrl+R)                          #
# ---------------------------------------------------------------------------- #

def decide_relink(
    exam: Dict,
    manual_picker_prompt: Optional[ManualPickerPrompt] = None,
    confirm_unlink_prompt: Optional[ConfirmUnlinkPrompt] = None,
) -> LinkAction:
    """
    Decide que hacer cuando el profesor pulsa "Re-vincular alumno (Ctrl+R)"
    sobre un examen ya guardado en el historico.

    Args:
        exam: fila del examen tal cual la devuelve
            `ExamDatabase.get_exam_by_id`. Se leen `id`, `student_name` y
            `student_id`.
        manual_picker_prompt: callback que abre el picker. None == cancelar.
        confirm_unlink_prompt: callback que pregunta "¿Desvincular?".
            Solo se llama si el examen *ya* tenia `student_id` y el profesor
            cancelo el picker.

    Returns:
        `LinkAction` con el efecto a aplicar:
          kind="manual"   → llamar a `db.set_student_id(exam_id, sid)`.
          kind="unlinked" → llamar a `db.set_student_id(exam_id, None)`.
          kind="noop"     → no tocar nada.
    """
    exam_id = exam.get("id")
    detected_name = exam.get("student_name") or ""
    current_sid = exam.get("student_id")

    reason = (
        f"Examen #{exam_id} — actualmente vinculado a student_id={current_sid}"
        if current_sid
        else f"Examen #{exam_id} — actualmente sin vincular"
    )

    chosen = (manual_picker_prompt(detected_name, reason)
              if manual_picker_prompt else None)

    if chosen is None:
        # Usuario cancelo. Si tenia vinculo previo, le ofrecemos
        # desvincularlo; si no, no-op.
        if current_sid and confirm_unlink_prompt is not None:
            if confirm_unlink_prompt(str(current_sid)):
                return LinkAction(
                    student_id=None,
                    link_note=f"Examen #{exam_id} des-vinculado.",
                    kind="unlinked",
                )
        return LinkAction(
            student_id=current_sid if current_sid is not None else None,
            link_note="Sin cambios.",
            kind="noop",
        )

    new_sid = _student_id_as_str(chosen)
    name = chosen.get("ALUMNO", "?")
    return LinkAction(
        student_id=new_sid,
        link_note=f"Examen #{exam_id} → {name} (ID {new_sid})",
        kind="manual",
    )
