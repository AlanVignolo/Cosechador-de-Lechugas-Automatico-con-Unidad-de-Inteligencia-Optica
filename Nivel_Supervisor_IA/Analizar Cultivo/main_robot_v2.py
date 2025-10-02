#!/usr/bin/env python3
"""
main_robot.py - SOLO PARA PRUEBAS INTERACTIVAS
Menú principal del sistema de control del robot CLAUDIO.
"""

import os
import sys
import time
import logging
from typing import Optional

# Importar componentes del sistema
from controller.uart_manager import UARTManager
from controller.command_manager import CommandManager
from controller.robot_controller import RobotController
from controller.arm_controller import ArmController
from config.robot_config import RobotConfig
from camera_manager import get_camera_manager

# Configurar paths para módulos de IA
BASE_DIR = os.path.dirname(__file__)
IA_BASE_DIR = os.path.join(os.path.dirname(BASE_DIR), 'Nivel_Supervisor_IA')
CORRECCION_H_DIR = os.path.join(IA_BASE_DIR, 'Correccion Posicion Horizontal')
CORRECCION_V_DIR = os.path.join(IA_BASE_DIR, 'Correccion Posicion Vertical')
ANALIZAR_DIR = os.path.join(IA_BASE_DIR, 'Analizar Cultivo')
ESCANER_H_DIR = os.path.join(IA_BASE_DIR, 'Escaner Horizontal')
ESCANER_V_DIR = os.path.join(IA_BASE_DIR, 'Escaner Vertical')

# Agregar directorios al path
for dir_path in [CORRECCION_H_DIR, CORRECCION_V_DIR, ANALIZAR_DIR, ESCANER_H_DIR, ESCANER_V_DIR]:
    if dir_path not in sys.path:
        sys.path.append(dir_path)

# Intentar importar módulos de IA
AI_MODULES_AVAILABLE = False
try:
    from test_horizontal import test_correction as test_horizontal_correction
    from test_vertical import test_correction as test_vertical_correction
    from escaner_standalone import scan_horizontal_with_live_camera
    from escaner_vertical import scan_vertical_manual
    AI_MODULES_AVAILABLE = True
    print("✓ Módulos de IA cargados correctamente")
except ImportError as e:
    print(f"⚠ Advertencia: No se pudieron cargar módulos de IA: {e}")
    print("  Las funciones de IA no estarán disponibles")

# Intentar importar módulos de clasificación
CLASIFICACION_AVAILABLE = False
try:
    # Módulo para entrenar
    sys.path.append(ANALIZAR_DIR)
    from Estadistica import main as entrenar_estadistica
    
    # Módulo para clasificar
    from clasificar import clasificar_imagen
    
    CLASIFICACION_AVAILABLE = True
    print("✓ Módulos de clasificación cargados correctamente")
except ImportError as e:
    print(f"⚠ Advertencia: No se pudieron cargar módulos de clasificación: {e}")
    print("  Las funciones de clasificación no estarán disponibles")


def enviar_movimiento_brazo(cmd_manager):
    """Submenu para controlar brazo con trayectorias"""
    print("\n" + "="*60)
    print("CONTROL DE BRAZO - TRAYECTORIAS")
    print("="*60)
    print("Ingresa los valores para cada servo (10-160 grados)")
    print("Tiempo de movimiento: define la velocidad (ms)")
    print("-"*60)
    
    try:
        servo1 = int(input("Ángulo Servo 1 (10-160): "))
        servo2 = int(input("Ángulo Servo 2 (10-160): "))
        tiempo_ms = int(input("Tiempo de movimiento (ms, ej: 2000): "))
        
        if not (10 <= servo1 <= 160 and 10 <= servo2 <= 160):
            print("Error: Los ángulos deben estar entre 10 y 160 grados")
            return
            
        if tiempo_ms < 100:
            print("Error: El tiempo debe ser mayor a 100ms")
            return
        
        print(f"\nEnviando: Servo1={servo1}°, Servo2={servo2}°, Tiempo={tiempo_ms}ms")
        result = cmd_manager.move_arm(servo1, servo2, tiempo_ms)
        print(f"Respuesta: {result['response']}")
        
    except ValueError:
        print("Error: Entrada inválida. Usa números enteros.")
    except Exception as e:
        print(f"Error: {e}")


def menu_brazo_avanzado(arm_controller: ArmController):
    """Menu para control avanzado del brazo con estados"""
    while True:
        print("\n" + "="*60)
        print("CONTROL AVANZADO DEL BRAZO")
        print("="*60)
        
        status = arm_controller.get_status()
        all_states = arm_controller.get_all_states()
        
        print(f"Estado actual del brazo: {status['state']}")
        print(f"Servo 1: {status['arm']['servo1']}°")
        print(f"Servo 2: {status['arm']['servo2']}°")
        print("-"*60)
        print("Estados disponibles:")
        
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
                        time.sleep(0.5)
                        arm_controller._detect_initial_state()
                        print("✅ Estado actualizado")
                        time.sleep(1)
                    else:
                        print(f"No se puede ir a '{target_state}': {result['message']}")
            else:
                print("Número inválido")
        else:
            print("Opción inválida")


