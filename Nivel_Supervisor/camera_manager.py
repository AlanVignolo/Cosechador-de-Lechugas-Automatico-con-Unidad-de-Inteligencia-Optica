"""
Gestor centralizado de cámara para el sistema CLAUDIO
Evita problemas de recursos al abrir/cerrar constantemente la cámara en Raspberry Pi
"""

import cv2
import time
import threading
from typing import Optional, Tuple, Callable
import numpy as np
from queue import Queue, Empty

class CameraManager:
    """Gestor singleton para la cámara del robot CLAUDIO"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CameraManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.cap = None
            self.camera_index = None
            self.is_active = False
            self.frame_lock = threading.Lock()
            self.last_frame = None
            self.initialized = True
            self._working_camera_cache = None
            # Reference counters
            self._use_count = 0          # How many components are using the camera
            self._stream_users = 0       # How many components requested video stream
            
            # Video streaming functionality
            self.video_mode = False
            self.video_thread = None
            self.video_queue = Queue(maxsize=5)
            self.video_callbacks = []
            self.video_fps = 30
            self.video_stop_event = threading.Event()
    
    def find_working_camera(self, timeout_per_camera: float = 3.0) -> Optional[int]:
        """Encuentra una cámara que funcione, probando índices de 0 a 9 con timeout"""
        if self._working_camera_cache is not None:
            # Verificar si la cámara cached sigue funcionando
            try:
                test_cap = cv2.VideoCapture(self._working_camera_cache)
                if test_cap.isOpened():
                    # Timeout para lectura
                    start_time = time.time()
                    ret, frame = None, None
                    while time.time() - start_time < 2.0:
                        ret, frame = test_cap.read()
                        if ret and frame is not None:
                            break
                        time.sleep(0.1)
                    
                    test_cap.release()
                    if ret and frame is not None:
                        return self._working_camera_cache
                    else:
                        self._working_camera_cache = None
                else:
                    test_cap.release()
                    self._working_camera_cache = None
            except:
                self._working_camera_cache = None
        
        # Buscar una cámara que funcione
        print("Buscando cámara disponible...")
        for i in range(10):
            print(f"Probando cámara índice {i}...")
            try:
                start_time = time.time()
                cap = cv2.VideoCapture(i)
                
                # Timeout para apertura
                if time.time() - start_time > timeout_per_camera:
                    print(f"Timeout abriendo cámara {i}")
                    cap.release()
                    continue
                    
                if cap.isOpened():
                    # Timeout para lectura de frame
                    frame_start = time.time()
                    ret, frame = None, None
                    while time.time() - frame_start < timeout_per_camera:
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            break
                        time.sleep(0.1)
                        
                    if ret and frame is not None:
                        print(f"✅ Cámara encontrada en índice {i}")
                        cap.release()
                        self._working_camera_cache = i
                        return i
                    else:
                        print(f"❌ No se pudo leer frame de cámara {i}")
                        cap.release()
                else:
                    print(f"❌ No se pudo abrir cámara {i}")
                    cap.release()
            except Exception as e:
                print(f"❌ Error probando cámara {i}: {e}")
                continue
        
        print("❌ No se encontró ninguna cámara funcional")
        return None
    
    def initialize_camera(self, camera_index: Optional[int] = None, force_reinit: bool = False) -> bool:
        """
        Inicializa la cámara
        
        Args:
            camera_index: Índice de la cámara (None para auto-detección)
            force_reinit: Forzar reinicialización aunque ya esté activa
            
        Returns:
            True si la inicialización fue exitosa
        """
        with self._lock:
            if self.is_active and not force_reinit:
                return True
            
            # Cerrar cámara anterior si existe
            if self.cap is not None:
                try:
                    self.cap.release()
                    time.sleep(0.2)
                except:
                    pass
                self.cap = None
                self.is_active = False
            
            # Limpiar recursos OpenCV
            cv2.destroyAllWindows()
            time.sleep(0.3)
            
            # Determinar índice de cámara
            if camera_index is None:
                camera_index = self.find_working_camera()
                if camera_index is None:
                    print("Error: No se pudo encontrar una cámara funcional")
                    return False
            # Inicializar cámara
            try:
                print(f"Inicializando cámara en índice {camera_index}")
                self.cap = cv2.VideoCapture(camera_index)
                
                if not self.cap.isOpened():
                    print(f"Error: No se pudo abrir la cámara en índice {camera_index}")
                    return False
                
                # Configuraciones de cámara
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                
                # Esperar inicialización y capturar frame de prueba
                time.sleep(0.5)
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    print("Error: No se pudo capturar frame de prueba")
                    self.cap.release()
                    self.cap = None
                    return False
                
                self.camera_index = camera_index
                self.is_active = True
                self.last_frame = frame.copy()
                
                print(f"Cámara inicializada exitosamente en índice {camera_index}")
                return True
                
            except Exception as e:
                print(f"Error al inicializar cámara: {e}")
                if self.cap is not None:
                    try:
                        self.cap.release()
                    except:
                        pass
                    self.cap = None
                return False
    
    def ensure_initialized(self) -> bool:
        """Asegura que la cámara esté inicializada sin reiniciar si ya está activa."""
        if self.is_camera_active():
            return True
        # Elegir índice actual o cacheado si existe; si no, auto-detectar dentro de initialize_camera
        idx = self.camera_index if self.camera_index is not None else self._working_camera_cache
        return self.initialize_camera(idx)
    
    def capture_frame(self, timeout: float = 5.0, max_retries: int = 3) -> Optional[np.ndarray]:
        """
        Captura un frame de la cámara
        
        Args:
            timeout: Tiempo máximo de espera
            max_retries: Número máximo de reintentos
            
        Returns:
            Frame capturado o None si falla
        """
        for attempt in range(max_retries):
            if not self.is_active:
                if not self.initialize_camera():
                    print(f"Intento {attempt + 1}: Fallo al inicializar cámara")
                    continue
            
            with self.frame_lock:
                try:
                    if self.cap is None or not self.cap.isOpened():
                        print(f"Intento {attempt + 1}: Cámara no disponible")
                        self.is_active = False
                        continue
                    
                    # Capturar con timeout usando threading
                    result = {'frame': None, 'success': False}
                    
                    def capture_thread():
                        try:
                            ret, frame = self.cap.read()
                            if ret and frame is not None:
                                result['frame'] = frame.copy()
                                result['success'] = True
                        except Exception as e:
                            print(f"Error en captura: {e}")
                            result['success'] = False
                    
                    thread = threading.Thread(target=capture_thread)
                    thread.start()
                    thread.join(timeout)
                    
                    if result['success'] and result['frame'] is not None:
                        self.last_frame = result['frame'].copy()
                        return result['frame']
                    else:
                        print(f"Intento {attempt + 1}: Fallo en captura de frame")
                        self.is_active = False
                        
                except Exception as e:
                    print(f"Intento {attempt + 1}: Error inesperado: {e}")
                    self.is_active = False
        
        print("Todos los intentos de captura fallaron")
        return None
    
    def get_last_frame(self) -> Optional[np.ndarray]:
        """Retorna el último frame capturado exitosamente"""
        return self.last_frame.copy() if self.last_frame is not None else None
    
    def is_camera_active(self) -> bool:
        """Verifica si la cámara está activa y funcionando"""
        return self.is_active and self.cap is not None and self.cap.isOpened()
    
    def get_camera_info(self) -> dict:
        """Retorna información sobre el estado de la cámara"""
        info = {
            'is_active': self.is_active,
            'camera_index': self.camera_index,
            'has_cap': self.cap is not None,
            'cap_opened': self.cap.isOpened() if self.cap is not None else False,
            'has_last_frame': self.last_frame is not None
        }
        
        if self.cap is not None and self.cap.isOpened():
            try:
                info['width'] = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                info['height'] = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                info['fps'] = int(self.cap.get(cv2.CAP_PROP_FPS))
            except:
                pass
        
        return info
    
    def restart_camera(self, camera_index: Optional[int] = None) -> bool:
        """Reinicia la cámara forzosamente"""
        print("Reiniciando cámara...")
        return self.initialize_camera(camera_index, force_reinit=True)
    
    def release_camera(self):
        """Libera la cámara completamente"""
        with self._lock:
            # Solo permitir liberar si nadie la está usando
            if getattr(self, '_use_count', 0) > 0:
                print(f"No se libera cámara: en uso por {_format_count(self._use_count)} consumidor(es)")
                return
            if self.cap is not None:
                try:
                    print("Liberando cámara...")
                    self.cap.release()
                    time.sleep(0.3)
                    cv2.destroyAllWindows()
                except Exception as e:
                    print(f"Error al liberar cámara: {e}")
                finally:
                    self.cap = None
                    self.is_active = False
                    self.camera_index = None
                    self.last_frame = None

    def acquire(self, owner: Optional[str] = None) -> bool:
        """Indica que un componente comenzará a usar la cámara."""
        with self._lock:
            self._use_count += 1
        # Inicializar si no está lista
        ok = self.ensure_initialized()
        if not ok:
            # revertir contador si falla
            with self._lock:
                self._use_count = max(0, self._use_count - 1)
        else:
            if owner:
                print(f"CameraManager: uso adquirido por '{owner}' (total={self._use_count})")
        return ok

    def release(self, owner: Optional[str] = None):
        """Indica que un componente ya no necesita la cámara. No libera el dispositivo a menos que el conteo llegue a 0 y no haya streaming."""
        with self._lock:
            self._use_count = max(0, self._use_count - 1)
            remaining = self._use_count
        if owner:
            print(f"CameraManager: uso liberado por '{owner}' (restantes={remaining})")
        # No apagamos la cámara aquí; se hace al cerrar app

    def start_stream_ref(self, fps: int = 30) -> bool:
        """Solicita el stream de video con referencia. Inicia el hilo solo cuando pasa de 0 -> 1 usuarios."""
        if not self.ensure_initialized():
            return False
        with self._lock:
            self._stream_users += 1
            need_start = (self._stream_users == 1)
        if need_start:
            return self.start_video_stream(fps=fps)
        else:
            # Ajustar FPS si se solicita distinto por nuevos usuarios (opcional: mantener el existente)
            return True

    def stop_stream_ref(self):
        """Libera una referencia de streaming. Detiene el hilo solo cuando el conteo llega a 0."""
        with self._lock:
            self._stream_users = max(0, self._stream_users - 1)
            need_stop = (self._stream_users == 0)
        if need_stop:
            self.stop_video_stream()
    
    def reset_completely(self):
        """Reset completo del camera manager - limpia todo estado y recursos"""
        print("Iniciando reset completo del camera manager...")
        
        # 1. Detener video stream si está activo
        self.stop_video_stream()
        
        # 2. Liberar cámara completamente
        self.release_camera()
        
        # 3. Reset completo de estado
        with self._lock:
            # Limpiar todas las variables de estado
            self.cap = None
            self.camera_index = None
            self.is_active = False
            self.last_frame = None
            self._working_camera_cache = None
            
            # Reset video state
            self.video_mode = False
            self.video_thread = None
            self.video_callbacks.clear()
            
            # Limpiar queue
            while not self.video_queue.empty():
                try:
                    self.video_queue.get_nowait()
                except:
                    break
            
            # Reset events
            if hasattr(self, 'video_stop_event'):
                self.video_stop_event.set()
                self.video_stop_event.clear()
        
        # 4. Limpieza agresiva de OpenCV
        for _ in range(5):
            cv2.destroyAllWindows()
            time.sleep(0.1)
        
        # 5. Espera adicional para liberación de recursos
        time.sleep(1.0)
        
        print("Reset completo del camera manager finalizado")
    
    def _video_capture_loop(self):
        """Loop interno de captura de video en hilo separado"""
        frame_interval = 1.0 / self.video_fps
        
        while not self.video_stop_event.is_set():
            try:
                if not self.is_active:
                    time.sleep(0.1)
                    continue
                
                frame = self.capture_frame(timeout=1.0, max_retries=1)
                if frame is not None:
                    # Agregar frame al queue (elimina el más viejo si está lleno)
                    try:
                        self.video_queue.put_nowait(frame.copy())
                    except:
                        # Queue lleno, remover el más viejo y agregar el nuevo
                        try:
                            self.video_queue.get_nowait()
                            self.video_queue.put_nowait(frame.copy())
                        except Empty:
                            pass
                    
                    # Llamar callbacks registrados
                    for callback in self.video_callbacks:
                        try:
                            callback(frame.copy())
                        except Exception as e:
                            print(f"Error en callback de video: {e}")
                
                time.sleep(frame_interval)
                
            except Exception as e:
                print(f"Error en video loop: {e}")
                time.sleep(0.1)
    
    def start_video_stream(self, fps: int = 30) -> bool:
        """
        Inicia el modo de video streaming automático
        
        Args:
            fps: Frames por segundo deseados
            
        Returns:
            True si se inició correctamente
        """
        if self.video_mode:
            return True
            
        if not self.initialize_camera():
            return False
            
        self.video_fps = fps
        self.video_stop_event.clear()
        self.video_thread = threading.Thread(target=self._video_capture_loop, daemon=True)
        self.video_thread.start()
        self.video_mode = True
        
        print(f"Video stream iniciado a {fps} FPS")
        return True
    
    def stop_video_stream(self):
        """Detiene el modo de video streaming"""
        if not self.video_mode:
            return
            
        self.video_stop_event.set()
        if self.video_thread and self.video_thread.is_alive():
            self.video_thread.join(timeout=2.0)
        
        # Limpiar queue
        while not self.video_queue.empty():
            try:
                self.video_queue.get_nowait()
            except Empty:
                break
                
        self.video_mode = False
        self.video_callbacks.clear()
        print("Video stream detenido")
    
    def register_video_callback(self, callback: Callable[[np.ndarray], None]):
        """
        Registra una función que será llamada automáticamente con cada frame
        
        Args:
            callback: Función que recibe un frame (numpy array) como parámetro
        """
        if callback not in self.video_callbacks:
            self.video_callbacks.append(callback)
    
    def unregister_video_callback(self, callback: Callable[[np.ndarray], None]):
        """Desregistra un callback de video"""
        if callback in self.video_callbacks:
            self.video_callbacks.remove(callback)
    
    def get_latest_video_frame(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Obtiene el frame más reciente del stream de video
        
        Args:
            timeout: Tiempo máximo de espera
            
        Returns:
            Frame más reciente o None si no hay disponible
        """
        if not self.video_mode:
            return self.capture_frame()
            
        try:
            # Obtener el frame más reciente (descartar los viejos)
            latest_frame = None
            while True:
                try:
                    latest_frame = self.video_queue.get_nowait()
                except Empty:
                    break
            # Fallbacks para evitar devolver None durante warm-up
            if latest_frame is None:
                # Intentar devolver el último frame válido conocido
                if self.last_frame is not None:
                    return self.last_frame.copy()
                # Como último recurso, intentar una captura directa rápida
                frame = self.capture_frame(timeout=0.5, max_retries=1)
                return frame
            return latest_frame
        except:
            return None
    
    def is_video_streaming(self) -> bool:
        """Verifica si el modo de video streaming está activo"""
        return self.video_mode and (self.video_thread is not None and self.video_thread.is_alive())

    def __del__(self):
        """Destructor para asegurar liberación de recursos"""
        try:
            self.stop_video_stream()
            self.release_camera()
        except:
            pass

