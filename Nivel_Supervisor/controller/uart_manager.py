import serial
import time
import logging
from typing import Optional, Dict, Callable
from threading import Lock, Thread, Event
import queue
import threading
from config.robot_config import RobotConfig

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
        # Timestamp del último START por tipo de acción (para validar completados recientes)
        self.last_started_ts = {}
        # Buffer de snapshots de último movimiento (lista de tuplas [(x_mm, y_mm), ...])
        self._last_movement_snapshots = []
        self._snap_header_printed = False
        # Deduplicación por movimiento: id -> (x_mm, y_mm)
        self._movement_snapshots_by_id = {}
        self._movement_seen_ids = set()
        # Estado persistente de límites
        self._limit_status = {
            'H_LEFT': False,
            'H_RIGHT': False,
            'V_UP': False,
            'V_DOWN': False,
        }
        self._limit_status_last_update = 0.0
        
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
            # Deshabilitar heartbeat inicialmente para evitar mensajes molestos durante inicialización
            try:
                self.send_command("HB:0")
            except Exception:
                pass
            return True
        except Exception as e:
            self.logger.error(f"Error conectando: {e}")
            return False
    
    def disconnect(self):
        # Deshabilitar heartbeat antes de cerrar
        try:
            self.send_command("HB:0")
        except Exception:
            pass
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
                if RobotConfig.VERBOSE_LOGGING:
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
            
            # Procesar información de posición relativa si está disponible
            if "STEPPER_MOVE_COMPLETED:" in message and "REL:" in message:
                self._process_movement_completed(message)
                
                # Llamar al callback del RobotController para tracking de posición
                if "stepper_complete_callback" in self.message_callbacks:
                    self.logger.info(f"🔧 Llamando callback stepper_complete_callback...")
                    self.message_callbacks["stepper_complete_callback"](message)
                    self.logger.info(f"🔧 Callback stepper_complete_callback ejecutado")
                else:
                    self.logger.warning(f"🔧 NO HAY CALLBACK stepper_complete_callback registrado")
                
                # Al completar el movimiento, permitir que el próximo movimiento imprima encabezado
                self._snap_header_printed = False
            
            # Log de diagnóstico
            try:
                if RobotConfig.SHOW_UART_EVENTS:
                    self.logger.info(f"EVENT COMPLETED RX: {message} | waiting_for={list(self.waiting_for_completion.keys())}")
            except Exception:
                pass
            if action_type in self.waiting_for_completion:
                event = self.waiting_for_completion[action_type]
                event.set()
        
        # Procesar parada de emergencia con información de posición
        elif "STEPPER_EMERGENCY_STOP:" in message:
            self._process_emergency_stop(message)
                
        # Procesar callbacks específicos
        if "LIMIT_" in message:
            # Actualizar estado persistente de límites si es un mensaje TRIGGERED
            try:
                if "LIMIT_H_LEFT_TRIGGERED" in message:
                    self._limit_status['H_LEFT'] = True
                elif "LIMIT_H_RIGHT_TRIGGERED" in message:
                    self._limit_status['H_RIGHT'] = True
                elif "LIMIT_V_UP_TRIGGERED" in message:
                    self._limit_status['V_UP'] = True
                elif "LIMIT_V_DOWN_TRIGGERED" in message:
                    self._limit_status['V_DOWN'] = True
                self._limit_status_last_update = time.time()
            except Exception:
                pass
            # Solo llamar callback para mensajes TRIGGERED, no para LIMIT_STATUS (heartbeat molesto)
            if "limit_callback" in self.message_callbacks and "TRIGGERED" in message:
                self.message_callbacks["limit_callback"](message)
        
        elif "SYSTEM_STATUS:" in message:
            if "status_callback" in self.message_callbacks:
                self.message_callbacks["status_callback"](message)
        elif "LIMIT_STATUS:" in message:
            # Mensaje de broadcast periódico de firmware con estado de límites
            try:
                payload = message.split('LIMIT_STATUS:')[-1]
                self._update_limit_status_from_response(payload)
            except Exception:
                pass
        
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
            # Registrar timestamp de START para validaciones de completado
            try:
                self.last_started_ts["STEPPER_MOVE"] = time.time()
            except Exception:
                pass
            # Al iniciar un nuevo movimiento, invalidar cualquier marca de completado
            # reciente para evitar falsos positivos en wait_for_action_completion.
            # De lo contrario, si un movimiento anterior terminó hace <5s,
            # el siguiente wait podría devolver True inmediatamente sin
            # que el movimiento actual haya terminado realmente.
            try:
                self.completed_actions_recent.pop("STEPPER_MOVE", None)
            except Exception:
                pass
            # Al iniciar un nuevo movimiento, limpiar snapshots previos
            try:
                self._last_movement_snapshots.clear()
                self._movement_snapshots_by_id.clear()
                self._movement_seen_ids.clear()
            except Exception:
                pass
                
        # STEPPER_MOVE_COMPLETED ya se procesa arriba en "_COMPLETED:" - evitar duplicación
                
        elif "MOVEMENT_SNAPSHOTS:" in message:
            self._process_movement_snapshots(message)
            
    
    def wait_for_action_completion(self, action_type: str, timeout: float = 30.0) -> bool:
        # Ruta robusta para STEPPER_MOVE: sincronizar con START, registrar evento,
        # chequear completado reciente >= START y luego esperar evento con fallback.
        if action_type == "STEPPER_MOVE":
            # 1) Asegurar que tengamos registrado un START (evita started_ts=None)
            start_detect_deadline = time.time() + 1.5  # hasta 1.5s para detectar START
            while self.last_started_ts.get("STEPPER_MOVE") is None and time.time() < start_detect_deadline:
                time.sleep(0.01)
            started_ts = self.last_started_ts.get("STEPPER_MOVE")

            # 2) Registrar evento de espera
            event = threading.Event()
            self.waiting_for_completion[action_type] = event

            # 3) Fast-path: si ya tenemos COMPLETED posterior al START, salir ya
            try:
                completed_ts = self.completed_actions_recent.get("STEPPER_MOVE")
                if started_ts is not None and completed_ts is not None and completed_ts >= started_ts:
                    self.completed_actions_recent.pop("STEPPER_MOVE", None)
                    del self.waiting_for_completion[action_type]
                    return True
            except Exception:
                pass

            # 4) Esperar evento normal
            done = event.wait(timeout)
            if action_type in self.waiting_for_completion:
                del self.waiting_for_completion[action_type]
            if done:
                return True

            # 5) Fallback post-wait: por si el evento se perdió pero el COMPLETED llegó
            try:
                completed_ts2 = self.completed_actions_recent.get("STEPPER_MOVE")
                if started_ts is not None and completed_ts2 is not None and completed_ts2 >= started_ts:
                    self.completed_actions_recent.pop("STEPPER_MOVE", None)
                    return True
            except Exception:
                pass
            return False

        # Para otras acciones, mantener la lógica basada en eventos con una
        # pequeña optimización si el completado fue muy reciente y posterior al START.
        try:
            completed_ts = self.completed_actions_recent.get(action_type)
            started_ts = self.last_started_ts.get(action_type)
            if started_ts is not None and completed_ts is not None:
                if completed_ts >= started_ts and (time.time() - completed_ts) < 5.0:
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
    
    def _process_movement_completed(self, message: str):
        """Procesar mensaje de movimiento completado con información de posición relativa"""
        try:
            # Limpiar el mensaje de posibles mezclas
            clean_message = message.split('\n')[0]  # Solo la primera línea
            
            # Formato: STEPPER_MOVE_COMPLETED:pos_h,pos_v,REL:rel_h,rel_v,MM:mm_h,mm_v
            parts = clean_message.split(',')
            if len(parts) >= 6:
                rel_h_steps = int(parts[2].split(':')[1])
                rel_v_steps = int(parts[3])
                rel_h_mm = int(parts[4].split(':')[1])
                rel_v_mm = int(parts[5])
                
                if RobotConfig.SHOW_MOVEMENT_COMPLETE:
                    display_x_mm = RobotConfig.display_x_distance(rel_h_mm)
                    display_y_mm = RobotConfig.display_y_distance(rel_v_mm)
                    display_x_steps = RobotConfig.display_x_distance(rel_h_steps)
                    display_y_steps = RobotConfig.display_y_distance(rel_v_steps)
                    print(f"📍 Movimiento completado - Distancia relativa: X={display_x_mm}mm ({display_x_steps} pasos), Y={display_y_mm}mm ({display_y_steps} pasos)")
        except Exception as e:
            if RobotConfig.VERBOSE_LOGGING:
                self.logger.warning(f"Error procesando mensaje de movimiento: {e}")
    
    def _process_emergency_stop(self, message: str):
        """Procesar mensaje de parada de emergencia con información de posición"""
        try:
            # Formato: STEPPER_EMERGENCY_STOP:pos_h,pos_v,REL:rel_h,rel_v,MM:mm_h,mm_v
            parts = message.split(',')
            if len(parts) >= 6:
                rel_h_steps = int(parts[2].split(':')[1])
                rel_v_steps = int(parts[3])
                rel_h_mm = int(parts[4].split(':')[1])
                rel_v_mm = int(parts[5])
                
                print(f"🚨 PARADA DE EMERGENCIA - Movido hasta parada: X={rel_h_mm}mm ({rel_h_steps} pasos), Y={rel_v_mm}mm ({rel_v_steps} pasos)")
        except Exception as e:
            if RobotConfig.VERBOSE_LOGGING:
                self.logger.warning(f"Error procesando mensaje de parada de emergencia: {e}")
    
    def _process_movement_snapshots(self, message: str):
        """Procesar mensaje con snapshots del movimiento"""
        try:
            # Limpiar el mensaje de posibles mezclas
            clean_message = message.split('\n')[0]  # Solo la primera línea
            snapshots_data = clean_message.replace("MOVEMENT_SNAPSHOTS:", "")
            if not snapshots_data:
                return
            if not self._snap_header_printed:
                print("SNAPSHOTS DEL MOVIMIENTO:")
                print("-" * 40)
                self._snap_header_printed = True
            
            snapshot_parts = snapshots_data.split(';')
            # No reiniciar el buffer aquí; permitimos múltiples mensajes chunked por movimiento
            for snapshot in snapshot_parts:
                if '=' in snapshot and ',' in snapshot:
                    try:
                        flag = snapshot.split('=')[0].strip()  # e.g., S1
                        coords = snapshot.split('=')[1].split(',')
                        if len(coords) >= 2:
                            x_mm = int(coords[0])
                            y_mm = int(coords[1])
                            # Extraer id numérico si es posible
                            snap_id = None
                            if flag and (flag[0] in ('S', 's')):
                                try:
                                    snap_id = int(''.join(ch for ch in flag[1:] if ch.isdigit()))
                                except Exception:
                                    snap_id = None
                            # Deduplicar por id dentro del mismo movimiento
                            if snap_id is not None:
                                if snap_id not in self._movement_seen_ids:
                                    self._movement_seen_ids.add(snap_id)
                                    self._movement_snapshots_by_id[snap_id] = (x_mm, y_mm)
                                    print(f"{flag}: X={x_mm}mm, Y={y_mm}mm")
                                else:
                                    # Ignorar duplicados exactos S# en mensajes repetidos
                                    continue
                            else:
                                # Si no se pudo extraer id, agregar secuencialmente evitando duplicados exactos consecutivos
                                if not self._last_movement_snapshots or self._last_movement_snapshots[-1] != (x_mm, y_mm):
                                    self._last_movement_snapshots.append((x_mm, y_mm))
                                    print(f"{flag}: X={x_mm}mm, Y={y_mm}mm")
                    except Exception:
                        continue
            # Reconstruir lista ordenada por id si tenemos ids
            if self._movement_snapshots_by_id:
                ordered = [self._movement_snapshots_by_id[k] for k in sorted(self._movement_snapshots_by_id.keys())]
                self._last_movement_snapshots = ordered
                        
        except Exception as e:
            if RobotConfig.VERBOSE_LOGGING:
                self.logger.warning(f"Error procesando snapshots: {e}")

    def get_last_snapshots(self):
        """Devuelve la lista de snapshots del último movimiento como lista de (x_mm, y_mm)."""
        try:
            return list(self._last_movement_snapshots)
        except Exception:
            return []

    def clear_last_snapshots(self):
        """Limpia la lista de snapshots almacenados."""
        try:
            self._last_movement_snapshots.clear()
            self._snap_header_printed = False
            self._movement_snapshots_by_id.clear()
            self._movement_seen_ids.clear()
        except Exception:
            pass
    
    
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
                # Procesar mensajes automáticos para no perder eventos durante lecturas síncronas
                try:
                    self._process_automatic_message(message)
                except Exception:
                    pass
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
        self.logger.info(f"🔧 set_stepper_callbacks llamado: start={start_callback}, complete={complete_callback}")
        self.message_callbacks["stepper_start_callback"] = start_callback
        self.message_callbacks["stepper_complete_callback"] = complete_callback
        self.logger.info(f"🔧 Callbacks registrados. Total callbacks: {list(self.message_callbacks.keys())}")
    
    def set_limit_callback(self, callback: Callable[[str], None]):
        self.message_callbacks["limit_callback"] = callback
    
    def check_limits(self) -> Dict:
        return self.send_command("L")

    def _update_limit_status_from_response(self, response: str):
        """Parsea una respuesta al comando 'L' para actualizar _limit_status.
        Acepta formatos tipo 'H_LEFT=1' o 'H_LEFT:true' en cualquier combinación.
        """
        try:
            s = response or ""
            def has_true(key: str) -> bool:
                # Busca patrones comunes: KEY=1, KEY:true, KEY=ON
                tokens = [f"{key}=1", f"{key}:1", f"{key}=true", f"{key}:true", f"{key}=ON", f"{key}:ON"]
                s_low = s.lower()
                return any(tok.lower() in s_low for tok in tokens)
            # Aceptar claves largas (LIMIT_STATUS) y cortas (respuesta de 'L')
            self._limit_status['H_LEFT'] = has_true('H_LEFT') or has_true('H_L')
            self._limit_status['H_RIGHT'] = has_true('H_RIGHT') or has_true('H_R')
            self._limit_status['V_UP'] = has_true('V_UP') or has_true('V_U')
            self._limit_status['V_DOWN'] = has_true('V_DOWN') or has_true('V_D')
            self._limit_status_last_update = time.time()
        except Exception:
            pass

    def get_limit_status(self) -> Dict:
        """Devuelve copia del estado persistente de límites y timestamp de actualización."""
        return {
            'status': dict(self._limit_status),
            'last_update': self._limit_status_last_update,
        }
    
    def wait_for_limit(self, timeout: float = 30.0) -> Optional[str]:
        start_time = time.time()
        last_poll = 0.0
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
                # Procesar eventos automáticos por si llegan durante la espera
                try:
                    self._process_automatic_message(message)
                except Exception:
                    pass
                if "LIMIT_" in message and "TRIGGERED" in message:
                    return message
            except queue.Empty:
                # Si no llegó evento, hacer polling periódico del estado de límites
                now = time.time()
                if now - last_poll >= 0.5:  # cada 500ms
                    last_poll = now
                    resp = self.check_limits()
                    try:
                        resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                    except Exception:
                        resp_str = ""
                    self._update_limit_status_from_response(resp_str)
                    # Si algún límite está activo, retornar como detección por polling
                    if any(self._limit_status.values()):
                        # Componer un mensaje compatible
                        active = [k for k, v in self._limit_status.items() if v]
                        return f"LIMIT_POLLED:{','.join(active)}"
                continue
        
        return None

    def wait_for_limit_specific(self, target: str, timeout: float = 30.0) -> Optional[str]:
        """Espera un límite específico.
        target en { 'H_LEFT','H_RIGHT','V_UP','V_DOWN' }
        Acepta mensajes TRIGGERED o estado polleado para ese target.
        """
        start_time = time.time()
        trigger_map = {
            'H_LEFT': 'LIMIT_H_LEFT_TRIGGERED',
            'H_RIGHT': 'LIMIT_H_RIGHT_TRIGGERED',
            'V_UP': 'LIMIT_V_UP_TRIGGERED',
            'V_DOWN': 'LIMIT_V_DOWN_TRIGGERED',
        }
        wanted_trigger = trigger_map.get(target, '')
        
        while time.time() - start_time < timeout:
            try:
                # Timeout más corto para ser más responsivo
                message = self.message_queue.get(timeout=0.1)
                try:
                    self._process_automatic_message(message)
                except Exception:
                    pass
                # Detección inmediata del trigger específico
                if wanted_trigger and wanted_trigger in message:
                    return message
            except queue.Empty:
                # Polling menos frecuente solo si no hay mensajes
                resp = self.check_limits()
                try:
                    resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                except Exception:
                    resp_str = ""
                self._update_limit_status_from_response(resp_str)
                if self._limit_status.get(target, False):
                    return f"LIMIT_POLLED:{target}"
                # Pequeña pausa para no saturar
                time.sleep(0.05)
                continue
        return None
    
    def reset_scanning_state(self):
        """Resetear estado completo para nuevo escáner"""
        print("Reseteando estado del UART manager...")
        
        with self.lock:
            # Limpiar cola de mensajes
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except:
                    break
            
            # Resetear callbacks (mantener solo los esenciales del sistema)
            essential_callbacks = {}
            # Mantener callbacks del sistema si existen
            for key in ["status_callback", "servo_start_callback", "servo_complete_callback", 
                       "gripper_start_callback", "gripper_complete_callback",
                       "stepper_start_callback", "stepper_complete_callback"]:  # CRÍTICO: Mantener callbacks de stepper para tracking de posición
                if key in self.message_callbacks:
                    essential_callbacks[key] = self.message_callbacks[key]
            
            # Limpiar todos los callbacks y restaurar solo los esenciales
            self.message_callbacks.clear()
            self.message_callbacks.update(essential_callbacks)
            self.logger.info(f"🔧 Callbacks después del reset: {list(self.message_callbacks.keys())}")
            
            # Resetear eventos de acción y completado
            self.action_events.clear()
            self.waiting_for_completion.clear()
            self.completed_actions_recent.clear()
            # Limpiar snapshots almacenados
            self._last_movement_snapshots.clear()
        
        # El firmware no tiene comando RS específico, pero se auto-resetea con nuevos movimientos
        # Los snapshots se limpian automáticamente cuando se inician nuevos movimientos
        print("UART manager state resetted (firmware auto-clears snapshots on new movements)")
        
        print("Reset del UART manager completado")
    
    def wait_for_message(self, expected_message: str, timeout: float = 10.0) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
                # Procesar eventos automáticos por si llegan durante la espera
                try:
                    self._process_automatic_message(message)
                except Exception:
                    pass
                if expected_message in message:
                    self.logger.debug(f"Confirmación recibida: {message}")
                    return True
            except queue.Empty:
                continue
        
        return False