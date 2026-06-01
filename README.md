# Sistema de Corrección de Exámenes con Reconocimiento de Imagen

Sistema automático para corregir exámenes utilizando reconocimiento de símbolos mediante cámara web.

---

## 🆕 Corrector TIPO TEST (prototipo convergente · 2026)

Además del sistema clásico basado en símbolos ✓/✗/~, el proyecto incorpora un
**corrector de exámenes tipo test** (opción múltiple a/b/c) en dos formas que
comparten exactamente el mismo prototipo y la misma forma de corregir:

- **App móvil / PWA** — `corrector_movil/` · en vivo:
  **https://upocuantitativo.github.io/corrector-examenes/**
  (instalable en el móvil; también empaquetable como **APK**, ver `apk_build/`).
- **App de escritorio** — `corrector_test_gui.py` (núcleo en
  `test_corrector_core.py`, lanzador `CORRECTOR_TEST.bat`).

**Prototipo de examen**: test de 10 preguntas × 3 opciones (a/b/c); el alumno
rodea la letra; 1 ó 2 páginas (1-4 / 5-10). Modelos precargados:

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|--|--|--|--|--|--|--|--|--|--|--|
| **Modelo 1** | a | a | b | a | a | a | c | b | a | a |
| **Modelo 2** | b | a | a | c | b | c | a | c | b | b |

**Forma de corregir**: **+0,30** por acierto, **−0,10** por fallo, no contestada
= 0, y **2+ opciones marcadas = DUDA** (amarillo, excluida del total). Nota /10 =
puntos / 3,00 × 10 (Sobresaliente ≥9 · Notable ≥7 · Aprobado ≥5 · Suspenso).
Gestión de exámenes con nombre y soluciones definibles a mano o **desde la foto
de un examen ya corregido**. Tests: `python -m unittest test_test_corrector`.

---

## Características

- **Diseño de Pesos**: Configura plantillas de examen con pesos personalizados para cada ítem
- **Tres Modos de Corrección Mejorados**:
  - **Modo 1 Mejorado (RECOMENDADO)**: Detección automática de nombre + captura continua de símbolos sin salir de cámara
  - **Modo 3 (MÁS RÁPIDO)**: Una sola foto de toda la hoja con detección automática completa
  - **Modo 2**: Cuadrícula con números y OCR (requiere Tesseract)
- **Detección Automática de Nombre**: Reconoce el nombre cuando confianza > 70%
- **Feedback Visual en Tiempo Real**: Muestra símbolos detectados, ítem actual y progreso
- **Reconocimiento Automático**: Utiliza OCR y reconocimiento de símbolos
- **Verificación Manual**: Permite verificar y corregir símbolos no reconocidos automáticamente
- **Cálculo de Calificaciones**: Escala configurable con calificaciones literales
- **Base de Datos**: Almacena histórico de exámenes
- **Exportación a Excel**: Exporta resultados para análisis posterior
- **Estadísticas**: Visualiza promedios, aprobados y suspensos

## Requisitos

### Software
- Python 3.8 o superior
- Tesseract OCR (OPCIONAL - solo para Modo 2)

### Instalación de Tesseract

**Windows:**
1. Descargar desde: https://github.com/UB-Mannheim/tesseract/wiki
2. Instalar en la ruta por defecto: `C:\Program Files\Tesseract-OCR`
3. Agregar al PATH del sistema

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

## Instalación

1. Clonar o descargar el repositorio

2. Instalar las dependencias de Python:
```bash
pip install -r requirements.txt
```

3. Verificar que Tesseract está instalado:
```bash
tesseract --version
```

## Uso

### 1. Iniciar la Aplicación

```bash
python main_app.py
```

### 2. Configurar una Plantilla de Examen

1. Hacer clic en "📋 Diseño de Pesos"
2. Introducir nombre de la plantilla y nota máxima (ej: 10)
3. Configurar los ítems del examen:
   - Número del ítem (automático)
   - Descripción (opcional)
   - Peso (puntos que vale cada ítem)
