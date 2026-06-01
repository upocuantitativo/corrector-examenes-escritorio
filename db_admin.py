"""
Herramienta CLI para mantenimiento de la base de datos de exámenes.

Ejecutable sin abrir la GUI — diseñada para diagnosticar instalaciones rotas,
re-vincular alumnos a partir del CSV, listar exámenes y exportar notas.

Uso:
    python3 db_admin.py info
    python3 db_admin.py list [--identifier ID]
    python3 db_admin.py student <student_id>
    python3 db_admin.py relink [--csv alumnos.csv]
    python3 db_admin.py relink --only-id <exam_id> [--manual-id <student_id>]
    python3 db_admin.py relink --only-id 3 --only-id 7 [--manual-id <sid>]
    python3 db_admin.py export <identifier> <salida.xlsx>
    python3 db_admin.py migrate

Todos los subcomandos respetan `--db <ruta>` (por defecto `examenes.db`).
"""
from __future__ import annotations
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)

import argparse
import sqlite3
import sys
from typing import List

from exam_database import ExamDatabase
from student_database import StudentDatabase


# ---------------------------------------------------------------------------- #
# Subcomandos                                                                  #
# ---------------------------------------------------------------------------- #

def cmd_info(args: argparse.Namespace) -> int:
    """Resumen del estado de la BD."""
    db = ExamDatabase(args.db)
    stats = db.get_statistics()

    conn = sqlite3.connect(args.db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]
    n_models = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='model_versions'"
    ).fetchone()[0]
    if n_models:
        n_versions = conn.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0]
        n_samples = conn.execute("SELECT COUNT(*) FROM training_samples").fetchone()[0]
        n_labeled = conn.execute(
            "SELECT COUNT(*) FROM training_samples WHERE true_symbol IS NOT NULL"
        ).fetchone()[0]
    else:
        n_versions = n_samples = n_labeled = 0
    conn.close()

    print(f"BD: {args.db}")
    print(f"  Tablas: {', '.join(sorted(tables))}")
    print()
    print("Exámenes:")
    print(f"  Total           : {stats['total_exams']}")
    print(f"  Promedio (%)    : {stats['average_percentage']:.1f}")
    print(f"  Aprobados       : {stats['passed']}")
    print(f"  Suspensos       : {stats['failed']}")
    if stats["grade_distribution"]:
        print("  Por calificación:")
        for grade, n in sorted(stats["grade_distribution"].items()):
            print(f"    {grade:<15} {n}")
    print()
    print("Aprendizaje ML:")
    print(f"  Versiones modelo : {n_versions}")
    print(f"  Muestras totales : {n_samples}")
    print(f"  Etiquetadas      : {n_labeled}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Lista exámenes (opcionalmente filtrados por identificador)."""
    db = ExamDatabase(args.db)
    if args.identifier:
        exams = db.get_exams_by_identifier(args.identifier)
    else:
        exams = db.get_all_exams(limit=args.limit)

    if not exams:
        print("(sin resultados)")
        return 0

    print(f"{'ID':<5}{'Sid':<6}{'Estudiante':<35}"
          f"{'Nota':>7}{'Calif':>15}  Fecha")
    print("-" * 90)
    for e in exams:
        sid = e.get("student_id") or "-"
        note = f"{e['scaled_score']:.2f}" if e.get("scaled_score") else "-"
        grade = e.get("literal_grade") or "-"
        date = (e.get("correction_date") or "")[:16].replace("T", " ")
        print(f"{e['id']:<5}{sid:<6}{e['student_name'][:34]:<35}"
              f"{note:>7}{grade:>15}  {date}")
    return 0


def cmd_student(args: argparse.Namespace) -> int:
    """Histórico de un estudiante por ID."""
    db = ExamDatabase(args.db)
    history = db.get_student_history(args.student_id)
    if not history:
        print(f"Sin histórico para student_id={args.student_id!r}")
        return 1
    print(f"Histórico del estudiante {args.student_id}: {len(history)} examen(es)")
    for e in history:
        note = f"{e['scaled_score']:.2f}" if e.get("scaled_score") else "-"
        grade = e.get("literal_grade") or "-"
        date = (e.get("correction_date") or "")[:16].replace("T", " ")
        ident = e.get("exam_identifier") or "(sin id)"
        print(f"  · {date}  {ident:<25} {note:>6}  {grade}")
    return 0


def cmd_relink(args: argparse.Namespace) -> int:
    """
    Vincula exámenes contra el CSV de alumnos.

    Sin flags: recorre todos los exámenes con `student_id` NULL y aplica
    fuzzy matching sobre el `student_name` almacenado. Útil para reparar
    instalaciones donde un bug guardó todo como NULL.

    Con `--only-id <exam_id>`: re-vincula un único examen, incluso si ya
    estaba vinculado a otro alumno. Si además se pasa `--manual-id <sid>`,
    salta el matching y asigna ese student_id literal (útil cuando el OCR
    capturó mal el nombre y el profesor sabe quién es).

    `--only-id` se puede repetir para procesar varios exámenes en una sola
    invocación. `--manual-id` admite las mismas semánticas: un único valor
    se aplica a todos, o tantos valores como ids para emparejamiento
    posicional. Si las cardinalidades no encajan, devuelve rc=6.
    """
    # Rama: re-vincular uno o varios exámenes por id
    if args.only_id:
        return _relink_by_ids(args)

    # Rama por defecto: re-vincular todos los huérfanos
    student_db = StudentDatabase(args.csv)
    if not student_db.students:
        print(f"ERROR: no se pudo cargar CSV {args.csv}")
        return 2

    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT id, student_name FROM exams WHERE student_id IS NULL"
    ).fetchall()

    if not rows:
        print("Sin exámenes huérfanos. Nada que hacer.")
        conn.close()
        return 0

    print(f"Encontrados {len(rows)} examen(es) sin student_id. Vinculando...")
    linked = 0
    unmatched: List[str] = []
    for exam_id, name in rows:
        student, conf = student_db.find_student_by_name(name)
        if student and conf >= args.min_confidence:
            sid = str(student.get("Id", "")).strip()
            if sid:
                conn.execute("UPDATE exams SET student_id = ? WHERE id = ?",
                             (sid, exam_id))
                linked += 1
                if args.verbose:
                    print(f"  · #{exam_id} '{name[:30]}' → {sid} "
                          f"({student.get('ALUMNO', '')[:30]}, {conf:.1f}%)")
        else:
            unmatched.append(f"#{exam_id} {name}")

    if args.dry_run:
        conn.rollback()
        print(f"[DRY-RUN] Habrían quedado vinculados: {linked}/{len(rows)}")
    else:
        conn.commit()
        print(f"Vinculados: {linked}/{len(rows)}")

    conn.close()
    if unmatched:
        print(f"Sin match ({len(unmatched)}):")
        for u in unmatched[:10]:
            print(f"  - {u}")
        if len(unmatched) > 10:
            print(f"  ... ({len(unmatched) - 10} más)")
    return 0


