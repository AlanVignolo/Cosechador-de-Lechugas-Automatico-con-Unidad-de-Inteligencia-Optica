"""
Detector de Tubos Vertical - Sistema de detección específico para tubos blancos opacos
Versión con debug visual paso a paso para ajustar filtros y parámetros
"""

import cv2
import numpy as np
import json
import matplotlib.pyplot as plt
import threading
import time
import os
import sys
from typing import List, Tuple, Optional, Dict, Any

# Importar el gestor de cámara centralizado
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

# Cache global para recordar qué cámara funciona
_working_camera_cache = None

def capture_new_image(camera_index=0):
    """Alias para capture_image_for_tube_detection - mantiene compatibilidad"""
    return capture_image_for_tube_detection(camera_index)

def scan_available_cameras():
    """Escanea cámaras disponibles en el sistema"""
    available_cameras = []
    
    print("Escaneando cámaras disponibles...")
    
    # Probar diferentes índices
    for i in range(10):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    available_cameras.append({
                        'index': i,
                        'resolution': f"{w}x{h}",
                        'working': True
                    })
                    print(f"Cámara {i}: {w}x{h} - FUNCIONAL")
                else:
                    available_cameras.append({
                        'index': i,
                        'resolution': "Error al capturar",
                        'working': False
                    })
                    print(f"Cámara {i}: Abierta pero no captura")
                cap.release()
        except Exception as e:
            continue
    
    if not available_cameras:
        print("No se encontraron cámaras funcionales")
    
    return available_cameras

def capture_with_timeout(camera_index, timeout=5.0):
    """Captura frame usando el gestor centralizado de cámara"""
    camera_mgr = get_camera_manager()
    
    # Adquirir uso temporal de cámara para captura puntual
    if not camera_mgr.acquire("tube_detector_vertical"):
        print(f"Error: No se pudo adquirir cámara {camera_index}")
        return None
    try:
        # Capturar frame (sin iniciar stream)
        frame = camera_mgr.capture_frame(timeout=timeout, max_retries=3)
        if frame is not None:
            print(f"Frame capturado exitosamente")
        else:
            print(f"Error: No se pudo capturar frame")
        return frame
    finally:
        camera_mgr.release("tube_detector_vertical")

def capture_image_for_tube_detection(camera_index=0, max_retries=1):
    """Captura una imagen para detección de tubos usando el gestor centralizado"""
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        # ROTAR 90° - La cámara está a 90° igual que en el detector horizontal
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        return frame_recortado
    
    return None

