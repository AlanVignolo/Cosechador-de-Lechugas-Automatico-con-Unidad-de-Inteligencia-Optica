"""
Exploración de técnicas alternativas de IA/ML para detectar tubos
- Template Matching mejorado
- Contour matching (Hu Moments)
- Hough Transform para líneas
- ML simple (opcional): Cascade Classifier, HOG, etc.
"""
import cv2
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

def capturar_imagen():
    """Captura imagen"""
    camera_mgr = get_camera_manager()
    if not camera_mgr.acquire("prueba_ia"):
        return None
    try:
        frame = camera_mgr.capture_frame(timeout=4.0, max_retries=3)
        if frame is None:
            return None
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)
        return frame_rotado[y1:y2, x1:x2]
    finally:
        camera_mgr.release("prueba_ia")

# ============================================================
# TÉCNICA 1: HOUGH TRANSFORM - Detectar líneas horizontales
# ============================================================
def detectar_lineas_hough(imagen):
    """Detecta líneas horizontales usando Hough Transform"""
    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # HoughLinesP: detecta segmentos de línea
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                            minLineLength=50, maxLineGap=10)

    resultado = imagen.copy()
    lineas_horizontales = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Filtrar solo líneas casi horizontales
            angulo = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            if angulo < 15:  # Menos de 15° → horizontal
                cv2.line(resultado, (x1, y1), (x2, y2), (0, 255, 0), 2)
                lineas_horizontales.append(((x1, y1), (x2, y2)))

    print(f"Hough: {len(lineas_horizontales)} líneas horizontales detectadas")
    return resultado, lineas_horizontales

