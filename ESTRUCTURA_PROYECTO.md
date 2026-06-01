# Estructura del Proyecto

## 📁 Organización de Archivos

```
examenes/
│
├── 📘 DOCUMENTACIÓN
│   ├── README.md                      # Documentación completa del proyecto
│   ├── INICIO_RAPIDO.md              # Guía de inicio rápido (5 minutos)
│   ├── CONFIGURAR_TESSERACT.md       # Guía de instalación de Tesseract
│   ├── CHANGELOG.md                  # Historial de versiones
│   ├── ESTRUCTURA_PROYECTO.md        # Este archivo
│   └── LICENSE.txt                    # Licencia MIT
│
├── 🐍 CÓDIGO FUENTE (2,687 líneas)
│   ├── main_app.py                   # Aplicación principal y GUI (629 líneas)
│   ├── camera_handler.py             # Gestión de cámara web (168 líneas)
│   ├── correction_modes.py           # Modos de corrección 1 y 2 (416 líneas)
│   ├── symbol_recognizer.py          # Reconocimiento de símbolos (234 líneas)
│   ├── ocr_handler.py               # OCR con Tesseract (245 líneas)
│   ├── grade_calculator.py          # Cálculo de notas (253 líneas)
│   ├── exam_database.py             # Base de datos SQLite (355 líneas)
│   └── verification_ui.py           # Ventanas de verificación (387 líneas)
│
├── ⚙️ CONFIGURACIÓN
│   ├── requirements.txt              # Dependencias de Python
│   ├── plantilla_ejemplo.json        # Plantilla de examen de ejemplo
│   └── .gitignore                    # Archivos ignorados por Git
│
├── 🪟 SCRIPTS WINDOWS
│   ├── install.bat                   # Instalador automático
│   └── run.bat                       # Ejecutor de la aplicación
│
└── 💾 ARCHIVOS GENERADOS (en tiempo de ejecución)
    ├── exams.db                      # Base de datos SQLite
    └── *.xlsx                        # Exportaciones Excel

```

## 🔧 Módulos Principales

### 1. `main_app.py` - Aplicación Principal
**Responsabilidad**: Interfaz gráfica y orquestación

**Clases**:
- `MainApplication`: Ventana principal y menú
- `TemplateConfigWindow`: Configuración de plantillas
- `HistoryWindow`: Visualización de histórico

**Funcionalidades**:
- Menú principal con 4 opciones
- Gestión de plantillas de examen
- Inicialización de proceso de corrección
- Configuración de escala de calificación
- Visualización de estadísticas

### 2. `camera_handler.py` - Gestión de Cámara
**Responsabilidad**: Captura y procesamiento de video

**Clase**:
- `CameraHandler`: Manejo de webcam con OpenCV

**Funcionalidades**:
- Inicialización de cámara
- Captura de frames en tiempo real
- Vista previa en ventana
- Control de liberación de recursos

### 3. `correction_modes.py` - Lógica de Corrección
**Responsabilidad**: Implementación de modos de corrección

**Clases**:
- `ExamItem`: Modelo de ítem de examen
- `ExamCorrection`: Modelo de corrección completa
- `Mode1Corrector`: Corrección con símbolos secuenciales
- `Mode2Corrector`: Corrección con cuadrícula

**Funcionalidades**:
- Captura de nombre de estudiante
- Procesamiento de símbolos/números
- Detección de necesidad de verificación
- Construcción de objeto de corrección

### 4. `symbol_recognizer.py` - Reconocimiento de Símbolos
**Responsabilidad**: Análisis de formas y símbolos

**Clase**:
- `SymbolRecognizer`: Reconocimiento de ✓, X, ~

**Funcionalidades**:
- Preprocesamiento de imagen
- Detección de contornos
- Clasificación de símbolos
- Cálculo de confianza

**Algoritmo**:
- Conversión a escala de grises
- Umbralización adaptativa
- Análisis de forma y área
- Scoring por características

### 5. `ocr_handler.py` - OCR con Tesseract
**Responsabilidad**: Reconocimiento de texto/números

**Clase**:
- `OCRHandler`: Procesamiento OCR

**Funcionalidades**:
- Detección de cuadrícula
- Extracción de números
- Procesamiento de imagen
- Validación de resultados

**Técnicas**:
- Detección de bordes (Canny)
- Detección de líneas (HoughLines)
- Segmentación de celdas
- OCR con Tesseract

### 6. `grade_calculator.py` - Cálculo de Calificaciones
**Responsabilidad**: Transformación de puntuación a calificación

**Clases**:
- `GradeScale`: Escala de calificación configurable
- `ExamTemplate`: Plantilla de examen con pesos
- `GradeCalculator`: Calculadora de notas finales

