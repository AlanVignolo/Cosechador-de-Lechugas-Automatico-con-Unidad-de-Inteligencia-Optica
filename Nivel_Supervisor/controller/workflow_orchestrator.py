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

# Import MatrizCintas (cintas X por tubo)
try:
    from matriz_cintas import MatrizCintas
except Exception:
    MatrizCintas = None

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

        # Pre-posicionamiento si el brazo NO está en 'movimiento': ir a (x_edge, Y>=250) y luego cambiar a 'movimiento'
        try:
            in_move = robot.arm.is_in_movement_position()
        except Exception:
            in_move = False
        if not in_move:
            print("[inicio_completo] Pre-posicionamiento: brazo no está en 'movimiento'.")
            # Calcular borde seguro (x_edge)
            dims_pp = robot.get_workspace_dimensions()
            if dims_pp.get('calibrated'):
                width_pp = float(dims_pp.get('width_mm', 0.0))
            else:
                width_pp = float(RobotConfig.MAX_X)
            edge_backoff_mm = 20.0
            x_edge_pp = max(0.0, width_pp - edge_backoff_mm)

            # Leer posición actual desde firmware para deltas correctos
            def _parse_fw_xy(resp: str):
                try:
                    if 'MM:' in resp:
                        mm_part = resp.split('MM:')[1]
                        parts = mm_part.replace('\n', ' ').split(',')
                        if len(parts) >= 2:
                            return float(parts[0].strip()), float(parts[1].strip())
                except Exception:
                    pass
                return None

            try:
                fw = robot.cmd.get_current_position_mm()
                fw_str = fw.get('response', '') if isinstance(fw, dict) else str(fw)
            except Exception:
                fw_str = ''
            parsed_pp = _parse_fw_xy(fw_str)
            if parsed_pp:
                curr_x_pp, curr_y_pp = parsed_pp
            else:
                st = robot.get_status()
                curr_x_pp = float(st['position']['x'])
                curr_y_pp = float(st['position']['y'])

            y_target_pp = curr_y_pp if curr_y_pp >= 250.0 else 250.0
            dx_pp = x_edge_pp - curr_x_pp
            dy_pp = y_target_pp - curr_y_pp
            print(f"[inicio_completo] Moviendo a zona segura X={x_edge_pp:.1f}, Y={y_target_pp:.1f} (ΔX={dx_pp:.1f}, ΔY={dy_pp:.1f})")
            res_pp = robot.cmd.move_xy(dx_pp, dy_pp)
            if not res_pp.get('success'):
                print(f"Error en pre-posicionamiento XY: {res_pp}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass
            time.sleep(0.1)

            # Cambiar brazo a 'movimiento' y esperar
            res_arm_pp = robot.arm.change_state('movimiento')
            if not res_arm_pp.get('success'):
                print(f"Error: no se pudo cambiar brazo a 'movimiento': {res_arm_pp}")
                return False
            t0 = time.time()
            while time.time() - t0 < 6.0:
                try:
                    if not getattr(robot.arm, 'is_executing_trajectory', False):
                        break
                except Exception:
                    break
                time.sleep(0.05)

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
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            # Posicionamiento combinado: volver a X≈0 y ajustar Y al siguiente tubo en un único movimiento diagonal
            # Calcular ΔX usando la posición global del supervisor (acumulada por STEPPER_MOVE_COMPLETED)
            dx = 0.0
            try:
                status_pos = robot.get_status()
                curr_x = float(status_pos['position']['x'])
            except Exception:
                curr_x = 0.0
            if not first_tube:
                try:
                    print(f"[inicio_completo] Supervisor X actual = {curr_x:.1f}mm")
                except Exception:
                    pass
                dx = -curr_x
            # ΔY desde la última Y alcanzada
            dy = y_target - y_curr

            print(f"  -> Tubo {tubo_id}: mover a (X=0.0, Y={y_target:.1f}) con ΔX={dx:.1f}mm, ΔY={dy:.1f}mm")
            if dx != 0.0 and dy != 0.0:
                print("     Movimiento diagonal entre tubos (retorno a X≈0 + ajuste Y)")
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

            # Preparar siguiente iteración
            first_tube = False
            time.sleep(0.2)

        # Paso 4: Volver a (0,0)
        if return_home:
            print("[inicio_completo] Paso 4/4: Volviendo a (0,0) en un único movimiento...")
            # Usar posición global del supervisor para volver a X≈0
            try:
                status_pos = robot.get_status()
                curr_x = float(status_pos['position']['x'])
            except Exception:
                curr_x = 0.0
            dx_back = -curr_x
            dy_back = -y_curr
            print(f"     ΔX={dx_back:.1f}mm, ΔY={dy_back:.1f}mm")
            ret_res = robot.cmd.move_xy(dx_back, dy_back)
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


def cosecha_interactiva(robot, return_home: bool = True) -> bool:
    """
    Flujo interactivo de cosecha por tubos y cintas.

    Secuencia:
    - Verificar brazo en 'mover_lechuga'. Si NO está, mover XY a (X=fin_workspace, Y=tubo1),
      y allí cambiar brazo a 'mover_lechuga'. Si ya está, mantenerlo.
    - Para cada tubo (y_mm desde configuracion_tubos):
        - Para cada cinta (x_mm desde MatrizCintas): ir a (x_mm, y_tubo)
        - Preguntar por consola estado de la lechuga: [1] lista, [2] no lista, [3] vacío
        - Si 'no lista' o 'vacío': pasar a siguiente cinta
        - Si 'lista': ejecutar posicionamiento completo (IA H+V),
            * Poner estado de lechuga en False (sin lechuga)
            * Brazo a 'recoger_lechuga' (cerrará gripper)
            * Setear estado de lechuga en True (con lechuga) y volver a 'mover_lechuga'
            * Mover a esquina (X=fin_workspace, Y=fin_workspace)
            * Brazo a 'depositar_lechuga' para soltar
            * Volver a 'mover_lechuga' y setear estado de lechuga en False
        - Continuar con la siguiente cinta
    - Al finalizar todos los tubos, volver a (0,0) si return_home
    """
    try:
        # Validaciones de dependencias
        if config_tubos is None:
            print("Error: Configuración de tubos no disponible")
            return False
        if MatrizCintas is None:
            print("Error: Matriz de cintas no disponible")
            return False

        # Asegurar estado HOMED (para tener origen y tracking coherente)
        status0 = robot.get_status()
        if not status0.get('homed'):
            print("[cosecha] Robot no homed. Preparando pre-posicionamiento seguro antes de homing...")
            # Si el brazo no está en 'movimiento', ir a (x_edge, Y>=250) y poner brazo en 'movimiento'
            try:
                arm_ok = robot.arm.is_in_movement_position()
            except Exception:
                arm_ok = False
            if not arm_ok:
                # Calcular borde seguro (x_edge)
                dims_pp = robot.get_workspace_dimensions()
                if dims_pp.get('calibrated'):
                    width_pp = float(dims_pp.get('width_mm', 0.0))
                else:
                    width_pp = float(RobotConfig.MAX_X)
                edge_backoff_mm = 20.0
                x_edge_pp = max(0.0, width_pp - edge_backoff_mm)

                # Leer posición actual desde firmware para deltas correctos
                def _parse_fw_xy(resp: str):
                    try:
                        if 'MM:' in resp:
                            mm_part = resp.split('MM:')[1]
                            parts = mm_part.replace('\n', ' ').split(',')
                            if len(parts) >= 2:
                                return float(parts[0].strip()), float(parts[1].strip())
                    except Exception:
                        pass
                    return None

                try:
                    fw = robot.cmd.get_current_position_mm()
                    fw_str = fw.get('response', '') if isinstance(fw, dict) else str(fw)
                except Exception:
                    fw_str = ''
                parsed = _parse_fw_xy(fw_str)
                if parsed:
                    curr_x_pp, curr_y_pp = parsed
                else:
                    st = robot.get_status()
                    curr_x_pp = float(st['position']['x'])
                    curr_y_pp = float(st['position']['y'])

                y_target_pp = curr_y_pp if curr_y_pp >= 250.0 else 250.0
                dx_pp = x_edge_pp - curr_x_pp
                dy_pp = y_target_pp - curr_y_pp
                print(f"[cosecha] Pre-posicionamiento: X={x_edge_pp:.1f}, Y={y_target_pp:.1f} (ΔX={dx_pp:.1f}, ΔY={dy_pp:.1f})")
                res_pp = robot.cmd.move_xy(dx_pp, dy_pp)
                if not res_pp.get('success'):
                    print(f"[cosecha] Error en pre-posicionamiento XY: {res_pp}")
                    return False
                try:
                    robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
                except Exception:
                    pass
                time.sleep(0.1)

                # Cambiar brazo a 'movimiento' y esperar
                res_arm_pp = robot.arm.change_state('movimiento')
                if not res_arm_pp.get('success'):
                    print(f"[cosecha] Error cambiando brazo a 'movimiento': {res_arm_pp}")
                    return False
                t0 = time.time()
                while time.time() - t0 < 6.0:
                    try:
                        if not getattr(robot.arm, 'is_executing_trajectory', False):
                            break
                    except Exception:
                        break
                    time.sleep(0.05)

            print("[cosecha] Ejecutando homing...")
            res_home = robot.home_robot()
            if not res_home.get('success'):
                print(f"[cosecha] Error en homing: {res_home.get('message')}")
                return False
        # Obtener dimensiones del workspace
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
            # Validación de medidas válidas
            if width_mm <= 0 or height_mm <= 0:
                print("[cosecha] Dimensiones calibradas inválidas. Usando RobotConfig MAX_X/Y")
                width_mm = float(RobotConfig.MAX_X)
                height_mm = float(RobotConfig.MAX_Y)
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)

        # Evitar acercarse al límite por seguridad al inicio y al depositar
        edge_backoff_mm = 20.0
        x_edge = max(0.0, width_mm - edge_backoff_mm)
        y_edge = max(0.0, height_mm - edge_backoff_mm)

        print(f"[cosecha] Workspace: width={width_mm:.1f}mm, height={height_mm:.1f}mm")
        print(f"[cosecha] Edges: x_edge={x_edge:.1f}mm, y_edge={y_edge:.1f}mm")

        # Helper: obtener posición actual desde firmware (preferido) o supervisor
        def _get_curr_pos_mm_from_fw() -> Optional[Tuple[float, float]]:
            try:
                resp = robot.cmd.get_current_position_mm()
                resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                if 'MM:' in resp_str:
                    mm_part = resp_str.split('MM:')[1]
                    parts = mm_part.replace('\n', ' ').split(',')
                    if len(parts) >= 2:
                        cx = float(parts[0].strip())
                        cy = float(parts[1].strip())
                        return (cx, cy)
            except Exception:
                pass
            return None

        # Helper: mover a posición absoluta
        def move_abs(x_target: float, y_target: float, timeout_s: float = 180.0):
            fw_pos = _get_curr_pos_mm_from_fw()
            if fw_pos is not None:
                curr_x, curr_y = fw_pos
            else:
                status = robot.get_status()
                curr_x = float(status['position']['x'])
                curr_y = float(status['position']['y'])
            dx = x_target - curr_x
            dy = y_target - curr_y
            # Evitar movimientos mínimos (ruido en tracking)
            if abs(dx) < 0.5:
                dx = 0.0
            if abs(dy) < 0.5:
                dy = 0.0
            if dx == 0.0 and dy == 0.0:
                return True
            print(f"[move_abs] curr=({curr_x:.1f},{curr_y:.1f}) -> target=({x_target:.1f},{y_target:.1f}) | d=({dx:.1f},{dy:.1f})")
            # Enviar directamente (firmware coincide con convención del supervisor)
            res = robot.cmd.move_xy(dx, dy)
            if not res.get('success'):
                print(f"Movimiento falló: {res}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=timeout_s)
            except Exception:
                pass
            # Pequeño delay para asegurar que el callback de posición global se procese
            import time as _t
            _t.sleep(0.1)
            return True

        # Helper: esperar hasta que la posición global esté cerca del target
        def wait_until_position(x_target: float, y_target: float, tol_mm: float = 2.0, timeout_s: float = 2.0) -> bool:
            import time as _t
            t0 = _t.time()
            last_cx = None
            last_cy = None
            while _t.time() - t0 < timeout_s:
                fw = _get_curr_pos_mm_from_fw()
                if fw is not None:
                    cx, cy = fw
                else:
                    st = robot.get_status()
                    cx = float(st['position']['x'])
                    cy = float(st['position']['y'])
                last_cx, last_cy = cx, cy
                if abs(cx - x_target) <= tol_mm and abs(cy - y_target) <= tol_mm:
                    return True
                _t.sleep(0.05)
            # No alcanzó exactamente; continuar igual pero avisar
            if last_cx is not None and last_cy is not None:
                print(f"[wait_until_position] Aviso: estado no llegó a target dentro de tolerancia. curr=({last_cx:.1f},{last_cy:.1f}), target=({x_target:.1f},{y_target:.1f})")
            return False

        # Helper: esperar a que el brazo termine cualquier trayectoria en curso
        def wait_arm_idle(timeout_s: float = 5.0) -> bool:
            import time as _t
            t0 = _t.time()
            while _t.time() - t0 < timeout_s:
                try:
                    if not getattr(robot.arm, 'is_executing_trajectory', False):
                        return True
                except Exception:
                    return True
                _t.sleep(0.05)
            print("[wait_arm_idle] Aviso: brazo aún en movimiento tras timeout; continuando con cuidado")
            return False

        # Helper: posicionamiento completo (opción main_robot 10-3)
        def posicionamiento_completo(robot):
            try:
                from main_robot import test_full_position_correction
            except Exception as e:
                print(f"No se pudo importar posicionamiento completo: {e}")
                return False
            try:
                test_full_position_correction(robot)
                return True
            except Exception as e:
                print(f"Error ejecutando posicionamiento completo: {e}")
                return False

        # Asegurar brazo seguro si es necesario
        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get('success'):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        # Preparar lista de tubos ordenada
        tubos_cfg = _get_ordered_tubos()  # {id: {y_mm, nombre}}
        if not tubos_cfg:
            print("No hay tubos configurados")
            return False

        # Ir SIEMPRE al punto inicial seguro (X=fin-20, Y=tubo1) en un solo movimiento y luego asegurar brazo en 'mover_lechuga'
        first_tube_id = sorted(tubos_cfg.keys())[0]
        y_tubo1 = float(tubos_cfg[first_tube_id]['y_mm'])
        print(f"[cosecha] Moviendo a inicio seguro: X={x_edge:.1f}, Y={y_tubo1:.1f}")
        if not move_abs(x_edge, y_tubo1):
            return False
        wait_until_position(x_edge, y_tubo1)
        if robot.arm.current_state != 'mover_lechuga':
            print("[cosecha] Cambiando brazo a 'mover_lechuga'")
            res_arm = robot.arm.change_state('mover_lechuga')
            if not res_arm.get('success'):
                print(f"No se pudo ir a 'mover_lechuga': {res_arm}")
                return False
            # Esperar a que termine el movimiento del brazo antes de avanzar
            wait_arm_idle(6.0)
        else:
            print("[cosecha] Brazo ya en 'mover_lechuga'")

        # Instancia de matriz de cintas
        matriz = MatrizCintas()

        # Iterar por tubos
        for tubo_id in sorted(tubos_cfg.keys()):
            y_tubo = float(tubos_cfg[tubo_id]['y_mm'])
            nombre_tubo = tubos_cfg[tubo_id]['nombre']
            print(f"\n== TUBO {tubo_id} ({nombre_tubo}) Y={y_tubo:.1f}mm ==")

            # Asegurar estar en Y del tubo actual (mantener X actual) solo después de que el brazo esté quieto
            wait_arm_idle(6.0)
            fwpos = _get_curr_pos_mm_from_fw()
            if fwpos is not None:
                curr_x, _ = fwpos
            else:
                status = robot.get_status()
                curr_x = float(status['position']['x'])
            if not move_abs(curr_x, y_tubo):
                return False

            # Obtener cintas de este tubo (x_mm)
            cintas = matriz.obtener_cintas_tubo(int(tubo_id))  # list of dicts with x_mm
            if not cintas:
                print("  (Sin cintas registradas para este tubo)")
                continue

            # Ordenar por id natural
            cintas_sorted = sorted(cintas, key=lambda c: c.get('id', 0))

            for cinta in cintas_sorted:
                x_cinta = float(cinta.get('x_mm', 0.0))
                print(f"  -> Cinta #{cinta.get('id','?')}: mover a X={x_cinta:.1f}mm (horizontal puro)")
                # Asegurar brazo quieto antes de mover XY
                wait_arm_idle(6.0)
                # Mantener Y actual para evitar movimientos diagonales involuntarios
                fwpos = _get_curr_pos_mm_from_fw()
                if fwpos is not None:
                    _, curr_y = fwpos
                else:
                    status = robot.get_status()
                    curr_y = float(status['position']['y'])
                if not move_abs(x_cinta, curr_y):
                    return False

                # Clasificación interactiva
                print("     Estado de la lechuga en esta cinta:")
                print("       1) lista    2) no lista    3) vacío")
                opt = input("       Selecciona (1/2/3): ").strip()
                if opt not in ['1','2','3']:
                    print("       Opción inválida, se asume 'no lista'")
                    opt = '2'

                if opt in ['2','3']:
                    print("     → Saltando a la siguiente cinta")
                    continue

                # 'lista' → posicionamiento completo y recolección
                print("     → Posicionamiento completo (IA H+V)...")
                if not posicionamiento_completo(robot):
                    print("       Advertencia: Posicionamiento completo falló, continuando...")

                # Preparar brazo para recoger: SIN lechuga
                robot.arm.set_lettuce_state(False)
                res_arm = robot.arm.change_state('recoger_lechuga')
                if not res_arm.get('success'):
                    print(f"       Error moviendo a 'recoger_lechuga': {res_arm}")
                    return False
                wait_arm_idle(8.0)
                # Al completarse, setear CON lechuga y volver a transporte
                robot.arm.set_lettuce_state(True)
                res_arm2 = robot.arm.change_state('mover_lechuga')
                if not res_arm2.get('success'):
                    print(f"       Error moviendo a 'mover_lechuga': {res_arm2}")
                    return False
                wait_arm_idle(6.0)

                # Ir a esquina para soltar: (fin_workspace, fin_workspace)
                print(f"     → Llevando a esquina para depositar: ({x_edge:.1f},{y_edge:.1f})")
                if not move_abs(x_edge, y_edge):
                    return False
                # Depositar
                res_dep = robot.arm.change_state('depositar_lechuga')
                if not res_dep.get('success'):
                    print(f"       Error en 'depositar_lechuga': {res_dep}")
                    return False
                wait_arm_idle(6.0)
                # Volver a transporte sin lechuga
                robot.arm.set_lettuce_state(False)
                res_back = robot.arm.change_state('mover_lechuga')
                if not res_back.get('success'):
                    print(f"       Error volviendo a 'mover_lechuga': {res_back}")
                    return False
                wait_arm_idle(6.0)
                # Volver a la Y del tubo actual antes de seguir con la siguiente cinta
                status = robot.get_status()
                curr_x_after_deposit = float(status['position']['x'])
                if not move_abs(curr_x_after_deposit, y_tubo):
                    return False
                wait_until_position(curr_x_after_deposit, y_tubo)

                print("     ✓ Cosecha y depósito completados para esta cinta")
                # Continuar a la siguiente cinta

            # Fin de cintas de este tubo
            print(f"== Fin de {nombre_tubo} ==")

        # Al terminar todos los tubos: volver a (0,0)
        if return_home:
            print("[cosecha] Volviendo a (0,0)...")
            if not move_abs(0.0, 0.0, timeout_s=240.0):
                print("Advertencia: No se pudo volver a (0,0)")

        print("[cosecha] Flujo completado")
        return True

    except KeyboardInterrupt:
        print("[cosecha] Interrumpido por el usuario")
        return False
    except Exception as e:
        print(f"[cosecha] Error: {e}")
        return False


def inicio_completo_legacy(robot, return_home: bool = True) -> bool:
    """
    Inicio completo (LEGACY - calibración del workspace):
    1) Calibración completa del workspace (homing + medida)
    2) Escaneo vertical (manual de flags)
    3) Para cada tubo detectado: mover al Y del tubo y ejecutar escaneo horizontal
       - Mover en diagonal entre tubos: back-off X desde límite izquierdo + ΔY al siguiente tubo
    4) Volver a (0,0) con un solo movimiento
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
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            # Posicionamiento combinado: si venimos del límite izquierdo (tubo anterior),
            # retroceder a X≈0 y subir/bajar al Y objetivo en un único movimiento diagonal
            dx = 0.0
            try:
                lim = robot.cmd.uart.get_limit_status()
                at_left = bool(lim and lim.get('status', {}).get('H_LEFT', False))
            except Exception:
                at_left = False
            if not first_tube and at_left:
                dx = -(max(0.0, width_mm - safety))
            # ΔY desde la última Y alcanzada
            dy = y_target - y_curr

            print(f"  -> Tubo {tubo_id}: mover a (X=0.0, Y={y_target:.1f}) con ΔX={dx:.1f}mm, ΔY={dy:.1f}mm")
            if dx != 0.0 and dy != 0.0:
                print("     Movimiento diagonal entre tubos (retorno a X≈0 + ajuste Y)")
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

            # Preparar siguiente iteración
            first_tube = False
            time.sleep(0.2)

        # Paso 4: Volver a (0,0)
        if return_home:
            print("[inicio_completo] Paso 4/4: Volviendo a (0,0) en un único movimiento...")
            # Incluir componente X solo si seguimos en límite izquierdo; si no, mover solo Y
            try:
                lim = robot.cmd.uart.get_limit_status()
                at_left = bool(lim and lim.get('status', {}).get('H_LEFT', False))
            except Exception:
                at_left = False
            dx_back = -(max(0.0, width_mm - safety)) if at_left else 0.0
            dy_back = -y_curr
            print(f"     ΔX={dx_back:.1f}mm, ΔY={dy_back:.1f}mm")
            ret_res = robot.cmd.move_xy(dx_back, dy_back)
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

        # Helpers locales para posición fiable
        def _parse_mm_from_xy_response(resp: str):
            try:
                s = str(resp or "")
                if "MM:" in s:
                    mm_part = s.split("MM:")[1]
                    parts = mm_part.replace('\n', ' ').split(',')
                    if len(parts) >= 2:
                        x = float(parts[0])
                        y = float(parts[1])
                        return x, y
            except Exception:
                pass
            return None

        def _wait_until_position(x_target: float, y_target: float, tol_mm: float = 2.0, timeout_s: float = 2.0):
            import time as _t
            t0 = _t.time()
            while _t.time() - t0 < timeout_s:
                st = robot.get_status()
                cx = float(st['position']['x'])
                cy = float(st['position']['y'])
                if abs(cx - x_target) <= tol_mm and abs(cy - y_target) <= tol_mm:
                    return True
                _t.sleep(0.05)
            return False

        # Paso 1: Ir a (0,0)
        print("[inicio_simple] Paso 1/4: Ir a (0,0)...")
        # Intentar leer posición real desde firmware (XY?) y usarla para el delta
        fw_pos = robot.cmd.get_current_position_mm()
        # Fallback a estado del supervisor si falla el parseo
        status_now = robot.get_status()
        curr_x = float(status_now['position']['x'])
        curr_y = float(status_now['position']['y'])
        try:
            resp = fw_pos.get('response', '') if isinstance(fw_pos, dict) else str(fw_pos)
        except Exception:
            resp = ""
        parsed = _parse_mm_from_xy_response(resp)
        if parsed:
            curr_x, curr_y = parsed
            print(f"[inicio_simple] Posición actual (firmware): X={curr_x:.1f}mm, Y={curr_y:.1f}mm")
        else:
            print(f"[inicio_simple] Posición actual (supervisor): X={curr_x:.1f}mm, Y={curr_y:.1f}mm")

        if abs(curr_x) > 0.01 or abs(curr_y) > 0.01:
            res0 = robot.cmd.move_xy(-curr_x, -curr_y)
            if not res0.get('success'):
                print(f"Error moviendo a (0,0): {res0}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=120.0)
            except Exception:
                pass
            # Pequeño delay y verificación de llegada
            time.sleep(0.1)
            _wait_until_position(0.0, 0.0)

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
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            # Posicionamiento combinado: si venimos del límite izquierdo (tubo anterior),
            # retroceder a X≈0 y subir/bajar al Y objetivo en un único movimiento diagonal
            dx = 0.0
            try:
                fw = robot.cmd.get_current_position_mm()
                resp = fw.get('response', '') if isinstance(fw, dict) else str(fw)
                if 'MM:' in resp:
                    mm_part = resp.split('MM:')[1]
                    parts = mm_part.replace('\n', ' ').split(',')
                    if len(parts) >= 2:
                        curr_x_fw = float(parts[0].strip())
                    else:
                        curr_x_fw = float(robot.get_status()['position']['x'])
                else:
                    curr_x_fw = float(robot.get_status()['position']['x'])
            except Exception:
                curr_x_fw = float(robot.get_status()['position']['x'])
            if not first_tube:
                dx = -curr_x_fw
            # ΔY desde la última Y alcanzada
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
            # Fallback: esperar según distancia/velocidad
            try:
                v_mm_s = max(1.0, float(RobotConfig.NORMAL_SPEED_V) / float(RobotConfig.STEPS_PER_MM_V))
                est_t = abs(dy) / v_mm_s + 0.5
                time.sleep(min(est_t, 10.0))
            except Exception:
                time.sleep(1.0)
            y_curr = y_target

            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
                return False

            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")

            # Preparar siguiente iteración
            first_tube = False
            time.sleep(0.2)

        # Paso 4: Volver a (0,0)
        if return_home:
            print("[inicio_simple] Paso 4/4: Volviendo a (0,0) en un único movimiento...")
            # Usar posición global del supervisor para calcular retorno a X≈0
            try:
                status_pos = robot.get_status()
                curr_x = float(status_pos['position']['x'])
            except Exception:
                curr_x = 0.0
            dx_back = -curr_x
            dy_back = -y_curr
            ret_res = robot.cmd.move_xy(dx_back, dy_back)
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


def inicio_completo_hard(robot, return_home: bool = True) -> bool:
    """
    Inicio completo con homing completo (calibración del workspace):
    1) Calibración completa del workspace (homing + medida)
    2) Escaneo vertical (manual de flags)
    3) Para cada tubo detectado: mover al Y del tubo y ejecutar escaneo horizontal
       - Mover en diagonal entre tubos: back-off X desde límite izquierdo + ΔY al siguiente tubo
    4) Volver a (0,0) con un solo movimiento
    """
    try:
        if scan_vertical_manual is None or scan_horizontal_with_live_camera is None:
            print("Error: Escáneres no disponibles (import fallido)")
            return False

        # Brazo seguro
        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        # Pre-posicionamiento seguro si el brazo NO está exactamente en 'movimiento' (10°,10°)
        if not robot.arm.is_in_movement_position():
            print("[inicio_completo_hard] Pre-posicionamiento: brazo no está en 'movimiento'.")
            # Calcular borde seguro de trabajo
            dims_pp = robot.get_workspace_dimensions()
            if dims_pp.get('calibrated'):
                width_pp = float(dims_pp.get('width_mm', 0.0))
            else:
                width_pp = float(RobotConfig.MAX_X)
            edge_backoff_mm = 20.0
            x_edge_pp = max(0.0, width_pp - edge_backoff_mm)

            # Leer posición actual desde firmware para deltas correctos
            def _parse_fw_xy(resp: str):
                try:
                    if 'MM:' in resp:
                        mm_part = resp.split('MM:')[1]
                        parts = mm_part.replace('\n', ' ').split(',')
                        if len(parts) >= 2:
                            return float(parts[0].strip()), float(parts[1].strip())
                except Exception:
                    pass
                return None

            try:
                fw = robot.cmd.get_current_position_mm()
                fw_str = fw.get('response', '') if isinstance(fw, dict) else str(fw)
            except Exception:
                fw_str = ''
            parsed = _parse_fw_xy(fw_str)
            if parsed:
                curr_x_pp, curr_y_pp = parsed
            else:
                st = robot.get_status()
                curr_x_pp = float(st['position']['x'])
                curr_y_pp = float(st['position']['y'])

            y_target_pp = curr_y_pp if curr_y_pp >= 250.0 else 250.0
            dx_pp = x_edge_pp - curr_x_pp
            dy_pp = y_target_pp - curr_y_pp
            print(f"[inicio_completo_hard] Moviendo a zona segura X={x_edge_pp:.1f}, Y={y_target_pp:.1f} (ΔX={dx_pp:.1f}, ΔY={dy_pp:.1f})")
            res_pp = robot.cmd.move_xy(dx_pp, dy_pp)
            if not res_pp.get('success'):
                print(f"Error en pre-posicionamiento XY: {res_pp}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass
            time.sleep(0.1)

            # Cambiar brazo a 'movimiento' y esperar a que quede quieto
            res_arm_pp = robot.arm.change_state('movimiento')
            if not res_arm_pp.get('success'):
                print(f"Error: no se pudo cambiar brazo a 'movimiento': {res_arm_pp}")
                return False
            t0 = time.time()
            while time.time() - t0 < 6.0:
                try:
                    if not getattr(robot.arm, 'is_executing_trajectory', False):
                        break
                except Exception:
                    break
                time.sleep(0.05)

        # Paso 1: Calibración completa (homing completo)
        print("[inicio_completo_hard] Paso 1/4: Calibración completa del workspace...")
        calib = robot.calibrate_workspace()
        if not calib.get('success'):
            print(f"Error en calibración: {calib.get('message')}")
            return False

        # Paso 2: Escaneo vertical
        print("[inicio_completo_hard] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

        # Paso 3: Tubos
        tubos_cfg = _get_ordered_tubos()
        if not tubos_cfg:
            print("No hay tubos configurados tras el escaneo vertical")
            return False

        print("[inicio_completo_hard] Paso 3/4: Escaneo horizontal por tubo...")
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)
        safety = 10.0
        y_curr = height_mm
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            dx = 0.0
            # Volver a X≈0 usando posición real de firmware, independientemente del switch
            try:
                fw = robot.cmd.get_current_position_mm()
                resp = fw.get('response', '') if isinstance(fw, dict) else str(fw)
                if 'MM:' in resp:
                    mm_part = resp.split('MM:')[1]
                    parts = mm_part.replace('\n', ' ').split(',')
                    if len(parts) >= 2:
                        curr_x_fw = float(parts[0].strip())
                    else:
                        curr_x_fw = float(robot.get_status()['position']['x'])
                else:
                    curr_x_fw = float(robot.get_status()['position']['x'])
            except Exception:
                curr_x_fw = float(robot.get_status()['position']['x'])
            if not first_tube:
                dx = -curr_x_fw
            dy = y_target - y_curr

            print(f"  -> Tubo {tubo_id}: mover a (X=0.0, Y={y_target:.1f}) con ΔX={dx:.1f}mm, ΔY={dy:.1f}mm")
            if dx != 0.0 and dy != 0.0:
                print("     Movimiento diagonal entre tubos (retorno a X≈0 + ajuste Y)")
            move_res = robot.cmd.move_xy(dx, dy)
            if not move_res.get('success'):
                print(f"Error moviendo a tubo {tubo_id}: {move_res}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass
            # Fallback por tiempo
            try:
                v_mm_s = max(1.0, float(RobotConfig.NORMAL_SPEED_V) / float(RobotConfig.STEPS_PER_MM_V))
                est_t = abs(dy) / v_mm_s + 0.5
                time.sleep(min(est_t, 10.0))
            except Exception:
                time.sleep(1.0)
            y_curr = y_target

            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
                return False
            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")
            first_tube = False
            time.sleep(0.2)

        # Paso 4: Volver a (0,0)
        if return_home:
            print("[inicio_completo_hard] Paso 4/4: Volviendo a (0,0) en un único movimiento...")
            # Usar firmware XY? para determinar ΔX de retorno a X≈0
            try:
                fw = robot.cmd.get_current_position_mm()
                resp = fw.get('response', '') if isinstance(fw, dict) else str(fw)
                if 'MM:' in resp:
                    mm_part = resp.split('MM:')[1]
                    parts = mm_part.replace('\n', ' ').split(',')
                    if len(parts) >= 2:
                        curr_x_fw = float(parts[0].strip())
                    else:
                        curr_x_fw = 0.0
                else:
                    curr_x_fw = 0.0
            except Exception:
                curr_x_fw = 0.0
            dx_back = -curr_x_fw
            dy_back = -y_curr
            print(f"     ΔX={dx_back:.1f}mm, ΔY={dy_back:.1f}mm")
            ret_res = robot.cmd.move_xy(dx_back, dy_back)
            if not ret_res.get('success'):
                print(f"Advertencia: No se pudo volver a (0,0): {ret_res}")
            else:
                print("Regreso a (0,0) solicitado")

        print("[inicio_completo_hard] Secuencia finalizada")
        return True

    except KeyboardInterrupt:
        print("[inicio_completo_hard] Interrumpido por el usuario")
        return False
    except Exception as e:
        print(f"[inicio_completo_hard] Error: {e}")
        return False
