from typing import Dict, Tuple, Optional
from .command_manager import CommandManager
from .arm_controller import ArmController
from config.robot_config import RobotConfig
import logging
import time

class RobotController:
    """Controlador principal del robot"""
    
    def __init__(self, command_manager: CommandManager):
        self.cmd = command_manager
        self.logger = logging.getLogger(__name__)
        
        # Estado actual del robot
        self.current_position = {"x": 0.0, "y": 0.0}  # mm
        self.arm_servo1_pos = 90  # muñeca
        self.arm_servo2_pos = 90  # codo  
        self.gripper_state = "unknown"  # open, closed, unknown
        self.is_homed = False
        self.arm = ArmController(command_manager)
        
    def home_robot(self) -> Dict:
        """Función de homing reactiva con feedback de límites"""
        self.logger.info("🏠 Iniciando secuencia de homing reactivo...")
        
        try:
            # Configurar callback para límites
            limit_touched = {"type": None}
            
            def on_limit_touched(message):
                limit_touched["type"] = message
                print(f"   🚨 Límite detectado: {message}")
            
            self.cmd.uart.set_limit_callback(on_limit_touched)
            
            # Paso 1: Configurar velocidades lentas
            print("   📐 Configurando velocidades de homing...")
            result = self.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H, 
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                return {"success": False, "message": "Error configurando velocidades"}
            time.sleep(0.5)
            
            # Paso 2: Mover hacia la DERECHA hasta tocar límite (valores positivos)
            print(f"   ➡️  Moviendo hacia la DERECHA hasta tocar límite...")
            result = self.cmd.move_xy(RobotConfig.HOMING_DISTANCE_H, 0)
            
            # Esperar hasta que se toque el límite DERECHO
            limit_message = self.cmd.uart.wait_for_limit(timeout=30.0)
            if limit_message and "H_RIGHT" in limit_message:
                print("   ✅ Límite derecho alcanzado")
            else:
                return {"success": False, "message": "No se alcanzó límite derecho"}
            
            time.sleep(1)
            
            # Paso 3: Mover hacia arriba hasta tocar límite (valores negativos)
            print(f"   ⬆️  Moviendo hacia arriba hasta tocar límite...")
            result = self.cmd.move_xy(0, -RobotConfig.HOMING_DISTANCE_V)  # ⭐ Y NEGATIVO para ir arriba
            
            # Esperar hasta que se toque el límite superior
            limit_message = self.cmd.uart.wait_for_limit(timeout=180.0)
            if limit_message and "V_UP" in limit_message:
                print("   ✅ Límite superior alcanzado")
            else:
                return {"success": False, "message": "No se alcanzó límite superior"}
            
            time.sleep(1)
            
            # Paso 4: Offset desde límites hacia el área de trabajo
            print(f"   📍 Estableciendo origen ({RobotConfig.HOME_OFFSET_H}mm, {RobotConfig.HOME_OFFSET_V}mm desde límites)...")
            
            # Mover hacia la IZQUIERDA (X negativo) y ABAJO (Y positivo) desde los límites
            result = self.cmd.move_xy(-RobotConfig.HOME_OFFSET_H, RobotConfig.HOME_OFFSET_V)  # ⭐ X-, Y+
            if not result["success"]:
                return {"success": False, "message": "Error en offset"}
            time.sleep(3)
            
            # Paso 5: Establecer origen
            self.current_position = {"x": 0.0, "y": 0.0}
            self.is_homed = True
            
            # Paso 6: Restaurar velocidades normales
            print("   🚀 Restaurando velocidades normales...")
            print(f"      De: H={RobotConfig.HOMING_SPEED_H}, V={RobotConfig.HOMING_SPEED_V}")
            print(f"      A:  H={RobotConfig.NORMAL_SPEED_H}, V={RobotConfig.NORMAL_SPEED_V}")
            
            result = self.cmd.set_velocities(
                RobotConfig.NORMAL_SPEED_H, 
                RobotConfig.NORMAL_SPEED_V
            )
            
            if result["success"]:
                print(f"   ✅ Velocidades restauradas: {result['response']}")
            else:
                print(f"   ⚠️  Error restaurando velocidades: {result}")
            
            self.logger.info("✅ Homing reactivo completado exitosamente")
            return {
                "success": True, 
                "message": "Homing completado exitosamente",
                "position": self.current_position
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error durante homing: {e}")
            # Restaurar velocidades normales
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
            "position": self.current_position,
            "arm": {
                "servo1": self.arm_servo1_pos,
                "servo2": self.arm_servo2_pos
            },
            "gripper": self.gripper_state
        }