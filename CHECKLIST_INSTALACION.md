# ✅ Checklist de Instalación

Usa esta lista para verificar que tienes todo listo para usar el sistema.

## 📋 Pre-requisitos

### Software Básico
- [ ] Python 3.8 o superior instalado
  - Verifica con: `python --version`
  - Si no: Descarga de https://www.python.org/downloads/

- [ ] pip instalado (viene con Python)
  - Verifica con: `pip --version`

- [ ] Git instalado (opcional, para clonar)
  - Verifica con: `git --version`

### Hardware
- [ ] Webcam o cámara USB funcionando
- [ ] Buena iluminación en el área de trabajo
- [ ] Papel y marcador (negro, grueso)

## 🔧 Instalación

### Paso 1: Obtener el Proyecto
- [ ] Proyecto descargado/clonado en tu computadora
- [ ] Navega al directorio del proyecto en la terminal

### Paso 2: Dependencias de Python
- [ ] Ejecuta `install.bat` (Windows) o `pip install -r requirements.txt`
- [ ] Verifica que se instalaron sin errores:
  - [ ] opencv-python
  - [ ] numpy
  - [ ] Pillow
  - [ ] pytesseract
  - [ ] openpyxl

### Paso 2.5: Estructura de directorios y datos

La aplicación crea automáticamente lo que necesita, pero conviene saberlo
para no asustarse al ver carpetas nuevas tras el primer arranque:

- [ ] `models/` — se crea sola la primera vez que `TrainingScheduler`
  promueve un modelo entrenado. **No es necesario crearla a mano** ni
  versionarla; cada instalación entrena la suya. Si la borras, simplemente
  se volverá a crear (perderás los modelos entrenados).
- [ ] `examenes.db` — SQLite con histórico de exámenes y el `FeedbackStore`
  para el ML. Se crea/migra sola al arrancar `main_app.py`. Si vienes de
  una versión anterior, las migraciones de esquema (`student_id`,
  `exam_identifier`) se aplican de forma transparente.
- [ ] `alumnos.csv` — **necesario** para vincular cada examen corregido
  con el alumno real. Debe ir en la raíz del proyecto, separador `;` y
  con cabecera mínima `Id;ALUMNO;ACORTADO;DNI` (el sistema tolera más
  columnas). Si falta, los exámenes se guardarán sin `student_id` y el
  diálogo de guardado avisará explícitamente.

### Paso 3: Tesseract (Solo para Modo 2)

**Si solo usarás Modo 1 (símbolos), puedes omitir esto**

- [ ] Tesseract descargado desde https://github.com/UB-Mannheim/tesseract/wiki
- [ ] Tesseract instalado en `C:\Program Files\Tesseract-OCR` (Windows)
- [ ] Tesseract agregado al PATH del sistema
- [ ] Terminal reiniciada después de agregar al PATH
- [ ] Verifica con: `tesseract --version`

## 🧪 Verificación

### Prueba Básica
- [ ] Ejecuta `python main_app.py` o `run.bat`
- [ ] La aplicación se abre sin errores
- [ ] Ves el menú principal con 4 opciones

### Prueba de Cámara
- [ ] Click en "Corregir Examen"
- [ ] Aparece ventana de cámara
- [ ] Ves la imagen en vivo de la cámara
- [ ] La imagen es clara y sin lag

### Prueba de Plantilla
- [ ] Click en "Diseño de Pesos"
- [ ] Puedes crear una nueva plantilla
- [ ] Puedes cargar `plantilla_ejemplo.json`
- [ ] Los pesos se muestran correctamente

### Prueba de Corrección - Modo 1
- [ ] Carga una plantilla
- [ ] Inicia corrección en Modo 1
- [ ] Dibuja ✓ en papel
- [ ] La cámara lo captura
- [ ] Se reconoce el símbolo (o puedes verificarlo con 'v')
- [ ] Completas la corrección
- [ ] Se guarda en la base de datos

### Prueba de Corrección - Modo 2 (Opcional)
- [ ] Tesseract instalado y funcionando
- [ ] Inicia corrección en Modo 2
- [ ] Dibuja números en cuadrícula
- [ ] Captura la hoja
- [ ] Se reconocen los números
- [ ] Se guarda correctamente

