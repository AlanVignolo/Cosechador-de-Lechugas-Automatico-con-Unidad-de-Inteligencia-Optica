import logging
import sys
import time
import threading
from controller.uart_manager import UARTManager
from controller.command_manager import CommandManager
from controller.robot_controller import RobotController
from config.robot_config import RobotConfig
from controller.trajectories import TrajectoryDefinitions, get_trajectory_time_estimate
# Importar módulos de IA para corrección de posición
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))

try:
    from base_width_detector import get_horizontal_correction_distance
    from vertical_detector import get_vertical_correction_distance
    AI_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Módulos de IA no disponibles: {e}")
    AI_MODULES_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

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

        input("\nPresiona Enter para continuar...")

def test_position_correction_direct(robot, camera_index=0, max_iterations=10, tolerance_mm=1.0):
    """
    Función directa para probar corrección de posición sin StateMachine
    """
    if not AI_MODULES_AVAILABLE:
        return {"success": False, "message": "Módulos de IA no disponibles"}
    
    print("Iniciando corrección de posición con IA...")
    
    # Conversión de píxeles a mm (aproximada, ajustar según calibración de cámara)
    pixels_per_mm_x = 2.0  # Ajustar según tu setup
    pixels_per_mm_y = 2.0  # Ajustar según tu setup
    tolerance_pixels_x = int(tolerance_mm * pixels_per_mm_x)
    tolerance_pixels_y = int(tolerance_mm * pixels_per_mm_y)
    
    try:
        # FASE 1: Corrección HORIZONTAL
        print("Iniciando corrección horizontal...")
        for h_iter in range(max_iterations):
            # Obtener distancia horizontal usando IA
            h_result = get_horizontal_correction_distance(camera_index)
            
            if not h_result['success']:
                print(f"Error en detección horizontal: {h_result.get('error', 'Desconocido')}")
                return {"success": False, "message": f"Error horizontal: {h_result.get('error')}"}
            
            distance_px = h_result['distance_pixels']
            # CORREGIR SIGNO: Para coherencia, valores positivos de X van hacia la derecha
            # Si IA detecta que necesita ir hacia la izquierda (-px), el robot debe moverse hacia la derecha (+mm)
            move_mm = -distance_px / pixels_per_mm_x  # Invertir signo para coherencia
            
            print(f"Iteración horizontal {h_iter+1}: corrección = {distance_px}px → {move_mm:.1f}mm")
            
            # Verificar si está dentro de tolerancia
            if abs(distance_px) <= tolerance_pixels_x:
                print(f"Corrección horizontal completada en {h_iter+1} iteraciones")
                break
            
            # Obtener posición actual
            status = robot.get_status()
            current_x = status['position']['x']
            current_y = status['position']['y']
            
            # Mover solo en X (horizontal)
            new_x = current_x + move_mm
            
            # Validar límites del workspace
            if new_x < 0 or new_x > RobotConfig.MAX_X:
                print(f"Movimiento horizontal fuera de límites: {new_x}mm")
                print(f"Límites válidos: 0 a {RobotConfig.MAX_X}mm")
                return {"success": False, "message": f"Límites excedidos: {new_x}mm"}
            
            # Ejecutar movimiento
            move_res = robot.move_to_absolute(new_x, current_y)
            if not move_res.get("success"):
                print(f"Error en movimiento horizontal: {move_res}")
                return {"success": False, "message": f"Error movimiento: {move_res}"}
            
            time.sleep(1.0)  # Pausa para estabilización
        else:
            return {"success": False, "message": f"No se logró corrección horizontal en {max_iterations} iteraciones"}
        
        # FASE 2: Corrección VERTICAL
        print("Iniciando corrección vertical...")
        for v_iter in range(max_iterations):
            # Obtener distancia vertical usando IA
            v_result = get_vertical_correction_distance(camera_index)
            
            if not v_result['success']:
                print(f"Error en detección vertical: {v_result.get('error', 'Desconocido')}")
                return {"success": False, "message": f"Error vertical: {v_result.get('error')}"}
            
            distance_px = v_result['distance_pixels']
            # CORREGIR SIGNO: Para coherencia, valores positivos de Y van hacia abajo
            # Si IA detecta que necesita ir hacia arriba (-px), el robot debe moverse hacia abajo (+mm)
            move_mm = -distance_px / pixels_per_mm_y  # Invertir signo para coherencia
            
            print(f"Iteración vertical {v_iter+1}: corrección = {distance_px}px → {move_mm:.1f}mm")
            
            # Verificar si está dentro de tolerancia
            if abs(distance_px) <= tolerance_pixels_y:
                print(f"Corrección vertical completada en {v_iter+1} iteraciones")
                break
            
            # Obtener posición actual
            status = robot.get_status()
            current_x = status['position']['x']
            current_y = status['position']['y']
            
            # Mover solo en Y (vertical)
            new_y = current_y + move_mm
            
            # Validar límites del workspace
            if new_y < 0 or new_y > RobotConfig.MAX_Y:
                print(f"Movimiento vertical fuera de límites: {new_y}mm")
                print(f"Límites válidos: 0 a {RobotConfig.MAX_Y}mm")
                return {"success": False, "message": f"Límites excedidos: {new_y}mm"}
            
            # Ejecutar movimiento
            move_res = robot.move_to_absolute(current_x, new_y)
            if not move_res.get("success"):
                print(f"Error en movimiento vertical: {move_res}")
                return {"success": False, "message": f"Error movimiento: {move_res}"}
            
            time.sleep(1.0)  # Pausa para estabilización
        else:
            return {"success": False, "message": f"No se logró corrección vertical en {max_iterations} iteraciones"}
        
        return {"success": True, "message": "Corrección de posición completada exitosamente"}
        
    except Exception as e:
        return {"success": False, "message": f"Error inesperado: {str(e)}"}

