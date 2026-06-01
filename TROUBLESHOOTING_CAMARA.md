# 🔧 Troubleshooting - Cámara No Se Ve

Si la cámara no se muestra al usar los modos de corrección, sigue estos pasos:

---

## 📋 Paso 1: Verificación Básica

### Test Simple de Cámara

Ejecuta el script de prueba básico:

```bash
python test_camera.py
```

**¿Qué debería pasar?**
- ✅ Ventana se abre mostrando video en tiempo real
- ✅ Contador de frames incrementando
- ✅ Puedes cerrar con ESC

**Si funciona**: La cámara está bien, el problema es de integración.
**Si NO funciona**: Problema con OpenCV o cámara del sistema.

---

## 📋 Paso 2: Test del Modo 1

Ejecuta el test específico del Modo 1:

```bash
python test_mode1_camera.py
```

**¿Qué debería pasar?**
- ✅ Ventana con overlay simulando Modo 1
- ✅ Video en tiempo real con texto superpuesto
- ✅ Contador de frames

**Si funciona**: El problema está en `correction_modes_improved.py`
**Si NO funciona**: Problema con la integración de OpenCV.

---

## 🔍 Diagnóstico de Problemas

### Problema 1: Ventana se abre pero está negra/congelada

**Causas posibles**:
- Otra aplicación está usando la cámara
- Permisos de cámara no otorgados
- Índice de cámara incorrecto

**Soluciones**:

1. **Cerrar otras aplicaciones** que usen la cámara:
   - Zoom, Teams, Skype
   - Otros programas de video

2. **Verificar permisos** (Windows 10/11):
   ```
   Configuración → Privacidad → Cámara
   → Permitir que las aplicaciones accedan a tu cámara
   ```

3. **Probar otro índice de cámara**:
   Edita `main_app.py` línea ~532:
   ```python
   # Cambia esto:
   self.camera = CameraHandler(camera_index=0)

   # Por esto:
   self.camera = CameraHandler(camera_index=1)
   ```

### Problema 2: La ventana no aparece para nada

**Causas posibles**:
- Backend de GUI de OpenCV no configurado
- OpenCV instalado sin soporte de GUI
- Problema con sistema de ventanas

**Soluciones**:

1. **Verificar instalación de OpenCV**:
   ```bash
   pip uninstall opencv-python
   pip install opencv-python
   ```

2. **En Windows**, instalar Visual C++ Redistributable:
   - Descargar de: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Ejecutar instalador

3. **Verificar backend**:
   ```python
   import cv2
   print(cv2.getBuildInformation())
   ```
   Buscar: `GUI: YES` o `Qt: YES` o `GTK: YES`

### Problema 3: Ventana aparece por un instante y desaparece

**Causa**: `cv2.waitKey()` no se llama correctamente o bucle se rompe.

**Solución**:
- Ya corregido en la última versión con más prints de debug
- Verifica la consola para mensajes de error

### Problema 4: En Modo 1/2 la ventana se ve, pero en Modo 3 no

**Causa**: Modo 3 captura una sola foto, ventana se cierra rápido.

**Esto es normal**. Modo 3 está diseñado así.

---

## 🛠️ Soluciones Específicas por Sistema

### Windows 10/11

1. **Antivirus bloqueando cámara**:
   ```
   Windows Security → Virus & threat protection
   → Manage settings → Allow apps to access camera
   ```

2. **Permisos de aplicación**:
   ```
   Settings → Privacy → Camera → Allow desktop apps
   ```

3. **Drivers de cámara**:
   - Actualizar drivers en Device Manager
   - Buscar "Camera" y actualizar

### Linux

1. **Permisos de dispositivo**:
   ```bash
   sudo usermod -a -G video $USER
   ```
   Luego cerrar sesión y volver a entrar.

2. **Verificar dispositivo**:
   ```bash
   ls -l /dev/video*
   ```

### macOS

1. **Permisos de privacidad**:
   ```
   System Preferences → Security & Privacy
   → Privacy → Camera → Marcar Terminal/Python
   ```

---

## 🔧 Configuraciones Avanzadas

### Aumentar Tiempo de waitKey

Si la ventana parpadea, edita `correction_modes_improved.py`:

```python
# Busca líneas con waitKey(1)
# Cámbialas a:
key = cv2.waitKey(30) & 0xFF  # 30ms en lugar de 1ms
```

### Forzar Backend Específico

Antes de importar cv2, configura:

```python
import os
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"  # Windows
# o
os.environ["OPENCV_VIDEOIO_PRIORITY_V4L2"] = "0"  # Linux
```

### Debug Avanzado

Agrega prints para ver qué pasa:

```python
while True:
    ret, frame = self.camera.capture_frame()
    print(f"Frame capturado: ret={ret}, shape={frame.shape if frame is not None else None}")

    cv2.imshow(window_name, frame)
    print("imshow llamado")

    key = cv2.waitKey(1)
    print(f"waitKey retornó: {key}")
```

---

## ✅ Checklist de Verificación

Antes de reportar un bug, verifica:

- [ ] `test_camera.py` funciona
- [ ] `test_mode1_camera.py` funciona
- [ ] Otra aplicación NO está usando la cámara
- [ ] Permisos de cámara otorgados
- [ ] OpenCV instalado correctamente
- [ ] La ventana de OpenCV tiene el foco (click en ella)
- [ ] Presionando teclas EN la ventana de OpenCV, no en consola

---

## 🚨 Si Nada Funciona

### Opción 1: Usar versión sin vista previa

Comenta las líneas de `cv2.imshow` y usa solo captura:

```python
# cv2.imshow(window_name, frame)  # Comentar
print(f"Frame {frame_count} capturado")
```

### Opción 2: Guardar frames a disco

En lugar de mostrar, guarda:

```python
cv2.imwrite(f"frame_{frame_count}.jpg", frame)
print(f"Frame guardado: frame_{frame_count}.jpg")
```

### Opción 3: Usar modo alternativo

- Si Modo 1 no funciona → Usa Modo 3
- Si Modo 3 no funciona → Usa Modo 1
- Modo 2 funciona igual que Modo 1

---

## 📞 Información para Reportar Bug

Si ninguna solución funciona, reporta incluyendo:

1. **Sistema operativo**: Windows/Linux/macOS + versión
2. **Versión de Python**: `python --version`
3. **Versión de OpenCV**: `pip show opencv-python`
4. **Resultado de test_camera.py**: ¿Funciona? ¿Error?
5. **Resultado de test_mode1_camera.py**: ¿Funciona? ¿Error?
6. **Mensajes de error** en consola (copia completa)
7. **Captura de pantalla** si es posible

---

## 💡 Workaround Temporal

Si la cámara no se ve PERO sí captura:

1. Abre otra aplicación de cámara (Windows Camera, VLC, etc.)
2. Deja esa ventana abierta en segundo plano
3. Ejecuta el sistema de corrección
4. Usa la otra ventana para ver lo que captura la cámara
5. Presiona ESPACIO en la ventana del sistema para capturar

No es ideal pero permite usar el sistema mientras se resuelve.

---

**Última actualización**: 21 de octubre de 2024
