import serial
import time
import logging
from typing import Optional, Dict, Callable
from threading import Lock, Thread, Event
import queue
import threading

class UARTManager:
    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.lock = Lock()
        self.logger = logging.getLogger(__name__)
        
        self.message_queue = queue.Queue()
        self.listening_thread = None
        self.stop_listening = Event()
        self.message_callbacks = {}
        
        self.action_events = {}
        self.waiting_for_completion = {}
        # Cache de completados recientes para evitar condiciones de carrera
        self.completed_actions_recent = {}
        
    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(
                self.port, 
                self.baud_rate, 
                timeout=self.timeout,
                dsrdtr=False, 
                rtscts=False
            )
            
            # Dar tiempo al microcontrolador para reiniciar
            time.sleep(2)
            self.ser.reset_input_buffer()
            
            self._start_listening()
            
            self.logger.info(f"Conectado a {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando: {e}")
            return False
    
    def disconnect(self):
        self.stop_listening.set()
        if self.listening_thread:
            self.listening_thread.join(timeout=2)
            
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Desconectado del puerto serial")
    
    def _start_listening(self):
        self.stop_listening.clear()
        self.listening_thread = Thread(target=self._listen_for_messages, daemon=True)
        self.listening_thread.start()
    
    def _listen_for_messages(self):
        while not self.stop_listening.is_set():
            try:
                if self.ser and self.ser.in_waiting:
                    line = self.ser.readline().decode('ascii', errors='ignore').strip()
                    if line:
                        self.logger.debug(f"RX: {line}")
                        self.message_queue.put(line)
                        self._process_automatic_message(line)
                
                time.sleep(0.01)
            except Exception as e:
                self.logger.warning(f"Error escuchando: {e}")
                time.sleep(0.1)
    
    def _process_automatic_message(self, message: str):
        # Procesar eventos de finalización
        if "_COMPLETED:" in message:
            action_type = message.split("_COMPLETED:")[0]
            # Marcar como completado recientemente por si aún no se registró el waiter
            try:
                self.completed_actions_recent[action_type] = time.time()
            except Exception:
                pass
            # Log de diagnóstico
            try:
                self.logger.info(f"EVENT COMPLETED RX: {message} | waiting_for={list(self.waiting_for_completion.keys())}")
            except Exception:
                pass
            if action_type in self.waiting_for_completion:
                event = self.waiting_for_completion[action_type]
                event.set()
                
        # Procesar callbacks específicos
        if "LIMIT_" in message:
            if "limit_callback" in self.message_callbacks:
                self.message_callbacks["limit_callback"](message)
        
        elif "SYSTEM_STATUS:" in message:
            if "status_callback" in self.message_callbacks:
                self.message_callbacks["status_callback"](message)
        
        elif "SERVO_MOVE_STARTED:" in message:
            try:
                self.logger.debug(f"EVENT STARTED RX: {message}")
            except Exception:
                pass
            if "servo_start_callback" in self.message_callbacks:
                self.message_callbacks["servo_start_callback"](message)
        
        elif "SERVO_MOVE_COMPLETED:" in message:
            if "servo_complete_callback" in self.message_callbacks:
                self.message_callbacks["servo_complete_callback"](message)
                
        elif "GRIPPER_ACTION_STARTED:" in message:
            if "gripper_start_callback" in self.message_callbacks:
                self.message_callbacks["gripper_start_callback"](message)
                
        elif "GRIPPER_ACTION_COMPLETED:" in message:
            if "gripper_complete_callback" in self.message_callbacks:
                self.message_callbacks["gripper_complete_callback"](message)
                
        elif "STEPPER_MOVE_STARTED:" in message:
            try:
                self.logger.debug(f"EVENT STARTED RX: {message}")
            except Exception:
                pass
            if "stepper_start_callback" in self.message_callbacks:
                self.message_callbacks["stepper_start_callback"](message)
                
        elif "STEPPER_MOVE_COMPLETED:" in message:
            if "stepper_complete_callback" in self.message_callbacks:
                self.message_callbacks["stepper_complete_callback"](message)
    
    def wait_for_action_completion(self, action_type: str, timeout: float = 30.0) -> bool:
        # Comprobar si ya se completó hace muy poco (evita carrera con comandos rápidos)
        try:
            ts = self.completed_actions_recent.get(action_type)
            if ts is not None and (time.time() - ts) < 5.0:
                del self.completed_actions_recent[action_type]
                return True
        except Exception:
            pass

        event = threading.Event()
        self.waiting_for_completion[action_type] = event

        completed = event.wait(timeout)

        if action_type in self.waiting_for_completion:
            del self.waiting_for_completion[action_type]

        return completed
    
    def send_command(self, command: str) -> Dict:
        if not self.ser or not self.ser.is_open:
            return {"success": False, "error": "Puerto no conectado"}
        
        with self.lock:
            try:
                self._clear_message_queue()
                
                cmd_formatted = f"<{command}>"
                self.ser.write(cmd_formatted.encode('utf-8'))
                self.logger.debug(f"TX: {command}")
                
                time.sleep(0.1)
                response = self._read_command_response()
                
                return {"success": True, "response": response}
                
            except Exception as e:
                self.logger.error(f"Error enviando comando: {e}")
                return {"success": False, "error": str(e)}
    
    def _clear_message_queue(self):
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except queue.Empty:
                break
    
    def _read_command_response(self) -> str:
        responses = []
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                message = self.message_queue.get(timeout=0.1)
                responses.append(message)
                
                if message.startswith(("OK:", "ERR:")):
                    break
                    
            except queue.Empty:
                continue
        
        return '\n'.join(responses) if responses else ""
    
    def set_status_callback(self, callback):
        self.message_callbacks["status_callback"] = callback

    def set_servo_callbacks(self, start_callback, complete_callback):
        self.message_callbacks["servo_start_callback"] = start_callback
        self.message_callbacks["servo_complete_callback"] = complete_callback

    def set_gripper_callbacks(self, start_callback, complete_callback):
        self.message_callbacks["gripper_start_callback"] = start_callback
        self.message_callbacks["gripper_complete_callback"] = complete_callback
        
    def set_stepper_callbacks(self, start_callback, complete_callback):
        self.message_callbacks["stepper_start_callback"] = start_callback
        self.message_callbacks["stepper_complete_callback"] = complete_callback
    
    def set_limit_callback(self, callback: Callable[[str], None]):
        self.message_callbacks["limit_callback"] = callback
    
    def check_limits(self) -> Dict:
        return self.send_command("L")
    
    def wait_for_limit(self, timeout: float = 30.0) -> Optional[str]:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
                if "LIMIT_" in message and "TRIGGERED" in message:
                    return message
            except queue.Empty:
                continue
        
        return None
    
    def wait_for_message(self, expected_message: str, timeout: float = 10.0) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
                if expected_message in message:
                    self.logger.debug(f"Confirmación recibida: {message}")
                    return True
            except queue.Empty:
                continue
        
        return False