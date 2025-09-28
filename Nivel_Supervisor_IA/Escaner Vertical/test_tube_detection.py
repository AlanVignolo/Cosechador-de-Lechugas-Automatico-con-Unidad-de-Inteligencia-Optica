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
        }
    ]
    
    results = []
    
    for i, config in enumerate(configs):
        print(f"\nProbando configuración {i+1}: {config['name']}")
        
        # Aplicar filtro según configuración - NUEVOS MÉTODOS
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if config['filter_type'] == 'template_tubo':
            # Template matching para tubo
            tubo_template = np.ones((20, 60), dtype=np.uint8) * 255
            tubo_template = cv2.rectangle(tubo_template, (5, 5), (55, 15), 0, 2)
            tubo_match = cv2.matchTemplate(gray, tubo_template, cv2.TM_CCOEFF_NORMED)
            _, mask = cv2.threshold((tubo_match * 255).astype(np.uint8), 100, 255, cv2.THRESH_BINARY)
            
        elif config['filter_type'] == 'template_tapa':
            # Template matching para tapa
            tapa_template = np.ones((40, 25), dtype=np.uint8) * 255
            tapa_template = cv2.rectangle(tapa_template, (5, 5), (20, 35), 0, 2)
            tapa_match = cv2.matchTemplate(gray, tapa_template, cv2.TM_CCOEFF_NORMED)
            _, mask = cv2.threshold((tapa_match * 255).astype(np.uint8), 80, 255, cv2.THRESH_BINARY)
            
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
            
        else:
            # Fallback a threshold simple
            _, mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # ANÁLISIS DE RECTÁNGULOS (igual que en detector principal)
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
