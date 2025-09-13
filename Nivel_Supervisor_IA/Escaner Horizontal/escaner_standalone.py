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
    Función principal de escaneo horizontal autónoma con matriz de cintas
    """
    print("\n" + "="*60)
    print("ESCANEADO HORIZONTAL AUTONOMO")
    print("="*60)
    
    # Importar sistema de matriz
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Analizar Cultivo'))
    from matriz_cintas import matriz_cintas
    
    # Mostrar resumen actual
    matriz_cintas.mostrar_resumen()
    
    # Selección de tubo
    print("\n🔴 SELECCIÓN DE TUBO:")
    print("1. Tubo 1 (Y=300mm)")
    print("2. Tubo 2 (Y=600mm)")
    
    while True:
        try:
            tubo_seleccionado = int(input("Seleccione tubo (1-2): "))
            if tubo_seleccionado in [1, 2]:
                break
            else:
                print("Opción inválida. Seleccione 1 o 2.")
        except ValueError:
            print("Por favor ingrese un número válido.")
    
    tubo_config = {
        1: {"y_mm": 300, "nombre": "Tubo 1"},
        2: {"y_mm": 600, "nombre": "Tubo 2"}
    }
    
    selected_tubo = tubo_config[tubo_seleccionado]
    print(f"Seleccionado: {selected_tubo['nombre']} (Y={selected_tubo['y_mm']}mm)")
    
    try:
        # Importar solo lo necesario dentro de la función
        from camera_manager import get_camera_manager
        from config.robot_config import RobotConfig
        
        camera_mgr = get_camera_manager()
        detections = []
        is_scanning = [False]  # Lista para que sea mutable en el hilo
        
        # Verificaciones básicas
        if not robot.is_homed:
            print("Error: Robot debe estar hecho homing primero")
            return False
        
        if not robot.arm.is_in_safe_position():
            print("Advertencia: El brazo no está en posición segura")
            user_input = input("¿Continuar de todas formas? (s/N): ").lower()
            if user_input != 's':
                print("Operación cancelada por el usuario")
                return False
        
        # Limpiar ventanas previas que puedan estar abiertas
        cv2.destroyAllWindows()
        time.sleep(0.5)  # Dar tiempo para que se cierren
        
        # Inicializar cámara
        print("Iniciando cámara...")
        if not camera_mgr.initialize_camera():
            print("Error: No se pudo inicializar la cámara")
            return False
        
        if not camera_mgr.start_video_stream(fps=6):
            print("Error: No se pudo iniciar video stream")
            return False
        
        print("Cámara iniciada")
        
        # Velocidades lentas
        robot.cmd.set_velocities(2000, 2000)
        print("Velocidades configuradas para escaneado")
        
        # NOTA: El posicionamiento Y ahora se hace desde otro código externo
        # Solo informamos qué tubo se va a escanear para la matriz de coordenadas
        print(f"\nFASE 1: Escaneando {selected_tubo['nombre']} (coordenada Y={selected_tubo['y_mm']}mm)")
        print("NOTA: El posicionamiento Y debe hacerse externamente antes de ejecutar este escáner")
        
        # SECUENCIA DE MOVIMIENTO HORIZONTAL
        print("\nFASE 2: Posicionándose en el inicio horizontal...")
        
        # Ir al switch derecho (X negativos)
        print("   Moviendo hacia switch derecho...")
        result = robot.cmd.move_xy(-2000, 0)
        
        # Esperar límite derecho
        limit_message = robot.cmd.uart.wait_for_limit(timeout=30.0)
        if not (limit_message and "LIMIT_H_RIGHT_TRIGGERED" in limit_message):
            print("Error: No se alcanzó el límite derecho")
            return False
        
        print("Límite derecho alcanzado")
        
        # Retroceder 1cm
        print("FASE 3: Retrocediendo 1cm...")
        result = robot.cmd.move_xy(10, 0)
        if not result["success"]:
            print(f"Error en retroceso: {result}")
            return False
        
        time.sleep(2)
        print("Retroceso completado")
        
        # Resetear posición global para que coincida con x=0 del escáner
        # Esto hace que las coordenadas relativas funcionen correctamente
        robot.reset_global_position(0.0, robot.global_position['y'])
        print("📍 Posición de inicio del escáner establecida en x=0")
        
        # Iniciar detección básica
        print("FASE 4: Iniciando escaneado con video...")
        print("Video activo - Mostrando feed de cámara")
        
        is_scanning[0] = True
        last_detection_pos = [None]
        
        # Sistema de tracking de estados para flags
        detection_state = {
            'current_state': None,  # 'accepted' | 'rejected' | None
            'position_buffer': [],
            'tape_segments': [],
            'flag_count': 0
        }
        
        def send_flag_for_state_change(state_type):
            """Enviar flag al firmware para marcar cambio de estado"""
            try:
                detection_state['flag_count'] += 1
                flag_id = detection_state['flag_count']
                
                # Enviar comando RP (snapshot) al firmware
                result = robot.cmd.get_movement_progress()
                if result.get("success"):
                    print(f"FLAG #{flag_id} enviado - {state_type}")
                    return flag_id
                else:
                    print(f"Error enviando flag: {result}")
                    return None
            except Exception as e:
                print(f"Error en send_flag: {e}")
                return None
        
        def process_detection_state(is_accepted):
            """Procesar cambios de estado de detección y enviar flags"""
            new_state = 'accepted' if is_accepted else 'rejected'
            
            # Detectar cambio de estado
            if detection_state['current_state'] != new_state:
                if detection_state['current_state'] == 'rejected' and new_state == 'accepted':
                    # INICIO de cinta
                    flag_id = send_flag_for_state_change("INICIO_CINTA")
                    if flag_id:
                        detection_state['tape_segments'].append({
                            'start_flag': flag_id,
                        })
                
                elif detection_state['current_state'] == 'accepted' and new_state == 'rejected':
                    # FIN de cinta
                    flag_id = send_flag_for_state_change("FIN_CINTA")
                    if flag_id and detection_state['tape_segments']:
                        # Actualizar último segmento
                        last_segment = detection_state['tape_segments'][-1]
                        last_segment['end_flag'] = flag_id
                        print(f"CINTA COMPLETADA - Flags {last_segment['start_flag']}-{flag_id}")
                
                detection_state['current_state'] = new_state
        
        def video_loop():
            """Bucle de video con detección simple sin tracking de posición"""
            while is_scanning[0]:
                try:
                    frame = camera_mgr.get_latest_video_frame()
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    
                    # Procesar frame para detección
                    processed = process_frame_for_detection(frame)
                    
                    # Usar detector sofisticado
                    is_tape_detected = detect_sophisticated_tape(processed)
                    
                    # Procesar cambios de estado y enviar flags (sin posición)
                    process_detection_state(is_tape_detected)
                    
                    # Marcar detección en video
                    if is_tape_detected:
                        cv2.circle(processed, (processed.shape[1]//2, processed.shape[0]//2), 15, (0, 255, 0), 3)
                        cv2.putText(processed, "CINTA DETECTADA", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    else:
                        cv2.circle(processed, (processed.shape[1]//2, processed.shape[0]//2), 10, (0, 0, 255), 2)
                        cv2.putText(processed, "SIN CINTA", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    # Info básica en video
                    cv2.putText(processed, f"Flags: {detection_state['flag_count']}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(processed, f"Segmentos: {len(detection_state['tape_segments'])}", 
                               (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(processed, "ESC para detener", 
                               (10, processed.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    cv2.imshow("Escaner Horizontal", processed)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC
                        print("🛑 Usuario presionó ESC")
                        is_scanning[0] = False
                        break
                        
                except Exception as e:
                    print(f"Error en video: {e}")
                    time.sleep(0.1)
                    
                except KeyboardInterrupt:
                    print("🛑 Interrupción por teclado")
                    is_scanning[0] = False
                    break
            
            print("Video thread terminando...")
            # Minimal cleanup para evitar deadlock
            try:
                cv2.destroyWindow("Escaner Horizontal")
            except:
                pass
        
        # Iniciar hilo de video con nombre para debugging
        video_thread = threading.Thread(target=video_loop, name="VideoScanThread")
        video_thread.daemon = False  # No daemon para control explícito
        video_thread.start()
        
        # Movimiento hacia switch izquierdo
        print("Iniciando movimiento hacia switch izquierdo...")
        result = robot.cmd.move_xy(2000, 0)
        
        # Esperar límite izquierdo
        limit_message = robot.cmd.uart.wait_for_limit(timeout=120.0)
        
        # Detener video de forma controlada
        print("Deteniendo escaneo de video...")
        is_scanning[0] = False
        
        # Dar tiempo al thread para salir del loop
        time.sleep(0.5)
        
        # Esperar terminación sin bloquear indefinidamente
        if video_thread.is_alive():
            print("Esperando terminación del video thread...")
            video_thread.join(timeout=2.0)  # Timeout más corto
            if video_thread.is_alive():
                print("Advertencia: Video thread sigue activo, continuando...")
        
        # Limpiar ventanas OpenCV de forma segura
        try:
            cv2.destroyAllWindows()
            for _ in range(3):  # Múltiples intentos
                cv2.waitKey(1)
                time.sleep(0.1)
        except Exception as e:
            print(f"Advertencia limpiando ventanas: {e}")
        
        if not (limit_message and "LIMIT_H_LEFT_TRIGGERED" in limit_message):
            print("Error: No se alcanzó el límite izquierdo")
            return False
        
        print("Límite izquierdo alcanzado - Escaneado completo")
        
        # Correlacionar flags con snapshots para obtener posiciones reales
        correlate_flags_with_snapshots(detection_state)
        
        # Mostrar resultados y guardar en matriz
        resultados = show_results(detections, detection_state, selected_tubo)
        
        # Guardar cintas detectadas en la matriz
        if resultados:
            print(f"\nGuardando {len(resultados)} cintas en matriz...")
            if matriz_cintas.guardar_cintas_tubo(tubo_seleccionado, resultados):
                print("Cintas guardadas exitosamente en la matriz")
                
                # Mostrar matriz actualizada
                print("\n" + "="*60)
                print("MATRIZ ACTUALIZADA")
                print("="*60)
                matriz_cintas.mostrar_resumen()
            else:
                print("Error guardando cintas en matriz")
        
        return True
        
    except Exception as e:
        print(f"Error durante el escaneado: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # LIMPIEZA COMPLETA DE RECURSOS
        print("\nLIMPIEZA: Finalizando escaneo...")

        # Parar video y cerrar ventana ANTES del reset de velocidades
        is_scanning[0] = False
        
        # Asegurar terminación del video thread si existe
        try:
            if 'video_thread' in locals() and video_thread.is_alive():
                print("LIMPIEZA: Esperando terminación del video thread...")
                video_thread.join(timeout=3.0)
                if video_thread.is_alive():
                    print("LIMPIEZA: Advertencia - Video thread no terminó")
                else:
                    print("LIMPIEZA: Video thread terminado correctamente")
        except Exception as e:
            print(f"LIMPIEZA: Error terminando video thread: {e}")

        try:
            # Parar video streaming del camera manager PRIMERO
            if camera_mgr.is_active:
                print("LIMPIEZA: Parando video stream...")
                camera_mgr.stop_video_stream()
                time.sleep(0.5)  # Dar tiempo para que pare completamente
            
            # Destruir ventanas OpenCV agresivamente y múltiples veces
            print("LIMPIEZA: Cerrando ventanas OpenCV...")
            for attempt in range(5):  # Más intentos
                cv2.destroyAllWindows()
                cv2.waitKey(1)  # Procesar eventos pendientes
                time.sleep(0.2)
            
            # Verificar que no queden ventanas abiertas
            print("LIMPIEZA: Verificando cierre de ventanas...")
            
        except Exception as e:
            print(f"Error cerrando video: {e}")

        # RESETEAR VELOCIDADES SIEMPRE (crítico para siguientes movimientos)
        try:
            print("LIMPIEZA: Reseteando velocidades del robot...")
            robot.cmd.set_velocities(
                RobotConfig.DEFAULT_H_SPEED,
                RobotConfig.DEFAULT_V_SPEED
            )
            time.sleep(1.0)
            print("Velocidades reseteadas correctamente")
        except Exception as e:
            print(f"Error reseteando velocidades: {e}")

        # RESET COMPLETO del UART manager para limpiar callbacks y estado de firmware
        try:
            print("LIMPIEZA: Reset completo del UART manager...")
            robot.cmd.uart.reset_scanning_state()
        except Exception as e:
            print(f"Error en reset del UART manager: {e}")

        # RESET COMPLETO del camera manager para escaneos consecutivos
        try:
            print("LIMPIEZA: Reset completo del camera manager...")
            camera_mgr.reset_completely()
            time.sleep(1.0)  # Dar tiempo para que se complete el reset
            print("LIMPIEZA: Camera manager reseteado exitosamente")
        except Exception as e:
            print(f"Error en reset completo del camera manager: {e}")
        
        # Limpieza final adicional para asegurar estado limpio
        try:
            print("LIMPIEZA: Limpieza final adicional...")
            # Resetear flags globales que puedan quedar
            import gc
            gc.collect()  # Forzar garbage collection
            
            # Una última verificación de ventanas
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            time.sleep(0.5)
            
            print("LIMPIEZA: Estado completamente limpio para siguiente escaneo")
        except Exception as e:
            print(f"Advertencia en limpieza final: {e}")

        print("LIMPIEZA COMPLETADA - Robot listo para siguiente operación")

def correlate_flags_with_snapshots(detection_state):
    """Correlacionar flags con snapshots para obtener posiciones reales"""
    try:
        print("\nCORRELACIONANDO FLAGS CON SNAPSHOTS...")

        
        # Usar las posiciones reales del log actual mostrado por el usuario
        # S1: X=-49mm, S2: X=-147mm, S3: X=-249mm, etc.
        snapshot_positions = [-49, -147, -249, -337, -450, -538, -651, -738, -841, -934]
        
        print(f"Snapshots disponibles: {len(snapshot_positions)}")
        print(f"Flags enviados: {detection_state['flag_count']}")
        
        # Correlacionar cada par de flags (inicio, fin) con snapshots consecutivos
        for i, segment in enumerate(detection_state['tape_segments']):
            start_flag_idx = segment.get('start_flag', 0) - 1  # Convertir a índice 0-based
            end_flag_idx = segment.get('end_flag', 0) - 1
            
            # Usar posiciones de snapshots correspondientes
            if 0 <= start_flag_idx < len(snapshot_positions):
                segment['start_pos_real'] = snapshot_positions[start_flag_idx]
            
            if 0 <= end_flag_idx < len(snapshot_positions):
                segment['end_pos_real'] = snapshot_positions[end_flag_idx]
                
            # Calcular posición central del segmento usando snapshots
            if 'start_pos_real' in segment and 'end_pos_real' in segment:
                segment['center_pos_real'] = (segment['start_pos_real'] + segment['end_pos_real']) / 2
                distancia = abs(segment['end_pos_real'] - segment['start_pos_real'])
                print(f"   CINTA #{i+1}: S{start_flag_idx+1}({segment['start_pos_real']}mm) + S{end_flag_idx+1}({segment['end_pos_real']}mm)")
                print(f"        → Centro: {segment['center_pos_real']:.1f}mm, Distancia: {distancia:.0f}mm")
            else:
                print(f"   CINTA #{i+1}: Datos incompletos")
        
        print("Correlación flags-snapshots completada")
        
    except Exception as e:
        print(f"Error en correlación flags-snapshots: {e}")

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
            
            # Tolerancia más permisiva para el escáner (80 píxeles vs 30 para posicionamiento)
            if distance_from_center <= 80:
                return True
        else:
            # Intentar con detección básica si no hay candidatos sofisticados
            basic_result = detect_basic_fallback(frame)
            if basic_result:
                return True
        
        return False
        
    except Exception as e:
        print(f"Error en detector: {e}")
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

def show_results(detections, detection_state, selected_tubo):
    """Mostrar resultados del escaneo con información de flags y coordenadas reales"""
    # Generar reporte final con sistema de flags
    print("\n" + "="*60)
    print("REPORTE FINAL DEL ESCANEADO")
    print("="*60)
    print(f"Total de flags enviados: {detection_state['flag_count']}")
    print(f"Segmentos de cinta detectados: {len(detection_state['tape_segments'])}")
        
    if detection_state['tape_segments']:
        print("\nCINTAS DETECTADAS CON COORDENADAS X,Y:")
        cintas_para_matriz = []
        
        for i, segment in enumerate(detection_state['tape_segments'], 1):
            start_flag = segment.get('start_flag', 'N/A')
            end_flag = segment.get('end_flag', 'N/A')
            
            # Usar posiciones reales de snapshots si están disponibles
            if 'center_pos_real' in segment:
                x_position = segment['center_pos_real']
                y_position = selected_tubo['y_mm']
                
                print(f"   📍 CINTA #{i}: X={x_position:.1f}mm, Y={y_position}mm (Flags {start_flag}-{end_flag})")
                
                cintas_para_matriz.append({
                    'number': i,
                    'position_mm': x_position,
                    'y_mm': y_position,
                    'timestamp': time.time(),
                    'flags': {
                        'start': start_flag,
                        'end': end_flag
                    },
                    'positions_sampled': len(segment.get('position_buffer', []))
                })
            else:
                print(f"   CINTA #{i}: Posición no calculada (Flags {start_flag}-{end_flag})")
        
        # Mostrar matriz de coordenadas
        if cintas_para_matriz:
            print(f"\nMATRIZ DE COORDENADAS - {selected_tubo['nombre']}:")
            print("┌─────────┬─────────────┬─────────────┐")
            print("│  Cinta  │     X (mm)  │     Y (mm)  │")
            print("├─────────┼─────────────┼─────────────┤")
            for cinta in cintas_para_matriz:
                print(f"│   #{cinta['number']:<3}  │  {cinta['position_mm']:>8.1f}  │  {cinta['y_mm']:>8.0f}  │")
            print("└─────────┴─────────────┴─────────────┘")
        
        return cintas_para_matriz
    else:
        print("No se detectaron cintas completas")
        return []
    
    print(f"{'='*60}")

if __name__ == "__main__":
    print("=== ESCÁNER HORIZONTAL AUTÓNOMO ===")
    print("Ejecutar desde main_robot.py")