def detect_tube_lines_debug(image, debug=True):
    """
    Detectar líneas horizontales de tubo con debug paso a paso
    Enfoque: detectar las líneas horizontales características del tubo opaco
    """
    
    if image is None:
        return []
    
    if debug:
        print("\n=== DETECTOR DE TUBOS VERTICALES ===")
        print("Objetivo: Detectar líneas horizontales del tubo opaco")
        print("Características: Tubo blanco opaco con tapas brillantes")
    
    h_img, w_img = image.shape[:2]
    img_center_y = h_img // 2
    
    # PASO 1: Preparar diferentes versiones de la imagen para análisis
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Canales individuales
    h_channel = hsv[:,:,0]  # Matiz
    s_channel = hsv[:,:,1]  # Saturación  
    v_channel = hsv[:,:,2]  # Brillo
    
    if debug:
        print(f"Imagen: {w_img}x{h_img}")
        print("Preparando filtros para detección de tubos blancos...")
        
        # Mostrar imagen original y canales
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('PASO 1: Análisis de Imagen Original', fontsize=14)
        
        axes[0,0].imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        axes[0,0].set_title('Original')
        axes[0,0].axis('off')
        
        axes[0,1].imshow(gray, cmap='gray')
        axes[0,1].set_title('Escala de Grises')
        axes[0,1].axis('off')
        
        axes[0,2].imshow(hsv)
        axes[0,2].set_title('HSV')
        axes[0,2].axis('off')
        
        axes[1,0].imshow(h_channel, cmap='hsv')
        axes[1,0].set_title('Canal H (Matiz)')
        axes[1,0].axis('off')
        
        axes[1,1].imshow(s_channel, cmap='gray')
        axes[1,1].set_title('Canal S (Saturación)')
        axes[1,1].axis('off')
        
        axes[1,2].imshow(v_channel, cmap='gray')
        axes[1,2].set_title('Canal V (Brillo)')
        axes[1,2].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    # PASO 2: DETECCIÓN DE BORDES + SOMBRAS/RELIEVES
    filters = {}
    
    # MÉTODO 1: DETECCIÓN DE BORDES CON CANNY
    # Suavizado previo para reducir ruido
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Canny con diferentes umbrales
    filters['canny_suave'] = cv2.Canny(blurred, 30, 80)
    filters['canny_medio'] = cv2.Canny(blurred, 50, 120) 
    filters['canny_fuerte'] = cv2.Canny(blurred, 80, 160)
    
    # MÉTODO 2: DETECCIÓN DE SOMBRAS Y RELIEVES
    # Kernel para operaciones morfológicas (forma del tubo esperado)
    kernel_horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))  # Para tubo horizontal
    kernel_vertical = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 15))    # Para tapa vertical
    kernel_circular = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))  # General
    
    # Top-hat: Resalta objetos más claros que el fondo (relieves)
    filters['tophat_horizontal'] = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel_horizontal)
    filters['tophat_vertical'] = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel_vertical)
    
    # Bottom-hat: Resalta objetos más oscuros que el fondo (sombras)
    filters['bottomhat_horizontal'] = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel_horizontal)
    filters['bottomhat_vertical'] = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel_vertical)
    
    # MÉTODO 3: COMBINACIÓN BORDES + RELIEVES
    # Combinar Canny con top-hat para mejorar detección
    tophat_combined = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel_circular)
    tophat_enhanced = cv2.addWeighted(gray, 0.7, tophat_combined, 0.3, 0)
    filters['canny_tophat'] = cv2.Canny(tophat_enhanced, 40, 100)
    
    # MÉTODO 4: TEMPLATE MATCHING
    # Crear plantillas simples del tubo y tapa
    tubo_template = np.ones((20, 60), dtype=np.uint8) * 255  # Rectángulo horizontal
    tubo_template = cv2.rectangle(tubo_template, (5, 5), (55, 15), 0, 2)  # Borde del tubo
    
    tapa_template = np.ones((40, 25), dtype=np.uint8) * 255  # Rectángulo vertical
    tapa_template = cv2.rectangle(tapa_template, (5, 5), (20, 35), 0, 2)  # Borde de la tapa
    
    # Template matching
    tubo_match = cv2.matchTemplate(gray, tubo_template, cv2.TM_CCOEFF_NORMED)
    tapa_match = cv2.matchTemplate(gray, tapa_template, cv2.TM_CCOEFF_NORMED)
    
    # Threshold para matches
    _, filters['template_tubo'] = cv2.threshold((tubo_match * 255).astype(np.uint8), 100, 255, cv2.THRESH_BINARY)
    _, filters['template_tapa'] = cv2.threshold((tapa_match * 255).astype(np.uint8), 80, 255, cv2.THRESH_BINARY)
    
    # MÉTODO 5: ANÁLISIS DE TEXTURAS (LBP)
    def get_lbp_simple(image, radius=1):
        """LBP simplificado para detectar texturas"""
        rows, cols = image.shape
        lbp = np.zeros_like(image)
        
        for i in range(radius, rows - radius):
            for j in range(radius, cols - radius):
                center = image[i, j]
                code = 0
                code |= (image[i-1, j-1] >= center) << 7
                code |= (image[i-1, j] >= center) << 6
                code |= (image[i-1, j+1] >= center) << 5
                code |= (image[i, j+1] >= center) << 4
                code |= (image[i+1, j+1] >= center) << 3
                code |= (image[i+1, j] >= center) << 2
                code |= (image[i+1, j-1] >= center) << 1
                code |= (image[i, j-1] >= center) << 0
                lbp[i, j] = code
        return lbp
    
    lbp = get_lbp_simple(gray)
    # Buscar texturas uniformes (tubo liso vs madera texturada)
    _, filters['textura_lbp'] = cv2.threshold(lbp, 50, 255, cv2.THRESH_BINARY)
    
    # MÉTODO 6: FILTRADO DIRECCIONAL ESPECÍFICO
    # Kernel para detectar solo líneas horizontales (suprimir verticales)
    kernel_horizontal_only = np.array([[-1, -1, -1],
                                     [ 2,  2,  2],
                                     [-1, -1, -1]], dtype=np.float32)
    
    horizontal_response = cv2.filter2D(gray, -1, kernel_horizontal_only)
    horizontal_response = np.clip(horizontal_response, 0, 255).astype(np.uint8)
    _, filters['solo_horizontales'] = cv2.threshold(horizontal_response, 50, 255, cv2.THRESH_BINARY)
    
    # MÉTODO 7: ANÁLISIS POR REGIONES (ROI)
    # Dividir imagen en 3 zonas y analizar centro (evitar bordes con madera)
    h_img, w_img = gray.shape
    zona_central = gray[h_img//4:3*h_img//4, w_img//4:3*w_img//4]  # Solo centro
    
    # Aplicar Canny solo en zona central
    zona_central_blur = cv2.GaussianBlur(zona_central, (5, 5), 0)
    zona_central_canny = cv2.Canny(zona_central_blur, 40, 100)
    
    # Expandir resultado a imagen completa
    filters['roi_central'] = np.zeros_like(gray)
    filters['roi_central'][h_img//4:3*h_img//4, w_img//4:3*w_img//4] = zona_central_canny
    
    # MÉTODO 8: COMBINACIÓN MULTICANAL
    # Aprovechar diferencias sutiles en R, G, B
    b, g, r = cv2.split(image)
    
    # Diferencia entre canales para resaltar objetos
    diff_rg = cv2.absdiff(r, g)
    diff_rb = cv2.absdiff(r, b)
    diff_gb = cv2.absdiff(g, b)
    
    # Combinar diferencias
    multi_diff = cv2.addWeighted(diff_rg, 0.33, diff_rb, 0.33, 0)
    multi_diff = cv2.addWeighted(multi_diff, 1.0, diff_gb, 0.34, 0)
    
    _, filters['multicanal_diff'] = cv2.threshold(multi_diff, 15, 255, cv2.THRESH_BINARY)
    
    if debug:
        print("PASO 2: Aplicando MÚLTIPLES ENFOQUES de detección")
        print(f"Total de filtros: {len(filters)}")
        
        # Ventana 1: Template Matching y Direccional
        template_filters = {k: v for k, v in filters.items() if 'template' in k or 'horizontales' in k}
        if template_filters:
            fig1, axes1 = plt.subplots(1, len(template_filters), figsize=(12, 4))
            fig1.suptitle('TEMPLATE MATCHING Y FILTRADO DIRECCIONAL', fontsize=14)
            if len(template_filters) == 1:
                axes1 = [axes1]
            for i, (name, filtered) in enumerate(template_filters.items()):
                axes1[i].imshow(filtered, cmap='gray')
                axes1[i].set_title(f'{name}')
                axes1[i].axis('off')
            plt.tight_layout()
            plt.show()
        
        # Ventana 2: Análisis de Texturas y ROI
        texture_filters = {k: v for k, v in filters.items() if 'textura' in k or 'roi' in k or 'multicanal' in k}
        if texture_filters:
            fig2, axes2 = plt.subplots(1, len(texture_filters), figsize=(12, 4))
            fig2.suptitle('TEXTURAS, ROI Y MULTICANAL', fontsize=14)
            if len(texture_filters) == 1:
                axes2 = [axes2]
            for i, (name, filtered) in enumerate(texture_filters.items()):
                axes2[i].imshow(filtered, cmap='gray')
                axes2[i].set_title(f'{name}')
                axes2[i].axis('off')
            plt.tight_layout()
            plt.show()
        
        # Ventana 3: Métodos anteriores (bordes, sombras)
        previous_filters = {k: v for k, v in filters.items() if 'canny' in k or 'hat' in k}
        if previous_filters:
            n_filters = len(previous_filters)
            cols = min(4, n_filters)
            rows = (n_filters + cols - 1) // cols
            
            fig3, axes3 = plt.subplots(rows, cols, figsize=(15, 4*rows))
            fig3.suptitle('MÉTODOS ANTERIORES - Bordes y Sombras/Relieves', fontsize=14)
            
            if rows == 1:
                axes3 = [axes3] if cols == 1 else axes3
            else:
                axes3 = axes3.flatten()
            
            for i, (name, filtered) in enumerate(previous_filters.items()):
                axes3[i].imshow(filtered, cmap='gray')
                axes3[i].set_title(f'{name}')
                axes3[i].axis('off')
            
            # Ocultar ejes no usados
            for i in range(len(previous_filters), rows * cols):
                axes3[i].axis('off')
            
            plt.tight_layout()
            plt.show()
    
    # PASO 3: Buscar rectángulos específicos - TUBO (horizontal) y TAPA (vertical)
    candidates = []
    
    for filter_name, binary_img in filters.items():
        if debug:
            pixels_blancos = cv2.countNonZero(binary_img)
            print(f"\n{filter_name}: {pixels_blancos} píxeles blancos")
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            if debug:
                print(f"  No se encontraron contornos en {filter_name}")
            continue
        
        # NUEVA LÓGICA: Buscar rectángulos específicos
        rectangulos_encontrados = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:  # Filtrar contornos muy pequeños
                continue
            
            # Obtener rectángulo delimitador
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # CLASIFICAR TIPO DE RECTÁNGULO
            tipo_rectangulo = None
            score = 0
            characteristics = []
            
            # SCORING PARA FILTROS DE BORDES Y RELIEVES
            center_y = y + h // 2
            center_distance = abs(center_y - img_center_y)
            
            # TUBO: Rectángulo horizontal (w > h)
            if aspect_ratio > 1.5:  # Claramente horizontal
                tipo_rectangulo = "TUBO_HORIZONTAL"
                score += 30  # Bonus alto para tubos
                characteristics.append(f"tubo_horizontal({aspect_ratio:.1f})")
                
                # Bonus si está centrado
                if center_distance < h_img * 0.3:
                    score += 25
                    characteristics.append("muy_centrado")
                elif center_distance < h_img * 0.5:
                    score += 15
                    characteristics.append("centrado")
                
                # Tamaño apropiado para tubo
                if 30 < w < 400 and 10 < h < 120:
                    score += 20
                    characteristics.append("tamaño_tubo_ok")
                    
            # TAPA: Rectángulo vertical (h > w)  
            elif aspect_ratio < 0.7:  # Claramente vertical
                tipo_rectangulo = "TAPA_VERTICAL"
                score += 25
                characteristics.append(f"tapa_vertical({aspect_ratio:.1f})")
                
                # Tamaño apropiado para tapa
                if 15 < w < 100 and 30 < h < 150:
                    score += 15
                    characteristics.append("tamaño_tapa_ok")
                    
                # Posición apropiada para tapa
                if center_y < h_img * 0.8:  # No muy abajo
                    score += 10
                    characteristics.append("posición_tapa_ok")
            
            # CUADRADO: Puede ser parte del tubo o tapa
            elif 0.7 <= aspect_ratio <= 1.4:
                tipo_rectangulo = "CUADRADO"
                score += 15
                characteristics.append(f"cuadrado({aspect_ratio:.1f})")
                
                # Si está centrado, puede ser tubo visto de frente
                if center_distance < h_img * 0.3:
                    score += 10
                    characteristics.append("cuadrado_centrado")
            
            # BONUS POR TIPO DE FILTRO
            # Filtros de bordes son muy buenos para formas definidas
            if 'canny' in filter_name:
                score += 15
                characteristics.append("filtro_bordes")
                
                # Bonus extra para Canny medio (balance ruido/detección)
                if 'medio' in filter_name:
                    score += 5
                    characteristics.append("canny_optimo")
                    
            # Filtros de relieves detectan elevaciones (tubos)
            elif 'tophat' in filter_name:
                score += 12
                characteristics.append("filtro_relieve")
                
                # Bonus para orientación correcta
                if ('horizontal' in filter_name and tipo_rectangulo == "TUBO_HORIZONTAL") or \
                   ('vertical' in filter_name and tipo_rectangulo == "TAPA_VERTICAL"):
                    score += 8
                    characteristics.append("orientación_correcta")
                    
            # Filtros de sombras detectan depresiones
            elif 'bottomhat' in filter_name:
                score += 8
                characteristics.append("filtro_sombras")
                
            # Gradientes detectan cambios sutiles
            elif 'gradientes' in filter_name:
                score += 10
                characteristics.append("filtro_gradientes")
            
            # Penalizar contornos muy pequeños (ruido) en filtros de bordes
            if ('canny' in filter_name or 'gradientes' in filter_name) and area < 200:
                score -= 10
                characteristics.append("posible_ruido")
            
            # Solo considerar candidatos con score mínimo
            if score > 15:
                rectangulos_encontrados.append({
                    'filter': filter_name,
                    'tipo': tipo_rectangulo,
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'aspect_ratio': aspect_ratio,
                    'center_y': y + h // 2,
                    'score': score,
                    'characteristics': characteristics
                })
        
        # Agregar a candidatos globales
        candidates.extend(rectangulos_encontrados)
        
        if debug:
            print(f"  {len(contours)} contornos totales")
            for rect in rectangulos_encontrados:
                print(f"    {rect['tipo']}: score={rect['score']}, {rect['characteristics']}")
        
        # PASO 3.5: Buscar combinaciones TUBO + TAPA
        tubos = [r for r in rectangulos_encontrados if r['tipo'] == 'TUBO_HORIZONTAL']
        tapas = [r for r in rectangulos_encontrados if r['tipo'] == 'TAPA_VERTICAL']
        
        if tubos and tapas and debug:
            print(f"  ¡COMBINACIÓN DETECTADA! {len(tubos)} tubos + {len(tapas)} tapas")
            
            # Buscar tapa cerca de tubo
            for tubo in tubos:
                tx, ty, tw, th = tubo['bbox']
                tubo_center_y = ty + th // 2
                
                for tapa in tapas:
                    px, py, pw, ph = tapa['bbox']
                    tapa_center_y = py + ph // 2
                    
                    distancia_y = abs(tubo_center_y - tapa_center_y)
                    if distancia_y < 50:  # Tapa cerca del tubo
                        # Bonus especial para combinación
                        tubo['score'] += 30
                        tapa['score'] += 25
                        tubo['characteristics'].append("con_tapa_cercana")
                        tapa['characteristics'].append("cerca_de_tubo")
                        
                        if debug:
                            print(f"    Tapa a {distancia_y}px del tubo - ¡BONUS!")
    
    if debug:
        print(f"\nPASO 3: {len(candidates)} candidatos rectangulares encontrados")
    
    # PASO 4: Mostrar mejores candidatos
    if debug and candidates:
        print(f"\nPASO 3: Encontrados {len(candidates)} candidatos")
        
        # Ordenar por score
        candidates.sort(key=lambda c: c['score'], reverse=True)
        
        # Mostrar top 6 candidatos
        top_candidates = candidates[:6]
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('PASO 3: Mejores Candidatos de Tubos', fontsize=14)
        
        for i, candidate in enumerate(top_candidates):
            if i < 6:
                row, col = divmod(i, 3)
                
                # Crear imagen del candidato
                x, y, w, h = candidate['bbox']
                candidate_img = image.copy()
                cv2.rectangle(candidate_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.circle(candidate_img, (x + w//2, candidate['center_y']), 5, (255, 0, 0), -1)
                
                axes[row, col].imshow(cv2.cvtColor(candidate_img, cv2.COLOR_BGR2RGB))
                axes[row, col].set_title(f"#{i+1}: {candidate['filter']}\nScore: {candidate['score']}")
                axes[row, col].axis('off')
        
        # Ocultar ejes no usados
        for i in range(len(top_candidates), 6):
            row, col = divmod(i, 3)
            axes[row, col].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    if debug:
        print(f"\nRESULTADO: {len(candidates)} candidatos encontrados")
        if candidates:
            best = candidates[0]
            print(f"Mejor candidato: filtro='{best['filter']}', score={best['score']}, centro_y={best['center_y']}")
    
    return candidates

def detect_tube_position(image, debug=False):
    """
    Función principal para detectar posición Y del tubo
    Retorna la coordenada Y del centro del tubo detectado
    """
    candidates = detect_tube_lines_debug(image, debug=debug)
    
    if candidates:
        # Retornar la coordenada Y del mejor candidato
        best_candidate = candidates[0]
        return best_candidate['center_y']
    
    return None

def test_tube_detection():
    """Función de test para calibrar la detección de tubos"""
    print("=== TEST DE DETECCIÓN DE TUBOS ===")
    print("Capturando imagen para análisis...")
    
    # Capturar imagen
    image = capture_image_for_tube_detection(camera_index=0)
    
    if image is None:
        print("Error: No se pudo capturar imagen")
        return
    
    print("Imagen capturada. Analizando con debug habilitado...")
    
    # Ejecutar detección con debug completo
    result = detect_tube_position(image, debug=True)
    
    if result is not None:
        print(f"\nTUBO DETECTADO en Y = {result} píxeles")
    else:
        print("\nNo se detectó ningún tubo")
    
    print("\nTest completado. Revisa las imágenes mostradas para ajustar parámetros.")

if __name__ == "__main__":
    print("=== DETECTOR DE TUBOS VERTICAL ===")
    print("Ejecuta test_tube_detection() para probar la detección")
    
    # Permitir ejecución directa del test
    test_tube_detection()
