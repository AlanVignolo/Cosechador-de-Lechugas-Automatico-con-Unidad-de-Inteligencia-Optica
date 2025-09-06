import cv2
import numpy as np
import json
import os
import threading
import time

# Cache global para recordar qué cámara funciona
_working_camera_cache = None

def capture_new_image(camera_index=0):
    """Alias para capture_image_for_correction - mantiene compatibilidad con otros módulos"""
    return capture_image_for_correction(camera_index)

def capture_with_timeout(camera_index, timeout=5.0):
    """Captura frame con timeout para evitar que se cuelgue"""
    result = {'frame': None, 'success': False, 'cap': None}
    
    def capture_thread():
        cap = None
        try:
            # Intentar liberar cualquier instancia previa
            cv2.destroyAllWindows()
            time.sleep(0.2)
            
            cap = cv2.VideoCapture(camera_index)
            result['cap'] = cap
            if cap.isOpened():
                # Esperar un momento para que la cámara se inicialice
                time.sleep(0.1)
                ret, frame = cap.read()
                if ret and frame is not None:
                    result['frame'] = frame.copy()
                    result['success'] = True
        except Exception as e:
            print(f"Error en captura: {e}")
            result['success'] = False
        finally:
            if cap is not None:
                try:
                    cap.release()
                    time.sleep(0.2)  # Más tiempo para liberación
                    cv2.destroyAllWindows()
                except:
                    pass
    
    thread = threading.Thread(target=capture_thread)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    # Cleanup forzado si hay timeout
    if thread.is_alive():
        print(f"⚠️ Timeout en captura de cámara {camera_index}")
        if result['cap'] is not None:
            try:
                result['cap'].release()
                time.sleep(0.3)
                cv2.destroyAllWindows()
            except:
                pass
        return None
    
    # Liberación adicional después del hilo
    if result['cap'] is not None:
        try:
            result['cap'].release()
            time.sleep(0.2)
        except:
            pass
    
    return result['frame'] if result['success'] else None

def scan_available_cameras():
    """Escanea cámaras disponibles"""
    available_cameras = []
    
    print("🔍 Escaneando cámaras disponibles...")
    
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
                    print(f"✅ Cámara {i}: {w}x{h} - FUNCIONAL")
                cap.release()
        except Exception:
            continue
    
    return available_cameras

def capture_image_for_correction(camera_index=0, max_retries=1):
    """Captura una imagen para corrección de posición vertical"""
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
    
    # Captura directa - cámara siempre en índice fijo
    print(f"🎥 Intento 1/3 - Cámara vertical {camera_index}...")
    
    frame = capture_with_timeout(camera_index, timeout=3.0)
    
    if frame is not None:
        print(f"✅ Imagen vertical capturada exitosamente desde cámara {camera_index}")
        
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        return frame_recortado
    
    print("❌ Error: No se pudo capturar imagen vertical")
    return None

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
            print("❌ No hay contornos que pasen el pre-filtrado")
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
            print("  ❌ Ningún contorno pasó el filtro de rectangularidad")
        return None
    
    if debug:
        print(f"  📦 {len(rectangle_filtered_contours)} contornos pasaron filtro rectangularidad")

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
        print(f"\n✅ MEJOR CANDIDATO seleccionado:")
        print(f"    Posición: ({x}, {y}, {w}, {h})")
        print(f"    Score: {best_candidate['score']:.3f}")
    
    return best_candidate['contour']

def detect_tape_position(image, debug=True):
    """
    Detección de posición de cinta usando selección inteligente de contornos
    """
    
    if debug:
        print("\n=== DETECTOR VERTICAL CON SELECCIÓN INTELIGENTE ===")
    
    h_img, w_img = image.shape[:2]
    img_center_x = w_img // 2
    img_center_y = h_img // 2
    
    # Aplicar filtrado HSV (igual que horizontal)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    _, binary_img = cv2.threshold(v_channel, 30, 255, cv2.THRESH_BINARY_INV)
    
    if debug:
        print("Usando filtro hsv_muy_oscuro (el más limpio)")
    
    # Encontrar todos los contornos
    contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        if debug:
            print("❌ No se encontraron contornos")
        return []
    
    # Selección inteligente del mejor contorno
    best_contour = smart_contour_selection(contours, w_img, h_img, debug)
    
    if best_contour is None:
        if debug:
            print("❌ No se pudo seleccionar un contorno válido")
        return []
    
    # Calcular información del contorno seleccionado
    x, y, w, h = cv2.boundingRect(best_contour)
    center_x = x + w // 2
    base_y = y + h  # Línea base (parte inferior) - MISMO QUE HORIZONTAL
    
    tape_result = {
        'base_center_x': center_x,
        'base_y': base_y,  # Usar línea base consistente
        'base_width': w,
        'start_x': x,
        'end_x': x + w,
        'distance_from_center_y': abs(base_y - img_center_y),
        'score': 0.9  # Mayor confianza con selección inteligente
    }
    
    if debug:
        print(f"✅ Centro detectado en X = {center_x} px")
        print(f"✅ Base detectada en Y = {base_y} px")
        print(f"Distancia vertical del centro: {tape_result['distance_from_center_y']} px")
    
    return [tape_result]

