import os
import sys
import time
import logging

# Importar componentes del sistema
from controller.uart_manager import UARTManager
from controller.command_manager import CommandManager
from controller.robot_controller import RobotController
from controller.workflow_orchestrator import inicio_completo, inicio_simple
from config.robot_config import RobotConfig
from camera_manager import get_camera_manager


def run_menu(robot: RobotController):
    """
    Menú de acciones automáticas (producción).
    Opciones: Inicio simple, Inicio completo.
    """
    while True:
        print("\n" + "=" * 60)
        print("ACCIONES AUTOMÁTICAS - SISTEMA CLAUDIO")
        print("=" * 60)
        status = robot.get_status()
        print(f"Estado: {'Homed' if status['homed'] else 'Sin Homing'}")
        print(f"Posición: X={status['position']['x']:.1f}mm, Y={status['position']['y']:.1f}mm")
        print("-" * 60)
        print("1. Inicio simple (ir a 0,0 -> escaneo vertical -> escaneos horizontales -> volver a 0,0)")
        print("2. Inicio completo (homing -> escaneo vertical -> escaneos horizontales -> volver a 0,0)")
        print("0. Salir")
        print("-" * 60)

        opcion = input("Selecciona opción (0-2): ").strip()

        if opcion == '1':
            print("\nINICIANDO 'INICIO SIMPLE'...")
            ok = inicio_simple(robot)
            if ok:
                print("Inicio simple finalizado correctamente")
            else:
                print("Inicio simple finalizado con errores")
        elif opcion == '2':
            print("\nINICIANDO 'INICIO COMPLETO'...")
            ok = inicio_completo(robot)
            if ok:
                print("Inicio completo finalizado correctamente")
            else:
                print("Inicio completo finalizado con errores")
        elif opcion == '0':
            print("Saliendo del menú de acciones automáticas...")
            break
        else:
            print("Opción inválida")


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("CLAUDIO - Orquestador de Flujos (Producción)")
    print("=" * 60)

    # Inicializar gestor de cámara (opcional, los módulos la manejarán con acquire/start)
    try:
        camera_mgr = get_camera_manager()
        camera_mgr.initialize_camera()
    except Exception:
        # No bloqueamos si la cámara no inicia aquí; los módulos de IA intentarán adquirirla
        pass

    # Detectar plataforma y puerto
    RobotConfig.auto_detect_platform()
    serial_port = RobotConfig.get_serial_port()
    print(f"Puerto serial: {serial_port}")
    print(f"Baudios: {RobotConfig.BAUD_RATE}")

    # Conectar UART
    uart = UARTManager(serial_port, RobotConfig.BAUD_RATE)
    if not uart.connect():
        print("No se pudo conectar al robot. Verifica el puerto y el cableado.")
        return

    try:
        cmd = CommandManager(uart)
        # Señal rápida para verificar comunicación
        cmd.emergency_stop()

        # Construir RobotController
        robot = RobotController(cmd)
        print("Sistema inicializado. Ingresando al menú...")

        run_menu(robot)

    finally:
        try:
            uart.disconnect()
        except Exception:
            pass
        try:
            camera_mgr.release_camera()
        except Exception:
            pass
        print("Recursos liberados. Bye.")


if __name__ == "__main__":
    main()
