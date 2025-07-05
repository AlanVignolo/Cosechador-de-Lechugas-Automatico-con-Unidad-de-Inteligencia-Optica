import serial
import time
import logging
from typing import Optional, Dict, Callable
from threading import Lock, Thread, Event
import queue

class UARTManager:
    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.lock = Lock()
        self.logger = logging.getLogger(__name__)
        
        # Para mensajes automáticos (límites, etc.)
        self.message_queue = queue.Queue()
        self.listening_thread = None
        self.stop_listening = Event()
        self.message_callbacks = {}  # Para diferentes tipos de mensajes
        
    def connect(self) -> bool:
        """Conectar al puerto serial"""
        try:
            self.ser = serial.Serial(
                self.port, 
                self.baud_rate, 
                timeout=self.timeout,
                dsrdtr=False, 
                rtscts=False
            )
            time.sleep(2)  # Esperar reset del Arduino
            self.ser.reset_input_buffer()
            
            # Iniciar hilo de escucha para mensajes automáticos
            self._start_listening()
            
            self.logger.info(f"Conectado a {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando: {e}")
            return False
    
    def disconnect(self):
        """Desconectar del puerto serial"""
        self.stop_listening.set()
        if self.listening_thread:
            self.listening_thread.join(timeout=2)
            
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Desconectado del puerto serial")
    
    def _start_listening(self):
        """Iniciar hilo para escuchar mensajes automáticos"""
        self.stop_listening.clear()
        self.listening_thread = Thread(target=self._listen_for_messages, daemon=True)
        self.listening_thread.start()
    
    def _listen_for_messages(self):
        """Hilo que escucha mensajes automáticos del microcontrolador"""
        while not self.stop_listening.is_set():
            try:
                if self.ser and self.ser.in_waiting:
                    line = self.ser.readline().decode('ascii', errors='ignore').strip()
                    if line:
                        self.logger.debug(f"Auto RX: {line}")
                        self.message_queue.put(line)
                        
                        # Procesar callbacks si hay
                        self._process_automatic_message(line)
                
                time.sleep(0.01)  # No saturar CPU
            except Exception as e:
                self.logger.warning(f"Error escuchando: {e}")
                time.sleep(0.1)
    
    def _process_automatic_message(self, message: str):
        """Procesar mensajes automáticos del microcontrolador"""
        if "LIMIT_" in message:
            if "limit_callback" in self.message_callbacks:
                self.message_callbacks["limit_callback"](message)
        
        elif "SYSTEM_STATUS:" in message:
            if "status_callback" in self.message_callbacks:
                self.message_callbacks["status_callback"](message)
        
        elif "SERVO_CHANGED:" in message:
            if "servo_callback" in self.message_callbacks:
                self.message_callbacks["servo_callback"](message)
        
        elif message in ["GRIPPER_OPENED", "GRIPPER_CLOSED"]:
            if "gripper_callback" in self.message_callbacks:
                self.message_callbacks["gripper_callback"](message)
                
    def set_status_callback(self, callback):
        """Callback para mensajes de estado del sistema"""
        self.message_callbacks["status_callback"] = callback

    def set_servo_callback(self, callback):
        """Callback para cambios de servo"""
        self.message_callbacks["servo_callback"] = callback

    def set_gripper_callback(self, callback):
        """Callback para cambios de gripper"""
        self.message_callbacks["gripper_callback"] = callback
    
    def set_limit_callback(self, callback: Callable[[str], None]):
        """Establecer callback para cuando se toquen límites"""
        self.message_callbacks["limit_callback"] = callback
    
    def send_command(self, command: str) -> Dict:
        """Enviar comando y esperar respuesta específica"""
        if not self.ser or not self.ser.is_open:
            return {"success": False, "error": "Puerto no conectado"}
        
        with self.lock:
            try:
                # Limpiar mensajes antiguos
                self._clear_message_queue()
                
                # Enviar comando
                cmd_formatted = f"<{command}>"
                self.ser.write(cmd_formatted.encode('utf-8'))
                self.logger.debug(f"TX: {command}")
                
                # Esperar respuesta específica del comando
                time.sleep(0.1)
                response = self._read_command_response()
                
                return {"success": True, "response": response}
                
            except Exception as e:
                self.logger.error(f"Error enviando comando: {e}")
                return {"success": False, "error": str(e)}
    
    def _clear_message_queue(self):
        """Limpiar cola de mensajes"""
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except queue.Empty:
                break
    
    def _read_command_response(self) -> str:
        """Leer respuesta específica del comando"""
        responses = []
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                # Leer de la cola de mensajes
                message = self.message_queue.get(timeout=0.1)
                responses.append(message)
                
                # Si es una respuesta de comando (OK: o ERR:), terminar
                if message.startswith(("OK:", "ERR:")):
                    break
                    
            except queue.Empty:
                continue
        
        return '\n'.join(responses) if responses else ""
    
    def check_limits(self) -> Dict:
        """Consultar estado actual de límites"""
        return self.send_command("L")
    
    def wait_for_limit(self, timeout: float = 30.0) -> Optional[str]:
        """Esperar hasta que se toque un límite"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
                if "LIMIT_" in message and "TRIGGERED" in message:
                    return message
            except queue.Empty:
                continue
        
        return None  # Timeout
    
    def wait_for_message(self, expected_message: str, timeout: float = 10.0) -> bool:
        """Esperar un mensaje específico del microcontrolador"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
                if expected_message in message:
                    self.logger.debug(f"Confirmación recibida: {message}")
                    return True
            except queue.Empty:
                continue
        
        return False  # Timeout