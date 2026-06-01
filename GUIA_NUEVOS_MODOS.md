# Guía de Nuevos Modos de Corrección

El sistema ahora incluye **3 modos de corrección mejorados** para mayor flexibilidad y eficiencia.

---

## 🎯 Modo 1 Mejorado: Detección Continua (RECOMENDADO)

### Características
- ✅ **Detección automática de nombre** (confianza > 70%)
- ✅ **Sin salir de cámara** entre capturas
- ✅ **Feedback visual en tiempo real**
- ✅ **Muestra símbolos detectados** en pantalla
- ✅ **Indica el ítem actual** que se está corrigiendo

### Cómo Usar

#### 1. Preparación
- Escribe el nombre del estudiante en una hoja
- Prepara símbolos grandes (✓, X, ~) en papel blanco

#### 2. Detección de Nombre
1. Muestra el nombre a la cámara
2. El sistema detecta automáticamente cuando confianza > 70%
3. Verás una barra de progreso de confianza
4. Cuando está listo, se confirma automáticamente (1 segundo)

**NO necesitas presionar nada** - se detecta solo cuando está seguro

#### 3. Corrección de Ítems
Para cada ítem del examen:

1. **Muestra el símbolo** correspondiente a la cámara:
   - ✓ = Correcto (100% del peso)
   - X = Incorrecto (0%)
   - ~ = Parcialmente correcto (50%)

2. **Presiona ESPACIO** para capturar

3. El sistema:
   - Reconoce el símbolo
   - Muestra feedback grande en pantalla (0.5 seg)
   - Agrega a la lista de "Capturados"
   - Avanza al siguiente ítem

4. **Repite** para todos los ítems

#### 4. Pantalla durante corrección

```
┌─────────────────────────────────────────┐
│ Estudiante: Juan Pérez                  │
│ Item 3/10: Pregunta 3                   │
│ Peso: 1.0 puntos                        │
│ ESPACIO: Capturar | ESC: Cancelar       │
├─────────────────────────────────────────┤
│                                         │
│  [Video de la cámara]                   │
│                                         │
│  Capturados:                            │
│  1. ✓                                   │
│  2. X                                   │
│                                         │
└─────────────────────────────────────────┘
```

### Ventajas
- Control total del profesor
- Ver cada símbolo antes de confirmar
- Feedback inmediato
- No requiere Tesseract

### Ideal Para
- Exámenes pequeños/medianos (hasta 20 ítems)
- Cuando quieres verificar cada símbolo
- Primera vez usando el sistema

---

## 🚀 Modo 3: Foto Completa Automática (MÁS RÁPIDO)

### Características
- ✅ **UNA sola foto** de toda la hoja
- ✅ **Detección 100% automática**
- ✅ Detecta nombre + todos los símbolos
- ✅ Organización: izquierda→derecha, arriba→abajo
- ✅ **Ideal para corrección masiva**

### Cómo Usar

#### 1. Preparación de la Hoja

**Formato requerido:**
```
┌─────────────────────────────┐
│  NOMBRE: Juan Pérez         │  ← Arriba
├─────────────────────────────┤
│                             │
│   ✓    X    ✓    ~         │  ← Símbolos
│                             │
│   ✓    ✓    X    ✓         │     Organizados
│                             │     en cuadrícula
│   ~    ✓    ✓    X         │
│                             │
└─────────────────────────────┘
```

**Requisitos:**
- Nombre del estudiante en el **tercio superior**
- Símbolos (✓, X, ~) en el resto
- Organizados de **izquierda a derecha**
- Luego de **arriba hacia abajo**
- Símbolos grandes y claros
- Fondo blanco

#### 2. Captura

1. **Posiciona la hoja** completa frente a la cámara
2. Verás un marco de guía verde
3. **Presiona ESPACIO** para capturar
4. El sistema procesa automáticamente

#### 3. Procesamiento Automático

El sistema:
1. Detecta el **nombre** (parte superior)
2. Encuentra todos los **símbolos** (parte inferior)
3. Los ordena correctamente
4. Asigna a cada ítem del examen
5. Muestra overlay con resultados (2 segundos)

#### 4. Verificación

Después verás un resumen con:
- Nombre detectado y confianza
- Cada símbolo detectado
- Confianza de cada detección
- Puntuación calculada

### Ventajas
- **Muy rápido**: 1 foto vs 10+ capturas
- Menos interacción
- Ideal para muchos exámenes
- Menos errores de orden

### Ideal Para
- Exámenes grandes (10+ ítems)
- Corrección masiva (muchos estudiantes)
- Cuando tienes buena iluminación
- Plantilla estandarizada

### Tips para Mejores Resultados

✅ **Iluminación**
- Luz uniforme sin sombras
- Preferir luz natural o lámpara LED

✅ **Símbolos**
- Marcador negro grueso
- Tamaño: al menos 2-3 cm
- Bien formados y claros