def menu_clasificacion(robot: RobotController):
    """Menú para funciones de clasificación de lechugas"""
    if not CLASIFICACION_AVAILABLE:
        print("\n❌ Los módulos de clasificación no están disponibles")
        print("Verifica que existan los archivos:")
        print(f"  - {os.path.join(ANALIZAR_DIR, 'Estadistica.py')}")
        print(f"  - {os.path.join(ANALIZAR_DIR, 'clasificar.py')}")
        print(f"  - {os.path.join(ANALIZAR_DIR, 'ContornosBienFiltrados.py')}")
        input("\nPresiona Enter para continuar...")
        return
    
    while True:
        print("\n" + "="*60)
        print("MÓDULO DE CLASIFICACIÓN DE LECHUGAS")
        print("="*60)
        print("1. Entrenar base de datos")
        print("2. Clasificar lechuga (tomar foto)")
        print("0. Volver al menú principal")
        print("-"*60)
        
        opcion = input("Selecciona opción (0-2): ").strip()
        
        if opcion == '0':
            break
            
        elif opcion == '1':
            print("\n" + "="*60)
            print("ENTRENAMIENTO DE BASE DE DATOS")
            print("="*60)
            print("Este proceso ejecutará Estadistica.py que internamente")
            print("llamará a ContornosBienFiltrados.py para analizar imágenes")
            print("-"*60)
            
            confirmar = input("¿Deseas continuar con el entrenamiento? (s/n): ").strip().lower()
            
            if confirmar == 's':
                print("\n🔄 Iniciando entrenamiento...")
                try:
                    # Llamar al módulo Estadistica.py
                    entrenar_estadistica()
                    print("\n✅ Entrenamiento completado exitosamente")
                except Exception as e:
                    print(f"\n❌ Error durante el entrenamiento: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Entrenamiento cancelado")
            
            input("\nPresiona Enter para continuar...")
            
        elif opcion == '2':
            print("\n" + "="*60)
            print("CLASIFICACIÓN DE LECHUGA")
            print("="*60)
            print("Se tomará una foto con la cámara y se clasificará")
            print("-"*60)
            
            confirmar = input("¿Deseas tomar la foto y clasificar? (s/n): ").strip().lower()
            
            if confirmar == 's':
                print("\n📷 Capturando imagen...")
                
                try:
                    # Obtener el gestor de cámara
                    camera_mgr = get_camera_manager() #Configurar la cámara como el archivo con el que se sacaron las fotos
                    
                    # Intentar inicializar la cámara si no está lista
                    if not camera_mgr.is_camera_ready():
                        print("Inicializando cámara...")
                        camera_mgr.initialize_camera()
                    
                    # Capturar imagen
                    frame = camera_mgr.capture_frame()
                    
                    if frame is None:
                        print("❌ No se pudo capturar la imagen de la cámara")
                        input("\nPresiona Enter para continuar...")
                        continue
                    
                    # Guardar imagen temporalmente
                    temp_image_path = os.path.join(ANALIZAR_DIR, 'temp_clasificacion.jpg')
                    import cv2
                    cv2.imwrite(temp_image_path, frame)
                    print(f"✓ Imagen guardada en: {temp_image_path}")
                    
                    # Clasificar la imagen
                    print("\n🔄 Clasificando imagen...")
                    resultado = clasificar_imagen(temp_image_path)
                    
                    # Mostrar resultado
                    print("\n" + "="*60)
                    print("RESULTADO DE LA CLASIFICACIÓN")
                    print("="*60)
                    print(f"Clase predicha: {resultado['clase']}")
                    print(f"Confianza: {resultado['confianza']:.2%}")
                    
                    if 'probabilidades' in resultado:
                        print("\nProbabilidades por clase:")
                        for clase, prob in resultado['probabilidades'].items():
                            print(f"  - {clase}: {prob:.2%}")
                    
                    print("="*60)
                    
                    # Limpiar imagen temporal (opcional)
                    # os.remove(temp_image_path)
                    
                except Exception as e:
                    print(f"\n❌ Error durante la clasificación: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Clasificación cancelada")
            
            input("\nPresiona Enter para continuar...")
            
        else:
            print("Opción inválida")


