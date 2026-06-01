# 📚 Índice de Documentación

Bienvenido al Sistema de Corrección de Exámenes. Este índice te ayudará a encontrar la información que necesitas.

## 🚀 Inicio Rápido (Nuevos Usuarios)

¿Primera vez usando el sistema? Lee estos documentos en orden:

1. **[RESUMEN_ACTUALIZACION.md](RESUMEN_ACTUALIZACION.md)** ⭐ LÉEME PRIMERO
   - Nuevas características implementadas
   - Qué modos usar y cuándo
   - Diferencias entre Modo 1 Mejorado y Modo 3

2. **[INICIO_RAPIDO.md](INICIO_RAPIDO.md)** ⭐ COMIENZA AQUÍ
   - Instalación en 3 pasos
   - Tu primera corrección en 5 minutos
   - Ejemplos prácticos

3. **[GUIA_NUEVOS_MODOS.md](GUIA_NUEVOS_MODOS.md)** 🆕 TUTORIAL COMPLETO
   - Modo 1 Mejorado: Detección continua
   - Modo 3: Foto completa automática
   - Comparación y recomendaciones

4. **[CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)**
   - Verificar que todo está instalado
   - Checklist paso a paso
   - Solución de problemas comunes

5. **[CONFIGURAR_TESSERACT.md](CONFIGURAR_TESSERACT.md)** (OPCIONAL - solo Modo 2)
   - Instalación de Tesseract OCR
   - Configuración en Windows
   - Troubleshooting

## 📖 Documentación Completa

### Uso General

- **[README.md](README.md)** - Documentación completa del proyecto
  - Características del sistema
  - Requisitos detallados
  - Guía de uso paso a paso
  - Flujo de trabajo recomendado
  - Solución de problemas
  - Consejos para mejores resultados

### Referencia Técnica

- **[ESTRUCTURA_PROYECTO.md](ESTRUCTURA_PROYECTO.md)** - Arquitectura del código
  - Organización de archivos
  - Descripción de cada módulo
  - Flujo de datos
  - Estadísticas del proyecto
  - Información para desarrolladores

- **[CHANGELOG.md](CHANGELOG.md)** - Historial de versiones
  - Versión actual: 1.0.0
  - Características implementadas
  - Funcionalidades futuras planeadas

### Legal

- **[LICENSE.txt](LICENSE.txt)** - Licencia MIT
  - Términos de uso
  - Licencias de dependencias

## 🎯 Guías por Tarea

### Quiero instalar el sistema
→ [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)

### Quiero hacer mi primera corrección
→ [INICIO_RAPIDO.md](INICIO_RAPIDO.md) sección "Primera Corrección"

### Quiero configurar Tesseract para Modo 2
→ [CONFIGURAR_TESSERACT.md](CONFIGURAR_TESSERACT.md)

### Quiero crear una plantilla de examen
→ [README.md](README.md) sección "Configurar una Plantilla de Examen"

### Quiero exportar resultados a Excel
→ [README.md](README.md) sección "Ver Histórico"

### Quiero entender cómo funciona el código
→ [ESTRUCTURA_PROYECTO.md](ESTRUCTURA_PROYECTO.md)

### Tengo un problema o error
→ [README.md](README.md) sección "Solución de Problemas"
→ [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) sección "Solución de Problemas Comunes"

## 🔧 Archivos de Configuración

### Para Usuario
- `plantilla_ejemplo.json` - Plantilla de ejemplo (10 ítems x 1 punto)
- `requirements.txt` - Lista de dependencias Python
- `install.bat` - Script de instalación (Windows)
- `run.bat` - Script para ejecutar la aplicación (Windows)

### Para Desarrollador
- `.gitignore` - Archivos ignorados por Git
- Todos los archivos `.py` - Código fuente (ver ESTRUCTURA_PROYECTO.md)

## 📊 Referencia Rápida

### Modos de Corrección

| Modo | Descripción | Requiere Tesseract | Velocidad | Precisión |
|------|-------------|-------------------|-----------|-----------|
| **Modo 1** | Símbolos secuenciales (✓, X, ~) | No | Media | Alta |
| **Modo 2** | Cuadrícula con números | Sí | Rápida | Alta* |

*Depende de la calidad de escritura

