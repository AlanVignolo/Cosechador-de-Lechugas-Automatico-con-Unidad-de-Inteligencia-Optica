from typing import Dict, Tuple, Optional
from hardware.command_manager import CommandManager
from robot.arm_controller import ArmController
from config.robot_config import RobotConfig
import logging
import time
import json
import os
import queue

class RobotController:
    def __init__(self, command_manager: CommandManager):
        self.cmd = command_manager
        self.logger = logging.getLogger(__name__)
        
        self.current_position = {"x": 0.0, "y": 0.0}
        self.global_position = {"x": 0.0, "y": 0.0}
        self.workspace_dimensions = {"width_mm": 0.0, "height_mm": 0.0, "calibrated": False}
        self.arm_servo1_pos = 90
        self.arm_servo2_pos = 90  
        self.gripper_state = "unknown"
        self.is_homed = False
        self.arm = ArmController(command_manager)

        self._setup_position_tracking()
        self._initialize_global_position()
        self._load_homing_reference()

        if self.is_homed:
            if not self._load_current_position():
                pass

        self._load_workspace_dimensions()
        self._request_system_status()
        self.cmd.uart.send_command("HB:1")
        
    def _request_system_status(self):
        self.logger.info("Solicitando estado inicial del sistema...")
        limits_result = self.cmd.check_limits()
        if limits_result["success"]:
            self.logger.info(f"Estado límites: {limits_result['response']}")
    
    def _setup_position_tracking(self):
        self.cmd.uart.set_stepper_callbacks(None, self._on_movement_completed)
        # Asegurar que también contabilizamos deltas cuando hay paradas de emergencia
        try:
            if not getattr(self.cmd.uart, "_supervisor_em_stop_wrapped", False):
                original_em_stop = self.cmd.uart._process_emergency_stop

                def _supervisor_emergency_wrapper(message: str):
                    # Sumar deltas reales reportados por el firmware en emergencias
                    try:
                        clean_message = message.split('\n')[0]
                        parts = clean_message.split(',')
                        if len(parts) >= 6:
                            rel_h_mm = float(parts[4].split(':')[1])
                            rel_v_mm = float(parts[5])

                            self.global_position["x"] += rel_h_mm
                            self.global_position["y"] += rel_v_mm

                            self._save_current_position()

                            display_x = RobotConfig.display_x_position(self.global_position['x'])
                            display_y = RobotConfig.display_y_position(self.global_position['y'])
                            self.logger.info(f"Posición global actualizada (emergencia): X={display_x}mm, Y={display_y}mm")
                    except Exception as e:
                        self.logger.warning(f"Error actualizando posición por emergencia: {e}")
                    finally:
                        # Ejecutar lógica original (logs/prints) DESPUÉS de actualizar
                        original_em_stop(message)

                self.cmd.uart._process_emergency_stop = _supervisor_emergency_wrapper
                setattr(self.cmd.uart, "_supervisor_em_stop_wrapped", True)
        except Exception as e:
            # No bloquear si por algún motivo no se puede envolver
            self.logger.warning(f"No se pudo registrar wrapper de emergencia: {e}")
    
    def _on_movement_completed(self, message: str):
        try:
            clean_message = message.split('\n')[0]
            parts = clean_message.split(',')
            if len(parts) >= 6:
                rel_h_mm = float(parts[4].split(':')[1])
                rel_v_mm = float(parts[5])

                self.global_position["x"] += rel_h_mm
                self.global_position["y"] += rel_v_mm

                self._save_current_position()

                display_x = RobotConfig.display_x_position(self.global_position['x'])
                display_y = RobotConfig.display_y_position(self.global_position['y'])
                self.logger.info(f"Posición global actualizada: X={display_x}mm, Y={display_y}mm")
        except Exception as e:
            self.logger.warning(f"Error actualizando posición global: {e}")
    
    def reset_global_position(self, x: float = 0.0, y: float = 0.0):
        self.global_position["x"] = x
        self.global_position["y"] = y
        display_x = RobotConfig.display_x_position(x)
        display_y = RobotConfig.display_y_position(y)
        self.logger.info(f"Posición global reseteada a: X={display_x}mm, Y={display_y}mm")
        try:
            self._save_current_position()
        except Exception:
            pass
    
    def _initialize_global_position(self):
        self.global_position = {"x": 0.0, "y": 0.0}
        self.logger.info("Posición global inicializada - usar HOMING para establecer origen")
    
    def _load_homing_reference(self):
        """Cargar referencia de homing desde archivo JSON"""
        homing_file = os.path.join(os.path.dirname(__file__), '..', 'homing_reference.json')
        try:
            if os.path.exists(homing_file):
                with open(homing_file, 'r') as f:
                    data = json.load(f)
                
                if data.get('homed', False):
                    self.current_position = data['position'].copy()
                    self.global_position = data['position'].copy()
                    self.is_homed = True
                    self.logger.info(f"Referencia de homing cargada: X={self.current_position['x']:.1f}mm, Y={self.current_position['y']:.1f}mm")
                    print(f"Referencia de homing restaurada desde sesión anterior")
                    print(f"   Posición: X={self.current_position['x']:.1f}mm, Y={self.current_position['y']:.1f}mm")
                else:
                    self.logger.info("Referencia de homing inválida")
            else:
                self.logger.info("No existe referencia de homing previa")
        except Exception as e:
            self.logger.error(f"Error cargando referencia de homing: {e}")
    
    def _save_homing_reference(self):
        """Guardar referencia de homing actual"""
        homing_file = os.path.join(os.path.dirname(__file__), '..', 'homing_reference.json')
        data = {
            'timestamp': time.time(),
            'position': self.current_position.copy(),
            'homed': self.is_homed
        }
        try:
            with open(homing_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Referencia de homing guardada: X={self.current_position['x']:.1f}mm, Y={self.current_position['y']:.1f}mm")
            return True
        except Exception as e:
            self.logger.error(f"Error guardando referencia de homing: {e}")
            return False
    
    def _save_workspace_dimensions(self, measurements: Dict):
        """Guardar dimensiones del workspace medidas durante calibración"""
        workspace_file = os.path.join(os.path.dirname(__file__), '..', 'workspace_dimensions.json')
        data = {
            'timestamp': time.time(),
            'width_mm': measurements.get('horizontal_mm', 0.0),
            'height_mm': measurements.get('vertical_mm', 0.0),
            'width_steps': measurements.get('horizontal_steps', 0),
            'height_steps': measurements.get('vertical_steps', 0),
            'calibrated': True,
            'steps_per_mm_h': RobotConfig.STEPS_PER_MM_H,
            'steps_per_mm_v': RobotConfig.STEPS_PER_MM_V
        }
        
        try:
            with open(workspace_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.workspace_dimensions = {
                'width_mm': data['width_mm'],
                'height_mm': data['height_mm'],
                'calibrated': True
            }
            
            self.logger.info(f"Dimensiones del workspace guardadas: {data['width_mm']:.1f}mm x {data['height_mm']:.1f}mm")
            return True
        except Exception as e:
            self.logger.error(f"Error guardando dimensiones del workspace: {e}")
            return False
    
    def _load_workspace_dimensions(self):
        """Cargar dimensiones del workspace desde archivo"""
        workspace_file = os.path.join(os.path.dirname(__file__), '..', 'workspace_dimensions.json')
        try:
            if os.path.exists(workspace_file):
                with open(workspace_file, 'r') as f:
                    data = json.load(f)
                
                if data.get('calibrated', False):
                    self.workspace_dimensions = {
                        'width_mm': data.get('width_mm', 0.0),
                        'height_mm': data.get('height_mm', 0.0),
                        'calibrated': True
                    }
                    self.logger.info(f"Dimensiones del workspace cargadas: {self.workspace_dimensions['width_mm']:.1f}mm x {self.workspace_dimensions['height_mm']:.1f}mm")
                    print(f"Workspace: {self.workspace_dimensions['width_mm']:.1f}mm x {self.workspace_dimensions['height_mm']:.1f}mm")
                    return True
        except Exception as e:
            self.logger.warning(f"Error cargando dimensiones del workspace: {e}")
        
        return False
    
    def get_workspace_dimensions(self) -> Dict:
        """Obtener las dimensiones actuales del workspace"""
        return self.workspace_dimensions.copy()
    
    def _save_current_position(self):
        if not self.is_homed:
            return
            
        position_file = os.path.join(os.path.dirname(__file__), '..', 'current_position.json')
        data = {
            'timestamp': time.time(),
            'position': self.global_position.copy(),
            'homed': self.is_homed
        }
        
        try:
            with open(position_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Error guardando posición actual: {e}")
    
    def _load_current_position(self):
        """Cargar última posición guardada"""
        position_file = os.path.join(os.path.dirname(__file__), '..', 'current_position.json')
        try:
            if os.path.exists(position_file):
                with open(position_file, 'r') as f:
                    data = json.load(f)
                
                if data.get('homed', False):
                    self.global_position = data['position'].copy()
                    display_x = RobotConfig.display_x_position(self.global_position['x'])
                    display_y = RobotConfig.display_y_position(self.global_position['y'])
                    self.logger.info(f"Posición anterior restaurada: X={display_x}mm, Y={display_y}mm")
                    print(f"Posición anterior restaurada: X={display_x}mm, Y={display_y}mm")
                    return True
        except Exception as e:
            self.logger.warning(f"Error cargando posición anterior: {e}")
        
        return False

    def home_robot(self) -> Dict:
        self.logger.info("Iniciando secuencia de homing reactivo...")
        
        try:
            print("Verificando posición del brazo...")
            arm_status = self.arm.get_current_state(force_refresh=True)
            current_pos = arm_status['position']
            current_state = arm_status['state']

            print(f"  Posición actual: servo1={current_pos[0]}°, servo2={current_pos[1]}°")
            print(f"  Estado detectado: {current_state}")

            if not self.arm.is_in_movement_position():
                print(f"  ❌ BRAZO NO ESTÁ EN POSICIÓN DE MOVIMIENTO")
                print(f"  Se requiere: servo1=10°±5°, servo2=10°±5°")
                print(f"  Actual: servo1={current_pos[0]}°, servo2={current_pos[1]}°")
                print(f"  Por seguridad, usa la opción 9 (Menú avanzado del brazo) para mover a 'movimiento'")
                return {"success": False, "message": f"Brazo no está en posición de movimiento. Actual: ({current_pos[0]}, {current_pos[1]})"}
            print("  ✅ Brazo en posición de movimiento")
            
            limit_touched = {"type": None}
            
            def on_limit_touched(message):
                limit_touched["type"] = message
                # Límite detectado (mensaje silencioso para evitar duplicados)
            
            self.cmd.uart.set_limit_callback(on_limit_touched)
            
            self.cmd.uart.send_command("HB:0")
            
            print("Configurando velocidades de homing...")
            result = self.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H, 
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                return {"success": False, "message": "Error configurando velocidades"}
            
            try:
                lim = self.cmd.uart.get_limit_status()
                active = lim.get('status', {}) if lim else {}
                pre_moves = []
                if active.get('H_RIGHT', False):
                    pre_moves.append((RobotConfig.apply_x_direction(20), 0))
                if active.get('H_LEFT', False):
                    pre_moves.append((RobotConfig.apply_x_direction(-20), 0))
                if active.get('V_UP', False):
                    pre_moves.append((0, RobotConfig.apply_y_direction(20)))
                if active.get('V_DOWN', False):
                    pre_moves.append((0, RobotConfig.apply_y_direction(-20)))
                for dx, dy in pre_moves:
                    print(f"Pre-homing: alejándose de límite activo ΔX={dx}mm, ΔY={dy}mm")
                    self.cmd.move_xy(dx, dy)
                    try:
                        self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=10.0)
                    except Exception:
                        time.sleep(0.5)
                    time.sleep(0.2)
            except Exception:
                pass
            
            print("Moviendo hacia la DERECHA hasta tocar límite...")
            result = self.cmd.move_xy(RobotConfig.get_homing_direction_x(), 0)
            
            limit_message = self.cmd.uart.wait_for_limit_specific('H_RIGHT', timeout=30.0)
            if limit_message:
                print("✅ Límite derecho alcanzado")
            else:
                return {"success": False, "message": "❌ No se alcanzó límite derecho"}
            
            try:
                lim = self.cmd.uart.get_limit_status()
                at_right = bool(lim and lim.get('status', {}).get('H_RIGHT', False))
            except Exception:
                at_right = False
            if at_right:
                try:
                    print(f"Despegando {RobotConfig.HOME_OFFSET_H}mm desde límite derecho antes de subir...")
                    self.cmd.move_xy(RobotConfig.apply_x_direction(RobotConfig.HOME_OFFSET_H), 0)
                    try:
                        self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=8.0)
                    except Exception:
                        time.sleep(0.5)
                    
                    start = time.time()
                    while time.time() - start < 1.0:
                        resp = self.cmd.check_limits()
                        try:
                            resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                        except Exception:
                            resp_str = ""
                        self.cmd.uart._update_limit_status_from_response(resp_str)
                        st = self.cmd.uart.get_limit_status()
                        if not st.get('status', {}).get('H_RIGHT', False):
                            break
                        time.sleep(0.05)
                except Exception:
                    pass

            print("Moviendo hacia ARRIBA hasta tocar límite...")
            result = self.cmd.move_xy(0, RobotConfig.get_homing_direction_y())
            
            limit_message = self.cmd.uart.wait_for_limit_specific('V_UP', timeout=180.0)
            if limit_message:
                print("Límite superior alcanzado")
            else:
                return {"success": False, "message": "No se alcanzó límite superior"}
            
            print(f"Estableciendo origen vertical (bajar {RobotConfig.HOME_OFFSET_V}mm desde límite superior)...")
            
            result = self.cmd.move_xy(0, RobotConfig.get_home_offset_y())
            if not result["success"]:
                return {"success": False, "message": "Error en offset"}
            
            print("Esperando completar movimiento de offset...")
            self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=10.0)

            # Establecer origen (0,0) - resetear AMBAS posiciones
            self.current_position = {"x": 0.0, "y": 0.0}
            self.global_position = {"x": 0.0, "y": 0.0}
            self.is_homed = True
            
            print("Guardando referencia de homing...")
            if self._save_homing_reference():
                print("   Referencia guardada exitosamente")
            else:
                print("   Error guardando referencia (continuando)")
            
            print("Restaurando velocidades normales...")
            result = self.cmd.set_velocities(
                RobotConfig.NORMAL_SPEED_H, 
                RobotConfig.NORMAL_SPEED_V
            )
            
            if result["success"]:
                print(f"Velocidades restauradas: {result['response']}")
            else:
                print(f"Error restaurando velocidades: {result}")
            
            self.cmd.uart.send_command("HB:1")
            
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
                self.cmd.uart.send_command("HB:1")
            except:
                pass
            return {"success": False, "message": f"Error durante homing: {str(e)}"}
    
    def move_to_absolute(self, x: float, y: float) -> Dict:
        if not self.is_homed:
            return {"success": False, "message": "Robot no está homed"}

        if not self.arm.is_in_safe_position():
            self.logger.warning("Brazo no está en posición segura. Moviendo...")
            result = self.arm.ensure_safe_position()
            if not result["success"]:
                return {"success": False, "message": "No se pudo mover brazo a posición segura"}

        if x < 0 or x > RobotConfig.MAX_X or y < 0 or y > RobotConfig.MAX_Y:
            return {"success": False, "message": f"Posición fuera de límites"}

        delta_x = x - self.current_position["x"]
        delta_y = y - self.current_position["y"]
        
        result = self.cmd.move_xy(delta_x, delta_y)
        
        if result["success"]:
            self.current_position["x"] = x
            self.current_position["y"] = y
            self.logger.info(f"Movido a posición absoluta: ({x}, {y})")
        
        return result
    
    def get_status(self) -> Dict:
        return {
            "homed": self.is_homed,
            "position": self.global_position,
            "arm": {
                "servo1": self.arm_servo1_pos,
                "servo2": self.arm_servo2_pos
            },
            "gripper": self.gripper_state
        }

    def resync_global_position_from_firmware(self) -> bool:
        try:
            resp = self.cmd.get_current_position_mm()
            s = resp.get('response', '') if isinstance(resp, dict) else str(resp)
            if 'MM:' in s:
                mm_part = s.split('MM:')[1]
                parts = mm_part.replace('\n', ' ').split(',')
                if len(parts) >= 2:
                    x = float(parts[0].strip())
                    y = float(parts[1].strip())
                    self.global_position['x'] = x
                    self.global_position['y'] = y
                    self._save_current_position()
                    display_x = RobotConfig.display_x_position(x)
                    display_y = RobotConfig.display_y_position(y)
                    self.logger.info(f"Resync posición desde firmware: X={display_x}mm, Y={display_y}mm")
                    return True
        except Exception as e:
            self.logger.warning(f"No se pudo resync desde firmware: {e}")
        return False

    def calibrate_workspace(self) -> Dict:
        print("Iniciando calibración del workspace...")

        captured_distances = {"horizontal_mm": None, "vertical_mm": None}
        original_process_emergency_stop = self.cmd.uart._process_emergency_stop
        
        def enhanced_process_emergency_stop(message: str):
            try:
                original_process_emergency_stop(message)

                if "STEPPER_EMERGENCY_STOP:" in message and "MM:" in message:
                    mm_part = message.split("MM:")[1]
                    mm_values = mm_part.split(",")
                    if len(mm_values) >= 2:
                        h_mm = abs(float(mm_values[0]))
                        v_mm = abs(float(mm_values[1]))

                        if h_mm > v_mm and h_mm > 50 and captured_distances["horizontal_mm"] is None:
                            captured_distances["horizontal_mm"] = h_mm
                            print(f"   Distancia horizontal capturada: {h_mm:.1f}mm")
                        elif v_mm > h_mm and v_mm > 50 and captured_distances["vertical_mm"] is None:
                            captured_distances["vertical_mm"] = v_mm
                            print(f"   Distancia vertical capturada: {v_mm:.1f}mm")
            except Exception as e:
                print(f"   Error en captura mejorada: {e}")
                original_process_emergency_stop(message)

        self.cmd.uart._process_emergency_stop = enhanced_process_emergency_stop
        
        try:
            print("Paso 1: Homing inicial...")

            homing_result = self.home_robot()
            if not homing_result["success"]:
                return {"success": False, "message": f"Error en homing inicial: {homing_result['message']}"}
            
            print("Verificando posición del brazo...")
            if not self.arm.is_in_safe_position():
                print("   Brazo no está en posición segura. Moviendo...")
                result = self.arm.ensure_safe_position()
                if not result["success"]:
                    return {"success": False, "message": "No se pudo mover brazo a posición segura"}
                print("   Brazo en posición segura")
            else:
                print("   Brazo ya está en posición segura")

            print("Paso 2: Calibrando horizontal (izquierda)...")

            captured_distances["horizontal_mm"] = None
            captured_distances["vertical_mm"] = None

            self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            
            direction_x = RobotConfig.get_workspace_measure_direction_x()
            print(f"   Moviendo X={direction_x}mm hacia límite izquierdo")
            result = self.cmd.move_xy(direction_x, 0)

            limit_message = self.cmd.uart.wait_for_limit_specific('H_LEFT', timeout=30.0)
            if limit_message:
                print("   Límite izquierdo alcanzado")

                if captured_distances["horizontal_mm"] is not None:
                    h_distance = captured_distances["horizontal_mm"]
                    print(f"      Distancia total horizontal: {h_distance:.1f}mm")
                else:
                    print("   No se capturó distancia horizontal")

            print("Paso 3: Calibrando vertical (abajo)...")

            print("   Alejándose del límite horizontal...")
            self.cmd.move_xy(RobotConfig.apply_x_direction(-20), 0)
            self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=5.0)

            self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)

            direction_y = RobotConfig.get_workspace_measure_direction_y()
            print(f"   Moviendo Y={direction_y}mm hacia límite inferior")
            result = self.cmd.move_xy(0, direction_y)

            limit_message = self.cmd.uart.wait_for_limit_specific('V_DOWN', timeout=60.0)
            if limit_message:
                print("   Límite inferior alcanzado")

                if captured_distances["vertical_mm"] is not None:
                    v_distance = captured_distances["vertical_mm"]
                    print(f"      Distancia total vertical: {v_distance:.1f}mm")
                else:
                    print("   ❌ No se capturó distancia vertical")
            else:
                print("   ❌ No se alcanzó límite inferior - revisar cableado o configuración Y")

            SAFETY_MARGIN_MM = 10.0
            measurements = {}


            if captured_distances["horizontal_mm"] is not None:
                raw_h_dist = captured_distances["horizontal_mm"]
                workspace_h_dist = max(0, raw_h_dist - SAFETY_MARGIN_MM)
                measurements["horizontal_steps"] = int(workspace_h_dist * RobotConfig.STEPS_PER_MM_H)
                measurements["horizontal_mm"] = round(workspace_h_dist, 1)
                print(f"   ℹ️  Workspace horizontal: {raw_h_dist:.1f}mm medidos - {SAFETY_MARGIN_MM}mm margen = {workspace_h_dist:.1f}mm útiles")


            if captured_distances["vertical_mm"] is not None:
                raw_v_dist = captured_distances["vertical_mm"]
                workspace_v_dist = max(0, raw_v_dist - SAFETY_MARGIN_MM)
                measurements["vertical_steps"] = int(workspace_v_dist * RobotConfig.STEPS_PER_MM_V)
                measurements["vertical_mm"] = round(workspace_v_dist, 1)
                print(f"   ℹ️  Workspace vertical: {raw_v_dist:.1f}mm medidos - {SAFETY_MARGIN_MM}mm margen = {workspace_v_dist:.1f}mm útiles")

            print("Paso 4: Homing final...")

            self.cmd.uart.set_limit_callback(None)
            try:
                while True:
                    self.cmd.uart.message_queue.get_nowait()
            except:
                pass

            print("   Ejecutando homing directo...")

            result = self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            if not result["success"]:
                return {"success": False, "message": "Error configurando velocidades de homing final"}

            limit_touched = {"type": None}
            def on_limit_touched_final(message):
                limit_touched["type"] = message
                # Límite detectado (mensaje silencioso para evitar duplicados)

            self.cmd.uart.set_limit_callback(on_limit_touched_final)

            print("      -> Moviendo hacia límite derecho...")
            result = self.cmd.move_xy(RobotConfig.get_homing_direction_x(), 0)
            limit_message = self.cmd.uart.wait_for_limit_specific('H_RIGHT', timeout=30.0)
            if not limit_message:
                return {"success": False, "message": "No se alcanzó límite derecho en homing final"}

            try:
                lim = self.cmd.uart.get_limit_status()
                at_right = bool(lim and lim.get('status', {}).get('H_RIGHT', False))
            except Exception:
                at_right = False
            if at_right:
                try:
                    print("      → Retrocediendo 12mm desde límite derecho para liberar switch...")
                    self.cmd.move_xy(RobotConfig.apply_x_direction(12), 0)
                    try:
                        self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=8.0)
                    except Exception:
                        time.sleep(0.5)
                    start = time.time()
                    while time.time() - start < 1.0:
                        resp = self.cmd.check_limits()
                        try:
                            resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                        except Exception:
                            resp_str = ""
                        self.cmd.uart._update_limit_status_from_response(resp_str)
                        st = self.cmd.uart.get_limit_status()
                        if not st.get('status', {}).get('H_RIGHT', False):
                            break
                        time.sleep(0.05)
                except Exception:
                    pass

            print("      → Moviendo hacia límite superior...")
            result = self.cmd.move_xy(0, RobotConfig.get_homing_direction_y())
            limit_message = self.cmd.uart.wait_for_limit_specific('V_UP', timeout=30.0)
            if not limit_message:
                return {"success": False, "message": "No se alcanzó límite superior en homing final"}

            print(f"      → Aplicando offset ({RobotConfig.HOME_OFFSET_H}mm, {RobotConfig.HOME_OFFSET_V}mm)...")
            result = self.cmd.move_xy(RobotConfig.get_home_offset_x(), RobotConfig.get_home_offset_y())
            if not result["success"]:
                return {"success": False, "message": "Error aplicando offset en homing final"}

            time.sleep(3.0)

            # Establecer origen (0,0) - resetear AMBAS posiciones
            self.current_position = {"x": 0.0, "y": 0.0}
            self.global_position = {"x": 0.0, "y": 0.0}
            self.is_homed = True

            result = self.cmd.set_velocities(RobotConfig.NORMAL_SPEED_H, RobotConfig.NORMAL_SPEED_V)
            if result["success"]:
                print(f"      Velocidades restauradas: {result['response']}")

            print("   Homing final completado")
            
            print(f"\n=== RESULTADOS DE CALIBRACIÓN ===")
            if "horizontal_mm" in measurements:
                print(f"Workspace Horizontal: {measurements['horizontal_mm']:.1f}mm ({measurements['horizontal_steps']} pasos)")
            if "vertical_mm" in measurements:
                print(f"Workspace Vertical: {measurements['vertical_mm']:.1f}mm ({measurements['vertical_steps']} pasos)")
            print("=" * 35)

            if measurements:
                print("Guardando dimensiones del workspace...")
                if self._save_workspace_dimensions(measurements):
                    print("   Dimensiones guardadas exitosamente")
                else:
                    print("   Error guardando dimensiones (continuando)")
            
            return {"success": True, "message": "Calibración completada", "measurements": measurements}
            
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}
        finally:
            self.cmd.uart._process_emergency_stop = original_process_emergency_stop