def test_position_correction_direct(robot, camera_index=0, max_iterations=10, tolerance_mm=1.0):
    """Función para probar corrección de posición con IA"""
    if not AI_MODULES_AVAILABLE:
        return {"success": False, "error": "Módulos de IA no disponibles"}
    
    print("\n" + "="*60)
    print("PRUEBA DE CORRECCIÓN DE POSICIÓN CON IA")
    print("="*60)
    
    # Prueba corrección horizontal
    print("\n1️⃣  CORRECCIÓN HORIZONTAL")
    print("-"*60)
    result_h = test_horizontal_correction(
        robot=robot,
        camera_index=camera_index,
        max_iterations=max_iterations,
        tolerance_mm=tolerance_mm
    )
    
    if result_h["success"]:
        print(f"✅ Corrección horizontal exitosa")
        print(f"   Iteraciones: {result_h.get('iterations', 'N/A')}")
        print(f"   Error final: {result_h.get('final_error_mm', 'N/A'):.2f} mm")
    else:
        print(f"❌ Corrección horizontal falló: {result_h.get('error', 'Error desconocido')}")
    
    time.sleep(1)
    
    # Prueba corrección vertical
    print("\n2️⃣  CORRECCIÓN VERTICAL")
    print("-"*60)
    result_v = test_vertical_correction(
        robot=robot,
        camera_index=camera_index,
        max_iterations=max_iterations,
        tolerance_mm=tolerance_mm
    )
    
    if result_v["success"]:
        print(f"✅ Corrección vertical exitosa")
        print(f"   Iteraciones: {result_v.get('iterations', 'N/A')}")
        print(f"   Error final: {result_v.get('final_error_mm', 'N/A'):.2f} mm")
    else:
        print(f"❌ Corrección vertical falló: {result_v.get('error', 'Error desconocido')}")
    
    # Resultado general
    success = result_h["success"] and result_v["success"]
    
    print("\n" + "="*60)
    if success:
        print("✅ CORRECCIÓN COMPLETA EXITOSA")
    else:
        print("❌ CORRECCIÓN COMPLETA FALLÓ")
    print("="*60)
    
    return {
        "success": success,
        "horizontal": result_h,
        "vertical": result_v
    }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("CLAUDIO - Sistema de Control del Robot Cosechador")
    print("="*60)
    
    # Autodetectar plataforma y configurar puerto
    RobotConfig.auto_detect_platform()
    serial_port = RobotConfig.get_serial_port()
    
    print(f"Puerto serial: {serial_port}")
    print(f"Baudios: {RobotConfig.BAUD_RATE}")
    print("-"*60)
    
    # Inicializar gestor de cámara
    try:
        camera_mgr = get_camera_manager()
        camera_mgr.initialize_camera()
        print("✓ Cámara inicializada")
    except Exception as e:
        print(f"⚠ Advertencia: No se pudo inicializar la cámara: {e}")
    
    # Conectar al robot
    uart = UARTManager(serial_port, RobotConfig.BAUD_RATE)
    if not uart.connect():
        print("❌ No se pudo conectar al robot")
        print("Verifica el puerto serial y la conexión")
        return
    
    print("✓ Conexión establecida con el robot")
    
    try:
        cmd_manager = CommandManager(uart)
        robot = RobotController(cmd_manager)
        arm_controller = ArmController(cmd_manager)
        
        # Variable para toggle de lechuga
        lettuce_on = False
        
        while True:
            print("\n" + "="*60)
            print("MENÚ PRINCIPAL - ROBOT CLAUDIO")
            print("="*60)
            
            status = robot.get_status()
            print(f"Estado: {'Homed ✓' if status['homed'] else 'Sin Homing ✗'}")
            print(f"Posición: X={status['position']['x']:.1f}mm, Y={status['position']['y']:.1f}mm")
            print(f"Estado Lechuga: {'CON lechuga' if lettuce_on else 'SIN lechuga'}")
            
            print("-"*60)
            print("1.  Mover a posición XY")
            print("2.  Mover brazo (trayectoria)")
            print("3.  Mover servo individual")
            print("4.  Consultar progreso de movimiento")
            print("5.  Calibración y Homing")
            print("6.  Control de Gripper")
            print("7.  Parada de emergencia")
            print("8.  Consultar estado completo")
            print("9.  Menú avanzado del brazo")
            print("10. Prueba corrección IA (Horizontal + Vertical)")
            print(f"11. Toggle Lechuga {'ON' if lettuce_on else 'OFF'}")
            print("12. Escaneado horizontal con cámara en vivo")
            print("13. Escaneado vertical manual (flags por usuario)")
            print("14. Clasificar lechugas (IA)")  # 🆕 NUEVA OPCIÓN
            print("-"*60)
            print("0.  Salir")
            print("-"*60)
            
            opcion = input("Selecciona opción (0-14): ").strip()
            
            if opcion == '0':
                print("Saliendo del sistema...")
                break
                
            elif opcion == '1':
                x = input("Posición X (mm) [Enter mantiene actual]: ").strip()
                y = input("Posición Y (mm) [Enter mantiene actual]: ").strip()
                try:
                    curr_x = status['position']['x']
                    curr_y = status['position']['y']
                    x_val = curr_x if x == "" else float(x)
                    y_val = curr_y if y == "" else float(y)
                    result = cmd_manager.move_xy(x_val, y_val)
                    print(f"Respuesta: {result['response']}")
                except ValueError:
                    print("Entrada inválida. Usa números (ej. 120 o 120.5).")
                    
            elif opcion == '2':
                enviar_movimiento_brazo(cmd_manager)
                
            elif opcion == '3':
                servo = input("Número de servo (1 o 2): ")
                angulo = input("Ángulo (10-160): ")
                result = cmd_manager.move_servo(int(servo), int(angulo))
                print(f"Respuesta: {result['response']}")
                
            elif opcion == '4':
                result = cmd_manager.get_movement_progress()
                if result["success"]:
                    print("Snapshot solicitado...")
                else:
                    print(f"Error: {result.get('error', 'Error desconocido')}")
                    
            elif opcion == '5':
                print("\nMENÚ DE CALIBRACIÓN")
                print("1. Homing normal")
                print("2. Calibración completa del workspace")
                calib_opt = input("Opción: ").strip()
                
                if calib_opt == '1':
                    print("\n🏠 INICIANDO HOMING")
                    confirmar = input("¿Continuar? (s/n): ").strip().lower()
                    if confirmar == 's':
                        result = cmd_manager.home()
                        print(f"Respuesta: {result['response']}")
                elif calib_opt == '2':
                    print("\n📐 CALIBRACIÓN COMPLETA DEL WORKSPACE")
                    confirmar = input("¿Continuar? (s/n): ").strip().lower()
                    if confirmar == 's':
                        result = cmd_manager.calibrate_workspace()
                        print(f"Respuesta: {result['response']}")
                        
            elif opcion == '6':
                print("\nCONTROL DE GRIPPER")
                print("1. Abrir gripper")
                print("2. Cerrar gripper")
                gripper_opt = input("Opción: ").strip()
                
                if gripper_opt == '1':
                    result = cmd_manager.gripper_open()
                    print(f"Respuesta: {result['response']}")
                elif gripper_opt == '2':
                    result = cmd_manager.gripper_close()
                    print(f"Respuesta: {result['response']}")
                    
            elif opcion == '7':
                print("\n⚠️  PARADA DE EMERGENCIA")
                confirmar = input("¿Confirmas la parada de emergencia? (s/n): ").strip().lower()
                if confirmar == 's':
                    result = cmd_manager.emergency_stop()
                    print(f"Respuesta: {result['response']}")
                    
            elif opcion == '8':
                print("\n📊 ESTADO COMPLETO DEL SISTEMA")
                print(f"Homed: {status['homed']}")
                print(f"Posición X: {status['position']['x']:.2f} mm")
                print(f"Posición Y: {status['position']['y']:.2f} mm")
                print(f"Brazo - Servo1: {status['arm']['servo1']}°")
                print(f"Brazo - Servo2: {status['arm']['servo2']}°")
                print(f"Gripper: {status['gripper']}")
                
            elif opcion == '9':
                menu_brazo_avanzado(arm_controller)
                
            elif opcion == '10':
                if AI_MODULES_AVAILABLE:
                    test_position_correction_direct(robot)
                else:
                    print("\n❌ Módulos de IA no disponibles")
                input("\nPresiona Enter para continuar...")
                
            elif opcion == '11':
                lettuce_on = not lettuce_on
                print(f"\n🥬 Estado de lechuga: {'CON lechuga' if lettuce_on else 'SIN lechuga'}")
                
            elif opcion == '12':
                if AI_MODULES_AVAILABLE:
                    print("\n📷 ESCANEADO HORIZONTAL")
                    scan_horizontal_with_live_camera(robot)
                else:
                    print("\n❌ Módulos de IA no disponibles")
                input("\nPresiona Enter para continuar...")
                
            elif opcion == '13':
                if AI_MODULES_AVAILABLE:
                    print("\n📷 ESCANEADO VERTICAL MANUAL")
                    scan_vertical_manual(robot)
                else:
                    print("\n❌ Módulos de IA no disponibles")
                input("\nPresiona Enter para continuar...")
            
            elif opcion == '14':  # 🆕 NUEVA OPCIÓN
                menu_clasificacion(robot)
                
            else:
                print("Opción inválida")
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupción detectada")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔌 Desconectando...")
        uart.disconnect()
        try:
            camera_mgr.release_camera()
        except:
            pass
        print("✓ Sistema cerrado correctamente")


if __name__ == "__main__":
    main()