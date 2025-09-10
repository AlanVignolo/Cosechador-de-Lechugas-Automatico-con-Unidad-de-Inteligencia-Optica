import json
import numpy as np
from tape_detector_vertical import capture_new_image, detect_tape_position

def create_linear_calibration():
    """Crea función lineal con tus datos de calibración vertical del archivo JSON"""
    
    print("=== CREANDO FUNCIÓN LINEAL VERTICAL ===")
    print("Cargando datos del archivo calibracion_vertical.json...")
    
    # Cargar datos del archivo JSON creado por manual_vertical_calibration.py
    try:
        with open('calibracion_vertical.json', 'r') as f:
            saved_data = json.load(f)
        
        # Extraer puntos de datos
        data_points = saved_data['data_points']
        calibration_data = [(point['position_mm'], point['detected_pixels']) for point in data_points]
        
        print(f"✓ Cargados {len(calibration_data)} puntos de calibración")
        
    except FileNotFoundError:
        print("❌ No se encontró calibracion_vertical.json")
        print("Primero ejecuta manual_vertical_calibration.py para crear los datos")
        return None
    except Exception as e:
        print(f"❌ Error cargando datos: {e}")
        return None
    
    # Extraer datos
    mm_real = np.array([d[0] for d in calibration_data])
    pixels = np.array([d[1] for d in calibration_data])
    
    # Función lineal: mm = a * pixels + b
    a, b = np.polyfit(pixels, mm_real, 1)
    
    # Verificar calidad
    predicted_mm = a * pixels + b
    errors = np.abs(mm_real - predicted_mm)
    max_error = np.max(errors)
    avg_error = np.mean(errors)
    r_squared = 1 - np.sum((mm_real - predicted_mm)**2) / np.sum((mm_real - np.mean(mm_real))**2)
    
    print(f"Función lineal: mm = {a:.5f} * pixels + {b:.2f}")
    print(f"R² = {r_squared:.6f} (muy cerca de 1.0 = perfecto)")
    print(f"Error promedio: ±{avg_error:.2f} mm")
    print(f"Error máximo: ±{max_error:.2f} mm")
    
    # Guardar función
    calibration = {
        'function': f'mm = {a:.5f} * pixels + {b:.2f}',
        'coefficients': {
            'a': float(a),
            'b': float(b)
        },
        'quality': {
            'r_squared': float(r_squared),
            'average_error_mm': float(avg_error),
            'max_error_mm': float(max_error)
        },
        'valid_range': {
            'pixels_min': float(pixels.min()),
            'pixels_max': float(pixels.max()),
            'mm_min': float(mm_real.min()),
            'mm_max': float(mm_real.max())
        }
    }
    
    with open('calibracion_vertical_lineal.json', 'w') as f:
        json.dump(calibration, f, indent=2)
    
    print("✓ Función guardada en 'calibracion_vertical_lineal.json'")
    
    # Mostrar algunos ejemplos
    print(f"\n=== EJEMPLOS DE CONVERSIÓN VERTICAL ===")
    test_pixels = [-165, -90, -30, 0, 30, 90, 165]
    for px in test_pixels:
        mm = a * px + b
        direction = "ARRIBA" if mm < 0 else "ABAJO" if mm > 0 else "CENTRO"
        print(f"{px:+4.0f} px → {mm:+6.1f} mm ({direction})")
    
    return calibration

def load_calibration():
    """Carga la función de calibración vertical"""
    try:
        with open('calibracion_vertical_lineal.json', 'r') as f:
            calibration = json.load(f)
        return calibration['coefficients']['a'], calibration['coefficients']['b']
    except:
        print("❌ No se encontró calibracion_vertical_lineal.json")
        print("Ejecuta create_linear_calibration() primero")
        return None, None

def pixels_to_mm_vertical(pixels, a, b):
    """Convierte píxeles verticales a milímetros usando función lineal"""
    return a * pixels + b

def measure_vertical_distance():
    """Programa principal: toma foto y mide distancia vertical real en mm"""
    
    print("\n=== MEDICIÓN DE DISTANCIA VERTICAL REAL ===")
    
    # Cargar calibración
    a, b = load_calibration()
    if a is None:
        return
    
    print(f"Función cargada: mm = {a:.5f} * pixels + {b:.2f}")
    print("+ = ABAJO del centro, - = ARRIBA del centro")
    
    while True:
        print(f"\n--- NUEVA MEDICIÓN VERTICAL ---")
        input("Presiona ENTER para tomar foto...")
        
        # Tomar foto con tu código de detección vertical
        image = capture_new_image()
        if image is None:
            print("❌ Sin imagen")
            continue
        
        # Detectar con tu IA vertical
        candidates = detect_tape_position(image, debug=False)
        if not candidates:
            print("❌ No se detectó cinta")
            continue
        
        # Calcular distancia vertical en píxeles
        best = candidates[0]
        img_center_y = image.shape[0] // 2
        detected_y = best['base_y']
        distance_pixels = detected_y - img_center_y
        
        # Convertir a milímetros reales
        distance_mm = pixels_to_mm_vertical(distance_pixels, a, b)
        
        # Mostrar resultado
        print(f"\n📏 RESULTADO VERTICAL:")
        print(f"  Y detectada:           {detected_y} px")
        print(f"  Y centro cámara:       {img_center_y} px")
        print(f"  Distancia en píxeles:  {distance_pixels:+7.1f} px")
        print(f"  Distancia REAL:        {distance_mm:+7.1f} mm")
        print(f"  Confianza IA:          {best['score']:.3f}")
        
        if abs(distance_mm) < 2:
            print(f"  Estado: ✅ CENTRADO VERTICALMENTE")
        elif distance_mm > 0:
            print(f"  Estado: ↓ {distance_mm:.1f}mm hacia ABAJO")
        else:
            print(f"  Estado: ↑ {abs(distance_mm):.1f}mm hacia ARRIBA")
        
        # Continuar?
        if input("\nOtra medición? (enter=sí, n=salir): ").lower() == 'n':
            break

def main():
    """Menú principal"""
    
    print("=== SISTEMA DE MEDICIÓN VERTICAL CON CALIBRACIÓN LINEAL ===")
    print("1. Crear calibración vertical (ejecutar una vez)")
    print("2. Medir distancia vertical (usar después de calibrar)")
    
    while True:
        print(f"\nOpciones:")
        print("1 = Crear calibración lineal vertical")
        print("2 = Medir distancia vertical real")  
        print("q = Salir")
        
        choice = input("Elección: ").strip().lower()
        
        if choice == '1':
            create_linear_calibration()
        elif choice == '2':
            measure_vertical_distance()
        elif choice == 'q':
            break
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()