4. Verificar que el peso total coincida con la nota máxima
5. Guardar la plantilla (se guarda como archivo JSON)

**Ejemplo de plantilla:**
- Ítem 1: Peso 2.0
- Ítem 2: Peso 2.0
- Ítem 3: Peso 3.0
- Ítem 4: Peso 3.0
- **Total: 10.0 puntos**

### 3. Corregir un Examen

1. Hacer clic en "✏️ Corregir Examen"
2. Cargar una plantilla (si no hay ninguna cargada)
3. Seleccionar el modo de corrección:

   **Modo 1 - Símbolos Secuenciales:**
   - Introducir nombre del estudiante
   - Para cada ítem, mostrar el símbolo a la cámara:
     - ✓ (checkmark) = Correcto (100%)
     - X = Incorrecto (0%)
     - ~ (tilde) = Parcialmente correcto (50%)
   - Presionar Enter o Espacio para capturar
   - Presionar 'v' para verificar/corregir manualmente

   **Modo 2 - Cuadrícula:**
   - Introducir nombre del estudiante
   - Mostrar una hoja con cuadrícula numerada
   - Escribir números en las casillas que están correctas
   - Capturar la imagen completa
   - El sistema reconoce los números automáticamente

4. Verificar símbolos no reconocidos (si es necesario)
5. Revisar resultados
6. Guardar en la base de datos

#### Vinculación con `alumnos.csv` al guardar

Al guardar la corrección, el sistema intenta vincular el examen con un
alumno de `alumnos.csv` usando el nombre detectado por OCR. El
comportamiento depende del resultado del matching difuso:

- **Match alto** (confianza ≥ umbral, por defecto 95%): se vincula sin
  preguntar y el diálogo de guardado muestra `Alumno vinculado: …`.
- **Match dudoso** (confianza por debajo del umbral): aparece un cuadro
  Sí/No/Cancelar con el candidato sugerido.
  - **Sí** → usar ese alumno.
  - **No** → abrir el buscador manual (`ManualStudentPickerDialog`).
  - **Cancelar** → guardar sin vincular.
- **Sin candidato razonable**: se abre directamente el buscador manual,
  precargado con el nombre detectado.
- **Sin `alumnos.csv` cargado**: el examen queda sin vincular y el
  diálogo lo indica con `Sin BD de alumnos cargada`.

En todos los casos el examen se guarda; lo que cambia es si el campo
`student_id` queda relleno o `NULL`. Si quedó `NULL`, se puede arreglar
después desde el histórico (ver siguiente sección) o desde el CLI
`db_admin.py relink` (ver más abajo).

### 4. Ver Histórico

1. Hacer clic en "📊 Histórico".
2. La tabla muestra una columna **`Sid`** con el `student_id` vinculado
   (o `-` si el examen está huérfano).
3. Buscar por nombre de estudiante.
4. Ver estadísticas generales (totales, aprobados/suspensos, media).
5. Ver detalles de un examen específico ("Ver Detalles").
6. Exportar a Excel para análisis.

#### Re-vincular un alumno a posteriori (`Ctrl+R`)

Si un examen quedó mal vinculado (o sin vincular), no hace falta
borrarlo y volver a corregirlo:

1. Seleccionar la fila del examen en la tabla.
2. Pulsar el botón **"Re-vincular alumno (Ctrl+R)"** o el atajo
   **`Ctrl+R`**. Ambos abren el mismo buscador manual precargado con el
   nombre detectado por OCR.
3. Elegir un alumno y pulsar "Vincular" → la fila se actualiza al
   instante con el nuevo `Sid` (sin tener que reabrir el histórico) y
   aparece un mensaje `Re-vinculado: #ID → NOMBRE`.
4. Si en su lugar se pulsa "Cancelar" en el buscador *y* el examen ya
   estaba vinculado, el sistema pregunta `¿des-vincular?` — aceptar
   deja `student_id = NULL` y el `Sid` pasa a `-`.

Restricciones del atajo y del botón:

- Si `alumnos.csv` **no** está cargado al arrancar la app, el botón
  aparece deshabilitado y `Ctrl+R` queda inactivo (no se registra el
  binding para no engañar al usuario con una tecla que no hace nada).
