"""
Ajuste de parámetros del detector de tubo vertical en VIVO
Permite ajustar umbrales y ver resultados en tiempo real
"""
import cv2
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

def nada(x):
    """Callback vacío para trackbars"""
    pass

def detectar_con_parametros(imagen, canny_low, canny_high, s_threshold, margin, min_altura):
    """
    Detecta tubo con parámetros ajustables

    Returns:
        y_sup, y_inf, tube_complete, info
    """
    if imagen is None:
        return None, None, False, {}

    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Aplicar Canny
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges_canny = cv2.Canny(blurred, canny_low, canny_high)

    # Máscara en Canal S
    s_inv = 255 - s
    _, mask_s_low = cv2.threshold(s_inv, s_threshold, 255, cv2.THRESH_BINARY)

    # Combinar Canny + Canal S
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges_dilated = cv2.dilate(edges_canny, kernel_dilate, iterations=1)
    edges_filtrados = cv2.bitwise_and(edges_dilated, mask_s_low)

    # Morfología
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9))
    edges_final = cv2.morphologyEx(edges_filtrados, cv2.MORPH_CLOSE, kernel_close)

    # Encontrar contornos
    contours, _ = cv2.findContours(edges_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidatos = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 250:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / h if h > 0 else 0

        # Buscar rectángulos VERTICALES
        if aspect_ratio < 0.9:
            roi_s = s[y:y+h, x:x+w]
            mean_s = np.mean(roi_s)
            std_s = np.std(roi_s)

            score = 0

            if aspect_ratio < 0.5:
                score += 35
            elif aspect_ratio < 0.7:
                score += 25
            else:
                score += 15

            if 15 < w < 80 and 30 < h < 150:
                score += 25

            if mean_s < 35:
                score += 30
                if std_s < 15:
                    score += 20

            centro_x = x + w // 2
            img_center_x = imagen.shape[1] // 2
            dist_x = abs(centro_x - img_center_x)
            if dist_x < imagen.shape[1] * 0.25:
                score += 20

            if 600 < area < 6000:
                score += 15

            y_superior = y
            y_inferior = y + h
            centro_y = y + h // 2

            candidatos.append({
                'bbox': (x, y, w, h),
                'y_superior': y_superior,
                'y_inferior': y_inferior,
                'centro_y': centro_y,
                'score': score,
                'mean_s': mean_s,
                'altura': h
            })

    # Ordenar por score
    candidatos = sorted(candidatos, key=lambda c: c['score'], reverse=True)

    if candidatos and candidatos[0]['score'] > 50:
        mejor = candidatos[0]
        y_sup = mejor['y_superior']
        y_inf = mejor['y_inferior']

        # Verificar si está completo
        frame_height = imagen.shape[0]
        superior_visible = (y_sup >= margin)
        inferior_visible = (y_inf <= frame_height - margin)
        altura = y_inf - y_sup

        tube_complete = (superior_visible and inferior_visible and altura >= min_altura)

        return y_sup, y_inf, tube_complete, {
            'altura': altura,
            'score': mejor['score'],
            'mean_s': mejor['mean_s'],
            'edges_final': edges_final,
            'mask_s': mask_s_low
        }

    return None, None, False, {'edges_final': edges_final, 'mask_s': mask_s_low}

def capturar_imagen():
    """Captura imagen de la cámara"""
    camera_mgr = get_camera_manager()
    if not camera_mgr.acquire("ajuste_parametros"):
        return None
    try:
        frame = camera_mgr.capture_frame(timeout=4.0, max_retries=3)
        if frame is None:
            return None

        # Rotar y recortar
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)

        return frame_rotado[y1:y2, x1:x2]
    finally:
        camera_mgr.release("ajuste_parametros")

