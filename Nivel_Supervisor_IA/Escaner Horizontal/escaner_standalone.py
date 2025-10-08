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
from core.camera_manager import get_camera_manager
from config.robot_config import RobotConfig

def scan_horizontal_with_live_camera(robot, tubo_id=None, debug=False):
    """
    Función principal de escaneo horizontal autónoma con matriz de cintas

    Args:
        robot: Instancia del RobotController
        tubo_id: ID del tubo a escanear (None = preguntar al usuario)
        debug: Si True, muestra visualización en tiempo real (default: False)
    """
    # Importar sistema de matriz y configuración dinámica de tubos
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Analizar Cultivo'))
    from matriz_cintas import matriz_cintas
    from configuracion_tubos import config_tubos
    
    # Obtener configuración dinámica de tubos
    tubo_config = config_tubos.obtener_configuracion_tubos()
    num_tubos = config_tubos.obtener_numero_tubos()
    
    # Mostrar configuración actual
    print(f"\nConfiguración actual de tubos:")
    if config_tubos.hay_configuracion_desde_escaner():
        print("(Actualizada desde escáner vertical)")
    else:
        print("(Configuración por defecto - se recomienda ejecutar escáner vertical primero)")
    
    config_tubos.mostrar_configuracion_actual()
    
    # Selección de tubo dinámica (permitir preselección para modo automático)
    print(f"\nSelección de tubo:")
    for t_id, config in tubo_config.items():
        print(f"{t_id}. {config['nombre']} (Y={config['y_mm']}mm)")
    
    # Definir un ID de escaneo por defecto y estado de escaneo por si hay errores tempranos
    import uuid
    scan_id = str(uuid.uuid4())[:8]
    is_scanning = [False]

    # Si se pasa un tubo preseleccionado y es válido, usarlo sin preguntar
    if tubo_id is not None and int(tubo_id) in tubo_config.keys():
        tubo_seleccionado = int(tubo_id)
        print(f"Seleccionado automáticamente Tubo {tubo_seleccionado}")
    else:
        while True:
            try:
                tubo_seleccionado = int(input(f"Seleccione tubo (1-{num_tubos}): "))
                if tubo_seleccionado in tubo_config.keys():
                    break
                else:
                    print(f"Opción inválida. Seleccione entre 1 y {num_tubos}.")
            except ValueError:
                print("Por favor ingrese un número válido.")
    
    selected_tubo = tubo_config[tubo_seleccionado]
    print(f"Tubo seleccionado: {selected_tubo['nombre']} (Y={selected_tubo['y_mm']}mm)")
    
    try:
        # Importar solo lo necesario dentro de la función (ya importado a nivel módulo)
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
        
        # Adquirir y preparar cámara (uso compartido administrado por CameraManager)
        # Adquirir cámara
        if not camera_mgr.acquire("escaner_standalone"):
            print("Error: No se pudo adquirir la cámara")
            return False
        
        if not camera_mgr.start_stream_ref(fps=6):
            print("Error: No se pudo iniciar video stream")
            camera_mgr.release("escaner_standalone")
            return False
        
        # Velocidades lentas
        robot.cmd.set_velocities(2000, 2000)
        
        # NOTA: El posicionamiento Y ahora se hace desde otro código externo
        # Solo informamos qué tubo se va a escanear para la matriz de coordenadas
        
        # SECUENCIA DE MOVIMIENTO HORIZONTAL
        # Nota: Evitar tocar el switch derecho. Comenzar el escaneo desde la
        # posición actual y mover directamente hacia el límite izquierdo.
        # Iniciar detección básica
        
        # PRE-ESCANEO: limpiar hilos zombie
        # utilizar/actualizar ID de escaneo ahora que comienza el proceso principal
        scan_id = str(uuid.uuid4())[:8]
        is_scanning = [True]
        video_thread = None
        
        print(f"Escaneo ID: {scan_id}")
        
        last_detection_pos = [None]
        
        # Sistema de tracking de estados para flags
        # Parámetros de debouncing y límites
        MAX_FLAGS = RobotConfig.MAX_SNAPSHOTS * 2
        DETECT_ON_FRAMES = 5    # Debounce más robusto para INICIO
        DETECT_OFF_FRAMES = 5   # Debounce más robusto para FIN
        MIN_TRANSITION_COOLDOWN_S = 0.25  # Evita chatter rápido entre transiciones
        # Umbrales de calidad para filtrar falsos positivos/negativos
        MIN_NEG_STREAK_FOR_START = 8  # mínimos negativos previos a INICIO (más estricto)
        MIN_POS_STREAK_FOR_END = 8    # mínimos positivos previos a FIN (más estricto)
        MIN_WIDTH_MM = 60             # ancho mínimo entre INICIO/FIN (mm) para considerar cinta válida

        detection_state = {
            'current_state': None,  # 'accepted' | 'rejected' | None
            'position_buffer': [],
            'tape_segments': [],
            'flag_count': 0,
            'uart_ref': robot.cmd.uart,
            'detect_streak': 0,
            'nodetect_streak': 0,
            'max_flags': MAX_FLAGS,
            # Valores pendientes para registrar rachas previas reales en el instante de cambio
            'pending_pre_start_neg_streak': 0,
            'pending_pre_end_pos_streak': 0,
            'last_transition_ts': 0.0,
        }
        
        def send_flag_for_state_change(state_type):
            """Enviar flag al firmware para marcar cambio de estado"""
            try:
                # No enviar más flags si alcanzamos el límite de snapshots del firmware
                if detection_state['flag_count'] >= detection_state['max_flags']:
                    print(f"Límite de flags alcanzado ({detection_state['max_flags']}). No se enviarán más RP en este movimiento.")
                    return None

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
            """Procesar cambios de estado con debouncing y enviar flags solo en transiciones.
            Además registra cuántos frames negativos/positivos precedieron a cada flag."""
            # Guardar rachas previas antes de actualizar
            prev_detect_streak = detection_state['detect_streak']
            prev_nodetect_streak = detection_state['nodetect_streak']

            # Actualizar rachas de detección / no detección
            if is_accepted:
                # Si acabamos de entrar a detección (streak pasa de 0 a 1),
                # guardar los negativos justo antes de entrar
                if prev_detect_streak == 0:
                    detection_state['pending_pre_start_neg_streak'] = prev_nodetect_streak
                detection_state['detect_streak'] = prev_detect_streak + 1
                detection_state['nodetect_streak'] = 0
            else:
                # Si acabamos de salir a no detección (streak pasa de 0 a 1),
                # guardar los positivos justo antes de salir
                if prev_nodetect_streak == 0:
                    detection_state['pending_pre_end_pos_streak'] = prev_detect_streak
                detection_state['nodetect_streak'] = prev_nodetect_streak + 1
                detection_state['detect_streak'] = 0

            # Evaluar transición a 'accepted' (INICIO) con debouncing y cooldown
            if detection_state['current_state'] != 'accepted' and detection_state['detect_streak'] >= DETECT_ON_FRAMES:
                now_ts = time.time()
                if now_ts - detection_state.get('last_transition_ts', 0.0) < MIN_TRANSITION_COOLDOWN_S:
                    return
                print(f"[TRANSICION] INICIO detectado (detect_streak={detection_state['detect_streak']}, prev_neg={prev_nodetect_streak})")
                detection_state['current_state'] = 'accepted'
                flag_id = send_flag_for_state_change("INICIO_CINTA")
                if flag_id:
                    detection_state['tape_segments'].append({
                        'start_flag': flag_id,
                        # Usar la racha negativa registrada justo cuando se inició la detección
                        'pre_start_neg_streak': detection_state.get('pending_pre_start_neg_streak', 0)
                    })
                detection_state['last_transition_ts'] = now_ts
                return

            # Evaluar transición a 'rejected' (FIN) con debouncing y cooldown
            if detection_state['current_state'] == 'accepted' and detection_state['nodetect_streak'] >= DETECT_OFF_FRAMES:
                now_ts = time.time()
                if now_ts - detection_state.get('last_transition_ts', 0.0) < MIN_TRANSITION_COOLDOWN_S:
                    return
                print(f"[TRANSICION] FIN detectado (nodetect_streak={detection_state['nodetect_streak']}, prev_pos={prev_detect_streak})")
                detection_state['current_state'] = 'rejected'
                flag_id = send_flag_for_state_change("FIN_CINTA")
                if flag_id and detection_state['tape_segments']:
                    last_segment = detection_state['tape_segments'][-1]
                    last_segment['end_flag'] = flag_id
                    # Usar la racha positiva registrada justo cuando se inició la no detección
                    last_segment['pre_end_pos_streak'] = detection_state.get('pending_pre_end_pos_streak', 0)
                    print(f"CINTA COMPLETADA - Flags {last_segment['start_flag']}-{flag_id}")
                detection_state['last_transition_ts'] = now_ts
        
        def video_loop():
            """Bucle de video; con opción de UI debug"""
            thread_name = threading.current_thread().name

            try:
                frame_count = 0
                start_ts = time.time()
                printed_none_once = False
                detection_count = 0
                last_status_report = time.time()

                while is_scanning[0]:
                    try:
                        frame = camera_mgr.get_latest_video_frame()
                        if frame is None:
                            printed_none_once = True
                            time.sleep(0.05)
                            continue

                        frame_count += 1
                        printed_none_once = False

                        # Procesar frame para detección
                        processed = process_frame_for_detection(frame)

                        # Usar detector sofisticado
                        is_tape_detected = detect_sophisticated_tape(processed)

                        if is_tape_detected:
                            detection_count += 1

                        # Procesar cambios de estado y enviar flags
                        process_detection_state(is_tape_detected)

                        # Visualización modo debug (sin texto, solo línea central limpia)
                        if debug:
                            display_frame = processed.copy()

                            # Dibujar línea de referencia central (gris claro, delgada)
                            img_center_x = display_frame.shape[1] // 2
                            cv2.line(display_frame, (img_center_x, 0), (img_center_x, display_frame.shape[0]), (180, 180, 180), 2)

                            cv2.imshow("Escaner Horizontal - DEBUG", display_frame)
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                print("Usuario presionó 'q'")
                                is_scanning[0] = False
                                break

                    except Exception:
                        time.sleep(0.1)
                        
                    except KeyboardInterrupt:
                        is_scanning[0] = False
                        break
                        
            finally:
                if debug:
                    cv2.destroyAllWindows()
        
        # Iniciar hilo de video con nombre único
        video_thread_name = f"VideoScanThread_{scan_id}"
        video_thread = threading.Thread(target=video_loop, name=video_thread_name)
        video_thread.daemon = True  # Evitar bloqueos si el hilo no termina
        video_thread.start()
        time.sleep(0.2)
        
        # Verificación rápida de que el stream está funcionando
        warmup_start = time.time()
        first_frame_ok = False
        while time.time() - warmup_start < 0.5:
            try:
                test_frame = camera_mgr.get_latest_video_frame(timeout=0.1)
                if test_frame is not None:
                    first_frame_ok = True
                    break
            except Exception:
                pass
            time.sleep(0.05)
        
        if not first_frame_ok:
            print("Error: Stream de video no disponible")
            is_scanning[0] = False
            camera_mgr.stop_stream_ref()
            camera_mgr.release("escaner_standalone")
            return False
        
        # Comprobación previa: si estamos en límite izquierdo, retroceder un poco a la derecha
        try:
            lim = robot.cmd.uart.get_limit_status()
            if lim and lim.get('status', {}).get('H_LEFT', False):
                print("Aviso: límite izquierdo activo al iniciar; retrocediendo 20mm a la derecha")
                robot.cmd.move_xy(-20.0, 0.0)
                time.sleep(0.5)
                robot.cmd.uart.check_limits()
        except Exception:
            pass

        time.sleep(0.25)
        
        # Limpiar snapshots previos
        try:
            robot.cmd.uart.clear_last_snapshots()
        except Exception as e:
            print(f"Advertencia: No se pudo limpiar snapshots: {e}")

        # Movimiento hasta el borde derecho seguro (x_edge = width_mm - safety)
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
        safety = 20.0
        x_edge = max(0.0, width_mm - safety)
        try:
            status = robot.get_status()
            curr_x = float(status['position']['x'])
        except Exception:
            curr_x = 0.0
        dx = x_edge - curr_x
        print(f"Escaneo horizontal: moviendo hasta X={x_edge:.1f}mm (ΔX={dx:.1f}mm)")
        res_move = robot.cmd.move_xy(dx, 0)
        if not res_move.get('success'):
            print(f"Error iniciando movimiento horizontal: {res_move}")
            return False
        # Esperar finalización normal del movimiento (no por límite)
        move_completed = False
        try:
            move_completed = robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
        except Exception:
            move_completed = False
        if not move_completed:
            # Fallback por tiempo estimado según velocidad configurada
            try:
                h_mm_s = max(1.0, float(RobotConfig.NORMAL_SPEED_H) / float(RobotConfig.STEPS_PER_MM_H))
                est_t = abs(dx) / h_mm_s + 0.5
                time.sleep(min(est_t, 10.0))
            except Exception:
                time.sleep(1.0)
        
        # Detener video
        is_scanning[0] = False
        time.sleep(0.2)
        if video_thread and video_thread.is_alive():
            video_thread.join(timeout=1.0)
        
        # Esperar terminación con intentos múltiples
        for attempt in range(3):
            if not video_thread.is_alive():
                break
            video_thread.join(timeout=1.0)
            if not video_thread.is_alive():
                break
        
        # Limpiar ventanas OpenCV de forma segura
        try:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
        except Exception:
            pass
        
        # Ya no esperamos tocar límite; el movimiento termina en x_edge con snapshots automáticos
        
        # Correlacionar flags con snapshots para obtener posiciones reales
        correlate_flags_with_snapshots(detection_state)
        
        # Filtrar segmentos incompletos y de baja calidad
        filtered_segments = []
        for idx, seg in enumerate(detection_state['tape_segments'], 1):
            # Requiere inicio y fin
            if 'start_flag' not in seg or 'end_flag' not in seg:
                print(f"   Segmento #{idx}: descartado por incompleto (falta inicio/fin)")
                continue
            # Rachas mínimas antes de cada transición
            pre_neg = seg.get('pre_start_neg_streak', 0)
            pre_pos = seg.get('pre_end_pos_streak', 0)
            if pre_neg < MIN_NEG_STREAK_FOR_START or pre_pos < MIN_POS_STREAK_FOR_END:
                print(f"   Segmento #{idx}: descartado por rachas insuficientes (neg={pre_neg}, pos={pre_pos})")
                continue
            # Si tenemos posiciones reales, filtrar por ancho mínimo
            if 'start_pos_real' in seg and 'end_pos_real' in seg:
                width_mm = abs(seg['end_pos_real'] - seg['start_pos_real'])
                if width_mm < MIN_WIDTH_MM:
                    print(f"   Segmento #{idx}: descartado por ancho insuficiente ({width_mm:.1f}mm < {MIN_WIDTH_MM}mm)")
                    continue
            filtered_segments.append(seg)
        # Reemplazar por lista filtrada
        detection_state['tape_segments'] = filtered_segments

        # Mostrar resultados y guardar en matriz
        resultados = show_results(detections, detection_state, selected_tubo)
        
        # Guardar cintas detectadas en la matriz
        if resultados:
            # Guardar en matriz (silenciar mensajes intermedios)
            if matriz_cintas.guardar_cintas_tubo(tubo_seleccionado, resultados):
                pass
            else:
                print("Error guardando cintas en matriz")
        
        return True
        
    except Exception as e:
        print(f"Error durante el escaneado: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Limpieza de recursos
        is_scanning[0] = False
        
        # FORZAR TERMINACIÓN DE TODOS LOS THREADS ACTIVOS
        
        # LIMPIEZA: Verificar y terminar video thread
        if 'video_thread' in locals() and video_thread is not None:
            # Esperar terminación con timeout agresivo
            for cleanup_attempt in range(10):
                if not video_thread.is_alive():
                    break
                
                video_thread.join(timeout=0.2)
                
                if cleanup_attempt == 9:
                    # FORZAR DESTRUCCIÓN DE VENTANAS OPENCV
                    try:
                        cv2.destroyAllWindows()
                        for _ in range(10):
                            cv2.waitKey(1)
                            time.sleep(0.01)
                    except:
                        pass
        else:
            pass
        
        # PARAR VIDEO STREAM (referenciado) Y LIBERAR USO
        try:
            camera_mgr.stop_stream_ref()
            time.sleep(0.2)
            camera_mgr.release("escaner_standalone")
        except Exception:
            pass

        # DESTRUIR VENTANAS OPENCV AGRESIVAMENTE
        try:
            for attempt in range(3):
                cv2.destroyAllWindows()
                cv2.waitKey(1)
                time.sleep(0.05)
        except Exception:
            pass

        # Resetear velocidades
        try:
            robot.cmd.set_velocities(
                RobotConfig.NORMAL_SPEED_H,
                RobotConfig.NORMAL_SPEED_V
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"Error reseteando velocidades: {e}")

        # Limpiar snapshots
        try:
            robot.cmd.uart.clear_last_snapshots()
        except Exception as e:
            print(f"Error limpiando snapshots: {e}")

        # No resetear completamente el camera manager: se conserva para otros módulos
        
        # Limpieza final
        try:
            import gc
            gc.collect()
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            time.sleep(0.5)
        except Exception:
            pass

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
            print("Advertencia: No se recibieron snapshots del firmware")
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
                
                print(f"   CINTA #{i}: X={x_position:.1f}mm, Y={y_position}mm (Flags {start_flag}-{end_flag})")
                
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
