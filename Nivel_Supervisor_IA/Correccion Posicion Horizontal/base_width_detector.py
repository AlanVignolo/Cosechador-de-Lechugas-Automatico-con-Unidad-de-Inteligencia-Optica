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

def scan_available_cameras():
    """Escanea cámaras disponibles en el sistema"""
    available_cameras = []
    
    print("🔍 Escaneando cámaras disponibles...")
    
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
                    print(f"✅ Cámara {i}: {w}x{h} - FUNCIONAL")
                else:
                    available_cameras.append({
                        'index': i,
                        'resolution': "Error al capturar",
                        'working': False
                    })
                    print(f"⚠️ Cámara {i}: Abierta pero no captura")
                cap.release()
        except Exception as e:
            continue
    
    if not available_cameras:
        print("❌ No se encontraron cámaras funcionales")
    
    return available_cameras

def capture_with_timeout(camera_index, timeout=5.0):
    """Captura frame con timeout para evitar que se cuelgue"""
    result = {'frame': None, 'success': False, 'cap': None}
    
    def capture_thread():
        cap = None
        try:
            cap = cv2.VideoCapture(camera_index)
            result['cap'] = cap
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    result['frame'] = frame.copy()
                    result['success'] = True
        except Exception as e:
            print(f"Error en captura: {e}")
            result['success'] = False
        finally:
            if cap is not None and cap.isOpened():
                cap.release()
                # Pequeña pausa para asegurar liberación completa
                time.sleep(0.1)
    
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
                time.sleep(0.1)
            except:
                pass
        return None
    
    return result['frame'] if result['success'] else None

def capture_image_for_correction(camera_index=1, max_retries=1):
    """Captura una imagen simple para corrección de posición horizontal con reintentos optimizado"""
    global _working_camera_cache
    
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    # Captura directa - cámara siempre en índice fijo
    print(f"🎥 Capturando desde cámara {camera_index}...")
    
    frame = capture_with_timeout(camera_index, timeout=3.0)
    
    if frame is not None:
        print(f"✅ Imagen capturada exitosamente")
        
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        return frame_recortado
    
    print("❌ Error: No se pudo capturar imagen")
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

def simple_horizontal_detection(image, debug=True):
    """
    Detección horizontal simplificada usando la misma lógica que vertical
    """
    
    if debug:
        print("\n=== DETECTOR HORIZONTAL SIMPLIFICADO ===")
    
    h_img, w_img = image.shape[:2]
    img_center_x = w_img // 2
    
    # Aplicar el mismo filtro que vertical
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    _, binary_img = cv2.threshold(v_channel, 30, 255, cv2.THRESH_BINARY_INV)
    
    # Encontrar la región oscura principal
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
    
    # Calcular centro horizontal directamente desde el contorno
    center_x = x + w // 2
    
    tape_result = {
        'base_center_x': center_x,
        'base_width': w,
        'start_x': x,
        'end_x': x + w,
        'base_y': y + h // 2,  # Centro vertical
        'distance_from_center_x': abs(center_x - img_center_x),
        'score': 0.8
    }
    
    if debug:
        print(f"✅ Centro detectado en X = {center_x} px")
        print(f"Distancia del centro: {tape_result['distance_from_center_x']} px")
    
    return [tape_result]

def get_horizontal_correction_distance(camera_index=0):
    """
    Función simplificada para corrección horizontal - solo devuelve distancia en píxeles
    Utilizada por la máquina de estados para corrección iterativa
    """
    # Capturar imagen
    image = capture_image_for_correction(camera_index)
    if image is None:
        return {'success': False, 'distance_pixels': 0, 'error': 'No se pudo capturar imagen'}
    
    # Detectar cinta con algoritmo simplificado
    candidates = simple_horizontal_detection(image, debug=False)
    
    if not candidates:
        # Si falla, intentar con el algoritmo original como respaldo
        candidates = find_tape_base_width(image, debug=False)
        if not candidates:
            return {'success': False, 'distance_pixels': 0, 'error': 'No se detectó cinta'}
    
    # Calcular distancia desde centro
    best_candidate = candidates[0]
    img_center_x = image.shape[1] // 2
    tape_center_x = best_candidate['base_center_x']
    distance = tape_center_x - img_center_x
    
    return {
        'success': True,
        'distance_pixels': int(distance),
        'confidence': best_candidate['score']
    }

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
    
    print(f"\n🔍 VENTANAS ABIERTAS (ANCHO DE BASE REAL):")
    print(f"   1. 'RESULTADO - Ancho de Base Real' (principal)")
    print(f"   2. 'Comparación: Nueva Imagen vs Base Real'")
    print(f"   📏 LÍNEA ROJA = Ancho real de la base de tu cinta")
    print(f"   📦 RECTÁNGULO VERDE = Cinta completa")
    print(f"   📍 LÍNEA AMARILLA = Centro de la cinta")
    print(f"\n👀 Presiona cualquier tecla para continuar...")
    
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
    
    cv2.imwrite('imagen_nueva_base.jpg', image)
    print("Nueva imagen guardada como 'imagen_nueva_base.jpg'\n")
    
    # Detectar usando ancho de base real
    candidates = find_tape_base_width(image, debug=True)
    
    if candidates:
        best_candidate = candidates[0]
        
        # Visualizar
        result_img = visualize_base_width_detection(image, candidates)
        cv2.imwrite('deteccion_base_real.jpg', result_img)
        
        # Calcular resultado
        img_center_x = image.shape[1] // 2
        tape_center_x = best_candidate['base_center_x']
        distance = tape_center_x - img_center_x
        
        print(f"\n=== RESULTADO FINAL CON ANCHO DE BASE REAL ===")
        print(f"✅ BASE de cinta detectada!")
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
        print(f"\n❌ NO SE DETECTÓ BASE DE CINTA")
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