def menu_interactivo(uart_manager, robot):
    cmd_manager = robot.cmd
    
    while True:
        opcion = input("Selecciona opción: ")

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
                print("📸 Snapshot solicitado...")
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
                confirmar = input("¿Continuar? (s/N): ")
                
                if confirmar.lower() == 's':
                    result = robot.home_robot()
                    
                    if result["success"]:
                        print("HOMING COMPLETADO")
                        print(f"Posición actual: {result.get('position', 'N/A')}")
                    else:
                        print("ERROR EN HOMING")
                        print(f"{result['message']}")
                else:
                    print("Homing cancelado")
                    
            elif calib_opt == '2':
                print("INICIANDO CALIBRACIÓN COMPLETA DEL WORKSPACE")
                print("Esto tomará varios minutos y medirá todo el área de trabajo")
                confirmar = input("¿Continuar? (s/N): ")
                
                if confirmar.lower() == 's':
                    result = robot.calibrate_workspace()
                    if result["success"]:
                        print("CALIBRACIÓN COMPLETADA")
                        print(f"Medidas: {result['measurements']}")
                    else:
                        print("ERROR EN CALIBRACIÓN")
                        print(f"{result['message']}")
                else:
                    print("Calibración cancelada")
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
            print(f"Posición: X={status['position']['x']}mm, Y={status['position']['y']}mm")
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
            print("\n=== PRUEBA DE CORRECCIÓN AUTOMÁTICA ===")
            print("Esta función usará la cámara y los módulos de IA para centrar automáticamente el robot")
            print("ASEGÚRATE de que:")
            print("- La cámara esté conectada y funcionando")
            print("- Hay una cinta visible en el campo de visión")
            print("- El robot está en una posición segura")
            confirmar = input("¿Continuar con la prueba? (s/N): ")
            
            if confirmar.lower() == 's':
                print("Iniciando corrección automática de posición...")
                try:
                    # Parámetros configurables para la prueba
                    camera_index = 0
                    max_iterations = 10
                    tolerance_mm = 1.0
                    
                    result = test_position_correction_direct(robot, camera_index, max_iterations, tolerance_mm)
                    
                    if result['success']:
                        print("✅ CORRECCIÓN COMPLETADA EXITOSAMENTE")
                        print(f"Mensaje: {result['message']}")
                        print("El robot debería estar ahora centrado en la cinta")
                    else:
                        print("❌ ERROR EN LA CORRECCIÓN")
                        print(f"Mensaje: {result['message']}")
                        print("Verifica la cámara y la visibilidad de la cinta")
                        
                except Exception as e:
                    print(f"❌ ERROR INESPERADO: {e}")
            else:
                print("Prueba cancelada")
        elif opcion == '0':
            print("Saliendo...")
            break
        else:
            print("Opción inválida")
    
    uart_manager.disconnect()

if __name__ == "__main__":
    print("CLAUDIO - Control Supervisor del Robot")
    print("=" * 50)
    
    print(f"Puerto: {RobotConfig.SERIAL_PORT}")
    print(f"Baudios: {RobotConfig.BAUD_RATE}")
    
    print("Conectando al robot...")
    
    uart = UARTManager(RobotConfig.SERIAL_PORT, RobotConfig.BAUD_RATE)
    
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