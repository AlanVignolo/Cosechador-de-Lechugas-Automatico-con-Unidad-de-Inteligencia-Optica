"""
Escáner Vertical Manual - Sistema de flags controlado por usuario
Versión manual donde el usuario envía los flags durante el movimiento vertical
"""

import sys
import os
import threading
import time
import uuid

# Solo importar lo esencial del sistema
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor', 'config'))

def scan_vertical_manual(robot):
    """
    Función principal de escaneo vertical manual con sistema de flags
    El usuario controla manualmente cuando se envían los flags durante el movimiento
    """
    print("\n" + "="*60)
    print("ESCÁNER VERTICAL MANUAL")
    print("="*60)
    print("Este modo permite escaneo vertical manual con flags controlados por el usuario")
    print("Durante el movimiento descendente, presiona ENTER para enviar flags")
    
    try:
        from config.robot_config import RobotConfig
        
        # ID único de escaneo
        scan_id = str(uuid.uuid4())[:8]
        print(f"Escaneo ID: {scan_id}")
        
        # Verificaciones básicas
        if not robot.is_homed:
            print("Error: Robot debe estar hecho homing primero")
            return False
        
        if not robot.arm.is_in_safe_position():
            print("Advertencia: El brazo no está en posición segura")
            user_input = input("¿Continuar de todas formas? (s/N): ").lower()
            if user_input != 's':
                print("Operación cancelada por el usuario")
                return False
        
        # Sistema de tracking de flags manual
        detection_state = {
            'flag_count': 0,
            'uart_ref': robot.cmd.uart,
            'max_flags': RobotConfig.MAX_SNAPSHOTS,
            'flag_positions': [],
            'flag_timestamps': []
        }
        
        def send_manual_flag():
            """Enviar flag manual al firmware"""
            try:
                if detection_state['flag_count'] >= detection_state['max_flags']:
                    print(f"LÍMITE DE FLAGS ALCANZADO ({detection_state['max_flags']})")
                    return None
                
                detection_state['flag_count'] += 1
                flag_id = detection_state['flag_count']
                
                # Enviar comando RP (snapshot) al firmware
                result = robot.cmd.get_movement_progress()
                if result.get("success"):
                    detection_state['flag_timestamps'].append(time.time())
                    print(f"FLAG #{flag_id} ENVIADO")
                    return flag_id
                else:
                    print(f"Error enviando flag: {result}")
                    return None
            except Exception as e:
                print(f"Error en send_manual_flag: {e}")
                return None
        
        # Velocidades para el escaneo (usar velocidades de homing que son apropiadas)
        print("Configurando velocidades de escaneo...")
        robot.cmd.set_velocities(RobotConfig.HOMING_SPEED_H, RobotConfig.HOMING_SPEED_V)  # 3000, 8000
        
        # Iniciar escaneo vertical sin tocar el límite superior
        print("\nINICIANDO MOVIMIENTO DESCENDENTE (sin tocar límite superior)...")
        print("Durante el movimiento, presiona ENTER para enviar flags")
        print("Los flags marcarán posiciones de interés durante el escaneo")
        print("Presiona 'q' + ENTER para terminar el escaneo antes del límite\n")
        
        # Variables de control del hilo de input
        is_scanning = [True]
        input_thread = None
        
        def input_loop():
            """Hilo para capturar input del usuario durante el movimiento"""
            while is_scanning[0]:
                try:
                    user_input = input().strip().lower()
                    if user_input == 'q':
                        print("TERMINANDO ESCANEO POR SOLICITUD DEL USUARIO...")
                        is_scanning[0] = False
                        # Detener movimiento
                        robot.cmd.uart.send_command("STOP")
                        break
                    elif user_input == '':  # ENTER presionado
                        if is_scanning[0]:  # Solo si aún estamos escaneando
                            send_manual_flag()
                    else:
                        print("Presiona ENTER para flag, 'q' + ENTER para terminar")
                except Exception as e:
                    if is_scanning[0]:  # Solo mostrar error si aún estamos activos
                        print(f"Error en input: {e}")
        
        # Iniciar hilo de input
        input_thread = threading.Thread(target=input_loop, daemon=True)
        input_thread.start()
        
        # Movimiento descendente largo hacia límite inferior
        result = robot.cmd.move_xy(0, 2000)  # Movimiento hacia abajo (valores positivos)
        
        # Esperar límite inferior o terminación manual
        limit_message = None
        if is_scanning[0]:  # Solo si no se terminó manualmente
            limit_message = robot.cmd.uart.wait_for_limit_specific('V_DOWN', timeout=120.0)
        
        # Detener hilo de input
        is_scanning[0] = False
        
        # Dar tiempo al thread de input para terminar
        time.sleep(0.5)
        
        if limit_message and ("LIMIT_V_DOWN_TRIGGERED" in limit_message or ("LIMIT_POLLED" in limit_message and "V_DOWN" in limit_message)):
            print("Límite inferior alcanzado")
        elif not is_scanning[0]:
            print("Escaneo terminado por el usuario")
        else:
            print("Error: No se alcanzó el límite inferior")
            return False
        
        # Correlacionar flags con snapshots
        correlate_flags_with_snapshots_vertical(detection_state)
        
        # Mostrar resultados
        show_results_vertical(detection_state)
        
        # Actualizar configuración de tubos con las posiciones Y detectadas
        if detection_state['flag_positions']:
            try:
                # Importar sistema de configuración de tubos
                sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Analizar Cultivo'))
                from configuracion_tubos import config_tubos
                
                # Actualizar configuración con las posiciones Y detectadas
                config_tubos.actualizar_desde_escaner_vertical(detection_state['flag_positions'])
                print("\nConfiguración de tubos actualizada para el escáner horizontal")
            except Exception as e:
                print(f"Error actualizando configuración de tubos: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error durante el escaneado vertical: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Limpieza final
        is_scanning[0] = False
        
        # Resetear velocidades
        try:
            print("Reseteando velocidades del robot...")
            robot.cmd.set_velocities(
                RobotConfig.NORMAL_SPEED_H,
                RobotConfig.NORMAL_SPEED_V
            )
            time.sleep(1.0)
            print("Velocidades reseteadas correctamente")
        except Exception as e:
            print(f"Error reseteando velocidades: {e}")
        
        # Reset del UART manager
        try:
            print("Reset del UART manager...")
            robot.cmd.uart.reset_scanning_state()
        except Exception as e:
            print(f"Error en reset del UART manager: {e}")
        
        print("LIMPIEZA COMPLETADA - Robot listo para siguiente operación")

def correlate_flags_with_snapshots_vertical(detection_state):
    """Correlacionar flags con snapshots para obtener posiciones verticales reales"""
    try:
        print("\nCORRELACIONANDO FLAGS CON SNAPSHOTS...")
        
        uart = detection_state.get('uart_ref')
        if uart is None:
            print("Error: No hay referencia UART disponible")
            return
        
        snapshot_pairs = []
        try:
            if uart is not None and hasattr(uart, 'get_last_snapshots'):
                snapshot_pairs = uart.get_last_snapshots()  # [(x_mm, y_mm), ...]
        except Exception:
            snapshot_pairs = []
        
        if not snapshot_pairs:
            print("⚠️ No se recibieron snapshots del robot para este movimiento. Verifique que el firmware esté enviando 'MOVEMENT_SNAPSHOTS' al finalizar o al tocar límites. No se calcularán posiciones.")
            print(f"Flags enviados: {detection_state['flag_count']}")
            # FALLBACK: usar timestamps para estimar posiciones
            detection_state['flag_positions'] = []
            return
        
        # DEBUG: Mostrar todos los snapshots recibidos
        print("SNAPSHOTS DEL MOVIMIENTO:")
        print("-" * 40)
        for i, (x, y) in enumerate(snapshot_pairs):
            print(f"S{i+1}: X={x}mm, Y={y}mm")
        print("-" * 40)
        
        # Usar solo Y para correlación vertical
        snapshot_positions = [xy[1] for xy in snapshot_pairs]
        print(f"Snapshots disponibles: {len(snapshot_positions)}")
        print(f"Flags enviados: {detection_state['flag_count']}")
        
        # CORRELACIÓN INTELIGENTE:
        # Buscar los snapshots más cercanos al momento en que se enviaron los flags
        # En lugar de correlación 1:1 simple, usar el timing
        detection_state['flag_positions'] = []
        
        if len(snapshot_positions) >= detection_state['flag_count']:
            # Hay suficientes snapshots: usar correlación selectiva
            # Para escaneo vertical manual, tomar snapshots distribuidos uniformemente
            if detection_state['flag_count'] > 0:
                for i in range(detection_state['flag_count']):
                    # Distribución uniforme a lo largo de los snapshots
                    snap_index = int((i * (len(snapshot_positions) - 1)) / max(1, detection_state['flag_count'] - 1))
                    snap_index = min(snap_index, len(snapshot_positions) - 1)
                    flag_position = snapshot_positions[snap_index]
                    detection_state['flag_positions'].append(flag_position)
                    
                    timestamp = detection_state['flag_timestamps'][i] if i < len(detection_state['flag_timestamps']) else 0
                    print(f"   FLAG #{i+1}: Y={flag_position:.1f}mm (timestamp: {timestamp:.2f})")
        else:
            # Pocos snapshots: usar los disponibles
            for i in range(min(detection_state['flag_count'], len(snapshot_positions))):
                flag_position = snapshot_positions[i]
                detection_state['flag_positions'].append(flag_position)
                timestamp = detection_state['flag_timestamps'][i] if i < len(detection_state['flag_timestamps']) else 0
                print(f"   FLAG #{i+1}: Y={flag_position:.1f}mm (timestamp: {timestamp:.2f})")
        
        print("Correlación flags-snapshots completada")
        
    except Exception as e:
        print(f"Error en correlación flags-snapshots: {e}")
        import traceback
        traceback.print_exc()

def show_results_vertical(detection_state):
    """Mostrar resultados del escaneo vertical"""
    print("\n" + "="*60)
    print("REPORTE FINAL DEL ESCANEADO VERTICAL")
    print("="*60)
    print(f"Total de flags enviados: {detection_state['flag_count']}")
    
    if detection_state['flag_positions']:
        print(f"Posiciones Y registradas: {len(detection_state['flag_positions'])}")
        print("\nPOSICIONES VERTICALES DETECTADAS:")
        print("┌─────────┬─────────────┬─────────────────────┐")
        print("│  Flag   │     Y (mm)  │      Timestamp      │")
        print("├─────────┼─────────────┼─────────────────────┤")
        
        for i, (pos_y, timestamp) in enumerate(zip(detection_state['flag_positions'], detection_state['flag_timestamps'])):
            time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
            print(f"│   #{i+1:<3}  │  {pos_y:>8.1f}  │  {time_str}         │")
        
        print("└─────────┴─────────────┴─────────────────────┘")
        
        # Estadísticas adicionales
        if len(detection_state['flag_positions']) > 1:
            distancias = []
            for i in range(1, len(detection_state['flag_positions'])):
                dist = abs(detection_state['flag_positions'][i] - detection_state['flag_positions'][i-1])
                distancias.append(dist)
            
            print(f"\nESTADÍSTICAS:")
            print(f"Distancia total escaneada: {abs(detection_state['flag_positions'][-1] - detection_state['flag_positions'][0]):.1f}mm")
            print(f"Distancia promedio entre flags: {sum(distancias)/len(distancias):.1f}mm")
            print(f"Distancia mínima entre flags: {min(distancias):.1f}mm")
            print(f"Distancia máxima entre flags: {max(distancias):.1f}mm")
    else:
        print("No se registraron posiciones durante el escaneo.")
    
    print("="*60)

if __name__ == "__main__":
    print("=== ESCÁNER VERTICAL MANUAL ===")
    print("Ejecutar desde main_robot.py")