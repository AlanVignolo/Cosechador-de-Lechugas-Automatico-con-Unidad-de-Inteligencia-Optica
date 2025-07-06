import logging
import sys
import time
from controller.uart_manager import UARTManager
from controller.command_manager import CommandManager
from controller.robot_controller import RobotController
from config.robot_config import RobotConfig
from controller.robot_controller import RobotController
from controller.trajectories import TrajectoryDefinitions, get_trajectory_time_estimate

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_connection():
    """Probar conexión básica"""
    print("🔌 Probando conexión UART...")
    
    uart = UARTManager(RobotConfig.SERIAL_PORT, RobotConfig.BAUD_RATE)
    
    if not uart.connect():
        print("❌ No se pudo conectar al robot")
        return False
    
    print("✅ Conectado al robot")
    
    # Probar comando básico
    cmd_manager = CommandManager(uart)
    result = cmd_manager.emergency_stop()  # Comando seguro
    
    if result["success"]:
        print("✅ Comunicación funcionando")
        print(f"   Respuesta: {result['response']}")
    else:
        print("❌ Error en comunicación")
        print(f"   Error: {result.get('error', 'Desconocido')}")
    
    uart.disconnect()
    return result["success"]

def test_basic_movements():
    """Probar movimientos básicos"""
    print("\n🤖 Probando movimientos básicos...")
    
    uart = UARTManager(RobotConfig.SERIAL_PORT, RobotConfig.BAUD_RATE)
    if not uart.connect():
        return False
    
    cmd_manager = CommandManager(uart)
    
    # Configurar velocidades normales
    print("   Configurando velocidades...")
    result = cmd_manager.set_velocities(
        RobotConfig.NORMAL_SPEED_H, 
        RobotConfig.NORMAL_SPEED_V
    )
    print(f"   Velocidades: {result['response']}")
    
    # Movimiento pequeño de prueba
    print("   Movimiento pequeño (10mm, 10mm)...")
    result = cmd_manager.move_xy(10, 10)
    print(f"   Resultado: {result['response']}")
    
    # Probar brazo
    print("   Moviendo brazo a posición inicial...")
    result = cmd_manager.reset_arm()
    print(f"   Brazo: {result['response']}")
    
    uart.disconnect()
    return True

def enviar_movimiento_brazo(cmd_manager):
    """Función igual que en el script de pruebas"""
    print("\n" + "="*50)
    print("CONTROL DE BRAZO - MOVIMIENTO SUAVE")
    print("="*50)
    
    angle1 = input("Ángulo Servo 1 (0-180): ")
    angle2 = input("Ángulo Servo 2 (0-180): ")
    tiempo = input("Tiempo en ms (0 para instantáneo): ")
    
    result = cmd_manager.move_arm(int(angle1), int(angle2), int(tiempo))
    print(f"Respuesta: {result['response']}")

def menu_control_brazo(arm_controller):
    """Submenu simple para control del brazo por estados"""
    while True:
        status = arm_controller.get_current_state()
        
        print("\n" + "="*50)
        print("🤖 CONTROL DEL BRAZO")
        print("="*50)
        print(f"📍 Estado actual: {status['state']}")
        print(f"📐 Posición: Servo1={status['position'][0]}°, Servo2={status['position'][1]}°")
        gripper_status = arm_controller.get_gripper_real_status()
        if gripper_status["success"]:
            print(f"🔧 Gripper: {gripper_status['state']} (pos: {gripper_status['position']})")
        else:
            print(f"🔧 Gripper: {status['gripper']} (sin confirmar)")
        
        # Mostrar advertencia si está en estado desconocido
        if not status['is_known']:
            print("⚠️  Estado desconocido - la posición no coincide con ningún estado definido")
        
        print("="*50)
        print("ESTADOS DISPONIBLES:")
        
        # Mostrar TODOS los estados disponibles
        all_states = arm_controller.list_available_states()
        for i, state in enumerate(all_states, 1):
            # Marcar el estado actual
            if state == status['state']:
                print(f"  {i}. ✅ {state} (ACTUAL)")
            else:
                print(f"  {i}. ⚪ {state}")
        
        print("-"*50)
        print("r. 🔄 Redetectar estado actual")
        print("0. Volver al menú principal")
        print("-"*50)
        
        opcion = input("Selecciona estado (número): ").strip()
        
        if opcion == '0':
            break
        elif opcion == 'r':
            print("🔄 Redetectando estado actual...")
            arm_controller._detect_initial_state()
            print(f"✅ Estado redetectado: {arm_controller.current_state}")
        elif opcion.isdigit():
            state_index = int(opcion) - 1
            if 0 <= state_index < len(all_states):
                target_state = all_states[state_index]
                
                if target_state == status['state']:
                    print(f"✅ Ya estás en el estado '{target_state}'")
                else:
                    print(f"🎯 Intentando ir al estado: {target_state}")
                    result = arm_controller.change_state(target_state)
                    
                    if result["success"]:
                        print(f"✅ {result['message']}")
                    else:
                        print(f"❌ No se puede ir a '{target_state}': {result['message']}")
            else:
                print("❌ Número inválido")
        else:
            print("❌ Opción inválida")

        input("\n📱 Presiona Enter para continuar...")

