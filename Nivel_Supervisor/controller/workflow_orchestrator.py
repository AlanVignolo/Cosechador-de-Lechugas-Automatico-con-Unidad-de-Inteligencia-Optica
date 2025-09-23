"""
Workflow Orchestrator for automated CLAUDIO routines.

This module keeps production-ready, higher-level flows out of main_robot.py (tests only).

Currently implemented:
- inicio_simple(robot): go to (0,0) -> vertical scan -> for each tube: move & horizontal scan -> return (0,0)
- inicio_completo(robot): homing -> vertical scan -> for each tube: move & horizontal scan -> return (0,0)

Notes:
- Uses relative movements via robot.cmd.move_xy(dx, dy), as in main_robot option 1.
- Horizontal/vertical scanners were adjusted to avoid touching right/upper switches.
- Vertical scan (manual flags) updates 'configuracion_tubos.json' with detected Y positions.

How to use from another module (e.g., a small runner or API endpoint):
    from controller.workflow_orchestrator import inicio_completo
    success = inicio_completo(robot)
"""
from typing import Dict, Tuple, Optional
import os
import sys
import time

# Add paths to IA scanner modules and config
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Nivel_Supervisor/
IA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'Nivel_Supervisor_IA')
ESC_H_DIR = os.path.join(IA_DIR, 'Escaner Horizontal')
ESC_V_DIR = os.path.join(IA_DIR, 'Escaner Vertical')
ANALIZAR_DIR = os.path.join(IA_DIR, 'Analizar Cultivo')

if ESC_H_DIR not in sys.path:
    sys.path.append(ESC_H_DIR)
if ESC_V_DIR not in sys.path:
    sys.path.append(ESC_V_DIR)
if ANALIZAR_DIR not in sys.path:
    sys.path.append(ANALIZAR_DIR)

# Import scanners and config
try:
    from escaner_vertical import scan_vertical_manual  # Vertical (manual flags)
except Exception as e:
    scan_vertical_manual = None

try:
    from escaner_standalone import scan_horizontal_with_live_camera  # Horizontal (flags + snapshots)
except Exception as e:
    scan_horizontal_with_live_camera = None

try:
    from configuracion_tubos import config_tubos
except Exception as e:
    config_tubos = None

# Import configs
from config.robot_config import RobotConfig


def _get_ordered_tubos() -> Dict[int, Dict[str, float]]:
    """Return configured tubes as a dict {id: {y_mm, nombre}} ordered by id."""
    if config_tubos is None:
        return {}
    cfg = config_tubos.obtener_configuracion_tubos()  # {id:int -> {y_mm, nombre}}
    return {k: cfg[k] for k in sorted(cfg.keys())}


def inicio_completo(robot, return_home: bool = True) -> bool:
    """
    Inicio completo:
    1) Homing
    2) Escaneo vertical (manual de flags) sin tocar switch superior
    3) Para cada tubo detectado: mover al Y del tubo y ejecutar escaneo horizontal
       - Evitar tocar switch derecho: no se posiciona en el límite derecho
       - Entre tubos, mover en diagonal (derecha + Y objetivo)
    4) Volver a (0,0) al terminar (opcional)

    Movimiento: relativo con robot.cmd.move_xy(dx, dy).
    """
    try:
        if scan_vertical_manual is None or scan_horizontal_with_live_camera is None:
            print("Error: Escáneres no disponibles (import fallido)")
            return False

        # Asegurar brazo seguro
        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        # Paso 1: Homing
        print("[inicio_completo] Paso 1/4: Homing...")
        res_home = robot.home_robot()
        if not res_home.get("success"):
            print(f"Error en homing: {res_home.get('message')}")
            return False

        # Paso 2: Escaneo vertical
        print("[inicio_completo] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

        # Paso 3: Leer tubos detectados
        tubos_cfg = _get_ordered_tubos()  # {id: {y_mm, nombre}}
        if not tubos_cfg:
            print("No hay tubos configurados tras el escaneo vertical")
            return False

        print("[inicio_completo] Paso 3/4: Escaneo horizontal por tubo...")
        # Calcular ancho/alto del workspace y semilla Y actual (después de escaneo vertical estamos en límite inferior)
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)
        safety = 10.0
        y_curr = height_mm
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            # Posicionamiento: asumir X≈0 (no dependemos de tracking) y calcular Y relativo desde y_curr
            dx = 0.0
            dy = y_target - y_curr

            print(f"  -> Tubo {tubo_id}: mover a (X=0.0, Y={y_target:.1f}) con ΔX={dx:.1f}mm, ΔY={dy:.1f}mm")
            move_res = robot.cmd.move_xy(dx, dy)
            if not move_res.get('success'):
                print(f"Error moviendo a tubo {tubo_id}: {move_res}")
                return False
            # Esperar a que finalice el movimiento antes de iniciar el escaneo horizontal
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass
            # Fallback: esperar según distancia/velocidad (por si no llegó COMPLETED)
            try:
                v_mm_s = max(1.0, float(RobotConfig.NORMAL_SPEED_V) / float(RobotConfig.STEPS_PER_MM_V))
                est_t = abs(dy) / v_mm_s + 0.5
                time.sleep(min(est_t, 10.0))
            except Exception:
                time.sleep(1.0)
            # Actualizar Y actual asumido
            y_curr = y_target

            # Ejecutar escaneo horizontal en el tubo actual
            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
                return False

            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")
                # Continuar con el siguiente tubo a pesar del error

            # Si quedó en límite izquierdo, retroceder hacia el origen X≈0 para el próximo tubo
            try:
                lim = robot.cmd.uart.get_limit_status()
                if lim and lim.get('status', {}).get('H_LEFT', False):
                    # Retroceder a la derecha sin tocar límite derecho (aprox hasta X=0)
                    back_dx = -(max(0.0, width_mm - safety))
                    robot.cmd.move_xy(back_dx, 0.0)
                    # Esperar a que termine el retroceso
                    try:
                        robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=60.0)
                    except Exception:
                        pass
                    # Fallback por tiempo
                    try:
                        h_mm_s = max(1.0, float(RobotConfig.NORMAL_SPEED_H) / float(RobotConfig.STEPS_PER_MM_H))
                        est_t = abs(back_dx) / h_mm_s + 0.5
                        time.sleep(min(est_t, 8.0))
                    except Exception:
                        time.sleep(1.0)
                    time.sleep(0.2)
            except Exception:
                pass

            # Optional: pequeña pausa para estabilización
            time.sleep(0.2)

        # Paso 4: Volver a (0,0)
        if return_home:
            print("[inicio_completo] Paso 4/4: Volviendo a (0,0)...")
            status = robot.get_status()
            curr_x = float(status['position']['x'])
            curr_y = float(status['position']['y'])
            ret_res = robot.cmd.move_xy(-curr_x, -curr_y)
            if not ret_res.get('success'):
                print(f"Advertencia: No se pudo volver a (0,0): {ret_res}")
            else:
                print("Regreso a (0,0) solicitado")

        print("[inicio_completo] Secuencia finalizada")
        return True

    except KeyboardInterrupt:
        print("[inicio_completo] Interrumpido por el usuario")
        return False
    except Exception as e:
        print(f"[inicio_completo] Error: {e}")
        return False


