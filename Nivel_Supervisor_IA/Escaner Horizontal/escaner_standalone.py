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
        
        # Variables de control para el video thread - ÚNICO POR ESCANEO
        import uuid
        scan_id = str(uuid.uuid4())[:8]
        is_scanning = [True]
        video_thread = None
        
        print(f"🔍 Iniciando escaneo ID: {scan_id}")
        
        last_detection_pos = [None]
        
        # Sistema de tracking de estados para flags
        detection_state = {
            'current_state': None,  # 'accepted' | 'rejected' | None
            'position_buffer': [],
            'tape_segments': [],
            'flag_count': 0,
            'uart_ref': robot.cmd.uart
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
            thread_name = threading.current_thread().name
            print(f"[{scan_id}][{thread_name}] Video thread iniciado")
            
            try:
                frame_count = 0
                while is_scanning[0]:
                    try:
                        frame = camera_mgr.get_latest_video_frame()
                        if frame is None:
                            print(f"[{scan_id}][{thread_name}] Frame {frame_count}: NONE - cámara no disponible")
                            time.sleep(0.05)
                            continue
                        
                        frame_count += 1
                        
                        # Debug cada 30 frames
                        if frame_count % 30 == 0:
                            print(f"[{scan_id}][{thread_name}] Frame {frame_count} - Flags: {detection_state['flag_count']}")
                        
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
                        cv2.putText(processed, f"ID: {scan_id}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                        cv2.putText(processed, f"Flags: {detection_state['flag_count']}", 
                                   (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        cv2.putText(processed, f"Segmentos: {len(detection_state['tape_segments'])}", 
                                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        cv2.putText(processed, f"Frame: {frame_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # Mostrar video solo si no hay ventanas bloqueadas
                        try:
                            cv2.imshow(f"Escaner Horizontal [{scan_id}]", processed)
                            key = cv2.waitKey(1) & 0xFF
                            if key == 27:  # ESC
                                print(f"[{scan_id}] 🛑 Usuario presionó ESC")
                                is_scanning[0] = False
                                break
                        except Exception as cv_err:
                            print(f"[{scan_id}][{thread_name}] Error OpenCV: {cv_err}")
                            time.sleep(0.1)
                            
                    except Exception as e:
                        print(f"[{scan_id}][{thread_name}] Error en video: {e}")
                        time.sleep(0.1)
                        
                    except KeyboardInterrupt:
                        print(f"[{scan_id}] 🛑 Interrupción por teclado")
                        is_scanning[0] = False
                        break
                        
            finally:
                print(f"[{scan_id}][{thread_name}] Video thread finalizando... (Total frames: {frame_count})")
                # Limpieza garantizada
                try:
                    cv2.destroyWindow(f"Escaner Horizontal [{scan_id}]")
                    cv2.destroyAllWindows()  # Forzar cierre de todas las ventanas
                    cv2.waitKey(1)
                except Exception as cleanup_err:
                    print(f"[{scan_id}][{thread_name}] Error en limpieza: {cleanup_err}")
                print(f"[{scan_id}][{thread_name}] Video thread terminado completamente")
        
        # KILLER DE THREADS ZOMBIE ANTES DE INICIAR NUEVO ESCANEO
        print(f"[{scan_id}] PRE-ESCANEO: Limpiando threads zombie...")
        zombie_count = 0
        for thread in threading.enumerate():
            if thread.name.startswith("VideoScanThread") and thread != threading.current_thread():
                if thread.is_alive():
                    zombie_count += 1
                    print(f"[{scan_id}] PRE-ESCANEO: ⚠️ Thread zombie detectado: {thread.name}")
        
        if zombie_count > 0:
            print(f"[{scan_id}] PRE-ESCANEO: 🧟 Detectados {zombie_count} threads zombie!")
            print(f"[{scan_id}] PRE-ESCANEO: Destruyendo TODAS las ventanas OpenCV...")
            cv2.destroyAllWindows()
            for _ in range(50):  # Más agresivo
                cv2.waitKey(1)
                time.sleep(0.02)
            time.sleep(1.0)  # Pausa para que mueran los threads
        
        # Iniciar hilo de video con nombre único
        video_thread_name = f"VideoScanThread_{scan_id}"
        video_thread = threading.Thread(target=video_loop, name=video_thread_name)
        video_thread.daemon = False  # No daemon para control explícito
        video_thread.start()
        print(f"[{scan_id}] Nuevo video thread iniciado: {video_thread_name}")
        
        # Movimiento hacia switch izquierdo
        print("Iniciando movimiento hacia switch izquierdo...")
        result = robot.cmd.move_xy(2000, 0)
        
        # Esperar límite izquierdo
        limit_message = robot.cmd.uart.wait_for_limit(timeout=120.0)
        
        # Detener video de forma controlada
        print("Deteniendo escaneo de video...")
        is_scanning[0] = False
        
        # Dar tiempo al thread para salir del loop
        time.sleep(0.2)
        
        # Esperar terminación con intentos múltiples
        for attempt in range(3):
            if not video_thread.is_alive():
                print("Video thread terminó correctamente")
                break
            
            print(f"Esperando terminación del video thread (intento {attempt + 1}/3)...")
            video_thread.join(timeout=1.0)
            
            if not video_thread.is_alive():
                print("Video thread terminó correctamente")
                break
            elif attempt == 2:
                print("ERROR: Video thread no terminó - esto causará problemas en próximos escaneos")
                # Force cleanup OpenCV windows
                cv2.destroyAllWindows()
                cv2.waitKey(1)
        
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
        print(f"\n[{scan_id}] LIMPIEZA: Finalizando escaneo...")

        # FORZAR PARADA DE VIDEO THREAD
        is_scanning[0] = False
        
        # FORZAR TERMINACIÓN DE TODOS LOS THREADS ACTIVOS
        active_threads = threading.active_count()
        print(f"[{scan_id}] LIMPIEZA: Threads activos: {active_threads}")
        
        # Listar todos los threads
        for thread in threading.enumerate():
            if thread.name.startswith("VideoScanThread") and thread != threading.current_thread():
                print(f"[{scan_id}] LIMPIEZA: Thread encontrado: {thread.name} - Alive: {thread.is_alive()}")
        
        # LIMPIEZA: Verificar y terminar video thread
        if 'video_thread' in locals() and video_thread is not None:
            print(f"[{scan_id}] LIMPIEZA: Terminando video thread {video_thread.name}...")
            
            # Esperar terminación con timeout agresivo
            for cleanup_attempt in range(10):
                if not video_thread.is_alive():
                    print(f"[{scan_id}] LIMPIEZA: ✅ Video thread terminó correctamente")
                    break
                
                print(f"[{scan_id}] LIMPIEZA: Esperando terminación {cleanup_attempt + 1}/10...")
                video_thread.join(timeout=0.2)
                
                if cleanup_attempt == 9:
                    print(f"[{scan_id}] LIMPIEZA: ❌ CRÍTICO - Video thread NO TERMINÓ")
                    print(f"[{scan_id}] LIMPIEZA: Esto BLOQUEARÁ próximos escaneos")
                    # FORZAR DESTRUCCIÓN DE VENTANAS OPENCV
                    try:
                        cv2.destroyAllWindows()
                        for _ in range(10):
                            cv2.waitKey(1)
                            time.sleep(0.01)
                    except:
                        pass
        else:
            print(f"[{scan_id}] LIMPIEZA: Video thread no encontrado o ya terminado")
        
        # BUSCAR Y TERMINAR THREADS ZOMBIE
        zombie_threads = []
        for thread in threading.enumerate():
            if thread.name.startswith("VideoScanThread") and thread != threading.current_thread():
                if thread.is_alive():
                    zombie_threads.append(thread)
                    print(f"[{scan_id}] LIMPIEZA: ⚠️ Thread zombie encontrado: {thread.name}")
        
        if zombie_threads:
            print(f"[{scan_id}] LIMPIEZA: Encontrados {len(zombie_threads)} threads zombie")
            # Intentar cerrar ventanas asociadas a threads zombie
            cv2.destroyAllWindows()
            for _ in range(20):
                cv2.waitKey(1)
                time.sleep(0.01)

        # PARAR VIDEO STREAM COMPLETAMENTE
        try:
            if camera_mgr.is_active:
                print(f"[{scan_id}] LIMPIEZA: Parando video stream...")
                camera_mgr.stop_video_stream()
                time.sleep(0.3)
            print(f"[{scan_id}] LIMPIEZA: Video stream detenido")
        except Exception as e:
            print(f"[{scan_id}] LIMPIEZA: Error parando video: {e}")

        # DESTRUIR VENTANAS OPENCV AGRESIVAMENTE
        try:
            print(f"[{scan_id}] LIMPIEZA: Cerrando ventanas OpenCV...")
            for attempt in range(5):
                cv2.destroyAllWindows()
                cv2.waitKey(1)
                time.sleep(0.1)
            print(f"[{scan_id}] LIMPIEZA: Ventanas OpenCV cerradas")
        except Exception as e:
            print(f"[{scan_id}] LIMPIEZA: Error cerrando ventanas: {e}")

        # RESETEAR VELOCIDADES SIEMPRE (crítico para siguientes movimientos)
        try:
            print(f"[{scan_id}] LIMPIEZA: Reseteando velocidades del robot...")
            robot.cmd.set_velocities(
                RobotConfig.NORMAL_SPEED_H,
                RobotConfig.NORMAL_SPEED_V
            )
            time.sleep(1.0)
            print(f"[{scan_id}] LIMPIEZA: Velocidades reseteadas correctamente")
        except Exception as e:
            print(f"[{scan_id}] LIMPIEZA: Error reseteando velocidades: {e}")

        # RESET COMPLETO del UART manager para limpiar callbacks y estado de firmware
        try:
            print(f"[{scan_id}] LIMPIEZA: Reset completo del UART manager...")
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
        # Obtener snapshots reales del último movimiento desde el UART manager
        # Nota: el escáner corre dentro de main_robot con un objeto 'robot'
        # accesible por cierre de ámbito no está aquí. Por eso, obtenemos el
        # UART manager a través de los flags de detección: guardamos una
        # referencia cuando enviamos flags. Como alternativa simple aquí,
        # accedemos al singleton de camera_manager no es adecuado; usamos
        # el truco de localizar un UARTManager en runtime a través de la
        # instancia global if disponible. Para mantenerlo simple y robusto,
        # pedimos al módulo command_manager expuesto por robot vía closures.
        # En este archivo, robot.cmd.uart fue usado en otras funciones, por
        # lo tanto, almacenamos un puntero dentro de detection_state.
        uart = detection_state.get('uart_ref')
        if uart is None:
            try:
                # Fallback: intentar acceder mediante un import tardío del main_robot
                from Nivel_Supervisor.controller.uart_manager import UARTManager  # tipo
            except Exception:
                pass
        
        snapshot_pairs = []
        try:
            if uart is not None and hasattr(uart, 'get_last_snapshots'):
                snapshot_pairs = uart.get_last_snapshots()  # [(x_mm, y_mm), ...]
        except Exception:
            snapshot_pairs = []

        if not snapshot_pairs:
            print("⚠️ No se recibieron snapshots del robot para este movimiento."
                  " Verifique que el firmware esté enviando 'MOVEMENT_SNAPSHOTS'"
                  " al finalizar o al tocar límites. No se calcularán posiciones.")
            print(f"Flags enviados: {detection_state['flag_count']}")
            return

        # Usar solo X para correlación horizontal
        snapshot_positions = [xy[0] for xy in snapshot_pairs]
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
