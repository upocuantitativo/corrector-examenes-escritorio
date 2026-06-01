"""
console_utf8.py
===============
Pone la salida estándar (stdout/stderr) en UTF-8 al importarse, para que los
mensajes con emojis/símbolos (✓, ✗, ✅, ⚠, …) NO provoquen UnicodeEncodeError
en la consola de Windows (cp1252).

Uso: importar al principio de cualquier módulo que imprima caracteres no ASCII.

    import console_utf8  # noqa: F401

Es idempotente y silencioso: si el flujo no se puede reconfigurar, no falla.
"""
import sys

for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    try:
        if _stream is not None and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