def menu_interactivo(uart_manager):
    """Menú que usa una conexión UART ya establecida"""
    cmd_manager = CommandManager(uart_manager)
    robot = RobotController(cmd_manager)  # ⭐ CREAR UNA SOLA VEZ AL PRINCIPIO
    
    while True:
        print("\n" + "="*50)
        print("CONTROL DE ROBOT - MENÚ PRINCIPAL")
        print("="*50)
        print("1. Mover a posición X,Y")
        print("2. Mover brazos (suave)")
        print("3. Mover servo individual")
        print("4. Resetear brazos a 90°")
        print("5. 🏠 HOMING")
        print("6. Control Gripper")
        print("7. PARADA DE EMERGENCIA")
        print("8. Estado del robot")
        print("9. 🤖 CONTROL DE BRAZO POR ESTADOS")
        print("0. Salir")
        print("-"*50)
        opcion = input("Selecciona opción: ")

        if opcion == '1':
            x = input("Posición X (mm): ")
            y = input("Posición Y (mm): ")
            result = cmd_manager.move_xy(float(x), float(y))
            print(f"Respuesta: {result['response']}")
            
        elif opcion == '2':
            enviar_movimiento_brazo(cmd_manager)
            
        elif opcion == '3':
            servo = input("Número de servo (1 o 2): ")
            angulo = input("Ángulo (0-180): ")
            result = cmd_manager.move_servo(int(servo), int(angulo))
            print(f"Respuesta: {result['response']}")
            
        elif opcion == '4':
            result = cmd_manager.reset_arm()
            print(f"Respuesta: {result['response']}")
            
        elif opcion == '5':
            print("🏠 MENÚ DE CALIBRACIÓN")
            print("1. Homing normal")
            print("2. 🔧 Calibración completa del workspace")
            calib_opt = input("Opción: ")
            
            if calib_opt == '1':
                # ⭐ HOMING NORMAL EXISTENTE
                print("🏠 INICIANDO SECUENCIA DE HOMING")
                print("⚠️  ASEGÚRATE DE QUE EL ROBOT TENGA ESPACIO LIBRE")
                confirmar = input("¿Continuar? (s/N): ")
                
                if confirmar.lower() == 's':
                    result = robot.home_robot()
                    
                    if result["success"]:
                        print("✅ HOMING COMPLETADO")
                        print(f"   Posición actual: {result.get('position', 'N/A')}")
                    else:
                        print("❌ ERROR EN HOMING")
                        print(f"   {result['message']}")
                else:
                    print("Homing cancelado")
                    
            elif calib_opt == '2':
                print("🔧 INICIANDO CALIBRACIÓN COMPLETA DEL WORKSPACE")
                print("⚠️  Esto tomará varios minutos y medirá todo el área de trabajo")
                confirmar = input("¿Continuar? (s/N): ")
                
                if confirmar.lower() == 's':
                    result = robot.calibrate_workspace()
                    if result["success"]:
                        print("✅ CALIBRACIÓN COMPLETADA")
                        print(f"📊 Medidas: {result['measurements']}")
                    else:
                        print("❌ ERROR EN CALIBRACIÓN")
                        print(f"   {result['message']}")
                else:
                    print("Calibración cancelada")
            else:
                print("❌ Opción inválida")
            
        elif opcion == '6':
            print("\nControl de Gripper:")
            print("1. 🔄 Accionar Gripper (abre si está cerrado, cierra si está abierto)")
            print("2. 📊 Consultar estado")
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
            status = robot.get_status()  # ⭐ USAR LA INSTANCIA YA CREADA
            print(f"📊 Estado del robot:")
            print(f"   Homed: {'✅' if status['homed'] else '❌'}")
            print(f"   Posición: X={status['position']['x']}mm, Y={status['position']['y']}mm")
            print(f"   Brazo: {status['arm']}")
            print(f"   Gripper: {status['gripper']}")
            
        elif opcion == '9':
            menu_control_brazo(robot.arm)  # ⭐ USAR LA INSTANCIA YA CREADA
            
        elif opcion == '0':
            print("Saliendo...")
            break
        else:
            print("Opción inválida")
    
    uart.disconnect()

if __name__ == "__main__":
    print("🚀 CLAUDIO - Control Supervisor del Robot")
    print("=" * 50)
    
    # Verificar configuración
    print(f"Puerto: {RobotConfig.SERIAL_PORT}")
    print(f"Baudios: {RobotConfig.BAUD_RATE}")
    
    print("🔌 Conectando al robot...")
    
    # UNA SOLA conexión para todo
    uart = UARTManager(RobotConfig.SERIAL_PORT, RobotConfig.BAUD_RATE)
    
    if uart.connect():
        print("✅ Conectado al robot")
        
        # Test rápido
        cmd_manager = CommandManager(uart)
        result = cmd_manager.emergency_stop()
        if result["success"]:
            print("✅ Comunicación OK")
        
        # Ir directo al menú (sin desconectar)
        menu_interactivo(uart)
        
        uart.disconnect()
    else:
        print("❌ No se pudo conectar")