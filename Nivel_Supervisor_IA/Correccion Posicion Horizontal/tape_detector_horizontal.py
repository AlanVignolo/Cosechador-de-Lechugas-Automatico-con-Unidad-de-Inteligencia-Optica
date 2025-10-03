import cv2
import numpy as np
import json
import matplotlib.pyplot as plt
import time
import os
import sys
from typing import List, Tuple, Optional, Dict, Any

# Importar el gestor de cámara centralizado
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from core.camera_manager import get_camera_manager

# Cache global para recordar qué cámara funciona
_working_camera_cache = None

def capture_new_image(camera_index=0):
    """Alias para capture_image_for_correction - mantiene compatibilidad con otros módulos"""
    return capture_image_for_correction(camera_index)

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
    if not camera_mgr.acquire("tape_detector_horizontal"):
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
        camera_mgr.release("tape_detector_horizontal")

def capture_image_for_correction(camera_index=0, max_retries=1):
    """Captura una imagen para corrección de posición horizontal usando el gestor centralizado"""
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        return frame_recortado
    
    return None

def find_tape_base_width(image, debug=True):
    """
    Nueva estrategia: encontrar la BASE de la cinta y medir su ancho real
    """
    
    if debug:
        print("\n=== DETECTOR BASADO EN ANCHO DE BASE REAL ===")
        print("Estrategia: encontrar base horizontal + medir ancho real + seguir forma curvada")
    
    h_img, w_img = image.shape[:2]
    img_center_x = w_img // 2
    
    # Aplicar el mejor filtro (según tus pruebas anteriores)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    _, binary_img = cv2.threshold(v_channel, 50, 255, cv2.THRESH_BINARY_INV)  # Filtro moderado (era 30)
    
    if debug:
        print("Usando filtro hsv_muy_oscuro (el más limpio)")
    
    # PASO 1: Encontrar la región oscura principal
    contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        if debug:
            print("No se encontraron contornos")
        return []
    
    # Contorno más grande
    main_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(main_contour)
    
    if debug:
        print(f"Región principal: {w}x{h} en ({x}, {y})")
    
    # PASO 2: BUSCAR LA BASE - analizamos las últimas filas de la región
    roi = binary_img[y:y+h, x:x+w]
    
    # Analizar últimas filas para encontrar la base sólida
    base_rows_to_check = min(20, h // 4)  # Últimas 20 filas o 25% de la altura
    base_candidates = []
    
    if debug:
        print(f"Buscando base en las últimas {base_rows_to_check} filas...")
    
    for row_offset in range(base_rows_to_check):
        row_idx = h - 1 - row_offset  # Desde abajo hacia arriba
        row = roi[row_idx, :]
        
        # Encontrar segmentos horizontales sólidos en esta fila
        white_pixels = np.where(row == 255)[0]
        
        if len(white_pixels) == 0:
            continue
        
        # Encontrar segmentos continuos
        segments = []
        start = white_pixels[0]
        end = white_pixels[0]
        
        for i in range(1, len(white_pixels)):
            if white_pixels[i] == white_pixels[i-1] + 1:
                end = white_pixels[i]
            else:
                segments.append((start, end))
                start = white_pixels[i]
                end = white_pixels[i]
        segments.append((start, end))
        
        # Evaluar cada segmento como posible base de cinta
        for seg_start, seg_end in segments:
            seg_width = seg_end - seg_start + 1
            seg_center_x = x + (seg_start + seg_end) // 2
            
            # Criterios para ser base de cinta
            if (seg_width >= 10 and  # Ancho mínimo razonable
                seg_width <= w * 0.8 and  # No más del 80% del ancho total
                seg_center_x >= w_img * 0.2 and  # No muy en el borde
                seg_center_x <= w_img * 0.8):
                
                base_candidates.append({
                    'row': row_idx,
                    'absolute_row': y + row_idx,
                    'start_x': x + seg_start,
                    'end_x': x + seg_end,
                    'width': seg_width,
                    'center_x': seg_center_x,
                    'distance_from_center': abs(seg_center_x - img_center_x)
                })
    
    if not base_candidates:
        if debug:
            print("No se encontraron candidatos a base")
        return []
    
    # Ordenar por: ancho (más ancho mejor) y cercanía al centro
    base_candidates.sort(key=lambda b: (b['width'], -b['distance_from_center']), reverse=True)
    
    if debug:
        print(f"Candidatos a base encontrados: {len(base_candidates)}")
        for i, base in enumerate(base_candidates[:3]):
            print(f"  {i+1}. Fila {base['absolute_row']}: ancho={base['width']}px, centro_x={base['center_x']}")
    
    # PASO 3: Para cada base candidata, trazar la cinta hacia arriba
    tape_candidates = []
    
    for base in base_candidates[:3]:  # Top 3 bases
        if debug:
            print(f"\nTrazando cinta desde base en fila {base['absolute_row']}")
        
        # Iniciar desde la base
        current_center_x = base['center_x']
        current_width = base['width']
        base_row = base['row']
        
        # Trazar hacia arriba, permitiendo curvatura
        top_row = None
        width_measurements = [current_width]
        center_positions = [current_center_x]
        
        for row_up in range(base_row - 1, -1, -1):  # Hacia arriba
            row = roi[row_up, :]
            
            # Buscar píxeles cerca de la posición actual (permite curvatura)
            search_radius = max(20, current_width // 2)
            search_start = max(0, int(current_center_x - x - search_radius))
            search_end = min(w, int(current_center_x - x + search_radius))
            
            search_region = row[search_start:search_end]
            white_pixels = np.where(search_region == 255)[0]
            
            if len(white_pixels) == 0:
                # No hay continuación, fin de la cinta
                break
            
            # Encontrar el segmento más cercano al centro actual
            segments = []
            if len(white_pixels) > 0:
                start = white_pixels[0]
                end = white_pixels[0]
                
                for i in range(1, len(white_pixels)):
                    if white_pixels[i] == white_pixels[i-1] + 1:
                        end = white_pixels[i]
                    else:
                        segments.append((start, end))
                        start = white_pixels[i]
                        end = white_pixels[i]
                segments.append((start, end))
            
            # Elegir segmento más cercano al centro actual
            best_segment = None
            min_distance = float('inf')
            
            for seg_start, seg_end in segments:
                abs_seg_start = search_start + seg_start
                abs_seg_end = search_start + seg_end
                seg_center = (abs_seg_start + abs_seg_end) // 2
                distance = abs((x + seg_center) - current_center_x)
                
                if distance < min_distance:
                    min_distance = distance
                    best_segment = (abs_seg_start, abs_seg_end, seg_center)
            
            if best_segment and min_distance <= search_radius:
                seg_start, seg_end, seg_center = best_segment
                new_width = seg_end - seg_start + 1
                new_center_x = x + seg_center
                
                # Actualizar para siguiente iteración (permite seguir curvatura)
                current_center_x = new_center_x
                current_width = new_width
                width_measurements.append(new_width)
                center_positions.append(new_center_x)
                top_row = row_up
            else:
                break
        
        # Calcular métricas de la cinta trazada
        if top_row is not None:
            tape_height = base_row - top_row + 1
            avg_width = np.mean(width_measurements)
            width_consistency = 1 - (np.std(width_measurements) / avg_width) if avg_width > 0 else 0
            avg_center_x = np.mean(center_positions)
            
            tape_candidates.append({
                'base_width': base['width'],
                'base_center_x': base['center_x'],
                'base_y': base['absolute_row'],
                'top_y': y + top_row,
                'height': tape_height,
                'avg_width': avg_width,
                'width_consistency': width_consistency,
                'avg_center_x': avg_center_x,
                'center_positions': center_positions,
                'width_measurements': width_measurements,
                'distance_from_center': abs(avg_center_x - img_center_x)
            })
            
            if debug:
                print(f"  Cinta trazada: altura={tape_height}, ancho_base={base['width']}, consistencia={width_consistency:.2f}")
    
    if not tape_candidates:
        if debug:
            print("No se pudieron trazar cintas válidas")
        return []
    
    # Ordenar candidatos por calidad
    for candidate in tape_candidates:
        # Score basado en: ancho de base + altura + consistencia + centrado
        score = (
            (candidate['base_width'] / 50.0) * 0.3 +  # Ancho base normalizado
            (min(candidate['height'] / 100.0, 1.0)) * 0.3 +  # Altura normalizada  
            candidate['width_consistency'] * 0.2 +  # Consistencia de ancho
            (1 - candidate['distance_from_center'] / (w_img / 2)) * 0.2  # Centrado
        )
        candidate['score'] = score
    
    tape_candidates.sort(key=lambda c: c['score'], reverse=True)
    
    if debug:
        print(f"\n=== TOP CANDIDATOS DE CINTA ===")
        for i, cand in enumerate(tape_candidates):
            print(f"{i+1}. Score: {cand['score']:.3f} | "
                  f"Base: {cand['base_width']}px | "
                  f"Altura: {cand['height']}px | "
                  f"Centro: {cand['avg_center_x']:.0f}")
    
    return tape_candidates

def evaluate_rectangularity_bottom_10_percent(contour):
    """Evalúa qué tan rectangular es el 10% inferior del contorno (base de cinta)"""
    x, y, w, h = cv2.boundingRect(contour)
    
    if h < 10:  # Contorno muy pequeño
        return 0.0
    
    # Extraer solo el 10% inferior
    bottom_fraction = 0.10
    bottom_height = max(int(h * bottom_fraction), 3)  # Mínimo 3 píxeles
    bottom_y_start = y + h - bottom_height
    
    # Crear máscara para el 10% inferior
    bottom_mask = np.zeros((bottom_height, w), dtype=np.uint8)
    
    # Trasladar contorno para que coincida con la región inferior
    translated_contour = contour - [x, bottom_y_start]  
    
    # Dibujar solo la parte que cae en la región inferior
    cv2.drawContours(bottom_mask, [translated_contour], -1, 255, -1)
    
    # Calcular área del contorno en la región inferior
    contour_area_bottom = cv2.countNonZero(bottom_mask)
    
    if contour_area_bottom == 0:
        return 0.0
    
    # Área del rectángulo completo del 10% inferior
    rectangle_area_bottom = w * bottom_height
    
    # Rectangularidad = qué porcentaje del rectángulo está ocupado por el contorno
    rectangularity = contour_area_bottom / rectangle_area_bottom
    
    # FILTRO ESTRICTO: Para cinta esperamos MUY alta rectangularidad (>0.75) en la base
    if rectangularity >= 0.90:
        return 1.0  # Perfectamente rectangular - cinta clara
    elif rectangularity >= 0.80:
        return 0.6  # Muy rectangular - cinta probable
    elif rectangularity >= 0.70:
        return 0.2  # Algo rectangular - dudoso
    else:
        return 0.0  # Irregular - RECHAZAR completamente

def evaluate_base_straightness(contour):
    """Evalúa qué tan recta es la base horizontal del contorno"""
    x, y, w, h = cv2.boundingRect(contour)
    base_y = y + h  # Línea base (parte inferior)
    
    # Extraer píxeles de la base en un rango de ±2 píxeles
    mask = np.zeros((h + 4, w + 4), dtype=np.uint8)
    cv2.drawContours(mask, [contour - [x-2, y-2]], -1, 255, -1)
    
    # Buscar píxeles en la región de la base
    base_pixels = []
    for i in range(max(0, base_y-2), min(mask.shape[0], base_y+3)):
        for j in range(mask.shape[1]):
            if mask[i-y+2, j] == 255:
                base_pixels.append(i)
    
    if len(base_pixels) < 3:
        return 0.0  # No hay suficientes píxeles para evaluar rectitud
    
    # Calcular desviación estándar (menor = más recto)
    std_dev = np.std(base_pixels)
    # Convertir a score: 0-1 donde 1 es perfectamente recto
    straightness_score = max(0, 1 - std_dev / 5.0)  # 5 píxeles de tolerancia
    
    return straightness_score

def evaluate_aspect_ratio(contour):
    """Evalúa el aspect ratio de la porción inferior del contorno (solo cinta, sin lechuga)"""
    x, y, w, h = cv2.boundingRect(contour)
    
    if w == 0 or h == 0:
        return 0.0
    
    # Extraer solo la franja inferior (25% inferior) donde debería estar la cinta
    # Esto evita que la lechuga arriba afecte el aspect ratio
    tape_fraction = 0.25  # 25% inferior del contorno
    tape_height = max(int(h * tape_fraction), 10)  # Mínimo 10 píxeles
    
    # Si el contorno es muy pequeño, usar todo
    if h < 40:  # Contorno pequeño, probablemente solo cinta
        tape_height = h
    
    # Aspect ratio de la franja inferior (cinta real)
    aspect_ratio = tape_height / w
    
    # Para cinta vertical en franja inferior esperamos ratio menor
    # porque es solo la parte de la cinta, no toda la altura
    if 0.3 <= aspect_ratio <= 1.5:  # Rango ajustado para franja inferior
        # Score óptimo entre 0.5 y 1.0
        if 0.5 <= aspect_ratio <= 1.0:
            return 1.0
        else:
            # Penalizar gradualmente fuera del rango óptimo
            return max(0.4, 1.0 - abs(aspect_ratio - 0.75) / 1.0)
    else:
        # Muy pequeña o muy alta incluso para franja
        return 0.2

def evaluate_centrality(contour, img_center_x):
    """Evalúa qué tan cerca del centro está el contorno"""
    x, y, w, h = cv2.boundingRect(contour)
    contour_center_x = x + w // 2
    
    distance_from_center = abs(contour_center_x - img_center_x)
    max_distance = img_center_x  # Máxima distancia posible
    
    # Score: 1.0 = en el centro, 0.0 = en el borde
    centrality_score = max(0, 1.0 - distance_from_center / max_distance)
    
    return centrality_score

def group_aligned_contours(contours, img_width):
    """Agrupa contornos que están alineados horizontalmente (misma X aproximada)"""
    if len(contours) <= 1:
        return [[c] for c in contours]
    
    groups = []
    tolerance = img_width * 0.15  # 15% del ancho como tolerancia
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        center_x = x + w // 2
        
        # Buscar grupo existente
        added_to_group = False
        for group in groups:
            # Verificar si está alineado con algún contorno del grupo
            for existing_contour in group:
                ex, ey, ew, eh = cv2.boundingRect(existing_contour)
                existing_center_x = ex + ew // 2
                
                if abs(center_x - existing_center_x) <= tolerance:
                    group.append(contour)
                    added_to_group = True
                    break
            
            if added_to_group:
                break
        
        # Si no se añadió a ningún grupo, crear uno nuevo
        if not added_to_group:
            groups.append([contour])
    
    return groups

def select_lowest_in_group(contour_group):
    """De un grupo de contornos alineados, selecciona el más bajo (mayor Y)"""
    if len(contour_group) == 1:
        return contour_group[0]
    
    lowest_contour = None
    lowest_y = -1
    
    for contour in contour_group:
        x, y, w, h = cv2.boundingRect(contour)
        base_y = y + h  # Parte inferior del contorno
        
        if base_y > lowest_y:
            lowest_y = base_y
            lowest_contour = contour
    
    return lowest_contour

def smart_contour_selection(contours, img_width, img_height, debug=True):
    """Selección inteligente de contorno usando múltiples criterios"""
    
    if not contours:
        return None
    
    img_center_x = img_width // 2
    img_area = img_width * img_height
    
    if debug:
        print(f"\n=== SELECCIÓN INTELIGENTE DE CONTORNOS ===")
        print(f"Contornos encontrados: {len(contours)}")
    
    # 1. Pre-filtrado básico
    filtered_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filtros básicos - permitir contornos grandes (cinta+vaso+lechuga unificados)
        if (area >= 200 and  # Área mínima
            area <= img_area * 0.95 and  # Permitir hasta 95% (casi toda la imagen)
            x > img_width * 0.02 and  # Menos restrictivo en bordes
            x + w < img_width * 0.98):  # Menos restrictivo en bordes
            filtered_contours.append(contour)
    
    if not filtered_contours:
        if debug:
            print("No hay contornos que pasen el pre-filtrado")
        return None
    
    if debug:
        print(f"Contornos tras pre-filtrado: {len(filtered_contours)}")
    
    # 2. PRE-FILTRO RECTANGULARIDAD: Eliminar contornos con baja rectangularidad
    rectangle_filtered_contours = []
    for contour in filtered_contours:
        rectangularity = evaluate_rectangularity_bottom_10_percent(contour)
        if rectangularity >= 0.70:  # Solo mantener contornos con base rectangular clara
            rectangle_filtered_contours.append(contour)
            if debug:
                x, y, w, h = cv2.boundingRect(contour)
                print(f"  ✓ Contorno ({x}, {y}, {w}x{h}) pasa filtro rectangularidad: {rectangularity:.3f}")
        else:
            if debug:
                x, y, w, h = cv2.boundingRect(contour)
                print(f"  ✗ Contorno ({x}, {y}, {w}x{h}) rechazado por baja rectangularidad: {rectangularity:.3f}")
    
    if not rectangle_filtered_contours:
        if debug:
            print("  Ningún contorno pasó el filtro de rectangularidad")
        return None
    
    if debug:
        print(f"  {len(rectangle_filtered_contours)} contornos pasaron filtro rectangularidad")

    # 3. Agrupar contornos alineados (para manejar cinta partida por reflejos)
    contour_groups = group_aligned_contours(rectangle_filtered_contours, img_width)
    
    if debug:
        print(f"Grupos de contornos alineados: {len(contour_groups)}")
        for i, group in enumerate(contour_groups):
            print(f"  Grupo {i+1}: {len(group)} contornos")
    
    # 4. Seleccionar el contorno más bajo de cada grupo
    candidate_contours = []
    for group in contour_groups:
        lowest = select_lowest_in_group(group)
        candidate_contours.append(lowest)
        
        if debug and len(group) > 1:
            x, y, w, h = cv2.boundingRect(lowest)
            print(f"  Grupo con {len(group)} contornos → seleccionado más bajo en Y={y+h}")
    
    # 5. Evaluar cada candidato con múltiples criterios
    candidate_scores = []
    
    for contour in candidate_contours:
        # Evaluar criterios individuales
        straightness = evaluate_base_straightness(contour)
        aspect_ratio = evaluate_aspect_ratio(contour)
        centrality = evaluate_centrality(contour, img_center_x)
        rectangularity = evaluate_rectangularity_bottom_10_percent(contour)  # NUEVO
        
        # Bonus por ser el más bajo en caso de grupos múltiples
        x, y, w, h = cv2.boundingRect(contour)
        base_y = y + h
        
        # Encontrar si hay otros contornos en posición similar
        position_bonus = 0.0
        for other_contour in candidate_contours:
            if other_contour is contour:
                continue
            ox, oy, ow, oh = cv2.boundingRect(other_contour)
            other_center_x = ox + ow // 2
            contour_center_x = x + w // 2
            
            # Si están alineados horizontalmente, dar bonus al más bajo
            if abs(contour_center_x - other_center_x) <= img_width * 0.15:
                other_base_y = oy + oh
                if base_y > other_base_y:
                    position_bonus = 0.2  # Bonus por ser más bajo
        
        # Score final combinado - rectangularidad es crítica para filtrar sombras
        final_score = (
            rectangularity * 0.30 +      # NUEVO: Filtrar sombras irregulares
            straightness * 0.30 +        # Rectitud sigue siendo importante
            aspect_ratio * 0.20 +        # Reducido pero importante
            centrality * 0.20 +          # Reducido pero importante
            position_bonus               # Bonus sin peso base
        )
        
        candidate_scores.append({
            'contour': contour,
            'score': final_score,
            'straightness': straightness,
            'aspect_ratio': aspect_ratio,
            'centrality': centrality,
            'rectangularity': rectangularity,  # NUEVO
            'position_bonus': position_bonus,
            'bbox': (x, y, w, h)
        })
        
        if debug:
            print(f"  Candidato en ({x}, {y}, {w}, {h}):")
            print(f"    Rectangularidad 10%: {rectangularity:.3f}")  # NUEVO - PRIMERO
            print(f"    Rectitud base: {straightness:.3f}")
            print(f"    Aspect ratio: {aspect_ratio:.3f}")
            print(f"    Centralidad: {centrality:.3f}")
            print(f"    Bonus posición: {position_bonus:.3f}")
            print(f"    Score final: {final_score:.3f}")
    
    # 5. Seleccionar el mejor candidato
    if not candidate_scores:
        return None
    
    best_candidate = max(candidate_scores, key=lambda c: c['score'])
    
    if debug:
        x, y, w, h = best_candidate['bbox']
        print(f"\nMEJOR CANDIDATO seleccionado:")
        print(f"    Posición: ({x}, {y}, {w}, {h})")
        print(f"    Score: {best_candidate['score']:.3f}")
    
    return best_candidate['contour']

def detect_tape_position(image, debug=False, mode='horizontal'):
    """
    Detección de posición de cinta usando selección inteligente de contornos
    """
    
    if debug:
        print("\n=== DETECTOR DE POSICIÓN DE CINTA CON SELECCIÓN INTELIGENTE ===")
    
    h_img, w_img = image.shape[:2]
    img_center_x = w_img // 2
    
    # Aplicar filtrado HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    _, binary_img = cv2.threshold(v_channel, 50, 255, cv2.THRESH_BINARY_INV)  # Filtro moderado
    
    # Encontrar todos los contornos
    contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        if debug:
            print("No se encontraron contornos")
        return []
    
    # ALGORITMO BASADO EN CALIDAD DE BASE: Evaluar 10% inferior de cada contorno
    best_contour = None
    best_score = 0
    
    if debug:
        print(f"Evaluando {len(contours)} contornos por CALIDAD DE BASE (10% inferior):")
    
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < 500:  # Filtro básico de área mínima
            continue
            
        x, y, w, h = cv2.boundingRect(contour)
        
        # EXTRAER 10% INFERIOR PARA EVALUACIÓN
        bottom_fraction = 0.10
        bottom_height = max(int(h * bottom_fraction), 5)
        bottom_y_start = y + h - bottom_height
        
        # Crear máscara para esta base específica
        mask = np.zeros((h_img, w_img), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        bottom_region = mask[bottom_y_start:y+h, :]
        
        # Evaluar CALIDAD de esta base
        base_pixels_found = False
        real_base_x_min = w_img
        real_base_x_max = 0
        
        # Contar píxeles blancos por fila para evaluar rectitud
        row_widths = []
        for row_idx in range(bottom_region.shape[0]):
            row = bottom_region[row_idx, :]
            white_pixels = np.where(row == 255)[0]
            
            if len(white_pixels) > 0:
                base_pixels_found = True
                row_x_min = white_pixels[0]
                row_x_max = white_pixels[-1]
                row_width = row_x_max - row_x_min + 1
                row_widths.append(row_width)
                real_base_x_min = min(real_base_x_min, row_x_min)
                real_base_x_max = max(real_base_x_max, row_x_max)
        
        if not base_pixels_found or len(row_widths) < 2:
            if debug:
                print(f"  Contorno {i+1}: No tiene base válida")
            continue
        
        # MÉTRICAS DE CALIDAD DE BASE
        real_base_width = real_base_x_max - real_base_x_min + 1
        
        # FILTRO: Base debe ser suficientemente ancha (eliminar bases muy pequeñas de lechuga)
        if real_base_width < 25:  # Mínimo 25px de ancho de base
            if debug:
                print(f"  Contorno {i+1}: Base muy estrecha ({real_base_width}px < 25px)")
            continue
        
        # Calcular métricas individuales
        width_variance = np.var(row_widths) if len(row_widths) > 1 else 1000
        consistency_score = max(0, 1.0 - (width_variance / 100.0))
        
        avg_width = np.mean(row_widths)
        straightness_score = avg_width / real_base_width if real_base_width > 0 else 0
        
        total_pixels_in_base = np.sum(bottom_region == 255)
        max_possible_pixels = real_base_width * bottom_height
        occupancy_score = total_pixels_in_base / max_possible_pixels if max_possible_pixels > 0 else 0
        
        width_score = min(real_base_width / 40.0, 1.0)
        size_bonus = min(real_base_width / 100.0, 0.3)
        
        # Score combinado
        combined_score = (
            width_score * 0.40 +
            consistency_score * 0.30 +
            occupancy_score * 0.20 +
            straightness_score * 0.10 +
            size_bonus
        )
        
        if debug:
            print(f"  Contorno {i+1}: {w}x{h} | Base: {real_base_width}px")
            print(f"    Consistencia: {consistency_score:.3f} | Rectitud: {straightness_score:.3f}")
            print(f"    Ocupación: {occupancy_score:.3f} | Ancho: {width_score:.3f}")
            print(f"    Size bonus: {size_bonus:.3f} | Score TOTAL: {combined_score:.3f}")
        
        if combined_score > best_score:
            best_score = combined_score
            best_contour = contour
    
    if best_contour is None:
        if debug:
            print("No se encontró contorno válido")
        return []
    
    main_contour = best_contour
    if debug:
        x, y, w, h = cv2.boundingRect(main_contour)
        print(f"ELEGIDO: {w}x{h} con MEJOR CALIDAD DE BASE (score: {best_score:.3f})")
    
    # Calcular información del contorno seleccionado
    x, y, w, h = cv2.boundingRect(main_contour)
    
    # USAR SOLO EL 10% INFERIOR DEL CONTORNO PARA CENTRO Y ANCHO
    bottom_fraction = 0.10  # 10% inferior
    bottom_height = max(int(h * bottom_fraction), 5)  # Mínimo 5 píxeles
    bottom_y_start = y + h - bottom_height
    
    # Crear máscara para extraer solo el 10% inferior
    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    cv2.drawContours(mask, [main_contour], -1, 255, -1)
    
    # Extraer solo la región inferior
    bottom_region = mask[bottom_y_start:y+h, :]
    
    # Encontrar el ancho real de la base en esta región
    base_pixels_found = False
    real_base_x_min = w_img
    real_base_x_max = 0
    
    for row_idx in range(bottom_region.shape[0]):
        row = bottom_region[row_idx, :]
        white_pixels = np.where(row == 255)[0]
        
        if len(white_pixels) > 0:
            base_pixels_found = True
            row_x_min = white_pixels[0]
            row_x_max = white_pixels[-1]
            real_base_x_min = min(real_base_x_min, row_x_min)
            real_base_x_max = max(real_base_x_max, row_x_max)
    
    if base_pixels_found:
        # Usar dimensiones REALES de la base (solo 10% inferior)
        real_base_width = real_base_x_max - real_base_x_min + 1
        real_center_x = (real_base_x_min + real_base_x_max) // 2
        base_y = y + h  # Línea base (parte inferior)
        
        if debug:
            print(f"Contorno completo: {w}x{h}")
            print(f"Base real (10% inferior): ancho={real_base_width}px, centro={real_center_x}px")
            print(f"Reducción: {w}px -> {real_base_width}px")
    else:
        # Fallback: usar contorno completo si falla extracción de base
        real_base_width = w
        real_center_x = x + w // 2
        base_y = y + h
        if debug:
            print("No se pudo extraer base, usando contorno completo")
    
    center_x = real_center_x
    base_width = real_base_width
    
    # Calcular distancia según el modo
    if mode == 'vertical':
        img_center_y = h_img // 2
        distance_pixels = base_y - img_center_y  # Para vertical: negativo=subir, positivo=bajar
    else:
        distance_pixels = center_x - img_center_x  # Para horizontal usar coordenada X
    
    tape_result = {
        'base_center_x': center_x,
        'contour_center_x': x + w // 2,  # Centro del contorno completo (para horizontal)
        'base_width': base_width,  # Usar ancho REAL de la base (10% inferior)
        'start_x': real_base_x_min if base_pixels_found else x,
        'end_x': real_base_x_max if base_pixels_found else x + w,
        'base_y': base_y,  # Usar línea base en lugar de centro
        'distance_from_center_x': abs(distance_pixels),
        'distance_pixels': distance_pixels,  # Campo requerido por main_robot.py
        'score': 0.9  # Mayor confianza con selección inteligente
    }
    
    if debug:
        print(f"Centro detectado en X = {center_x} px")
        print(f"Base detectada en Y = {base_y} px")
        print(f"Distancia del centro: {tape_result['distance_pixels']} px (con signo)")
    
    return [tape_result]

def capture_image_for_correction_debug(camera_index=0, max_retries=1):
    """Captura una imagen para corrección de posición horizontal con modo debug"""
    global _working_camera_cache
    
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    # Liberar recursos previos
    cv2.destroyAllWindows()
    time.sleep(0.3)
    
    # Captura directa - cámara siempre en índice fijo
    print(f"Intento 1/3 - Cámara {camera_index}...")
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        print(f"Imagen capturada exitosamente desde cámara {camera_index}")
        
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Calcular área de recorte
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        # Mostrar imagen rotada con cuadrado de referencia
        frame_con_rectangulo = frame_rotado.copy()
        cv2.rectangle(frame_con_rectangulo, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(frame_con_rectangulo, "AREA DE ANALISIS", (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("DEBUG HORIZONTAL: 1. Imagen + Area de Analisis", frame_con_rectangulo)
        cv2.resizeWindow("DEBUG HORIZONTAL: 1. Imagen + Area de Analisis", 800, 600)
        print("🔄 1. Imagen con área de análisis marcada - Presiona 'c' para continuar...")
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                break
        cv2.destroyAllWindows()
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        
        # Mostrar imagen recortada
        cv2.imshow("DEBUG HORIZONTAL: 2. Imagen Recortada", frame_recortado)
        cv2.resizeWindow("DEBUG HORIZONTAL: 2. Imagen Recortada", 800, 600)
        print("✂️ 2. Imagen recortada para análisis - Presiona 'c' para continuar...")
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                break
        cv2.destroyAllWindows()
        
        return frame_recortado
    else:
        print("Error: No se pudo capturar imagen")
        return None

def detect_tape_position_debug(image, debug=True):
    """Detecta la posición de la cinta horizontal con modo debug visual - MISMO ALGORITMO QUE EL NORMAL"""
    if image is None:
        return []
    
    h_img, w_img = image.shape[:2]
    img_center_x = w_img // 2
    
    print(f"Analizando imagen: {w_img}x{h_img}, centro X: {img_center_x}")
    
    # Mostrar imagen original
    cv2.imshow("DEBUG HORIZONTAL: Imagen Original", image)
    print("Imagen para análisis - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # USAR MISMO ALGORITMO QUE EL MODO NORMAL: HSV V-channel threshold
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    
    # Mostrar canal V
    cv2.imshow("DEBUG HORIZONTAL: 3. Canal V (Brillo)", v_channel)
    cv2.resizeWindow("DEBUG HORIZONTAL: 3. Canal V (Brillo)", 800, 600)
    print("🌈 3. Canal V extraído - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # Threshold para zonas oscuras (igual que modo normal)
    _, thresh = cv2.threshold(v_channel, 50, 255, cv2.THRESH_BINARY_INV)  # Filtro moderado
    
    # Mostrar threshold
    cv2.imshow("DEBUG HORIZONTAL: 4. Imagen Binaria", thresh)
    cv2.resizeWindow("DEBUG HORIZONTAL: 4. Imagen Binaria", 800, 600)
    print("4. Threshold aplicado (zonas oscuras) - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # Encontrar contornos
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        print("No se encontraron contornos")
        return []
    
    # USAR MISMO ALGORITMO MEJORADO QUE MODO NORMAL + ANÁLISIS VISUAL
    best_contour = None
    best_score = 0
    contour_analysis = []  # Para guardar análisis de cada contorno
    
    print(f"Evaluando {len(contours)} contornos por ancho de base:")
    
    # Crear imagen para mostrar análisis de todos los contornos
    analysis_image = image.copy()
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < 500:  # Filtro básico de área mínima
            continue
            
        x, y, w, h = cv2.boundingRect(contour)
        
        # EXTRAER 10% INFERIOR PARA EVALUACIÓN (MISMO ALGORITMO ACTUALIZADO)
        bottom_fraction = 0.10
        bottom_height = max(int(h * bottom_fraction), 5)
        bottom_y_start = y + h - bottom_height
        
        # Crear máscara para esta base específica
        mask = np.zeros((h_img, w_img), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        bottom_region = mask[bottom_y_start:y+h, :]
        
        # Evaluar CALIDAD de esta base
        base_pixels_found = False
        real_base_x_min = w_img
        real_base_x_max = 0
        
        # Contar píxeles blancos por fila para evaluar rectitud
        row_widths = []
        for row_idx in range(bottom_region.shape[0]):
            row = bottom_region[row_idx, :]
            white_pixels = np.where(row == 255)[0]
            
            if len(white_pixels) > 0:
                base_pixels_found = True
                row_x_min = white_pixels[0]
                row_x_max = white_pixels[-1]
                row_width = row_x_max - row_x_min + 1
                row_widths.append(row_width)
                real_base_x_min = min(real_base_x_min, row_x_min)
                real_base_x_max = max(real_base_x_max, row_x_max)
        
        if not base_pixels_found or len(row_widths) < 2:
            print(f"  Contorno {i+1}: No tiene base válida")
            continue
        
        # MÉTRICAS DE CALIDAD DE BASE
        real_base_width = real_base_x_max - real_base_x_min + 1
        
        # FILTRO: Base debe ser suficientemente ancha
        if real_base_width < 25:
            print(f"  Contorno {i+1}: Base muy estrecha ({real_base_width}px < 25px)")
            continue
        
        # Calcular métricas individuales
        width_variance = np.var(row_widths) if len(row_widths) > 1 else 1000
        consistency_score = max(0, 1.0 - (width_variance / 100.0))
        
        avg_width = np.mean(row_widths)
        straightness_score = avg_width / real_base_width if real_base_width > 0 else 0
        
        total_pixels_in_base = np.sum(bottom_region == 255)
        max_possible_pixels = real_base_width * bottom_height
        occupancy_score = total_pixels_in_base / max_possible_pixels if max_possible_pixels > 0 else 0
        
        width_score = min(real_base_width / 40.0, 1.0)
        size_bonus = min(real_base_width / 100.0, 0.3)
        
        # Score combinado
        combined_score = (
            width_score * 0.40 +
            consistency_score * 0.30 +
            occupancy_score * 0.20 +
            straightness_score * 0.10 +
            size_bonus
        )
        
        # Guardar análisis para visualización
        contour_info = {
            'contour': contour,
            'index': i + 1,
            'bbox': (x, y, w, h),
            'base_bbox': (real_base_x_min, bottom_y_start, real_base_width, bottom_height),
            'real_base_width': real_base_width,
            'consistency_score': consistency_score,
            'straightness_score': straightness_score,
            'occupancy_score': occupancy_score,
            'width_score': width_score,
            'size_bonus': size_bonus,
            'combined_score': combined_score,
            'color': colors[i % len(colors)]
        }
        contour_analysis.append(contour_info)
        
        print(f"  Contorno {i+1}: {w}x{h} | Base: {real_base_width}px")
        print(f"    Consistencia: {consistency_score:.3f} | Rectitud: {straightness_score:.3f}")
        print(f"    Ocupación: {occupancy_score:.3f} | Ancho: {width_score:.3f}")
        print(f"    Size bonus: {size_bonus:.3f} | Score TOTAL: {combined_score:.3f}")
        
        if combined_score > best_score:
            best_score = combined_score
            best_contour = contour
    
    if best_contour is None:
        print("No se encontró contorno válido")
        return []
    
    # CREAR IMAGEN DE ANÁLISIS VISUAL
    # Dibujar todos los contornos analizados con sus métricas
    for info in contour_analysis:
        color = info['color']
        
        # 1. Dibujar contorno completo
        cv2.drawContours(analysis_image, [info['contour']], -1, color, 2)
        
        # 2. Dibujar rectángulo de la base (10% inferior)
        base_x, base_y, base_w, base_h = info['base_bbox']
        cv2.rectangle(analysis_image, (base_x, base_y), (base_x + base_w, base_y + base_h), color, 2)
        
        # 3. Marcar si es el contorno elegido
        x, y, w, h = info['bbox']
        marker = "✓ ELEGIDO" if info['contour'] is best_contour else f"#{info['index']}"
        font_scale = 0.6 if info['contour'] is best_contour else 0.5
        thickness = 2 if info['contour'] is best_contour else 1
        
        # Texto de identificación
        cv2.putText(analysis_image, marker, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        
        # 4. Mostrar métricas individuales al lado del contorno
        metrics_text = [
            f"W:{info['width_score']:.2f}(40%)",
            f"C:{info['consistency_score']:.2f}(30%)",
            f"O:{info['occupancy_score']:.2f}(20%)", 
            f"R:{info['straightness_score']:.2f}(10%)",
            f"B:{info['size_bonus']:.2f}",
            f"TOT:{info['combined_score']:.2f}"
        ]
        
        for j, text in enumerate(metrics_text):
            cv2.putText(analysis_image, text, 
                       (x + w + 10, y + 20 + j * 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # Mostrar imagen de análisis
    cv2.imshow('ANÁLISIS DE CONTORNOS - Métricas por Área', analysis_image)
    print(f"\nIMAGEN DE ANÁLISIS: Mostrando {len(contour_analysis)} contornos con sus puntajes")
    print("   - Contorno completo (color)")
    print("   - Base 10% inferior (rectángulo del mismo color)")
    print("   - W=Ancho(40%), C=Consistencia(30%), O=Ocupación(20%), R=Rectitud(10%), B=Bonus")
    
    main_contour = best_contour
    x, y, w, h = cv2.boundingRect(main_contour)
    print(f"ELEGIDO: {w}x{h} con ancho de base {w}px (score: {best_score:.3f})")
    
    # EXTRAER SOLO EL 10% INFERIOR (igual que modo normal)
    bottom_fraction = 0.10  # 10% inferior
    bottom_height = max(int(h * bottom_fraction), 5)  # Mínimo 5 píxeles
    bottom_y_start = y + h - bottom_height
    
    # Crear máscara para extraer solo el 10% inferior
    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    cv2.drawContours(mask, [main_contour], -1, 255, -1)
    
    # Extraer solo la región inferior
    bottom_region = mask[bottom_y_start:y+h, :]
    
    # Encontrar el ancho real de la base en esta región
    base_pixels_found = False
    real_base_x_min = w_img
    real_base_x_max = 0
    
    for row_idx in range(bottom_region.shape[0]):
        row = bottom_region[row_idx, :]
        white_pixels = np.where(row == 255)[0]
        
        if len(white_pixels) > 0:
            base_pixels_found = True
            row_x_min = white_pixels[0]
            row_x_max = white_pixels[-1]
            real_base_x_min = min(real_base_x_min, row_x_min)
            real_base_x_max = max(real_base_x_max, row_x_max)
    
    if base_pixels_found:
        # Usar dimensiones REALES de la base (solo 10% inferior)
        real_base_width = real_base_x_max - real_base_x_min + 1
        real_center_x = (real_base_x_min + real_base_x_max) // 2
        print(f"Contorno completo: {w}x{h}")
        print(f"Base real (10% inferior): ancho={real_base_width}px, centro={real_center_x}px")
        print(f"Reducción: {w}px -> {real_base_width}px")
    else:
        # Fallback: usar contorno completo si falla extracción de base
        real_base_width = w
        real_center_x = x + w // 2
        print("No se pudo extraer base, usando contorno completo")
    
    center_x = real_center_x
    base_width = real_base_width
    
    print(f"Región principal: {w}x{h} en ({x}, {y})")
    
    # Crear imagen con contornos sobre imagen a COLOR
    if len(image.shape) == 3:
        contour_image = image.copy()
    else:
        # Si es escala de grises, convertir a color
        contour_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    
    # Dibujar contorno completo (verde)
    cv2.drawContours(contour_image, [main_contour], -1, (0, 255, 0), 2)
    
    # Dibujar SOLO la región de la base real (10% inferior) - RECTÁNGULO AZUL
    if base_pixels_found:
        base_rect_x = real_base_x_min
        base_rect_y = bottom_y_start
        base_rect_w = real_base_width
        base_rect_h = bottom_height
        cv2.rectangle(contour_image, (base_rect_x, base_rect_y), 
                     (base_rect_x + base_rect_w, base_rect_y + base_rect_h), 
                     (255, 0, 0), 4)  # AZUL GRUESO = Base real
        
        # Marcar línea de la base específicamente (ROJA)
        cv2.line(contour_image, (real_base_x_min, y + h), (real_base_x_max, y + h), (0, 0, 255), 3)
    else:
        # Si falla, usar rectángulo completo (amarillo)
        cv2.rectangle(contour_image, (x, y), (x + w, y + h), (0, 255, 255), 3)  # Amarillo
    
    # Dibujar centro REAL (círculo grande ROJO)
    cv2.circle(contour_image, (center_x, y + h - bottom_height // 2), 15, (0, 0, 255), -1)
    
    # Líneas de referencia MÁS GRUESAS
    cv2.line(contour_image, (img_center_x, 0), (img_center_x, h_img), (255, 0, 255), 4)  # Magenta = centro imagen
    cv2.line(contour_image, (center_x, 0), (center_x, h_img), (0, 0, 255), 4)  # Rojo = centro detectado
    
    # Agregar texto explicativo ACTUALIZADO
    cv2.putText(contour_image, f"Centro IMG: {img_center_x}px", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
    cv2.putText(contour_image, f"Centro BASE REAL: {center_x}px", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(contour_image, f"DIFERENCIA: {center_x - img_center_x}px", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    if base_pixels_found:
        cv2.putText(contour_image, f"Ancho base real: {real_base_width}px", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        cv2.putText(contour_image, f"RECTANGULO AZUL = 10% inferior", (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    # Mostrar resultado final
    cv2.imshow("DEBUG HORIZONTAL: 5. DETECCION FINAL", contour_image)
    cv2.resizeWindow("DEBUG HORIZONTAL: 5. DETECCION FINAL", 800, 600)
    print(f"5. Centro detectado en X={center_x}px (centro imagen={img_center_x}px) - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # Calcular distancia desde el centro (igual que modo normal)
    distance_pixels = center_x - img_center_x
    
    # Crear resultado usando BASE REAL (igual que modo normal)
    tape_result = {
        'base_center_x': center_x,  # Centro de la base real
        'base_width': base_width,   # Ancho de la base real
        'start_x': real_base_x_min if base_pixels_found else x,
        'end_x': real_base_x_max if base_pixels_found else x + w,
        'base_y': y + h,  # Línea base
        'distance_from_center_x': abs(distance_pixels),
        'distance_pixels': distance_pixels,  # Campo requerido por main_robot.py
        'score': 0.8
    }
    
    print(f"Resultado: centro X={center_x}px, distancia del centro={distance_pixels}px")
    
    return [tape_result]

def get_position_distance_for_correction(camera_index=0, mode='horizontal'):
    """
    Función unificada para corrección horizontal y vertical - devuelve distancia en píxeles
    Utilizada por la máquina de estados para corrección iterativa
    
    Args:
        camera_index: Índice de la cámara a usar
        mode: Modo de corrección ('horizontal' o 'vertical')
    """
    # Capturar imagen
    if mode == 'horizontal':
        image = capture_image_for_correction(camera_index)
    elif mode == 'vertical':
        image = capture_image_for_vertical_correction(camera_index)
    else:
        raise ValueError("Modo de corrección no válido")
    
    if image is None:
        return {'success': False, 'distance_pixels': 0, 'error': 'No se pudo capturar imagen'}
    
    # Detectar cinta
    candidates = detect_tape_position(image, debug=False)
    
    if not candidates:
        return {'success': False, 'distance_pixels': 0, 'error': 'No se detectó cinta'}
    
    # Calcular distancia horizontal desde centro
    best_candidate = candidates[0]
    img_center_x = image.shape[1] // 2
    detected_x = best_candidate['base_center_x']
    distance = detected_x - img_center_x  # Positivo = derecha, Negativo = izquierda
    
    return {
        'success': True,
        'distance_pixels': int(distance),
        'confidence': best_candidate['score']
    }

def get_horizontal_correction_mm(camera_index=0, offset_x_mm=0.0):
    """
    Función NUEVA que devuelve corrección horizontal directamente en MM
    Aplica calibración interna y devuelve movimiento necesario en milímetros
    """
    try:
        # Cargar calibración lineal
        calibracion_lineal_path = os.path.join(os.path.dirname(__file__), "calibracion_lineal_horizontal.json")
        
        with open(calibracion_lineal_path, 'r') as f:
            calibracion_lineal = json.load(f)
            
        # Obtener coeficientes de la calibración lineal: mm = a * pixels + b
        a_coef = calibracion_lineal['coefficients']['a']
        b_coef = calibracion_lineal['coefficients']['b']
        
        # Obtener corrección en píxeles
        pixel_result = get_position_distance_for_correction(camera_index, mode='horizontal')
        
        if not pixel_result['success']:
            print(f"Error obteniendo corrección: {pixel_result.get('error', 'Desconocido')}")
            return None
            
        distance_pixels = pixel_result['distance_pixels']
        
        # Convertir píxeles a mm usando calibración lineal: mm = a * pixels + b
        correction_mm = a_coef * distance_pixels + b_coef
        
        # Aplicar offset si se proporciona
        final_correction_mm = correction_mm + offset_x_mm
        
        print(f"Corrección horizontal: {distance_pixels}px -> {correction_mm:.2f}mm (final: {final_correction_mm:.2f}mm)")
        
        return final_correction_mm
        
    except Exception as e:
        print(f"Error en get_horizontal_correction_mm: {e}")
        return None

def capture_image_for_vertical_correction(camera_index=0):
    """Captura imagen para corrección vertical con rotación y recorte"""
    global _working_camera_cache
    
    # Liberar recursos previos
    cv2.destroyAllWindows()
    time.sleep(0.3)
    
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    print(f"Capturando imagen vertical desde cámara {camera_index}...")
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        print(f"Imagen vertical capturada exitosamente desde cámara {camera_index}")
        
        # Rotar imagen 90 grados en sentido antihorario
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Calcular área de recorte
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        # Aplicar recorte
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        
        return frame_recortado
    else:
        print("Error: No se pudo capturar imagen vertical")
        return None

# FUNCIÓN ELIMINADA - Esta función duplicada se movió a vertical_detector.py
# para evitar duplicación de código antes de la unificación final

# FUNCIÓN ELIMINADA - Esta función duplicada ya existe en vertical_detector.py
# Se eliminó para evitar duplicación de código antes de la unificación final

def visualize_base_width_detection(image, candidates):
    """Visualiza la detección basada en ancho de base real"""
    
    if not candidates:
        print("No hay candidatos para visualizar")
        no_detection_img = image.copy()
        cv2.putText(no_detection_img, "NO SE DETECTÓ BASE DE CINTA", (50, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow('RESULTADO - Sin Base Detectada', no_detection_img)
        return no_detection_img
    
    result_img = image.copy()
    h_img, w_img = image.shape[:2]
    img_center_x = w_img // 2
    
    # MEJOR CANDIDATO
    best = candidates[0]
    
    # Dibujar rectángulo basado en el ANCHO DE BASE REAL
    rect_x = int(best['base_center_x'] - best['base_width'] // 2)
    rect_y = best['top_y']
    rect_w = best['base_width']  # USAR ANCHO REAL DE LA BASE
    rect_h = best['base_width']  # Altura = ancho de base (cuadrado)
    
    # Rectángulo principal (verde grueso)
    cv2.rectangle(result_img, (rect_x, rect_y), (rect_x + rect_w, rect_y + rect_h), (0, 255, 0), 4)
    
    # Línea central
    center_x = int(best['base_center_x'])
    cv2.line(result_img, (center_x, rect_y), (center_x, rect_y + rect_h), (0, 255, 255), 3)
    
    # Marcar la BASE específicamente (línea horizontal roja)
    base_start_x = int(best['base_center_x'] - best['base_width'] // 2)
    base_end_x = int(best['base_center_x'] + best['base_width'] // 2)
    cv2.line(result_img, (base_start_x, best['base_y']), (base_end_x, best['base_y']), (0, 0, 255), 3)
    
    # Centro de imagen
    cv2.line(result_img, (img_center_x, 0), (img_center_x, h_img), (128, 128, 128), 2)
    cv2.putText(result_img, "Centro Imagen", (img_center_x + 10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
    
    # Información detallada
    info_lines = [
        f"CINTA CON ANCHO DE BASE REAL - Score: {best['score']:.2f}",
        f"ANCHO BASE: {best['base_width']} pixels (LÍNEA ROJA)",
        f"Altura total: {best['height']} pixels",
        f"Centro base X: {best['base_center_x']:.0f}",
        f"Centro imagen X: {img_center_x}",
        f"Distancia: {best['base_center_x'] - img_center_x:.0f} px",
        f"Direccion: {'DERECHA' if best['base_center_x'] > img_center_x else 'IZQUIERDA' if best['base_center_x'] < img_center_x else 'CENTRADO'}",
        f"Consistencia ancho: {best['width_consistency']:.1%}",
        f"Confianza: {'ALTA' if best['score'] > 0.7 else 'MEDIA' if best['score'] > 0.5 else 'BAJA'}"
    ]
    
    for i, line in enumerate(info_lines):
        y_pos = 25 + i * 20
        cv2.rectangle(result_img, (10, y_pos-12), (650, y_pos+8), (0, 0, 0), -1)
        cv2.putText(result_img, line, (15, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Mostrar ventana principal
    cv2.namedWindow('RESULTADO - Ancho de Base Real', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('RESULTADO - Ancho de Base Real', 900, 700)
    cv2.imshow('RESULTADO - Ancho de Base Real', result_img)
    
    # Comparación
    original_resized = cv2.resize(image, (400, 300))
    result_resized = cv2.resize(result_img, (400, 300))
    comparison = np.hstack([original_resized, result_resized])
    
    cv2.putText(comparison, "ORIGINAL NUEVA", (10, 25), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(comparison, "BASE REAL DETECTADA", (410, 25), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    cv2.imshow('Comparación: Nueva Imagen vs Base Real', comparison)
    
    print(f"\nVENTANAS ABIERTAS (ANCHO DE BASE REAL):")
    print(f"   1. 'RESULTADO - Ancho de Base Real' (principal)")
    print(f"   2. 'Comparación: Nueva Imagen vs Base Real'")
    print(f"   LÍNEA ROJA = Ancho real de la base de tu cinta")
    print(f"   RECTÁNGULO VERDE = Cinta completa")
    print(f"   LÍNEA AMARILLA = Centro de la cinta")
    print(f"\nPresiona cualquier tecla para continuar...")
    
    return result_img

def main():
    """Función principal con detección de ancho de base real"""
    
    print("=== DETECTOR DE ANCHO DE BASE REAL ===")
    print("Nueva estrategia específica para cintas curvadas/inclinadas:")
    print("1. Capturar NUEVA imagen")
    print("2. Encontrar base horizontal sólida de la cinta")
    print("3. Medir ancho REAL en esa base")
    print("4. Seguir forma de cinta hacia arriba (permite curvatura)")
    print("5. Dibujar rectángulo basado en ancho de base real\n")
    
    # SIEMPRE capturar nueva imagen
    print("Capturando nueva imagen...")
    image = capture_new_image()
    
    if image is None:
        print("No se capturó ninguna imagen")
        return
    
    # Imagen capturada - procesando sin guardar archivos
    
    # Detectar posición de cinta
    candidates = detect_tape_position(image, debug=True, mode='horizontal')
    
    if candidates:
        best_candidate = candidates[0]
        
        # Calcular resultado sin guardar imágenes
        # result_img = visualize_base_width_detection(image, candidates)
        
        # Calcular resultado
        img_center_x = image.shape[1] // 2
        tape_center_x = best_candidate['base_center_x']
        distance = tape_center_x - img_center_x
        
        print(f"\n=== RESULTADO FINAL CON ANCHO DE BASE REAL ===")
        print(f"BASE de cinta detectada!")
        print(f"Ancho REAL de base: {best_candidate['base_width']} px")
        print(f"Altura total cinta: {best_candidate['height']} px")
        print(f"Centro imagen: {img_center_x} px")
        print(f"Centro base cinta: {tape_center_x:.0f} px")
        print(f"Distancia: {distance:.0f} px ({'derecha' if distance > 0 else 'izquierda' if distance < 0 else 'centrado'})")
        print(f"Consistencia de ancho: {best_candidate['width_consistency']:.1%}")
        print(f"Score: {best_candidate['score']:.3f}")
        print(f"Confianza: {'Alta' if best_candidate['score'] > 0.7 else 'Media' if best_candidate['score'] > 0.5 else 'Baja'}")
        
        result = {
            'success': True,
            'tape_center_x': tape_center_x,
            'distance_from_center': distance,
            'base_width_pixels': best_candidate['base_width'],
            'total_height': best_candidate['height'],
            'width_consistency': best_candidate['width_consistency'],
            'confidence_score': best_candidate['score']
        }
        
    else:
        print(f"\nNO SE DETECTÓ BASE DE CINTA")
        print("Posibles causas:")
        print("- La base horizontal no está visible claramente")
        print("- La cinta está muy tapada en la parte inferior")
        print("- Los parámetros necesitan ajuste para tu setup específico")
        
        result = {
            'success': False,
            'tape_center_x': None,
            'distance_from_center': None,
            'base_width_pixels': 0
        }
    
    print("\nPresiona cualquier tecla para cerrar...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return result

if __name__ == "__main__":
    main()