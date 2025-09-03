from typing import Dict, Tuple, Optional
from controller.command_manager import CommandManager
from controller.arm_controller import ArmController
from config.robot_config import RobotConfig
import logging
import time

class RobotController:
    def __init__(self, command_manager: CommandManager):
        self.cmd = command_manager
        self.logger = logging.getLogger(__name__)
        
        self.current_position = {"x": 0.0, "y": 0.0}
        self.global_position = {"x": 0.0, "y": 0.0}  # Posición global acumulada
        self.arm_servo1_pos = 90
        self.arm_servo2_pos = 90  
        self.gripper_state = "unknown"
        self.is_homed = False
        self.arm = ArmController(command_manager)
        
        # Configurar callback para tracking de posición
        self._setup_position_tracking()
        
        # Inicializar posición global al arrancar
        self._initialize_global_position()
        
        # Solicitar estado inicial del sistema
        self._request_system_status()
        
    def _request_system_status(self):
        """Solicitar estado inicial del sistema completo"""
        self.logger.info("Solicitando estado inicial del sistema...")
        
        # El ArmController ya solicita su propio estado
        # Aquí podemos solicitar información adicional del sistema si es necesario
        
        # Por ejemplo, consultar límites
        limits_result = self.cmd.check_limits()
        if limits_result["success"]:
            self.logger.info(f"Estado límites: {limits_result['response']}")
    
    def _setup_position_tracking(self):
        """Configurar callback para tracking automático de posición global"""
        self.cmd.uart.set_stepper_callbacks(None, self._on_movement_completed)
    
    def _on_movement_completed(self, message: str):
        """Callback para actualizar posición global cuando se completa un movimiento"""
        try:
            # Limpiar mensaje de posibles mezclas
            clean_message = message.split('\n')[0]
            
            # Formato: STEPPER_MOVE_COMPLETED:pos_h,pos_v,REL:rel_h,rel_v,MM:mm_h,mm_v
            parts = clean_message.split(',')
            if len(parts) >= 6:
                rel_h_mm = float(parts[4].split(':')[1])
                rel_v_mm = float(parts[5])
                
                # Actualizar posición global acumulada
                self.global_position["x"] += rel_h_mm
                self.global_position["y"] += rel_v_mm
                
                self.logger.info(f"Posición global actualizada: X={self.global_position['x']}mm, Y={self.global_position['y']}mm")
                
        except Exception as e:
            self.logger.warning(f"Error actualizando posición global: {e}")
    
    def reset_global_position(self, x: float = 0.0, y: float = 0.0):
        """Resetear posición global (usado en homing)"""
        self.global_position["x"] = x
        self.global_position["y"] = y
        self.logger.info(f"Posición global reseteada a: X={x}mm, Y={y}mm")
    
    def _initialize_global_position(self):
        """Inicializar posición global al arrancar Python"""
        # Asumir posición desconocida al inicio - será 0,0 tras homing
        self.global_position = {"x": 0.0, "y": 0.0}
        self.logger.info("Posición global inicializada - usar HOMING para establecer origen")
    def home_robot(self) -> Dict:
        self.logger.info("Iniciando secuencia de homing reactivo...")
        
        try:
            print("Verificando posición del brazo...")
            if not self.arm.is_in_safe_position():
                print("Brazo no está en posición segura. Moviendo...")
                result = self.arm.ensure_safe_position()
                if not result["success"]:
                    return {"success": False, "message": "No se pudo mover brazo a posición segura"}
                print("Brazo en posición segura")
            
            limit_touched = {"type": None}
            
            def on_limit_touched(message):
                limit_touched["type"] = message
                print(f"Límite detectado: {message}")
            
            self.cmd.uart.set_limit_callback(on_limit_touched)
            
            print("Configurando velocidades de homing...")
            result = self.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H, 
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                return {"success": False, "message": "Error configurando velocidades"}
            
            print("Moviendo hacia la DERECHA hasta tocar límite...")
            result = self.cmd.move_xy(RobotConfig.HOMING_DISTANCE_H, 0)
            
            limit_message = self.cmd.uart.wait_for_limit(timeout=30.0)
            if limit_message and "LIMIT_H_RIGHT_TRIGGERED" in limit_message:
                print("Límite derecho alcanzado")
            else:
                return {"success": False, "message": "No se alcanzó límite derecho"}
            
            print("Moviendo hacia arriba hasta tocar límite...")
            result = self.cmd.move_xy(0, -RobotConfig.HOMING_DISTANCE_V)
            
            limit_message = self.cmd.uart.wait_for_limit(timeout=180.0)
            if limit_message and "LIMIT_V_UP_TRIGGERED" in limit_message:
                print("Límite superior alcanzado")
            else:
                return {"success": False, "message": "No se alcanzó límite superior"}
            
            print(f"Estableciendo origen ({RobotConfig.HOME_OFFSET_H}mm, {RobotConfig.HOME_OFFSET_V}mm desde límites)...")
            
            result = self.cmd.move_xy(-RobotConfig.HOME_OFFSET_H, RobotConfig.HOME_OFFSET_V)
            if not result["success"]:
                return {"success": False, "message": "Error en offset"}
            
            # Esperar que complete el movimiento - usar método simple de timeout en lugar de eventos
            print("Esperando completar movimiento de offset...")
            time.sleep(3.0)  # Dar tiempo suficiente para que complete el movimiento de offset
            
            # Verificar si llegaron mensajes de completado
            completed = True  # Asumir que se completó después del delay
            
            # Opcionalmente drenar la cola de mensajes para limpiar
            try:
                while True:
                    msg = self.cmd.uart.message_queue.get_nowait()
                    self.logger.debug(f"Mensaje drenado durante offset: {msg}")
            except:
                pass
            
            self.current_position = {"x": 0.0, "y": 0.0}
            self.is_homed = True
            
            print("Restaurando velocidades normales...")
            result = self.cmd.set_velocities(
                RobotConfig.NORMAL_SPEED_H, 
                RobotConfig.NORMAL_SPEED_V
            )
            
            if result["success"]:
                print(f"Velocidades restauradas: {result['response']}")
            else:
                print(f"Error restaurando velocidades: {result}")
            
            self.logger.info("Homing reactivo completado exitosamente")
            return {
                "success": True, 
                "message": "Homing completado exitosamente",
                "position": self.current_position
            }
            
        except Exception as e:
            self.logger.error(f"Error durante homing: {e}")
            try:
                self.cmd.set_velocities(RobotConfig.NORMAL_SPEED_H, RobotConfig.NORMAL_SPEED_V)
            except:
                pass
            return {"success": False, "message": f"Error durante homing: {str(e)}"}
    
    def move_to_absolute(self, x: float, y: float) -> Dict:
        """Mover a posición absoluta (verifica posición segura del brazo)"""
        if not self.is_homed:
            return {"success": False, "message": "⚠️  Robot no está homed"}
        
        # VERIFICAR QUE EL BRAZO ESTÉ EN POSICIÓN SEGURA
        if not self.arm.is_in_safe_position():
            self.logger.warning("⚠️  Brazo no está en posición segura. Moviendo...")
            result = self.arm.ensure_safe_position()
            if not result["success"]:
                return {"success": False, "message": "No se pudo mover brazo a posición segura"}
        
        # Verificar límites del workspace
        if x < 0 or x > RobotConfig.MAX_X or y < 0 or y > RobotConfig.MAX_Y:
            return {"success": False, "message": f"Posición fuera de límites"}
        
        # Calcular y ejecutar movimiento
        delta_x = x - self.current_position["x"]
        delta_y = y - self.current_position["y"]
        
        result = self.cmd.move_xy(delta_x, delta_y)
        
        if result["success"]:
            self.current_position["x"] = x
            self.current_position["y"] = y
            self.logger.info(f"Movido a posición absoluta: ({x}, {y})")
        
        return result
    
    def get_status(self) -> Dict:
        """Obtener estado completo del robot"""
        return {
            "homed": self.is_homed,
            "position": self.global_position,  # Usar posición global acumulada
            "arm": {
                "servo1": self.arm_servo1_pos,
                "servo2": self.arm_servo2_pos
            },
            "gripper": self.gripper_state
        }
    def calibrate_workspace(self) -> Dict:
        """Calibración del workspace usando distancias del config"""
        print("🔧 Iniciando calibración del workspace...")
        
        try:
            # 0. Verificar que brazo esté en posición segura
            print("🤖 Verificando posición del brazo...")
            if not self.arm.is_in_safe_position():
                print("   ⚠️  Brazo no está en posición segura. Moviendo...")
                result = self.arm.ensure_safe_position()
                if not result["success"]:
                    return {"success": False, "message": "No se pudo mover brazo a posición segura"}
                print("   ✅ Brazo en posición segura")
            else:
                print("   ✅ Brazo ya está en posición segura")
            
            # 1. Homing inicial
            print("📍 Paso 1: Homing inicial...")
            result = self.home_robot()
            if not result["success"]:
                return {"success": False, "message": "Error en homing inicial"}
            time.sleep(2)
            
            measurements = {}
            
            # 2. Calibrar horizontal (izquierda)
            print("📏 Paso 2: Calibrando horizontal (izquierda)...")
            
            # Configurar velocidades de homing
            self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            time.sleep(0.5)
            
            # Activar modo calibración
            self.cmd.uart.send_command("CS")
            time.sleep(0.5)
            
            # Usar distancia del config
            distance_mm = RobotConfig.HOMING_DISTANCE_H
            result = self.cmd.move_xy(-distance_mm, 0)
            
            # Esperar límite y capturar pasos
            limit_message = self.cmd.uart.wait_for_limit(timeout=30.0)
            if "LIMIT_H_LEFT_TRIGGERED" in limit_message:
                print("   ✅ Límite izquierdo alcanzado")
                
                # ⭐ CAPTURAR PASOS DE CALIBRACIÓN
                steps_value = self._wait_for_calibration_steps()
                if steps_value is not None:
                    steps = steps_value
                    horizontal_mm = steps / RobotConfig.STEPS_PER_MM_H
                    measurements["horizontal_steps"] = steps
                    measurements["horizontal_mm"] = round(horizontal_mm, 1)
                    print(f"      📐 Distancia horizontal: {horizontal_mm:.1f}mm ({steps} pasos)")
            
            # 3. Calibrar vertical (abajo)
            print("📏 Paso 3: Calibrando vertical (abajo)...")
            
            # Configurar velocidades de homing
            self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            time.sleep(0.5)
            
            # Activar modo calibración
            self.cmd.uart.send_command("CS")
            time.sleep(0.5)
            
            distance_mm = RobotConfig.HOMING_DISTANCE_V
            result = self.cmd.move_xy(0, distance_mm)
            
            # Esperar límite y capturar pasos
            limit_message = self.cmd.uart.wait_for_limit(timeout=30.0)
            if "LIMIT_V_DOWN_TRIGGERED" in limit_message:
                print("   ✅ Límite inferior alcanzado")
                
                # ⭐ CAPTURAR PASOS DE CALIBRACIÓN
                steps_value = self._wait_for_calibration_steps()
                if steps_value is not None:
                    steps = steps_value
                    vertical_mm = steps / RobotConfig.STEPS_PER_MM_V
                    measurements["vertical_steps"] = steps
                    measurements["vertical_mm"] = round(vertical_mm, 1)
                    print(f"      📐 Distancia vertical: {vertical_mm:.1f}mm ({steps} pasos)")
            
            # 4. Homing final
            print("🏠 Paso 4: Homing final...")
            
            # Desactivar modo calibración antes del homing
            self.cmd.uart.send_command("CE")
            time.sleep(0.5)
            
            # Alejarse de los límites para dar espacio al homing
            print("   📦 Alejándose de límites...")
            result = self.cmd.move_xy(50, -50)  # Moverse hacia derecha y arriba
            if result["success"]:
                time.sleep(3.0)  # Dar tiempo para completar movimiento
            
            # Limpiar callbacks y colas de mensajes antes del homing final
            self.cmd.uart.set_limit_callback(None)
            try:
                while True:
                    self.cmd.uart.message_queue.get_nowait()
            except:
                pass
            
            # HOMING DIRECTO - evitar recursión
            print("   🎯 Ejecutando homing directo...")
            
            # Configurar velocidades de homing
            result = self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            if not result["success"]:
                return {"success": False, "message": "Error configurando velocidades de homing final"}
            
            # Configurar callback para límites
            limit_touched = {"type": None}
            def on_limit_touched_final(message):
                limit_touched["type"] = message
                print(f"      Límite detectado: {message}")
            
            self.cmd.uart.set_limit_callback(on_limit_touched_final)
            
            # Ir a límite derecho
            print("      → Moviendo hacia límite derecho...")
            result = self.cmd.move_xy(RobotConfig.HOMING_DISTANCE_H, 0)
            limit_message = self.cmd.uart.wait_for_limit(timeout=30.0)
            if not (limit_message and "LIMIT_H_RIGHT_TRIGGERED" in limit_message):
                return {"success": False, "message": "No se alcanzó límite derecho en homing final"}
            
            # Ir a límite superior
            print("      → Moviendo hacia límite superior...")
            result = self.cmd.move_xy(0, -RobotConfig.HOMING_DISTANCE_V)
            limit_message = self.cmd.uart.wait_for_limit(timeout=30.0)
            if not (limit_message and "LIMIT_V_UP_TRIGGERED" in limit_message):
                return {"success": False, "message": "No se alcanzó límite superior en homing final"}
            
            # APLICAR OFFSET CRÍTICO
            print(f"      → Aplicando offset ({RobotConfig.HOME_OFFSET_H}mm, {RobotConfig.HOME_OFFSET_V}mm)...")
            result = self.cmd.move_xy(-RobotConfig.HOME_OFFSET_H, RobotConfig.HOME_OFFSET_V)
            if not result["success"]:
                return {"success": False, "message": "Error aplicando offset en homing final"}
            
            # Esperar completar offset
            time.sleep(3.0)
            
            # Establecer origen y estado
            self.current_position = {"x": 0.0, "y": 0.0}
            self.reset_global_position(0.0, 0.0)  # Resetear posición global tras homing
            self.is_homed = True
            
            # Restaurar velocidades normales
            result = self.cmd.set_velocities(RobotConfig.NORMAL_SPEED_H, RobotConfig.NORMAL_SPEED_V)
            if result["success"]:
                print(f"      ✅ Velocidades restauradas: {result['response']}")
            
            print("   ✅ Homing final completado")
            
            return {"success": True, "message": "Calibración completada", "measurements": measurements}
            
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}

    def _wait_for_calibration_steps(self, timeout: float = 5.0) -> Optional[int]:
        """Esperar mensaje de pasos de calibración del micro.
        Acepta 'CALIBRATION_STEPS:<n>' o 'CALIBRATION_COMPLETED:<n>' y devuelve <n> como int."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = self.cmd.uart.message_queue.get(timeout=0.5)
                if "CALIBRATION_STEPS:" in message or "CALIBRATION_COMPLETED:" in message:
                    try:
                        value = int(message.split(":")[1])
                        return value
                    except Exception:
                        continue
            except:
                continue
        
        return None