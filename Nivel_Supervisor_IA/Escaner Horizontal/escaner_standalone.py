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
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Correccion Posicion Horizontal'))

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
        
        # Resetear posición global para que coincida con x=0 del escáner
        # Esto hace que las coordenadas relativas funcionen correctamente
        robot.reset_global_position(0.0, robot.global_position['y'])
        print("📍 Posición de inicio del escáner establecida en x=0")
        
        # Iniciar detección básica
        print("📍 FASE 3: Iniciando escaneado con video...")
        print("🎥 Video activo - Mostrando feed de cámara")
        
        is_scanning[0] = True
        last_detection_pos = [None]
        
        # Sistema de tracking de estados para flags
        detection_state = {
            'current_state': None,  # 'accepted' | 'rejected' | None
            'position_buffer': [],
            'tape_segments': [],
            'flag_count': 0
        }
        
        def send_flag_for_state_change(state_type, position):
            """Enviar flag al firmware para marcar cambio de estado"""
            try:
                detection_state['flag_count'] += 1
                flag_id = detection_state['flag_count']
                
                # Enviar comando RP (snapshot) al firmware
                result = robot.cmd.get_movement_progress()
                if result.get("success"):
                    print(f"🚩 FLAG #{flag_id} enviado - {state_type} en x={position:.1f}mm")
                    return flag_id
                else:
                    print(f"❌ Error enviando flag: {result}")
                    return None
            except Exception as e:
                print(f"❌ Error en send_flag: {e}")
                return None
        
        def process_detection_state(is_accepted, current_pos):
            """Procesar cambios de estado de detección y enviar flags"""
            new_state = 'accepted' if is_accepted else 'rejected'
            
            # Detectar cambio de estado
            if detection_state['current_state'] != new_state:
                if detection_state['current_state'] == 'rejected' and new_state == 'accepted':
                    # INICIO de cinta
                    flag_id = send_flag_for_state_change("INICIO_CINTA", current_pos)
                    detection_state['position_buffer'] = [current_pos]  # Resetear buffer
                    if flag_id:
                        detection_state['tape_segments'].append({
                            'start_flag': flag_id,
                            'start_pos': current_pos,
                            'positions': [current_pos]
                        })
                
                elif detection_state['current_state'] == 'accepted' and new_state == 'rejected':
                    # FIN de cinta
                    flag_id = send_flag_for_state_change("FIN_CINTA", current_pos)
                    if flag_id and detection_state['tape_segments']:
                        # Actualizar último segmento
                        last_segment = detection_state['tape_segments'][-1]
                        last_segment['end_flag'] = flag_id
                        last_segment['end_pos'] = current_pos
                        
                        # Calcular posición media del segmento
                        if detection_state['position_buffer']:
                            avg_pos = sum(detection_state['position_buffer']) / len(detection_state['position_buffer'])
                            last_segment['center_pos'] = avg_pos
                            print(f"📏 CINTA COMPLETADA - Centro: {avg_pos:.1f}mm (de {len(detection_state['position_buffer'])} muestras)")
                
                detection_state['current_state'] = new_state
            
            # Acumular posiciones durante estado 'accepted'
            if new_state == 'accepted':
                detection_state['position_buffer'].append(current_pos)
        
        def video_loop():
            """Bucle de video con detección de estados"""
            detection_count = 0
            
            while is_scanning[0]:
                try:
                    frame = camera_mgr.get_latest_video_frame()
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    
                    # Procesar frame como el sistema de posicionamiento
                    processed = process_frame_for_detection(frame)
                    
                    # Obtener posición actual
                    current_x = robot.global_position['x']
                    
                    # Usar el detector sofisticado del sistema de posicionamiento
                    is_tape_detected = detect_sophisticated_tape(processed)
                    
                    # Procesar cambios de estado y enviar flags
                    process_detection_state(is_tape_detected, current_x)
                    
                    # Marcar detección en video
                    if is_tape_detected:
                        cv2.circle(processed, (processed.shape[1]//2, processed.shape[0]//2), 15, (0, 255, 0), 3)
                        cv2.putText(processed, "CINTA DETECTADA", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    else:
                        cv2.circle(processed, (processed.shape[1]//2, processed.shape[0]//2), 10, (0, 0, 255), 2)
                        cv2.putText(processed, "SIN CINTA", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    # Mostrar info en video
                    cv2.putText(processed, f"ESCANER - Flags: {detection_state['flag_count']}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(processed, f"Segmentos: {len(detection_state['tape_segments'])}", 
                               (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(processed, f"Posicion: {current_x:.1f}mm", 
                               (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
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
        show_results(detections, detection_state)
        
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

def process_frame_for_detection(frame):
    """Procesar frame igual que el sistema de posicionamiento"""
    try:
        # Rotar 90° anti-horario (igual que tape_detector_horizontal)
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Aplicar el mismo recorte que usa el detector de posicionamiento
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        return frame_recortado
    except:
        return frame

def detect_sophisticated_tape(frame):
    """Usar el mismo algoritmo sofisticado del sistema de posicionamiento"""
    try:
        # Importar el detector sofisticado dentro de la función para evitar errores de import
        from tape_detector_horizontal import detect_tape_position
        
        # Usar el detector sofisticado
        candidates = detect_tape_position(frame, debug=False)
        
        if candidates:
            # Si hay candidatos válidos, considerar como detección exitosa
            best_candidate = candidates[0]
            
            # Verificar que la cinta esté razonablemente centrada
            tape_center_x = best_candidate['base_center_x']
            frame_center_x = frame.shape[1] // 2
            distance_from_center = abs(tape_center_x - frame_center_x)
            
            # Debug: Imprimir información de candidatos encontrados
            print(f"🔍 DEBUG: {len(candidates)} candidatos, mejor en x={tape_center_x}, centro={frame_center_x}, dist={distance_from_center}")
            
            # Tolerancia más permisiva para el escáner (80 píxeles vs 30 para posicionamiento)
            if distance_from_center <= 80:
                print(f"✅ DEBUG: Cinta aceptada (dist={distance_from_center} <= 80)")
                return True
            else:
                print(f"❌ DEBUG: Cinta rechazada (dist={distance_from_center} > 80)")
        else:
            # Intentar con detección básica si no hay candidatos sofisticados
            basic_result = detect_basic_fallback(frame)
            if basic_result:
                print("🔄 DEBUG: Detectado con algoritmo básico")
                return True
        
        return False
        
    except Exception as e:
        print(f"⚠️ DEBUG: Error en detector sofisticado: {e}")
        # Si falla el detector sofisticado, usar detección básica como respaldo
        return detect_basic_fallback(frame)

def detect_basic_fallback(frame):
    """Detección básica como respaldo si falla el sistema sofisticado"""
    try:
        if frame is None:
            return False
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Threshold para objetos oscuros
        _, binary = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return False
        
        # Buscar contorno significativo en el centro
        frame_center_x = frame.shape[1] // 2
        center_tolerance = 60
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 200:  # Área mínima
                x, y, w, h = cv2.boundingRect(contour)
                center_x = x + w // 2
                
                # Verificar si está cerca del centro
                if abs(center_x - frame_center_x) < center_tolerance:
                    # Verificar forma vertical (cinta)
                    if h > w * 0.8:  # Más alto que ancho o similar
                        return True
        
        return False
    except:
        return False

def show_results(detections, detection_state):
    """Mostrar resultados del escaneo con información de flags"""
    # Generar reporte final con sistema de flags
    print("\n" + "="*60)
    print("📊 REPORTE FINAL DEL ESCANEADO CON FLAGS")
    print("="*60)
    print(f"🚩 Total de flags enviados: {detection_state['flag_count']}")
    print(f"📏 Segmentos de cinta detectados: {len(detection_state['tape_segments'])}")
        
    if detection_state['tape_segments']:
        print("\n🎯 CINTAS DETECTADAS CON POSICIONES CALCULADAS:")
        for i, segment in enumerate(detection_state['tape_segments'], 1):
            start_pos = segment.get('start_pos', 'N/A')
            end_pos = segment.get('end_pos', 'En progreso')
            center_pos = segment.get('center_pos', 'Calculando...')
            start_flag = segment.get('start_flag', 'N/A')
            end_flag = segment.get('end_flag', 'N/A')
                
            print(f"   📏 CINTA #{i}:")
            print(f"      🚩 Flags: Inicio={start_flag}, Fin={end_flag}")
            if isinstance(center_pos, (int, float)):
                print(f"      📍 Posiciones: Inicio={start_pos:.1f}mm, Fin={end_pos}, Centro={center_pos:.1f}mm")
            else:
                print(f"      📍 Posiciones: Inicio={start_pos}mm, Fin={end_pos}, Centro={center_pos}")
            print(f"      📊 Muestras procesadas: {len(segment.get('positions', []))}")
    else:
        print("❌ No se detectaron cintas completas")
        
    # Crear reporte compatible con sistema anterior para retrocompatibilidad
    legacy_detections = []
    for i, segment in enumerate(detection_state['tape_segments'], 1):
        if 'center_pos' in segment:
            legacy_detections.append({
                'number': i,
                'position_mm': segment['center_pos'],
                'timestamp': time.time(),
                'flags': {
                    'start': segment.get('start_flag'),
                    'end': segment.get('end_flag')
                },
                'positions_sampled': len(segment.get('positions', []))
            })
        
    return legacy_detections
    
    print(f"{'='*60}")

if __name__ == "__main__":
    print("=== ESCÁNER HORIZONTAL AUTÓNOMO ===")
    print("Ejecutar desde main_robot.py")