def modo_interactivo():
    """Modo interactivo con trackbars"""

    print("="*70)
    print("AJUSTE DE PARÁMETROS DEL DETECTOR DE TUBO VERTICAL")
    print("="*70)
    print("\nCapturando imagen inicial...")

    imagen = capturar_imagen()

    if imagen is None:
        print("Error: No se pudo capturar imagen")
        return

    print("Imagen capturada. Iniciando modo interactivo...")

    # Crear ventanas
    cv2.namedWindow('Original', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Resultado', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Controles', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Debug', cv2.WINDOW_NORMAL)

    # Trackbars
    cv2.createTrackbar('Canny Low', 'Controles', 20, 200, nada)
    cv2.createTrackbar('Canny High', 'Controles', 172, 300, nada)
    cv2.createTrackbar('S Threshold', 'Controles', 150, 255, nada)
    cv2.createTrackbar('Margen (px)', 'Controles', 10, 50, nada)
    cv2.createTrackbar('Altura Min (px)', 'Controles', 30, 200, nada)
    cv2.createTrackbar('Capturar Nueva', 'Controles', 0, 1, nada)

    print("\n" + "="*70)
    print("CONTROLES:")
    print("  - Ajusta los trackbars para modificar parámetros")
    print("  - 'Capturar Nueva': Activa para tomar nueva imagen")
    print("  - Presiona 'q' para salir")
    print("  - Presiona 'g' para guardar parámetros")
    print("="*70)

    ultima_captura = imagen

    while True:
        # Leer trackbars
        canny_low = cv2.getTrackbarPos('Canny Low', 'Controles')
        canny_high = cv2.getTrackbarPos('Canny High', 'Controles')
        s_threshold = cv2.getTrackbarPos('S Threshold', 'Controles')
        margin = cv2.getTrackbarPos('Margen (px)', 'Controles')
        min_altura = cv2.getTrackbarPos('Altura Min (px)', 'Controles')
        capturar = cv2.getTrackbarPos('Capturar Nueva', 'Controles')

        # Capturar nueva imagen si se solicitó
        if capturar == 1:
            nueva_img = capturar_imagen()
            if nueva_img is not None:
                ultima_captura = nueva_img
                print("Nueva imagen capturada")
            cv2.setTrackbarPos('Capturar Nueva', 'Controles', 0)

        # Aplicar detección
        y_sup, y_inf, tube_complete, info = detectar_con_parametros(
            ultima_captura, canny_low, canny_high, s_threshold, margin, min_altura
        )

        # Visualización
        resultado = ultima_captura.copy()

        if y_sup is not None and y_inf is not None:
            # Dibujar líneas
            cv2.line(resultado, (0, y_sup), (resultado.shape[1], y_sup), (0, 0, 255), 2)
            cv2.line(resultado, (0, y_inf), (resultado.shape[1], y_inf), (0, 255, 0), 2)

            # Estado
            status_color = (0, 255, 0) if tube_complete else (0, 165, 255)
            status_text = "COMPLETO" if tube_complete else "CORTADO"
            cv2.putText(resultado, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)

            # Info
            altura = info.get('altura', 0)
            score = info.get('score', 0)
            mean_s = info.get('mean_s', 0)

            cv2.putText(resultado, f"Altura: {altura}px", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(resultado, f"Score: {score}", (10, 85),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(resultado, f"S_mean: {mean_s:.1f}", (10, 110),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        else:
            cv2.putText(resultado, "NO DETECTADO", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Parámetros actuales
        cv2.putText(resultado, f"Canny: {canny_low}-{canny_high}", (10, resultado.shape[0]-60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        cv2.putText(resultado, f"S_thr: {s_threshold}", (10, resultado.shape[0]-40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        cv2.putText(resultado, f"Margin: {margin}, Min_H: {min_altura}", (10, resultado.shape[0]-20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # Mostrar ventanas
        cv2.imshow('Original', ultima_captura)
        cv2.imshow('Resultado', resultado)

        # Debug: mostrar bordes y máscara S
        if 'edges_final' in info:
            cv2.imshow('Debug', info['edges_final'])

        # Esperar tecla
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('g'):
            print("\n" + "="*70)
            print("PARÁMETROS GUARDADOS:")
            print(f"  canny_low = {canny_low}")
            print(f"  canny_high = {canny_high}")
            print(f"  s_threshold = {s_threshold}")
            print(f"  margin = {margin}")
            print(f"  min_altura = {min_altura}")
            print("="*70)

            # Guardar en archivo
            with open('parametros_detector.txt', 'w') as f:
                f.write(f"# Parámetros del detector de tubo vertical\n")
                f.write(f"canny_low = {canny_low}\n")
                f.write(f"canny_high = {canny_high}\n")
                f.write(f"s_threshold = {s_threshold}\n")
                f.write(f"margin = {margin}\n")
                f.write(f"min_altura = {min_altura}\n")

            print("Parámetros guardados en 'parametros_detector.txt'")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    print("="*70)
    print("AJUSTE INTERACTIVO DE PARÁMETROS")
    print("="*70)
    modo_interactivo()