def inicio_simple(robot, return_home: bool = True) -> bool:
    """
    Inicio simple (robot ya referenciado):
    1) Ir a (0,0) sin hacer homing
    2) Escaneo vertical (manual de flags) sin tocar switch superior
    3) Para cada tubo detectado: mover al Y del tubo y ejecutar escaneo horizontal
       - Evitar tocar switch derecho: no se posiciona en el límite derecho
       - Entre tubos, mover en diagonal (derecha + Y objetivo)
    4) Volver a (0,0) al terminar (opcional)

    Movimiento: relativo con robot.cmd.move_xy(dx, dy).
    """
    try:
        if scan_vertical_manual is None or scan_horizontal_with_live_camera is None:
            print("Error: Escáneres no disponibles (import fallido)")
            return False

        # Confirmar que el robot esté homed
        status = robot.get_status()
        if not status.get('homed'):
            print("Error: Robot no está homed. Ejecuta homing antes de 'inicio_simple'.")
            return False

        # Asegurar brazo seguro
        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        # Paso 1: Ir a (0,0)
        print("[inicio_simple] Paso 1/4: Ir a (0,0)...")
        curr_x = float(status['position']['x'])
        curr_y = float(status['position']['y'])
        if abs(curr_x) > 0.01 or abs(curr_y) > 0.01:
            res0 = robot.cmd.move_xy(-curr_x, -curr_y)
            if not res0.get('success'):
                print(f"Error moviendo a (0,0): {res0}")
                return False

        # Paso 2: Escaneo vertical
        print("[inicio_simple] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

        # Paso 3: Leer tubos detectados
        tubos_cfg = _get_ordered_tubos()
        if not tubos_cfg:
            print("No hay tubos configurados tras el escaneo vertical")
            return False

        print("[inicio_simple] Paso 3/4: Escaneo horizontal por tubo...")
        # Calcular ancho util del workspace para retroceso controlado entre tubos
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
        safety = 10.0
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            status = robot.get_status()
            curr_x = float(status['position']['x'])
            curr_y = float(status['position']['y'])

            # Posicionamiento absoluto requerido: X=0, Y=Y_tubo
            dx = -curr_x
            dy = y_target - curr_y

            print(f"  -> Tubo {tubo_id}: mover a (X=0.0, Y={y_target:.1f}) con ΔX={dx:.1f}mm, ΔY={dy:.1f}mm")
            move_res = robot.cmd.move_xy(dx, dy)
            if not move_res.get('success'):
                print(f"Error moviendo a tubo {tubo_id}: {move_res}")
                return False

            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
                return False

            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")

            # Si quedó en límite izquierdo, retroceder hacia el origen X≈0 para el próximo tubo
            try:
                lim = robot.cmd.uart.get_limit_status()
                if lim and lim.get('status', {}).get('H_LEFT', False):
                    back_dx = -(max(0.0, width_mm - safety))
                    robot.cmd.move_xy(back_dx, 0.0)
                    # Esperar a que termine el retroceso
                    try:
                        robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=60.0)
                    except Exception:
                        pass
                    time.sleep(0.2)
            except Exception:
                pass

            # Optional: pequeña pausa para estabilización
            time.sleep(0.2)

        # Paso 4: Volver a (0,0)
        if return_home:
            print("[inicio_simple] Paso 4/4: Volviendo a (0,0)...")
            status = robot.get_status()
            curr_x = float(status['position']['x'])
            curr_y = float(status['position']['y'])
            ret_res = robot.cmd.move_xy(-curr_x, -curr_y)
            if not ret_res.get('success'):
                print(f"Advertencia: No se pudo volver a (0,0): {ret_res}")
            else:
                print("Regreso a (0,0) solicitado")

        print("[inicio_simple] Secuencia finalizada")
        return True

    except KeyboardInterrupt:
        print("[inicio_simple] Interrumpido por el usuario")
        return False
    except Exception as e:
        print(f"[inicio_simple] Error: {e}")
        return False
