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
    
    # PASO 2: ENFOQUE EN CANAL S (SATURACIÓN) - Donde se distingue mejor el tubo
    filters = {}

    if debug:
        print("\n=== ANÁLISIS DE SATURACIÓN (Canal S) ===")
        print("El tubo blanco tiene BAJA saturación")
        print("El fondo madera tiene MAYOR saturación")

    # MÉTODO 1: UMBRALIZACIÓN ADAPTIVA EN CANAL S
    # El tubo blanco opaco tiene saturación MUY BAJA (casi 0)
    # La madera tiene saturación más alta

    # Invertir canal S para que objetos blancos/grises tengan valores altos
    s_invertido = 255 - s_channel

    # Diferentes umbrales en canal S
    _, filters['s_baja_sat_1'] = cv2.threshold(s_invertido, 180, 255, cv2.THRESH_BINARY)  # Muy estricto
    _, filters['s_baja_sat_2'] = cv2.threshold(s_invertido, 160, 255, cv2.THRESH_BINARY)  # Medio
    _, filters['s_baja_sat_3'] = cv2.threshold(s_invertido, 140, 255, cv2.THRESH_BINARY)  # Permisivo

    # Umbralización adaptativa en canal S
    filters['s_adaptativo'] = cv2.adaptiveThreshold(s_invertido, 255,
                                                     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                     cv2.THRESH_BINARY, 21, -5)

    # MÉTODO 2: COMBINACIÓN S + V (Saturación + Brillo)
    # Tubo blanco: Baja saturación + Alto brillo
    mask_bajo_s = s_channel < 40  # Saturación muy baja
    mask_alto_v = v_channel > 150  # Brillo alto
    filters['s_bajo_v_alto'] = ((mask_bajo_s & mask_alto_v) * 255).astype(np.uint8)

    # MÉTODO 3: DIFERENCIA ENTRE CANAL S Y V
    # En objetos blancos: V alto, S bajo → diferencia grande
    diff_v_s = cv2.absdiff(v_channel, s_channel)
    _, filters['diff_v_menos_s'] = cv2.threshold(diff_v_s, 100, 255, cv2.THRESH_BINARY)

    # MÉTODO 4: ANÁLISIS ESTADÍSTICO LOCAL EN CANAL S
    # Buscar regiones uniformemente blancas (varianza baja en S)
    s_blur = cv2.GaussianBlur(s_channel, (15, 15), 0)
    s_variance = cv2.absdiff(s_channel, s_blur)
    # Invertir: donde hay poca varianza (tubo uniforme) → blanco
    s_variance_inv = 255 - s_variance
    _, filters['s_uniforme'] = cv2.threshold(s_variance_inv, 200, 255, cv2.THRESH_BINARY)

    # MÉTODO 5: DETECCIÓN DE BORDES EN CANAL S
    # Los bordes del tubo son más visibles en canal S
    s_blurred = cv2.GaussianBlur(s_channel, (5, 5), 0)
    filters['s_canny_suave'] = cv2.Canny(s_blurred, 20, 60)
    filters['s_canny_medio'] = cv2.Canny(s_blurred, 30, 80)

    # MÉTODO 6: MORFOLOGÍA EN CANAL S
    # Cerrar gaps en regiones de baja saturación
    kernel_rect = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    s_morph = cv2.morphologyEx(filters['s_baja_sat_2'], cv2.MORPH_CLOSE, kernel_rect)
    filters['s_morfologia'] = s_morph

    # MÉTODO 7: GRADIENTES EN CANAL S
    # Detectar bordes usando Sobel en canal S
    s_sobelx = cv2.Sobel(s_channel, cv2.CV_64F, 1, 0, ksize=3)
    s_sobely = cv2.Sobel(s_channel, cv2.CV_64F, 0, 1, ksize=3)
    s_sobel_mag = np.sqrt(s_sobelx**2 + s_sobely**2)
    s_sobel_mag = np.clip(s_sobel_mag, 0, 255).astype(np.uint8)
    _, filters['s_gradientes'] = cv2.threshold(s_sobel_mag, 20, 255, cv2.THRESH_BINARY)

    # MÉTODO 8: OPERACIONES MORFOLÓGICAS AVANZADAS
    # Opening: Elimina ruido pequeño, mantiene estructuras grandes
    kernel_opening = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    s_opening = cv2.morphologyEx(filters['s_baja_sat_2'], cv2.MORPH_OPEN, kernel_opening)

    # Luego closing: Cierra gaps internos
    kernel_closing = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 7))
    s_opening_closing = cv2.morphologyEx(s_opening, cv2.MORPH_CLOSE, kernel_closing)
    filters['s_open_close'] = s_opening_closing

    # MÉTODO 9: COMBINACIÓN S + GRADIENTES
    # Zonas de baja saturación + bordes detectados
    s_mask = filters['s_baja_sat_2']
    s_edges = filters['s_canny_medio']
    # Dilatar bordes para capturar región interna
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    s_edges_dilated = cv2.dilate(s_edges, kernel_dilate, iterations=2)
    # Combinar: regiones de baja saturación dentro de bordes detectados
    filters['s_mask_edges'] = cv2.bitwise_and(s_mask, s_edges_dilated)

    # MÉTODO 10: ANÁLISIS DE REGIONES CONECTADAS EN CANAL S
    # Encontrar componentes conexas en máscara de baja saturación
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(filters['s_baja_sat_2'], connectivity=8)

    # Filtrar por área y aspecto (buscar tubo horizontal)
    tubo_mask = np.zeros_like(filters['s_baja_sat_2'])
    for i in range(1, num_labels):  # Ignorar fondo (label 0)
        area = stats[i, cv2.CC_STAT_AREA]
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]

        # Filtros para tubo: área razonable, aspecto horizontal
        if area > 500 and w > h * 1.2:  # Horizontal
            tubo_mask[labels == i] = 255

    filters['s_componentes'] = tubo_mask
    
    if debug:
        print("PASO 2: Aplicando filtros basados en CANAL S (Saturación)")
        print(f"Total de filtros: {len(filters)}")

        # Ventana 1: Umbrales en Canal S
        threshold_filters = {k: v for k, v in filters.items() if 's_baja_sat' in k or 's_adaptativo' in k}
        if threshold_filters:
            n = len(threshold_filters)
            fig1, axes1 = plt.subplots(1, n, figsize=(5*n, 5))
            fig1.suptitle('FILTRO 1: Umbrales en Canal S (Baja Saturación = Blanco)', fontsize=14)
            if n == 1:
                axes1 = [axes1]
            for i, (name, filtered) in enumerate(threshold_filters.items()):
                axes1[i].imshow(filtered, cmap='gray')
                axes1[i].set_title(f'{name}\nPíxeles: {cv2.countNonZero(filtered)}')
                axes1[i].axis('off')
            plt.tight_layout()
            plt.show()

        # Ventana 2: Combinaciones S+V
        combo_filters = {k: v for k, v in filters.items() if 'bajo_v_alto' in k or 'diff_v' in k or 'uniforme' in k}
        if combo_filters:
            n = len(combo_filters)
            fig2, axes2 = plt.subplots(1, n, figsize=(5*n, 5))
            fig2.suptitle('FILTRO 2: Combinaciones S+V y Uniformidad', fontsize=14)
            if n == 1:
                axes2 = [axes2]
            for i, (name, filtered) in enumerate(combo_filters.items()):
                axes2[i].imshow(filtered, cmap='gray')
                axes2[i].set_title(f'{name}\nPíxeles: {cv2.countNonZero(filtered)}')
                axes2[i].axis('off')
            plt.tight_layout()
            plt.show()

        # Ventana 3: Bordes en Canal S
        edge_filters = {k: v for k, v in filters.items() if 's_canny' in k or 's_gradientes' in k}
        if edge_filters:
            n = len(edge_filters)
            fig3, axes3 = plt.subplots(1, n, figsize=(5*n, 5))
            fig3.suptitle('FILTRO 3: Detección de Bordes en Canal S', fontsize=14)
            if n == 1:
                axes3 = [axes3]
            for i, (name, filtered) in enumerate(edge_filters.items()):
                axes3[i].imshow(filtered, cmap='gray')
                axes3[i].set_title(f'{name}\nPíxeles: {cv2.countNonZero(filtered)}')
                axes3[i].axis('off')
            plt.tight_layout()
            plt.show()

        # Ventana 4: Morfología
        morph_filters = {k: v for k, v in filters.items() if 'morfologia' in k or 'open_close' in k or 'mask_edges' in k}
        if morph_filters:
            n = len(morph_filters)
            fig4, axes4 = plt.subplots(1, n, figsize=(5*n, 5))
            fig4.suptitle('FILTRO 4: Operaciones Morfológicas', fontsize=14)
            if n == 1:
                axes4 = [axes4]
            for i, (name, filtered) in enumerate(morph_filters.items()):
                axes4[i].imshow(filtered, cmap='gray')
                axes4[i].set_title(f'{name}\nPíxeles: {cv2.countNonZero(filtered)}')
                axes4[i].axis('off')
            plt.tight_layout()
            plt.show()

        # Ventana 5: Componentes Conexas
        component_filters = {k: v for k, v in filters.items() if 'componentes' in k}
        if component_filters:
            n = len(component_filters)
            fig5, axes5 = plt.subplots(1, n, figsize=(5*n, 5))
            fig5.suptitle('FILTRO 5: Análisis de Componentes Conexas', fontsize=14)
            if n == 1:
                axes5 = [axes5]
            for i, (name, filtered) in enumerate(component_filters.items()):
                axes5[i].imshow(filtered, cmap='gray')
                axes5[i].set_title(f'{name}\nPíxeles: {cv2.countNonZero(filtered)}')
                axes5[i].axis('off')
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
            
            # BONUS POR TIPO DE FILTRO - Priorizar filtros basados en Canal S
            if 's_componentes' in filter_name:
                # Máxima confianza: análisis inteligente de regiones
                score += 40
                characteristics.append("filtro_componentes_s")

            elif 's_open_close' in filter_name or 's_morfologia' in filter_name:
                # Alta confianza: morfología en canal S
                score += 35
                characteristics.append("filtro_morfologia_s")

            elif 's_mask_edges' in filter_name:
                # Buena confianza: combinación de máscara + bordes
                score += 30
                characteristics.append("filtro_s_bordes_combinado")

            elif 's_bajo_v_alto' in filter_name or 'diff_v' in filter_name:
                # Buena confianza: combinaciones S+V
                score += 28
                characteristics.append("filtro_s_v_combinado")

            elif 's_baja_sat' in filter_name:
                # Confianza media-alta: umbral directo en S
                score += 25
                characteristics.append("filtro_umbral_s")

                # Bonus para umbral medio (balance)
                if '_2' in filter_name:
                    score += 5
                    characteristics.append("umbral_s_optimo")

            elif 's_adaptativo' in filter_name or 's_uniforme' in filter_name:
                # Confianza media: análisis adaptativo
                score += 22
                characteristics.append("filtro_adaptativo_s")

            elif 's_canny' in filter_name or 's_gradientes' in filter_name:
                # Confianza media: bordes en canal S
                score += 20
                characteristics.append("filtro_bordes_s")

            # Penalizar contornos muy pequeños (ruido)
            if area < 300:
                score -= 15
                characteristics.append("area_pequeña")
            
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
