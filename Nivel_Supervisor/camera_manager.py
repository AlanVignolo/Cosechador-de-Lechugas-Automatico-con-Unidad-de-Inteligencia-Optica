"""
Gestor centralizado de cámara para el sistema CLAUDIO
Evita problemas de recursos al abrir/cerrar constantemente la cámara en Raspberry Pi
"""

import cv2
import time
import threading
from typing import Optional, Tuple
import numpy as np

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
    
    def find_working_camera(self) -> Optional[int]:
        """Encuentra una cámara que funcione, probando índices de 0 a 9"""
        if self._working_camera_cache is not None:
            # Verificar si la cámara cached sigue funcionando
            try:
                test_cap = cv2.VideoCapture(self._working_camera_cache)
                if test_cap.isOpened():
                    ret, frame = test_cap.read()
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
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"Cámara encontrada en índice {i}")
                        cap.release()
                        self._working_camera_cache = i
                        return i
                    else:
                        cap.release()
                else:
                    cap.release()
            except Exception as e:
                continue
        
        print("No se encontró ninguna cámara funcional")
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
    
    def __del__(self):
        """Destructor para asegurar liberación de recursos"""
        try:
            self.release_camera()
        except:
            pass


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