**Funcionalidades**:
- Cálculo de puntuación bruta
- Escalado a nota final
- Asignación de calificación literal
- Guardado/carga de plantillas JSON

**Escalas**:
- Sobresaliente: >= 90%
- Notable: >= 70%
- Aprobado: >= 50%
- Suspenso: < 50%

### 7. `exam_database.py` - Base de Datos
**Responsabilidad**: Persistencia de datos

**Clase**:
- `ExamDatabase`: Gestión de SQLite

**Funcionalidades**:
- Creación de tablas
- Guardado de correcciones
- Búsqueda y filtrado
- Cálculo de estadísticas
- Exportación a Excel

**Esquema**:
- Tabla `exams`: Datos generales
- Tabla `exam_items`: Detalles por ítem

### 8. `verification_ui.py` - Interfaces de Verificación
**Responsabilidad**: Ventanas de verificación y resultados

**Clases**:
- `VerificationWindow`: Verificación de símbolos no reconocidos
- `ResultsWindow`: Visualización de resultados finales

**Funcionalidades**:
- Selección manual de símbolos
- Vista previa de imagen capturada
- Desglose de puntuación por ítem
- Confirmación antes de guardar

## 📊 Flujo de Datos

```
1. Usuario crea/carga plantilla
   └─> ExamTemplate (grade_calculator.py)

2. Usuario inicia corrección
   └─> MainApplication._start_correction_process()

3. Captura con cámara
   └─> CameraHandler.capture_frame()

4. Procesamiento según modo:

   Modo 1:
   └─> SymbolRecognizer.recognize_symbol()
       └─> ExamItem con símbolo detectado

   Modo 2:
   └─> OCRHandler.extract_grid_numbers()
       └─> Lista de ítems correctos

5. Verificación (si necesario)
   └─> VerificationWindow
       └─> Usuario corrige símbolos

6. Cálculo de calificación
   └─> GradeCalculator.calculate_final_grade()
       └─> Puntuación escalada + calificación literal

7. Visualización de resultados
   └─> ResultsWindow

8. Guardado en BD
   └─> ExamDatabase.save_correction()
       └─> exams.db actualizada
```

## 🔌 Dependencias Externas

### Python (pip)
```
opencv-python   → Captura de cámara, procesamiento de imagen
numpy          → Operaciones matemáticas, arrays
Pillow         → Conversión de formatos de imagen
pytesseract    → Interfaz Python para Tesseract
openpyxl       → Exportación a Excel
```

### Sistema
```
Tesseract OCR  → Motor OCR (solo Modo 2)
Webcam         → Captura de imágenes
```

## 📈 Estadísticas del Proyecto

- **Total líneas de código**: ~2,687
- **Archivos Python**: 8
- **Archivos de documentación**: 6
- **Clases principales**: 15+
- **Funciones/métodos**: 100+

## 🎯 Puntos de Entrada

### Para Usuario
```bash
# Windows
install.bat      # Primer uso
run.bat          # Uso diario

# Multiplataforma
python main_app.py
```

### Para Desarrollador
```python
# Importar módulos
from correction_modes import Mode1Corrector, Mode2Corrector
from grade_calculator import GradeCalculator, ExamTemplate
from exam_database import ExamDatabase

# Usar programáticamente
template = ExamTemplate.load("mi_plantilla.json")
database = ExamDatabase()
# ... etc
```

## 🧪 Testing

Actualmente no hay tests unitarios. Áreas sugeridas para testing:

- `SymbolRecognizer._calculate_symbol_scores()`
- `GradeCalculator.calculate_final_grade()`
- `ExamTemplate.add_item()` (validaciones)
- `ExamDatabase.save_correction()` (integridad)
- `OCRHandler.extract_grid_numbers()` (casos edge)

## 🔐 Seguridad y Privacidad

- ✅ Sin conexión a internet requerida
- ✅ Datos almacenados localmente
- ✅ Sin telemetría o tracking
- ✅ Base de datos sin encriptación (mejora futura)

## 🚀 Extensibilidad

### Agregar nuevo modo de corrección
1. Crear clase en `correction_modes.py`
2. Heredar de clase base o implementar interface similar
3. Agregar opción en `main_app.py._open_correction()`

### Agregar nuevo símbolo
1. Editar `SymbolRecognizer._calculate_symbol_scores()`
2. Agregar lógica de detección
3. Actualizar documentación

### Cambiar escala de calificación
1. Editar `GradeScale` en `grade_calculator.py`
2. O configurar desde GUI en tiempo de ejecución

---

**Última actualización**: 21 de octubre de 2024
**Versión**: 1.0.0
