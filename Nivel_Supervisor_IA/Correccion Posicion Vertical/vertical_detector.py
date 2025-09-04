import cv2
import numpy as np
import json
import os
import threading
import time

# Cache global para recordar qué cámara funciona
_working_camera_cache_vertical = None

def capture_new_image(camera_index=0):
    """Alias para capture_image_for_vertical_correction - mantiene compatibilidad con otros módulos"""
    return capture_image_for_vertical_correction(camera_index)

def capture_with_timeout_vertical(camera_index, timeout=5.0):
    """Captura frame con timeout para evitar que se cuelgue - versión vertical"""
    result = {'frame': None, 'success': False}
    
    def capture_thread():
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                ret, frame = cap.read()
                if ret:
                    result['frame'] = frame
                    result['success'] = True
                cap.release()
        except Exception as e:
            print(f"Error en captura vertical: {e}")
        
    thread = threading.Thread(target=capture_thread)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        print(f"⚠️ Timeout en captura vertical de cámara {camera_index}")
        return None
    
    return result['frame'] if result['success'] else None

def scan_available_cameras_vertical():
    """Escanea cámaras disponibles - versión vertical"""
    available_cameras = []
    
    print("🔍 Escaneando cámaras disponibles (vertical)...")
    
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

def capture_image_for_vertical_correction(camera_index=0, max_retries=3):
    """Captura una imagen simple para corrección de posición vertical con reintentos optimizado"""
    global _working_camera_cache_vertical
    
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    # Usar cache si existe, sino empezar con el índice solicitado
    cameras_to_try = []
    if _working_camera_cache_vertical is not None:
        cameras_to_try.append(_working_camera_cache_vertical)
        print(f"🎯 Usando cámara vertical cacheada: {_working_camera_cache_vertical}")
    else:
        cameras_to_try.append(camera_index)
    
    for attempt in range(max_retries):
        # Probar cámaras disponibles
        for cam_idx in cameras_to_try:
            print(f"🎥 Intento {attempt + 1}/{max_retries} - Cámara vertical {cam_idx}...")
            
            frame = capture_with_timeout_vertical(cam_idx, timeout=5.0)
            
            if frame is not None:
                print(f"✅ Imagen vertical capturada exitosamente desde cámara {cam_idx}")
                
                # Actualizar cache con la cámara que funciona
                if _working_camera_cache_vertical != cam_idx:
                    _working_camera_cache_vertical = cam_idx
                    print(f"📌 Cache vertical actualizado: cámara {cam_idx}")
                
                frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                
                alto, ancho = frame_rotado.shape[:2]
                x1 = int(ancho * recorte_config['x_inicio'])
                x2 = int(ancho * recorte_config['x_fin'])
                y1 = int(alto * recorte_config['y_inicio'])
                y2 = int(alto * recorte_config['y_fin'])
                
                frame_recortado = frame_rotado[y1:y2, x1:x2]
                return frame_recortado
        
        # Solo escanear si fallan todos los intentos previos
        if attempt == 1 and len([c for c in cameras_to_try if c != camera_index]) == 0:
            print("🔍 Buscando cámaras alternativas...")
            available = scan_available_cameras_vertical()
            working_cameras = [cam['index'] for cam in available if cam['working']]
            
            # Agregar solo cámaras no probadas
            for cam_idx in working_cameras:
                if cam_idx not in cameras_to_try:
                    cameras_to_try.append(cam_idx)
        
        if attempt < max_retries - 1:
            print(f"❌ Fallo en intento vertical {attempt + 1}, esperando 2 segundos...")
            time.sleep(2)
    
    print("❌ Error: No se pudo capturar imagen vertical después de todos los intentos")
    return None

def find_tape_vertical_position(image, debug=True):
    """
    Estrategia vertical: encontrar la posición Y de la BASE de la cinta
    """
    
    if debug:
        print("\n=== DETECTOR VERTICAL DE BASE DE CINTA ===")
        print("Estrategia: encontrar coordenada Y de la base como referencia vertical")
    
    h_img, w_img = image.shape[:2]
    img_center_y = h_img // 2
    
    # Aplicar el mejor filtro (igual que horizontal)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    _, binary_img = cv2.threshold(v_channel, 30, 255, cv2.THRESH_BINARY_INV)  # hsv_muy_oscuro
    
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
                    'absolute_row': y + row_idx,  # COORDENADA Y ABSOLUTA
                    'start_x': x + seg_start,
                    'end_x': x + seg_end,
                    'width': seg_width,
                    'center_x': seg_center_x,
                    'distance_from_center_y': abs((y + row_idx) - img_center_y)
                })
    
    if not base_candidates:
        if debug:
            print("No se encontraron candidatos a base")
        return []
    
    # Ordenar por: ancho (más ancho mejor) y cercanía al centro Y
    base_candidates.sort(key=lambda b: (b['width'], -b['distance_from_center_y']), reverse=True)
    
    if debug:
        print(f"Candidatos a base encontrados: {len(base_candidates)}")
        for i, base in enumerate(base_candidates[:3]):
            print(f"  {i+1}. Y={base['absolute_row']}: ancho={base['width']}px, centro_x={base['center_x']}")
    
    # Tomar el mejor candidato y crear resultado
    best_base = base_candidates[0]
    
    tape_result = {
        'base_width': best_base['width'],
        'base_center_x': best_base['center_x'],
        'base_y': best_base['absolute_row'],  # ESTA ES LA COORDENADA Y PRINCIPAL
        'start_x': best_base['start_x'],
        'end_x': best_base['end_x'],
        'distance_from_center_y': best_base['distance_from_center_y'],
        'score': 0.8  # Score fijo
    }
    
    if debug:
        print(f"✅ Base detectada en Y = {tape_result['base_y']} px")
        print(f"Distancia vertical del centro: {tape_result['distance_from_center_y']} px")
    
    return [tape_result]

def get_vertical_correction_distance(camera_index=0):
    """
    Función simplificada para corrección vertical - solo devuelve distancia en píxeles
    Utilizada por la máquina de estados para corrección iterativa
    """
    # Capturar imagen
    image = capture_image_for_vertical_correction(camera_index)
    if image is None:
        return {'success': False, 'distance_pixels': 0, 'error': 'No se pudo capturar imagen'}
    
    # Detectar cinta
    candidates = find_tape_vertical_position(image, debug=False)
    
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
    
    cv2.imwrite('imagen_nueva_vertical.jpg', image)
    print("Nueva imagen guardada como 'imagen_nueva_vertical.jpg'\n")
    
    # Detectar usando método vertical
    candidates = find_tape_vertical_position(image, debug=True)
    
    if candidates:
        best_candidate = candidates[0]
        
        # Visualizar
        result_img = visualize_vertical_detection(image, candidates)
        cv2.imwrite('deteccion_vertical_y.jpg', result_img)
        
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

if __name__ == "__main__":
    main()