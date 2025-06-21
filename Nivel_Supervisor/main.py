import serial
import time
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Parámetros de la conexión serial
SERIAL_PORT = 'COM14'  # Cambiar según tu sistema (COMx en Windows)
BAUD_RATE = 115200  # Velocidad de baudios
TIMEOUT = 1.0  # segundos

# Inicializar UART
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
time.sleep(2)  # Esperar que Arduino se reinicie
ser.reset_input_buffer()

def enviar_comando(cmd):
    comando = f"<{cmd}>"  # SIN \n al final
    logging.info(f"TX >> {cmd}")
    ser.write(comando.encode('utf-8'))
    time.sleep(0.3)  # Aumentar delay un poco
    leer_respuesta()
    
def leer_respuesta():
    try:
        while ser.in_waiting:
            line = ser.readline()
            decoded = line.decode('ascii', errors='ignore').strip()
            if decoded:
                logging.info(f"RX << {decoded}")
    except Exception as e:
        logging.error(f"Error en lectura: {e}")


def menu():
    while True:
        print("\n" + "="*50)
        print("CONTROL DE ROBOT - MENÚ PRINCIPAL")
        print("="*50)
        print("1. Mover a posición X,Y")
        print("2. Hacer HOME")
        print("3. PARADA DE EMERGENCIA")
        print("4. Estado actual")
        print("5. Posición de brazo predefinida")
        print("6. Control de gripper")
        print("7. Establecer velocidad")
        print("8. Enviar trayectoria")
        print("9. Comando manual")
        print("10. Debug")
        print("11. Debug extendido")
        print("0. Salir")
        print("-"*50)
        opcion = input("Selecciona opción: ")

        if opcion == '1':
            x = input("Posición X (mm): ")
            y = input("Posición Y (mm): ")
            enviar_comando(f"M:{x},{y}")
        elif opcion == '2':
            enviar_comando("H")
        elif opcion == '3':
            enviar_comando("S")
        elif opcion == '4':
            enviar_comando("?")
        elif opcion == '5':
            pos = input("Nombre de la posición: ")
            enviar_comando(f"A:{pos}")
        elif opcion == '6':
            estado = input("Abrir o Cerrar (open/close): ")
            enviar_comando(f"G:{estado}")
        elif opcion == '7':
            vel = input("Velocidad (0-100): ")
            enviar_comando(f"V:{vel}")
        elif opcion == '8':
            tray = input("Trayectoria (ej: P1,P2,P3): ")
            enviar_comando(f"T:{tray}")
        elif opcion == '9':
            raw = input("Ingresa comando manual (sin <>): ")
            enviar_comando(raw)
        elif opcion == '10':
            enviar_comando("D")
        elif opcion == '11':
            enviar_comando("E")
        elif opcion == '0':
            print("Saliendo...")
            break
        else:
            print("Opción inválida")
            continue

        # Leer cualquier respuesta que venga después del comando
        leer_respuesta()

if __name__ == '__main__':
    try:
        menu()
    except KeyboardInterrupt:
        print("\nPrograma terminado por el usuario.")
    finally:
        ser.close()
