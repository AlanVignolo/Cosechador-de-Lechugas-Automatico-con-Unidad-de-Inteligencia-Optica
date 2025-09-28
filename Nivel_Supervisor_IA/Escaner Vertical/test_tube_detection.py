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
    
    # Diferentes configuraciones para probar (basadas en feedback del usuario)
    configs = [
        {
            'name': 'Baja Saturación Estricta (Recomendado)',
            'saturacion_threshold': 25,
            'area_min': 100,
            'area_max': 3000,
            'morfologia': False
        },
        {
            'name': 'Baja Saturación Original',
            'saturacion_threshold': 40,
            'area_min': 200,
            'area_max': 5000,
            'morfologia': False
        },
        {
            'name': 'Baja Saturación con Morfología',
            'saturacion_threshold': 30,
            'area_min': 150,
            'area_max': 4000,
            'morfologia': True
        },
        {
            'name': 'Blancos Brillantes HSV',
            'hsv_lower': [0, 0, 160],
            'hsv_upper': [180, 60, 255],
            'area_min': 200,
            'area_max': 4000
        }
    ]
    
    results = []
    
    for i, config in enumerate(configs):
        print(f"\nProbando configuración {i+1}: {config['name']}")
        
        # Aplicar filtro según configuración
        if 'hsv_lower' in config:
            # Filtro HSV
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            lower = np.array(config['hsv_lower'])
            upper = np.array(config['hsv_upper'])
            mask = cv2.inRange(hsv, lower, upper)
        elif 'saturacion_threshold' in config:
            # Filtro de baja saturación (nuevo método principal)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            s_channel = hsv[:,:,1]  # Canal de saturación
            _, mask = cv2.threshold(s_channel, config['saturacion_threshold'], 255, cv2.THRESH_BINARY_INV)
            
            # Aplicar morfología si está habilitada
            if config.get('morfologia', False):
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        else:
            # Filtro threshold en gris (fallback)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, config.get('gray_threshold', 150), 255, cv2.THRESH_BINARY)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filtrar por área
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if config['area_min'] <= area <= config['area_max']:
                valid_contours.append(contour)
        
        print(f"  Contornos encontrados: {len(contours)}")
        print(f"  Contornos válidos (área {config['area_min']}-{config['area_max']}): {len(valid_contours)}")
        
        # Crear imagen resultado
        result_img = image.copy()
        
        # Dibujar todos los contornos en rojo
        cv2.drawContours(result_img, contours, -1, (0, 0, 255), 1)
        
        # Dibujar contornos válidos en verde
        cv2.drawContours(result_img, valid_contours, -1, (0, 255, 0), 2)
        
        # Si hay contornos válidos, marcar el más grande
        if valid_contours:
            largest = max(valid_contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            center_y = y + h // 2
            
            cv2.rectangle(result_img, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.circle(result_img, (x + w//2, center_y), 5, (255, 0, 0), -1)
            
            results.append({
                'config': config['name'],
                'center_y': center_y,
                'area': cv2.contourArea(largest),
                'bbox': (x, y, w, h)
            })
            
            print(f"  Mejor candidato: Y={center_y}, Área={cv2.contourArea(largest):.0f}")
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
