"""
Detector de Tubo Vertical - Detecta líneas superior e inferior de la tapa

Estrategia:
1. Canny (20, 172) + Canal S para detectar bordes de la tapa ignorando fondo blanco
2. Encontrar contorno de la tapa (rectángulo vertical)
3. Extraer LÍNEAS SUPERIOR E INFERIOR del rectángulo (lo importante)
4. Retornar coordenadas Y de ambas líneas
"""
import cv2
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

def capturar_imagen():
    """Captura imagen de la cámara"""
    camera_mgr = get_camera_manager()
    if not camera_mgr.acquire("detector_tubo_vertical"):
        return None
    try:
        frame = camera_mgr.capture_frame(timeout=4.0, max_retries=3)
        if frame is None:
            return None

        # Rotar 90°
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Recortar ROI
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.25)
        x2 = int(ancho * 0.75)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)

        return frame_rotado[y1:y2, x1:x2]
    finally:
        camera_mgr.release("detector_tubo_vertical")

def detectar_lineas_tubo(imagen, debug=False):
    """
    Detecta las líneas superior e inferior de la tapa del tubo

    Returns:
        tuple: (y_superior, y_inferior, centro_y, info) o (None, None, None, None)
    """

    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # ==== PASO 1: Canny para detectar bordes ====
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges_canny = cv2.Canny(blurred, 20, 172)

    # ==== PASO 2: Máscara en Canal S (baja saturación) ====
    s_inv = 255 - s
    _, mask_s_low = cv2.threshold(s_inv, 150, 255, cv2.THRESH_BINARY)

    # ==== PASO 3: Combinar Canny + Canal S ====
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges_dilated = cv2.dilate(edges_canny, kernel_dilate, iterations=1)
    edges_filtrados = cv2.bitwise_and(edges_dilated, mask_s_low)

    # ==== PASO 4: Morfología para cerrar gaps ====
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9))
    edges_final = cv2.morphologyEx(edges_filtrados, cv2.MORPH_CLOSE, kernel_close)

    # ==== PASO 5: Encontrar contornos ====
    contours, _ = cv2.findContours(edges_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidatos = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 250:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / h if h > 0 else 0

        # Buscar rectángulos VERTICALES (tapa)
        if aspect_ratio < 0.9:

            # Analizar saturación en ROI
            roi_s = s[y:y+h, x:x+w]
            mean_s = np.mean(roi_s)
            std_s = np.std(roi_s)

            score = 0

            # Scoring por forma vertical
            if aspect_ratio < 0.5:
                score += 35
            elif aspect_ratio < 0.7:
                score += 25
            else:
                score += 15

            # Scoring por tamaño
            if 15 < w < 80 and 30 < h < 150:
                score += 25

            # Scoring por saturación baja y uniforme
            if mean_s < 35:
                score += 30
                if std_s < 15:
                    score += 20

            # Scoring por estar centrado horizontalmente
            centro_x = x + w // 2
            img_center_x = imagen.shape[1] // 2
            dist_x = abs(centro_x - img_center_x)
            if dist_x < imagen.shape[1] * 0.25:
                score += 20

            # Scoring por área
            if 600 < area < 6000:
                score += 15

            # NUEVO: Extraer líneas superior e inferior
            y_superior = y
            y_inferior = y + h
            centro_y = y + h // 2

            candidatos.append({
                'bbox': (x, y, w, h),
                'y_superior': y_superior,
                'y_inferior': y_inferior,
                'centro_y': centro_y,
                'centro_x': centro_x,
                'area': area,
                'aspect': aspect_ratio,
                'score': score,
                'mean_s': mean_s,
                'std_s': std_s
            })

    # Ordenar por score
    candidatos = sorted(candidatos, key=lambda c: c['score'], reverse=True)

    # Visualización
    if debug:
        print(f"\n{'='*70}")
        print("DETECTOR DE LÍNEAS DEL TUBO")
        print(f"{'='*70}")
        print(f"Candidatos encontrados: {len(candidatos)}")

        if candidatos:
            mejor = candidatos[0]
            print(f"\nMejor candidato:")
            print(f"  Score: {mejor['score']}")
            print(f"  Línea Superior (Y): {mejor['y_superior']}")
            print(f"  Línea Inferior (Y): {mejor['y_inferior']}")
            print(f"  Centro (Y): {mejor['centro_y']}")
            print(f"  Altura: {mejor['y_inferior'] - mejor['y_superior']} px")
            print(f"  Saturación media: {mejor['mean_s']:.1f}")

        # Crear visualización
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('DETECTOR DE LÍNEAS DEL TUBO', fontsize=16, fontweight='bold')

        # Fila 1: Proceso
        axes[0,0].imshow(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
        axes[0,0].set_title('Original')
        axes[0,0].axis('off')

        axes[0,1].imshow(s, cmap='gray')
        axes[0,1].set_title(f'Canal S\nMedia: {np.mean(s):.1f}')
        axes[0,1].axis('off')

        axes[0,2].imshow(mask_s_low, cmap='gray')
        axes[0,2].set_title('Máscara S Bajo')
        axes[0,2].axis('off')

        # Fila 2: Detección
        axes[1,0].imshow(edges_canny, cmap='gray')
        axes[1,0].set_title('Canny (20, 172)')
        axes[1,0].axis('off')

        axes[1,1].imshow(edges_final, cmap='gray')
        axes[1,1].set_title('Bordes Filtrados')
        axes[1,1].axis('off')

        # Resultado: Mostrar LÍNEAS detectadas
        resultado = imagen.copy()

        for i, cand in enumerate(candidatos[:3]):
            x, y, w, h = cand['bbox']
            y_sup = cand['y_superior']
            y_inf = cand['y_inferior']
            centro_y = cand['centro_y']

            if i == 0:  # Mejor candidato
                # Línea superior (ROJA)
                cv2.line(resultado, (0, y_sup), (imagen.shape[1], y_sup), (0, 0, 255), 3)
                cv2.putText(resultado, f"Y_SUP = {y_sup}", (10, y_sup - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Línea inferior (VERDE)
                cv2.line(resultado, (0, y_inf), (imagen.shape[1], y_inf), (0, 255, 0), 3)
                cv2.putText(resultado, f"Y_INF = {y_inf}", (10, y_inf + 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # Línea centro (AZUL)
                cv2.line(resultado, (0, centro_y), (imagen.shape[1], centro_y), (255, 0, 0), 2)
                cv2.putText(resultado, f"CENTRO = {centro_y}", (10, centro_y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

                # Rectángulo del contorno (amarillo pálido)
                cv2.rectangle(resultado, (x, y), (x+w, y+h), (0, 255, 255), 1)

            else:  # Otros candidatos
                color = [(100, 100, 100), (150, 150, 150)][i-1]
                cv2.rectangle(resultado, (x, y), (x+w, y+h), color, 1)

        axes[1,2].imshow(cv2.cvtColor(resultado, cv2.COLOR_BGR2RGB))
        axes[1,2].set_title(f'LÍNEAS DETECTADAS\n{len(candidatos)} candidatos')
        axes[1,2].axis('off')

        plt.tight_layout()
        plt.show()

    # Retornar mejor candidato si tiene score suficiente
    if candidatos and candidatos[0]['score'] > 50:
        mejor = candidatos[0]
        return (mejor['y_superior'],
                mejor['y_inferior'],
                mejor['centro_y'],
                mejor)
    else:
        return None, None, None, None

def detectar_posicion_tubo(imagen=None, debug=False):
    """
    Función principal para detectar posición del tubo
    Compatible con la interfaz anterior (retorna solo centro_y)
    """
    if imagen is None:
        imagen = capturar_imagen()
        if imagen is None:
            return None

    y_sup, y_inf, centro_y, info = detectar_lineas_tubo(imagen, debug=debug)
    return centro_y

if __name__ == "__main__":
    print("="*70)
    print("DETECTOR DE LÍNEAS DEL TUBO VERTICAL")
    print("="*70)
    print("\nDetecta las líneas superior e inferior de la tapa del tubo")
    print()

    imagen = capturar_imagen()

    if imagen is None:
        print("Error al capturar imagen")
        exit(1)

    print("Detectando líneas del tubo...")
    y_superior, y_inferior, centro_y, info = detectar_lineas_tubo(imagen, debug=True)

    print(f"\n{'='*70}")
    if y_superior is not None:
        print(f"✓ TUBO DETECTADO")
        print(f"  Línea Superior: Y = {y_superior} px")
        print(f"  Línea Inferior: Y = {y_inferior} px")
        print(f"  Centro:         Y = {centro_y} px")
        print(f"  Altura:         {y_inferior - y_superior} px")
        print(f"  Confianza:      {info['score']} puntos")
    else:
        print(f"✗ NO SE DETECTÓ EL TUBO")
    print(f"{'='*70}")
