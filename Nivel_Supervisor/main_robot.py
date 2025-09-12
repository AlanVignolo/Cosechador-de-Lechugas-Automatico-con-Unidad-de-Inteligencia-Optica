import logging
import sys
import time
import threading
import json
from controller.uart_manager import UARTManager  
from controller.command_manager import CommandManager
from controller.arm_controller import ArmController
from controller.robot_controller import RobotController
from config.robot_config import RobotConfig
from controller.trajectories import TrajectoryDefinitions, get_trajectory_time_estimate
from camera_manager import get_camera_manager
# Importar módulos de IA para corrección de posición
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Escaner Horizontal'))

# Importar detectores de posición (para corrección)
try:
    print("Intentando importar detectores horizontal y vertical...")
    # Importar funciones horizontales
    from tape_detector_horizontal import (
        get_horizontal_correction_mm,
        get_position_distance_for_correction,
        capture_image_for_correction_debug,
        detect_tape_position_debug
    )
    print("Detector horizontal importado exitosamente")
    
    # Importar funciones verticales
    from tape_detector_vertical import (
        get_vertical_correction_mm,
        capture_image_for_correction_vertical_debug,
        detect_tape_position_vertical_debug
    )
    print("Detector vertical importado exitosamente")
    
    AI_MODULES_AVAILABLE = True
    print("Módulos de corrección de IA disponibles")
except ImportError as e:
    print(f"Error importando módulos de corrección: {e}")
    import traceback
    traceback.print_exc()
    AI_MODULES_AVAILABLE = False
except Exception as e:
    print(f"Error inesperado en imports de corrección: {e}")
    import traceback
    traceback.print_exc()
    AI_MODULES_AVAILABLE = False

# Importar escáner horizontal autónomo (independiente)
SCANNER_AVAILABLE = False
scan_horizontal_with_live_camera = None

try:
    print("Intentando importar escáner horizontal...")
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Escaner Horizontal'))
    from escaner_standalone import scan_horizontal_with_live_camera
    SCANNER_AVAILABLE = True
    print("Escáner horizontal autónomo importado exitosamente")
except ImportError as e:
    print(f"Error importando escáner: {e}")
    SCANNER_AVAILABLE = False
except Exception as e:
    print(f"Error inesperado en import de escáner: {e}")
    SCANNER_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Archivo para persistencia del homing
HOMING_DATA_FILE = os.path.join(os.path.dirname(__file__), 'homing_reference.json')

# Variable global para estado de lechuga
lettuce_on = True  # True = robot tiene lechuga, False = robot no tiene lechuga

