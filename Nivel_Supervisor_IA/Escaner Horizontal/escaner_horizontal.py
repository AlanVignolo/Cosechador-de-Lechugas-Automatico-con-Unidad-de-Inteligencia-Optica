"""
Escáner Horizontal con Cámara en Vivo
Detecta cintas negras mientras se mueve horizontalmente a lo largo del tubo
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
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Correccion Posicion Horizontal'))

from camera_manager import get_camera_manager
from robot_controller import RobotController
from config.robot_config import RobotConfig
from tape_detector_horizontal import detect_tape_position

class HorizontalScanner:
    def __init__(self):
        self.camera_mgr = get_camera_manager()
        self.is_scanning = False
        self.scan_thread = None
        self.detections = []
        self.last_detection_position = None
        self.detection_cooldown_mm = 50  # No detectar otra cinta hasta 50mm de movimiento
        
    def start_live_camera(self):
        """Inicia la cámara en modo video streaming"""
        print("Iniciando cámara en modo video streaming (uso compartido)...")
        # Adquirir uso y arrancar stream con referencia
        if not self.camera_mgr.acquire("escaner_horizontal"):
            print("Error: No se pudo adquirir la cámara")
            return False
        # Iniciar video stream a 10 FPS para no saturar (movimiento lento)
        if not self.camera_mgr.start_stream_ref(fps=10):
            print("Error: No se pudo iniciar video stream")
            self.camera_mgr.release("escaner_horizontal")
            return False
        print("Cámara lista (stream 10 FPS)")
        return True
    
    def stop_live_camera(self):
        """Detiene la cámara y el video streaming"""
        print("Deteniendo referencia de video streaming y liberando cámara...")
        try:
            self.camera_mgr.stop_stream_ref()
        finally:
            self.camera_mgr.release("escaner_horizontal")
        print("Stream liberado y cámara disponible para otros módulos")
    
    def video_callback(self, frame, robot=None):
        """Callback para procesar cada frame del video durante el escaneo"""
        if frame is None:
            return
        
        # Rotar y recortar el frame (como en el tape detector)
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Aplicar el mismo recorte que usa el detector
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)
        
        frame_procesado = frame_rotado[y1:y2, x1:x2]
        
        # *** DETECCIÓN DE CINTAS EN TIEMPO REAL ***
        self.detect_tapes_in_frame(frame_procesado, robot)
        
        # Mostrar el frame procesado con detecciones marcadas
        cv2.imshow("Escáner Horizontal - Video Live", frame_procesado)
        cv2.waitKey(1)  # No bloquear
    
    def detect_tapes_in_frame(self, frame, robot):
        """Detecta cintas en el frame actual y registra su posición"""
        try:
            # Usar el detector inteligente de cintas
            candidates = detect_tape_position(frame, debug=False)
            
            if candidates:
                # Obtener la posición actual del robot
                current_pos = robot.get_current_position_relative()
                current_x_mm = current_pos['position_mm']['x']
                
                # Verificar cooldown de detección
                if self.last_detection_position is not None:
                    distance_since_last = abs(current_x_mm - self.last_detection_position)
                    if distance_since_last < self.detection_cooldown_mm:
                        return  # Muy cerca de la última detección
                
                # Analizar la mejor cinta detectada
                best_candidate = candidates[0]
                tape_center_x = best_candidate['base_center_x']
                frame_center_x = frame.shape[1] // 2
                distance_from_center = tape_center_x - frame_center_x
                
                # Solo registrar si la cinta está cerca del centro (±30 píxeles)
                if abs(distance_from_center) <= 30:
                    detection = {
                        'position_mm': current_x_mm,
                        'tape_center_x': tape_center_x,
                        'distance_from_center': distance_from_center,
                        'confidence': best_candidate['score'],
                        'timestamp': time.time()
                    }
                    
                    self.detections.append(detection)
                    self.last_detection_position = current_x_mm
                    
                    print(f"CINTA DETECTADA en posición {current_x_mm:.1f}mm - Confianza: {best_candidate['score']:.2f}")
                    
                    # Marcar detección en el frame
                    cv2.circle(frame, (tape_center_x, frame.shape[0]//2), 10, (0, 255, 0), 3)
                    cv2.putText(frame, f"CINTA #{len(self.detections)}", 
                               (tape_center_x-30, frame.shape[0]//2-20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
        except Exception as e:
            # No mostrar errores para no saturar la consola
            pass
    
    def display_live_feed(self, robot):
        """Muestra el feed de video en tiempo real en una ventana"""
        print("Iniciando visualización en vivo...")
        print("Presiona 'q' para detener la visualización")
        
        while self.is_scanning:
            # Obtener frame más reciente
            frame = self.camera_mgr.get_latest_video_frame()
            
            if frame is not None:
                self.video_callback(frame, robot)
                
                # Verificar si se presionó 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Usuario presionó 'q' - deteniendo visualización")
                    break
            else:
                # Si no hay frame, esperar un poco
                time.sleep(0.1)
        
        # Cerrar ventanas
        cv2.destroyAllWindows()
        print("Visualización detenida")
    
    def print_detection_summary(self):
        """Muestra un resumen de todas las detecciones realizadas"""
        print(f"\n{'='*60}")
        print("RESUMEN DE DETECCIÓN DE CINTAS")
        print(f"{'='*60}")
        
        if not self.detections:
            print("No se detectaron cintas durante el escaneado")
        else:
            print(f"Se detectaron {len(self.detections)} cintas:")
            print(f"{'#':<3} {'Posición (mm)':<15} {'Confianza':<12} {'Centro X':<10}")
            print("-" * 50)
            
            for i, detection in enumerate(self.detections, 1):
                position = detection['position_mm']
                confidence = detection['confidence']
                center_x = detection['tape_center_x']
                
                print(f"{i:<3} {position:<15.1f} {confidence:<12.2f} {center_x:<10}")
            
            # Calcular distancia promedio entre cintas
            if len(self.detections) > 1:
                distances = []
                for i in range(1, len(self.detections)):
                    dist = abs(self.detections[i]['position_mm'] - self.detections[i-1]['position_mm'])
                    distances.append(dist)
                
                avg_distance = sum(distances) / len(distances)
                print(f"\nDistancia promedio entre cintas: {avg_distance:.1f}mm")
        
        print(f"{'='*60}")
        return self.detections
    
    def start_scanning_with_movement(self, robot):
        """
        Inicia el proceso completo de escaneado:
        1. Va al switch derecho
        2. Retrocede 1cm
        3. Recorre hasta el switch izquierdo con velocidad de homing
        4. Muestra cámara en vivo durante todo el proceso
        """
        print("\n" + "="*60)
        print("INICIANDO ESCANEADO HORIZONTAL CON CAMARA EN VIVO")
        print("="*60)
        
        # Verificar que el robot esté homed
        if not robot.is_homed:
            print("Error: El robot debe estar homed antes del escaneado")
            return False
        
        # Verificar que el brazo esté en posición segura
        if not robot.arm.is_in_safe_position():
            print("Moviendo brazo a posición segura...")
            result = robot.arm.ensure_safe_position()
            if not result["success"]:
                print("Error: No se pudo mover brazo a posición segura")
                return False
        
        try:
            # 1. Iniciar cámara en vivo
            if not self.start_live_camera():
                return False
            
            # 2. Iniciar visualización en hilo separado
            self.is_scanning = True
            self.detections = []
            
            display_thread = threading.Thread(target=self.display_live_feed, daemon=True)
            display_thread.start()
            
            print("Fase única: Recorrido horizontal dentro del espacio de trabajo...")
            from config.robot_config import RobotConfig
            # Velocidad de homing para recorrido estable (puedes ajustar a NORMAL si prefieres)
            result = robot.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H,
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                print(f"Error configurando velocidades: {result}")
                return False

            # Calcular borde seguro de trabajo (x_edge)
            dims = robot.get_workspace_dimensions()
            if dims.get('calibrated'):
                width_mm = float(dims.get('width_mm', 0.0))
            else:
                width_mm = float(RobotConfig.MAX_X)
            safety = 20.0
            x_edge = max(0.0, width_mm - safety)

            # Mover desde X actual hasta x_edge (sin tocar switches)
            try:
                st = robot.get_status()
                curr_x = float(st['position']['x'])
            except Exception:
                curr_x = 0.0
            dx = x_edge - curr_x
            print(f"   Moviendo hasta X={x_edge:.1f}mm (ΔX={dx:.1f}mm) sin tocar límites...")
            move_res = robot.cmd.move_xy(dx, 0)
            if not move_res.get('success'):
                print(f"Error iniciando recorrido: {move_res}")
                return False

            # Esperar finalización normal (no por límite)
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass

            print("Recorrido horizontal terminado en x_edge")
            
            return True
            
        except Exception as e:
            print(f"Error durante escaneado: {e}")
            return False
            
        finally:
            # Cleanup
            print("\n🧹 Limpieza final...")
            
            # Detener scanning
            self.is_scanning = False
            
            # Esperar que termine display thread
            if display_thread.is_alive():
                display_thread.join(timeout=2)
            
            # Detener cámara
            self.stop_live_camera()
            
            # Restaurar velocidades normales
            try:
                result = robot.cmd.set_velocities(
                    RobotConfig.NORMAL_SPEED_H, 
                    RobotConfig.NORMAL_SPEED_V
                )
                if result["success"]:
                    print("Velocidades restauradas a normales")
            except:
                pass
            
            # Limpiar callbacks
            try:
                robot.cmd.uart.set_limit_callback(None)
            except:
                pass
            
            print("Escaneado completado y recursos liberados")

# Función principal para usar desde main_robot.py
def scan_horizontal_with_live_camera(robot):
    """
    Función principal para el escaneado horizontal con cámara en vivo
    Para usar desde main_robot.py
    """
    scanner = HorizontalScanner()
    return scanner.start_scanning_with_movement(robot)


if __name__ == "__main__":
    print("Este módulo debe ser importado desde main_robot.py")
    print("No ejecutar directamente")