from typing import Dict, Optional
from .uart_manager import UARTManager
import time
import logging

class CommandManager:
    def __init__(self, uart_manager: UARTManager):
        self.uart = uart_manager
        self.logger = logging.getLogger(__name__)
    
    def move_xy(self, x_mm: float, y_mm: float) -> Dict:
        command = f"M:{x_mm},{y_mm}"
        self.logger.debug(f"Movimiento: X={x_mm}mm, Y={y_mm}mm")
        return self.uart.send_command(command)


    def get_system_status(self) -> Dict:
        return self.uart.send_command("S?")


    def set_velocities(self, h_speed: int, v_speed: int) -> Dict:
        command = f"V:{h_speed},{v_speed}"
        return self.uart.send_command(command)


    def move_arm(self, servo1_angle: int, servo2_angle: int, time_ms: int = 0) -> Dict:
        a1 = max(10, min(160, int(servo1_angle)))
        a2 = max(10, min(160, int(servo2_angle)))
        t = max(0, int(time_ms))
        command = f"A:{a1},{a2},{t}"
        return self.uart.send_command(command)


    def move_servo(self, servo_num: int, angle: int) -> Dict:
        sn = 1 if int(servo_num) != 2 else 2
        a = max(10, min(160, int(angle)))
        command = f"P:{sn},{a}"
        return self.uart.send_command(command)


    def reset_arm(self) -> Dict:
        return self.uart.send_command("RA")


    def gripper_toggle(self) -> Dict:
        print("Accionando gripper...")
        result = self.uart.send_command("GT")
        print(f"   Respuesta: {result.get('response', 'Sin respuesta')}")
        return result

    def gripper_open(self) -> Dict:
        return self.gripper_toggle()

    def gripper_close(self) -> Dict:
        return self.gripper_toggle()


    def emergency_stop(self) -> Dict:
        return self.uart.send_command("S")

    def wait_for_completion(self, timeout: float = 30.0) -> bool:
        time.sleep(0.5)
        return True


    def get_servo_positions(self) -> Dict:
        return self.uart.send_command("Q")

    def get_movement_progress(self) -> Dict:
        if not self.uart.ser or not self.uart.ser.is_open:
            return {"success": False, "error": "Puerto no conectado"}
        
        try:
            cmd_formatted = f"<RP>"
            self.uart.ser.write(cmd_formatted.encode('utf-8'))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


    def check_limits(self) -> Dict:
        return self.uart.check_limits()

    def get_gripper_status(self) -> Dict:
        return self.uart.send_command("G?")

    def gripper_open_and_wait(self, timeout: float = 10.0) -> Dict:
        result = self.uart.send_command("G:O")
        if not result["success"]:
            return result

        confirmation = self.uart.wait_for_message("GRIPPER_OPENED", timeout)
        if confirmation:
            return {"success": True, "message": "Gripper abierto confirmado"}
        else:
            return {"success": False, "message": "Timeout esperando confirmación de apertura"}

    def gripper_close_and_wait(self, timeout: float = 10.0) -> Dict:
        result = self.uart.send_command("G:C")
        if not result["success"]:
            return result

        confirmation = self.uart.wait_for_message("GRIPPER_CLOSED", timeout)
        if confirmation:
            return {"success": True, "message": "Gripper cerrado confirmado"}
        else:
            return {"success": False, "message": "Timeout esperando confirmación de cierre"}


    def get_current_position_mm(self) -> Dict:
        return self.uart.send_command("XY?")