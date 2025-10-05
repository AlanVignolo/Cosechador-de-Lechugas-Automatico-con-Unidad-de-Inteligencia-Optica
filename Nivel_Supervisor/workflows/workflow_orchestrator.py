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

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
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

try:
    from escaner_vertical_manual import scan_vertical_manual
    print("Escáner vertical manual importado")
except Exception as e:
    scan_vertical_manual = None
    print(f"Advertencia: No se pudo importar escáner vertical manual: {e}")

try:
    from escaner_standalone import scan_horizontal_with_live_camera
    print("Escáner horizontal importado")
except Exception as e:
    scan_horizontal_with_live_camera = None
    print(f"Advertencia: No se pudo importar escáner horizontal: {e}")

try:
    from configuracion_tubos import config_tubos
    print("Configuración de tubos importada")
except Exception as e:
    config_tubos = None
    print(f"Advertencia: No se pudo importar configuración de tubos: {e}")

try:
    from Clasificador_integrado import clasificar_imagen
    CLASIFICADOR_DISPONIBLE = True
    print("Clasificador de plantas importado")
except Exception as e:
    clasificar_imagen = None
    CLASIFICADOR_DISPONIBLE = False
    print(f"Advertencia: No se pudo importar clasificador de plantas: {e}")

try:
    from matriz_cintas import MatrizCintas
except Exception:
    MatrizCintas = None

# Importar módulo de corrección de posición con IA
TESTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'tests')
if TESTS_DIR not in sys.path:
    sys.path.append(TESTS_DIR)

# Importar también las carpetas de corrección H y V
CORRECCION_H_DIR = os.path.join(IA_DIR, 'Correccion Posicion Horizontal')
CORRECCION_V_DIR = os.path.join(IA_DIR, 'Correccion Posicion Vertical')
if CORRECCION_H_DIR not in sys.path:
    sys.path.append(CORRECCION_H_DIR)
if CORRECCION_V_DIR not in sys.path:
    sys.path.append(CORRECCION_V_DIR)

try:
    from main_robot import test_position_correction_direct, AI_TEST_PARAMS
    POSICIONAMIENTO_DISPONIBLE = True
    print("Posicionamiento con IA importado")
except Exception as e:
    test_position_correction_direct = None
    AI_TEST_PARAMS = None
    POSICIONAMIENTO_DISPONIBLE = False
    print(f"Advertencia: No se pudo importar posicionamiento con IA: {e}")

from config.robot_config import RobotConfig
from core.camera_manager import get_camera_manager


def _clasificar_lechuga_automatico() -> str:
    """
    Usa la IA de clasificación para determinar el estado de la lechuga.

    Returns:
        '1' = lechuga lista (LECHUGA)
        '2' = no lista (otros estados de lechuga)
        '3' = vacío (VASO_NEGRO, VASO_VACIO, VASOS)
    """
    if not CLASIFICADOR_DISPONIBLE:
        print("       Clasificador no disponible, usando input manual")
        opt = input("       Selecciona (1/2/3): ").strip()
        return opt if opt in ['1','2','3'] else '2'

    try:
        import cv2
        import os

        camera_mgr = get_camera_manager()
        if not camera_mgr.is_camera_active():
            camera_mgr.initialize_camera()

        frame = camera_mgr.capture_frame()
        if frame is None:
            print("       No se pudo capturar imagen, usando input manual")
            opt = input("       Selecciona (1/2/3): ").strip()
            return opt if opt in ['1','2','3'] else '2'

        # Usar /tmp para evitar problemas con espacios en nombres de carpetas
        temp_path = '/tmp/temp_workflow_clasificacion_claudio.jpg'
        cv2.imwrite(temp_path, frame)

        resultado = clasificar_imagen(temp_path)
        clase = resultado.get('clase', 'DESCONOCIDO')
        confianza = resultado.get('confianza', 0)

        print(f"       IA: {clase} ({confianza:.1%})")

        if 'LECHUGA' in clase.upper():
            return '1'
        elif clase in ['VASO_NEGRO', 'VASO_VACIO', 'VASOS']:
            return '3'
        elif 'PLANTIN' in clase.upper():
            return '2'
        else:
            return '2'

    except Exception as e:
        print(f"       Error IA: {e} - Modo manual")
        opt = input("       Selecciona (1/2/3): ").strip()
        return opt if opt in ['1','2','3'] else '2'


def _get_ordered_tubos() -> Dict[int, Dict[str, float]]:
    """Return configured tubes as a dict {id: {y_mm, nombre}} ordered by id."""
    if config_tubos is None:
        return {}
    cfg = config_tubos.obtener_configuracion_tubos()
    return {k: cfg[k] for k in sorted(cfg.keys())}