✅ **Organización**
- Mantén espaciado uniforme
- Evita que símbolos se toquen
- Cuadrícula visible ayuda

✅ **Cámara**
- Mantén perpendicular a la hoja
- Distancia: hoja completa visible
- Evita reflejos

---

## 📊 Modo 2: Cuadrícula con Números (Original)

Este modo sigue disponible para quien prefiera usar números en lugar de símbolos.

### Características
- Cuadrícula numerada
- Escribes números de respuestas correctas
- Usa OCR (requiere Tesseract)

### Cuándo Usar
- Prefieres escribir números
- Tienes Tesseract configurado
- Plantilla de cuadrícula ya preparada

---

## 🔄 Comparación de Modos

| Característica | Modo 1 Mejorado | Modo 3 Foto Completa | Modo 2 Cuadrícula |
|----------------|-----------------|---------------------|-------------------|
| **Velocidad** | Media | Muy rápida | Media |
| **Control** | Alto | Medio | Alto |
| **Facilidad** | Fácil | Muy fácil | Media |
| **Requiere Tesseract** | No | No | Sí |
| **Interacción** | Alta | Baja | Media |
| **Precisión** | Muy alta | Alta* | Alta* |
| **Capturas** | 1 por ítem | 1 total | 1 total |

*Depende de calidad de escritura/iluminación

---

## 💡 Recomendaciones por Escenario

### 📝 Pocos Exámenes (1-5)
→ **Modo 1 Mejorado**
- Mayor control
- Verificas cada símbolo
- Más flexible

### 📚 Muchos Exámenes (10+)
→ **Modo 3 Foto Completa**
- Mucho más rápido
- Menos fatiga
- Estandarizado

### 🎓 Primeros Usos
→ **Modo 1 Mejorado**
- Más intuitivo
- Ves el proceso paso a paso
- Aprendes cómo funciona

### ⚡ Producción Masiva
→ **Modo 3 Foto Completa**
- Optimizado para volumen
- Workflow eficiente
- Menos clicks

---

## 🎬 Flujo de Trabajo Recomendado

### Para Modo 1 Mejorado

```
1. Preparar símbolos en papel
2. Iniciar corrección → Modo 1
3. Mostrar nombre (espera detección automática)
4. Para cada ítem:
   - Mostrar símbolo
   - ESPACIO
   - Ver feedback
5. Revisar resumen
6. Guardar
```

### Para Modo 3 Foto Completa

```
1. Preparar hoja completa:
   - Nombre arriba
   - Símbolos organizados abajo
2. Iniciar corrección → Modo 3
3. Posicionar hoja
4. ESPACIO
5. Revisar detección (2 seg)
6. Verificar y guardar
```

---

## ❓ FAQ

**P: ¿Puedo cambiar de modo entre exámenes?**
R: Sí, cada vez que corriges puedes elegir el modo.

**P: ¿Los resultados son iguales entre modos?**
R: Sí, todos calculan igual. Solo cambia el método de captura.

**P: ¿Qué modo es más preciso?**
R: Modo 1 permite más control, pero Modo 3 es muy preciso con buena preparación.

**P: ¿Necesito Tesseract para los nuevos modos?**
R: NO. Solo Modo 2 requiere Tesseract. Modos 1 y 3 funcionan sin él.

**P: ¿Puedo mezclar símbolos en Modo 3?**
R: Sí, puedes usar ✓, X y ~ en la misma hoja.

**P: ¿Qué pasa si la detección falla?**
R: Siempre hay una pantalla de verificación donde puedes corregir manualmente.

---

## 🛠️ Troubleshooting

### Modo 1: Nombre no se detecta
- Escribe más grande
- Letra de imprenta clara
- Mejor iluminación
- Acerca más a la cámara

### Modo 1: Símbolo no reconocido
- Dibuja más grande
- Marcador más grueso
- Más contraste con fondo
- Usa verificación manual ('v')

### Modo 3: Símbolos desordenados
- Verifica orden: izq→der, arriba→abajo
- Espaciado más uniforme
- Evita símbolos muy juntos
- Mantén cuadrícula visible

### Modo 3: No detecta todos los símbolos
- Mejora iluminación
- Símbolos más grandes
- Más contraste
- Verifica que todos estén en la foto

---

## ✅ Checklist de Éxito

### Antes de Empezar
- [ ] Buena iluminación
- [ ] Cámara funcionando
- [ ] Plantilla cargada
- [ ] Papel y marcador listos

### Modo 1
- [ ] Nombre en hoja separada
- [ ] Símbolos grandes (5+ cm)
- [ ] Fondo blanco/claro
- [ ] Marcador negro grueso

### Modo 3
- [ ] Hoja con formato correcto
- [ ] Nombre arriba
- [ ] Símbolos organizados
- [ ] Todo visible en cámara

---

**¡Listo para empezar!** Prueba ambos modos y elige el que mejor se adapte a tu flujo de trabajo.
