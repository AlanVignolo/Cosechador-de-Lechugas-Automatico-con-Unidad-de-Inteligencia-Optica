import logging
import threading
import time
import sys
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from controller.robot_controller import RobotController
from controller.command_manager import CommandManager
from config.robot_config import RobotConfig

# Agregar path para los módulos de IA
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))

try:
    from base_width_detector import get_horizontal_correction_distance
    from vertical_detector import get_vertical_correction_distance
except ImportError as e:
    logging.warning(f"No se pudieron importar módulos de IA: {e}")
    # Funciones dummy para evitar errores
    def get_horizontal_correction_distance(camera_index=0):
        return {'success': False, 'distance_pixels': 0, 'error': 'Módulo no disponible'}
    def get_vertical_correction_distance(camera_index=0):
        return {'success': False, 'distance_pixels': 0, 'error': 'Módulo no disponible'}


class RobotState(str, Enum):
    INIT = "INIT"
    IDLE = "IDLE"
    HOMING = "HOMING"
    SCANNING = "SCANNING"
    MOVING_TO_PICK = "MOVING_TO_PICK"
    HARVESTING = "HARVESTING"
    MOVING_TO_DEPOSIT = "MOVING_TO_DEPOSIT"
    DEPOSITING = "DEPOSITING"
    CALIBRATION = "CALIBRATION"
    MANUAL = "MANUAL"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ERROR = "ERROR"


@dataclass
class StateConfig:
    speed_h: int
    speed_v: int
    require_homed: bool = False
    require_safe_arm_for_xy: bool = True
    allow_xy_moves: bool = True
    ai_modules: List[str] = field(default_factory=list)
    timeout_s: Optional[float] = None


