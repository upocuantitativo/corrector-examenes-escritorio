# NEXT_STEP

## Hecho (sesión 2026-06-01) — Versión escritorio del corrector TIPO TEST + APK

A partir del prototipo y la forma de corregir a los que se llegó en la PWA
(`corrector_movil/`, publicada en
https://upocuantitativo.github.io/corrector-examenes/), se ha llevado el mismo
concepto a la **versión de escritorio** del proyecto y se ha generado un **APK**.

### Núcleo + GUI de escritorio (nuevos)

- **`test_corrector_core.py`** — núcleo lógico SIN tkinter (probable y probado):
  - Prototipo: test de N (10) preguntas × 3 opciones a/b/c; 1 ó 2 páginas
    (1-4 / 5-10). Modelos 1 y 2 precargados con sus soluciones.
  - Corrección idéntica a la PWA: **+0,30 acierto / −0,10 fallo**; no contestada
    = 0; **duda (2+ marcas) = 0, excluida**; nota/10 y literal.
  - `ExamLibrary` con guardado/carga JSON (crear/renombrar/borrar exámenes con
    nombre). Geometría de calibración (2 anclas) y detección por densidad de
    tinta (`numpy`) calcadas de la PWA.
- **`corrector_test_gui.py`** — app Tkinter de escritorio (gemela de la PWA):
  selector/creación de exámenes, edición de soluciones a mano o **desde foto de
  un examen corregido**, carga de imagen, calibración por clic, 2 referencias,
  detección, overlay ✔/✘/? y cuadro de puntuación. Lanzador **`CORRECTOR_TEST.bat`**.
- **`test_test_corrector.py`** — 14 tests (puntuación, biblioteca, geometría,
  detección sobre imágenes sintéticas) → **14/14 OK**.
- **`plantilla_test_estadistica.json`** — biblioteca de ejemplo (Modelos 1 y 2,
  2 páginas) para el corrector de escritorio.

### APK (carpeta `apk_build/`, fuera del repo publicado)

- Generado con **Bubblewrap** (TWA que envuelve la PWA publicada). JDK 17 + SDK
  Android ya estaban en `~/.bubblewrap`. Proyecto en `apk_build/`; build real en
  ruta ASCII `C:\corrector_apk` (el plugin de Android rechaza rutas con «Ó»).
  Keystore `android.keystore` (alias `android`, pass `corrector`).
- APK firmado de salida: ver `corrector-examenes.apk` en la carpeta del proyecto.

### Arreglo de Windows + publicación (añadido)

- **`console_utf8.py`** (nuevo): pone stdout/stderr en UTF-8 al importarse;
  importado al inicio de los módulos que imprimen símbolos (✓/✗/✅/⚠). Corrige
  los `UnicodeEncodeError` de la consola cp1252 de Windows. **Tests: 81/81 OK**
  en Windows (antes 20 fallos por emojis; eran del entorno, no regresión).
- **Repo público del escritorio**:
  https://github.com/upocuantitativo/corrector-examenes-escritorio
  (cuenta `upocuantitativo`). EXCLUIDOS por privacidad: `alumnos.csv`, `*.db`,
  carpeta `examen/` (imágenes con nombre/DNI), keystore, APK y `corrector_movil/`
  (que tiene su propio repo). 59 ficheros, verificado sin datos sensibles.

### Siguiente paso pendiente (escritorio/APK)

- Probar `corrector_test_gui.py` en Windows con pantalla (la lógica está cubierta
  por tests; falta validar la interacción tkinter real: clics de calibración,
  carga de imagen, overlay).
- Instalar el `.apk` en un móvil (ajustes → permitir orígenes desconocidos) y
  comprobar que abre la PWA a pantalla completa.

---

## Hecho (sesión 2026-06-01) — App móvil PWA de corrección

Nuevo entregable independiente del programa de escritorio: una **app web
instalable (PWA)** para corregir exámenes tipo test con la cámara del móvil.
Carpeta: `corrector_movil/`.

### Qué hace

- Corrige test de 10 preguntas × 3 opciones (a/b/c).
- **Algoritmo de corrección adaptado del proyecto de escritorio**:
  acierto = **+0,30**, fallo = **−0,10**, no contestada = 0,
  **2+ opciones marcadas = DUDA** (amarillo ?, excluida del total).
  Nota /10 = puntos/3,00×10. Literal: Sobresaliente ≥9 / Notable ≥7 /
  Aprobado ≥5 / Suspenso.
- **Soluciones precargadas** (editables y persistidas en localStorage):
  - Modelo 1 (Duración subrayada): a,a,b,a,a,a,c,b,a,a
  - Modelo 2 (Duración sin subrayar): b,a,a,c,b,c,a,c,b,b
- **Captura**: `<input capture=environment>` (funciona aunque abras el HTML
  directo, sin HTTPS) + cámara en vivo opcional si hay contexto seguro.
- **Panel de corrección por toque** (siempre fiable, sin configurar nada):
  fila por pregunta con a/b/c, columna de solución, icono ✔/✘/?/·, y cuadro
  resumen (aciertos/fallos/dudas/blancos + total desglosado + nota).
- **Detección automática opcional**: calibración 1 vez por modelo (tocar las
  30 letras) → guarda posiciones relativas a 2 anclas (Q1a, Q10c). En cada
  examen el profe marca solo 2 referencias y `detect()` mide densidad de
  tinta en discos ROI por opción; argmax = respuesta, top-2 cercanos = duda,
  todo bajo el suelo = en blanco. Deslizador de sensibilidad. Overlay ✔/✘/?
  dibujado sobre la foto.

### Archivos creados

- `corrector_movil/index.html` — app completa (HTML+CSS+JS, ~317 líneas JS).
- `corrector_movil/manifest.webmanifest`, `sw.js`, `icon-192.png`,
  `icon-512.png` — instalable y offline.
- `corrector_movil/LEEME.md` — guía de uso, calibración e instalación.

### Verificado en este entorno

- `node --check` del JS embebido → **sintaxis OK**.
- Renderizado real con Playwright (servido por `python -m http.server`):
  carga sin errores (solo 404 de favicon, irrelevante), modelo 1 muestra las
  10 soluciones correctas, panel y cuadro total operativos.

### Publicado (2026-06-01)

- Repo Git en `corrector_movil/` (rama `main`, commit inicial).
- Repo GitHub **público**: https://github.com/upocuantitativo/corrector-examenes
  (cuenta `upocuantitativo`).
- **GitHub Pages activo** → URL para el móvil:
  **https://upocuantitativo.github.io/corrector-examenes/**
  (HTTP 200; manifest/sw/iconos accesibles → instalable y offline).

## Siguiente paso pendiente

**Probar en un móvil real** (es lo único que requiere persona con el
dispositivo):

1. Abrir en el móvil **https://upocuantitativo.github.io/corrector-examenes/**
   y «Añadir a pantalla de inicio».
2. Verificar flujo a mano (sin calibrar): foto → tocar respuestas → cuadro
   total correcto. Caso de prueba leído de las fotos del alumno (Modelo 1):
   respuestas b,a,a,c,a,c,a,a,a,b → 3 aciertos / 7 fallos → **0,20 / 3,00**.
3. Calibrar Modelo 1 con una foto bien encuadrada (30 toques) y probar
   detección automática + 2 referencias; ajustar sensibilidad.
4. «Añadir a pantalla de inicio» para el icono tipo app.

### Pendiente del proyecto de escritorio (sin cambios esta sesión)

- Verificación en instalación real Windows con cámara/GUI de los diálogos
  tkinter de vinculación (ver historial anterior). Baseline 67/67.
