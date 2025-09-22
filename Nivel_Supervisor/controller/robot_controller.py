from typing import Dict, Tuple, Optional
from controller.command_manager import CommandManager
from controller.arm_controller import ArmController
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
        self.global_position = {"x": 0.0, "y": 0.0}  # Posición global acumulada
        self.workspace_dimensions = {"width_mm": 0.0, "height_mm": 0.0, "calibrated": False}  # Dimensiones del workspace
        self.arm_servo1_pos = 90
        self.arm_servo2_pos = 90  
        self.gripper_state = "unknown"
        self.is_homed = False
        self.arm = ArmController(command_manager)
        
        # Pasarle referencia de este RobotController al ArmController para callbacks
        self.arm.robot_controller = self
        
        # Configurar callback para tracking de posición
        self._setup_position_tracking()
        
        # Inicializar posición global al arrancar
        self._initialize_global_position()
        self._load_homing_reference()
        # Cargar posición anterior si existe y el robot estaba homed
        # (esto debe ir DESPUÉS de cargar homing reference)
        if self.is_homed:
            if not self._load_current_position():
                # Si no hay posición guardada, usar la del homing reference
                pass
        
        # Cargar dimensiones del workspace si existen
        self._load_workspace_dimensions()
        
        # Solicitar estado inicial del sistema
        self._request_system_status()
        
        # Habilitar heartbeat después de la inicialización
        self.cmd.uart.send_command("HB:1")
        
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
        self.logger.info("🔧 Configurando callback de posición...")
        self.cmd.uart.set_stepper_callbacks(None, self._on_movement_completed)
        self.logger.info("🔧 Callback registrado correctamente")
    
    def _on_movement_completed(self, message: str):
        """Callback para actualizar posición global cuando se completa un movimiento"""
        try:
            # DEBUG: Imprimir mensaje recibido
            self.logger.info(f"🔍 CALLBACK RECIBIDO: {message}")
            
            # Limpiar mensaje de posibles mezclas
            clean_message = message.split('\n')[0]
            self.logger.info(f"🔍 MENSAJE LIMPIO: {clean_message}")
            
            # Formato: STEPPER_MOVE_COMPLETED:pos_h,pos_v,REL:rel_h,rel_v,MM:mm_h,mm_v
            parts = clean_message.split(',')
            self.logger.info(f"🔍 PARTES DEL MENSAJE: {parts} (total: {len(parts)})")
            
            if len(parts) >= 6:
                rel_h_mm = float(parts[4].split(':')[1])
                rel_v_mm = float(parts[5])
                
                self.logger.info(f"🔍 MOVIMIENTO PARSEADO: X={rel_h_mm}mm, Y={rel_v_mm}mm")
                
                # Actualizar posición global acumulada
                old_x = self.global_position["x"]
                old_y = self.global_position["y"]
                
                self.global_position["x"] += rel_h_mm
                self.global_position["y"] += rel_v_mm
                
                self.logger.info(f"🔍 POSICIÓN ACTUALIZADA: ({old_x:.1f},{old_y:.1f}) → ({self.global_position['x']:.1f},{self.global_position['y']:.1f})")
                
                # Guardar posición actualizada
                self._save_current_position()
                
                display_x = RobotConfig.display_x_position(self.global_position['x'])
                display_y = RobotConfig.display_y_position(self.global_position['y'])
                self.logger.info(f"Posición global actualizada: X={display_x}mm, Y={display_y}mm")
            else:
                self.logger.warning(f"🔍 MENSAJE CON FORMATO INCORRECTO: {len(parts)} partes, esperaba >= 6")
                
        except Exception as e:
            self.logger.warning(f"Error actualizando posición global: {e}")
            import traceback
            self.logger.warning(f"Traceback: {traceback.format_exc()}")
    
    def reset_global_position(self, x: float = 0.0, y: float = 0.0):
        """Resetear posición global (usado en homing)"""
        self.global_position["x"] = x
        self.global_position["y"] = y
        display_x = RobotConfig.display_x_position(x)
        display_y = RobotConfig.display_y_position(y)
        self.logger.info(f"Posición global reseteada a: X={display_x}mm, Y={display_y}mm")
    
    def _initialize_global_position(self):
        """Inicializar posición global al arrancar Python"""
        # Asumir posición desconocida al inicio - será 0,0 tras homing
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
            
            # Actualizar dimensiones en memoria
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
        """Guardar posición actual después de cada movimiento"""
        if not self.is_homed:
            return  # Solo guardar si el robot está homed
            
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
            if not self.arm.is_in_movement_position():
                print("  BRAZO NO ESTÁ EN POSICIÓN DE MOVIMIENTO (servo1=10°, servo2=10°)")
                print("  Por seguridad, mueve el brazo manualmente antes de hacer homing")
                return {"success": False, "message": "Brazo no está en posición de movimiento. Configura servo1=10°, servo2=10° antes de hacer homing."}
            print(" Brazo en posición de movimiento")
            
            limit_touched = {"type": None}
            
            def on_limit_touched(message):
                limit_touched["type"] = message
                print(f"Límite detectado: {message}")
            
            self.cmd.uart.set_limit_callback(on_limit_touched)
            
            # Deshabilitar heartbeat molesto durante homing
            self.cmd.uart.send_command("HB:0")
            time.sleep(0.2)
            
            print("Configurando velocidades de homing...")
            result = self.cmd.set_velocities(
                RobotConfig.HOMING_SPEED_H, 
                RobotConfig.HOMING_SPEED_V
            )
            if not result["success"]:
                return {"success": False, "message": "Error configurando velocidades"}
            
            print("Moviendo hacia la DERECHA hasta tocar límite...")
            result = self.cmd.move_xy(RobotConfig.get_homing_direction_x(), 0)
            
            limit_message = self.cmd.uart.wait_for_limit_specific('H_RIGHT', timeout=30.0)
            if limit_message:
                print("✅ Límite derecho alcanzado")
            else:
                return {"success": False, "message": "❌ No se alcanzó límite derecho"}
            
            print("Moviendo hacia ARRIBA hasta tocar límite...")
            result = self.cmd.move_xy(0, RobotConfig.get_homing_direction_y())
            
            limit_message = self.cmd.uart.wait_for_limit_specific('V_UP', timeout=180.0)
            if limit_message:
                print("✅ Límite superior alcanzado")
            else:
                return {"success": False, "message": "❌ No se alcanzó límite superior"}
            
            print(f"Estableciendo origen ({RobotConfig.HOME_OFFSET_H}mm, {RobotConfig.HOME_OFFSET_V}mm desde límites)...")
            
            result = self.cmd.move_xy(RobotConfig.get_home_offset_x(), RobotConfig.get_home_offset_y())
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
            self.reset_global_position(0.0, 0.0)
            self.is_homed = True
            
            # Guardar referencia de homing
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
            
            # Rehabilitar heartbeat
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
                # Rehabilitar heartbeat en caso de error también
                self.cmd.uart.send_command("HB:1")
            except:
                pass
            return {"success": False, "message": f"Error durante homing: {str(e)}"}
    
    def move_to_absolute(self, x: float, y: float) -> Dict:
        """Mover a posición absoluta (verifica posición segura del brazo)"""
        if not self.is_homed:
            return {"success": False, "message": "Robot no está homed"}
        
        # VERIFICAR QUE EL BRAZO ESTÉ EN POSICIÓN SEGURA
        if not self.arm.is_in_safe_position():
            self.logger.warning("Brazo no está en posición segura. Moviendo...")
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
        """Calibración del workspace usando mensajes STEPPER_EMERGENCY_STOP del firmware"""
        print("Iniciando calibración del workspace...")
        
        # Variables para capturar distancias reales
        captured_distances = {"horizontal_mm": None, "vertical_mm": None}
        
        # Guardar el método original
        original_process_emergency_stop = self.cmd.uart._process_emergency_stop
        
        def enhanced_process_emergency_stop(message: str):
            """Procesamiento mejorado que también captura distancias"""
            try:
                # Llamar al procesamiento original
                original_process_emergency_stop(message)
                
                # Extraer distancias para calibración
                if "STEPPER_EMERGENCY_STOP:" in message and "MM:" in message:
                    mm_part = message.split("MM:")[1]
                    mm_values = mm_part.split(",")
                    if len(mm_values) >= 2:
                        h_mm = abs(float(mm_values[0]))
                        v_mm = abs(float(mm_values[1]))
                        
                        # Guardar distancias significativas (solo la distancia mayor)
                        if h_mm > v_mm and h_mm > 50 and captured_distances["horizontal_mm"] is None:
                            captured_distances["horizontal_mm"] = h_mm
                            print(f"   📏 Distancia horizontal capturada: {h_mm:.1f}mm")
                        elif v_mm > h_mm and v_mm > 50 and captured_distances["vertical_mm"] is None:
                            captured_distances["vertical_mm"] = v_mm
                            print(f"   📏 Distancia vertical capturada: {v_mm:.1f}mm")
            except Exception as e:
                print(f"   Error en captura mejorada: {e}")
                # Asegurar que el procesamiento original siempre funcione
                original_process_emergency_stop(message)
        
        # Reemplazar temporalmente el método
        self.cmd.uart._process_emergency_stop = enhanced_process_emergency_stop
        
        try:
            print("Paso 1: Homing inicial...")
            
            # 1. Homing inicial para establecer origen
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
            
            # 2. Calibrar horizontal (izquierda)
            print("Paso 2: Calibrando horizontal (izquierda)...")
            
            # RESETEAR distancias capturadas antes de calibración horizontal
            captured_distances["horizontal_mm"] = None
            captured_distances["vertical_mm"] = None
            
            # Configurar velocidades de homing
            self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            time.sleep(0.5)
            
            direction_x = RobotConfig.get_workspace_measure_direction_x()
            print(f"   Moviendo X={direction_x}mm hacia límite izquierdo")
            result = self.cmd.move_xy(direction_x, 0)
            
            # Esperar límite
            limit_message = self.cmd.uart.wait_for_limit_specific('H_LEFT', timeout=30.0)
            if limit_message:
                print("   Límite izquierdo alcanzado")
                
                # Dar un momento para que se procese el mensaje STEPPER_EMERGENCY_STOP
                time.sleep(1.0)
                
                if captured_distances["horizontal_mm"] is not None:
                    h_distance = captured_distances["horizontal_mm"]
                    print(f"      Distancia total horizontal: {h_distance:.1f}mm")
                else:
                    print("   ❌ No se capturó distancia horizontal")
            
            # 3. Calibrar vertical (abajo)
            print("Paso 3: Calibrando vertical (abajo)...")
            
            # IMPORTANTE: Alejarse un poco del límite horizontal antes de mover verticalmente
            print("   Alejándose del límite horizontal...")
            self.cmd.move_xy(RobotConfig.apply_x_direction(-20), 0)  # 20mm hacia el centro
            time.sleep(1.0)
            
            # Configurar velocidades de homing
            self.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)
            time.sleep(0.5)
            
            # Usar distancia del config
            direction_y = RobotConfig.get_workspace_measure_direction_y()
            print(f"   Moviendo Y={direction_y}mm hacia límite inferior")
            result = self.cmd.move_xy(0, direction_y)
            
            # Esperar límite
            limit_message = self.cmd.uart.wait_for_limit_specific('V_DOWN', timeout=60.0)
            if limit_message:
                print("   Límite inferior alcanzado")
                
                # Dar un momento para que se procese el mensaje STEPPER_EMERGENCY_STOP
                time.sleep(1.0)
                
                if captured_distances["vertical_mm"] is not None:
                    v_distance = captured_distances["vertical_mm"]
                    print(f"      Distancia total vertical: {v_distance:.1f}mm")
                else:
                    print("   ❌ No se capturó distancia vertical")
            else:
                print("   ❌ No se alcanzó límite inferior - revisar cableado o configuración Y")
            
            # Crear medidas finales (restar 10mm para límites izquierdo e inferior)
            SAFETY_MARGIN_MM = 10.0
            measurements = {}
            
            if captured_distances["horizontal_mm"] is not None:
                raw_h_dist = captured_distances["horizontal_mm"]
                workspace_h_dist = max(0, raw_h_dist - SAFETY_MARGIN_MM)  # Restar margen para límite izquierdo
                measurements["horizontal_steps"] = int(workspace_h_dist * RobotConfig.STEPS_PER_MM_H)
                measurements["horizontal_mm"] = round(workspace_h_dist, 1)
                print(f"   ℹ️  Workspace horizontal: {raw_h_dist:.1f}mm medidos - {SAFETY_MARGIN_MM}mm margen = {workspace_h_dist:.1f}mm útiles")
            
            if captured_distances["vertical_mm"] is not None:
                raw_v_dist = captured_distances["vertical_mm"]
                workspace_v_dist = max(0, raw_v_dist - SAFETY_MARGIN_MM)  # Restar margen para límite inferior
                measurements["vertical_steps"] = int(workspace_v_dist * RobotConfig.STEPS_PER_MM_V)
                measurements["vertical_mm"] = round(workspace_v_dist, 1)
                print(f"   ℹ️  Workspace vertical: {raw_v_dist:.1f}mm medidos - {SAFETY_MARGIN_MM}mm margen = {workspace_v_dist:.1f}mm útiles")
            
            # 4. Homing final
            print("Paso 4: Homing final...")
            
            # Alejarse de los límites para dar espacio al homing
            print("   Alejandose de limites...")
            result = self.cmd.move_xy(RobotConfig.apply_x_direction(-50), RobotConfig.apply_y_direction(-50))  # Alejarse de límites
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
            print("   Ejecutando homing directo...")
            
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
            print("      -> Moviendo hacia límite derecho...")
            result = self.cmd.move_xy(RobotConfig.get_homing_direction_x(), 0)
            limit_message = self.cmd.uart.wait_for_limit_specific('H_RIGHT', timeout=30.0)
            if not limit_message:
                return {"success": False, "message": "No se alcanzó límite derecho en homing final"}
            
            # Ir a límite superior
            print("      → Moviendo hacia límite superior...")
            result = self.cmd.move_xy(0, RobotConfig.get_homing_direction_y())
            limit_message = self.cmd.uart.wait_for_limit_specific('V_UP', timeout=30.0)
            if not limit_message:
                return {"success": False, "message": "No se alcanzó límite superior en homing final"}
            
            # APLICAR OFFSET CRÍTICO
            print(f"      → Aplicando offset ({RobotConfig.HOME_OFFSET_H}mm, {RobotConfig.HOME_OFFSET_V}mm)...")
            result = self.cmd.move_xy(RobotConfig.get_home_offset_x(), RobotConfig.get_home_offset_y())
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
                print(f"      Velocidades restauradas: {result['response']}")
            
            print("   Homing final completado")
            
            print(f"\n=== RESULTADOS DE CALIBRACIÓN ===")
            if "horizontal_mm" in measurements:
                print(f"Workspace Horizontal: {measurements['horizontal_mm']:.1f}mm ({measurements['horizontal_steps']} pasos)")
            if "vertical_mm" in measurements:
                print(f"Workspace Vertical: {measurements['vertical_mm']:.1f}mm ({measurements['vertical_steps']} pasos)")
            print("=" * 35)
            
            # Guardar dimensiones del workspace
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
            # Restaurar el método original del UARTManager
            self.cmd.uart._process_emergency_stop = original_process_emergency_stop