def save_homing_reference(position, origin_steps=None):
    """Guardar referencia de homing en archivo JSON"""
    data = {
        'timestamp': time.time(),
        'position': position,
        'origin_steps': origin_steps,
        'homed': True
    }
    try:
        with open(HOMING_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Referencia de homing guardada: {position}")
        return True
    except Exception as e:
        logger.error(f"Error guardando referencia de homing: {e}")
        return False

def load_homing_reference():
    """Cargar referencia de homing desde archivo JSON"""
    try:
        if os.path.exists(HOMING_DATA_FILE):
            with open(HOMING_DATA_FILE, 'r') as f:
                data = json.load(f)
            logger.info(f"Referencia de homing cargada: {data['position']}")
            return data
        else:
            logger.info("No existe referencia de homing previa")
            return None
    except Exception as e:
        logger.error(f"Error cargando referencia de homing: {e}")
        return None

def clear_homing_reference():
    """Limpiar referencia de homing"""
    try:
        if os.path.exists(HOMING_DATA_FILE):
            os.remove(HOMING_DATA_FILE)
        logger.info("Referencia de homing eliminada")
        return True
    except Exception as e:
        logger.error(f"Error eliminando referencia de homing: {e}")
        return False

def test_connection():
    print("Probando conexión UART...")
    
    uart = UARTManager(RobotConfig.SERIAL_PORT, RobotConfig.BAUD_RATE)
    
    if not uart.connect():
        print("No se pudo conectar al robot")
        return False
    
    print("Conectado al robot")
    
    cmd_manager = CommandManager(uart)
    result = cmd_manager.emergency_stop()
    
    if result["success"]:
        print("Comunicación funcionando")
        print(f"Respuesta: {result['response']}")
    else:
        print("Error en comunicación")
        print(f"Error: {result.get('error', 'Desconocido')}")
    
    uart.disconnect()
    return result["success"]

def enviar_movimiento_brazo(cmd_manager):
    print("\n" + "="*50)
    print("CONTROL DE BRAZO - MOVIMIENTO SUAVE")
    print("="*50)
    
    angle1 = input("Ángulo Servo 1 (10-160): ")
    angle2 = input("Ángulo Servo 2 (10-160): ")
    
    tiempo = input("Tiempo en ms (0 para instantáneo): ")
    
    result = cmd_manager.move_arm(int(angle1), int(angle2), int(tiempo))
    print(f"Respuesta: {result['response']}")

def menu_control_brazo(arm_controller):
    while True:
        status = arm_controller.get_current_state()
        
        print("\n" + "="*50)
        print("CONTROL DEL BRAZO")
        print("="*50)
        print(f"Estado actual: {status['state']}")
        print(f"Posición: Servo1={status['position'][0]}°, Servo2={status['position'][1]}°")
        gripper_status = arm_controller.get_gripper_real_status()
        if gripper_status["success"]:
            print(f"Gripper: {gripper_status['state']} (pos: {gripper_status['position']})")
        else:
            print(f"Gripper: {status['gripper']} (sin confirmar)")
        
        if not status['is_known']:
            print("Estado desconocido - la posición no coincide con ningún estado definido")
        
        print("="*50)
        print("ESTADOS DISPONIBLES:")
        
        all_states = arm_controller.list_available_states()
        for i, state in enumerate(all_states, 1):
            if state == status['state']:
                print(f"  {i}. {state} (ACTUAL)")
            else:
                print(f"  {i}. {state}")
        
        print("-"*50)
        print("r. Redetectar estado actual")
        print("0. Volver al menú principal")
        print("-"*50)
        
        opcion = input("Selecciona estado (número): ").strip()
        
        if opcion == '0':
            break
        elif opcion == 'r':
            print("Redetectando estado actual...")
            arm_controller._detect_initial_state()
            print(f"Estado redetectado: {arm_controller.current_state}")
        elif opcion.isdigit():
            state_index = int(opcion) - 1
            if 0 <= state_index < len(all_states):
                target_state = all_states[state_index]
                
                if target_state == status['state']:
                    print(f"Ya estás en el estado '{target_state}'")
                else:
                    print(f"Intentando ir al estado: {target_state}")
                    result = arm_controller.change_state(target_state)
                    
                    if result["success"]:
                        print(f"{result['message']}")
                    else:
                        print(f"No se puede ir a '{target_state}': {result['message']}")
            else:
                print("Número inválido")
        else:
            print("Opción inválida")

        # input("\nPresiona Enter para continuar...")  # Confirmación removida

def test_position_correction_direct(robot, camera_index=0, max_iterations=10, tolerance_mm=1.0):
    """
    Función directa para probar corrección de posición sin StateMachine
    """
    if not AI_MODULES_AVAILABLE:
        return {"success": False, "message": "Módulos de IA no disponibles"}
    
    print("Iniciando corrección de posición con IA...")
    
    # Importar funciones de corrección directa en mm
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))
    
    from tape_detector_horizontal import get_horizontal_correction_mm
    from tape_detector_vertical import get_vertical_correction_mm
    
    try:
        # FASE 1: Corrección HORIZONTAL
        print("Iniciando corrección horizontal...")
        for h_iter in range(max_iterations):
            # Obtener corrección directamente en mm usando la nueva función
            move_mm = get_horizontal_correction_mm(camera_index, AI_TEST_PARAMS['offset_x_mm'])
            
            if move_mm is None:
                return {"success": False, "message": "Error horizontal: No se detectó cinta o error en calibración"}
            
            print(f"Iteración horizontal {h_iter+1}: detección → {move_mm:.1f}mm")
            
            # Verificar si está dentro de tolerancia
            if abs(move_mm) <= tolerance_mm:
                print(f"Corrección horizontal completada en {h_iter+1} iteraciones")
                break
            
            # Ejecutar movimiento relativo horizontal
            move_res = robot.cmd.move_xy(move_mm, 0)  # Solo corrección horizontal
            if not move_res.get("success"):
                print(f"Error en movimiento horizontal: {move_res}")
                return {"success": False, "message": f"Error movimiento: {move_res}"}
            
            time.sleep(1.0)  # Pausa para estabilización
        else:
            return {"success": False, "message": f"No se logró corrección horizontal en {max_iterations} iteraciones"}
        
        # FASE 2: Corrección VERTICAL
        print("Iniciando corrección vertical...")
        for v_iter in range(max_iterations):
            # Obtener corrección directamente en mm usando la nueva función
            move_mm = get_vertical_correction_mm(camera_index, AI_TEST_PARAMS['offset_y_mm'])
            
            if move_mm is None:
                return {"success": False, "message": "Error vertical: No se detectó cinta o error en calibración"}
            
            # Aplicar corrección de signo para dirección correcta
            move_mm = -move_mm
            
            print(f"Iteración vertical {v_iter+1}: detección → {move_mm:.1f}mm")
            
            # Verificar si está dentro de tolerancia
            if abs(move_mm) <= tolerance_mm:
                print(f"Corrección vertical completada en {v_iter+1} iteraciones")
                break
            
            # Ejecutar movimiento relativo vertical
            move_res = robot.cmd.move_xy(0, move_mm)  # Solo corrección vertical
            if not move_res.get("success"):
                print(f"Error en movimiento vertical: {move_res}")
                return {"success": False, "message": f"Error movimiento: {move_res}"}
            
            time.sleep(1.0)  # Pausa para estabilización
        else:
            return {"success": False, "message": f"No se logró corrección vertical en {max_iterations} iteraciones"}
        
        return {"success": True, "message": "Corrección de posición completada exitosamente"}
        
    except Exception as e:
        return {"success": False, "message": f"Error inesperado: {str(e)}"}

