import serial
import time
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Parámetros de la conexión serial
SERIAL_PORT = 'COM15'  # Cambiar según tu sistema (COMx en Windows)
BAUD_RATE = 115200  # Velocidad de baudios
TIMEOUT = 1.0  # segundos

# Inicializar UART
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT, dsrdtr=False, rtscts=False)
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


def enviar_movimiento_brazo():
    print("\n" + "="*50)
    print("CONTROL DE BRAZO - MOVIMIENTO SUAVE")
    print("="*50)
    
    angle1 = input("Ángulo Servo 1 (0-180): ")
    angle2 = input("Ángulo Servo 2 (0-180): ")
    tiempo = input("Tiempo en ms (0 para instantáneo): ")
    
    comando = f"A:{angle1},{angle2},{tiempo}"
    enviar_comando(comando)

def menu():
    while True:
        print("\n" + "="*50)
        print("CONTROL DE ROBOT - MENÚ PRINCIPAL")
        print("="*50)
        print("1. Mover a posición X,Y")
        print("2. Mover brazos (suave)")
        print("3. Mover servo individual")
        print("4. Resetear brazos a 90°")
        print("5. Control Gripper")
        print("6. PARADA DE EMERGENCIA")
        print("0. Salir")
        print("-"*50)
        opcion = input("Selecciona opción: ")

        if opcion == '1':
            x = input("Posición X (mm): ")
            y = input("Posición Y (mm): ")
            enviar_comando(f"M:{x},{y}")
        elif opcion == '2':
            enviar_movimiento_brazo()
        elif opcion == '3':
            servo = input("Número de servo (1 o 2): ")
            angulo = input("Ángulo (0-180): ")
            enviar_comando(f"P:{servo},{angulo}")
        elif opcion == '4':
            enviar_comando("RA")
        elif opcion == '5':
            print("\nControl de Gripper:")
            print("1. Cerrar")
            print("2. Abrir")
            gripper_opt = input("Opción: ")
            if gripper_opt == '1':
                enviar_comando("G:O")
            elif gripper_opt == '2':
                enviar_comando("G:C")
        elif opcion == '6':
            enviar_comando("S")
        elif opcion == '0':
            print("Saliendo...")
            break
        else:
            print("Opción inválida")

        leer_respuesta()
        
if __name__ == '__main__':
    try:
        menu()
    except KeyboardInterrupt:
        print("\nPrograma terminado por el usuario.")
    finally:
        ser.close()
