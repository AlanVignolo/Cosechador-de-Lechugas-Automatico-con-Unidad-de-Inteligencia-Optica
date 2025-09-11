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
        print("Iniciando cámara en modo video streaming...")
        
        if not self.camera_mgr.initialize_camera():
            print("Error: No se pudo inicializar la cámara")
            return False
        
        # Iniciar video stream a 10 FPS para no saturar (movimiento lento)
        if not self.camera_mgr.start_video_stream(fps=10):
            print("Error: No se pudo iniciar video stream")
            return False
            
        print("Cámara iniciada en modo streaming a 10 FPS")
        return True
    
    def stop_live_camera(self):
        """Detiene la cámara y el video streaming"""
        print("Deteniendo video streaming...")
        self.camera_mgr.stop_video_stream()
        print("Video streaming detenido")
    
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
                    
                    print(f"🎯 CINTA DETECTADA en posición {current_x_mm:.1f}mm - Confianza: {best_candidate['score']:.2f}")
                    
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
        print("🎯 RESUMEN DE DETECCIÓN DE CINTAS")
        print(f"{'='*60}")
        
        if not self.detections:
            print("❌ No se detectaron cintas durante el escaneado")
        else:
            print(f"✅ Se detectaron {len(self.detections)} cintas:")
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
                print(f"\n📏 Distancia promedio entre cintas: {avg_distance:.1f}mm")
        
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
            
            print("Fase 1: Moviendo al switch derecho...")
            
            # Configurar velocidades de homing
            from config.robot_config import RobotConfig
            result = robot.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H, 
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                print(f"Error configurando velocidades: {result}")
                return False
            
            # Configurar callback para límites
            limit_reached = {"reached": False, "type": None}
            
            def on_limit_callback(message):
                limit_reached["reached"] = True
                limit_reached["type"] = message
                print(f"Límite alcanzado: {message}")
            
            robot.cmd.uart.set_limit_callback(on_limit_callback)
            
            # Mover hacia el switch derecho (X negativos)
            print("   Moviendo hacia switch derecho...")
            result = robot.cmd.move_xy(-2000, 0)  # Hacia X negativos (switch derecho)
            
            # Esperar límite derecho
            limit_message = robot.cmd.uart.wait_for_limit(timeout=30.0)
            if not (limit_message and "LIMIT_H_RIGHT_TRIGGERED" in limit_message):
                print("Error: No se alcanzó el límite derecho")
                return False
            
            print("Límite derecho alcanzado")
            
            # 3. Retroceder 1cm
            print("Fase 2: Retrocediendo 1cm desde el switch...")
            result = robot.cmd.move_xy(10, 0)  # 10mm hacia X positivos (alejarse del switch derecho)
            if not result["success"]:
                print(f"Error en retroceso: {result}")
                return False
            
            time.sleep(2)  # Esperar que complete el movimiento
            print("Retroceso completado")
            
            # 4. Recorrido completo hacia el switch izquierdo
            print("Fase 3: Iniciando recorrido horizontal completo...")
            print("Cámara activa - observe el feed de video")
            print("Recorriendo a velocidad de homing...")
            
            # Reiniciar callback para límite izquierdo
            limit_reached = {"reached": False, "type": None}
            robot.cmd.uart.set_limit_callback(on_limit_callback)
            
            # Mover hacia el switch izquierdo (X positivos) - DISTANCIA MUY LARGA
            result = robot.cmd.move_xy(2000, 0)  # 2000mm hacia X positivos (switch izquierdo)
            
            # Esperar límite izquierdo
            print("   Esperando alcanzar límite izquierdo...")
            limit_message = robot.cmd.uart.wait_for_limit(timeout=120.0)  # 2 minutos timeout
            if not (limit_message and "LIMIT_H_LEFT_TRIGGERED" in limit_message):
                print("Error: No se alcanzó el límite izquierdo en tiempo esperado")
                return False
            
            print("Límite izquierdo alcanzado - Recorrido completo terminado")
            
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