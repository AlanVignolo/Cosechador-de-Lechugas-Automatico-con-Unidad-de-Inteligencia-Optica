import serial # type: ignore
import time
import threading
import queue
import logging
from datetime import datetime
import sys

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'arduino_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

class ArduinoController:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.response_queue = queue.Queue()
        self.read_thread = None
        
    def connect(self):
        """Conectar al Arduino"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                write_timeout=1
            )
            time.sleep(2)  # Esperar reset del Arduino
            self.serial.flush()
            logging.info(f"Conectado a {self.port} @ {self.baudrate} bps")
            
            # Iniciar thread de lectura
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop)
            self.read_thread.start()
            return True
            
        except Exception as e:
            logging.error(f"Error al conectar: {e}")
            return False
    
    def disconnect(self):
        """Desconectar del Arduino"""
        self.running = False
        if self.read_thread:
            self.read_thread.join()
        if self.serial and self.serial.is_open:
            self.serial.close()
        logging.info("Desconectado")
    
    def _read_loop(self):
        """Loop de lectura en thread separado"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    response = self.serial.readline().decode('utf-8').strip()
                    if response:
                        logging.info(f"RX << {response}")
                        self.response_queue.put(response)
                        
                        # Procesar respuestas especiales
                        if response.startswith("LIM"):
                            logging.warning(f"¡Límite alcanzado! {response}")
                        elif response.startswith("ERR"):
                            logging.error(f"Error del Arduino: {response}")
                        elif response == "ARR":
                            logging.info("✓ Llegó a posición objetivo")
                        elif response == "HOM":
                            logging.info("✓ Home completado")
                            
            except Exception as e:
                if self.running:
                    logging.error(f"Error en lectura: {e}")
            time.sleep(0.001)
    
    def send_command(self, command):
        """Enviar comando al Arduino"""
        if not self.serial or not self.serial.is_open:
            logging.error("No conectado")
            return False
        
        try:
            cmd_formatted = f"<{command}>\n"
            self.serial.write(cmd_formatted.encode('utf-8'))
            logging.info(f"TX >> {command}")
            return True
        except Exception as e:
            logging.error(f"Error al enviar: {e}")
            return False
    
    def get_response(self, timeout=5):
        """Obtener respuesta con timeout"""
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    # ========== COMANDOS ESPECÍFICOS ==========
    
    def move_xy(self, x, y):
        """Mover a posición X,Y en mm"""
        return self.send_command(f"M:{x:.2f},{y:.2f}")
    
    def home(self):
        """Ejecutar secuencia de home"""
        return self.send_command("H")
    
    def stop(self):
        """Parada de emergencia"""
        return self.send_command("S")
    
    def get_status(self):
        """Solicitar estado actual"""
        return self.send_command("?")
    
    def set_arm_position(self, position):
        """Mover brazo a posición predefinida"""
        positions = ["RETRACTED", "EXTENDED", "COLLECTING", "DROPPING", "HANGING"]
        if position.upper() in positions:
            return self.send_command(f"A:{position.upper()}")
        else:
            logging.error(f"Posición inválida: {position}")
            return False
    
    def control_gripper(self, action):
        """Control del gripper"""
        if action.upper() in ["OPEN", "CLOSE"]:
            return self.send_command(f"G:{action.upper()}")
        else:
            logging.error(f"Acción gripper inválida: {action}")
            return False
    
    def set_speed(self, percent):
        """Establecer velocidad (0-100%)"""
        if 0 <= percent <= 100:
            return self.send_command(f"V:{percent}")
        else:
            logging.error(f"Velocidad inválida: {percent}%")
            return False
    
    def send_trajectory(self, points):
        """Enviar trayectoria de brazo
        points: lista de tuplas (servo1, servo2, gripper)
        """
        trajectory = ";".join([f"{s1},{s2},{g}" for s1, s2, g in points])
        return self.send_command(f"T:{trajectory}")


def print_menu():
    """Mostrar menú de opciones"""
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
    print("0. Salir")
    print("-"*50)


def main():
    # Configurar puerto (cambiar según tu sistema)
    if sys.platform == "linux":
        port = "/dev/ttyACM0"  # Linux
    elif sys.platform == "darwin":
        port = "/dev/tty.usbmodem1421"  # macOS
    else:
        port = "COM3"  # Windows
    
    # Crear controlador
    arduino = ArduinoController(port=port)
    
    # Conectar
    print(f"Conectando a {port}...")
    if not arduino.connect():
        print("No se pudo conectar. Verifica el puerto.")
        return
    
    try:
        while True:
            print_menu()
            opcion = input("Selecciona opción: ")
            
            if opcion == "1":
                x = float(input("Posición X (mm): "))
                y = float(input("Posición Y (mm): "))
                arduino.move_xy(x, y)
                
            elif opcion == "2":
                print("Iniciando HOME...")
                arduino.home()
                
            elif opcion == "3":
                print("¡PARADA DE EMERGENCIA!")
                arduino.stop()
                
            elif opcion == "4":
                arduino.get_status()
                time.sleep(0.5)  # Esperar respuesta
                
            elif opcion == "5":
                print("Posiciones disponibles:")
                print("1. RETRACTED")
                print("2. EXTENDED")
                print("3. COLLECTING")
                print("4. DROPPING")
                print("5. HANGING")
                pos = input("Selecciona posición: ")
                positions = ["", "RETRACTED", "EXTENDED", "COLLECTING", "DROPPING", "HANGING"]
                if pos.isdigit() and 1 <= int(pos) <= 5:
                    arduino.set_arm_position(positions[int(pos)])
                
            elif opcion == "6":
                action = input("OPEN/CLOSE: ")
                arduino.control_gripper(action)
                
            elif opcion == "7":
                speed = int(input("Velocidad (0-100%): "))
                arduino.set_speed(speed)
                
            elif opcion == "8":
                print("Ingresa puntos de trayectoria (servo1,servo2,gripper)")
                print("Ejemplo: 90,45,0")
                print("Escribe 'fin' para terminar")
                points = []
                while True:
                    point = input(f"Punto {len(points)+1}: ")
                    if point.lower() == 'fin':
                        break
                    try:
                        values = [int(x) for x in point.split(',')]
                        if len(values) == 3:
                            points.append(tuple(values))
                        else:
                            print("Formato incorrecto")
                    except:
                        print("Error en formato")
                
                if points:
                    arduino.send_trajectory(points)
                
            elif opcion == "9":
                cmd = input("Comando manual: ")
                arduino.send_command(cmd)
                
            elif opcion == "0":
                print("Saliendo...")
                break
            
            else:
                print("Opción inválida")
            
            # Dar tiempo para ver respuestas
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
    
    finally:
        arduino.disconnect()
        print("Programa terminado")


if __name__ == "__main__":
    main()