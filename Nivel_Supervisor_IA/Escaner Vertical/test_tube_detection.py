"""
Test independiente para calibrar la detección de tubos verticales
Permite probar diferentes parámetros y ver resultados en tiempo real
"""
import sys
import os
import cv2
import numpy as np
sys.path.append (os.path.join(os.path.dirname(__file__),'..','..','Nivel_Supervisor'))

from tube_detector_vertical import (
    capture_image_for_tube_detection,
    detect_tube_position
)

def test_detection_debug():
    """Test de detección con debug completo"""
    print("\n=== TEST DE DETECCIÓN CON DEBUG ===")
    
    image = capture_image_for_tube_detection(camera_index=0)
    
    if image is None:
        print("Error: No se pudo capturar imagen")
        return False
    
    # Detección con debug completo
    result = detect_tube_position(image, debug=True)
    
    if result is not None:
        print(f"\nRESULTADO FINAL: TUBO DETECTADO en Y = {result} píxeles")
        return True
    else:
        print("\nRESULTADO FINAL: No se detectó ningún tubo")
        return False

def interactive_parameter_tuning():
    """Función interactiva para ajustar parámetros"""
    print("\n=== AJUSTE INTERACTIVO DE PARÁMETROS ===")
    print("Esta función permite capturar una imagen y probar diferentes parámetros")
    
    # Capturar imagen base
    image = capture_image_for_tube_detection(camera_index=0)
    
    if image is None:
        print("Error: No se pudo capturar imagen")
        return
    
    print("Imagen capturada. Probando diferentes configuraciones...")
    
    # Pipelines activos a evaluar
    configs = [
        {
            'name': 'HSV Adaptativo (S Otsu + H centro) → Hough',
            'filter_type': 'hsv_adapt_hough',
            'roi_frac_x': 0.55,
            'v_max': 245,
            'h_tol': 10,
            'remove_vertical_len': 35,
            'canny_low': 40,
            'canny_high': 100,
            'min_line_length': 60,
            'max_line_gap': 15,
            'min_sep_px': 8,
            'max_sep_px': 120,
            'area_min': 120,
            'area_max': 20000
        },
        {
            'name': 'HSV H+S → Hough horizontales',
            'filter_type': 'hsv_hs_hough',
            's_min': 25,
            'h_tol': 12,
            'roi_frac_x': 0.5,
            'v_max': 245,
            'canny_low': 40,
            'canny_high': 100,
            'min_line_length': 60,
            'max_line_gap': 15,
            'min_sep_px': 8,
            'max_sep_px': 120,
            'area_min': 120,
            'area_max': 20000
        },
        {
            'name': 'Sobel-Y Pair Sweep (HS ROI)',
            'filter_type': 'sobely_pair_sweep',
            'roi_frac_x': 0.55,
            's_min': 20,
            'h_tol': 12,
            'v_max': 245,
            'smooth_sigma_rows': 6,
            'min_sep_px': 8,
            'max_sep_px': 160,
            'band_expand_rows': 8,
            'area_min': 120,
            'area_max': 20000
        }
    ]
    
    results = []
    
    for i, config in enumerate(configs):
        print(f"\nProbando configuración {i+1}: {config['name']}")
        
        # Aplicar filtro según configuración - NUEVOS MÉTODOS
        pair_info = None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if config['filter_type'] == 'hsv_hs_hough':
            # Combinar H y S (con V como anti-blanco) y buscar líneas horizontales (Hough)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            H, S, V = cv2.split(hsv)
            s_min = int(config.get('s_min', 25))
            v_max = int(config.get('v_max', 245))
            h_tol = int(config.get('h_tol', 12))
            # Máscara por saturación (evita blancos puros)
            mask_s = (S >= s_min).astype(np.uint8) * 255
            # Estimar hue dominante en ROI central sobre píxeles con S >= s_min
            h_img, w_img = H.shape
            frac = float(config.get('roi_frac_x', 0.5))
            frac = min(1.0, max(0.2, frac))
            x0 = int((w_img * (1 - frac)) // 2)
            x1 = w_img - x0
            roi_h = H[:, x0:x1]
            roi_s = S[:, x0:x1]
            valid = roi_s >= max(10, s_min)
            if np.count_nonzero(valid) > 50:
                h_vals = roi_h[valid]
                hist, _ = np.histogram(h_vals, bins=180, range=(0, 180))
                h_center = int(np.argmax(hist))
                # Distancia circular de hue
                diff = cv2.absdiff(H, np.uint8(h_center))
                diff2 = cv2.absdiff(diff, np.uint8(180))
                circ = cv2.min(diff, diff2)
                mask_h = (circ <= h_tol).astype(np.uint8) * 255
                # Confiar en H solo donde hay saturación
                mask_h = cv2.bitwise_and(mask_h, (S >= max(10, s_min)).astype(np.uint8) * 255)
            else:
                mask_h = np.zeros_like(H)
            # Evitar blancos puros con V muy alto
            mask_v = (V <= v_max).astype(np.uint8) * 255
            # Combinar
            comb = cv2.bitwise_and(cv2.bitwise_or(mask_s, mask_h), mask_v)
            comb = cv2.GaussianBlur(comb, (5, 5), 0)
            edges = cv2.Canny(comb, int(config.get('canny_low', 40)), int(config.get('canny_high', 100)))
            # Hough de líneas: elegir el par de horizontales más largas con separación razonable
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=60,
                                    minLineLength=int(config.get('min_line_length', 60)),
                                    maxLineGap=int(config.get('max_line_gap', 15)))
            horizontals = []  # (y_mid, xL, xR, length)
            if lines is not None:
                for l in lines:
                    x1, y1, x2, y2 = l[0]
                    if abs(y2 - y1) <= max(2, int(0.2 * abs(x2 - x1))):
                        xL, xR = min(x1, x2), max(x1, x2)
                        length = float(np.hypot(x2 - x1, y2 - y1))
                        y_mid = int(round((y1 + y2) / 2.0))
                        horizontals.append((y_mid, xL, xR, length))
            # Elegir par con mayor suma de longitudes y separación razonable; requerir solape mínimo
            min_sep = int(config.get('min_sep_px', 8))
            max_sep = int(config.get('max_sep_px', 120))
            best_pair = None
            best_total_len = -1.0
            for i in range(len(horizontals)):
                yA, xL_A, xR_A, lenA = horizontals[i]
                for j in range(i+1, len(horizontals)):
                    yB, xL_B, xR_B, lenB = horizontals[j]
                    dy = abs(yB - yA)
                    if min_sep <= dy <= max_sep:
                        xL = max(min(xL_A, xR_A), min(xL_B, xR_B))
                        xR = min(max(xL_A, xR_A), max(xL_B, xR_B))
                        overlap = max(0, xR - xL)
                        total_len = lenA + lenB
                        if overlap > 20 and total_len > best_total_len:
                            best_total_len = total_len
                            best_pair = (min(yA, yB), max(yA, yB), xL, xR)
            # Construir máscara final y guardar par de líneas
            if best_pair is not None:
                y_top, y_bot, xL, xR = best_pair
                pair_info = {'y_top': y_top, 'y_bot': y_bot, 'xL': xL, 'xR': xR}
                mask = np.zeros_like(gray)
                cv2.rectangle(mask, (xL, y_top), (xR, y_bot), 255, -1)
            else:
                mask = comb
        
        elif config['filter_type'] == 'hsv_adapt_hough':
            # Umbral adaptativo de S (Otsu) en ROI central + H centrado (modo) + Hough de horizontales
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            H, S, V = cv2.split(hsv)
            h_img, w_img = H.shape
            v_max = int(config.get('v_max', 245))
            frac = float(config.get('roi_frac_x', 0.55))
            frac = min(1.0, max(0.2, frac))
            x0 = int((w_img * (1 - frac)) // 2)
            x1 = w_img - x0
            roi_s = S[:, x0:x1]
            roi_v = V[:, x0:x1]
            # Anti-blanco en ROI
            roi_mask_v = (roi_v <= v_max).astype(np.uint8) * 255
            # Otsu sobre S restringido a V bajo
            s_roi = roi_s.copy()
            s_roi[roi_mask_v == 0] = 0
            try:
                thr_val, _ = cv2.threshold(s_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                s_min = max(10, int(thr_val))
            except Exception:
                s_min = 25
            mask_s = (S >= s_min).astype(np.uint8) * 255
            # H centro (modo) en ROI sobre pixeles con S >= s_min y V <= v_max
            roi_h = H[:, x0:x1]
            valid = (roi_s >= s_min) & (roi_v <= v_max)
            if np.count_nonzero(valid) > 50:
                h_vals = roi_h[valid]
                hist, _ = np.histogram(h_vals, bins=180, range=(0, 180))
                h_center = int(np.argmax(hist))
                h_tol = int(config.get('h_tol', 10))
                diff = cv2.absdiff(H, np.uint8(h_center))
                diff2 = cv2.absdiff(diff, np.uint8(180))
                circ = cv2.min(diff, diff2)
                mask_h = (circ <= h_tol).astype(np.uint8) * 255
                mask_h = cv2.bitwise_and(mask_h, (S >= s_min).astype(np.uint8) * 255)
            else:
                mask_h = np.zeros_like(H)
            mask_v = (V <= v_max).astype(np.uint8) * 255
            comb = cv2.bitwise_and(cv2.bitwise_or(mask_s, mask_h), mask_v)
            # Remover verticales largos antes de Hough
            vlen = int(config.get('remove_vertical_len', 35))
            kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vlen))
            comb_nv = cv2.morphologyEx(comb, cv2.MORPH_OPEN, kernel_vert, iterations=1)
            comb = cv2.subtract(comb, comb_nv)
            comb = cv2.GaussianBlur(comb, (5, 5), 0)
            edges = cv2.Canny(comb, int(config.get('canny_low', 40)), int(config.get('canny_high', 100)))
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=60,
                                    minLineLength=int(config.get('min_line_length', 60)),
                                    maxLineGap=int(config.get('max_line_gap', 15)))
            horizontals = []  # (y_mid, xL, xR, length)
            if lines is not None:
                for l in lines:
                    x1, y1, x2, y2 = l[0]
                    if abs(y2 - y1) <= max(2, int(0.2 * abs(x2 - x1))):
                        xL, xR = min(x1, x2), max(x1, x2)
                        length = float(np.hypot(x2 - x1, y2 - y1))
                        y_mid = int(round((y1 + y2) / 2.0))
                        horizontals.append((y_mid, xL, xR, length))
            min_sep = int(config.get('min_sep_px', 8))
            max_sep = int(config.get('max_sep_px', 120))
            best_pair = None
            best_total_len = -1.0
            for i in range(len(horizontals)):
                yA, xL_A, xR_A, lenA = horizontals[i]
                for j in range(i+1, len(horizontals)):
                    yB, xL_B, xR_B, lenB = horizontals[j]
                    dy = abs(yB - yA)
                    if min_sep <= dy <= max_sep:
                        xL = max(min(xL_A, xR_A), min(xL_B, xR_B))
                        xR = min(max(xL_A, xR_A), max(xL_B, xR_B))
                        overlap = max(0, xR - xL)
                        total_len = lenA + lenB
                        if overlap > 20 and total_len > best_total_len:
                            best_total_len = total_len
                            best_pair = (min(yA, yB), max(yA, yB), xL, xR)
            if best_pair is not None:
                y_top, y_bot, xL, xR = best_pair
                mask = np.zeros_like(gray)
                cv2.rectangle(mask, (xL, y_top), (xR, y_bot), 255, -1)
            else:
                mask = comb

        elif config['filter_type'] == 'sobely_pair_sweep':
            # Buscar par (y, y+dy) que maximiza la energía vertical sumada en ROI, barriendo dy
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            H, S, V = cv2.split(hsv)
            v_max = int(config.get('v_max', 245))
            s_min = int(config.get('s_min', 20))
            h_tol = int(config.get('h_tol', 12))
            h_img, w_img = H.shape
            frac = float(config.get('roi_frac_x', 0.55))
            frac = min(1.0, max(0.2, frac))
            x0 = int((w_img * (1 - frac)) // 2)
            x1 = w_img - x0
            roi_h = H[:, x0:x1]
            roi_s = S[:, x0:x1]
            valid = roi_s >= max(10, s_min)
            if np.count_nonzero(valid) > 50:
                h_vals = roi_h[valid]
                hist, _ = np.histogram(h_vals, bins=180, range=(0, 180))
                h_center = int(np.argmax(hist))
            else:
                h_center = 0
            diff = cv2.absdiff(H, np.uint8(h_center))
            diff2 = cv2.absdiff(diff, np.uint8(180))
            circ = cv2.min(diff, diff2)
            mask_h = (circ <= h_tol).astype(np.uint8) * 255
            mask_s = (S >= s_min).astype(np.uint8) * 255
            mask_v = (V <= v_max).astype(np.uint8) * 255
            hs = cv2.bitwise_or(mask_s, mask_h)
            comb = cv2.bitwise_and(hs, mask_v)
            gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
            sobely = cv2.Sobel(gray_blur, cv2.CV_32F, 0, 1, ksize=3)
            sobely = np.abs(sobely)
            sobely = cv2.normalize(sobely, None, 0, 255, cv2.NORM_MINMAX)
            sobely = (sobely * (comb.astype(np.float32) / 255.0)).astype(np.uint8)
            sob_roi = sobely[:, x0:x1].astype(np.float32)
            row_energy = sob_roi.sum(axis=1)
            sigma = float(config.get('smooth_sigma_rows', 6))
            ksize = int(max(3, 2 * int(3 * sigma) + 1))
            row_sm = cv2.GaussianBlur(row_energy[:, None], (1, ksize), sigma).ravel()
            min_sep = int(config.get('min_sep_px', 8))
            max_sep = int(config.get('max_sep_px', 160))
            best_score = -1.0
            best_pair = None
            # Barrido de separaciones
            for dy in range(min_sep, min(max_sep, h_img - 1)):
                if dy >= h_img:
                    break
                Epair = row_sm[:-dy] + row_sm[dy:]
                if Epair.size == 0:
                    continue
                idx = int(np.argmax(Epair))
                score = float(Epair[idx])
                if score > best_score:
                    best_score = score
                    best_pair = (idx, idx + dy)
            mask = np.zeros_like(gray)
            if best_pair is not None:
                y_top, y_bot = best_pair
                expand = int(config.get('band_expand_rows', 8))
                y_top = max(0, y_top - expand)
                y_bot = min(h_img - 1, y_bot + expand)
                pair_info = {'y_top': y_top, 'y_bot': y_bot, 'xL': x0, 'xR': x1}
                cv2.rectangle(mask, (x0, y_top), (x1, y_bot), 255, -1)
            else:
                # Fallback: umbralizar sobely dentro del ROI
                _, mask_roi = cv2.threshold(sob_roi.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                mask[:, :] = 0
                mask[:, x0:x1] = mask_roi
        
        else:
            # Fallback a threshold simple
            _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # Mostrar solo las dos líneas horizontales detectadas (si existen)
        debug_img = image.copy()
        if pair_info is not None:
            y_top = pair_info['y_top']; y_bot = pair_info['y_bot']
            xL = pair_info['xL']; xR = pair_info['xR']
            cv2.line(debug_img, (xL, y_top), (xR, y_top), (0, 0, 255), 2)
            cv2.line(debug_img, (xL, y_bot), (xR, y_bot), (0, 255, 0), 2)
            center_y = (y_top + y_bot) // 2
            cv2.circle(debug_img, (xL + (xR - xL)//2, center_y), 5, (255, 0, 0), -1)
            print(f"  Líneas detectadas: y_top={y_top}, y_bot={y_bot} -> center_y={center_y}")
        else:
            print("  No se detectó par de líneas horizontales válidas")

        # Mostrar resultado simple
        cv2.imshow(f"Config {i+1}: {config['name']} - Presiona tecla para siguiente", debug_img)
        cv2.waitKey(0)
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    print("=== TEST DE DETECCIÓN DE TUBOS VERTICALES (DEBUG) ===")
    test_detection_debug()
