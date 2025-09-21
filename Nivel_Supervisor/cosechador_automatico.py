#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COSECHADOR AUTOMÁTICO CLAUDIO
==============================

Sistema automatizado completo para cosecha de lechugas
Incluye máquina de estados, mapeo de cultivos y ciclos de cosecha

Autor: Sistema CLAUDIO
Fecha: 2025-09-21
"""

import logging
import sys
import os
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Agregar paths para importaciones
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Importar componentes del sistema
try:
    from controller.robot_controller import RobotController
    from controller.command_manager import CommandManager
    from controller.uart_manager import UARTManager
    from controller.robot_state_machine import RobotStateMachine
    from config.robot_config import RobotConfig
    from camera_manager import get_camera_manager
    print("✅ Todos los módulos del sistema importados correctamente")
except ImportError as e:
    print(f"❌ Error importando módulos del sistema: {e}")
    print("Verificar que todos los archivos estén en su lugar")
    sys.exit(1)

def mostrar_banner():
    """Mostrar banner de bienvenida del cosechador automático"""
    print("\n" + "="*80)
    print("🤖 COSECHADOR AUTOMÁTICO CLAUDIO v1.0")
    print("="*80)
    print("Sistema de cosecha automatizada de lechugas")
    print("Desarrollado para el Proyecto Final de Ingeniería")
    print(f"Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

def mostrar_menu_principal():
    """Mostrar menú principal del cosechador automático"""
    print("\n" + "="*60)
    print("📋 MENÚ PRINCIPAL - COSECHADOR AUTOMÁTICO")
    print("="*60)
    print("1. 🚀 INICIO TOTAL (primera vez)")
    print("   └─ Homing + Mapeo Completo + Cosecha")
    print("")
    print("2. 🔄 ESCÁNER DIARIO (uso diario)")
    print("   └─ Solo ciclo de cosecha con mapeo existente")
    print("")
    print("3. 📊 DATOS DEL SISTEMA (diagnóstico)")
    print("   └─ Estado completo: hardware, configuración, estadísticas")
    print("")
    print("4. ⚙️ CONFIGURACIÓN AVANZADA")
    print("   └─ Ajustes del sistema y parámetros")
    print("")
    print("0. ❌ SALIR")
    print("="*60)

def menu_configuracion_avanzada(state_machine):
    """Menú de configuración avanzada"""
    while True:
        print("\n" + "="*50)
        print("⚙️ CONFIGURACIÓN AVANZADA")
        print("="*50)
        print("1. 🏠 Solo Homing")
        print("2. 🌿 Solo Mapeo de Cultivo")
        print("3. 🛠️ Solo Mapeo de Recursos")
        print("4. 🔧 Reiniciar Configuración")
        print("5. 📋 Ver Estado de la Máquina")
        print("0. ← Volver al menú principal")
        print("-"*50)
        
        opcion = input("Opción: ").strip()
        
        if opcion == '1':
            print("\n🏠 EJECUTANDO SOLO HOMING...")
            try:
                success = state_machine._execute_homing()
                if success:
                    print("✅ Homing completado")
                else:
                    print("❌ Error en homing")
            except Exception as e:
                print(f"❌ Error: {e}")
                
        elif opcion == '2':
            print("\n🌿 EJECUTANDO SOLO MAPEO DE CULTIVO...")
            try:
                success = state_machine._execute_mapeo_cultivo()
                if success:
                    print("✅ Mapeo de cultivo completado")
                else:
                    print("❌ Error en mapeo de cultivo")
            except Exception as e:
                print(f"❌ Error: {e}")
                
        elif opcion == '3':
            print("\n🛠️ EJECUTANDO SOLO MAPEO DE RECURSOS...")
            try:
                success = state_machine._execute_mapeo_recursos()
                if success:
                    print("✅ Mapeo de recursos completado")
                else:
                    print("❌ Error en mapeo de recursos")
            except Exception as e:
                print(f"❌ Error: {e}")
                
        elif opcion == '4':
            print("\n🔧 REINICIANDO CONFIGURACIÓN...")
            confirmar = input("¿Estás seguro? Esto borrará todos los datos (s/N): ")
            if confirmar.lower() == 's':
                try:
                    # Reiniciar estadísticas
                    state_machine.statistics.reset_totals()
                    # Limpiar recursos
                    state_machine.resources.plantines = None
                    state_machine.resources.cesto = None
                    state_machine._save_state_data()
                    print("✅ Configuración reiniciada")
                except Exception as e:
                    print(f"❌ Error: {e}")
            else:
                print("Operación cancelada")
                
        elif opcion == '5':
            print("\n📋 ESTADO DE LA MÁQUINA:")
            status = state_machine.get_status()
            print(f"Estado actual: {status['current_state']}")
            print(f"Operación activa: {status['operation_active']}")
            print(f"Robot homed: {status['robot_status']['homed']}")
            print(f"Recursos mapeados: {status['resources']['all_mapped']}")
            
        elif opcion == '0':
            break
        else:
            print("❌ Opción inválida")

def inicializar_sistema():
    """Inicializar el sistema del robot"""
    print("\n🔧 INICIALIZANDO SISTEMA...")
    
    # Inicializar gestor de cámara
    print("📷 Inicializando cámara...")
    try:
        camera_mgr = get_camera_manager()
        if camera_mgr.initialize_camera():
            print("✅ Cámara inicializada")
        else:
            print("⚠️ Advertencia: Cámara no disponible")
    except Exception as e:
        print(f"⚠️ Error con cámara: {e}")
    
    # Detectar plataforma y configurar puerto
    detected_platform = RobotConfig.auto_detect_platform()
    serial_port = RobotConfig.get_serial_port()
    
    print(f"🖥️ Plataforma: {detected_platform}")
    print(f"📡 Puerto serial: {serial_port}")
    print(f"⚡ Baudios: {RobotConfig.BAUD_RATE}")
    
    # Conectar al robot
    print("🔌 Conectando al robot...")
    uart = UARTManager(serial_port, RobotConfig.BAUD_RATE)
    
    if not uart.connect():
        print("❌ ERROR: No se pudo conectar al robot")
        print("Verificar:")
        print("  - Cable USB conectado")
        print("  - Puerto serial correcto")
        print("  - Robot encendido")
        return None, None
    
    print("✅ Conectado al robot")
    
    # Crear controladores
    cmd_manager = CommandManager(uart)
    
    # Verificar comunicación inicial
    print("🧪 Verificando comunicación...")
    result = cmd_manager.emergency_stop()
    if not result["success"]:
        print("❌ ERROR: Fallo en comunicación inicial")
        uart.disconnect()
        return None, None
    
    print("✅ Comunicación verificada")
    
    # Crear controlador del robot
    robot = RobotController(cmd_manager)
    print("✅ Sistema inicializado correctamente")
    
    return uart, robot

def main():
    """Función principal del cosechador automático"""
    mostrar_banner()
    
    # Inicializar sistema
    uart, robot = inicializar_sistema()
    if uart is None or robot is None:
        print("\n❌ FALLO EN INICIALIZACIÓN - ABORTANDO")
        return
    
    # Crear máquina de estados
    print("🔄 Creando máquina de estados...")
    try:
        state_machine = RobotStateMachine(robot)
        print("✅ Máquina de estados lista")
    except Exception as e:
        print(f"❌ Error creando máquina de estados: {e}")
        uart.disconnect()
        return
    
    # Menú principal
    try:
        while True:
            mostrar_menu_principal()
            opcion = input("\n👉 Selecciona opción (0-4): ").strip()
            
            if opcion == '1':
                print("\n" + "🚀"*20)
                print("INICIANDO SECUENCIA COMPLETA")
                print("🚀"*20)
                print("Esta operación puede tomar varios minutos...")
                print("Presiona Ctrl+C para interrumpir si es necesario")
                
                try:
                    success = state_machine.inicio_total()
                    if success:
                        print("\n" + "✅"*20)
                        print("INICIO TOTAL COMPLETADO EXITOSAMENTE")
                        print("✅"*20)
                    else:
                        print("\n" + "❌"*20)
                        print("INICIO TOTAL FALLÓ")
                        print("❌"*20)
                        
                except KeyboardInterrupt:
                    print("\n⏹️ OPERACIÓN INTERRUMPIDA POR EL USUARIO")
                    state_machine.stop_operation()
                except Exception as e:
                    print(f"\n❌ ERROR DURANTE INICIO TOTAL: {e}")
                    import traceback
                    traceback.print_exc()
                
            elif opcion == '2':
                print("\n" + "🔄"*20)
                print("INICIANDO ESCÁNER DIARIO")
                print("🔄"*20)
                
                try:
                    success = state_machine.escaner_diario()
                    if success:
                        print("\n" + "✅"*20)
                        print("ESCÁNER DIARIO COMPLETADO")
                        print("✅"*20)
                    else:
                        print("\n" + "❌"*20)
                        print("ESCÁNER DIARIO FALLÓ")
                        print("❌"*20)
                        
                except KeyboardInterrupt:
                    print("\n⏹️ OPERACIÓN INTERRUMPIDA POR EL USUARIO")
                    state_machine.stop_operation()
                except Exception as e:
                    print(f"\n❌ ERROR DURANTE ESCÁNER DIARIO: {e}")
                    import traceback
                    traceback.print_exc()
                
            elif opcion == '3':
                try:
                    state_machine.mostrar_datos()
                except Exception as e:
                    print(f"\n❌ ERROR MOSTRANDO DATOS: {e}")
                    import traceback
                    traceback.print_exc()
                
            elif opcion == '4':
                menu_configuracion_avanzada(state_machine)
                
            elif opcion == '0':
                print("\n👋 FINALIZANDO COSECHADOR AUTOMÁTICO...")
                break
                
            else:
                print("❌ Opción inválida. Use 0-4.")
            
            # Pausa antes de mostrar menú nuevamente
            if opcion != '0':
                input("\n📱 Presiona ENTER para continuar...")
    
    except KeyboardInterrupt:
        print("\n\n⏹️ INTERRUPCIÓN DE TECLADO DETECTADA")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Limpieza final
        print("\n🧹 LIBERANDO RECURSOS...")
        try:
            camera_mgr = get_camera_manager()
            camera_mgr.release_camera()
            print("✅ Cámara liberada")
        except:
            pass
        
        try:
            uart.disconnect()
            print("✅ UART desconectado")
        except:
            pass
        
        print("\n" + "="*60)
        print("🏁 COSECHADOR AUTOMÁTICO FINALIZADO")
        print(f"Hora de finalización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("¡Gracias por usar el sistema CLAUDIO!")
        print("="*60)

if __name__ == "__main__":
    main()
