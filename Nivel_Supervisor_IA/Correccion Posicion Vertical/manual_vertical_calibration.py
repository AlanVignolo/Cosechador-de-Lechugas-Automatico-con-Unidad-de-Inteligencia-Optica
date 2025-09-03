import json
import numpy as np

def main():
    """Calibración vertical manual súper simple"""
    
    print("=== CALIBRACIÓN VERTICAL MANUAL ===")
    print("1. Ejecuta tu programa vertical_detector.py")
    print("2. Anota la 'Distancia vertical' en píxeles que te da")
    print("3. Ingresa aquí: posición real (mm) y píxeles detectados")
    print("4. Repite para todas las posiciones verticales")
    print("5. Creamos la función automáticamente\n")
    
    # Posiciones verticales sugeridas
    positions_suggested = [0, -5, -10, -15, -20, -25, -30, -35, -40, -45, -50, -55, -60,
                          5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
    
    print("Posiciones verticales sugeridas:", positions_suggested)
    print("+ = ABAJO del centro, - = ARRIBA del centro")
    print("(No es obligatorio hacer todas, con 8-10 ya alcanza)\n")
    
    calibration_data = []
    
    while True:
        print(f"\n--- PUNTO VERTICAL {len(calibration_data) + 1} ---")
        
        # Ingresar datos manualmente
        try:
            pos_mm = float(input("Posición REAL en mm (0=centro, +=abajo, -=arriba): "))
            pixels = float(input("Píxeles detectados por vertical_detector.py: "))
        except KeyboardInterrupt:
            break
        except:
            print("Número inválido")
            continue
        
        # Guardar
        calibration_data.append({
            'position_mm': pos_mm,
            'detected_pixels': pixels
        })
        
        direction = "ABAJO" if pos_mm > 0 else "ARRIBA" if pos_mm < 0 else "CENTRO"
        print(f"✓ Guardado: {pos_mm:+.0f}mm ({direction}) → {pixels:+.1f}px")
        
        # Continuar?
        if input("Otro punto? (enter=sí, n=terminar): ").lower() == 'n':
            break
    
    if len(calibration_data) < 3:
        print("❌ Necesitas al menos 3 puntos")
        return
    
    print(f"\n=== DATOS VERTICALES INGRESADOS: {len(calibration_data)} puntos ===")
    for i, data in enumerate(calibration_data, 1):
        direction = "ABAJO" if data['position_mm'] > 0 else "ARRIBA" if data['position_mm'] < 0 else "CENTRO"
        print(f"{i:2d}. {data['position_mm']:+6.0f}mm ({direction:>5s}) → {data['detected_pixels']:+8.1f}px")
    
    # Crear función lineal: mm = a * pixels + b
    pixels = np.array([d['detected_pixels'] for d in calibration_data])
    mm_real = np.array([d['position_mm'] for d in calibration_data])
    
    # Regresión lineal
    a, b = np.polyfit(pixels, mm_real, 1)
    
    # Calcular calidad
    predicted = a * pixels + b
    error = np.abs(mm_real - predicted)
    max_error = np.max(error)
    avg_error = np.mean(error)
    
    print(f"\n=== FUNCIÓN VERTICAL CREADA ===")
    print(f"mm = {a:.4f} * pixels + {b:.2f}")
    print(f"Error promedio: ±{avg_error:.1f}mm")
    print(f"Error máximo: ±{max_error:.1f}mm")
    
    # Guardar en archivo
    result = {
        'function': f'mm = {a:.4f} * pixels + {b:.2f}',
        'coefficients': [float(a), float(b)],
        'data_points': calibration_data,
        'errors': {
            'average_mm': float(avg_error),
            'maximum_mm': float(max_error)
        }
    }
    
    with open('calibracion_vertical.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n✓ Guardado en calibracion_vertical.json")
    
    # Mostrar ejemplos
    print(f"\n=== EJEMPLOS ===")
    for px in [-50, -25, 0, 25, 50]:
        mm = a * px + b
        direction = "ARRIBA" if mm < 0 else "ABAJO" if mm > 0 else "CENTRO"
        print(f"{px:+4.0f}px → {mm:+6.1f}mm ({direction})")

if __name__ == "__main__":
    main()