# Importar parámetros de configuración desde config
from config.robot_config import AI_TEST_PARAMS

def configure_ai_test_parameters():
    """Configurar parámetros para las pruebas de IA"""
    global AI_TEST_PARAMS
    
    print("\nCONFIGURACION ACTUAL:")
    print(f"   Camara: {AI_TEST_PARAMS['camera_index']}")
    print(f"   Max iteraciones: {AI_TEST_PARAMS['max_iterations']}")
    print(f"   Tolerancia: {AI_TEST_PARAMS['tolerance_mm']}mm")
    print(f"   Offset X: {AI_TEST_PARAMS['offset_x_mm']}mm")
    print(f"   Offset Y: {AI_TEST_PARAMS['offset_y_mm']}mm")
    
    try:
        print("\nPresiona Enter para mantener valor actual")
        
        camera = input(f"Indice de camara [{AI_TEST_PARAMS['camera_index']}]: ").strip()
        if camera: AI_TEST_PARAMS['camera_index'] = int(camera)
        
        iterations = input(f"Max iteraciones [{AI_TEST_PARAMS['max_iterations']}]: ").strip()
        if iterations: AI_TEST_PARAMS['max_iterations'] = int(iterations)
        
        tolerance = input(f"Tolerancia mm [{AI_TEST_PARAMS['tolerance_mm']}]: ").strip()
        if tolerance: AI_TEST_PARAMS['tolerance_mm'] = float(tolerance)
        
        offset_x = input(f"Offset X mm [{AI_TEST_PARAMS['offset_x_mm']}]: ").strip()
        if offset_x: AI_TEST_PARAMS['offset_x_mm'] = float(offset_x)
        
        offset_y = input(f"Offset Y mm [{AI_TEST_PARAMS['offset_y_mm']}]: ").strip()
        if offset_y: AI_TEST_PARAMS['offset_y_mm'] = float(offset_y)
        
        print("\nConfiguracion actualizada")
        
    except ValueError:
        print("Valor invalido, configuracion no cambiada")

