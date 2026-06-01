"""
Test simple del Modo 1 para verificar que la cámara se ve
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import cv2
import sys
from camera_handler import CameraHandler

print("=== TEST MODO 1 - VISUALIZACIÓN DE CÁMARA ===\n")

# Inicializar cámara
camera = CameraHandler(camera_index=0)

print("Iniciando cámara...")
if not camera.start():
    print("❌ ERROR: No se pudo iniciar la cámara")
    sys.exit(1)

print("✅ Cámara iniciada\n")

# Crear ventana
window_name = "Test Modo 1 - Cámara"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 800, 600)

print("Mostrando cámara...")
print("Presiona ESPACIO para capturar")
print("Presiona ESC para salir\n")

frame_count = 0

while True:
    # Capturar frame
    ret, frame = camera.capture_frame()

    if not ret or frame is None:
        print(f"❌ Error al capturar frame")
        break

    frame_count += 1

    # Dibujar overlay (simulando lo que hace Modo 1)
    display_frame = frame.copy()

    # Panel superior
    height, width = frame.shape[:2]
    cv2.rectangle(display_frame, (0, 0), (width, 150), (0, 0, 0), -1)

    cv2.putText(display_frame, "TEST MODO 1 - DETECCION CONTINUA",
               (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

    cv2.putText(display_frame, f"Frame: {frame_count}",
               (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    cv2.putText(display_frame, "ESPACIO: Capturar | ESC: Salir",
               (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 200, 255), 2)

    # Mezclar
    result = cv2.addWeighted(frame, 0.7, display_frame, 0.3, 0)

    # IMPORTANTE: Mostrar la ventana
    cv2.imshow(window_name, result)

    # IMPORTANTE: waitKey para procesar eventos de ventana
    key = cv2.waitKey(30) & 0xFF

    if key == ord(' '):  # ESPACIO
        print(f"✅ Frame {frame_count} capturado!")

    elif key == 27:  # ESC
        print(f"\n✅ Test finalizado. {frame_count} frames procesados")
        break

# Limpiar
camera.stop()
cv2.destroyAllWindows()

print("✅ Test completado exitosamente")
print("\nSi viste la cámara, el problema NO está en camera_handler.py")
print("Si NO viste la cámara, el problema es de configuración de OpenCV/sistema")
