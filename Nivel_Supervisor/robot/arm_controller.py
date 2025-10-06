import logging
from typing import Dict, Optional, Tuple
from hardware.command_manager import CommandManager
from .arm_states import ARM_STATES, MOVEMENT_TIMING
from .trajectories import TrajectoryDefinitions, validate_trajectory, get_trajectory_time_estimate
import threading

class ArmController:
    def __init__(self, command_manager: CommandManager):
        self.cmd = command_manager
        self.logger = logging.getLogger(__name__)
        
        self.current_state = "unknown"
        self.current_position = (90, 90)
        self.gripper_state = "unknown"

        self.lettuce_on = True
        
        self.is_executing_trajectory = False
        self.current_trajectory = None
        self.current_step_index = 0
        
        self._setup_callbacks()
        self._request_initial_state()
    
    def _setup_callbacks(self):
        self.cmd.uart.set_status_callback(self._on_system_status_received)
        self.cmd.uart.set_servo_callbacks(self._on_servo_started, self._on_servo_completed)
        self.cmd.uart.set_gripper_callbacks(self._on_gripper_started, self._on_gripper_completed)
        self.cmd.uart.set_stepper_callbacks(self._on_stepper_started, self._on_stepper_completed)
    
    def _request_initial_state(self):
        self.logger.info("Solicitando estado inicial del microcontrolador...")

        servo_result = self.cmd.get_servo_positions()
        if servo_result["success"] and "SERVO_POS:" in servo_result["response"]:
            try:
                response_clean = servo_result["response"].split('\n')[0].strip()
                pos_str = response_clean.split("SERVO_POS:")[1].strip()
                pos_parts = pos_str.split(",")
                servo1 = int(pos_parts[0].strip())
                servo2 = int(pos_parts[1].strip())
                self.current_position = (servo1, servo2)
                self.current_state = self._determine_state_from_position(servo1, servo2)
                self.logger.info(f"Estado inicial: {self.current_state} pos=({servo1},{servo2})")
            except Exception as e:
                self.logger.error(f"Error parseando posición de servos: {e}")
                try:
                    import re
                    response = servo_result["response"]
                    match = re.search(r'SERVO_POS:(\d+),(\d+)', response)
                    if match:
                        servo1, servo2 = int(match.group(1)), int(match.group(2))
                        self.current_position = (servo1, servo2)
                        self.current_state = self._determine_state_from_position(servo1, servo2)
                        self.logger.info(f"Estado inicial (método alternativo): {self.current_state} pos=({servo1},{servo2})")
                except Exception as e2:
                    self.logger.error(f"Error en método alternativo: {e2}")

        gripper_result = self.cmd.get_gripper_status()
        if gripper_result["success"] and "GRIPPER_STATUS:" in gripper_result["response"]:
            try:
                status_str = gripper_result["response"].split("GRIPPER_STATUS:")[1]
                state = status_str.split(",")[0].lower()
                self.gripper_state = state
                self.logger.info(f"Estado gripper inicial: {state}")
            except Exception as e:
                self.logger.error(f"Error parseando estado del gripper: {e}")
    
    def _on_system_status_received(self, message: str):
        try:
            clean_message = message.split('\n')[0].strip()
            status_part = clean_message.split("SYSTEM_STATUS:")[1]
            parts = status_part.split(",")
            
            servo1 = int(parts[0].split("=")[1].strip())
            servo2 = int(parts[1].split("=")[1].strip())
            gripper_state = parts[2].split("=")[1].strip().lower()
            
            self.current_position = (servo1, servo2)
            self.gripper_state = gripper_state
            self.current_state = self._determine_state_from_position(servo1, servo2)
            
            self.logger.info(f"Estado actualizado: {self.current_state} pos=({servo1},{servo2}) gripper={gripper_state}")
            
        except Exception as e:
            self.logger.error(f"Error procesando estado del sistema: {e}")
    
    def _on_servo_started(self, message: str):
        self.logger.debug(f"Servo iniciado: {message}")
    
    def _on_servo_completed(self, message: str):
        self.logger.debug(f"Servo completado: {message}")
        if self.is_executing_trajectory:
            self._continue_trajectory()
    
    def _on_gripper_started(self, message: str):
        self.logger.debug(f"Gripper iniciado: {message}")
    
    def _on_gripper_completed(self, message: str):
        self.logger.debug(f"Gripper completado: {message}")
        
        if "OPEN" in message:
            self.gripper_state = "open"
        elif "CLOSED" in message:
            self.gripper_state = "closed"
            
        if self.is_executing_trajectory:
            self._continue_trajectory()
    
    def _on_stepper_started(self, message: str):
        self.logger.debug(f"Stepper iniciado: {message}")
    
    def _on_stepper_completed(self, message: str):
        self.logger.debug(f"Stepper completado: {message}")
    
    def get_current_state(self, force_refresh: bool = False) -> Dict:
        if force_refresh:
            self._detect_initial_state()

        if self.current_state == "unknown":
            detected = self._determine_state_from_position(self.current_position[0], self.current_position[1])
            if detected != "unknown":
                self.logger.info(f"Auto-corrección: estado detectado como '{detected}' desde posición {self.current_position}")
                self.current_state = detected

        return {
            "state": self.current_state,
            "position": self.current_position,
            "gripper": self.gripper_state,
            "available_states": list(ARM_STATES.keys()),
            "is_safe": self.is_in_safe_position(),
            "is_known": self.current_state != "unknown",
            "is_executing": self.is_executing_trajectory
        }


    def is_in_safe_position(self) -> bool:
        safe_states = ["movimiento", "mover_lechuga"]

        if self.current_state in safe_states:
            return True

        if self.current_state == "unknown":
            servo1, servo2 = self.current_position
            tolerance = 5

            for safe_state in safe_states:
                target_config = ARM_STATES[safe_state]
                position_matches = (
                    abs(servo1 - target_config["servo1"]) <= tolerance and
                    abs(servo2 - target_config["servo2"]) <= tolerance
                )
                if position_matches:
                    self.logger.info(f"Auto-corrección: brazo en estado seguro '{safe_state}' {self.current_position}")
                    self.current_state = safe_state
                    return True

        return False


    def is_in_movement_position(self) -> bool:
        if self.current_state == "movimiento":
            return True

        if self.current_state == "unknown":
            servo1, servo2 = self.current_position
            target_config = ARM_STATES["movimiento"]
            tolerance = 5
            position_matches = (
                abs(servo1 - target_config["servo1"]) <= tolerance and
                abs(servo2 - target_config["servo2"]) <= tolerance
            )
            if position_matches:
                self.logger.info(f"Auto-corrección: brazo en posición 'movimiento' {self.current_position}")
                self.current_state = "movimiento"
                return True

        return False
    
    def ensure_safe_position(self) -> Dict:
        if self.is_in_safe_position():
            self.logger.info("Brazo ya está en posición segura")
            return {"success": True, "message": "Ya en posición segura"}
        
        closest_safe_state = self._get_closest_safe_position()
        
        self.logger.info(f"Moviendo brazo a posición segura más cercana: {closest_safe_state}")
        return self.change_state(closest_safe_state)
    
    def _get_closest_safe_position(self) -> str:
        safe_states = ["movimiento", "mover_lechuga"]
        current_servo1, current_servo2 = self.current_position

        min_distance = float('inf')
        closest_state = "movimiento"
        
        for state in safe_states:
            target_config = ARM_STATES[state]
            target_servo1 = target_config["servo1"]
            target_servo2 = target_config["servo2"]

            distance = ((current_servo1 - target_servo1) ** 2 + (current_servo2 - target_servo2) ** 2) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                closest_state = state
        
        self.logger.info(f"Estado más cercano: {closest_state} (distancia: {min_distance:.1f})")
        return closest_state
    
    def change_state(self, target_state: str) -> Dict:
        if target_state not in ARM_STATES:
            return {"success": False, "message": f"Estado '{target_state}' no existe"}
        
        if self.current_state == target_state:
            return {"success": True, "message": f"Ya está en estado '{target_state}'"}
        
        if self.is_executing_trajectory:
            return {"success": False, "message": "Ya ejecutando una trayectoria"}
        
        trajectory = TrajectoryDefinitions.get_trajectory(self.current_state, target_state, self.lettuce_on)
        
        if not trajectory:
            return {
                "success": False, 
                "message": f"No hay trayectoria definida de '{self.current_state}' → '{target_state}'"
            }
        
        estimated_time = get_trajectory_time_estimate(trajectory)
        print(f"Ejecutando: {trajectory['description']}")
        print(f"Tiempo estimado: {estimated_time:.1f} segundos")
        
        result = self.execute_trajectory(trajectory, target_state)
        return result
    
    def execute_trajectory(self, trajectory: dict, target_state: str = None) -> Dict:
        if not validate_trajectory(trajectory):
            return {"success": False, "message": "Trayectoria inválida"}
        
        if self.is_executing_trajectory:
            return {"success": False, "message": "Ya ejecutando una trayectoria"}
        
        self.logger.info(f"Ejecutando: {trajectory['description']}")
        
        self.is_executing_trajectory = True
        self.current_trajectory = trajectory
        self.current_step_index = 0
        self.target_state = target_state
        
        result = self._execute_current_step()
        
        if not result["success"]:
            self.is_executing_trajectory = False
            self.current_trajectory = None
            
        return result
    
    def _execute_current_step(self) -> Dict:
        if not self.is_executing_trajectory or not self.current_trajectory:
            return {"success": False, "message": "No hay trayectoria en ejecución"}
        
        if self.current_step_index >= len(self.current_trajectory["steps"]):
            return self._complete_trajectory()
        
        step = self.current_trajectory["steps"][self.current_step_index]
        print(f"Paso {self.current_step_index + 1}/{len(self.current_trajectory['steps'])}: {step['description']}")
        
        if step["type"] == "gripper":
            return self._execute_gripper_action(step)
        elif step["type"] == "arm_move":
            return self._execute_arm_movement(step)
        else:
            self.logger.warning(f"Tipo de paso desconocido: {step['type']}")
            self._continue_trajectory()
            return {"success": True, "message": "Paso omitido"}
    
    def _execute_gripper_action(self, step: Dict) -> Dict:
        target_action = step["action"]

        status_result = self.cmd.get_gripper_status()
        
        if status_result["success"] and "GRIPPER_STATUS:" in status_result["response"]:
            try:
                response = status_result["response"]
                status_part = response.split("GRIPPER_STATUS:")[1]
                current_state = status_part.split(",")[0].lower()

                if (target_action == "open" and current_state == "closed") or \
                   (target_action == "close" and current_state == "open"):
                    
                    result = self.cmd.gripper_toggle()
                    if result["success"]:
                        return {"success": True, "message": f"Gripper cambiando a {target_action}"}
                    else:
                        return result
                else:
                    self.gripper_state = target_action
                    self._continue_trajectory()
                    return {"success": True, "message": f"Gripper ya estaba {target_action}"}
                    
            except Exception as e:
                result = self.cmd.gripper_toggle()
                if result["success"]:
                    return {"success": True, "message": f"Gripper accionado"}
                return result
        else:
            result = self.cmd.gripper_toggle()
            if result["success"]:
                return {"success": True, "message": f"Gripper accionado"}
            return result
    
    def _execute_arm_movement(self, step: Dict) -> Dict:
        servo1 = step["servo1"]
        servo2 = step["servo2"]
        time_ms = step["time_ms"]
        
        result = self.cmd.move_arm(servo1, servo2, time_ms)
        
        if result["success"]:
            self.current_position = (servo1, servo2)
            return {"success": True, "message": f"Brazo moviéndose a ({servo1}°, {servo2}°)"}
        else:
            return result
    
    def _continue_trajectory(self):
        self.current_step_index += 1

        def execute_next():
            import time
            time.sleep(0.05)
            self._execute_current_step()

        threading.Thread(target=execute_next, daemon=True).start()
    
    def _complete_trajectory(self) -> Dict:
        final_state = self.target_state

        if final_state:
            target_config = ARM_STATES[final_state]
            self.current_position = (target_config["servo1"], target_config["servo2"])
            self.current_state = final_state
            if target_config["gripper"] != "any":
                self.gripper_state = target_config["gripper"]

            self.logger.info(f"Estado actualizado a: {final_state} pos={self.current_position}")

        self.is_executing_trajectory = False
        self.current_trajectory = None
        self.current_step_index = 0
        self.target_state = None

        self.logger.info("Trayectoria completada exitosamente")
        return {"success": True, "message": "Trayectoria completada"}
    
    def stop_trajectory(self) -> Dict:
        if not self.is_executing_trajectory:
            return {"success": False, "message": "No hay trayectoria en ejecución"}
        
        self.is_executing_trajectory = False
        self.current_trajectory = None
        self.current_step_index = 0
        self.target_state = None

        self.cmd.emergency_stop()
        
        return {"success": True, "message": "Trayectoria detenida"}
    
    def get_gripper_real_status(self) -> Dict:
        result = self.cmd.get_gripper_status()
        if result["success"]:
            response = result["response"]
            if "GRIPPER_STATUS:" in response:
                status_str = response.split("GRIPPER_STATUS:")[1].strip()
                status_line = status_str.split('\n')[0].strip()
                parts = status_line.split(",")
                if len(parts) >= 2:
                    state = parts[0].strip()
                    position_str = parts[1].strip()
                    try:
                        position = int(position_str)
                        return {
                            "success": True,
                            "state": state.lower(),
                            "position": position
                        }
                    except ValueError:
                        self.logger.warning(f"No se pudo convertir posición a entero: '{position_str}'")
                else:
                    self.logger.warning(f"Formato inesperado en respuesta gripper: {status_line}")
        
        return {"success": False, "message": "No se pudo consultar estado del gripper"}
    
    def list_available_states(self) -> list:
        return list(ARM_STATES.keys())
    
    def list_possible_transitions(self) -> list:
        possible = []
        for state in ARM_STATES.keys():
            if state != self.current_state:
                trajectory = TrajectoryDefinitions.get_trajectory(self.current_state, state, self.lettuce_on)
                if trajectory:
                    possible.append(state)
        return possible
    
    def set_lettuce_state(self, has_lettuce: bool):
        self.lettuce_on = has_lettuce
        estado = "CON lechuga" if has_lettuce else "SIN lechuga"
        self.logger.info(f"Estado de lechuga actualizado: {estado}")

    def get_lettuce_state(self) -> bool:
        return self.lettuce_on
    
    def _detect_initial_state(self):
        try:
            result = self.cmd.get_servo_positions()
            if result["success"]:
                response = result["response"]
                
                if "SERVO_POS:" in response:
                    pos_str = response.split("SERVO_POS:")[1]
                    servo1, servo2 = map(int, pos_str.split(","))
                    self.current_position = (servo1, servo2)
                    
                    detected_state = self._determine_state_from_position(servo1, servo2)
                    self.current_state = detected_state
                    
                    self.logger.info(f"Estado inicial detectado: {detected_state} en posición ({servo1}, {servo2})")
                else:
                    self.logger.warning("No se pudo parsear posición de servos")
                    self.current_state = "unknown"
            else:
                self.logger.warning("No se pudo consultar posición de servos")
                self.current_state = "unknown"
                
        except Exception as e:
            self.logger.error(f"Error detectando estado inicial: {e}")
            self.current_state = "unknown"

    def _determine_state_from_position(self, servo1: int, servo2: int) -> str:
        tolerance = 5

        for state_name, state_config in ARM_STATES.items():
            target_servo1 = state_config["servo1"]
            target_servo2 = state_config["servo2"]

            if (abs(servo1 - target_servo1) <= tolerance and
                abs(servo2 - target_servo2) <= tolerance):
                return state_name

        return "unknown"