def test_horizontal_correction_only(robot):
    """Probar solo corrección horizontal"""
    if not AI_MODULES_AVAILABLE:
        print("Modulos de IA no disponibles")
        return
    
    print("\nCORRECCION HORIZONTAL UNICAMENTE")
    print("ASEGURATE de que:")
    print("- La camara este conectada y funcionando")
    print("- Hay una cinta horizontal visible")
    print("- El robot esta en posicion segura")
    
    # if input("Continuar? (s/N): ").lower() != 's':
    #     print("Prueba cancelada")
    #     return
    print("Iniciando automáticamente...")
    
    try:
        # Cargar calibración horizontal con ruta absoluta
        import sys
        import os
        import json
        
        h_calibration_path = os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal', 'calibracion_lineal.json')
        
        try:
            with open(h_calibration_path, 'r') as f:
                h_calibration = json.load(f)
            a = h_calibration['coefficients']['a']
            b = h_calibration['coefficients']['b']
        except Exception as e:
            print(f"Error cargando calibración horizontal: {str(e)}")
            return
        
        # Importar función de conversión
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
        from calibration_horizontal import pixels_to_mm
        
        def mm_to_pixels(mm, a, b):
            """Convierte milímetros a píxeles: px = (mm - b) / a"""
            return (mm - b) / a
        
        print(f"Iniciando corrección horizontal con calibración: mm = {a:.5f} * px + {b:.2f}")
        
        tolerance_mm = AI_TEST_PARAMS['tolerance_mm']
        
        for iteration in range(AI_TEST_PARAMS['max_iterations']):
            print(f"\nIteracion horizontal {iteration + 1}/{AI_TEST_PARAMS['max_iterations']}")
            
            # Obtener corrección horizontal
            move_mm = get_horizontal_correction_mm(AI_TEST_PARAMS['camera_index'])
            
            if move_mm is None:
                print(f"Error en deteccion horizontal")
                break
            
            print(f"   Correccion detectada: {move_mm:.1f}mm")
            
            if abs(move_mm) <= tolerance_mm:
                print(f"Correccion horizontal completada en {iteration + 1} iteraciones")
                return
            
            # Ejecutar movimiento relativo
            move_result = robot.cmd.move_xy(move_mm, 0)  # Solo corrección horizontal
            if not move_result.get("success"):
                print(f"Error en movimiento: {move_result}")
                break
            
            time.sleep(1.0)
        
        print(f"No se logro correccion en {AI_TEST_PARAMS['max_iterations']} iteraciones")
        
    except Exception as e:
        print(f"Error: {e}")

def test_vertical_correction_only(robot):
    """Probar solo corrección vertical"""
    if not AI_MODULES_AVAILABLE:
        print("Modulos de IA no disponibles")
        return
    
    print("\nCORRECCION VERTICAL UNICAMENTE")
    print("ASEGURATE de que:")
    print("- La camara este conectada y funcionando")
    print("- Hay una cinta vertical visible")
    print("- El robot esta en posicion segura")
    
    # if input("Continuar? (s/N): ").lower() != 's':
    #     print("Prueba cancelada")
    #     return
    print("Iniciando automáticamente...")
    
    try:
        # Cargar calibración vertical con ruta absoluta
        import sys
        import os
        import json
        
        v_calibration_path = os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical', 'calibracion_vertical_lineal.json')
        
        try:
            with open(v_calibration_path, 'r') as f:
                v_calibration = json.load(f)
            a = v_calibration['coefficients']['a']
            b = v_calibration['coefficients']['b']
        except Exception as e:
            print(f"Error cargando calibración vertical: {str(e)}")
            return
        
        # Importar función de conversión
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))
        from test_vertical import pixels_to_mm_vertical
        
        def mm_to_pixels_vertical(mm, a, b):
            """Convierte milímetros a píxeles vertical: px = (mm - b) / a"""
            return (mm - b) / a
        
        print(f"Iniciando corrección vertical con calibración: mm = {a:.5f} * px + {b:.2f}")
        
        for iteration in range(AI_TEST_PARAMS['max_iterations']):
            print(f"\nIteracion vertical {iteration + 1}/{AI_TEST_PARAMS['max_iterations']}")
            
            # Obtener corrección vertical
            move_mm = get_vertical_correction_mm(AI_TEST_PARAMS['camera_index'])
            
            if move_mm is None:
                print(f"Error en deteccion vertical")
                break
            
            print(f"   Correccion detectada: {move_mm:.1f}mm")
            
            if abs(move_mm) <= AI_TEST_PARAMS['tolerance_mm']:
                print(f"Correccion vertical completada en {iteration + 1} iteraciones")
                return
            
            # Ejecutar movimiento relativo
            move_result = robot.cmd.move_xy(0, move_mm)  # Solo corrección vertical
            if not move_result.get("success"):
                print(f"Error en movimiento: {move_result}")
                break
            
            time.sleep(1.0)
        
        print(f"No se logro correccion en {AI_TEST_PARAMS['max_iterations']} iteraciones")
        
    except Exception as e:
        print(f"Error: {e}")

