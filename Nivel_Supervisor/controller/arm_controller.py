import time
import logging
from typing import Dict, Optional, Tuple
from .command_manager import CommandManager
from .arm_states import ARM_STATES, MOVEMENT_TIMING
from .trajectories import TrajectoryDefinitions, validate_trajectory, get_trajectory_time_estimate

class ArmController:
    def __init__(self, command_manager: CommandManager):
        self.cmd = command_manager
        self.logger = logging.getLogger(__name__)
        
        # Estado inicial desconocido
        self.current_state = "unknown"
        self.current_position = (90, 90)
        self.gripper_state = "unknown"
        
        # Configurar callbacks para notificaciones automáticas
        self.cmd.uart.set_status_callback(self._on_system_status_received)
        self.cmd.uart.set_servo_callback(self._on_servo_changed)
        self.cmd.uart.set_gripper_callback(self._on_gripper_changed)
        
        # Esperar a recibir estado inicial
        self._wait_for_initial_status()
    
    def _wait_for_initial_status(self):
        """Esperar a recibir estado inicial del microcontrolador"""
        print("🔄 Esperando estado inicial del microcontrolador...")
        
        # Esperar hasta 5 segundos por el mensaje inicial
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if self.current_state != "unknown":
                break
            time.sleep(0.1)
        
        if self.current_state == "unknown":
            self.logger.warning("No se recibió estado inicial, consultando manualmente...")
            self._detect_initial_state()
    
    def _on_system_status_received(self, message: str):
        """Procesar mensaje de estado del sistema"""
        try:
            # Parsear: "SYSTEM_STATUS:SERVO1=90,SERVO2=90,GRIPPER=OPEN,GRIPPER_POS=0"
            status_part = message.split("SYSTEM_STATUS:")[1]
            parts = status_part.split(",")
            
            servo1 = int(parts[0].split("=")[1])
            servo2 = int(parts[1].split("=")[1])
            gripper_state = parts[2].split("=")[1].lower()
            
            # Actualizar estado interno
            self.current_position = (servo1, servo2)
            self.gripper_state = gripper_state
            
            # Determinar estado basándose en posición
            self.current_state = self._determine_state_from_position(servo1, servo2)
            
            self.logger.info(f"Estado actualizado desde micro: {self.current_state} "f"pos=({servo1},{servo2}) grippe{gripper_state}")
            
        except Exception as e:
            self.logger.error(f"Error procesando estado del sistema: {e}")
    
    def _on_servo_changed(self, message: str):
        """Procesar cambio de servo"""
        try:
            # Parsear: "SERVO_CHANGED:1,45"
            change_part = message.split("SERVO_CHANGED:")[1]
            servo_num, angle = map(int, change_part.split(","))
            
            # Actualizar posición
            if servo_num == 1:
                self.current_position = (angle, self.current_position[1])
            else:
                self.current_position = (self.current_position[0], angle)
            
            # Redeterminar estado
            self.current_state = self._determine_state_from_position(
                self.current_position[0], self.current_position[1]
            )
            
            self.logger.debug(f"Servo {servo_num} cambió a {angle}°, estado: {self.current_state}")
            
        except Exception as e:
            self.logger.error(f"Error procesando cambio de servo: {e}")
    
    def _on_gripper_changed(self, message: str):
        """Procesar cambio de gripper"""
        if "GRIPPER_OPENED" in message:
            self.gripper_state = "open"
        elif "GRIPPER_CLOSED" in message:
            self.gripper_state = "closed"
        
        self.logger.debug(f"Gripper cambió a: {self.gripper_state}")
        
    def get_current_state(self) -> Dict:
        """Obtener estado actual completo"""
        return {
            "state": self.current_state,
            "position": self.current_position,
            "gripper": self.gripper_state,
            "available_states": list(ARM_STATES.keys()),
            "is_safe": self.is_in_safe_position()
        }
    
    def is_in_safe_position(self) -> bool:
        """Verificar si está en posición segura para movimiento X-Y"""
        safe_state = ARM_STATES["movimiento"]
        tolerance = 5  # grados de tolerancia
        
        pos_ok = (
            abs(self.current_position[0] - safe_state["servo1"]) <= tolerance and
            abs(self.current_position[1] - safe_state["servo2"]) <= tolerance
        )
        
        return pos_ok and self.current_state == "movimiento"
    
    def ensure_safe_position(self) -> Dict:
        """Asegurar que el brazo esté en posición segura"""
        if self.is_in_safe_position():
            self.logger.info("✅ Brazo ya está en posición segura")
            return {"success": True, "message": "Ya en posición segura"}
        
        self.logger.info("🔄 Moviendo brazo a posición segura...")
        return self.change_state("movimiento")
    
    def change_state(self, target_state: str) -> Dict:
        """Cambiar a un estado específico usando trayectorias"""
        if target_state not in ARM_STATES:
            return {"success": False, "message": f"Estado '{target_state}' no existe"}
        
        if self.current_state == target_state:
            return {"success": True, "message": f"Ya está en estado '{target_state}'"}
        
        # Buscar trayectoria específica primero
        trajectory = TrajectoryDefinitions.get_trajectory(self.current_state, target_state)
        
        if not trajectory:
            return {
                "success": False, 
                "message": f"No hay trayectoria definida de '{self.current_state}' → '{target_state}'"
            }
        
        # Mostrar información de la trayectoria
        estimated_time = get_trajectory_time_estimate(trajectory)
        print(f"   📋 {trajectory['description']}")
        print(f"   ⏱️  Tiempo estimado: {estimated_time:.1f} segundos")
        
        # Ejecutar trayectoria
        result = self.execute_trajectory(trajectory)
        
        if result["success"]:
            self.current_state = target_state
            target_config = ARM_STATES[target_state]
            self.current_position = (target_config["servo1"], target_config["servo2"])
            if target_config["gripper"] != "any":
                self.gripper_state = target_config["gripper"]
            
            self.logger.info(f"✅ Estado cambiado a: {target_state}")
            result["message"] = f"Estado cambiado exitosamente a '{target_state}'"
        
        return result
    
    def execute_trajectory(self, trajectory: dict) -> Dict:
        """Ejecutar una trayectoria completa"""
        if not validate_trajectory(trajectory):
            return {"success": False, "message": "Trayectoria inválida"}
        
        self.logger.info(f"🎯 Ejecutando: {trajectory['description']}")
        estimated_time = get_trajectory_time_estimate(trajectory)
        print(f"   ⏱️  Tiempo estimado: {estimated_time:.1f} segundos")
        
        try:
            for i, step in enumerate(trajectory["steps"]):
                print(f"   📍 Paso {i+1}/{len(trajectory['steps'])}: {step['description']}")
                
                if step["type"] == "gripper":
                    result = self._execute_gripper_action(step)
                elif step["type"] == "arm_move":
                    result = self._execute_arm_movement(step)
                else:
                    self.logger.warning(f"Tipo de paso desconocido: {step['type']}")
                    continue
                
                if not result["success"]:
                    return {"success": False, "message": f"Error en paso {i+1}: {result['message']}"}
                
                # Delay de seguridad entre pasos
                time.sleep(MOVEMENT_TIMING["safety_delay"])
            
            print("   ✅ Trayectoria completada exitosamente")
            return {"success": True, "message": "Trayectoria completada"}
            
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando trayectoria: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def _execute_gripper_action(self, step: Dict) -> Dict:
        """Ejecutar acción del gripper con toggle inteligente"""
        target_action = step["action"]  # "open" o "close"
        
        print(f"      🎯 Objetivo: {target_action} gripper...")
        
        # Consultar estado actual
        status_result = self.cmd.get_gripper_status()
        print(f"      🔍 Respuesta completa: {status_result.get('response', 'Sin respuesta')}")
        
        if status_result["success"] and "GRIPPER_STATUS:" in status_result["response"]:
            try:
                # Parsear: "GRIPPER_STATUS:OPEN,1150"
                response = status_result["response"]
                status_part = response.split("GRIPPER_STATUS:")[1]  # "OPEN,1150"
                current_state = status_part.split(",")[0].lower()   # "open"
                current_position = int(status_part.split(",")[1])   # 1150
                
                print(f"      📊 Estado actual: {current_state} (pos: {current_position})")
                
                # Solo accionar si necesita cambiar de estado
                if (target_action == "open" and current_state == "closed") or \
                (target_action == "close" and current_state == "open"):
                    
                    print(f"      🔄 Cambiando gripper de {current_state} a {target_action}...")
                    result = self.cmd.gripper_toggle()
                    
                    if result["success"]:
                        self.gripper_state = target_action
                        # Esperar un poco para que se procese
                        time.sleep(2.0)  # ⭐ Aumentar tiempo de espera
                        return {"success": True, "message": f"Gripper cambiado a {target_action}"}
                    else:
                        return result
                else:
                    print(f"      ✅ Gripper ya está {target_action} - no hace falta cambiar")
                    self.gripper_state = target_action
                    return {"success": True, "message": f"Gripper ya estaba {target_action}"}
                    
            except Exception as e:
                print(f"      ❌ Error parseando estado: {e}")
                print(f"      🔄 Accionando gripper sin verificar estado...")
                result = self.cmd.gripper_toggle()
                if result["success"]:
                    self.gripper_state = target_action
                    time.sleep(2.0)
                return result
        else:
            print(f"      ⚠️ No se pudo consultar estado, accionando gripper...")
            result = self.cmd.gripper_toggle()
            if result["success"]:
                self.gripper_state = target_action
                time.sleep(2.0)
            return result
        
    def get_gripper_real_status(self) -> Dict:
        """Consultar estado real del gripper desde el micro"""
        result = self.cmd.get_gripper_status()
        if result["success"]:
            response = result["response"]
            # Parsear: "GRIPPER_STATUS:OPEN,150"
            if "GRIPPER_STATUS:" in response:
                status_str = response.split("GRIPPER_STATUS:")[1]
                state, position = status_str.split(",")
                return {
                    "success": True,
                    "state": state.lower(),
                    "position": int(position)
                }
        
        return {"success": False, "message": "No se pudo consultar estado del gripper"}
    
    def _execute_arm_movement(self, step: Dict) -> Dict:
        """Ejecutar movimiento del brazo"""
        servo1 = step["servo1"]
        servo2 = step["servo2"]
        time_ms = step["time_ms"]
        
        # Ejecutar movimiento
        result = self.cmd.move_arm(servo1, servo2, time_ms)
        
        if result["success"]:
            # Actualizar posición actual
            self.current_position = (servo1, servo2)
            
            # Esperar a que complete el movimiento
            total_wait = (time_ms / 1000.0) + MOVEMENT_TIMING["arm_move_buffer"]
            print(f"      ⏳ Esperando {total_wait:.1f}s para completar movimiento...")
            time.sleep(total_wait)
            
            return {"success": True, "message": f"Brazo movido a ({servo1}°, {servo2}°)"}
        else:
            return result
    
    def list_available_states(self) -> list:
        """Listar estados disponibles"""
        return list(ARM_STATES.keys())
    
    def list_possible_transitions(self) -> list:
        """Listar transiciones posibles desde el estado actual"""
        possible = []
        for state in ARM_STATES.keys():
            if state != self.current_state:
                trajectory = TrajectoryDefinitions.get_trajectory(self.current_state, state)
                if trajectory:
                    possible.append(state)
        return possible
    
    def _detect_initial_state(self):
        """Detectar el estado inicial consultando al microcontrolador"""
        try:
            # Consultar posición actual de los servos
            result = self.cmd.get_servo_positions()
            if result["success"]:
                response = result["response"]
                
                # Parsear respuesta: "SERVO_POS:45,120"
                if "SERVO_POS:" in response:
                    pos_str = response.split("SERVO_POS:")[1]
                    servo1, servo2 = map(int, pos_str.split(","))
                    self.current_position = (servo1, servo2)
                    
                    # Determinar estado basándose en la posición
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
        """Determinar estado basándose en la posición actual"""
        tolerance = 10  # grados de tolerancia
        
        # Verificar cada estado definido
        for state_name, state_config in ARM_STATES.items():
            target_servo1 = state_config["servo1"]
            target_servo2 = state_config["servo2"]
            
            # Verificar si la posición coincide con este estado
            if (abs(servo1 - target_servo1) <= tolerance and 
                abs(servo2 - target_servo2) <= tolerance):
                return state_name
        
        # Si no coincide con ningún estado definido
        return "unknown"
    
    def get_current_state(self) -> Dict:
        """Obtener estado actual completo"""
        return {
            "state": self.current_state,
            "position": self.current_position,
            "gripper": self.gripper_state,
            "available_states": list(ARM_STATES.keys()),
            "is_safe": self.is_in_safe_position(),
            "is_known": self.current_state != "unknown"
        }
    
    def is_in_safe_position(self) -> bool:
        """Verificar si está en posición segura para movimiento X-Y"""
        if self.current_state == "unknown":
            return False
            
        safe_state = ARM_STATES["movimiento"]
        tolerance = 10  # grados de tolerancia
        
        pos_ok = (
            abs(self.current_position[0] - safe_state["servo1"]) <= tolerance and
            abs(self.current_position[1] - safe_state["servo2"]) <= tolerance
        )
        
        return pos_ok and self.current_state == "movimiento"