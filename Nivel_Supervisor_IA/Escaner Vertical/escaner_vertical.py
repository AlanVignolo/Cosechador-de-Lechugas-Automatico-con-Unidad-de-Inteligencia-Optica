"""
Escáner Vertical Automático con Sistema de FLAGS
Detecta cuando el tubo está COMPLETO (líneas superior e inferior visibles)
Envía flags al firmware para marcar inicio/fin de tubo visible
"""

import sys
import os
import threading
import time
import cv2
import numpy as np

# Importar módulos del sistema
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor', 'config'))

# Solo importar lo que NO depende de robot_controller
from detector_canny_s_combinado import detectar_lineas_tubo

# Lazy imports (se importan cuando se necesitan)
# camera_manager, RobotConfig se importan en las funciones

class VerticalScanner:
    def __init__(self):
        self.camera_mgr = get_camera_manager()
        self.is_scanning = False
        self.scan_thread = None
        self.tube_segments = []  # Segmentos donde el tubo está completo

    def start_live_camera(self):
        """Inicia la cámara en modo video streaming"""
        print("Iniciando cámara en modo video streaming...")
        if not self.camera_mgr.acquire("escaner_vertical"):
            print("Error: No se pudo adquirir la cámara")
            return False
        if not self.camera_mgr.start_stream_ref(fps=10):
            print("Error: No se pudo iniciar video stream")
            self.camera_mgr.release("escaner_vertical")
            return False
        print("Cámara lista (stream 10 FPS)")
        return True

    def stop_live_camera(self):
        """Detiene la cámara y el video streaming"""
        print("Deteniendo video streaming...")
        try:
            self.camera_mgr.stop_stream_ref()
        finally:
            self.camera_mgr.release("escaner_vertical")
        print("Cámara liberada")

    def is_tube_complete(self, y_superior, y_inferior, frame_height, margin=10):
        """
        Verifica si el tubo está COMPLETO (ambas líneas visibles)

        Args:
            y_superior: Coordenada Y de línea superior
            y_inferior: Coordenada Y de línea inferior
            frame_height: Altura del frame
            margin: Margen de seguridad desde los bordes (píxeles)

        Returns:
            bool: True si ambas líneas están completamente dentro del frame
        """
        if y_superior is None or y_inferior is None:
            return False

        # Verificar que ambas líneas estén dentro del frame con margen
        superior_visible = (y_superior >= margin)
        inferior_visible = (y_inferior <= frame_height - margin)

        return superior_visible and inferior_visible

    def process_detection_state(self, is_complete, detection_state, robot):
        """
        Procesar cambios de estado con debouncing y enviar flags

        Estados:
        - None: No se ha detectado nada
        - 'complete': Tubo completo visible
        - 'incomplete': Tubo detectado pero cortado
        """

        # Parámetros de debouncing
        COMPLETE_ON_FRAMES = 5   # Frames para confirmar tubo completo
        COMPLETE_OFF_FRAMES = 5  # Frames para confirmar pérdida de tubo

        # Actualizar rachas
        if is_complete:
            detection_state['complete_streak'] += 1
            detection_state['incomplete_streak'] = 0
        else:
            detection_state['incomplete_streak'] += 1
            detection_state['complete_streak'] = 0

        # Transición a 'complete' (INICIO_TUBO)
        if (detection_state['current_state'] != 'complete' and
            detection_state['complete_streak'] >= COMPLETE_ON_FRAMES):

            print(f"[TRANSICION] INICIO_TUBO detectado (streak={detection_state['complete_streak']})")
            detection_state['current_state'] = 'complete'

            # Enviar flag
            flag_id = self.send_flag(robot, detection_state, "INICIO_TUBO")
            if flag_id:
                detection_state['tube_segments'].append({
                    'start_flag': flag_id,
                    'start_time': time.time()
                })

        # Transición a 'incomplete' (FIN_TUBO)
        elif (detection_state['current_state'] == 'complete' and
              detection_state['incomplete_streak'] >= COMPLETE_OFF_FRAMES):

            print(f"[TRANSICION] FIN_TUBO detectado (streak={detection_state['incomplete_streak']})")
            detection_state['current_state'] = 'incomplete'

            # Enviar flag
            flag_id = self.send_flag(robot, detection_state, "FIN_TUBO")
            if flag_id and detection_state['tube_segments']:
                last_segment = detection_state['tube_segments'][-1]
                last_segment['end_flag'] = flag_id
                last_segment['end_time'] = time.time()
                duration = last_segment['end_time'] - last_segment['start_time']
                print(f"TUBO COMPLETADO - Flags {last_segment['start_flag']}-{flag_id} (duración: {duration:.1f}s)")

    def send_flag(self, robot, detection_state, state_type):
        """Enviar flag al firmware para marcar cambio de estado"""
        try:
            # Verificar límite de flags
            if detection_state['flag_count'] >= detection_state['max_flags']:
                print(f"Límite de flags alcanzado ({detection_state['max_flags']})")
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

    def video_loop(self, robot, detection_state):
        """Bucle de video para procesamiento continuo"""
        print("Iniciando bucle de video...")

        frame_count = 0

        while self.is_scanning:
            try:
                frame = self.camera_mgr.get_latest_video_frame()

                if frame is None:
                    time.sleep(0.05)
                    continue

                frame_count += 1

                # Rotar y recortar
                frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                alto, ancho = frame_rotado.shape[:2]
                x1 = int(ancho * 0.2)
                x2 = int(ancho * 0.8)
                y1 = int(alto * 0.3)
                y2 = int(alto * 0.7)

                frame_procesado = frame_rotado[y1:y2, x1:x2]

                # Detectar líneas del tubo
                y_sup, y_inf, centro_y, info = detectar_lineas_tubo(frame_procesado, debug=False)

                # Determinar si el tubo está completo
                tube_complete = self.is_tube_complete(y_sup, y_inf, frame_procesado.shape[0])

                # Procesar estado y generar flags
                self.process_detection_state(tube_complete, detection_state, robot)

                # Visualización (opcional, comentar para mejor performance)
                if y_sup is not None and y_inf is not None:
                    cv2.line(frame_procesado, (0, y_sup), (frame_procesado.shape[1], y_sup), (0, 0, 255), 2)
                    cv2.line(frame_procesado, (0, y_inf), (frame_procesado.shape[1], y_inf), (0, 255, 0), 2)

                    status_color = (0, 255, 0) if tube_complete else (0, 165, 255)
                    status_text = "COMPLETO" if tube_complete else "CORTADO"
                    cv2.putText(frame_procesado, status_text, (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
                else:
                    cv2.putText(frame_procesado, "NO DETECTADO", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                cv2.imshow("Escaner Vertical", frame_procesado)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Usuario presionó 'q'")
                    self.is_scanning = False
                    break

            except Exception as e:
                # No mostrar errores menores
                pass

        cv2.destroyAllWindows()
        print(f"Bucle de video terminado. Frames procesados: {frame_count}")

    def start_scanning_with_movement(self, robot):
        """
        Inicia el escaneo vertical con movimiento
        """
        print("\n" + "="*60)
        print("INICIANDO ESCANEO VERTICAL CON SISTEMA DE FLAGS")
        print("="*60)

        # Verificar homing
        if not robot.is_homed:
            print("Error: El robot debe estar homed")
            return False

        # Verificar brazo en posición segura
        if not robot.arm.is_in_safe_position():
            print("Moviendo brazo a posición segura...")
            result = robot.arm.ensure_safe_position()
            if not result["success"]:
                print("Error: No se pudo mover brazo a posición segura")
                return False

        # Estado de detección
        from config.robot_config import RobotConfig
        MAX_FLAGS = RobotConfig.MAX_SNAPSHOTS * 2

        detection_state = {
            'current_state': None,  # 'complete' | 'incomplete' | None
            'complete_streak': 0,
            'incomplete_streak': 0,
            'tube_segments': [],
            'flag_count': 0,
            'max_flags': MAX_FLAGS,
            'uart_ref': robot.cmd.uart
        }

        video_thread = None

        try:
            # Iniciar cámara
            if not self.start_live_camera():
                return False

            # Iniciar bucle de video en thread separado
            self.is_scanning = True
            video_thread = threading.Thread(
                target=self.video_loop,
                args=(robot, detection_state),
                daemon=True
            )
            video_thread.start()

            # Configurar velocidades
            print("Configurando velocidades de movimiento...")
            result = robot.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H,
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                print(f"Error configurando velocidades: {result}")
                return False

            # Movimiento vertical
            print("Iniciando movimiento vertical...")
            dims = robot.get_workspace_dimensions()
            if dims.get('calibrated'):
                height_mm = float(dims.get('height_mm', 0.0))
            else:
                height_mm = float(RobotConfig.MAX_Y)

            safety = 20.0
            y_target = max(0.0, height_mm - safety)

            # Obtener posición actual
            try:
                st = robot.get_status()
                curr_y = float(st['position']['y'])
            except Exception:
                curr_y = 0.0

            dy = y_target - curr_y
            print(f"Moviendo hasta Y={y_target:.1f}mm (ΔY={dy:.1f}mm)...")

            move_res = robot.cmd.move_xy(0, dy)
            if not move_res.get('success'):
                print(f"Error iniciando movimiento: {move_res}")
                return False

            # Esperar finalización
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass

            print("Movimiento vertical completado")

            # Esperar procesamiento de últimos frames
            time.sleep(1.0)

            return True

        except Exception as e:
            print(f"Error durante escaneo: {e}")
            return False

        finally:
            print("\n🧹 Limpieza final...")

            # Detener scanning
            self.is_scanning = False

            # Esperar video thread
            if video_thread and video_thread.is_alive():
                video_thread.join(timeout=2)

            # Detener cámara
            self.stop_live_camera()

            # Restaurar velocidades
            try:
                result = robot.cmd.set_velocities(
                    RobotConfig.NORMAL_SPEED_H,
                    RobotConfig.NORMAL_SPEED_V
                )
                if result["success"]:
                    print("Velocidades restauradas")
            except:
                pass

            # Correlacionar flags con snapshots
            correlate_flags_with_snapshots_vertical(detection_state)

            # Mostrar resultados
            self.print_detection_summary(detection_state)

            print("Escaneo completado")

    def print_detection_summary(self, detection_state):
        """Muestra resumen de detecciones"""
        print(f"\n{'='*60}")
        print("RESUMEN DE DETECCIÓN DE TUBOS")
        print(f"{'='*60}")
        print(f"Total de flags enviados: {detection_state['flag_count']}")

        segments = detection_state['tube_segments']
        if not segments:
            print("No se detectaron tubos completos")
        else:
            print(f"Se detectaron {len(segments)} segmentos de tubo completo:")
            print(f"{'#':<3} {'Flag Inicio':<12} {'Flag Fin':<12} {'Y Inicio (mm)':<15} {'Y Fin (mm)':<15}")
            print("-" * 60)

            for i, seg in enumerate(segments, 1):
                start_flag = seg.get('start_flag', 'N/A')
                end_flag = seg.get('end_flag', 'N/A')
                y_start = seg.get('start_pos_real', 'N/A')
                y_end = seg.get('end_pos_real', 'N/A')

                print(f"{i:<3} {start_flag:<12} {end_flag:<12} {y_start!s:<15} {y_end!s:<15}")

        print(f"{'='*60}")
        return segments

def correlate_flags_with_snapshots_vertical(detection_state):
    """Correlacionar flags con snapshots para obtener posiciones Y reales"""
    try:
        print("\nCORRELACIONANDO FLAGS CON SNAPSHOTS...")

        uart = detection_state.get('uart_ref')
        if uart is None:
            print("Error: No hay referencia UART disponible")
            return

        snapshot_pairs = []
        try:
            if uart is not None and hasattr(uart, 'get_last_snapshots'):
                snapshot_pairs = uart.get_last_snapshots()
        except Exception:
            snapshot_pairs = []

        if not snapshot_pairs:
            print("No se recibieron snapshots del firmware")
            return

        # Usar solo coordenada Y
        snapshot_positions = [xy[1] for xy in snapshot_pairs]
        print(f"Snapshots disponibles: {len(snapshot_positions)}")
        print(f"Flags enviados: {detection_state['flag_count']}")

        # Correlacionar cada segmento
        for i, segment in enumerate(detection_state['tube_segments']):
            start_flag_idx = segment.get('start_flag', 0) - 1
            end_flag_idx = segment.get('end_flag', 0) - 1

            if 0 <= start_flag_idx < len(snapshot_positions):
                segment['start_pos_real'] = snapshot_positions[start_flag_idx]

            if 0 <= end_flag_idx < len(snapshot_positions):
                segment['end_pos_real'] = snapshot_positions[end_flag_idx]

            if 'start_pos_real' in segment and 'end_pos_real' in segment:
                print(f"   TUBO #{i+1}: Y_inicio={segment['start_pos_real']:.1f}mm, Y_fin={segment['end_pos_real']:.1f}mm")

        print("Correlación completada")

    except Exception as e:
        print(f"Error en correlación: {e}")

# Función principal
def scan_vertical_with_flags(robot):
    """Función principal para escaneo vertical con flags"""
    scanner = VerticalScanner()
    return scanner.start_scanning_with_movement(robot)

if __name__ == "__main__":
    print("Este módulo debe ser importado desde main_robot.py")
    print("No ejecutar directamente")