def test_full_position_correction(robot):
    """Probar corrección completa (horizontal + vertical)"""
    if not AI_MODULES_AVAILABLE:
        print("Modulos de IA no disponibles")
        return
    
    print("\nCORRECCION COMPLETA (HORIZONTAL + VERTICAL)")
    print("ASEGURATE de que:")
    print("- La camara este conectada y funcionando")
    print("- Hay una cinta visible (ambos ejes)")
    print("- El robot esta en posicion segura")
    
    # if input("Continuar? (s/N): ").lower() != 's':
    #     print("Prueba cancelada")
    #     return
    print("Iniciando automáticamente...")
    
    try:
        result = test_position_correction_direct(
            robot, 
            AI_TEST_PARAMS['camera_index'], 
            AI_TEST_PARAMS['max_iterations'], 
            AI_TEST_PARAMS['tolerance_mm']
        )
        
        if result['success']:
            print("\nCORRECCION COMPLETADA EXITOSAMENTE")
            print(f"Resultado: {result['message']}")
        else:
            print("\nERROR EN LA CORRECCION")
            print(f"Error: {result['message']}")
            
    except Exception as e:
        print(f"Error inesperado: {e}")

def test_full_position_correction_debug(robot):
    """Probar corrección completa con modo debug (muestra imágenes paso a paso)"""
    if not AI_MODULES_AVAILABLE:
        print("Modulos de IA no disponibles")
        return
    
    print("\nCORRECCION COMPLETA (DEBUG - MODO VISUAL)")
    print("ASEGURATE de que:")
    print("- La camara este conectada y funcionando")
    print("- Hay una cinta visible (ambos ejes)")
    print("- El robot esta en posicion segura")
    print("- Puedes ver las ventanas de imagen (presiona 'c' para continuar)")
    
    # if input("Continuar? (s/N): ").lower() != 's':
    #     print("Prueba cancelada")
    #     return
    print("Iniciando automáticamente...")
    
    try:
        result = test_position_correction_direct_debug(
            robot, 
            AI_TEST_PARAMS['camera_index'], 
            AI_TEST_PARAMS['max_iterations'], 
            AI_TEST_PARAMS['tolerance_mm']
        )
        
        if result['success']:
            print("\nCORRECCION COMPLETADA EXITOSAMENTE")
            print(f"Resultado: {result['message']}")
        else:
            print("\nERROR EN LA CORRECCION")
            print(f"Error: {result['message']}")
            
    except Exception as e:
        print(f"Error inesperado: {e}")