class RobotStateMachine:
    """
    Máquina de estados de alto nivel para el robot CLAUDIO.
    - Controla transiciones y restricciones por estado
    - Aplica velocidades por estado
    - Coordina movimientos XY (con brazo en posición segura)
    - Activa hooks de IA (stubs) cuando corresponde
    """

    def __init__(self, robot: RobotController):
        self.robot = robot
        self.cmd: CommandManager = robot.cmd
        self.logger = logging.getLogger(__name__)

        # Estado
        self.current_state: RobotState = RobotState.INIT
        self.previous_state: Optional[RobotState] = None
        self._pending_transition: Optional[RobotState] = None
        self._state_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Configuración por estado
        self.state_configs: Dict[RobotState, StateConfig] = {
            RobotState.INIT: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=False,
                allow_xy_moves=False,
            ),
            RobotState.IDLE: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=True,
                allow_xy_moves=True,
            ),
            RobotState.HOMING: StateConfig(
                speed_h=RobotConfig.HOMING_SPEED_H,
                speed_v=RobotConfig.HOMING_SPEED_V,
                require_homed=False,
                allow_xy_moves=True,
                timeout_s=180.0,
            ),
            RobotState.SCANNING: StateConfig(
                speed_h=RobotConfig.MAPPING_SPEED_H,
                speed_v=RobotConfig.MAPPING_SPEED_V,
                require_homed=True,
                allow_xy_moves=True,
                ai_modules=["scan"],
            ),
            RobotState.MOVING_TO_PICK: StateConfig(
                speed_h=RobotConfig.ALIGN_SPEED_H,
                speed_v=RobotConfig.ALIGN_SPEED_V,
                require_homed=True,
                allow_xy_moves=True,
                require_safe_arm_for_xy=True,
                timeout_s=60.0,
            ),
            RobotState.HARVESTING: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=True,
                allow_xy_moves=False,
                ai_modules=["position_correction"],
                timeout_s=60.0,
            ),
            RobotState.MOVING_TO_DEPOSIT: StateConfig(
                speed_h=RobotConfig.ALIGN_SPEED_H,
                speed_v=RobotConfig.ALIGN_SPEED_V,
                require_homed=True,
                allow_xy_moves=True,
                require_safe_arm_for_xy=True,
                timeout_s=60.0,
            ),
            RobotState.DEPOSITING: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=True,
                allow_xy_moves=False,
                timeout_s=30.0,
            ),
            RobotState.CALIBRATION: StateConfig(
                speed_h=RobotConfig.HOMING_SPEED_H,
                speed_v=RobotConfig.HOMING_SPEED_V,
                require_homed=False,
                allow_xy_moves=True,
            ),
            RobotState.MANUAL: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=False,
                allow_xy_moves=True,
            ),
            RobotState.EMERGENCY_STOP: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=False,
                allow_xy_moves=False,
            ),
            RobotState.ERROR: StateConfig(
                speed_h=RobotConfig.NORMAL_SPEED_H,
                speed_v=RobotConfig.NORMAL_SPEED_V,
                require_homed=False,
                allow_xy_moves=False,
            ),
        }

        # Hooks opcionales de IA / eventos
        self.hooks: Dict[str, Callable] = {}
        # Posiciones objetivo de trabajo
        self._target_pick_xy: Optional[Tuple[float, float]] = None
        self._deposit_xy: Optional[Tuple[float, float]] = None
        # Flags de control de ciclo
        self._harvest_requested: bool = False

    # =========================
    # API pública
    # =========================
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("StateMachine iniciada")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.logger.info("StateMachine detenida")

    def emergency_stop(self):
        # Parada física
        self.cmd.emergency_stop()
        # Cambiar estado de forma inmediata
        self._force_transition(RobotState.EMERGENCY_STOP)

    def reset_from_emergency(self):
        if self.current_state != RobotState.EMERGENCY_STOP:
            return
        self._request_transition(RobotState.IDLE)

    def enable_manual_control(self):
        self._request_transition(RobotState.MANUAL)

    def disable_manual_control(self):
        self._request_transition(RobotState.IDLE)

    def start_homing(self):
        self._request_transition(RobotState.HOMING)

    def start_calibration(self):
        self._request_transition(RobotState.CALIBRATION)

    def test_position_correction(self, camera_index=0, max_iterations=10, tolerance_mm=1.0) -> Dict:
        """
        Método público para probar la corrección de posición independientemente
        """
        if self.current_state not in [RobotState.IDLE, RobotState.MANUAL]:
            return {"success": False, "message": "Solo se puede probar corrección en estado IDLE o MANUAL"}
        
        try:
            success = self._perform_position_correction(camera_index, max_iterations, tolerance_mm)
            if success:
                return {"success": True, "message": "Corrección de posición completada exitosamente"}
            else:
                return {"success": False, "message": "Falló la corrección de posición"}
        except Exception as e:
            self.logger.error(f"Error en test_position_correction: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}

    def set_scan_hook(self, hook: Callable[[], Optional[Tuple[float, float]]]):
        """Hook que debe devolver (x_mm, y_mm) del próximo objetivo o None."""
        self.hooks["scan_next_target"] = hook

    def set_on_state_change(self, hook: Callable[[RobotState, RobotState], None]):
        self.hooks["on_state_change"] = hook

    def set_deposit_position(self, x_mm: float, y_mm: float):
        self._deposit_xy = (float(x_mm), float(y_mm))

    def request_harvest_cycle(self):
        """Solicitar ciclo de cosecha: scan -> move_to_pick -> harvesting.
        Depósito opcional si está configurada posición de depósito."""
        self._harvest_requested = True

    def move_to(self, x_mm: float, y_mm: float) -> Dict:
        """Movimiento absoluto respetando restricciones del estado actual."""
        with self._state_lock:
            state = self.current_state
        cfg = self.state_configs[state]
        if not cfg.allow_xy_moves:
            return {"success": False, "message": f"Estado {state} no permite movimientos XY"}

        if cfg.require_safe_arm_for_xy and not self.robot.arm.is_in_safe_position():
            res = self.robot.arm.ensure_safe_position()
            if not res.get("success"):
                return res

        # Delegar en RobotController que valida límites
        return self.robot.move_to_absolute(float(x_mm), float(y_mm))

    def get_state_info(self) -> Dict:
        with self._state_lock:
            return {
                "state": self.current_state,
                "homed": self.robot.is_homed,
                "position": dict(self.robot.current_position),
                "arm": self.robot.arm.get_current_state(),
                "pending_transition": self._pending_transition,
                "target_pick": self._target_pick_xy,
                "deposit_xy": self._deposit_xy,
                "harvest_requested": self._harvest_requested,
            }

    # =========================
    # Bucle y transiciones
    # =========================
    def _run_loop(self):
        # Estado inicial
        self._enter_state(RobotState.INIT)
        last_tick = 0.0
        while self._running:
            # Tick máximo ~10 Hz
            if time.time() - last_tick < 0.1:
                time.sleep(0.02)
                continue
            last_tick = time.time()

            # Ejecutar transición pendiente
            if self._pending_transition is not None:
                self._apply_transition(self._pending_transition)
                self._pending_transition = None

            # Ejecutar lógica por estado
            try:
                self._execute_state_once()
            except Exception as e:
                self.logger.error(f"Error en ejecución de estado: {e}")
                self._enter_state(RobotState.ERROR)

    def _execute_state_once(self):
        state = self.current_state
        if state == RobotState.INIT:
            # Preparación inicial -> si no homed, ir a HOMING, sino IDLE
            if not self.robot.is_homed:
                self._request_transition(RobotState.HOMING)
            else:
                self._request_transition(RobotState.IDLE)

        elif state == RobotState.HOMING:
            self._apply_state_config(state)
            result = self.robot.home_robot()
            if result.get("success"):
                self._enter_state(RobotState.IDLE)
            else:
                self.logger.error(f"Homing falló: {result}")
                self._enter_state(RobotState.ERROR)

        elif state == RobotState.CALIBRATION:
            self._apply_state_config(state)
            result = self.robot.calibrate_workspace()
            if result.get("success"):
                self._enter_state(RobotState.IDLE)
            else:
                self.logger.error(f"Calibración falló: {result}")
                self._enter_state(RobotState.ERROR)

        elif state == RobotState.IDLE:
            self._apply_state_config(state)
            # ¿hay pedido de cosecha?
            if self._harvest_requested:
                # Si hay hook de scan, intentamos conseguir objetivo
                target = None
                scan_hook = self.hooks.get("scan_next_target")
                if scan_hook:
                    try:
                        target = scan_hook()
                    except Exception as e:
                        self.logger.error(f"Scan hook error: {e}")
                if target is not None:
                    self._target_pick_xy = (float(target[0]), float(target[1]))
                    self._enter_state(RobotState.MOVING_TO_PICK)
                else:
                    # Si no hay objetivo, pasar por SCANNING para intentar de nuevo
                    self._enter_state(RobotState.SCANNING)
            else:
                # Permanecer en idle
                time.sleep(0.05)

        elif state == RobotState.SCANNING:
            self._apply_state_config(state)
            target = None
            scan_hook = self.hooks.get("scan_next_target")
            if scan_hook:
                try:
                    target = scan_hook()
                except Exception as e:
                    self.logger.error(f"Scan hook error: {e}")
            if target is not None:
                self._target_pick_xy = (float(target[0]), float(target[1]))
                self._enter_state(RobotState.MOVING_TO_PICK)
            else:
                # No target, volver a IDLE y esperar próximo pedido
                self._harvest_requested = False
                self._enter_state(RobotState.IDLE)

        elif state == RobotState.MOVING_TO_PICK:
            self._apply_state_config(state)
            if not self._target_pick_xy:
                self.logger.warning("Sin objetivo de recolección, regresando a IDLE")
                self._enter_state(RobotState.IDLE)
                return
            x, y = self._target_pick_xy
            # Asegurar brazo seguro si se requiere
            cfg = self.state_configs[state]
            if cfg.require_safe_arm_for_xy and not self.robot.arm.is_in_safe_position():
                r = self.robot.arm.ensure_safe_position()
                if not r.get("success"):
                    self.logger.error(f"No se pudo mover brazo a posición segura: {r}")
                    self._enter_state(RobotState.ERROR)
                    return
            # Mover XY absoluto
            move_res = self.robot.move_to_absolute(x, y)
            if not move_res.get("success"):
                self.logger.error(f"Error moviendo a objetivo ({x},{y}): {move_res}")
                self._enter_state(RobotState.ERROR)
                return
            # Esperar final de movimiento por evento
            completed = self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=self.state_configs[state].timeout_s or 60.0)
            if not completed:
                self.logger.error("Timeout esperando fin de movimiento XY")
                self._enter_state(RobotState.ERROR)
                return
            # Alcanzado el objetivo -> ir a cosechar
            self._enter_state(RobotState.HARVESTING)

        elif state == RobotState.HARVESTING:
            self._apply_state_config(state)
            
            # PASO 1: Corrección de posición iterativa
            if not self._perform_position_correction():
                self.logger.error("Falló la corrección de posición")
                self._enter_state(RobotState.ERROR)
                return
            
            # PASO 2: Ejecutar trayectoria de recolección con el ArmController
            res = self.robot.arm.change_state("recoger_lechuga")
            if not res.get("success"):
                self.logger.error(f"No se pudo iniciar recolección: {res}")
                self._enter_state(RobotState.ERROR)
                return
            # Esperar a que termine la trayectoria
            if not self._wait_arm_idle(timeout=self.state_configs[state].timeout_s or 60.0):
                self.logger.error("Timeout esperando fin de recolección")
                self._enter_state(RobotState.ERROR)
                return
            # Ir a estado de transporte (lleva lechuga)
            res = self.robot.arm.change_state("mover_lechuga")
            if not res.get("success"):
                self.logger.error(f"No se pudo ir a transporte: {res}")
                self._enter_state(RobotState.ERROR)
                return
            if not self._wait_arm_idle(timeout=30.0):
                self.logger.error("Timeout esperando mover a transporte")
                self._enter_state(RobotState.ERROR)
                return
            # Decidir siguiente paso
            if self._deposit_xy:
                self._enter_state(RobotState.MOVING_TO_DEPOSIT)
            else:
                # Si no hay depósito configurado, finalizar ciclo y quedar en IDLE con lechuga en mano
                self._harvest_requested = False
                self._target_pick_xy = None
                self._enter_state(RobotState.IDLE)

        elif state == RobotState.MOVING_TO_DEPOSIT:
            self._apply_state_config(state)
            if not self._deposit_xy:
                self.logger.warning("Sin posición de depósito configurada")
                self._enter_state(RobotState.IDLE)
                return
            x, y = self._deposit_xy
            # Asegurar brazo en transporte ya está seguro para XY
            if not self.robot.arm.is_in_safe_position():
                r = self.robot.arm.change_state("mover_lechuga")
                if not r.get("success"):
                    self.logger.error(f"No se pudo asegurar brazo (transporte) antes de depositar: {r}")
                    self._enter_state(RobotState.ERROR)
                    return
                if not self._wait_arm_idle(timeout=20.0):
                    self.logger.error("Timeout asegurando brazo")
                    self._enter_state(RobotState.ERROR)
                    return
            # Mover XY a depósito
            move_res = self.robot.move_to_absolute(x, y)
            if not move_res.get("success"):
                self.logger.error(f"Error moviendo a depósito ({x},{y}): {move_res}")
                self._enter_state(RobotState.ERROR)
                return
            completed = self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=self.state_configs[state].timeout_s or 60.0)
            if not completed:
                self.logger.error("Timeout esperando fin de movimiento a depósito")
                self._enter_state(RobotState.ERROR)
                return
            self._enter_state(RobotState.DEPOSITING)

        elif state == RobotState.DEPOSITING:
            self._apply_state_config(state)
            # Abrir gripper en posición de depósito
            res = self.robot.arm.change_state("depositar_lechuga")
            if not res.get("success"):
                self.logger.error(f"No se pudo iniciar depósito: {res}")
                self._enter_state(RobotState.ERROR)
                return
            if not self._wait_arm_idle(timeout=self.state_configs[state].timeout_s or 30.0):
                self.logger.error("Timeout esperando depósito")
                self._enter_state(RobotState.ERROR)
                return
            # Volver a posición segura y finalizar ciclo
            res = self.robot.arm.change_state("movimiento")
            if not res.get("success"):
                self.logger.error(f"No se pudo volver a posición segura: {res}")
                self._enter_state(RobotState.ERROR)
                return
            if not self._wait_arm_idle(timeout=20.0):
                self.logger.error("Timeout volviendo a posición segura")
                self._enter_state(RobotState.ERROR)
                return
            # Ciclo completo
            self._harvest_requested = False
            self._target_pick_xy = None
            self._enter_state(RobotState.IDLE)

        elif state == RobotState.MANUAL:
            # No hacer nada automáticamente
            time.sleep(0.1)

        elif state == RobotState.EMERGENCY_STOP:
            # Esperar reset explícito
            time.sleep(0.1)

        elif state == RobotState.ERROR:
            # Quedar en error hasta intervención
            time.sleep(0.2)

    def _apply_state_config(self, state: RobotState):
        cfg = self.state_configs[state]
        # Aplicar velocidades
        self.cmd.set_velocities(cfg.speed_h, cfg.speed_v)
        # Verificar homing si es requerido
        if cfg.require_homed and not self.robot.is_homed:
            self.logger.info("Estado requiere homing, forzando transición a HOMING")
            self._enter_state(RobotState.HOMING)

    def _wait_arm_idle(self, timeout: float) -> bool:
        start = time.time()
        # Si no se está ejecutando trayectoria, considerar listo
        if not self.robot.arm.is_executing_trajectory:
            return True
        while time.time() - start < timeout:
            if not self.robot.arm.is_executing_trajectory:
                return True
            time.sleep(0.1)
        return False

    def _perform_position_correction(self, camera_index=0, max_iterations=10, tolerance_mm=1.0) -> bool:
        """
        Realiza corrección iterativa de posición horizontal y vertical usando IA
        Primero horizontal, luego vertical hasta lograr ±1mm de tolerancia
        """
        self.logger.info("Iniciando corrección de posición con IA")
        
        # Conversión de píxeles a mm (aproximada, ajustar según calibración de cámara)
        pixels_per_mm_x = 2.0  # Ajustar según tu setup
        pixels_per_mm_y = 2.0  # Ajustar según tu setup
        tolerance_pixels_x = int(tolerance_mm * pixels_per_mm_x)
        tolerance_pixels_y = int(tolerance_mm * pixels_per_mm_y)
        
        # FASE 1: Corrección HORIZONTAL
        self.logger.info("Iniciando corrección horizontal")
        for h_iter in range(max_iterations):
            # Obtener distancia horizontal usando IA
            h_result = get_horizontal_correction_distance(camera_index)
            
            if not h_result['success']:
                self.logger.error(f"Error en detección horizontal: {h_result.get('error', 'Desconocido')}")
                return False
            
            distance_px = h_result['distance_pixels']
            self.logger.info(f"Iteración horizontal {h_iter+1}: distancia = {distance_px} px")
            
            # Verificar si está dentro de tolerancia
            if abs(distance_px) <= tolerance_pixels_x:
                self.logger.info(f"Corrección horizontal completada en {h_iter+1} iteraciones")
                break
            
            # Calcular movimiento en mm
            move_mm = distance_px / pixels_per_mm_x
            
            # Obtener posición actual
            status = self.robot.get_status()
            current_x = status['position']['x']
            current_y = status['position']['y']
            
            # Mover solo en X (horizontal)
            new_x = current_x + move_mm
            
            # Validar límites del workspace
            if new_x < 0 or new_x > RobotConfig.MAX_X_MM:
                self.logger.warning(f"Movimiento horizontal fuera de límites: {new_x}")
                return False
            
            # Ejecutar movimiento
            move_res = self.robot.move_to_absolute(new_x, current_y)
            if not move_res.get("success"):
                self.logger.error(f"Error en movimiento horizontal: {move_res}")
                return False
            
            # Esperar finalización
            if not self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=30.0):
                self.logger.error("Timeout en movimiento horizontal")
                return False
            
            time.sleep(0.5)  # Pausa para estabilización
        else:
            self.logger.warning(f"No se logró corrección horizontal en {max_iterations} iteraciones")
            return False
        
        # FASE 2: Corrección VERTICAL
        self.logger.info("Iniciando corrección vertical")
        for v_iter in range(max_iterations):
            # Obtener distancia vertical usando IA
            v_result = get_vertical_correction_distance(camera_index)
            
            if not v_result['success']:
                self.logger.error(f"Error en detección vertical: {v_result.get('error', 'Desconocido')}")
                return False
            
            distance_px = v_result['distance_pixels']
            self.logger.info(f"Iteración vertical {v_iter+1}: distancia = {distance_px} px")
            
            # Verificar si está dentro de tolerancia
            if abs(distance_px) <= tolerance_pixels_y:
                self.logger.info(f"Corrección vertical completada en {v_iter+1} iteraciones")
                break
            
            # Calcular movimiento en mm
            move_mm = distance_px / pixels_per_mm_y
            
            # Obtener posición actual
            status = self.robot.get_status()
            current_x = status['position']['x']
            current_y = status['position']['y']
            
            # Mover solo en Y (vertical)
            new_y = current_y + move_mm
            
            # Validar límites del workspace
            if new_y < 0 or new_y > RobotConfig.MAX_Y_MM:
                self.logger.warning(f"Movimiento vertical fuera de límites: {new_y}")
                return False
            
            # Ejecutar movimiento
            move_res = self.robot.move_to_absolute(current_x, new_y)
            if not move_res.get("success"):
                self.logger.error(f"Error en movimiento vertical: {move_res}")
                return False
            
            # Esperar finalización
            if not self.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=30.0):
                self.logger.error("Timeout en movimiento vertical")
                return False
            
            time.sleep(0.5)  # Pausa para estabilización
        else:
            self.logger.warning(f"No se logró corrección vertical en {max_iterations} iteraciones")
            return False
        
        self.logger.info("Corrección de posición completada exitosamente")
        return True

    # =========================
    # Gestión de transiciones
    # =========================
    def _request_transition(self, next_state: RobotState):
        with self._state_lock:
            # Si estamos en emergencia, solo permitimos reset explícito
            if self.current_state == RobotState.EMERGENCY_STOP and next_state not in (RobotState.IDLE, RobotState.HOMING):
                self.logger.warning("En EMERGENCY_STOP: ignorando transición solicitada")
                return
            self._pending_transition = next_state

    def _force_transition(self, next_state: RobotState):
        with self._state_lock:
            self._pending_transition = None
            self._apply_transition(next_state)

    def _apply_transition(self, next_state: RobotState):
        if not self._validate_transition(self.current_state, next_state):
            self.logger.warning(f"Transición inválida {self.current_state} -> {next_state}")
            return
        self._enter_state(next_state)

    def _enter_state(self, next_state: RobotState):
        with self._state_lock:
            prev = self.current_state
            self.previous_state = prev
            self.current_state = next_state
            # Notificar hook
            try:
                hook = self.hooks.get("on_state_change")
                if hook:
                    hook(prev, next_state)
            except Exception as e:
                self.logger.error(f"Error en on_state_change hook: {e}")
            self.logger.info(f"STATE: {prev} -> {next_state}")

    def _validate_transition(self, current: RobotState, nxt: RobotState) -> bool:
        if current == nxt:
            return True
        # Simplificación: no permitir cualquier transición desde ERROR/EMERGENCY salvo a IDLE/HOMING
        if current in (RobotState.ERROR, RobotState.EMERGENCY_STOP):
            return nxt in (RobotState.IDLE, RobotState.HOMING)
        # Reglas básicas
        allowed: Dict[RobotState, List[RobotState]] = {
            RobotState.INIT: [RobotState.HOMING, RobotState.IDLE],
            RobotState.IDLE: [RobotState.HOMING, RobotState.SCANNING, RobotState.MOVING_TO_PICK, RobotState.MANUAL, RobotState.CALIBRATION],
            RobotState.HOMING: [RobotState.IDLE, RobotState.ERROR],
            RobotState.SCANNING: [RobotState.MOVING_TO_PICK, RobotState.IDLE],
            RobotState.MOVING_TO_PICK: [RobotState.HARVESTING, RobotState.ERROR],
            RobotState.HARVESTING: [RobotState.MOVING_TO_DEPOSIT, RobotState.IDLE, RobotState.ERROR],
            RobotState.MOVING_TO_DEPOSIT: [RobotState.DEPOSITING, RobotState.ERROR],
            RobotState.DEPOSITING: [RobotState.IDLE, RobotState.ERROR],
            RobotState.CALIBRATION: [RobotState.IDLE, RobotState.ERROR],
            RobotState.MANUAL: [RobotState.IDLE, RobotState.HOMING],
            RobotState.ERROR: [RobotState.IDLE, RobotState.HOMING],
            RobotState.EMERGENCY_STOP: [RobotState.IDLE, RobotState.HOMING],
        }
        return nxt in allowed.get(current, [])
