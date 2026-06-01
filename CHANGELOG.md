# Changelog - Sistema de Corrección de Exámenes

## [1.0.0] - 2024-10-21

### ✨ Características Iniciales

#### Diseño de Plantillas
- ✅ Configuración de plantillas de examen con pesos personalizados
- ✅ Soporte para número ilimitado de ítems
- ✅ Guardado y carga de plantillas en formato JSON
- ✅ Validación de peso total
- ✅ Interfaz intuitiva con scroll para muchos ítems

#### Modos de Corrección

**Modo 1 - Símbolos Secuenciales**
- ✅ Reconocimiento de símbolos: ✓ (correcto), X (incorrecto), ~ (parcial)
- ✅ Captura individual por ítem
- ✅ Retroalimentación visual en tiempo real
- ✅ Modo de verificación manual (tecla 'v')
- ✅ No requiere Tesseract OCR

**Modo 2 - Cuadrícula con Números**
- ✅ Captura de hoja completa con cuadrícula
- ✅ Reconocimiento OCR de números escritos a mano
- ✅ Configuración automática de dimensiones de cuadrícula
- ✅ Procesamiento de imagen para mejor reconocimiento
- ✅ Requiere Tesseract OCR

#### Sistema de Calificación
- ✅ Cálculo de puntuación bruta
- ✅ Escalado a nota final configurable (por defecto sobre 10)
- ✅ Calificaciones literales: Sobresaliente, Notable, Aprobado, Suspenso
- ✅ Porcentajes configurables para cada calificación
- ✅ Umbrales personalizables

#### Base de Datos
- ✅ Almacenamiento en SQLite
- ✅ Registro completo de cada corrección
- ✅ Guardado de detalles por ítem
- ✅ Timestamp de corrección
- ✅ Búsqueda por nombre de estudiante
- ✅ Estadísticas generales (promedio, aprobados, suspensos)

#### Interfaz de Usuario
- ✅ GUI moderna con Tkinter
- ✅ Ventana principal con menú de opciones
- ✅ Ventana de configuración de plantillas
- ✅ Ventana de verificación de símbolos
- ✅ Ventana de resultados con detalles
- ✅ Ventana de histórico con tabla
- ✅ Ventana de configuración de escala

#### Funcionalidades Adicionales
- ✅ Vista previa de cámara en tiempo real
- ✅ Verificación manual de símbolos no reconocidos
- ✅ Exportación a Excel (.xlsx)
- ✅ Visualización de detalles de examen
- ✅ Eliminación de exámenes del histórico
- ✅ Estadísticas en tiempo real

### 📦 Archivos Incluidos

- `main_app.py` - Aplicación principal y GUI
- `camera_handler.py` - Gestión de cámara web
- `correction_modes.py` - Lógica de modos de corrección
- `symbol_recognizer.py` - Reconocimiento de símbolos
- `ocr_handler.py` - Procesamiento OCR
- `grade_calculator.py` - Cálculo de calificaciones
- `exam_database.py` - Gestión de base de datos
- `verification_ui.py` - Ventanas de verificación y resultados
- `requirements.txt` - Dependencias de Python
- `README.md` - Documentación completa
- `INICIO_RAPIDO.md` - Guía de inicio rápido
- `CONFIGURAR_TESSERACT.md` - Guía de instalación de Tesseract
- `plantilla_ejemplo.json` - Plantilla de ejemplo
- `install.bat` - Script de instalación para Windows
- `run.bat` - Script de ejecución para Windows
- `.gitignore` - Configuración de Git

### 🛠️ Requisitos Técnicos

**Python**
- Python 3.8 o superior

**Dependencias**
- opencv-python >= 4.8.0 (gestión de cámara y procesamiento de imagen)
- numpy >= 1.24.0 (operaciones matemáticas)
- Pillow >= 10.0.0 (procesamiento de imágenes)
- pytesseract >= 0.3.10 (OCR, solo Modo 2)
- openpyxl >= 3.1.0 (exportación a Excel)

**Software Externo**
- Tesseract OCR (solo para Modo 2)

**Hardware**
- Webcam o cámara USB
- Resolución mínima recomendada: 640x480

### 📝 Notas de Uso

#### Mejores Prácticas
- Para Modo 1: usar marcador negro grueso sobre fondo blanco
- Para Modo 2: escribir números grandes y claros
- Asegurar buena iluminación al capturar
- Verificar símbolos dudosos antes de guardar

#### Limitaciones Conocidas
- El Modo 2 puede tener dificultad con caligrafía muy irregular
- El reconocimiento de símbolos depende de la calidad de la cámara
- La exportación a Excel requiere permisos de escritura

### 🔮 Funcionalidades Futuras (Posibles)

- [ ] Soporte para múltiples escalas de calificación por plantilla
- [ ] Importación masiva de exámenes
- [ ] Gráficos y estadísticas avanzadas
- [ ] Modo de corrección híbrido (símbolos + números)
- [ ] Detección automática de cuadrícula
- [ ] Reconocimiento de códigos QR para identificación de estudiantes
- [ ] Exportación a PDF con detalles
- [ ] API REST para integración con otros sistemas
- [ ] Soporte para corrección colaborativa
- [ ] Backup automático de base de datos

### 🐛 Correcciones

Ninguna - Primera versión

### 🔒 Seguridad

- Datos almacenados localmente en SQLite
- Sin conexión a internet requerida
- Sin recopilación de datos externos

---

**Versión actual**: 1.0.0
**Fecha de lanzamiento**: 21 de octubre de 2024
**Estado**: Estable ✅
