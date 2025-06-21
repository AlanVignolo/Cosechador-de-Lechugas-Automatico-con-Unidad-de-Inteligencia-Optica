import serial
import time
import logging

# Configurar logging más detallado
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Probar diferentes baudrates
BAUDRATES_TO_TEST = [9600, 19200, 38400, 57600, 115200]
SERIAL_PORT = 'COM9'

def test_baudrate(port, baudrate):
    """Prueba un baudrate específico"""
    print(f"\n{'='*50}")
    print(f"PROBANDO BAUDRATE: {baudrate}")
    print(f"{'='*50}")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=2.0)
        time.sleep(2)  # Esperar reset
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Enviar comando simple
        test_command = "<H>"
        print(f"Enviando: {test_command}")
        ser.write(test_command.encode('utf-8'))
        ser.flush()
        
        time.sleep(0.5)
        
        # Leer respuesta
        responses = []
        start_time = time.time()
        
        while (time.time() - start_time) < 1.0:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline()
                    # Mostrar tanto bytes como texto
                    print(f"Bytes recibidos: {line}")
                    decoded = line.decode('ascii', errors='replace').strip()
                    print(f"Texto decodificado: '{decoded}'")
                    responses.append(decoded)
                    if decoded and not any(ord(c) > 127 for c in decoded):
                        print(f"✓ RESPUESTA VÁLIDA: {decoded}")
                        return True, responses
                except Exception as e:
                    print(f"Error decodificando: {e}")
            time.sleep(0.01)
        
        ser.close()
        
        if responses:
            print(f"❌ Respuestas con caracteres extraños: {responses}")
        else:
            print("❌ Sin respuesta")
        
        return False, responses
        
    except Exception as e:
        print(f"❌ Error con baudrate {baudrate}: {e}")
        return False, []

def test_basic_arduino_echo():
    """Prueba si hay un sketch básico corriendo"""
    print(f"\n{'='*50}")
    print("PROBANDO COMUNICACIÓN BÁSICA")
    print(f"{'='*50}")
    
    for baudrate in BAUDRATES_TO_TEST:
        success, responses = test_baudrate(SERIAL_PORT, baudrate)
        if success:
            print(f"\n🎉 BAUDRATE CORRECTO ENCONTRADO: {baudrate}")
            return baudrate
        time.sleep(1)
    
    return None

def test_raw_communication():
    """Prueba comunicación sin protocolo"""
    print(f"\n{'='*50}")
    print("PRUEBA DE COMUNICACIÓN RAW")
    print(f"{'='*50}")
    
    try:
        ser = serial.Serial(SERIAL_PORT, 115200, timeout=2.0)
        time.sleep(2)
        ser.reset_input_buffer()
        
        # Enviar caracteres simples
        test_chars = ['H', '?', 'A', '\n', '\r']
        
        for char in test_chars:
            print(f"Enviando: '{char}' (ASCII: {ord(char)})")
            ser.write(char.encode('utf-8'))
            ser.flush()
            time.sleep(0.2)
            
            # Leer respuesta inmediata
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                print(f"Respuesta bytes: {response}")
                print(f"Respuesta hex: {response.hex()}")
                try:
                    print(f"Respuesta texto: '{response.decode('ascii', errors='replace')}'")
                except:
                    print("No se pudo decodificar como ASCII")
        
        ser.close()
        
    except Exception as e:
        print(f"Error en prueba raw: {e}")

def check_arduino_bootloader():
    """Verifica si el Arduino está en modo bootloader"""
    print(f"\n{'='*50}")
    print("VERIFICANDO ESTADO DEL ARDUINO")
    print(f"{'='*50}")
    
    try:
        # Probar baudrate del bootloader (57600 para Mega)
        ser = serial.Serial(SERIAL_PORT, 57600, timeout=1.0)
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"Datos del bootloader: {data}")
        else:
            print("No hay datos del bootloader")
        
        ser.close()
        
        # Ahora probar baudrate normal
        ser = serial.Serial(SERIAL_PORT, 115200, timeout=1.0)
        time.sleep(2)  # Tiempo para reset
        
        print("Arduino debería haberse reseteado")
        time.sleep(1)
        
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"Datos después del reset: {data}")
        
        ser.close()
        
    except Exception as e:
        print(f"Error verificando Arduino: {e}")

if __name__ == '__main__':
    print("DIAGNÓSTICO DE COMUNICACIÓN SERIAL")
    print("=" * 60)
    
    # 1. Verificar estado del Arduino
    check_arduino_bootloader()
    
    # 2. Probar diferentes baudrates
    working_baudrate = test_basic_arduino_echo()
    
    # 3. Si no funciona, probar comunicación raw
    if not working_baudrate:
        test_raw_communication()
    
    print(f"\n{'='*60}")
    print("DIAGNÓSTICO COMPLETADO")
    print(f"{'='*60}")
    
    if working_baudrate:
        print(f"✓ Usar baudrate: {working_baudrate}")
    else:
        print("❌ No se encontró baudrate funcional")
        print("Posibles problemas:")
        print("1. Arduino no tiene el firmware correcto")
        print("2. Problema de conexión física")
        print("3. Arduino en modo bootloader o colgado")
        print("4. Puerto COM incorrecto")
        print("\nSoluciones:")
        print("- Verificar conexiones TX/RX")
        print("- Re-flashear el firmware")
        print("- Probar otro puerto COM")
        print("- Resetear Arduino manualmente")