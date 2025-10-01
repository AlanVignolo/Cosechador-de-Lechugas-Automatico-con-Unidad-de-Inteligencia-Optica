"""
Ajuste de filtros en VIVO con trackbars de OpenCV
Permite probar diferentes filtros y ajustar parámetros en tiempo real
"""
import cv2
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

# Variables globales
imagen_global = None
filtro_actual = 0

def capturar_imagen():
    """Captura imagen usando el gestor de cámara"""
    camera_mgr = get_camera_manager()

    if not camera_mgr.acquire("ajuste_filtros"):
        print("Error: No se pudo adquirir cámara")
        return None

    try:
        frame = camera_mgr.capture_frame(timeout=4.0, max_retries=3)
        if frame is None:
            return None

        # Rotar 90°
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Recortar ROI
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)

        return frame_rotado[y1:y2, x1:x2]

    finally:
        camera_mgr.release("ajuste_filtros")

def nada(x):
    """Callback vacío para trackbars"""
    pass

def aplicar_filtro_canny(gray, low, high):
    """Canny con parámetros ajustables"""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.Canny(blurred, low, high)

def aplicar_filtro_canny_tophat(gray, low, high, kernel_size):
    """Canny + Top-hat con parámetros ajustables"""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, max(3, kernel_size//3)))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    return cv2.Canny(tophat, low, high)

def aplicar_filtro_s_umbral(s, threshold):
    """Umbral en canal S invertido"""
    s_inv = 255 - s
    _, result = cv2.threshold(s_inv, threshold, 255, cv2.THRESH_BINARY)
    return result

def aplicar_filtro_s_canny(s, low, high):
    """Canny en canal S"""
    s_blur = cv2.GaussianBlur(s, (5, 5), 0)
    return cv2.Canny(s_blur, low, high)

def aplicar_filtro_combinado_sv(s, v, s_max, v_min):
    """S bajo + V alto"""
    mask_s = (s < s_max).astype(np.uint8) * 255
    mask_v = (v > v_min).astype(np.uint8) * 255
    return cv2.bitwise_and(mask_s, mask_v)

def modo_interactivo(imagen):
    """Modo interactivo con trackbars para ajustar filtros"""
    global filtro_actual

    # Preparar canales
    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Crear ventanas
    cv2.namedWindow('Original', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Filtro', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Controles', cv2.WINDOW_NORMAL)

    # Mostrar original
    cv2.imshow('Original', imagen)

    # Trackbars para seleccionar filtro
    cv2.createTrackbar('Filtro', 'Controles', 0, 5, nada)
    cv2.setTrackbarPos('Filtro', 'Controles', 0)

    # Trackbars para Canny
    cv2.createTrackbar('Canny Low', 'Controles', 30, 200, nada)
    cv2.createTrackbar('Canny High', 'Controles', 80, 300, nada)

    # Trackbars para morfología
    cv2.createTrackbar('Kernel Size', 'Controles', 15, 50, nada)

    # Trackbars para canal S
    cv2.createTrackbar('S Threshold', 'Controles', 160, 255, nada)
    cv2.createTrackbar('S Max', 'Controles', 40, 255, nada)
    cv2.createTrackbar('V Min', 'Controles', 150, 255, nada)

    print("\n" + "="*70)
    print("MODO INTERACTIVO - Ajuste de Filtros")
    print("="*70)
    print("\nFiltros disponibles (usa trackbar 'Filtro'):")
    print("  0 - Canny Simple")
    print("  1 - Canny + Top-hat")
    print("  2 - Umbral en Canal S")
    print("  3 - Canny en Canal S")
    print("  4 - Combinado S+V")
    print("  5 - Canal S Raw")
    print("\nPresiona 'q' para salir")
    print("="*70)

    while True:
        # Leer valores de trackbars
        filtro_seleccionado = cv2.getTrackbarPos('Filtro', 'Controles')
        canny_low = cv2.getTrackbarPos('Canny Low', 'Controles')
        canny_high = cv2.getTrackbarPos('Canny High', 'Controles')
        kernel_size = max(3, cv2.getTrackbarPos('Kernel Size', 'Controles'))
        s_threshold = cv2.getTrackbarPos('S Threshold', 'Controles')
        s_max = cv2.getTrackbarPos('S Max', 'Controles')
        v_min = cv2.getTrackbarPos('V Min', 'Controles')

        # Aplicar filtro según selección
        if filtro_seleccionado == 0:
            titulo = f"Canny Simple (low={canny_low}, high={canny_high})"
            resultado = aplicar_filtro_canny(gray, canny_low, canny_high)

        elif filtro_seleccionado == 1:
            titulo = f"Canny + Top-hat (low={canny_low}, high={canny_high}, kernel={kernel_size})"
            resultado = aplicar_filtro_canny_tophat(gray, canny_low, canny_high, kernel_size)

        elif filtro_seleccionado == 2:
            titulo = f"Umbral Canal S (threshold={s_threshold})"
            resultado = aplicar_filtro_s_umbral(s, s_threshold)

        elif filtro_seleccionado == 3:
            titulo = f"Canny en Canal S (low={canny_low}, high={canny_high})"
            resultado = aplicar_filtro_s_canny(s, canny_low, canny_high)

        elif filtro_seleccionado == 4:
            titulo = f"S+V Combinado (S<{s_max}, V>{v_min})"
            resultado = aplicar_filtro_combinado_sv(s, v, s_max, v_min)

        else:  # 5
            titulo = "Canal S Raw"
            resultado = s

        # Agregar título a la imagen
        img_con_titulo = resultado.copy()
        if len(img_con_titulo.shape) == 2:
            img_con_titulo = cv2.cvtColor(img_con_titulo, cv2.COLOR_GRAY2BGR)

        cv2.putText(img_con_titulo, titulo, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Mostrar resultado
        cv2.imshow('Filtro', img_con_titulo)

        # Esperar tecla
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    print("="*70)
    print("AJUSTE DE FILTROS EN VIVO")
    print("="*70)
    print("\nCapturando imagen...")

    imagen = capturar_imagen()

    if imagen is not None:
        print("Imagen capturada. Iniciando modo interactivo...")
        modo_interactivo(imagen)
    else:
        print("Error al capturar imagen")
