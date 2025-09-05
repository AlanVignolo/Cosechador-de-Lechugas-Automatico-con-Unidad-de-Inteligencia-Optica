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
            cap = cv2.VideoCapture(camera_index)
            result['cap'] = cap
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
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

def detect_tape_position(image, debug=True):
    """
    Detección de posición de cinta usando algoritmo unificado
    """
    
    if debug:
        print("\n=== DETECTOR DE POSICIÓN DE CINTA ===")
    
    h_img, w_img = image.shape[:2]
    img_center_y = h_img // 2
    
    # Aplicar el mejor filtro (igual que horizontal)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:,:,2]
    _, binary_img = cv2.threshold(v_channel, 30, 255, cv2.THRESH_BINARY_INV)  # hsv_muy_oscuro
    
    if debug:
        print("Usando filtro hsv_muy_oscuro (el más limpio)")
    
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
    
    # Calcular centro y posición directamente desde el contorno (versión vertical)
    center_x = x + w // 2
    center_y = y + h // 2  # Para corrección vertical usamos Y
    
    tape_result = {
        'base_center_x': center_x,
        'base_y': center_y,  # Coordenada Y para corrección vertical
        'base_width': w,
        'start_x': x,
        'end_x': x + w,
        'distance_from_center_y': abs(center_y - img_center_y),
        'score': 0.8
    }
    
    if debug:
        print(f"✅ Centro detectado en Y = {center_y} px")
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

if __name__ == "__main__":
    main()