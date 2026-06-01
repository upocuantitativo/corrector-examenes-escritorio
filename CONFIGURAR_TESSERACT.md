# Configurar Tesseract OCR en Windows

Tesseract es necesario **solo para el Modo 2** (cuadrícula con números). Si solo usarás el Modo 1 (símbolos), puedes omitir esta instalación.

## Descarga e Instalación

### 1. Descargar Tesseract

Ve a: https://github.com/UB-Mannheim/tesseract/wiki

O descarga directamente:
https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe

### 2. Instalar

1. Ejecuta el instalador descargado
2. **IMPORTANTE**: Instala en la ruta por defecto:
   ```
   C:\Program Files\Tesseract-OCR
   ```
3. Durante la instalación, asegúrate de seleccionar:
   - ✅ Tesseract executable
   - ✅ English language data
   - ✅ Spanish language data (opcional, pero recomendado)

4. Completa la instalación

### 3. Agregar al PATH del Sistema

#### Opción A: Automática (durante instalación)
- El instalador puede ofrecer agregar Tesseract al PATH
- Si lo hace, acepta esta opción

#### Opción B: Manual
1. Abre el "Panel de Control"
2. Sistema y Seguridad > Sistema > Configuración avanzada del sistema
3. Click en "Variables de entorno"
4. En "Variables del sistema", busca "Path" y click en "Editar"
5. Click en "Nuevo"
6. Agrega la ruta: `C:\Program Files\Tesseract-OCR`
7. Click en "Aceptar" en todas las ventanas
8. **IMPORTANTE**: Cierra y vuelve a abrir cualquier terminal/CMD que tengas abierto

### 4. Verificar Instalación

Abre una terminal (CMD o PowerShell) y ejecuta:

```bash
tesseract --version
```

Deberías ver algo como:
```
tesseract v5.3.3.20231005
```

Si ves esto, ¡Tesseract está correctamente instalado! ✅

## Solución de Problemas

### Error: 'tesseract' no se reconoce como comando

**Causa**: Tesseract no está en el PATH o la terminal no se ha reiniciado.

**Solución**:
1. Verifica que Tesseract está instalado en: `C:\Program Files\Tesseract-OCR`
2. Verifica que agregaste la ruta al PATH (ver paso 3)
3. **Cierra y vuelve a abrir** la terminal
4. Intenta de nuevo

### Error en la aplicación: "Tesseract not found"

**Solución**:
1. Abre el archivo `ocr_handler.py`
2. Busca la línea que dice:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```
3. Verifica que la ruta sea correcta para tu instalación
4. Si instalaste en otra ubicación, actualiza la ruta

### La aplicación funciona pero no reconoce números

**Posibles causas**:
- Iluminación pobre
- Números muy pequeños
- Números mal escritos
- Cuadrícula borrosa

**Soluciones**:
- Usa buena iluminación (luz natural o lámpara brillante)
- Escribe números grandes (al menos 1-2 cm de altura)
- Usa marcador negro grueso
- Mantén la cámara estable al capturar
- Evita sombras sobre el papel

## Configuración Avanzada

### Cambiar la ruta de Tesseract en la aplicación

Si instalaste Tesseract en una ubicación diferente, edita `ocr_handler.py`:

```python
# Línea ~12-15
pytesseract.pytesseract.tesseract_cmd = r'TU_RUTA_AQUI\tesseract.exe'
```

Ejemplo:
```python
pytesseract.pytesseract.tesseract_cmd = r'D:\Apps\Tesseract\tesseract.exe'
```

## Alternativa: Usar solo Modo 1

Si tienes problemas con Tesseract o prefieres no instalarlo:

**Usa el Modo 1 (Símbolos)**
- No requiere Tesseract
- Funciona con reconocimiento de formas
- Igual de efectivo para corrección
- Más control visual

## Verificación Final

Para verificar que todo funciona:

1. Ejecuta la aplicación: `python main_app.py`
2. Crea/carga una plantilla
3. Inicia corrección en Modo 2
4. Dibuja números en papel: 1, 2, 3
5. Captura con la cámara
6. Verifica que se reconocen correctamente

Si funcionan, ¡todo está listo! ✅

---

**¿Necesitas ayuda?**
- Consulta el README.md principal
- Revisa los logs de error en la aplicación
- Prueba el Modo 1 como alternativa