def _resync_position_from_firmware_DISABLED(robot) -> bool:
    """
    Resincronizar posición global del supervisor desde la posición real del firmware.
    Útil antes de movimientos críticos como retorno a (0,0) para evitar errores acumulados.
    
    Returns:
        bool: True si la resincronización fue exitosa, False en caso contrario
    """
    try:
        resp = robot.cmd.get_current_position_mm()
        resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
        
        if 'MM:' in resp_str:
            mm_part = resp_str.split('MM:')[1]
            parts = mm_part.replace('\n', ' ').split(',')
            if len(parts) >= 2:
                fw_x = float(parts[0].strip())
                fw_y = float(parts[1].strip())

                status = robot.get_status()
                sup_x = float(status['position']['x'])
                sup_y = float(status['position']['y'])

                diff_x = abs(fw_x - sup_x)
                diff_y = abs(fw_y - sup_y)
                
                if diff_x > 0.5 or diff_y > 0.5:
                    print(f"[resync] DESINCRONIZACIÓN DETECTADA:")
                    print(f"[resync]   Supervisor: X={sup_x:.1f}mm, Y={sup_y:.1f}mm")
                    print(f"[resync]   Firmware:   X={fw_x:.1f}mm, Y={fw_y:.1f}mm")
                    print(f"[resync]   Diferencia: ΔX={diff_x:.1f}mm, ΔY={diff_y:.1f}mm")
                else:
                    print(f"[resync] Posiciones sincronizadas correctamente (diff < 0.5mm)")

                robot.global_position["x"] = fw_x
                robot.global_position["y"] = fw_y
                
                print(f"[resync] Posición actualizada desde firmware: X={fw_x:.1f}mm, Y={fw_y:.1f}mm")
                return True
        else:
            print(f"[resync] No se pudo parsear respuesta del firmware: {resp_str[:100]}")
            return False
            
    except Exception as e:
        print(f"[resync] Error durante resincronización: {e}")
        import traceback
        traceback.print_exc()
        return False