def get_vertical_correction_distance(camera_index=0):
    """
    Función simplificada para corrección vertical - solo devuelve distancia en píxeles
    Utilizada por la máquina de estados para corrección iterativa
    """
    # Capturar imagen
    image = capture_image_for_correction(camera_index)
    if image is None:
        return {'success': False, 'distance_pixels': 0, 'error': 'No se pudo capturar imagen'}
    
    # Detectar cinta
    candidates = detect_tape_position(image, debug=False)
    
    if not candidates:
        return {'success': False, 'distance_pixels': 0, 'error': 'No se detectó cinta'}
    
    # Calcular distancia vertical desde centro
    best_candidate = candidates[0]
    img_center_y = image.shape[0] // 2
    detected_y = best_candidate['base_y']
    distance = detected_y - img_center_y
    
    return {
        'success': True,
        'distance_pixels': int(distance),
        'confidence': best_candidate['score']
    }

def visualize_vertical_detection(image, candidates):
    """Visualiza la detección vertical basada en coordenada Y de la base"""
    
    if not candidates:
        print("No hay candidatos para visualizar")
        no_detection_img = image.copy()
        cv2.putText(no_detection_img, "NO SE DETECTÓ BASE DE CINTA VERTICAL", (50, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow('RESULTADO - Sin Base Detectada', no_detection_img)
        return no_detection_img
    
    result_img = image.copy()
    h_img, w_img = image.shape[:2]
    img_center_y = h_img // 2
    
    # MEJOR CANDIDATO
    best = candidates[0]
    
    # Marcar la BASE específicamente (línea horizontal roja)
    cv2.line(result_img, (best['start_x'], best['base_y']), (best['end_x'], best['base_y']), (0, 0, 255), 6)
    
    # Centro Y de imagen (línea horizontal gris)
    cv2.line(result_img, (0, img_center_y), (w_img, img_center_y), (128, 128, 128), 2)
    cv2.putText(result_img, "Centro Imagen Y", (10, img_center_y - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
    
    # Información detallada para CALIBRACIÓN VERTICAL
    distance_y = best['base_y'] - img_center_y
    
    info_lines = [
        f"DETECCIÓN VERTICAL - COORDENADA Y DE BASE",
        f"Y DETECTADA: {best['base_y']} px",
        f"Y CENTRO IMAGEN: {img_center_y} px", 
        f"DISTANCIA VERTICAL: {distance_y:+d} px",
        f"Ancho base: {best['base_width']} pixels",
        f"Centro X: {best['base_center_x']:.0f}",
        f"Dirección: {'ABAJO' if distance_y > 0 else 'ARRIBA' if distance_y < 0 else 'CENTRADO'}",
        f"Confianza: ALTA",
        f"",
        f"LÍNEA ROJA = Base de cinta detectada",
        f"LÍNEA GRIS = Centro Y de imagen",
        f"Usar distancia {distance_y:+d} px para calibración vertical"
    ]
    
    for i, line in enumerate(info_lines):
        y_pos = 25 + i * 20
        if line:  # Solo si no es línea vacía
            cv2.rectangle(result_img, (10, y_pos-12), (650, y_pos+8), (0, 0, 0), -1)
            cv2.putText(result_img, line, (15, y_pos),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Mostrar ventana principal
    cv2.namedWindow('RESULTADO - Detección Vertical Y', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('RESULTADO - Detección Vertical Y', 900, 700)
    cv2.imshow('RESULTADO - Detección Vertical Y', result_img)
    
    # Comparación
    original_resized = cv2.resize(image, (400, 300))
    result_resized = cv2.resize(result_img, (400, 300))
    comparison = np.hstack([original_resized, result_resized])
    
    cv2.putText(comparison, "ORIGINAL NUEVA", (10, 25), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(comparison, "Y DETECTADA", (410, 25), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    
    cv2.imshow('Comparación: Nueva Imagen vs Y Detectada', comparison)
    
    print(f"\n🔍 VENTANAS ABIERTAS (DETECCIÓN VERTICAL):")
    print(f"   1. 'RESULTADO - Detección Vertical Y' (principal)")
    print(f"   2. 'Comparación: Nueva Imagen vs Y Detectada'")
    print(f"   📏 LÍNEA ROJA = Coordenada Y de la base detectada")
    print(f"   📍 LÍNEA GRIS = Centro Y de la imagen")
    print(f"\n👀 Presiona cualquier tecla para continuar...")
    
    return result_img

def main():
    """Función principal con detección vertical de coordenada Y"""
    
    print("=== DETECTOR VERTICAL DE COORDENADA Y ===")
    print("Estrategia vertical específica:")
    print("1. Capturar NUEVA imagen")
    print("2. Encontrar base horizontal de la cinta")
    print("3. Detectar coordenada Y de esa base")
    print("4. Calcular distancia vertical desde centro de imagen")
    print("5. Mostrar resultado para uso en calibración vertical\n")
    
    # SIEMPRE capturar nueva imagen
    print("Capturando nueva imagen...")
    image = capture_new_image()
    
    if image is None:
        print("No se capturó ninguna imagen")
        return
    
    # Imagen capturada - procesando sin guardar archivos
    
    # Detectar posición de cinta
    candidates = detect_tape_position(image, debug=True)
    
    if candidates:
        best_candidate = candidates[0]
        
        # Calcular resultado sin guardar imágenes
        # result_img = visualize_vertical_detection(image, candidates)
        
        # Calcular resultado VERTICAL
        img_center_y = image.shape[0] // 2
        detected_y = best_candidate['base_y']
        distance_vertical = detected_y - img_center_y
        
        print(f"\n=== RESULTADO FINAL DETECCIÓN VERTICAL ===")
        print(f"✅ BASE de cinta detectada verticalmente!")
        print(f"Y detectada: {detected_y} px")
        print(f"Y centro imagen: {img_center_y} px")
        print(f"Distancia vertical: {distance_vertical:+d} px ({'abajo' if distance_vertical > 0 else 'arriba' if distance_vertical < 0 else 'centrado'})")
        print(f"Ancho base: {best_candidate['base_width']} px")
        print(f"Centro X: {best_candidate['base_center_x']:.0f} px")
        print(f"Confianza: Alta")
        
        result = {
            'success': True,
            'detected_y': detected_y,
            'distance_vertical_pixels': distance_vertical,
            'base_width_pixels': best_candidate['base_width'],
            'confidence_score': best_candidate['score']
        }
        
    else:
        print(f"\n❌ NO SE DETECTÓ BASE DE CINTA VERTICAL")
        print("Posibles causas:")
        print("- La base horizontal no está visible claramente")
        print("- La cinta está muy tapada en la parte inferior")
        print("- Los parámetros necesitan ajuste para tu setup específico")
        
        result = {
            'success': False,
            'detected_y': None,
            'distance_vertical_pixels': 0
        }
    
    print("\nPresiona cualquier tecla para cerrar...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return result

def capture_image_for_correction_vertical_debug(camera_index=0, max_retries=1):
    """Captura una imagen para corrección de posición vertical con modo debug"""
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
    
    # Captura directa - cámara siempre en índice fijo
    print(f"🎥 Intento 1/3 - Cámara vertical {camera_index}...")
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        print(f"✅ Imagen vertical capturada exitosamente desde cámara {camera_index}")
        
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
        cv2.putText(frame_con_rectangulo, "AREA DE ANALISIS VERTICAL", (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("DEBUG VERTICAL: 1. Imagen + Area de Analisis", frame_con_rectangulo)
        cv2.resizeWindow("DEBUG VERTICAL: 1. Imagen + Area de Analisis", 800, 600)
        print("🔄 1. Imagen vertical con área de análisis marcada - Presiona 'c' para continuar...")
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                break
        cv2.destroyAllWindows()
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        
        # Mostrar imagen recortada
        cv2.imshow("DEBUG VERTICAL: 2. Imagen Recortada", frame_recortado)
        cv2.resizeWindow("DEBUG VERTICAL: 2. Imagen Recortada", 800, 600)
        print("✂️ 2. Imagen recortada para análisis vertical - Presiona 'c' para continuar...")
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                break
        cv2.destroyAllWindows()
        
        return frame_recortado
    else:
        print("❌ Error: No se pudo capturar imagen vertical")
        return None

def detect_tape_position_vertical_debug(image, debug=True):
    """Detecta la posición de la cinta vertical con modo debug visual"""
    if image is None:
        return []
    
    h_img, w_img = image.shape[:2]
    img_center_y = h_img // 2
    
    print(f"🔍 Analizando imagen vertical: {w_img}x{h_img}, centro Y: {img_center_y}")
    
    # Aplicar filtros
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    
    # Mostrar canal V
    cv2.imshow("DEBUG VERTICAL: 3. Canal V (Brillo)", v_channel)
    cv2.resizeWindow("DEBUG VERTICAL: 3. Canal V (Brillo)", 800, 600)
    print("🌈 3. Canal V extraído - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # Aplicar threshold
    _, binary_img = cv2.threshold(v_channel, 30, 255, cv2.THRESH_BINARY_INV)
    
    # Mostrar imagen binaria
    cv2.imshow("DEBUG VERTICAL: 4. Imagen Binaria", binary_img)
    cv2.resizeWindow("DEBUG VERTICAL: 4. Imagen Binaria", 800, 600)
    print("🎭 4. Threshold aplicado (zonas oscuras) - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # Encontrar contornos
    contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        print("❌ No se encontraron contornos verticales")
        return []
    
    # Encontrar el contorno más grande
    main_contour = max(contours, key=cv2.contourArea)
    
    if cv2.contourArea(main_contour) < 500:
        print("❌ Contorno vertical demasiado pequeño")
        return []
    
    # Calcular BASE del rectángulo (línea inferior)
    x, y, w, h = cv2.boundingRect(main_contour)
    center_x = x + w // 2  # Centro horizontal (para visualización)
    base_y = y + h         # BASE del rectángulo (línea inferior) - ESTO ES LO IMPORTANTE
    
    print(f"📏 Región principal: {w}x{h} en ({x}, {y})")
    print(f"🔴 Base de cinta en Y={base_y}px (y={y} + h={h})")
    
    # Crear imagen con contornos sobre imagen a COLOR
    if len(image.shape) == 3:
        contour_image = image.copy()
    else:
        # Si es escala de grises, convertir a color
        contour_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    
    # Dibujar solo el contorno (no el rectángulo completo)
    cv2.drawContours(contour_image, [main_contour], -1, (0, 255, 0), 3)
    
    # Dibujar LÍNEA DE BASE (la más importante) - MUY GRUESA
    cv2.line(contour_image, (x, base_y), (x + w, base_y), (0, 0, 255), 6)  # Rojo = BASE detectada
    
    # Marcar centro de la base con círculo
    cv2.circle(contour_image, (center_x, base_y), 10, (0, 0, 255), -1)  # Rojo
    
    # Línea de referencia (centro de imagen Y)
    cv2.line(contour_image, (0, img_center_y), (w_img, img_center_y), (255, 0, 255), 4)  # Magenta = centro imagen Y
    
    # Agregar texto explicativo
    cv2.putText(contour_image, f"Centro IMG Y: {img_center_y}px", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
    cv2.putText(contour_image, f"BASE CINTA Y: {base_y}px", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(contour_image, f"DIFERENCIA Y: {base_y - img_center_y}px", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Mostrar resultado final
    cv2.imshow("DEBUG VERTICAL: 5. DETECCION FINAL", contour_image)
    cv2.resizeWindow("DEBUG VERTICAL: 5. DETECCION FINAL", 800, 600)
    print(f"✅ 5. BASE detectada en Y={base_y}px (centro imagen Y={img_center_y}px) - Presiona 'c' para continuar...")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            break
    cv2.destroyAllWindows()
    
    # Calcular distancia desde la BASE (vertical usa BASE Y)
    distance_pixels = base_y - img_center_y
    
    tape_result = {
        'center_x': center_x,
        'base_y': base_y,           # CAMBIO: usar base_y en lugar de center_y
        'distance_pixels': distance_pixels,
        'contour_area': int(cv2.contourArea(main_contour)),
        'bbox': (x, y, w, h)
    }
    
    return [tape_result]

if __name__ == "__main__":
    main()