def _relink_by_ids(args: argparse.Namespace) -> int:
    """
    Despacha re-vinculación de uno o varios exámenes (`--only-id` repetido).

    Empareja `--manual-id` con `--only-id`:
      * sin `--manual-id`         → fuzzy match para todos.
      * un solo `--manual-id`     → mismo id forzado para todos.
      * N `--manual-id`s == N ids → emparejamiento posicional.
      * cualquier otra cardinalidad → rc=6.

    Devuelve 0 si todos los ids procesados terminan en 0; en otro caso,
    el primer rc no-cero (la salida estándar imprime el detalle por id).
    """
    only_ids: List[int] = list(args.only_id)
    manual_ids = args.manual_id  # None | List[str]

    # Validación de cardinalidad de --manual-id frente a --only-id
    expanded_manual: List[str | None]
    if manual_ids is None:
        expanded_manual = [None] * len(only_ids)
    elif len(manual_ids) == 1:
        expanded_manual = manual_ids * len(only_ids)
    elif len(manual_ids) == len(only_ids):
        expanded_manual = list(manual_ids)
    else:
        print(
            f"ERROR: --manual-id se pasó {len(manual_ids)} vez(es) pero "
            f"--only-id {len(only_ids)} vez(es). Use 1 manual-id (para "
            f"todos) o tantos como ids (emparejamiento posicional)."
        )
        return 6

    overall_rc = 0
    for exam_id, mid in zip(only_ids, expanded_manual):
        if len(only_ids) > 1:
            print(f"\n=== Examen #{exam_id} ===")
        rc = _relink_single(args, exam_id, mid)
        if rc != 0 and overall_rc == 0:
            overall_rc = rc
    return overall_rc


