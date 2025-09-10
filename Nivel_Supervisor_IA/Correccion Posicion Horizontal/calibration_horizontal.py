import json
import numpy as np
from tape_detector_horizontal import capture_new_image, find_tape_base_width

def create_linear_calibration():
    """Crea función lineal con tus datos de calibración"""
    
    # Tus datos de calibración
    calibration_data = [
        (0, 0.0), (-5, -13.0), (-10, -26.0), (-15, -39.0), (-20, -52.0), (-25, -66.0),
        (-30, -80.0), (-35, -93.0), (-40, -105.0), (-45, -117.0), (-50, -129.0), (-55, -140.0),
        (5, 14.0), (10, 27.0), (15, 39.0), (20, 53.0), (25, 66.0), (30, 79.0),
        (35, 92.0), (40, 103.0), (45, 114.0), (50, 126.0), (55, 138.0)
    ]
    
    print("=== CREANDO FUNCIÓN LINEAL ===")
    print("Usando tus datos de calibración...")
    
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
    
    with open('calibracion_horizontal.json', 'w') as f:
        json.dump(calibration, f, indent=2)
    
    print("✓ Función guardada en 'calibracion_horizontal.json'")
    
    # Mostrar algunos ejemplos
    print(f"\n=== EJEMPLOS DE CONVERSIÓN ===")
    test_pixels = [-140, -80, -26, 0, 27, 80, 140]
    for px in test_pixels:
        mm = a * px + b
        print(f"{px:+4.0f} px → {mm:+6.1f} mm")
    
    return calibration

def load_calibration():
    """Carga la función de calibración"""
    try:
        with open('calibracion_horizontal.json', 'r') as f:
            calibration = json.load(f)
        return calibration['coefficients']['a'], calibration['coefficients']['b']
    except:
        print("❌ No se encontró calibracion_horizontal.json")
        print("Ejecuta create_linear_calibration() primero")
        return None, None

def pixels_to_mm(pixels, a, b):
    """Convierte píxeles a milímetros usando función lineal"""
    return a * pixels + b

def measure_distance():
    """Programa principal: toma foto y mide distancia real en mm"""
    
    print("\n=== MEDICIÓN DE DISTANCIA REAL ===")
    
    # Cargar calibración
    a, b = load_calibration()
    if a is None:
        return
    
    print(f"Función cargada: mm = {a:.5f} * pixels + {b:.2f}")
    
    while True:
        print(f"\n--- NUEVA MEDICIÓN ---")
        input("Presiona ENTER para tomar foto...")
        
        # Tomar foto con tu código
        image = capture_new_image()
        if image is None:
            print("❌ Sin imagen")
            continue
        
        # Detectar con tu IA
        candidates = find_tape_base_width(image, debug=False)
        if not candidates:
            print("❌ No se detectó cinta")
            continue
        
        # Calcular distancia en píxeles
        best = candidates[0]
        img_center = image.shape[1] // 2
        distance_pixels = best['base_center_x'] - img_center
        
        # Convertir a milímetros reales
        distance_mm = pixels_to_mm(distance_pixels, a, b)
        
        # Mostrar resultado
        print(f"\n📏 RESULTADO:")
        print(f"  Distancia en píxeles: {distance_pixels:+7.1f} px")
        print(f"  Distancia REAL:       {distance_mm:+7.1f} mm")
        print(f"  Confianza IA:         {best['score']:.3f}")
        
        if abs(distance_mm) < 2:
            print(f"  Estado: ✅ CENTRADO")
        elif distance_mm > 0:
            print(f"  Estado: → {distance_mm:.1f}mm hacia la DERECHA")
        else:
            print(f"  Estado: ← {abs(distance_mm):.1f}mm hacia la IZQUIERDA")
        
        # Continuar?
        if input("\nOtra medición? (enter=sí, n=salir): ").lower() == 'n':
            break

def main():
    """Menú principal"""
    
    print("=== SISTEMA DE MEDICIÓN CON CALIBRACIÓN LINEAL ===")
    print("1. Crear calibración (ejecutar una vez)")
    print("2. Medir distancia (usar después de calibrar)")
    
    while True:
        print(f"\nOpciones:")
        print("1 = Crear calibración lineal")
        print("2 = Medir distancia real")  
        print("q = Salir")
        
        choice = input("Elección: ").strip().lower()
        
        if choice == '1':
            create_linear_calibration()
        elif choice == '2':
            measure_distance()
        elif choice == 'q':
            break
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()