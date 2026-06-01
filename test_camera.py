"""
Script de prueba para verificar que la cámara funciona
"""
import console_utf8  # noqa: F401  (consola UTF-8 en Windows)
import cv2

print("=== TEST DE CÁMARA ===")
print("Intentando abrir la cámara...")

# Intentar abrir cámara
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ ERROR: No se pudo abrir la cámara")
    print("Probando índice 1...")
    cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        print("❌ ERROR: Tampoco funciona con índice 1")
        exit(1)

print("✅ Cámara abierta correctamente")

# Configurar ventana
cv2.namedWindow("Test Cámara", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Test Cámara", 800, 600)

print("\nMostrando cámara...")
print("Presiona ESC para salir")

frame_count = 0

while True:
    ret, frame = cap.read()

    if not ret:
        print(f"❌ Error al capturar frame {frame_count}")
        break

    frame_count += 1

    # Dibujar info en frame
    cv2.putText(frame, f"Frame: {frame_count}", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame, "Presiona ESC para salir", (10, 70),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Mostrar
    cv2.imshow("Test Cámara", frame)

    # Esperar tecla
    key = cv2.waitKey(1) & 0xFF

    if key == 27:  # ESC
        print(f"\n✅ Test completado. {frame_count} frames capturados")
        break

# Limpiar
cap.release()
cv2.destroyAllWindows()

print("✅ Test finalizado exitosamente")