- Si no hay ninguna fila seleccionada en la tabla, tanto el botón como
  `Ctrl+R` muestran el aviso `Selecciona un examen` en lugar de abrir
  el buscador.

Para re-vincular en lote sin GUI (varios exámenes a la vez), usar el
CLI `db_admin.py relink` documentado más abajo.

### 5. Configurar Escala de Calificación

1. Hacer clic en "⚙️ Configuración"
2. Configurar:
   - Nota sobre (ej: 10)
   - Nota mínima para aprobar (ej: 5)
   - Umbrales de calificación (en porcentaje):
     - Sobresaliente: 90%
     - Notable: 70%
     - Aprobado: 50%

## Mantenimiento de la BD desde la línea de comandos (`db_admin.py`)

Todas las operaciones administrativas habituales sobre `examenes.db` se
pueden hacer sin abrir la GUI con el script `db_admin.py`. Esto es útil
para tareas en lote, scripts de despliegue, o cuando se trabaja sobre la
BD desde un servidor sin pantalla.

```bash
python3 db_admin.py info                 # Resumen del estado de la BD
python3 db_admin.py migrate              # Aplica migraciones pendientes
python3 db_admin.py list --limit 20      # Últimos exámenes
python3 db_admin.py student --id 42      # Histórico del alumno 42
python3 db_admin.py export salida.xlsx   # Exporta notas a Excel
```

Por defecto opera sobre `examenes.db` en el directorio actual. Para
trabajar con otra BD: `python3 db_admin.py --db ruta/al/archivo.db ...`.

### Re-vincular exámenes con `alumnos.csv` (`relink`)

El subcomando `relink` asigna `student_id` a exámenes huérfanos
(`student_id IS NULL`) usando coincidencia difusa contra `alumnos.csv`.
También permite asignar IDs manualmente.

**Modo masivo** (todos los huérfanos a la vez, fuzzy match):

```bash
python3 db_admin.py relink --dry-run -v          # Previsualizar
python3 db_admin.py relink                       # Aplicar
python3 db_admin.py relink --min-confidence 90   # Umbral más estricto
```

**Modo dirigido por ID** (`--only-id`): permite tocar exámenes concretos
*incluso si ya tenían `student_id` asignado* — útil para corregir errores
puntuales sin reprocesar toda la BD.

```bash
# Un único examen, fuzzy match
python3 db_admin.py relink --only-id 7 --dry-run
python3 db_admin.py relink --only-id 7

# Forzar un student_id literal (sin fuzzy)
python3 db_admin.py relink --only-id 7 --manual-id 42

# Des-vincular (manual-id vacío)
python3 db_admin.py relink --only-id 7 --manual-id ""
```

**Multi-id** — `--only-id` y `--manual-id` son repetibles, lo que
permite re-vincular varios exámenes en una sola pasada:

```bash
# Procesar varios IDs con fuzzy match (uno por uno)
python3 db_admin.py relink --only-id 3 --only-id 7 --dry-run

# Broadcast: mismo student_id para todos los exámenes
python3 db_admin.py relink --only-id 3 --only-id 7 --manual-id 999

# Posicional: empareja 1-a-1 (orden importa)
python3 db_admin.py relink --only-id 3 --only-id 7 \
    --manual-id 100 --manual-id 200
```

Semántica de `--manual-id` cuando hay varios `--only-id`:

| `--only-id` | `--manual-id` | Comportamiento                          |
|-------------|---------------|-----------------------------------------|
| N           | 0             | Fuzzy match para todos                  |
| N           | 1             | Broadcast: mismo id forzado para todos  |
| N           | N             | Emparejamiento posicional (1-a-1)       |
| N           | otra cardin.  | Error `rc=6`, **no se persiste nada**   |

**Códigos de retorno de `relink`** (útiles en scripts):