def test_position_correction_direct_debug(robot, camera_index, max_iterations, tolerance_mm):
    """
    Corrección de posición completa (horizontal + vertical) con modo debug visual
    """
    print("Iniciando corrección de posición con IA...")
    
    # Importar funciones de corrección directa en mm
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))
    
    from tape_detector_horizontal import get_horizontal_correction_mm
    from tape_detector_vertical import get_vertical_correction_mm
    
    print("\nINICIANDO CORRECCIÓN HORIZONTAL (DEBUG)...")
    
    # Fase 1: Corrección horizontal con debug
    for iteration in range(1, max_iterations + 1):
        print(f"\nIteracion horizontal {iteration}/{max_iterations}")
        
        try:
            # Capturar imagen con debug visual
            image = capture_image_for_correction_debug(camera_index)
            if image is None:
                return {'success': False, 'message': "Error horizontal: No se pudo capturar imagen"}
            
            # Detectar posición con debug visual (muestra todas las etapas)
            candidates = detect_tape_position_debug(image)
            if not candidates:
                return {'success': False, 'message': "Error horizontal: No se detectó cinta"}
            
            # Calcular movimiento en mm usando calibración (igual que modo normal)
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
            
            try:
                import json
                # Cargar calibración lineal
                calibracion_lineal_path = os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal', "calibracion_lineal_horizontal.json")
                
                with open(calibracion_lineal_path, 'r') as f:
                    calibracion_lineal = json.load(f)
                    
                # Obtener coeficientes de la calibración lineal: mm = a * pixels + b
                a_coef = calibracion_lineal['coefficients']['a']
                b_coef = calibracion_lineal['coefficients']['b']
                
                detected_x = candidates[0]['base_center_x']
                img_center_x = image.shape[1] // 2
                distance_pixels = detected_x - img_center_x
                
                # Convertir píxeles a mm usando calibración lineal: mm = a * pixels + b
                correction_mm = a_coef * distance_pixels + b_coef
                move_mm = correction_mm + AI_TEST_PARAMS['offset_x_mm']
                
            except Exception as e:
                return {'success': False, 'message': f"Error en calibración horizontal: {e}"}
            
            if move_mm is None:
                return {'success': False, 'message': "Error horizontal: No se detectó cinta o error en calibración"}
            
            print(f"Movimiento requerido: {move_mm:.2f}mm")
            
            if abs(move_mm) <= tolerance_mm:
                print(f"Corrección horizontal completada (tolerancia: {tolerance_mm}mm)")
                break
            
            print(f"Moviendo robot: X={move_mm:.2f}mm")
            move_result = robot.cmd.move_xy(move_mm, 0)
            
            if not move_result['success']:
                return {'success': False, 'message': f"Error de movimiento: {move_result['message']}"}
            
            time.sleep(1)
            
        except Exception as e:
            return {'success': False, 'message': f"Error horizontal: {str(e)}"}
    else:
        return {'success': False, 'message': "No se logró corrección horizontal en el número máximo de iteraciones"}
    
    print("\nINICIANDO CORRECCIÓN VERTICAL (DEBUG)...")
    
    # Fase 2: Corrección vertical con debug
    for iteration in range(1, max_iterations + 1):
        print(f"\nIteracion vertical {iteration}/{max_iterations}")
        
        try:
            # Capturar imagen con debug visual
            image_v = capture_image_for_correction_vertical_debug(camera_index)
            if image_v is None:
                return {'success': False, 'message': "Error vertical: No se pudo capturar imagen"}
            
            # Detectar posición con debug visual (muestra todas las etapas)
            candidates_v = detect_tape_position_vertical_debug(image_v)
            if not candidates_v:
                return {'success': False, 'message': "Error vertical: No se detectó cinta"}
            
            # Calcular movimiento en mm usando calibración (igual que modo normal)
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))
            
            try:
                import json
                # Cargar calibración lineal vertical
                calibracion_lineal_path_v = os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical', "calibracion_vertical_lineal.json")
                
                with open(calibracion_lineal_path_v, 'r') as f:
                    calibracion_lineal_v = json.load(f)
                    
                # Obtener coeficientes de la calibración lineal: mm = a * pixels + b
                a_coef_v = calibracion_lineal_v['coefficients']['a']
                b_coef_v = calibracion_lineal_v['coefficients']['b']
                
                detected_y = candidates_v[0]['base_y']
                img_center_y = image_v.shape[0] // 2
                distance_pixels_v = img_center_y - detected_y  # Corrected coordinate system
                
                # Convertir píxeles a mm usando calibración lineal: mm = a * pixels + b
                correction_mm_v = a_coef_v * distance_pixels_v + b_coef_v
                move_mm_v = correction_mm_v + AI_TEST_PARAMS['offset_y_mm']
                
            except Exception as e:
                return {'success': False, 'message': f"Error en calibración vertical: {e}"}
            
            if move_mm_v is None:
                return {'success': False, 'message': "Error vertical: No se detectó cinta o error en calibración"}
            
            # Aplicar corrección de signo para dirección correcta
            move_mm_v = -move_mm_v
            
            print(f"Movimiento requerido: {move_mm_v:.2f}mm")
            
            if abs(move_mm_v) <= tolerance_mm:
                print(f"Corrección vertical completada (tolerancia: {tolerance_mm}mm)")
                break
            
            print(f"Moviendo robot: Y={move_mm_v:.2f}mm")
            move_result_v = robot.cmd.move_xy(0, move_mm_v)
            
            if not move_result_v['success']:
                return {'success': False, 'message': f"Error de movimiento: {move_result_v['message']}"}
            
            time.sleep(1)
            
        except Exception as e:
            return {'success': False, 'message': f"Error vertical: {str(e)}"}
    else:
        return {'success': False, 'message': "No se logró corrección vertical en el número máximo de iteraciones"}
    
    return {'success': True, 'message': "Corrección completa (horizontal + vertical) exitosa"}


