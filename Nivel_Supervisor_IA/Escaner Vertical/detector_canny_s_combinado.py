"""
Detector que COMBINA Canny + Canal S para ignorar fondo blanco

Estrategia:
1. Usar Canny (20, 172) para detectar bordes de la tapa
2. Usar Canal S para distinguir tubo PVC (S bajo) de fondo madera (S más alto)
3. Combinar ambos para filtrar falsos positivos del fondo blanco
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
    if not camera_mgr.acquire("detector_combinado"):
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
        camera_mgr.release("detector_combinado")

def detectar_con_canny_y_canal_s(imagen, debug=False):
    """
    Combina Canny + Canal S para detectar tubo ignorando fondo blanco

    El problema: Fondo blanco también tiene bordes detectados por Canny
    La solución: Usar Canal S para diferenciar
    - Tubo PVC blanco: S muy bajo (0-30)
    - Fondo madera: S más alto (40+)
    - Fondo blanco: S bajo PERO sin estructura rectangular
    """

    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # ==== PASO 1: Canny para detectar bordes ====
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges_canny = cv2.Canny(blurred, 20, 172)

    # ==== PASO 2: Máscara en Canal S ====
    # Buscar regiones de BAJA saturación (tubo + fondo blanco)
    s_inv = 255 - s
    _, mask_s_low = cv2.threshold(s_inv, 150, 255, cv2.THRESH_BINARY)

    # ==== PASO 3: Combinar Canny + Canal S ====
    # Opción A: Bordes que estén en regiones de baja saturación
    edges_en_low_s = cv2.bitwise_and(edges_canny, mask_s_low)

    # Opción B: Dilatar bordes y luego filtrar con S
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
        if aspect_ratio < 0.9:  # Más alto que ancho

            # Extraer ROI del contorno
            roi_s = s[y:y+h, x:x+w]

            # Analizar saturación en ROI
            mean_s = np.mean(roi_s)
            std_s = np.std(roi_s)

            score = 0

            # Bonus por forma vertical
            if aspect_ratio < 0.5:
                score += 35
            elif aspect_ratio < 0.7:
                score += 25
            else:
                score += 15

            # Bonus por tamaño
            if 15 < w < 80 and 30 < h < 150:
                score += 25

            # NUEVO: Bonus por saturación BAJA y UNIFORME
            if mean_s < 35:  # Saturación muy baja (tubo PVC)
                score += 30
                if std_s < 15:  # Uniforme (no es textura de madera)
                    score += 20

            # Bonus por estar centrado
            centro_x = x + w // 2
            img_center_x = imagen.shape[1] // 2
            dist_x = abs(centro_x - img_center_x)
            if dist_x < imagen.shape[1] * 0.25:
                score += 20

            # Bonus por área
            if 600 < area < 6000:
                score += 15

            candidatos.append({
                'bbox': (x, y, w, h),
                'centro_y': y + h // 2,
                'centro_x': centro_x,
                'area': area,
                'aspect': aspect_ratio,
                'score': score,
                'mean_s': mean_s,
                'std_s': std_s
            })

    # Ordenar por score
    candidatos = sorted(candidatos, key=lambda c: c['score'], reverse=True)

    if debug:
        print(f"\n{'='*70}")
        print("DETECTOR COMBINADO: Canny + Canal S")
        print(f"{'='*70}")
        print(f"Candidatos encontrados: {len(candidatos)}")

        if candidatos:
            for i, cand in enumerate(candidatos[:5]):
                print(f"\n  Candidato #{i+1}:")
                print(f"    Score: {cand['score']}")
                print(f"    Centro Y: {cand['centro_y']}")
                print(f"    Aspecto: {cand['aspect']:.2f}")
                print(f"    Área: {cand['area']:.0f}")
                print(f"    Saturación media: {cand['mean_s']:.1f}")
                print(f"    Saturación std: {cand['std_s']:.1f}")

        # Visualización
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('DETECTOR COMBINADO: Canny + Canal S', fontsize=16, fontweight='bold')

        # Fila 1
        axes[0,0].imshow(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
        axes[0,0].set_title('Original')
        axes[0,0].axis('off')

        axes[0,1].imshow(s, cmap='gray')
        axes[0,1].set_title(f'Canal S\nMedia: {np.mean(s):.1f}')
        axes[0,1].axis('off')

        axes[0,2].imshow(mask_s_low, cmap='gray')
        axes[0,2].set_title('Máscara S Bajo\n(Tubo + Fondo blanco)')
        axes[0,2].axis('off')

        # Fila 2
        axes[1,0].imshow(edges_canny, cmap='gray')
        axes[1,0].set_title('Canny (20, 172)')
        axes[1,0].axis('off')

        axes[1,1].imshow(edges_final, cmap='gray')
        axes[1,1].set_title('Canny + S filtrado')
        axes[1,1].axis('off')

        # Resultado final
        resultado = imagen.copy()
        for i, cand in enumerate(candidatos[:3]):
            x, y, w, h = cand['bbox']
            color = [(0, 255, 0), (0, 255, 255), (255, 0, 255)][i]
            cv2.rectangle(resultado, (x, y), (x+w, y+h), color, 2)
            texto = f"#{i+1}: {cand['score']}\nS:{cand['mean_s']:.0f}"
            y_texto = y - 10 if y > 40 else y + h + 20
            for j, linea in enumerate(texto.split('\n')):
                cv2.putText(resultado, linea, (x, y_texto + j*15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.circle(resultado, (cand['centro_x'], cand['centro_y']), 5, (255, 0, 0), -1)

        axes[1,2].imshow(cv2.cvtColor(resultado, cv2.COLOR_BGR2RGB))
        axes[1,2].set_title(f'Resultado: {len(candidatos)} candidatos')
        axes[1,2].axis('off')

        plt.tight_layout()
        plt.show()

    # Retornar mejor candidato
    if candidatos and candidatos[0]['score'] > 50:  # Threshold de confianza
        return candidatos[0]['centro_y'], candidatos
    else:
        return None, candidatos

if __name__ == "__main__":
    print("="*70)
    print("DETECTOR COMBINADO: Canny + Canal S")
    print("="*70)
    print("\nVentaja: Ignora fondo blanco usando saturación")
    print()

    imagen = capturar_imagen()

    if imagen is None:
        print("Error al capturar imagen")
        exit(1)

    print("Detectando tubo...")
    centro_y, candidatos = detectar_con_canny_y_canal_s(imagen, debug=True)

    print(f"\n{'='*70}")
    if centro_y is not None:
        print(f"✓ TUBO DETECTADO en Y = {centro_y} píxeles")
        if candidatos:
            print(f"  Confianza: {candidatos[0]['score']} puntos")
    else:
        if candidatos:
            print(f"✗ Candidatos encontrados pero con baja confianza")
            print(f"  Mejor score: {candidatos[0]['score']}")
        else:
            print(f"✗ NO SE DETECTÓ EL TUBO")
    print(f"{'='*70}")
