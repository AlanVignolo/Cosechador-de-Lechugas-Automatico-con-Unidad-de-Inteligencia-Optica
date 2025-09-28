"""
Test independiente para calibrar la detección de tubos verticales
Permite probar diferentes parámetros y ver resultados en tiempo real
"""

import sys
import os
import cv2
import numpy as np

# Agregar paths necesarios
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))

from tube_detector_vertical import (
    test_tube_detection,
    capture_image_for_tube_detection,
    detect_tube_position,
    detect_tube_lines_debug,
    scan_available_cameras
)

def test_camera_connection():
    """Test básico de conexión de cámara"""
    print("=== TEST DE CONEXIÓN DE CÁMARA ===")
    
    cameras = scan_available_cameras()
    
    if not cameras:
        print("Error: No se encontraron cámaras funcionales")
        return False
    
    print(f"Cámaras encontradas: {len(cameras)}")
    for cam in cameras:
        print(f"  Cámara {cam['index']}: {cam['resolution']} - {'OK' if cam['working'] else 'ERROR'}")
    
    return len([c for c in cameras if c['working']]) > 0

def test_image_capture():
    """Test de captura de imagen"""
    print("\n=== TEST DE CAPTURA DE IMAGEN ===")
    
    image = capture_image_for_tube_detection(camera_index=0)
    
    if image is None:
        print("Error: No se pudo capturar imagen")
        return False
    
    h, w = image.shape[:2]
    print(f"Imagen capturada exitosamente: {w}x{h}")
    
    # Mostrar imagen capturada
    cv2.imshow("Imagen Capturada - Presiona cualquier tecla para continuar", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return True

def test_detection_simple():
    """Test de detección simple sin debug visual"""
    print("\n=== TEST DE DETECCIÓN SIMPLE ===")
    
    image = capture_image_for_tube_detection(camera_index=0)
    
    if image is None:
        print("Error: No se pudo capturar imagen")
        return False
    
    # Detección simple
    result = detect_tube_position(image, debug=False)
    
    if result is not None:
        print(f"TUBO DETECTADO en Y = {result} píxeles")
        
        # Mostrar resultado en imagen
        result_img = image.copy()
        h, w = result_img.shape[:2]
        cv2.line(result_img, (0, result), (w, result), (0, 255, 0), 2)
        cv2.circle(result_img, (w//2, result), 10, (255, 0, 0), -1)
        cv2.putText(result_img, f"Tubo Y={result}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Resultado - Presiona cualquier tecla para continuar", result_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return True
    else:
        print("No se detectó ningún tubo")
        return False

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
    
    # MÚLTIPLES ENFOQUES NUEVOS
    configs = [
        {
            'name': 'Template Matching Tubo',
            'filter_type': 'template_tubo',
            'area_min': 300,
            'area_max': 5000
        },
        {
            'name': 'Template Matching Tapa',
            'filter_type': 'template_tapa',
            'area_min': 200,
            'area_max': 3000
        },
        {
            'name': 'Solo Líneas Horizontales (Direccional)',
            'filter_type': 'direccional',
            'area_min': 200,
            'area_max': 6000
        },
        {
            'name': 'Análisis ROI Central',
            'filter_type': 'roi_central',
            'area_min': 150,
            'area_max': 4000
        },
        {
            'name': 'Texturas LBP',
            'filter_type': 'textura_lbp',
            'area_min': 200,
            'area_max': 5000
        },
        {
            'name': 'Diferencias RGB Multicanal',
            'filter_type': 'multicanal',
            'area_min': 100,
            'area_max': 4000
        },
        {
            'name': 'Orientación Horizontal por Gradiente',
            'filter_type': 'orientation',
            'angle_tol_deg': 20,  # tolerancia respecto a 90° (bordes horizontales)
            'area_min': 150,
            'area_max': 8000
        },
        {
            'name': 'Suprimir Líneas Verticales (Morph)',
            'filter_type': 'remove_vertical',
            'vertical_len': 35,
            'area_min': 150,
            'area_max': 8000
        },
        {
            'name': 'Hough de Líneas Horizontales',
            'filter_type': 'hough_horizontal',
            'min_line_length': 60,
            'max_line_gap': 15,
            'canny_low': 40,
            'canny_high': 100,
            'area_min': 150,
            'area_max': 8000
        },
        {
            'name': 'Gabor Horizontal (theta=90°)',
            'filter_type': 'gabor',
            'theta_deg': 90,
            'ksize': 31,
            'sigma': 4.0,
            'lambd': 10.0,
            'gamma': 0.5,
            'area_min': 150,
            'area_max': 7000
        },
        {
            'name': 'Pipeline: quitar vertical + cerrar horizontal',
            'filter_type': 'close_connect',
            'vertical_len': 35,
            'horiz_len': 25,
            'canny_low': 40,
            'canny_high': 100,
            'area_min': 150,
            'area_max': 9000
        },
        {
            'name': 'FFT Notch (suprimir frecuencias verticales)',
            'filter_type': 'fft_notch',
            'notch_width': 8,
            'area_min': 150,
            'area_max': 9000
        },
        {
            'name': 'Hough Ensamble Rectangular (dos horizontales)',
            'filter_type': 'hough_rect_assembly',
            'canny_low': 40,
            'canny_high': 100,
            'min_line_length': 40,
            'max_line_gap': 20,
            'max_y_gap_between_horizontals': 80,
            'area_min': 150,
            'area_max': 12000
        },
        {
            'name': 'CLAHE + Canny',
            'filter_type': 'clahe_canny',
            'clip_limit': 3.0,
            'tile_grid': 8,
            'canny_low': 50,
            'canny_high': 120,
            'area_min': 150,
            'area_max': 9000
        },
        {
            'name': 'MSER con TopHat',
            'filter_type': 'mser',
            'delta': 5,
            'min_area': 60,
            'max_area': 10000,
            'area_min': 150,
            'area_max': 12000
        },
        {
            'name': 'Proyección Horizontal (picos en filas)',
            'filter_type': 'row_projection',
            'canny_low': 40,
            'canny_high': 100,
            'vertical_len': 35,
            'min_band_thickness': 8,
            'prominence': 0.15,  # fracción del máximo
            'area_min': 200,
            'area_max': 12000
        }
    ]
    
    results = []
    
    for i, config in enumerate(configs):
        print(f"\nProbando configuración {i+1}: {config['name']}")
        
        # Aplicar filtro según configuración - NUEVOS MÉTODOS
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if config['filter_type'] == 'template_tubo':
            # Template matching para tubo (construye máscara al tamaño original)
            th, tw = 20, 60
            tubo_template = np.ones((th, tw), dtype=np.uint8) * 255
            tubo_template = cv2.rectangle(tubo_template, (5, 5), (tw-5, 15), 0, 2)
            tubo_match = cv2.matchTemplate(gray, tubo_template, cv2.TM_CCOEFF_NORMED)
            mask = np.zeros_like(gray)
            # Umbral de similitud
            y_idx, x_idx = np.where(tubo_match >= 0.6)
            for (yy, xx) in zip(y_idx, x_idx):
                cv2.rectangle(mask, (int(xx), int(yy)), (int(xx+tw), int(yy+th)), 255, -1)
            
        elif config['filter_type'] == 'template_tapa':
            # Template matching para tapa (construye máscara al tamaño original)
            th, tw = 40, 25
            tapa_template = np.ones((th, tw), dtype=np.uint8) * 255
            tapa_template = cv2.rectangle(tapa_template, (5, 5), (tw-5, th-5), 0, 2)
            tapa_match = cv2.matchTemplate(gray, tapa_template, cv2.TM_CCOEFF_NORMED)
            mask = np.zeros_like(gray)
            y_idx, x_idx = np.where(tapa_match >= 0.55)
            for (yy, xx) in zip(y_idx, x_idx):
                cv2.rectangle(mask, (int(xx), int(yy)), (int(xx+tw), int(yy+th)), 255, -1)
            
        elif config['filter_type'] == 'direccional':
            # Filtrado direccional - solo líneas horizontales
            kernel_horizontal = np.array([[-1, -1, -1],
                                        [ 2,  2,  2],
                                        [-1, -1, -1]], dtype=np.float32)
            horizontal_response = cv2.filter2D(gray, -1, kernel_horizontal)
            horizontal_response = np.clip(horizontal_response, 0, 255).astype(np.uint8)
            _, mask = cv2.threshold(horizontal_response, 50, 255, cv2.THRESH_BINARY)
            
        elif config['filter_type'] == 'roi_central':
            # Análisis solo en ROI central
            h_img, w_img = gray.shape
            zona_central = gray[h_img//4:3*h_img//4, w_img//4:3*w_img//4]
            zona_central_blur = cv2.GaussianBlur(zona_central, (5, 5), 0)
            zona_central_canny = cv2.Canny(zona_central_blur, 40, 100)
            mask = np.zeros_like(gray)
            mask[h_img//4:3*h_img//4, w_img//4:3*w_img//4] = zona_central_canny
            
        elif config['filter_type'] == 'textura_lbp':
            # Análisis de texturas LBP simplificado
            def get_lbp_simple(img):
                rows, cols = img.shape
                lbp = np.zeros_like(img)
                for i in range(1, rows - 1):
                    for j in range(1, cols - 1):
                        center = img[i, j]
                        code = 0
                        code |= (img[i-1, j-1] >= center) << 7
                        code |= (img[i-1, j] >= center) << 6
                        code |= (img[i-1, j+1] >= center) << 5
                        code |= (img[i, j+1] >= center) << 4
                        code |= (img[i+1, j+1] >= center) << 3
                        code |= (img[i+1, j] >= center) << 2
                        code |= (img[i+1, j-1] >= center) << 1
                        code |= (img[i, j-1] >= center)
                        lbp[i, j] = code
                return lbp
            lbp = get_lbp_simple(gray)
            _, mask = cv2.threshold(lbp, 50, 255, cv2.THRESH_BINARY)
            
        elif config['filter_type'] == 'multicanal':
            # Diferencias entre canales R, G, B
            b, g, r = cv2.split(image)
            diff_rg = cv2.absdiff(r, g)
            diff_rb = cv2.absdiff(r, b)
            diff_gb = cv2.absdiff(g, b)
            multi_diff = cv2.addWeighted(diff_rg, 0.33, diff_rb, 0.33, 0)
            multi_diff = cv2.addWeighted(multi_diff, 1.0, diff_gb, 0.34, 0)
            _, mask = cv2.threshold(multi_diff, 15, 255, cv2.THRESH_BINARY)
        
        elif config['filter_type'] == 'orientation':
            # Mantener solo bordes con orientación horizontal (gradiente ~90°)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 40, 100)
            dx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
            dy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
            ang = np.rad2deg(np.arctan2(np.abs(dy), np.abs(dx) + 1e-5))  # 0° vertical, 90° horizontal
            tol = float(config.get('angle_tol_deg', 20))
            orient_mask = (ang >= (90 - tol)).astype(np.uint8) * 255
            mask = cv2.bitwise_and(edges, orient_mask)
        
        elif config['filter_type'] == 'remove_vertical':
            # Suprimir líneas verticales largas por apertura morfológica
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 40, 100)
            vlen = int(config.get('vertical_len', 35))
            kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vlen))
            verticals = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel_vert, iterations=1)
            mask = cv2.subtract(edges, verticals)
        
        elif config['filter_type'] == 'hough_horizontal':
            # Detectar líneas horizontales con Hough y dibujarlas como máscara
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, int(config.get('canny_low', 40)), int(config.get('canny_high', 100)))
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=60,
                                    minLineLength=int(config.get('min_line_length', 60)),
                                    maxLineGap=int(config.get('max_line_gap', 15)))
            mask = np.zeros_like(gray)
            if lines is not None:
                for l in lines:
                    x1, y1, x2, y2 = l[0]
                    # Mantener casi horizontales
                    if abs(y2 - y1) <= max(2, int(0.2 * abs(x2 - x1))):
                        cv2.line(mask, (x1, y1), (x2, y2), 255, 3)
            # Expandir a regiones
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel_h, iterations=1)
        
        elif config['filter_type'] == 'gabor':
            # Filtro Gabor orientado
            theta = np.deg2rad(float(config.get('theta_deg', 90)))
            ksize = int(config.get('ksize', 31))
            sigma = float(config.get('sigma', 4.0))
            lambd = float(config.get('lambd', 10.0))
            gamma = float(config.get('gamma', 0.5))
            kernel = cv2.getGaborKernel((ksize, ksize), sigma, theta, lambd, gamma, psi=0)
            resp = cv2.filter2D(gray, cv2.CV_32F, kernel)
            resp = cv2.normalize(resp, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            # Umbral automático (Otsu)
            _, mask = cv2.threshold(resp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        elif config['filter_type'] == 'close_connect':
            # Pipeline: quitar verticales y cerrar horizontal
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, int(config.get('canny_low', 40)), int(config.get('canny_high', 100)))
            vlen = int(config.get('vertical_len', 35))
            hlen = int(config.get('horiz_len', 25))
            kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vlen))
            only_verticals = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel_vert, iterations=1)
            no_verticals = cv2.subtract(edges, only_verticals)
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (hlen, 3))
            mask = cv2.morphologyEx(no_verticals, cv2.MORPH_CLOSE, kernel_h, iterations=1)
        
        elif config['filter_type'] == 'fft_notch':
            # Suprimir banda de frecuencias verticales alrededor de kx=0 (elimina líneas verticales largas)
            g = gray.astype(np.float32)
            f = np.fft.fft2(g)
            fshift = np.fft.fftshift(f)
            h_img, w_img = g.shape
            notch_w = int(config.get('notch_width', 8))
            mask_fft = np.ones((h_img, w_img), dtype=np.float32)
            cx = w_img // 2
            mask_fft[:, cx - notch_w: cx + notch_w] = 0.0
            f_filtered = fshift * mask_fft
            img_back = np.fft.ifft2(np.fft.ifftshift(f_filtered))
            img_back = np.abs(img_back)
            img_back = cv2.normalize(img_back, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            # Realzar horizontales tras notch
            blurred = cv2.GaussianBlur(img_back, (5, 5), 0)
            mask = cv2.Canny(blurred, 40, 100)
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel_h, iterations=1)
        
        elif config['filter_type'] == 'hough_rect_assembly':
            # Ensamblar rectángulos a partir de pares de líneas horizontales
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, int(config.get('canny_low', 40)), int(config.get('canny_high', 100)))
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=60,
                                    minLineLength=int(config.get('min_line_length', 40)),
                                    maxLineGap=int(config.get('max_line_gap', 20)))
            horizontals = []
            if lines is not None:
                for l in lines:
                    x1, y1, x2, y2 = l[0]
                    if abs(y2 - y1) <= max(2, int(0.2 * abs(x2 - x1))):
                        x_left, x_right = min(x1, x2), max(x1, x2)
                        horizontals.append((y1, x_left, x_right))
            mask = np.zeros_like(gray)
            best_pair = None
            best_span = 0
            max_gap = int(config.get('max_y_gap_between_horizontals', 80))
            for i in range(len(horizontals)):
                yA, xL_A, xR_A = horizontals[i]
                for j in range(i+1, len(horizontals)):
                    yB, xL_B, xR_B = horizontals[j]
                    dy = abs(yB - yA)
                    if 5 <= dy <= max_gap:
                        xL = max(min(xL_A, xR_A), min(xL_B, xR_B))
                        xR = min(max(xL_A, xR_A), max(xL_B, xR_B))
                        span = max(0, xR - xL)
                        if span > best_span and span > 20:
                            best_span = span
                            best_pair = (min(yA, yB), max(yA, yB), xL, xR)
            if best_pair is not None:
                y_top, y_bot, xL, xR = best_pair
                # Dibujar rectángulo lleno como máscara
                cv2.rectangle(mask, (xL, y_top), (xR, y_bot), 255, -1)
            else:
                mask = edges
        
        elif config['filter_type'] == 'clahe_canny':
            # Mejora de contraste local + Canny
            clip = float(config.get('clip_limit', 3.0))
            tiles = int(config.get('tile_grid', 8))
            clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles))
            gray_eq = clahe.apply(gray)
            mask = cv2.Canny(gray_eq, int(config.get('canny_low', 50)), int(config.get('canny_high', 120)))
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel_h, iterations=1)
        
        elif config['filter_type'] == 'mser':
            # Regiones MSER sobre una imagen realzada con TopHat horizontal
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
            th = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel_h)
            try:
                mser = cv2.MSER_create(_delta=int(config.get('delta', 5)),
                                       _min_area=int(config.get('min_area', 60)),
                                       _max_area=int(config.get('max_area', 10000)))
                regions, bboxes = mser.detectRegions(th)
                mask = np.zeros_like(gray)
                for (x, y, w, h) in bboxes:
                    if w > 10 and h > 8:  # descartar demasiado pequeños
                        cv2.rectangle(mask, (x, y), (x+w, y+h), 255, -1)
            except Exception as e:
                # Fallback si MSER no está disponible en la build
                mask = th
        
        elif config['filter_type'] == 'row_projection':
            # Proyección de bordes por filas para ubicar bandas horizontales
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, int(config.get('canny_low', 40)), int(config.get('canny_high', 100)))
            # Eliminar verticales
            vlen = int(config.get('vertical_len', 35))
            kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vlen))
            only_verticals = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel_vert, iterations=1)
            edges_nv = cv2.subtract(edges, only_verticals)
            # Proyección por filas
            row_sum = edges_nv.sum(axis=1).astype(np.float32)
            if row_sum.max() > 0:
                row_sum_norm = row_sum / (row_sum.max() + 1e-6)
            else:
                row_sum_norm = row_sum
            thr = float(config.get('prominence', 0.15))
            rows_sel = (row_sum_norm >= thr).astype(np.uint8)
            # Construir máscara por bandas
            mask = np.zeros_like(gray)
            h_img, w_img = gray.shape
            mask[rows_sel.astype(bool), :] = 255
            # Espesar verticalmente para formar regiones
            band_th = max(3, int(config.get('min_band_thickness', 8)))
            kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (3, band_th))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_v, iterations=1)
            # Suavizar horizontalmente
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 1))
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel_h, iterations=1)
        
        else:
            # Fallback a threshold simple
            _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        # Post-proceso genérico: cerrar regiones para tener contornos rellenados
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask_for_contours = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close, iterations=1)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(mask_for_contours, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Inicializar colecciones por configuración
        rectangulos_encontrados = []
        tubos = []
        tapas = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # Clasificar rectángulos
            if aspect_ratio > 1.5:  # TUBO horizontal
                tipo = "TUBO"
                tubos.append((contour, x, y, w, h, aspect_ratio))
            elif aspect_ratio < 0.8:  # TAPA vertical
                tipo = "TAPA"
                tapas.append((contour, x, y, w, h, aspect_ratio))
            else:
                tipo = "CUADRADO"
            
            if config['area_min'] <= area <= config['area_max']:
                rectangulos_encontrados.append({
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'aspect_ratio': aspect_ratio,
                    'tipo': tipo,
                    'center_y': y + h // 2
                })
        
        print(f"  Contornos totales: {len(contours)}")
        print(f"  Rectángulos válidos: {len(rectangulos_encontrados)}")
        print(f"  TUBOS (horizontales): {len(tubos)}")
        print(f"  TAPAS (verticales): {len(tapas)}")
        
        # Crear imagen resultado con clasificación por colores
        result_img = image.copy()
        
        # Dibujar según tipo
        for rect in rectangulos_encontrados:
            contour = rect['contour']
            x, y, w, h = rect['bbox']
            tipo = rect['tipo']
            
            if tipo == "TUBO":
                color = (0, 255, 0)  # Verde para tubos
                cv2.drawContours(result_img, [contour], -1, color, 2)
                cv2.putText(result_img, "TUBO", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            elif tipo == "TAPA":
                color = (255, 0, 0)  # Azul para tapas
                cv2.drawContours(result_img, [contour], -1, color, 2)
                cv2.putText(result_img, "TAPA", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            else:
                color = (0, 255, 255)  # Amarillo para cuadrados
                cv2.drawContours(result_img, [contour], -1, color, 1)
        
        # Si hay tubos, usar el más centrado como resultado
        if tubos:
            h_img = image.shape[0]
            img_center_y = h_img // 2
            
            mejor_tubo = min(tubos, key=lambda t: abs((t[2] + t[4]//2) - img_center_y))
            _, x, y, w, h, aspect_ratio = mejor_tubo
            center_y = y + h // 2
            
            cv2.rectangle(result_img, (x, y), (x+w, y+h), (0, 0, 255), 3)
            cv2.circle(result_img, (x + w//2, center_y), 8, (0, 0, 255), -1)
            
            results.append({
                'config': config['name'],
                'center_y': center_y,
                'area': w * h,
                'bbox': (x, y, w, h),
                'tipo': 'TUBO'
            })
            
            print(f"  ¡TUBO DETECTADO! Y={center_y}, Aspect={aspect_ratio:.1f}")
        elif rectangulos_encontrados:
            mejor = max(rectangulos_encontrados, key=lambda r: r['area'])
            x, y, w, h = mejor['bbox']
            center_y = mejor['center_y']
            
            results.append({
                'config': config['name'],
                'center_y': center_y,
                'area': mejor['area'],
                'bbox': (x, y, w, h),
                'tipo': mejor['tipo']
            })
            print(f"  Mejor candidato ({mejor['tipo']}): Y={center_y}, Área={mejor['area']:.0f}")
        else:
            print(f"  No se encontraron candidatos válidos")
        
        # Mostrar resultado
        cv2.imshow(f"Config {i+1}: {config['name']} - Presiona tecla para siguiente", result_img)
        cv2.waitKey(0)
    
    cv2.destroyAllWindows()
    
    # Resumen de resultados
    print(f"\n=== RESUMEN DE RESULTADOS ===")
    if results:
        print("Configuraciones que detectaron tubos:")
        for result in results:
            print(f"  {result['config']}: Y={result['center_y']}, Área={result['area']:.0f}")
    else:
        print("Ninguna configuración detectó tubos válidos")
        print("Considera ajustar los parámetros o verificar la iluminación")

def menu_principal():
    """Menú principal para los tests"""
    while True:
        print("\n" + "="*50)
        print("SISTEMA DE TEST DE DETECCIÓN DE TUBOS")
        print("="*50)
        print("1. Test conexión de cámara")
        print("2. Test captura de imagen")
        print("3. Test detección simple")
        print("4. Test detección con debug")
        print("5. Ajuste interactivo de parámetros")
        print("6. Test completo (todo lo anterior)")
        print("0. Salir")
        print("="*50)
        
        try:
            opcion = input("Selecciona una opción: ").strip()
            
            if opcion == '0':
                print("Saliendo...")
                break
            elif opcion == '1':
                test_camera_connection()
            elif opcion == '2':
                test_image_capture()
            elif opcion == '3':
                test_detection_simple()
            elif opcion == '4':
                test_detection_debug()
            elif opcion == '5':
                interactive_parameter_tuning()
            elif opcion == '6':
                print("Ejecutando test completo...")
                if test_camera_connection():
                    if test_image_capture():
                        test_detection_simple()
                        test_detection_debug()
                        interactive_parameter_tuning()
            else:
                print("Opción inválida")
                
        except KeyboardInterrupt:
            print("\nInterrumpido por el usuario")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("=== TEST DE DETECCIÓN DE TUBOS VERTICALES ===")
    menu_principal()