# ============================================================
# TÉCNICA 2: TEMPLATE MATCHING - Buscar forma del tubo
# ============================================================
def template_matching(imagen):
    """Busca tubo usando templates de diferentes tamaños"""
    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    resultado = imagen.copy()

    # Crear template sintético del tubo (rectángulo horizontal con bordes)
    templates = []

    # Varios tamaños de templates
    for w in [80, 100, 120]:
        for h in [30, 40, 50]:
            template = np.ones((h, w), dtype=np.uint8) * 200
            # Bordes oscuros (simulando bordes del tubo)
            cv2.rectangle(template, (2, 2), (w-3, h-3), 50, 2)
            templates.append(template)

    mejores_matches = []

    for template in templates:
        # Matching
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.6
        loc = np.where(res >= threshold)

        h, w = template.shape

        for pt in zip(*loc[::-1]):
            mejores_matches.append((pt, w, h, res[pt[1], pt[0]]))

    # Eliminar duplicados (Non-Maximum Suppression simple)
    if mejores_matches:
        mejores_matches = sorted(mejores_matches, key=lambda x: x[3], reverse=True)
        mejor = mejores_matches[0]
        pt, w, h, score = mejor
        cv2.rectangle(resultado, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 2)
        cv2.putText(resultado, f"Score: {score:.2f}", (pt[0], pt[1]-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        print(f"Template Matching: Mejor match en {pt} con score {score:.2f}")
    else:
        print("Template Matching: No se encontraron matches")

    return resultado

# ============================================================
# TÉCNICA 3: ANÁLISIS DE CONTORNOS CON HU MOMENTS
# ============================================================
def analisis_contornos_hu(imagen):
    """Encuentra contornos y los compara con forma esperada del tubo"""
    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

    # Preprocesamiento
    s_inv = 255 - cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)[:,:,1]
    _, binary = cv2.threshold(s_inv, 160, 255, cv2.THRESH_BINARY)

    # Encontrar contornos
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    resultado = imagen.copy()

    # Filtrar contornos por área y aspecto
    candidatos = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 500:  # Muy pequeño
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / h if h > 0 else 0

        # Buscar rectángulos horizontales
        if aspect_ratio > 1.5 and area > 800:
            # Calcular Hu Moments (invariantes a escala/rotación)
            moments = cv2.moments(cnt)
            hu_moments = cv2.HuMoments(moments)

            candidatos.append({
                'contorno': cnt,
                'bbox': (x, y, w, h),
                'area': area,
                'aspect': aspect_ratio,
                'hu': hu_moments
            })

    # Ordenar por área (mayor = más probable)
    candidatos = sorted(candidatos, key=lambda c: c['area'], reverse=True)

    # Dibujar mejores candidatos
    for i, cand in enumerate(candidatos[:3]):  # Top 3
        x, y, w, h = cand['bbox']
        color = [(0, 255, 0), (0, 255, 255), (255, 0, 255)][i]
        cv2.rectangle(resultado, (x, y), (x+w, y+h), color, 2)
        cv2.putText(resultado, f"#{i+1} Area:{cand['area']:.0f}", (x, y-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    print(f"Contornos: {len(candidatos)} candidatos encontrados")
    return resultado

# ============================================================
# TÉCNICA 4: ANÁLISIS DE PROYECCIÓN HORIZONTAL
# ============================================================
def proyeccion_horizontal(imagen):
    """Analiza proyección horizontal para encontrar bandas del tubo"""
    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    s = hsv[:,:,1]

    # Usar canal S invertido
    s_inv = 255 - s

    # Proyección horizontal (suma por fila)
    proyeccion = np.sum(s_inv, axis=1).astype(np.float32)

    # Suavizar proyección con convolución 1D
    kernel_size = 15
    kernel = cv2.getGaussianKernel(kernel_size, 0)
    proyeccion_suave = np.convolve(proyeccion, kernel.ravel(), mode='same')

    # Encontrar picos (filas con alta intensidad)
    mean_proj = np.mean(proyeccion_suave)
    threshold = mean_proj * 1.2

    # Buscar regiones sobre threshold
    sobre_threshold = proyeccion_suave > threshold
    cambios = np.diff(sobre_threshold.astype(int))

    inicios = np.where(cambios == 1)[0]
    finales = np.where(cambios == -1)[0]

    resultado = imagen.copy()

    # Dibujar líneas horizontales en los bordes detectados
    for y in inicios:
        cv2.line(resultado, (0, y), (imagen.shape[1], y), (0, 255, 0), 2)
    for y in finales:
        cv2.line(resultado, (0, y), (imagen.shape[1], y), (0, 0, 255), 2)

    # Buscar par de líneas (superior e inferior del tubo)
    if len(inicios) > 0 and len(finales) > 0:
        # Tomar primer inicio y último final como candidatos
        y_top = inicios[0]
        y_bot = finales[-1] if len(finales) > 0 else inicios[0] + 50

        centro_y = (y_top + y_bot) // 2
        cv2.line(resultado, (0, centro_y), (imagen.shape[1], centro_y), (255, 0, 0), 3)
        cv2.putText(resultado, f"Centro Y: {centro_y}", (10, centro_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        print(f"Proyección: Centro detectado en Y={centro_y}")

    # Mostrar gráfico de proyección
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    ax1.imshow(cv2.cvtColor(resultado, cv2.COLOR_BGR2RGB))
    ax1.set_title('Detección por Proyección Horizontal')
    ax1.axis('off')

    ax2.plot(proyeccion_suave, range(len(proyeccion_suave)), 'b-', label='Proyección')
    ax2.axvline(threshold, color='r', linestyle='--', label='Threshold')
    ax2.set_xlabel('Suma de intensidad')
    ax2.set_ylabel('Fila (Y)')
    ax2.invert_yaxis()
    ax2.legend()
    ax2.grid(True)
    plt.tight_layout()
    plt.show()

    return resultado

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("="*70)
    print("PRUEBA DE TÉCNICAS ALTERNATIVAS DE IA/ML")
    print("="*70)

    imagen = capturar_imagen()

    if imagen is None:
        print("Error al capturar imagen")
        exit(1)

    print("\nAplicando diferentes técnicas...\n")

    # Aplicar técnicas
    img_hough, lineas = detectar_lineas_hough(imagen)
    img_template = template_matching(imagen)
    img_contornos = analisis_contornos_hu(imagen)
    img_proyeccion = proyeccion_horizontal(imagen)

    # Mostrar resultados
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('TÉCNICAS ALTERNATIVAS DE DETECCIÓN', fontsize=16, fontweight='bold')

    axes[0,0].imshow(cv2.cvtColor(img_hough, cv2.COLOR_BGR2RGB))
    axes[0,0].set_title('1. Hough Transform\n(Líneas horizontales)')
    axes[0,0].axis('off')

    axes[0,1].imshow(cv2.cvtColor(img_template, cv2.COLOR_BGR2RGB))
    axes[0,1].set_title('2. Template Matching\n(Búsqueda de forma)')
    axes[0,1].axis('off')

    axes[1,0].imshow(cv2.cvtColor(img_contornos, cv2.COLOR_BGR2RGB))
    axes[1,0].set_title('3. Análisis de Contornos\n(Hu Moments)')
    axes[1,0].axis('off')

    axes[1,1].imshow(cv2.cvtColor(img_proyeccion, cv2.COLOR_BGR2RGB))
    axes[1,1].set_title('4. Proyección Horizontal\n(Análisis de filas)')
    axes[1,1].axis('off')

    plt.tight_layout()
    plt.show()

    print("\n" + "="*70)
    print("¿Cuál técnica funciona mejor?")
    print("="*70)