- `0` — todo OK.
- `2` — no se pudo cargar `alumnos.csv` (ausente, vacío o inválido).
- `4` — un examen referenciado por `--only-id` no existe en la BD.
- `5` — fuzzy match sin candidato por encima de `--min-confidence`.
- `6` — cardinalidad inválida de `--manual-id` frente a `--only-id`.

Con varios `--only-id`, si alguno falla se devuelve **el primer rc
no-cero**; los demás IDs siguen procesándose. Así, `cmd && next` solo se
ejecuta cuando *todo* salió bien, mientras que `cmd || handler` captura
cualquier fallo parcial.

## Estructura del Proyecto

```
examenes/
├── main_app.py              # Aplicación principal y GUI
├── camera_handler.py        # Gestión de cámara web
├── correction_modes.py      # Modos de corrección (1 y 2)
├── symbol_recognizer.py     # Reconocimiento de símbolos
├── ocr_handler.py          # Procesamiento OCR con Tesseract
├── grade_calculator.py     # Cálculo de calificaciones
├── exam_database.py        # Base de datos SQLite
├── student_database.py     # Resolución de alumnos contra alumnos.csv
├── db_admin.py             # CLI de mantenimiento sin GUI (info/list/relink/export)
├── verification_ui.py      # Ventanas de verificación y resultados
├── alumnos.csv             # Base de datos de alumnos (Id, ALUMNO, …)
├── requirements.txt        # Dependencias
└── README.md              # Este archivo
```

## Archivos Generados

- `examenes.db` - Base de datos SQLite con histórico de exámenes
  (creada al primer guardado en el directorio desde el que se lanza la
  app). El CLI `db_admin.py` opera sobre el mismo fichero por defecto.
- `*.json` - Plantillas de examen guardadas
- `*.xlsx` - Exportaciones de resultados

## Solución de Problemas

### La cámara no funciona
- Verificar que la cámara está conectada
- Verificar permisos de la aplicación
- Probar cambiar el índice de cámara en `camera_handler.py` (0, 1, 2...)

### Tesseract no reconoce números
- Verificar que Tesseract está instalado correctamente
- En Windows, verificar la ruta en `ocr_handler.py`
- Asegurar buena iluminación al capturar
- Escribir números claros y grandes

### Símbolos no se reconocen bien
- Mejorar iluminación
- Acercar más el símbolo a la cámara
- Dibujar símbolos más grandes y claros
- Usar el modo de verificación manual ('v')

### Error al exportar a Excel
- Verificar que `openpyxl` está instalado: `pip install openpyxl`
- Verificar permisos de escritura en el directorio

## Flujo de Trabajo Recomendado

1. **Preparación**:
   - Crear plantilla de examen con pesos
   - Configurar escala de calificación
   - Verificar que la cámara funciona

2. **Corrección**:
   - Elegir modo según preferencia
   - Modo 1: Más lento pero más preciso
   - Modo 2: Más rápido para muchos ítems

3. **Revisión**:
   - Verificar símbolos dudosos
   - Confirmar resultados antes de guardar

4. **Análisis**:
   - Revisar estadísticas en Histórico
   - Exportar a Excel para análisis detallado

## Consejos para Mejores Resultados

### Modo 1 (Símbolos)
- Usar marcador grueso negro
- Fondo blanco o claro
- Buena iluminación uniforme
- Dibujar símbolos grandes (5-10 cm)
- Mantener símbolo centrado en la cámara

### Modo 2 (Cuadrícula)
- Imprimir cuadrícula con líneas claras
- Números grandes y bien formados (usar letra de imprenta)
- Evitar borrones o tachaduras
- Capturar la hoja completa, bien centrada
- Evitar sombras sobre el papel

## Personalización

### Agregar nuevos símbolos
Editar `symbol_recognizer.py` - método `_calculate_symbol_scores()`

### Cambiar escala por defecto
Editar `grade_calculator.py` - clase `GradeScale`

### Modificar dimensiones de cuadrícula
Al crear el corrector en `main_app.py`, ajustar `grid_rows` y `grid_cols`

## Licencia

Este proyecto es de código abierto para uso educativo.

## Soporte

Para reportar problemas o sugerencias, crear un issue en el repositorio del proyecto.
