from typing import Dict, Optional
from .uart_manager import UARTManager
import time
import logging

class CommandManager:
    def __init__(self, uart_manager: UARTManager):
        self.uart = uart_manager
        self.logger = logging.getLogger(__name__)
    
    def move_xy(self, x_mm: float, y_mm: float) -> Dict:
        """Mover a posición X,Y en mm (relativo)"""
        command = f"M:{x_mm},{y_mm}"
        return self.uart.send_command(command)
    
    def get_system_status(self) -> Dict:
        """Solicitar estado completo del sistema"""
        return self.uart.send_command("S?")
    
    def set_velocities(self, h_speed: int, v_speed: int) -> Dict:
        """Configurar velocidades máximas"""
        command = f"V:{h_speed},{v_speed}"
        return self.uart.send_command(command)
    
    def move_arm(self, servo1_angle: int, servo2_angle: int, time_ms: int = 0) -> Dict:
        """Mover brazo (servo1=muñeca, servo2=codo)"""
        a1 = max(10, min(160, int(servo1_angle)))
        a2 = max(10, min(160, int(servo2_angle)))
        t = max(0, int(time_ms))
        command = f"A:{a1},{a2},{t}"
        return self.uart.send_command(command)
    
    def move_servo(self, servo_num: int, angle: int) -> Dict:
        """Mover servo individual"""
        sn = 1 if int(servo_num) != 2 else 2
        a = max(10, min(160, int(angle)))
        command = f"P:{sn},{a}"
        return self.uart.send_command(command)
    
    def reset_arm(self) -> Dict:
        """Resetear brazo a posición 90°"""
        return self.uart.send_command("RA")
    
    def gripper_toggle(self) -> Dict:
        """Accionar gripper - alterna entre abierto y cerrado automáticamente"""
        print("🔧 Accionando gripper...")
        result = self.uart.send_command("GT")
        print(f"   Respuesta: {result.get('response', 'Sin respuesta')}")
        return result

    # Mantener las funciones antiguas para compatibilidad, pero que usen toggle
    def gripper_open(self) -> Dict:
        """Abrir gripper (usa toggle interno)"""
        return self.gripper_toggle()

    def gripper_close(self) -> Dict:
        """Cerrar gripper (usa toggle interno)"""
        return self.gripper_toggle()
    
    def emergency_stop(self) -> Dict:
        """Parada de emergencia"""
        return self.uart.send_command("S")
    
    def wait_for_completion(self, timeout: float = 30.0) -> bool:
        """Esperar a que termine el movimiento actual"""
        # Implementar polling del estado o usar timeout
        time.sleep(0.5)  # Por ahora simple delay
        return True
    
    def get_servo_positions(self) -> Dict:
        """Consultar posiciones actuales de los servos"""
        return self.uart.send_command("Q")
    
    def get_movement_progress(self) -> Dict:
        """Obtener el progreso del movimiento actual (tomar snapshot) - no bloqueante"""
        # Enviar comando sin esperar respuesta específica
        if not self.uart.ser or not self.uart.ser.is_open:
            return {"success": False, "error": "Puerto no conectado"}
        
        try:
            cmd_formatted = f"<RP>"
            self.uart.ser.write(cmd_formatted.encode('utf-8'))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_limits(self) -> Dict:
        """Consultar estado de límites"""
        return self.uart.check_limits()
    
    def get_gripper_status(self) -> Dict:
        """Consultar estado actual del gripper"""
        return self.uart.send_command("G?")
    
    def gripper_open_and_wait(self, timeout: float = 10.0) -> Dict:
        """Abrir gripper y esperar confirmación"""
        # Enviar comando
        result = self.uart.send_command("G:O")
        if not result["success"]:
            return result
        
        # Esperar confirmación
        confirmation = self.uart.wait_for_message("GRIPPER_OPENED", timeout)
        if confirmation:
            return {"success": True, "message": "Gripper abierto confirmado"}
        else:
            return {"success": False, "message": "Timeout esperando confirmación de apertura"}

    def gripper_close_and_wait(self, timeout: float = 10.0) -> Dict:
        """Cerrar gripper y esperar confirmación"""
        # Enviar comando
        result = self.uart.send_command("G:C")
        if not result["success"]:
            return result
        
        # Esperar confirmación
        confirmation = self.uart.wait_for_message("GRIPPER_CLOSED", timeout)
        if confirmation:
            return {"success": True, "message": "Gripper cerrado confirmado"}
        else:
            return {"success": False, "message": "Timeout esperando confirmación de cierre"}