"""
Escáner Horizontal con Cámara en Vivo
Detecta cintas negras mientras se mueve horizontalmente a lo largo del tubo
"""

import cv2
import time
import threading
import sys
import os

# Importar camera manager
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

class HorizontalScanner:
    def __init__(self):
        self.camera_mgr = get_camera_manager()
        self.is_scanning = False
        self.scan_thread = None
        self.detections = []
        
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
    
    def display_live_feed(self):
        """Muestra el feed de video en tiempo real en una ventana"""
        print("Iniciando visualización en vivo...")
        print("Presiona 'q' para detener la visualización")
        
        while self.is_scanning:
            # Obtener frame más reciente
            frame = self.camera_mgr.get_latest_video_frame()
            
            if frame is not None:
                # Rotar frame para orientación correcta (como en detector horizontal)
                frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                
                # Aplicar recorte similar al detector horizontal
                alto, ancho = frame_rotado.shape[:2]
                recorte_config = {
                    'x_inicio': 0.2,
                    'x_fin': 0.8,
                    'y_inicio': 0.3,
                    'y_fin': 0.7
                }
                
                x1 = int(ancho * recorte_config['x_inicio'])
                x2 = int(ancho * recorte_config['x_fin'])
                y1 = int(alto * recorte_config['y_inicio'])
                y2 = int(alto * recorte_config['y_fin'])
                
                frame_recortado = frame_rotado[y1:y2, x1:x2]
                
                # Agregar información en pantalla
                cv2.putText(frame_recortado, "ESCANER HORIZONTAL - EN VIVO", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame_recortado, f"Detecciones: {len(self.detections)}", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(frame_recortado, "Presiona 'q' para salir", 
                           (10, frame_recortado.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Mostrar frame
                cv2.imshow("Escaner Horizontal - Live Feed", frame_recortado)
                
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
            
            # Mover hacia el switch derecho (movimiento hacia la izquierda)
            print("   Moviendo hacia switch derecho...")
            result = robot.cmd.move_xy(RobotConfig.get_homing_direction_x(), 0)
            
            # Esperar límite derecho
            limit_message = robot.cmd.uart.wait_for_limit(timeout=30.0)
            if not (limit_message and "LIMIT_H_RIGHT_TRIGGERED" in limit_message):
                print("Error: No se alcanzó el límite derecho")
                return False
            
            print("Límite derecho alcanzado")
            
            # 3. Retroceder 1cm
            print("Fase 2: Retrocediendo 1cm desde el switch...")
            result = robot.cmd.move_xy(10, 0)  # 10mm hacia la derecha
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
            
            # Mover hacia el switch izquierdo (movimiento hacia la derecha) - DISTANCIA MUY LARGA
            result = robot.cmd.move_xy(-2000, 0)  # 2000mm hacia la izquierda - debería alcanzar límite antes
            
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