import cv2
import time

# Inicializar la cámara (0 para la cámara predeterminada)
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)  # Usa el backend Video4Linux2

# Verificar si la cámara está abierta
if not camera.isOpened():
    print("Error: No se pudo acceder a la cámara.")
    exit()

# Ajustar parámetros de la cámara
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # Ancho de la imagen
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)  # Alto de la imagen
camera.set(cv2.CAP_PROP_BRIGHTNESS, 0.5)  # Brillo (0.0 a 1.0)
camera.set(cv2.CAP_PROP_CONTRAST, 0.5)  # Contraste (0.0 a 1.0)
camera.set(cv2.CAP_PROP_EXPOSURE, -1)  # Exposición automática (-1) o manual (mayor a 0)

print("Calentando la cámara...")
# Realizar algunas capturas previas para permitir que la cámara se ajuste
for _ in range(30):  # Capturar 30 frames para ajuste
    ret, frame = camera.read()
    time.sleep(0.1)  # Pequeña pausa entre capturas

print("Capturando imagen final en:")
for i in range(3, 0, -1):
    print(f"{i}...")
    time.sleep(1)

# Capturar la imagen final
ret, frame = camera.read()
if ret:
    cv2.imwrite("foto_prueba.jpg", frame)
    print("Imagen capturada y guardada como 'foto_prueba.jpg'.")
else:
    print("Error: No se pudo capturar la imagen.")

# Liberar la cámara
camera.release()