def menu_interactivo(uart_manager, robot):
    global lettuce_on
    cmd_manager = robot.cmd
    
    while True:
        print("\n" + "="*60)
        print("MENU PRINCIPAL - CONTROL DEL ROBOT CLAUDIO")
        print("="*60)
        status = robot.get_status()
        print(f"Estado: {'Homed' if status['homed'] else 'Sin Homing'}")
        print(f"Posicion: X={status['position']['x']:.1f}mm, Y={status['position']['y']:.1f}mm")
        print("="*60)
        print("1.  Mover a posicion XY")
        print("2.  Movimiento de brazo completo")
        print("3.  Mover servo individual")
        print("4.  Snapshot de progreso")
        print("5.  Calibracion y Homing")
        print("6.  Control de Gripper")
        print("7.  Parada de emergencia")
        print("8.  Consultar estado completo")
        print("9.  Menu avanzado del brazo")
        print("10. Prueba correccion IA (Horizontal + Vertical)")
        print(f"11. Toggle Lechuga {'ON' if lettuce_on else 'OFF'} (Estado: {'Con lechuga' if lettuce_on else 'Sin lechuga'})")
        print("12. Escaneado horizontal con camara en vivo")
        print("-"*60)
        print("0.  Salir")
        print("-"*60)
        
        opcion = input("Selecciona opción (0-12): ")

        if opcion == '1':
            x = input("Posición X (mm) [Enter mantiene actual]: ").strip()
            y = input("Posición Y (mm) [Enter mantiene actual]: ").strip()
            try:
                status = robot.get_status()
                curr_x = status['position']['x']
                curr_y = status['position']['y']
                x_val = curr_x if x == "" else float(x)
                y_val = curr_y if y == "" else float(y)
                result = cmd_manager.move_xy(x_val, y_val)
                print(f"Respuesta: {result['response']}")
            except ValueError:
                print("Entrada inválida. Usa números (ej. 120 o 120.5).")
                continue
            
        elif opcion == '2':
            enviar_movimiento_brazo(cmd_manager)
            
        elif opcion == '3':
            servo = input("Número de servo (1 o 2): ")
            angulo = input("Ángulo (10-160): ")
            result = cmd_manager.move_servo(int(servo), int(angulo))
            print(f"Respuesta: {result['response']}")
            
        elif opcion == '4':
            # Tomar snapshot del progreso del movimiento actual (no bloqueante)
            result = cmd_manager.get_movement_progress()
            if result["success"]:
                print("Snapshot solicitado...")
            else:
                print(f"Error: {result.get('error', 'Error desconocido')}")
            
        elif opcion == '5':
            print("MENÚ DE CALIBRACIÓN")
            print("1. Homing normal")
            print("2. Calibración completa del workspace")
            calib_opt = input("Opción: ")
            
            if calib_opt == '1':
                print("INICIANDO SECUENCIA DE HOMING")
                print("ASEGÚRATE DE QUE EL ROBOT TENGA ESPACIO LIBRE")
                # confirmar = input("¿Continuar? (s/N): ")
                # 
                # if confirmar.lower() == 's':
                result = robot.home_robot()
                    
                if result["success"]:
                    print("HOMING COMPLETADO")
                    print(f"Posición actual: {result.get('position', 'N/A')}")
                else:
                    print("ERROR EN HOMING")
                    print(f"{result['message']}")
                # else:
                #     print("Homing cancelado")
                    
            elif calib_opt == '2':
                print("INICIANDO CALIBRACIÓN COMPLETA DEL WORKSPACE")
                print("Esto tomará varios minutos y medirá todo el área de trabajo")
                # confirmar = input("¿Continuar? (s/N): ")
                # 
                # if confirmar.lower() == 's':
                result = robot.calibrate_workspace()
                if result["success"]:
                    print("CALIBRACIÓN COMPLETADA")
                    print(f"Medidas: {result['measurements']}")
                else:
                    print("ERROR EN CALIBRACIÓN")
                    print(f"{result['message']}")
                # else:
                #     print("Calibración cancelada")
            else:
                print("Opción inválida")
            
        elif opcion == '6':
            print("\nControl de Gripper:")
            print("1. Accionar Gripper (abre si está cerrado, cierra si está abierto)")
            print("2. Consultar estado")
            gripper_opt = input("Opción: ")
            
            if gripper_opt == '1':
                result = cmd_manager.gripper_toggle()
                print(f"Respuesta: {result['response']}")
            elif gripper_opt == '2':
                result = cmd_manager.get_gripper_status()
                print(f"Estado: {result['response']}")
            else:
                print("Opción inválida")
                continue
            
        elif opcion == '7':
            result = cmd_manager.emergency_stop()
            print(f"Respuesta: {result['response']}")
            
        elif opcion == '8':
            status = robot.get_status()
            print(f"Estado del robot:")
            print(f"Homed: {'Sí' if status['homed'] else 'No'}")
            display_x = RobotConfig.display_x_position(status['position']['x'])
            display_y = RobotConfig.display_y_position(status['position']['y'])
            print(f"Posición: X={display_x}mm, Y={display_y}mm")
            print(f"Brazo: {status['arm']}")
            print(f"Gripper: {status['gripper']}")
            
            # Consultar estado de límites para diagnóstico
            limits_result = cmd_manager.check_limits()
            if limits_result["success"]:
                print(f"Límites: {limits_result['response']}")
            else:
                print("Error consultando límites")
            
        elif opcion == '9':
            menu_control_brazo(robot.arm)
        elif opcion == '10':
            print("\n" + "="*60)
            print("MENU DE PRUEBAS DE CORRECCION IA")
            print("="*60)
            print("1. Correccion HORIZONTAL unicamente")
            print("2. Correccion VERTICAL unicamente")
            print("3. Correccion COMPLETA (horizontal + vertical)")
            print("4. Correccion COMPLETA (DEBUG - muestra imagenes)")
            print("5. Configurar parametros")
            print("0. Volver al menu principal")
            print("-"*60)
            
            sub_opcion = input("Selecciona tipo de prueba (0-5): ")
            
            if sub_opcion == '1':
                print("\nINICIANDO CORRECCION HORIZONTAL")
                test_horizontal_correction_only(robot)
            elif sub_opcion == '2':
                print("\nINICIANDO CORRECCION VERTICAL")
                test_vertical_correction_only(robot)
            elif sub_opcion == '3':
                print("\nINICIANDO CORRECCION COMPLETA")
                test_full_position_correction(robot)
            elif sub_opcion == '4':
                print("\nINICIANDO CORRECCION COMPLETA (DEBUG)")
                test_full_position_correction_debug(robot)
            elif sub_opcion == '5':
                print("\nCONFIGURACION DE PARAMETROS")
                configure_ai_test_parameters()
            elif sub_opcion == '0':
                pass
            else:
                print("Opcion invalida")
        elif opcion == '11':
            lettuce_on = not lettuce_on
            # Sincronizar con el ArmController
            robot.arm.set_lettuce_state(lettuce_on)
            estado = 'CON lechuga' if lettuce_on else 'SIN lechuga'
            print(f"Estado cambiado: Robot ahora está {estado}")
            print(f"Las trayectorias mover_lechuga -> recoger_lechuga usarán el comportamiento para {estado.lower()}")
        elif opcion == '12':
            if SCANNER_AVAILABLE:
                try:
                    success = scan_horizontal_with_live_camera(robot)
                    if success:
                        print("Escaneado completado exitosamente")
                    else:
                        print("El escaneado se completó con errores")
                except KeyboardInterrupt:
                    print("\nEscaneado interrumpido por el usuario")
                except Exception as e:
                    print(f"Error durante el escaneado: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Mensaje de seguridad
                print("\nIMPORTANTE: Verificar que el robot esté en posición segura")
                print("Si el robot quedó en una posición no deseada, usar las opciones de movimiento manual")
            else:
                print("Escáner horizontal no disponible. Verificar imports.")
        elif opcion == '0':
            print("Saliendo...")
            break
        else:
            print("Opción inválida")
    
    # Liberar recursos al salir
    print("Liberando recursos...")
    try:
        camera_mgr = get_camera_manager()
        camera_mgr.release_camera()
    except:
        pass
    uart_manager.disconnect()

if __name__ == "__main__":
    print("CLAUDIO - Control Supervisor del Robot")
    print("=" * 50)
    
    # Inicializar gestor de cámara automáticamente
    print("Inicializando gestor de cámara...")
    camera_mgr = get_camera_manager()
    if camera_mgr.initialize_camera():
        print("Cámara inicializada exitosamente")
    else:
        print("Advertencia: No se pudo inicializar cámara (funciones de IA pueden fallar)")
    
    # Auto-detectar plataforma o usar configuración manual
    detected_platform = RobotConfig.auto_detect_platform()
    serial_port = RobotConfig.get_serial_port()
    
    print(f"Plataforma: {detected_platform}")
    print(f"Puerto: {serial_port}")
    print(f"Baudios: {RobotConfig.BAUD_RATE}")
    print("Conectando al robot...")
    
    uart = UARTManager(serial_port, RobotConfig.BAUD_RATE)
    
    if uart.connect():
        print("Conectado al robot")
        
        cmd_manager = CommandManager(uart)
        
        result = cmd_manager.emergency_stop()
        if result["success"]:
            print("Comunicación OK")
            
            robot = RobotController(cmd_manager)
            print("Sistema inicializado")
            
            menu_interactivo(uart, robot)
        else:
            print("Error en comunicación inicial")
        
        uart.disconnect()
    else:
        print("No se pudo conectar")