def homing_simple(robot) -> bool:
    """
    Ejecuta homing simple del robot (tocar límites derecho y superior para establecer origen).

    Pre-requisitos:
    - Brazo debe estar en posición de movimiento (servo1=10°, servo2=10°)

    Returns:
        bool: True si el homing fue exitoso, False en caso contrario
    """
    print("\n" + "="*60)
    print("HOMING SIMPLE")
    print("="*60)

    try:
        # Verificar que el brazo esté en posición de movimiento
        arm_status = robot.arm.get_current_state(force_refresh=True)
        if not robot.arm.is_in_movement_position():
            current_pos = arm_status['position']
            print(f"❌ ERROR: Brazo NO está en posición de movimiento")
            print(f"   Actual: servo1={current_pos[0]}°, servo2={current_pos[1]}°")
            print(f"   Requerido: servo1=10°±5°, servo2=10°±5°")
            print(f"   Por favor mueve el brazo a posición de movimiento primero")
            return False

        print("✓ Brazo en posición de movimiento")
        print("\nIniciando secuencia de homing...")

        # Ejecutar homing
        result = robot.home_robot()

        if result["success"]:
            print("\n" + "="*60)
            print("✓ HOMING COMPLETADO EXITOSAMENTE")
            print("="*60)
            position = result.get('position', {'x': 0, 'y': 0})
            print(f"Posición de origen establecida: X={position['x']:.1f}mm, Y={position['y']:.1f}mm")
            return True
        else:
            print("\n" + "="*60)
            print("❌ ERROR EN HOMING")
            print("="*60)
            print(f"Mensaje: {result.get('message', 'Error desconocido')}")
            return False

    except Exception as e:
        print("\n" + "="*60)
        print("❌ EXCEPCIÓN DURANTE HOMING")
        print("="*60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


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
        errores = []
        if scan_vertical_manual is None:
            errores.append("Escáner vertical")
        if scan_horizontal_with_live_camera is None:
            errores.append("Escáner horizontal")

        if errores:
            print(f"Error: Módulos no disponibles: {', '.join(errores)}")
            print("Verifica que los archivos existan:")
            if scan_vertical_manual is None:
                print(f"  - {ESC_V_DIR}/escaner_vertical_manual.py")
            if scan_horizontal_with_live_camera is None:
                print(f"  - {ESC_H_DIR}/escaner_standalone.py")
            return False

        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        try:
            in_move = robot.arm.is_in_movement_position()
        except Exception:
            in_move = False
        if not in_move:
            print("[inicio_completo] Pre-posicionamiento: brazo no está en 'movimiento'.")
            dims_pp = robot.get_workspace_dimensions()
            if dims_pp.get('calibrated'):
                width_pp = float(dims_pp.get('width_mm', 0.0))
            else:
                width_pp = float(RobotConfig.MAX_X)
            edge_backoff_mm = 20.0
            x_edge_pp = max(0.0, width_pp - edge_backoff_mm)

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

            res_arm_pp = robot.arm.change_state('movimiento')
            if not res_arm_pp.get('success'):
                print(f"Error: no se pudo cambiar brazo a 'movimiento': {res_arm_pp}")
                return False

            if not wait_for_arm_state('movimiento', timeout_s=20.0):
                print(f"Error: Brazo no llegó a 'movimiento'")
                return False

        print("[inicio_completo] Paso 1/4: Homing...")
        res_home = robot.home_robot()
        if not res_home.get("success"):
            print(f"Error en homing: {res_home.get('message')}")
            return False

        print("[inicio_completo] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

        tubos_cfg = _get_ordered_tubos()  # {id: {y_mm, nombre}}
        if not tubos_cfg:
            print("No hay tubos configurados tras el escaneo vertical")
            return False

        print("[inicio_completo] Paso 3/4: Escaneo horizontal por tubo...")
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)
        safety = 10.0
        y_curr = height_mm
        
        status = robot.get_status()
        y_curr = float(status['position']['y'])
        print(f"[workflow] Posición Y inicial desde tracking global: {y_curr:.1f}mm")
        
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
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
            
            y_curr = y_target

            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
                return False

            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")

            first_tube = False

        if return_home:
            print("[workflow] Paso 4/4: Volviendo a (0,0)...")
            
            print("[workflow] Resincronizando posición desde firmware...")
            
            try:
                status_pos = robot.get_status()
                curr_x = float(status_pos['position']['x'])
                curr_y = float(status_pos['position']['y'])
            except Exception:
                curr_x = 0.0
                curr_y = y_curr
            
            dx_back = -curr_x
            dy_back = -curr_y
            print(f"     Desde ({curr_x:.1f}, {curr_y:.1f}) -> (0,0): ΔX={dx_back:.1f}mm, ΔY={dy_back:.1f}mm")
            
            if abs(dx_back) < 2.0 and abs(dy_back) < 2.0:
                print("     Ya estamos en (0,0)")
                try:
                    robot.reset_global_position(0.0, 0.0)
                except Exception:
                    pass
            else:
                ret_res = robot.cmd.move_xy(dx_back, dy_back)
                if not ret_res.get('success'):
                    print(f"Advertencia: No se pudo iniciar movimiento a (0,0): {ret_res}")
                else:
                    print("Regreso a (0,0) solicitado")
                    
                    try:
                        robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
                    except Exception:
                        pass
                    
                    pos_after = robot.get_status()['position']
                    
                    if abs(pos_after['x']) < 5.0 and abs(pos_after['y']) < 5.0:
                        print(f"     ✅ Llegó a (0,0): posición final ({pos_after['x']:.1f}, {pos_after['y']:.1f})")
                        try:
                            robot.reset_global_position(0.0, 0.0)
                        except Exception:
                            pass
                    else:
                        print(f"     NO llegó a (0,0): posición final ({pos_after['x']:.1f}, {pos_after['y']:.1f})")
                        print(f"     Probablemente tocó un límite. Posición NO reseteada.")

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

    Secuencia completa:
    
    PASO 1: Verificar si brazo está en 'mover_lechuga'
        - Si NO está: ir a (X=fin_workspace, Y=tubo1) y cambiar a 'mover_lechuga'
        - Si ya está: continuar
    
    PASO 2: Para cada tubo (ordenado por ID):
        - Ir a la primera cinta del tubo (X=cinta1, Y=tubo)
        
    PASO 3: Para cada cinta del tubo (ordenada por ID):
        - Mover a posición de la cinta (X=cinta, Y=tubo)
        
    PASO 4: Aplicar IA "Analizar Cultivo" (clasificación automática):
        - Captura imagen con cámara
        - Clasifica: LECHUGA (lista), VASO (vacío), otros (no lista)
        - Si no lista o vacío: pasar a siguiente cinta
        
    PASO 5: Si lechuga LISTA:
        - Ejecutar posicionamiento completo (IA H+V - opción 10-3 de main_robot)
        
    PASO 6: Asegurar flag de lechuga en FALSE (sin lechuga)
    
    PASO 7: Cambiar brazo a 'recoger_lechuga'
    
    PASO 8: Al terminar movimiento, setear flag en TRUE (con lechuga)
    
    PASO 9: Cambiar brazo a 'mover_lechuga' para transporte

    PASO 10: Ir a posición de depósito (X=fin, Y=fin-250mm)

    PASO 11: Cambiar brazo a 'depositar_lechuga'
    
    PASO 12: Cambiar brazo a 'mover_lechuga' y setear flag en FALSE
    
    - Continuar con siguiente cinta del mismo tubo
    - Al terminar un tubo, ir a cinta 1 del siguiente tubo
    - Al finalizar todos los tubos, volver a (0,0) si return_home
    """
    try:
        if config_tubos is None:
            print("Error: Configuración de tubos no disponible")
            return False
        if MatrizCintas is None:
            print("Error: Matriz de cintas no disponible")
            return False

        status0 = robot.get_status()
        if not status0.get('homed'):
            print("[cosecha] Robot no homed. Preparando pre-posicionamiento seguro antes de homing...")
            try:
                arm_ok = robot.arm.is_in_movement_position()
            except Exception:
                arm_ok = False
            if not arm_ok:
                dims_pp = robot.get_workspace_dimensions()
                if dims_pp.get('calibrated'):
                    width_pp = float(dims_pp.get('width_mm', 0.0))
                else:
                    width_pp = float(RobotConfig.MAX_X)
                edge_backoff_mm = 20.0
                x_edge_pp = max(0.0, width_pp - edge_backoff_mm)

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
        st_current = robot.get_status()
        current_x = st_current['position']['x']
        current_y = st_current['position']['y']
        is_homed = st_current.get('is_homed', False)

        print(f"[cosecha] Posición actual del supervisor: X={current_x:.1f}mm, Y={current_y:.1f}mm (Homed: {is_homed})")

        if not is_homed:
            print("=" * 60)
            print("❌ ERROR: Robot NO está homed")
            print("=" * 60)
            print("Para ejecutar cosecha interactiva, el robot DEBE estar homed.")
            print("Por favor ejecuta primero:")
            print("  - Opción 2: Inicio completo (homing + escaneos)")
            print("  - O desde el menú principal: Opción 5 -> Homing")
            print("=" * 60)
            return False

        print(f"[cosecha] Robot homed - Usando posición del supervisor (confiable)")

        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
            if width_mm <= 0 or height_mm <= 0:
                print("[cosecha] Dimensiones calibradas inválidas. Usando RobotConfig MAX_X/Y")
                width_mm = float(RobotConfig.MAX_X)
                height_mm = float(RobotConfig.MAX_Y)
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)

        edge_backoff_mm = 20.0
        x_edge = max(0.0, width_mm - edge_backoff_mm)
        y_edge = max(0.0, height_mm - edge_backoff_mm)

        y_deposit = max(0.0, y_edge - 250.0)

        print(f"[cosecha] Workspace: width={width_mm:.1f}mm, height={height_mm:.1f}mm")
        print(f"[cosecha] Borde seguro: x_edge={x_edge:.1f}mm, y_edge={y_edge:.1f}mm")
        print(f"[cosecha] Posición de depósito: X={x_edge:.1f}mm, Y={y_deposit:.1f}mm")

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

        def move_abs(x_target: float, y_target: float, timeout_s: float = 180.0):
            status = robot.get_status()
            curr_x = float(status['position']['x'])
            curr_y = float(status['position']['y'])
            dx = x_target - curr_x
            dy = y_target - curr_y
            if abs(dx) < 0.5:
                dx = 0.0
            if abs(dy) < 0.5:
                dy = 0.0
            if dx == 0.0 and dy == 0.0:
                return True
            print(f"[move_abs] curr=({curr_x:.1f},{curr_y:.1f}) -> target=({x_target:.1f},{y_target:.1f}) | d=({dx:.1f},{dy:.1f})")
            res = robot.cmd.move_xy(dx, dy)
            if not res.get('success'):
                print(f"Movimiento falló: {res}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=timeout_s)
            except Exception:
                pass
            return True

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
            if last_cx is not None and last_cy is not None:
                print(f"[wait_until_position] Aviso: estado no llegó a target dentro de tolerancia. curr=({last_cx:.1f},{last_cy:.1f}), target=({x_target:.1f},{y_target:.1f})")
            return False

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

        def wait_for_arm_state(target_state: str, timeout_s: float = 20.0) -> bool:
            """Espera hasta que el brazo esté realmente en el estado objetivo"""
            import time as _t
            t0 = _t.time()
            print(f"       [wait_for_arm_state] Esperando estado '{target_state}'...")

            while _t.time() - t0 < timeout_s:
                try:
                    if not getattr(robot.arm, 'is_executing_trajectory', False):
                        if robot.arm.current_state == target_state:
                            elapsed = _t.time() - t0
                            print(f"       [wait_for_arm_state] Estado '{target_state}' alcanzado en {elapsed:.1f}s")
                            return True
                except Exception as e:
                    print(f"       [wait_for_arm_state] Exception: {e}")
                    pass
                _t.sleep(0.1)

            print(f"       [wait_for_arm_state] Timeout esperando '{target_state}' (actual: {robot.arm.current_state})")
            return False

        def posicionamiento_completo(robot):
            """Ejecuta corrección de posición con IA (Horizontal + Vertical)"""
            if not POSICIONAMIENTO_DISPONIBLE:
                print("       Módulo de posicionamiento no disponible")
                return False

            try:
                # Usar parámetros de AI_TEST_PARAMS si están disponibles, sino valores por defecto
                if AI_TEST_PARAMS:
                    camera_index = AI_TEST_PARAMS.get('camera_index', 0)
                    max_iterations = AI_TEST_PARAMS.get('max_iterations', 3)
                    tolerance_mm = AI_TEST_PARAMS.get('tolerance_mm', 5.0)
                else:
                    camera_index = 0
                    max_iterations = 3
                    tolerance_mm = 5.0

                print("       Ejecutando corrección H+V...")
                result = test_position_correction_direct(
                    robot,
                    camera_index,
                    max_iterations,
                    tolerance_mm
                )

                if result.get('success'):
                    print(f"       ✓ Corrección completada: {result.get('message', 'OK')}")
                    return True
                else:
                    print(f"       ✗ Corrección falló: {result.get('message', 'Error')}")
                    return False

            except Exception as e:
                print(f"       Error ejecutando corrección: {e}")
                import traceback
                traceback.print_exc()
                return False

        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get('success'):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        tubos_cfg = _get_ordered_tubos()  # {id: {y_mm, nombre}}
        if not tubos_cfg:
            print("No hay tubos configurados")
            return False

        first_tube_id = sorted(tubos_cfg.keys())[0]
        y_tubo1 = float(tubos_cfg[first_tube_id]['y_mm'])
        
        if robot.arm.current_state != 'mover_lechuga':
            print("[cosecha] Brazo NO está en 'mover_lechuga'")
            print(f"[cosecha] Moviendo a posición segura: X={x_edge:.1f}, Y={y_tubo1:.1f}")
            if not move_abs(x_edge, y_tubo1):
                return False
            print("[cosecha] Cambiando brazo a 'mover_lechuga'")
            res_arm = robot.arm.change_state('mover_lechuga')
            if not res_arm.get('success'):
                print(f"No se pudo ir a 'mover_lechuga': {res_arm}")
                return False
            if not wait_for_arm_state('mover_lechuga', timeout_s=20.0):
                print(f"Error: Brazo no llegó a 'mover_lechuga'")
                return False
        else:
            print("[cosecha] Brazo ya está en 'mover_lechuga'")

        matriz = MatrizCintas()

        need_move = True

        tubos_list = sorted(tubos_cfg.keys())
        for tubo_idx, tubo_id in enumerate(tubos_list):
            y_tubo = float(tubos_cfg[tubo_id]['y_mm'])
            nombre_tubo = tubos_cfg[tubo_id]['nombre']
            print(f"\n== TUBO {tubo_id} ({nombre_tubo}) Y={y_tubo:.1f}mm ==")

            cintas = matriz.obtener_cintas_tubo(int(tubo_id))  # list of dicts with x_mm
            if not cintas:
                print("  (Sin cintas registradas para este tubo)")
                continue

            cintas_sorted = sorted(cintas, key=lambda c: c.get('id', 0))

            for idx, cinta in enumerate(cintas_sorted):
                x_cinta = float(cinta.get('x_mm', 0.0))
                print(f"\n  -> Cinta #{cinta.get('id','?')}: X={x_cinta:.1f}mm")

                if need_move:
                    print(f"     Moviendo a cinta: X={x_cinta:.1f}mm, Y={y_tubo:.1f}mm")
                    if not move_abs(x_cinta, y_tubo):
                        return False
                    need_move = False  # Ya nos movimos, la siguiente puede venir pre-posicionada
                else:
                    print(f"     Ya posicionado en cinta desde movimiento anterior")

                print("     [Clasificando...]")
                opt = _clasificar_lechuga_automatico()

                if opt == '3':
                    print("     → VACÍO - siguiente cinta")
                    need_move = True
                    continue
                elif opt == '2':
                    print("     → NO LISTA - siguiente cinta")
                    need_move = True
                    continue

                print("     → LECHUGA LISTA - Iniciando cosecha...")
                print("     → Ejecutando posicionamiento completo (IA H+V)...")
                if not posicionamiento_completo(robot):
                    print("       Advertencia: Posicionamiento completo falló, continuando...")

                print("     → Paso 6: Asegurando flag de lechuga en FALSE (sin lechuga)")
                robot.arm.set_lettuce_state(False)
                
                print("     → Paso 7: Cambiando brazo a 'recoger_lechuga'")
                res_arm = robot.arm.change_state('recoger_lechuga')
                if not res_arm.get('success'):
                    print(f"       Error iniciando transición a 'recoger_lechuga': {res_arm}")
                    return False

                if not wait_for_arm_state('recoger_lechuga', timeout_s=20.0):
                    print(f"       ERROR: Brazo no llegó a 'recoger_lechuga'")
                    return False

                print("     → Paso 8: Lechuga recogida - Seteando flag en TRUE")
                robot.arm.set_lettuce_state(True)
                
                
                print("     → Paso 9: Cambiando brazo a 'mover_lechuga' para transporte")
                res_arm2 = robot.arm.change_state('mover_lechuga')

                if not res_arm2.get('success'):
                    print(f"       ❌ ERROR iniciando transición a 'mover_lechuga': {res_arm2}")
                    return False

                if not wait_for_arm_state('mover_lechuga', timeout_s=20.0):
                    print(f"       ❌ ERROR: Brazo no llegó a 'mover_lechuga'")
                    return False

                print(f"     → ✅ Brazo confirmado en 'mover_lechuga', listo para mover XY")


                print(f"     → Paso 10: Moviendo a posición de depósito: X={x_edge:.1f}mm, Y={y_deposit:.1f}mm")
                if not move_abs(x_edge, y_deposit):
                    return False
                
                print("     → Paso 11: Cambiando brazo a 'depositar_lechuga'")
                res_dep = robot.arm.change_state('depositar_lechuga')
                if not res_dep.get('success'):
                    print(f"       Error iniciando transición a 'depositar_lechuga': {res_dep}")
                    return False

                if not wait_for_arm_state('depositar_lechuga', timeout_s=20.0):
                    print(f"       ERROR: Brazo no llegó a 'depositar_lechuga'")
                    return False
                
                print("     → Paso 12: Lechuga depositada - Cambiando a 'mover_lechuga' y flag en FALSE")
                robot.arm.set_lettuce_state(False)
                res_back = robot.arm.change_state('mover_lechuga')
                if not res_back.get('success'):
                    print(f"       Error iniciando transición a 'mover_lechuga': {res_back}")
                    return False

                if not wait_for_arm_state('mover_lechuga', timeout_s=20.0):
                    print(f"       ❌ ERROR: Brazo no llegó a 'mover_lechuga'")
                    return False

                siguiente_cinta_idx = idx + 1
                if siguiente_cinta_idx < len(cintas_sorted):
                    siguiente_cinta = cintas_sorted[siguiente_cinta_idx]
                    x_siguiente = float(siguiente_cinta.get('x_mm', 0.0))
                    print(f"     → Paso 13: Moviendo directamente a siguiente cinta del mismo tubo (X={x_siguiente:.1f}mm, Y={y_tubo:.1f}mm)")
                    if not move_abs(x_siguiente, y_tubo):
                        return False
                    need_move = False
                else:
                    siguiente_tubo_idx = tubo_idx + 1
                    if siguiente_tubo_idx < len(tubos_list):
                        siguiente_tubo_id = tubos_list[siguiente_tubo_idx]
                        y_siguiente_tubo = float(tubos_cfg[siguiente_tubo_id]['y_mm'])

                        cintas_siguiente_tubo = matriz.obtener_cintas_tubo(int(siguiente_tubo_id))
                        if cintas_siguiente_tubo:
                            cintas_siguiente_sorted = sorted(cintas_siguiente_tubo, key=lambda c: c.get('id', 0))
                            primera_cinta_siguiente = cintas_siguiente_sorted[0]
                            x_primera_siguiente = float(primera_cinta_siguiente.get('x_mm', 0.0))

                            print(f"     → Paso 13: Moviendo directamente a primera cinta del siguiente tubo (X={x_primera_siguiente:.1f}mm, Y={y_siguiente_tubo:.1f}mm)")
                            if not move_abs(x_primera_siguiente, y_siguiente_tubo):
                                return False
                            need_move = False
                        else:
                            print(f"     → Paso 13: Volviendo al tubo (Y={y_tubo:.1f}mm)")
                            fwpos_after = _get_curr_pos_mm_from_fw()
                            if fwpos_after is not None:
                                curr_x_after, _ = fwpos_after
                            else:
                                status_after = robot.get_status()
                                curr_x_after = float(status_after['position']['x'])
                            if not move_abs(curr_x_after, y_tubo):
                                return False
                    else:
                        print(f"     → Paso 13: Volviendo al tubo (Y={y_tubo:.1f}mm)")
                        fwpos_after = _get_curr_pos_mm_from_fw()
                        if fwpos_after is not None:
                            curr_x_after, _ = fwpos_after
                        else:
                            status_after = robot.get_status()
                            curr_x_after = float(status_after['position']['x'])
                        if not move_abs(curr_x_after, y_tubo):
                            return False

                print("     Cosecha y depósito completados para esta cinta")

            print(f"== Fin de {nombre_tubo} ==")

        if return_home:
            fwpos_end = _get_curr_pos_mm_from_fw()
            if fwpos_end is not None:
                _, y_actual = fwpos_end
            else:
                st_end = robot.get_status()
                y_actual = float(st_end['position']['y'])

            print(f"[cosecha] Preparando retorno: mover a borde seguro X={x_edge:.1f}, Y={y_actual:.1f}")
            if not move_abs(x_edge, y_actual, timeout_s=240.0):
                print("Advertencia: No se pudo mover a borde seguro antes de volver a (0,0)")
            else:
                pass

            print("[cosecha] Poniendo brazo en 'movimiento' para retorno al origen")
            res_arm_end = robot.arm.change_state('movimiento')
            if not res_arm_end.get('success'):
                print(f"Advertencia: No se pudo poner brazo en 'movimiento': {res_arm_end}")
            else:
                if not wait_for_arm_state('movimiento', timeout_s=20.0):
                    print(f"Advertencia: Brazo no llegó a 'movimiento', continuando con cuidado")

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

        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        print("[inicio_completo] Paso 1/4: Homing...")
        res_home = robot.home_robot()
        if not res_home.get("success"):
            print(f"Error en homing: {res_home.get('message')}")
            return False

        print("[inicio_completo] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

        tubos_cfg = _get_ordered_tubos()  # {id: {y_mm, nombre}}
        if not tubos_cfg:
            print("No hay tubos configurados tras el escaneo vertical")
            return False

        print("[inicio_completo] Paso 3/4: Escaneo horizontal por tubo...")
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)
        safety = 10.0
        y_curr = height_mm
        
        status = robot.get_status()
        y_curr = float(status['position']['y'])
        print(f"[workflow] Posición Y inicial desde tracking global: {y_curr:.1f}mm")
        
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            dx = 0.0
            try:
                lim = robot.cmd.uart.get_limit_status()
                at_left = bool(lim and lim.get('status', {}).get('H_LEFT', False))
            except Exception:
                at_left = False
            if not first_tube and at_left:
                dx = -(max(0.0, width_mm - safety))
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
            
            y_curr = y_target

            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
                return False

            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")

            first_tube = False

        if return_home:
            print("[inicio_completo] Paso 4/4: Volviendo a (0,0) en un único movimiento...")
            
            print("[inicio_completo] Resincronizando posición desde firmware...")
            
            try:
                lim = robot.cmd.uart.get_limit_status()
                at_left = bool(lim and lim.get('status', {}).get('H_LEFT', False))
            except Exception:
                at_left = False
            
            try:
                status = robot.get_status()
                curr_x = float(status['position']['x'])
                curr_y = float(status['position']['y'])
            except Exception:
                curr_x = 0.0
                curr_y = y_curr
            
            dx_back = -curr_x
            dy_back = -curr_y
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

        status = robot.get_status()
        if not status.get('homed'):
            print("Error: Robot no está homed. Ejecuta homing antes de 'inicio_simple'.")
            return False

        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

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

        print("[inicio_simple] Paso 1/4: Ir a (0,0)...")
        fw_pos = robot.cmd.get_current_position_mm()
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
            time.sleep(0.1)
            _wait_until_position(0.0, 0.0)

        print("[inicio_simple] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

        tubos_cfg = _get_ordered_tubos()
        if not tubos_cfg:
            print("No hay tubos configurados tras el escaneo vertical")
            return False

        print("[inicio_simple] Paso 3/4: Escaneo horizontal por tubo...")
        dims = robot.get_workspace_dimensions()
        if dims.get('calibrated'):
            width_mm = float(dims.get('width_mm', 0.0))
            height_mm = float(dims.get('height_mm', 0.0))
        else:
            width_mm = float(RobotConfig.MAX_X)
            height_mm = float(RobotConfig.MAX_Y)
        safety = 10.0
        y_curr = height_mm
        
        status = robot.get_status()
        y_curr = float(status['position']['y'])
        print(f"[workflow] Posición Y inicial desde tracking global: {y_curr:.1f}mm")
        
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
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
            dy = y_target - y_curr

            print(f"  -> Tubo {tubo_id}: mover a (X=0.0, Y={y_target:.1f}) con ΔX={dx:.1f}mm, ΔY={dy:.1f}mm")
            move_res = robot.cmd.move_xy(dx, dy)
            if not move_res.get('success'):
                print(f"Error moviendo a tubo {tubo_id}: {move_res}")
                return False
            try:
                robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=180.0)
            except Exception:
                pass
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

        if return_home:
            print("[inicio_simple] Paso 4/4: Volviendo a (0,0) en un único movimiento...")
            
            print("[inicio_simple] Resincronizando posición desde firmware...")
            
            try:
                status_pos = robot.get_status()
                curr_x = float(status_pos['position']['x'])
                curr_y = float(status_pos['position']['y'])
            except Exception:
                curr_x = 0.0
                curr_y = y_curr
            dx_back = -curr_x
            dy_back = -curr_y
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

        if not robot.arm.is_in_safe_position():
            res = robot.arm.ensure_safe_position()
            if not res.get("success"):
                print("Error: no se pudo mover el brazo a posición segura")
                return False

        if not robot.arm.is_in_movement_position():
            print("[inicio_completo_hard] Pre-posicionamiento: brazo no está en 'movimiento'.")
            dims_pp = robot.get_workspace_dimensions()
            if dims_pp.get('calibrated'):
                width_pp = float(dims_pp.get('width_mm', 0.0))
            else:
                width_pp = float(RobotConfig.MAX_X)
            edge_backoff_mm = 20.0
            x_edge_pp = max(0.0, width_pp - edge_backoff_mm)

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

        print("[inicio_completo_hard] Paso 1/4: Calibración completa del workspace...")
        calib = robot.calibrate_workspace()
        if not calib.get('success'):
            print(f"Error en calibración: {calib.get('message')}")
            return False

        print("[inicio_completo_hard] Paso 2/4: Escaneo vertical (manual)...")
        v_ok = scan_vertical_manual(robot)
        if not v_ok:
            print("Escaneo vertical con errores")
            return False

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
        
        status = robot.get_status()
        y_curr = float(status['position']['y'])
        print(f"[inicio_completo_hard] Posición Y inicial desde tracking global: {y_curr:.1f}mm")
        
        first_tube = True
        for tubo_id in sorted(tubos_cfg.keys()):
            y_target = float(tubos_cfg[tubo_id]['y_mm'])
            
            try:
                status = robot.get_status()
                curr_x = float(status['position']['x'])
            except Exception:
                curr_x = 0.0
            
            if first_tube:
                dx = 0.0  # Primer tubo: ya estamos en X≈0 después del escaneo vertical
            else:
                dx = -curr_x  # Tubos siguientes: volver desde posición actual a X=0
            
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
            
            y_curr = y_target

            try:
                h_ok = scan_horizontal_with_live_camera(robot, tubo_id=int(tubo_id))
            except Exception as e:
                print(f"Error en escáner horizontal (tubo {tubo_id}): {e}")
            if not h_ok:
                print(f"Escaneo horizontal con errores en tubo {tubo_id}")
            first_tube = False

        if return_home:
            print("[inicio_completo_hard] Paso 4/4: Volviendo a (0,0)...")
            
            try:
                status = robot.get_status()
                curr_x = float(status['position']['x'])
                curr_y = float(status['position']['y'])
            except Exception:
                curr_x = 0.0
                curr_y = 0.0
            
            dx_back = -curr_x
            dy_back = -curr_y
            print(f"     desde ({curr_x:.1f}, {curr_y:.1f}) -> (0,0): ΔX={dx_back:.1f}mm, ΔY={dy_back:.1f}mm")
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