### Símbolos Reconocidos (Modo 1)

- ✓ (Checkmark) = Correcto (100%)
- X (Equis) = Incorrecto (0%)
- ~ (Tilde) = Parcial (50%)

### Teclas de Atajo

- `ESPACIO` / `ENTER` - Capturar símbolo
- `v` - Modo verificación manual
- `ESC` - Cancelar/Salir

### Escala de Calificación por Defecto

- Sobresaliente: ≥ 90%
- Notable: ≥ 70%
- Aprobado: ≥ 50%
- Suspenso: < 50%

(Configurable desde "⚙️ Configuración")

## 🗂️ Organización de Archivos del Proyecto

```
examenes/
│
├── 📘 Documentación (8 archivos)
│   ├── INDICE.md                     ← Estás aquí
│   ├── README.md                     ← Documentación principal
│   ├── INICIO_RAPIDO.md              ← Guía de 5 minutos
│   ├── CHECKLIST_INSTALACION.md      ← Lista de verificación
│   ├── CONFIGURAR_TESSERACT.md       ← Instalación de Tesseract
│   ├── ESTRUCTURA_PROYECTO.md        ← Arquitectura técnica
│   ├── CHANGELOG.md                  ← Historial de versiones
│   └── LICENSE.txt                   ← Licencia
│
├── 🐍 Código Fuente (8 archivos .py)
│   ├── main_app.py
│   ├── camera_handler.py
│   ├── correction_modes.py
│   ├── symbol_recognizer.py
│   ├── ocr_handler.py
│   ├── grade_calculator.py
│   ├── exam_database.py
│   └── verification_ui.py
│
├── ⚙️ Configuración (4 archivos)
│   ├── requirements.txt
│   ├── plantilla_ejemplo.json
│   ├── install.bat
│   └── run.bat
│
└── 💾 Total: 20 archivos

```

## 🎓 Recursos de Aprendizaje

### Para Usuarios Finales (Profesores, Correctores)
1. Lee [INICIO_RAPIDO.md](INICIO_RAPIDO.md)
2. Prueba con la plantilla de ejemplo
3. Consulta [README.md](README.md) para detalles

### Para Desarrolladores
1. Lee [ESTRUCTURA_PROYECTO.md](ESTRUCTURA_PROYECTO.md)
2. Examina el código fuente (empieza por `main_app.py`)
3. Consulta [CHANGELOG.md](CHANGELOG.md) para roadmap

### Para Administradores de Sistemas
1. Revisa [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)
2. Consulta `requirements.txt` para dependencias
3. Lee [CONFIGURAR_TESSERACT.md](CONFIGURAR_TESSERACT.md) si despliegan Modo 2

## 🆘 Soporte

### Problemas Comunes
Consulta la sección "Solución de Problemas" en:
- [README.md](README.md)
- [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)
- [CONFIGURAR_TESSERACT.md](CONFIGURAR_TESSERACT.md)

### Preguntas Frecuentes

**P: ¿Necesito Tesseract?**
R: Solo para Modo 2. Modo 1 funciona sin Tesseract.

**P: ¿Qué modo es mejor?**
R: Modo 1 es más confiable para empezar. Modo 2 es más rápido una vez configurado.

**P: ¿Puedo personalizar la escala de calificación?**
R: Sí, desde "⚙️ Configuración" en la aplicación.

**P: ¿Cómo exporto los resultados?**
R: Histórico > Exportar a Excel

**P: ¿Dónde se guardan los datos?**
R: En `exams.db` (SQLite) en el mismo directorio.

## 📞 Contacto y Contribuciones

- **Issues**: Reporta problemas en el repositorio del proyecto
- **Contribuciones**: Fork el proyecto y crea un Pull Request
- **Documentación**: Mejoras bienvenidas vía PR

## 🔄 Actualizaciones

Para estar al día con nuevas versiones:
1. Consulta [CHANGELOG.md](CHANGELOG.md)
2. Revisa el repositorio del proyecto

---

## 🚀 Empezar Ahora

**Nuevo usuario**: [INICIO_RAPIDO.md](INICIO_RAPIDO.md)

**Ya instalado**: Ejecuta `run.bat` o `python main_app.py`

---

*Última actualización: 21 de octubre de 2024*
*Versión: 1.0.0*
