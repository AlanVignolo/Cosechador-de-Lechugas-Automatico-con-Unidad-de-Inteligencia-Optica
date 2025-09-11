"""
Escáner Horizontal Simplificado - Versión Funcional
Detecta cintas negras durante el movimiento horizontal con IA simple
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

from camera_manager import get_camera_manager
from robot_controller import RobotController
from config.robot_config import RobotConfig
from simple_tape_detector import SimpleTapeDetector

class SimpleHorizontalScanner:
    def __init__(self):
        self.camera_mgr = get_camera_manager()
        self.detector = SimpleTapeDetector()
        self.is_scanning = False
        self.detections = []
        
    def scan_with_live_camera(self, robot):
        """
        Función principal de escaneo horizontal con detección simple
        """
        print("\n" + "="*60)
        print("ESCANEADO HORIZONTAL SIMPLE CON IA")
        print("="*60)
        
        try:
            # Verificar que el robot esté hecho homing
            if not robot.is_homed:
                print("❌ Error: Robot debe estar hecho homing primero")
                return False
            
            # Verificar posición segura del brazo
            if not robot.arm.is_in_safe_position():
                print("⚠️ Advertencia: El brazo no está en posición segura")
                user_input = input("¿Continuar de todas formas? (s/N): ").lower()
                if user_input != 's':
                    print("Operación cancelada por el usuario")
                    return False
            
            # Inicializar cámara
            print("Iniciando cámara...")
            if not self.camera_mgr.initialize_camera():
                print("❌ Error: No se pudo inicializar la cámara")
                return False
            
            if not self.camera_mgr.start_video_stream(fps=8):
                print("❌ Error: No se pudo iniciar video stream")
                return False
            
            print("✅ Cámara iniciada - Resolución y FPS configurados")
            
            # Configurar velocidades lentas para el escaneado
            robot.cmd.set_speeds(2000, 2000)  # Velocidad lenta para detectar bien
            print("✅ Velocidades configuradas para escaneado")
            
            # Limpiar detecciones anteriores
            self.detections = []
            self.detector.last_detection_position = None
            
            # Iniciar escaneado con movimiento
            success = self._execute_scan_sequence(robot)
            
            # Mostrar resultados
            self._print_scan_results()
            
            return success
            
        except Exception as e:
            print(f"❌ Error durante el escaneado: {e}")
            return False
        finally:
            # Limpiar recursos
            self.is_scanning = False
            self.camera_mgr.stop_video_stream()
            cv2.destroyAllWindows()
            # Restaurar velocidades normales
            robot.cmd.set_speeds(
                RobotConfig.get_normal_speed_x(),
                RobotConfig.get_normal_speed_y()
            )
            print("🔧 Recursos liberados y velocidades restauradas")
    
    def _execute_scan_sequence(self, robot):
        """Ejecuta la secuencia completa de escaneado"""
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
        print("📍 FASE 2: Retrocediendo 1cm desde el switch...")
        result = robot.cmd.move_xy(10, 0)  # 10mm hacia X positivos
        if not result["success"]:
            print(f"❌ Error en retroceso: {result}")
            return False
        
        time.sleep(2)
        print("✅ Retroceso completado")
        
        # Iniciar detección y movimiento
        print("📍 FASE 3: Iniciando escaneado con detección...")
        print("🎥 Cámara activa - Detectando cintas automáticamente")
        
        self.is_scanning = True
        
        # Iniciar hilo de visualización
        video_thread = threading.Thread(target=self._video_detection_loop, args=(robot,))
        video_thread.daemon = True
        video_thread.start()
        
        # Movimiento hacia el switch izquierdo
        print("🚀 Iniciando movimiento lento hacia switch izquierdo...")
        result = robot.cmd.move_xy(2000, 0)  # Hacia X positivos
        
        # Esperar límite izquierdo
        limit_message = robot.cmd.uart.wait_for_limit(timeout=120.0)
        
        # Detener detección
        self.is_scanning = False
        time.sleep(1)  # Dar tiempo para que termine el hilo
        
        if not (limit_message and "LIMIT_H_LEFT_TRIGGERED" in limit_message):
            print("❌ Error: No se alcanzó el límite izquierdo")
            return False
        
        print("✅ Límite izquierdo alcanzado - Escaneado completo")
        return True
    
    def _video_detection_loop(self, robot):
        """Bucle de detección en video separado"""
        print("🎯 Iniciando detección de cintas en tiempo real...")
        
        detection_count = 0
        
        while self.is_scanning:
            try:
                # Obtener frame
                frame = self.camera_mgr.get_latest_video_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # Procesar frame (rotar y recortar como el sistema original)
                processed_frame = self._process_frame(frame)
                
                # Detectar cinta
                detection = self.detector.detect_tape_in_frame(processed_frame)
                
                if detection['detected']:
                    # Obtener posición actual del robot
                    current_pos = robot.get_current_position_relative()
                    current_x_mm = current_pos['position_mm']['x']
                    
                    # Verificar cooldown
                    if self.detector.should_record_detection(current_x_mm):
                        detection_count += 1
                        
                        # Registrar detección
                        detection_record = {
                            'number': detection_count,
                            'position_mm': current_x_mm,
                            'center_x': detection['center_x'],
                            'confidence': detection['confidence'],
                            'timestamp': time.time()
                        }
                        
                        self.detections.append(detection_record)
                        self.detector.record_detection(current_x_mm)
                        
                        print(f"🎯 CINTA #{detection_count} - Posición: {current_x_mm:.1f}mm - Confianza: {detection['confidence']:.2f}")
                
                # Dibujar detección en frame
                display_frame = self.detector.draw_detection(processed_frame, detection)
                
                # Agregar información en pantalla
                cv2.putText(display_frame, f"ESCANER SIMPLE - Detecciones: {len(self.detections)}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(display_frame, "Presiona ESC para detener", 
                           (10, display_frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Mostrar frame
                cv2.imshow("Escaner Horizontal Simple - IA", display_frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    print("🛑 Usuario presionó ESC - Deteniendo detección")
                    self.is_scanning = False
                    break
                
            except Exception as e:
                print(f"⚠️ Error en detección: {e}")
                time.sleep(0.1)
        
        cv2.destroyAllWindows()
        print("🎯 Detección de cintas finalizada")
    
    def _process_frame(self, frame):
        """Procesa el frame como el sistema original"""
        # Rotar 90° anti-horario
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Recortar zona de interés
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * 0.2)
        x2 = int(ancho * 0.8)
        y1 = int(alto * 0.3)
        y2 = int(alto * 0.7)
        
        return frame_rotado[y1:y2, x1:x2]
    
    def _print_scan_results(self):
        """Muestra los resultados del escaneo"""
        print(f"\n{'='*60}")
        print("🎯 RESULTADOS DEL ESCANEADO HORIZONTAL")
        print(f"{'='*60}")
        
        if not self.detections:
            print("❌ No se detectaron cintas durante el escaneado")
            print("💡 Sugerencias:")
            print("   - Verificar que hay cintas negras en el tubo")
            print("   - Ajustar iluminación")
            print("   - Verificar posición de la cámara")
        else:
            print(f"✅ Se detectaron {len(self.detections)} cintas:")
            print(f"{'#':<3} {'Posición (mm)':<15} {'Confianza':<12} {'Centro X':<10}")
            print("-" * 50)
            
            for detection in self.detections:
                number = detection['number']
                position = detection['position_mm']
                confidence = detection['confidence']
                center_x = detection['center_x']
                
                print(f"{number:<3} {position:<15.1f} {confidence:<12.2f} {center_x:<10}")
            
            # Calcular distancias entre cintas
            if len(self.detections) > 1:
                distances = []
                for i in range(1, len(self.detections)):
                    dist = abs(self.detections[i]['position_mm'] - self.detections[i-1]['position_mm'])
                    distances.append(dist)
                
                avg_distance = sum(distances) / len(distances)
                min_distance = min(distances)
                max_distance = max(distances)
                
                print(f"\n📏 Distancia promedio entre cintas: {avg_distance:.1f}mm")
                print(f"📏 Distancia mínima: {min_distance:.1f}mm")
                print(f"📏 Distancia máxima: {max_distance:.1f}mm")
        
        print(f"{'='*60}")
        return self.detections

# Función que busca main_robot.py
def scan_horizontal_with_live_camera(robot):
    """
    Función de interfaz para main_robot.py
    Crea y ejecuta el escáner horizontal simple
    """
    scanner = SimpleHorizontalScanner()
    return scanner.scan_with_live_camera(robot)

if __name__ == "__main__":
    print("=== ESCÁNER HORIZONTAL SIMPLE - MODO DE PRUEBA ===")
    print("Este módulo debe ejecutarse desde main_robot.py")
