"""
Escáner Horizontal Autónomo - Sin dependencias externas complejas
Versión ultra-simplificada que funciona independientemente
"""

import sys
import os
import threading
import time
import cv2
import numpy as np

# Solo importar lo esencial del sistema
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor', 'config'))

def scan_horizontal_with_live_camera(robot):
    """
    Función principal de escaneo horizontal autónoma
    Sin dependencias complejas - todo integrado
    """
    print("\n" + "="*60)
    print("ESCANEADO HORIZONTAL AUTONOMO")
    print("="*60)
    
    try:
        # Importar solo lo necesario dentro de la función
        from camera_manager import get_camera_manager
        from config.robot_config import RobotConfig
        
        camera_mgr = get_camera_manager()
        detections = []
        is_scanning = [False]  # Lista para que sea mutable en el hilo
        
        # Verificaciones básicas
        if not robot.is_homed:
            print("❌ Error: Robot debe estar hecho homing primero")
            return False
        
        if not robot.arm.is_in_safe_position():
            print("⚠️ Advertencia: El brazo no está en posición segura")
            user_input = input("¿Continuar de todas formas? (s/N): ").lower()
            if user_input != 's':
                print("Operación cancelada por el usuario")
                return False
        
        # Inicializar cámara
        print("Iniciando cámara...")
        if not camera_mgr.initialize_camera():
            print("❌ Error: No se pudo inicializar la cámara")
            return False
        
        if not camera_mgr.start_video_stream(fps=6):
            print("❌ Error: No se pudo iniciar video stream")
            return False
        
        print("✅ Cámara iniciada")
        
        # Velocidades lentas
        robot.cmd.set_velocities(2000, 2000)
        print("✅ Velocidades configuradas para escaneado")
        
        # SECUENCIA DE MOVIMIENTO
        print("\n📍 FASE 1: Posicionándose en el inicio...")
        
        # Ir al switch derecho (X negativos)
        print("   Moviendo hacia switch derecho...")
        result = robot.cmd.move_xy(-2000, 0)
        
        # Esperar límite derecho
        limit_message = robot.cmd.uart.wait_for_limit(timeout=30.0)
        if not (limit_message and "LIMIT_H_RIGHT_TRIGGERED" in limit_message):
            print("❌ Error: No se alcanzó el límite derecho")
            return False
        
        print("✅ Límite derecho alcanzado")
        
        # Retroceder 1cm
        print("📍 FASE 2: Retrocediendo 1cm...")
        result = robot.cmd.move_xy(10, 0)
        if not result["success"]:
            print(f"❌ Error en retroceso: {result}")
            return False
        
        time.sleep(2)
        print("✅ Retroceso completado")
        
        # Iniciar detección básica
        print("📍 FASE 3: Iniciando escaneado con video...")
        print("🎥 Video activo - Mostrando feed de cámara")
        
        is_scanning[0] = True
        last_detection_pos = [None]
        
        def video_loop():
            """Bucle de video simple"""
            detection_count = 0
            
            while is_scanning[0]:
                try:
                    frame = camera_mgr.get_latest_video_frame()
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    
                    # Procesar frame básico
                    processed = process_frame_simple(frame)
                    
                    # Detección ultra-simple
                    if detect_dark_object(processed):
                        # Obtener posición actual
                        current_pos = robot.get_current_position_relative()
                        current_x = current_pos['position_mm']['x']
                        
                        # Cooldown simple
                        if last_detection_pos[0] is None or abs(current_x - last_detection_pos[0]) > 50:
                            detection_count += 1
                            detection = {
                                'number': detection_count,
                                'position_mm': current_x,
                                'timestamp': time.time()
                            }
                            detections.append(detection)
                            last_detection_pos[0] = current_x
                            
                            print(f"🎯 CINTA #{detection_count} - Posición: {current_x:.1f}mm")
                            
                            # Marcar en video
                            cv2.circle(processed, (processed.shape[1]//2, processed.shape[0]//2), 15, (0, 255, 0), 3)
                    
                    # Mostrar info en video
                    cv2.putText(processed, f"ESCANER - Detecciones: {len(detections)}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(processed, "ESC para detener", 
                               (10, processed.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    cv2.imshow("Escaner Horizontal Autonomo", processed)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC
                        print("🛑 Usuario presionó ESC")
                        is_scanning[0] = False
                        break
                        
                except Exception as e:
                    print(f"⚠️ Error en video: {e}")
                    time.sleep(0.1)
        
        # Iniciar hilo de video
        video_thread = threading.Thread(target=video_loop)
        video_thread.daemon = True
        video_thread.start()
        
        # Movimiento hacia switch izquierdo
        print("🚀 Iniciando movimiento hacia switch izquierdo...")
        result = robot.cmd.move_xy(2000, 0)
        
        # Esperar límite izquierdo
        limit_message = robot.cmd.uart.wait_for_limit(timeout=120.0)
        
        # Detener video
        is_scanning[0] = False
        time.sleep(1)
        
        if not (limit_message and "LIMIT_H_LEFT_TRIGGERED" in limit_message):
            print("❌ Error: No se alcanzó el límite izquierdo")
            return False
        
        print("✅ Límite izquierdo alcanzado - Escaneado completo")
        
        # Mostrar resultados
        show_results(detections)
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante el escaneado: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Limpiar recursos
        try:
            is_scanning[0] = False
            camera_mgr.stop_video_stream()
            cv2.destroyAllWindows()
            robot.cmd.set_velocities(
                RobotConfig.get_normal_speed_x(),
                RobotConfig.get_normal_speed_y()
            )
            print("🔧 Recursos liberados")
        except:
            pass

def process_frame_simple(frame):
    """Procesar frame de forma ultra-simple"""
    try:
        # Rotar 90° anti-horario
        rotated = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Recortar zona central
        h, w = rotated.shape[:2]
        x1 = w // 4
        x2 = 3 * w // 4
        y1 = h // 4
        y2 = 3 * h // 4
        
        cropped = rotated[y1:y2, x1:x2]
        return cropped
    except:
        return frame

def detect_dark_object(frame):
    """Detección ultra-simple de objetos oscuros"""
    try:
        if frame is None:
            return False
        
        # Convertir a gris
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Threshold para objetos oscuros
        _, binary = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return False
        
        # Buscar contorno significativo en el centro
        frame_center_x = frame.shape[1] // 2
        center_tolerance = 50
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 300:  # Área mínima
                x, y, w, h = cv2.boundingRect(contour)
                center_x = x + w // 2
                
                # Verificar si está cerca del centro
                if abs(center_x - frame_center_x) < center_tolerance:
                    # Verificar forma vertical (cinta)
                    if h > w * 1.2:  # Más alto que ancho
                        return True
        
        return False
    except:
        return False

def show_results(detections):
    """Mostrar resultados del escaneo"""
    print(f"\n{'='*60}")
    print("🎯 RESULTADOS DEL ESCANEADO")
    print(f"{'='*60}")
    
    if not detections:
        print("❌ No se detectaron cintas")
    else:
        print(f"✅ Se detectaron {len(detections)} cintas:")
        print(f"{'#':<3} {'Posición (mm)':<15}")
        print("-" * 25)
        
        for detection in detections:
            number = detection['number']
            position = detection['position_mm']
            print(f"{number:<3} {position:<15.1f}")
        
        if len(detections) > 1:
            distances = []
            for i in range(1, len(detections)):
                dist = abs(detections[i]['position_mm'] - detections[i-1]['position_mm'])
                distances.append(dist)
            
            avg_distance = sum(distances) / len(distances)
            print(f"\n📏 Distancia promedio: {avg_distance:.1f}mm")
    
    print(f"{'='*60}")

if __name__ == "__main__":
    print("=== ESCÁNER HORIZONTAL AUTÓNOMO ===")
    print("Ejecutar desde main_robot.py")
