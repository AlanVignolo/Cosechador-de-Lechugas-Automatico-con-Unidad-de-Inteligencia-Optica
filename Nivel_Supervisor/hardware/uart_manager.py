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
        self.completed_actions_recent = {}
        self._action_last_started = {}
        self._last_movement_snapshots = []
        self._snap_header_printed = False
        self._movement_snapshots_by_id = {}
        self._movement_seen_ids = set()
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

            time.sleep(2)
            self.ser.reset_input_buffer()

            self._start_listening()

            self.logger.info(f"Conectado a {self.port}")
            try:
                self.send_command("HB:0")
            except Exception:
                pass
            return True
        except Exception as e:
            self.logger.error(f"Error conectando: {e}")
            return False

    def disconnect(self):
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
        if "_COMPLETED:" in message:
            action_type = message.split("_COMPLETED:")[0]
            try:
                self.completed_actions_recent[action_type] = time.time()
            except Exception:
                pass

            if "STEPPER_MOVE_COMPLETED:" in message and "REL:" in message:
                self._process_movement_completed(message)

            try:
                if RobotConfig.SHOW_UART_EVENTS:
                    self.logger.info(f"EVENT COMPLETED RX: {message} | waiting_for={list(self.waiting_for_completion.keys())}")
            except Exception:
                pass
            if action_type in self.waiting_for_completion:
                event = self.waiting_for_completion[action_type]
                event.set()

        elif "STEPPER_EMERGENCY_STOP:" in message:
            self._process_emergency_stop(message)

        if "LIMIT_" in message:
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
            if "limit_callback" in self.message_callbacks and "TRIGGERED" in message:
                self.message_callbacks["limit_callback"](message)
        
        elif "SYSTEM_STATUS:" in message:
            if "status_callback" in self.message_callbacks:
                self.message_callbacks["status_callback"](message)
        elif "LIMIT_STATUS:" in message:
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
            try:
                self._action_last_started["SERVO_MOVE"] = time.time()
            except Exception:
                pass
        
        elif "SERVO_MOVE_COMPLETED:" in message:
            if "servo_complete_callback" in self.message_callbacks:
                self.message_callbacks["servo_complete_callback"](message)
                
        elif "GRIPPER_ACTION_STARTED:" in message:
            if "gripper_start_callback" in self.message_callbacks:
                self.message_callbacks["gripper_start_callback"](message)
            try:
                self._action_last_started["GRIPPER_ACTION"] = time.time()
            except Exception:
                pass
                
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
            try:
                self._last_movement_snapshots.clear()
                self._movement_snapshots_by_id.clear()
                self._movement_seen_ids.clear()
            except Exception:
                pass
            try:
                self._action_last_started["STEPPER_MOVE"] = time.time()
            except Exception:
                pass
                
        elif "STEPPER_MOVE_COMPLETED:" in message:
            if hasattr(self, '_last_completed_message') and self._last_completed_message == message:
                return
            self._last_completed_message = message

            if "stepper_complete_callback" in self.message_callbacks:
                self.message_callbacks["stepper_complete_callback"](message)
            self._snap_header_printed = False
                
        elif "MOVEMENT_SNAPSHOTS:" in message:
            self._process_movement_snapshots(message)
            
    
    def wait_for_action_completion(self, action_type: str, timeout: float = 30.0) -> bool:
        try:
            ts_completed = self.completed_actions_recent.get(action_type)
            ts_started = self._action_last_started.get(action_type)
            now = time.time()
            if ts_completed is not None and (now - ts_completed) < 5.0:
                if action_type == "STEPPER_MOVE" and ts_started is None:
                    pass
                else:
                    if ts_started is None or ts_completed >= ts_started:
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
        try:
            clean_message = message.split('\n')[0]
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
        try:
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
        try:
            clean_message = message.split('\n')[0]
            snapshots_data = clean_message.replace("MOVEMENT_SNAPSHOTS:", "")
            if not snapshots_data:
                return
            if not self._snap_header_printed:
                print("SNAPSHOTS DEL MOVIMIENTO:")
                print("-" * 40)
                self._snap_header_printed = True

            snapshot_parts = snapshots_data.split(';')
            for snapshot in snapshot_parts:
                if '=' in snapshot and ',' in snapshot:
                    try:
                        flag = snapshot.split('=')[0].strip()
                        coords = snapshot.split('=')[1].split(',')
                        if len(coords) >= 2:
                            x_mm = int(coords[0])
                            y_mm = int(coords[1])
                            snap_id = None
                            if flag and (flag[0] in ('S', 's')):
                                try:
                                    snap_id = int(''.join(ch for ch in flag[1:] if ch.isdigit()))
                                except Exception:
                                    snap_id = None
                            if snap_id is not None:
                                if snap_id not in self._movement_seen_ids:
                                    self._movement_seen_ids.add(snap_id)
                                    self._movement_snapshots_by_id[snap_id] = (x_mm, y_mm)
                                    print(f"{flag}: X={x_mm}mm, Y={y_mm}mm")
                                else:
                                    continue
                            else:
                                if not self._last_movement_snapshots or self._last_movement_snapshots[-1] != (x_mm, y_mm):
                                    self._last_movement_snapshots.append((x_mm, y_mm))
                                    print(f"{flag}: X={x_mm}mm, Y={y_mm}mm")
                    except Exception:
                        continue
            if self._movement_snapshots_by_id:
                ordered = [self._movement_snapshots_by_id[k] for k in sorted(self._movement_snapshots_by_id.keys())]
                self._last_movement_snapshots = ordered
                        
        except Exception as e:
            if RobotConfig.VERBOSE_LOGGING:
                self.logger.warning(f"Error procesando snapshots: {e}")

    def get_last_snapshots(self):
        try:
            return list(self._last_movement_snapshots)
        except Exception:
            return []

    def clear_last_snapshots(self):
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
        self.message_callbacks["stepper_start_callback"] = start_callback
        self.message_callbacks["stepper_complete_callback"] = complete_callback
    
    def set_limit_callback(self, callback: Callable[[str], None]):
        self.message_callbacks["limit_callback"] = callback
    
    def check_limits(self) -> Dict:
        return self.send_command("L")

    def _update_limit_status_from_response(self, response: str):
        try:
            s = response or ""
            def has_true(key: str) -> bool:
                tokens = [f"{key}=1", f"{key}:1", f"{key}=true", f"{key}:true", f"{key}=ON", f"{key}:ON"]
                s_low = s.lower()
                return any(tok.lower() in s_low for tok in tokens)
            self._limit_status['H_LEFT'] = has_true('H_LEFT') or has_true('H_L')
            self._limit_status['H_RIGHT'] = has_true('H_RIGHT') or has_true('H_R')
            self._limit_status['V_UP'] = has_true('V_UP') or has_true('V_U')
            self._limit_status['V_DOWN'] = has_true('V_DOWN') or has_true('V_D')
            self._limit_status_last_update = time.time()
        except Exception:
            pass

    def get_limit_status(self) -> Dict:
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
                try:
                    self._process_automatic_message(message)
                except Exception:
                    pass
                if "LIMIT_" in message and "TRIGGERED" in message:
                    return message
            except queue.Empty:
                now = time.time()
                if now - last_poll >= 0.5:
                    last_poll = now
                    resp = self.check_limits()
                    try:
                        resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                    except Exception:
                        resp_str = ""
                    self._update_limit_status_from_response(resp_str)
                    if any(self._limit_status.values()):
                        active = [k for k, v in self._limit_status.items() if v]
                        return f"LIMIT_POLLED:{','.join(active)}"
                continue
        
        return None

    def wait_for_limit_specific(self, target: str, timeout: float = 30.0) -> Optional[str]:
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
                message = self.message_queue.get(timeout=0.1)
                try:
                    self._process_automatic_message(message)
                except Exception:
                    pass
                if wanted_trigger and wanted_trigger in message:
                    return message
            except queue.Empty:
                resp = self.check_limits()
                try:
                    resp_str = resp.get('response', '') if isinstance(resp, dict) else str(resp)
                except Exception:
                    resp_str = ""
                self._update_limit_status_from_response(resp_str)
                if self._limit_status.get(target, False):
                    return f"LIMIT_POLLED:{target}"
                time.sleep(0.05)
                continue
        return None

    def reset_scanning_state(self):
        print("Reseteando estado del UART manager...")


        with self.lock:
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except:
                    break

            essential_callbacks = {}
            for key in [
                "status_callback",
                "servo_start_callback", "servo_complete_callback",
                "gripper_start_callback", "gripper_complete_callback",
                "stepper_start_callback", "stepper_complete_callback",
                "limit_callback",
            ]:
                if key in self.message_callbacks:
                    essential_callbacks[key] = self.message_callbacks[key]

            self.message_callbacks.clear()
            self.message_callbacks.update(essential_callbacks)

            self.action_events.clear()
            self.waiting_for_completion.clear()
            self.completed_actions_recent.clear()
            self._action_last_started.clear()
            self._last_movement_snapshots.clear()

        print("UART manager state resetted (firmware auto-clears snapshots on new movements)")


        print("Reset del UART manager completado")

    def wait_for_message(self, expected_message: str, timeout: float = 10.0) -> bool:
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.5)
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