def _relink_single(args: argparse.Namespace,
                   exam_id: int,
                   manual_id: "str | None") -> int:
    """
    Re-vincula un único examen identificado por `exam_id`.

    Casos:
      * `manual_id` no None → asigna ese id (cadena vacía → des-vincula).
        Si `args.csv` apunta a un CSV cargable, valida que el id exista.
      * `manual_id` None    → fuzzy match sobre el `student_name`,
        respeta `--min-confidence`.

    Soporta `--dry-run` para imprimir lo que haría sin tocar la BD.
    """
    conn = sqlite3.connect(args.db)
    row = conn.execute(
        "SELECT id, student_name, student_id FROM exams WHERE id = ?",
        (exam_id,),
    ).fetchone()
    if row is None:
        print(f"ERROR: no existe examen con id={exam_id}")
        conn.close()
        return 4

    current_id, current_name, current_sid = row
    print(f"Examen #{current_id}: nombre='{current_name}', "
          f"student_id actual={current_sid or 'NULL'}")

    # Caso: id forzado manualmente
    if manual_id is not None:
        new_sid = str(manual_id).strip() or None
        # Validación opcional contra CSV si está disponible
        if new_sid and args.csv:
            try:
                student_db = StudentDatabase(args.csv)
                if student_db.students:
                    found = student_db.get_student_by_id(new_sid)
                    if found is None:
                        print(f"⚠️ El id {new_sid} no aparece en {args.csv}.")
                    else:
                        print(f"  · validado en CSV: {found.get('ALUMNO', '')}")
            except Exception as e:
                print(f"  (no se pudo validar contra CSV: {e})")

        if args.dry_run:
            print(f"[DRY-RUN] Habría asignado student_id={new_sid!r} "
                  f"al examen #{exam_id}")
            conn.close()
            return 0

        conn.execute("UPDATE exams SET student_id = ? WHERE id = ?",
                     (new_sid, exam_id))
        conn.commit()
        conn.close()
        print(f"✅ Examen #{exam_id} → student_id = {new_sid!r}")
        return 0

    # Caso: fuzzy match
    student_db = StudentDatabase(args.csv)
    if not student_db.students:
        print(f"ERROR: no se pudo cargar CSV {args.csv}")
        conn.close()
        return 2

    student, conf = student_db.find_student_by_name(current_name or "")
    if not student or conf < args.min_confidence:
        print(f"Sin match suficiente (mejor candidato: "
              f"{student.get('ALUMNO', '?') if student else '—'}, "
              f"confianza {conf:.1f}%, umbral {args.min_confidence}%)")
        conn.close()
        return 5

    new_sid = str(student.get("Id", "")).strip() or None
    msg = (f"#{exam_id}: '{current_name}' → {new_sid} "
           f"({student.get('ALUMNO', '')}, {conf:.1f}%)")

    if args.dry_run:
        print(f"[DRY-RUN] {msg}")
        conn.close()
        return 0

    conn.execute("UPDATE exams SET student_id = ? WHERE id = ?",
                 (new_sid, exam_id))
    conn.commit()
    conn.close()
    print(f"✅ Vinculado: {msg}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Exporta notas de un identificador a Excel."""
    db = ExamDatabase(args.db)
    ok = db.export_exam_grades(args.identifier, args.output)
    return 0 if ok else 3


def cmd_migrate(args: argparse.Namespace) -> int:
    """Migra el esquema de la BD a la versión actual (idempotente)."""
    # La migración ya se dispara al instanciar ExamDatabase.
    ExamDatabase(args.db)
    print(f"BD {args.db} al día.")
    return 0


# ---------------------------------------------------------------------------- #
# Entry point                                                                  #
# ---------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Mantenimiento de la BD de exámenes (sin GUI).",
    )
    p.add_argument("--db", default="examenes.db",
                   help="Ruta de la BD (por defecto: examenes.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Resumen del estado de la BD").set_defaults(
        func=cmd_info)
    sub.add_parser("migrate", help="Aplica migraciones pendientes").set_defaults(
        func=cmd_migrate)

    p_list = sub.add_parser("list", help="Lista exámenes")
    p_list.add_argument("--identifier", help="Filtra por identificador de examen")
    p_list.add_argument("--limit", type=int, default=50,
                        help="Máximo a mostrar sin --identifier (default 50)")
    p_list.set_defaults(func=cmd_list)

    p_stu = sub.add_parser("student", help="Histórico de un estudiante por ID")
    p_stu.add_argument("student_id")
    p_stu.set_defaults(func=cmd_student)

    p_relink = sub.add_parser(
        "relink",
        help="Vincula exámenes con student_id NULL contra el CSV de alumnos",
    )
    p_relink.add_argument("--csv", default="alumnos.csv")
    p_relink.add_argument("--min-confidence", type=float, default=70.0,
                          help="Mínimo %% de similitud para aceptar match")
    p_relink.add_argument("--dry-run", action="store_true",
                          help="No persistir cambios, solo simular")
    p_relink.add_argument("-v", "--verbose", action="store_true")
    p_relink.add_argument(
        "--only-id", type=int, action="append", default=None,
        help="Re-vincular un examen por su id (entero). Repetible: "
             "`--only-id 3 --only-id 7` procesa ambos. A diferencia del "
             "modo masivo, permite tocar exámenes que ya tenían "
             "student_id asignado."
    )
    p_relink.add_argument(
        "--manual-id", action="append", default=None,
        help="Asignar este student_id literalmente (sin fuzzy match). "
             "Solo válido junto a --only-id. Cadena vacía → des-vincular. "
             "Repetible: si se pasa N veces emparejado con N `--only-id` "
             "se aplica posicionalmente; si se pasa 1 vez, se aplica a "
             "todos los ids."
    )
    p_relink.set_defaults(func=cmd_relink)

    p_exp = sub.add_parser("export", help="Exporta notas a Excel")
    p_exp.add_argument("identifier")
    p_exp.add_argument("output")
    p_exp.set_defaults(func=cmd_export)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
