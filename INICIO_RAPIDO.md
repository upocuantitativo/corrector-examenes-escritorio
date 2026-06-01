# Inicio Rápido - Sistema de Corrección de Exámenes

## Instalación en 3 Pasos

### 1️⃣ Instalar
```bash
# Windows: Haz doble clic en install.bat
# O desde terminal:
pip install -r requirements.txt
```

### 2️⃣ Ejecutar
```bash
# Windows: Haz doble clic en run.bat
# O desde terminal:
python main_app.py
```

### 3️⃣ Usar
1. **Crear Plantilla**: Click en "📋 Diseño de Pesos"
   - Nombre: "Mi Examen"
   - Nota sobre: 10
   - Configurar pesos (total debe sumar 10)
   - Guardar

2. **Corregir**: Click en "✏️ Corregir Examen"
   - Cargar plantilla
   - Elegir modo (1 o 2)
   - Seguir instrucciones en pantalla

3. **Ver Resultados**: Click en "📊 Histórico"

## Modos de Corrección

### 🎯 Modo 1: Símbolos (Recomendado para empezar)
- Dibuja símbolos grandes en papel:
  - ✓ = Correcto
  - X = Incorrecto
  - ~ = Medio
- Muestra cada símbolo a la cámara
- Presiona ESPACIO para capturar

### 📊 Modo 2: Cuadrícula (Requiere Tesseract)
- Dibuja cuadrícula en papel
- Escribe números de preguntas correctas
- Captura toda la hoja de una vez

## Requisitos Mínimos

✅ Python 3.8+
✅ Webcam
✅ Papel y marcador
⚠️ Tesseract OCR (solo para Modo 2)

## Ayuda Rápida

**Problema**: No funciona la cámara
**Solución**: Verifica permisos, prueba otra cámara

**Problema**: No reconoce símbolos
**Solución**: Más luz, símbolos más grandes, presiona 'v' para verificar manual

**Problema**: Error con Tesseract
**Solución**: Instala Tesseract o usa Modo 1 (no lo necesita)

## Plantilla de Ejemplo

Se incluye `plantilla_ejemplo.json` con 10 ítems de 1 punto cada uno.

Cárgala desde "Diseño de Pesos" > "Cargar Plantilla"

## Primera Corrección (Modo 1)

1. Ejecuta la aplicación
2. "Diseño de Pesos" > "Cargar Plantilla" > `plantilla_ejemplo.json`
3. "Corregir Examen" > Modo 1
4. Nombre: "Estudiante Prueba"
5. Dibuja ✓ en papel, muéstralo a cámara, presiona ESPACIO
6. Repite para los 10 ítems
7. Revisa resultados y guarda

¡Listo! Tu primer examen corregido.

## Exportar Resultados

"📊 Histórico" > "Exportar a Excel"

Genera archivo .xlsx con todos los exámenes.

---

📖 Para más detalles, consulta README.md
