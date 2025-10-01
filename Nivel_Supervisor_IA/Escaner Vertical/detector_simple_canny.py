"""
Detector SIMPLE basado en Canny
Parámetros encontrados que funcionan: low=20, high=172
Detecta la tapa del tubo (rectángulo vertical)
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
    if not camera_mgr.acquire("detector_simple"):
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
        camera_mgr.release("detector_simple")

def detectar_tubo_simple(imagen, canny_low=20, canny_high=172, debug=False):
    """
    Detector simple usando Canny + búsqueda de rectángulos verticales

    Parámetros que funcionaron:
    - canny_low: 20
    - canny_high: 172
    """

    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

    # Aplicar Canny con parámetros optimizados
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)

    if debug:
        print(f"Canny: low={canny_low}, high={canny_high}")
        print(f"Píxeles detectados: {np.count_nonzero(edges)}")

    # Cerrar gaps con morfología
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 7))
    edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_close)

    # Encontrar contornos
    contours, _ = cv2.findContours(edges_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if debug:
        print(f"Contornos encontrados: {len(contours)}")

    # Filtrar contornos buscando rectángulos VERTICALES (tapa del tubo)
    candidatos = []

    for cnt in contours:
        area = cv2.contourArea(cnt)

        # Filtrar por área mínima
        if area < 200:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / h if h > 0 else 0

        # Buscar rectángulos VERTICALES (h > w)
        # La TAPA del tubo es vertical
        if aspect_ratio < 0.8:  # Más alto que ancho

            # Calcular centro
            centro_y = y + h // 2
            centro_x = x + w // 2

            # Score según características
            score = 0

            # Bonus por ser vertical
            if aspect_ratio < 0.5:
                score += 30
            elif aspect_ratio < 0.7:
                score += 20
            else:
                score += 10

            # Bonus por tamaño apropiado para tapa
            if 15 < w < 80 and 30 < h < 150:
                score += 25

            # Bonus por estar centrado horizontalmente
            img_center_x = imagen.shape[1] // 2
            dist_x = abs(centro_x - img_center_x)
            if dist_x < imagen.shape[1] * 0.2:
                score += 20
            elif dist_x < imagen.shape[1] * 0.4:
                score += 10

            # Bonus por área razonable
            if 500 < area < 5000:
                score += 15

            candidatos.append({
                'bbox': (x, y, w, h),
                'centro_y': centro_y,
                'centro_x': centro_x,
                'area': area,
                'aspect': aspect_ratio,
                'score': score,
                'contorno': cnt
            })

    # Ordenar por score
    candidatos = sorted(candidatos, key=lambda c: c['score'], reverse=True)

    if debug and candidatos:
        print(f"\nCandidatos encontrados: {len(candidatos)}")
        for i, cand in enumerate(candidatos[:5]):
            print(f"  #{i+1}: score={cand['score']}, "
                  f"centro_y={cand['centro_y']}, "
                  f"aspect={cand['aspect']:.2f}, "
                  f"area={cand['area']:.0f}")

    # Visualización
    if debug:
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        # Original
        axes[0].imshow(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
        axes[0].set_title('Original')
        axes[0].axis('off')

        # Canny
        axes[1].imshow(edges, cmap='gray')
        axes[1].set_title(f'Canny (low={canny_low}, high={canny_high})')
        axes[1].axis('off')

        # Resultado con candidatos
        resultado = imagen.copy()
        for i, cand in enumerate(candidatos[:3]):
            x, y, w, h = cand['bbox']
            color = [(0, 255, 0), (0, 255, 255), (255, 0, 255)][i]
            cv2.rectangle(resultado, (x, y), (x+w, y+h), color, 2)
            cv2.putText(resultado, f"#{i+1}: {cand['score']}", (x, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.circle(resultado, (cand['centro_x'], cand['centro_y']), 5, (255, 0, 0), -1)

        axes[2].imshow(cv2.cvtColor(resultado, cv2.COLOR_BGR2RGB))
        axes[2].set_title(f'Detectados: {len(candidatos)} candidatos')
        axes[2].axis('off')

        plt.tight_layout()
        plt.show()

    # Retornar mejor candidato
    if candidatos:
        mejor = candidatos[0]
        return mejor['centro_y'], candidatos
    else:
        return None, []

def test_con_diferentes_parametros(imagen):
    """Prueba diferentes combinaciones de parámetros Canny"""

    # Parámetros a probar (cerca de los que funcionaron: 20, 172)
    configs = [
        (20, 172, "Óptimo encontrado"),
        (15, 172, "Low más bajo"),
        (20, 150, "High más bajo"),
        (20, 200, "High más alto"),
        (30, 172, "Low más alto"),
    ]

    resultados = []

    for low, high, descripcion in configs:
        print(f"\nProbando: {descripcion} (low={low}, high={high})")
        centro_y, candidatos = detectar_tubo_simple(imagen, low, high, debug=False)

        if centro_y is not None:
            print(f"  ✓ Detectado en Y={centro_y}, {len(candidatos)} candidatos")
            resultados.append((low, high, centro_y, len(candidatos), descripcion))
        else:
            print(f"  ✗ No detectado")

    # Mostrar comparación
    if resultados:
        print("\n" + "="*70)
        print("RESUMEN DE RESULTADOS:")
        print("="*70)
        for low, high, y, n_cand, desc in resultados:
            print(f"  {desc:20s} | low={low:3d} high={high:3d} | Y={y:3d} | {n_cand} candidatos")
        print("="*70)

if __name__ == "__main__":
    print("="*70)
    print("DETECTOR SIMPLE BASADO EN CANNY")
    print("="*70)

    imagen = capturar_imagen()

    if imagen is None:
        print("Error al capturar imagen")
        exit(1)

    print("\nOpciones:")
    print("  1. Detección con parámetros óptimos (low=20, high=172) + debug")
    print("  2. Probar diferentes parámetros")
    print()

    opcion = input("Selecciona opción (1/2) [1]: ").strip()

    if opcion == "2":
        test_con_diferentes_parametros(imagen)
    else:
        print("\nDetectando con parámetros óptimos...")
        centro_y, candidatos = detectar_tubo_simple(imagen, canny_low=20, canny_high=172, debug=True)

        if centro_y is not None:
            print(f"\n{'='*70}")
            print(f"✓ TUBO DETECTADO en Y = {centro_y} píxeles")
            print(f"{'='*70}")
        else:
            print(f"\n{'='*70}")
            print(f"✗ NO SE DETECTÓ EL TUBO")
            print(f"{'='*70}")