# Helper interno para mensajes
def _format_count(n: int) -> int:
    try:
        return int(n)
    except Exception:
        return 0


# Instancia global del gestor
camera_manager = CameraManager()

def get_camera_manager() -> CameraManager:
    """Retorna la instancia singleton del gestor de cámara"""
    return camera_manager

def capture_frame_safe(timeout: float = 5.0, max_retries: int = 3) -> Optional[np.ndarray]:
    """Función de conveniencia para capturar un frame"""
    return camera_manager.capture_frame(timeout, max_retries)

def initialize_camera_safe(camera_index: Optional[int] = None) -> bool:
    """Función de conveniencia para inicializar la cámara"""
    return camera_manager.initialize_camera(camera_index)

def get_camera_status() -> dict:
    """Función de conveniencia para obtener estado de la cámara"""
    return camera_manager.get_camera_info()

# Funciones de conveniencia para video streaming
def start_video_stream(fps: int = 30) -> bool:
    """Inicia video streaming automático"""
    return camera_manager.start_video_stream(fps)

def stop_video_stream():
    """Detiene video streaming"""
    camera_manager.stop_video_stream()

def register_video_callback(callback):
    """Registra función que será llamada con cada frame automáticamente"""
    camera_manager.register_video_callback(callback)

def get_latest_video_frame():
    """Obtiene el frame más reciente del video stream"""
    return camera_manager.get_latest_video_frame()

def is_video_streaming() -> bool:
    """Verifica si está en modo video streaming"""
    return camera_manager.is_video_streaming()