### Prueba de Vinculación de Alumno (nuevo)
- [ ] Tras una corrección, al guardar:
  - Si el nombre detectado coincide claramente con un alumno → ves
    `Alumno vinculado: NOMBRE (ID …, confianza XX%)` en el diálogo.
  - Si la confianza es baja → aparece un diálogo Sí/No/Cancelar para
    aceptar el candidato sugerido, buscar otro a mano o guardar sin
    vincular.
  - Si no hay candidato → aparece el buscador manual de alumnos.
  - Si `alumnos.csv` no está cargado → el diálogo muestra explícitamente
    `Sin BD de alumnos cargada`.

### Prueba de Histórico
- [ ] Click en "Histórico"
- [ ] Ves exámenes guardados
- [ ] Puedes ver detalles de un examen
- [ ] Puedes buscar por nombre

### Prueba de Exportación
- [ ] En Histórico, click "Exportar a Excel"
- [ ] Se genera archivo .xlsx
- [ ] El archivo se abre en Excel/LibreOffice
- [ ] Los datos son correctos

## 🎯 Configuración Inicial Recomendada

### Escala de Calificación
- [ ] Click en "Configuración"
- [ ] Configura tu escala preferida:
  - [ ] Nota sobre: _____ (ej: 10)
  - [ ] Nota mínima aprobado: _____ (ej: 5)
  - [ ] Sobresaliente %: _____ (ej: 90)
  - [ ] Notable %: _____ (ej: 70)
  - [ ] Aprobado %: _____ (ej: 50)
- [ ] Guarda la configuración

### Primera Plantilla
- [ ] Click en "Diseño de Pesos"
- [ ] Crea tu primera plantilla real:
  - [ ] Nombre: _____
  - [ ] Nota sobre: _____
  - [ ] Ítems configurados
  - [ ] Peso total = Nota sobre
- [ ] Guarda la plantilla con nombre descriptivo

## 📱 Preparación del Área de Trabajo

### Para Modo 1 (Símbolos)
- [ ] Marcador negro grueso
- [ ] Hojas blancas o cartulina blanca
- [ ] Superficie plana
- [ ] Buena iluminación (natural o lámpara)
- [ ] Cámara a 30-50 cm de altura

### Para Modo 2 (Cuadrícula)
- [ ] Papel cuadriculado o imprime una cuadrícula
- [ ] Marcador negro
- [ ] Superficie sin sombras
- [ ] Cámara estable (trípode recomendado)
- [ ] Iluminación uniforme

## ❓ Solución de Problemas Comunes

### ❌ Error: "Python no se reconoce..."
**Solución**: Python no está en PATH
- [ ] Reinstala Python marcando "Add to PATH"
- [ ] O agrega manualmente al PATH del sistema

### ❌ Error: "No module named 'cv2'"
**Solución**: opencv-python no instalado
- [ ] Ejecuta: `pip install opencv-python`

### ❌ Error: "Camera not found"
**Solución**: Problema con la cámara
- [ ] Verifica que la cámara está conectada
- [ ] Cierra otras apps que usen la cámara (Zoom, Teams, etc.)
- [ ] Prueba cambiar el índice en `camera_handler.py`

### ❌ Error: "Tesseract not found"
**Solución**: Tesseract no instalado o no en PATH
- [ ] Instala Tesseract (ver CONFIGURAR_TESSERACT.md)
- [ ] Verifica PATH
- [ ] Reinicia terminal
- [ ] O usa Modo 1 (no necesita Tesseract)

### ❌ Los símbolos no se reconocen
**Solución**: Problemas de iluminación o contraste
- [ ] Mejora la iluminación
- [ ] Usa marcador más grueso
- [ ] Dibuja símbolos más grandes
- [ ] Acerca más a la cámara
- [ ] Usa verificación manual (tecla 'v')

## ✨ Todo Listo!

Si marcaste todos los checks relevantes, ¡estás listo para empezar!

### Primer Examen Real

1. [ ] Crea/carga plantilla para tu examen
2. [ ] Prepara área de trabajo
3. [ ] Inicia corrección (elige modo)
4. [ ] Corrige un examen de prueba
5. [ ] Verifica resultados
6. [ ] Ajusta configuración si es necesario

### Flujo de Trabajo Diario

```
1. Ejecutar: run.bat
2. Cargar plantilla (o usar la última)
3. Corregir exámenes uno por uno
4. Revisar estadísticas en Histórico
5. Exportar a Excel al final del día
```

---

**¿Problemas?**
- Consulta README.md para documentación completa
- Revisa INICIO_RAPIDO.md para guía rápida
- Revisa CONFIGURAR_TESSERACT.md si usas Modo 2

**¿Todo funciona?**
- ¡Excelente! Comienza a corregir exámenes 🎉
