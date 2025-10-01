"""
Test simple de filtros para detectar tubo de PVC blanco con tapa
Solo prueba y visualiza diferentes filtros - SIN detección compleja
"""
import cv2
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

def capturar_imagen():
    """Captura imagen usando el gestor de cámara"""
    camera_mgr = get_camera_manager()

    if not camera_mgr.acquire("test_filtros"):
        print("Error: No se pudo adquirir cámara")
        return None

    try:
        frame = camera_mgr.capture_frame(timeout=4.0, max_retries=3)
        if frame is None:
            print("Error: No se pudo capturar frame")
            return None

        # Rotar 90° como en el detector
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Recortar ROI
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)

        return frame_rotado[y1:y2, x1:x2]

    finally:
        camera_mgr.release("test_filtros")

def probar_filtros(image):
    """Prueba diferentes filtros para ver cuál funciona mejor"""

    if image is None:
        print("Error: imagen es None")
        return

    print(f"Imagen: {image.shape[1]}x{image.shape[0]}")

    # Preparar canales
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Diccionario de filtros
    filtros = {}

    # ============ FILTROS BÁSICOS ============

    # 1. Canny sobre escala de grises
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    filtros['1. Canny Suave'] = cv2.Canny(blurred, 30, 80)
    filtros['2. Canny Medio'] = cv2.Canny(blurred, 50, 120)
    filtros['3. Canny Fuerte'] = cv2.Canny(blurred, 80, 160)

    # 2. Top-hat (relieves)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel_h)
    filtros['4. Top-hat Horizontal'] = tophat
    filtros['5. Canny + Top-hat'] = cv2.Canny(tophat, 40, 100)

    # 3. Bottom-hat (sombras)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel_h)
    filtros['6. Black-hat Horizontal'] = blackhat

    # ============ FILTROS EN CANAL S ============

    # 4. Canal S directo
    filtros['7. Canal S Raw'] = s

    # 5. Canal S invertido (blancos → alto valor)
    s_inv = 255 - s
    filtros['8. Canal S Invertido'] = s_inv

    # 6. Umbral en S invertido
    _, s_thresh = cv2.threshold(s_inv, 160, 255, cv2.THRESH_BINARY)
    filtros['9. S Invertido Umbral 160'] = s_thresh

    # 7. Canny en Canal S
    s_blur = cv2.GaussianBlur(s, (5, 5), 0)
    filtros['10. Canny en Canal S'] = cv2.Canny(s_blur, 30, 80)

    # 8. Gradientes en S (Sobel)
    sobelx = cv2.Sobel(s, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(s, cv2.CV_64F, 0, 1, ksize=3)
    sobel_mag = np.sqrt(sobelx**2 + sobely**2)
    sobel_mag = np.clip(sobel_mag, 0, 255).astype(np.uint8)
    filtros['11. Sobel en Canal S'] = sobel_mag

    # ============ COMBINACIONES S+V ============

    # 9. Máscara: S bajo (< 40) + V alto (> 150)
    mask_s_bajo = (s < 40).astype(np.uint8) * 255
    mask_v_alto = (v > 150).astype(np.uint8) * 255
    filtros['12. S<40 (Baja Saturación)'] = mask_s_bajo
    filtros['13. V>150 (Alto Brillo)'] = mask_v_alto
    filtros['14. S<40 AND V>150'] = cv2.bitwise_and(mask_s_bajo, mask_v_alto)

    # 10. Diferencia V - S
    diff_vs = cv2.absdiff(v, s)
    filtros['15. Diferencia |V-S|'] = diff_vs

    # ============ OTROS ENFOQUES ============

    # 11. Laplaciano (detecta cambios bruscos)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian = np.absolute(laplacian)
    laplacian = np.clip(laplacian, 0, 255).astype(np.uint8)
    filtros['16. Laplaciano'] = laplacian

    # 12. Detección de líneas horizontales (kernel específico)
    kernel_horizontal = np.array([[-1, -1, -1],
                                   [ 2,  2,  2],
                                   [-1, -1, -1]], dtype=np.float32)
    horizontal_edges = cv2.filter2D(gray, -1, kernel_horizontal)
    horizontal_edges = np.clip(horizontal_edges, 0, 255).astype(np.uint8)
    filtros['17. Kernel Horizontal'] = horizontal_edges

    # 13. Adaptive threshold
    adapt_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 21, 2)
    filtros['18. Adaptive Threshold'] = adapt_thresh

    # ============ VISUALIZACIÓN ============

    n_filtros = len(filtros)
    cols = 4
    rows = (n_filtros + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(20, 5*rows))
    fig.suptitle('PRUEBA DE FILTROS - Detección Tubo PVC Blanco', fontsize=16, fontweight='bold')

    axes = axes.flatten() if rows > 1 else [axes] if cols == 1 else axes

    for i, (nombre, filtro) in enumerate(filtros.items()):
        axes[i].imshow(filtro, cmap='gray')
        axes[i].set_title(nombre, fontsize=10, fontweight='bold')
        axes[i].axis('off')

        # Mostrar estadísticas
        if filtro.dtype == np.uint8:
            mean_val = np.mean(filtro)
            nonzero = np.count_nonzero(filtro)
            total = filtro.shape[0] * filtro.shape[1]
            axes[i].text(5, 20, f'Media: {mean_val:.1f}\n{nonzero}/{total} px',
                        color='yellow', fontsize=8,
                        bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))

    # Ocultar ejes no usados
    for i in range(n_filtros, len(axes)):
        axes[i].axis('off')

    plt.tight_layout()
    plt.show()

    # Mostrar imagen original al final
    fig2, ax2 = plt.subplots(1, 1, figsize=(10, 8))
    ax2.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    ax2.set_title('IMAGEN ORIGINAL', fontsize=14, fontweight='bold')
    ax2.axis('off')
    plt.tight_layout()
    plt.show()

    print("\n" + "="*60)
    print("Filtros aplicados. Revisa las ventanas.")
    print("¿Cuáles muestran mejor el contorno del tubo/tapa?")
    print("="*60)

if __name__ == "__main__":
    print("="*60)
    print("TEST SIMPLE DE FILTROS - Tubo PVC Blanco")
    print("="*60)
    print("\nCapturando imagen...")

    imagen = capturar_imagen()

    if imagen is not None:
        print("Imagen capturada. Aplicando filtros...")
        probar_filtros(imagen)
    else:
        print("Error al capturar imagen")
