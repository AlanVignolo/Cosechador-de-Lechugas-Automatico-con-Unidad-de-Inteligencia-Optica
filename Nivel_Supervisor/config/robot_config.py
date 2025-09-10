class RobotConfig:
    # =================================
    # CONFIGURACIÓN PRINCIPAL DEL ROBOT
    # =================================
    
    # ---- INVERSIÓN DE EJES ----
    # Cambiar estas flags para invertir direcciones sin modificar código
    X_AXIS_INVERTED = True   # True = invertir eje X (izquierda es positivo)
    Y_AXIS_INVERTED = False  # False = normal (arriba es negativo)
    
    # ---- PLATAFORMA ----
    # Cambiar esta variable para alternar entre plataformas
    PLATFORM = 'RASPBERRY_PI'  # 'WINDOWS' o 'RASPBERRY_PI'
    
    # ---- COMUNICACIÓN ----
    # Puertos seriales por plataforma
    SERIAL_PORTS = {
        'WINDOWS': 'COM15',
        'RASPBERRY_PI': '/dev/ttyUSB0'  # o /dev/ttyACM0 dependiendo del adaptador
    }
    
    BAUD_RATE = 115200
    TIMEOUT = 2.0
    
    # ---- CONVERSIONES MECÁNICAS ----
    STEPS_PER_MM_H = 40.0   # pasos por mm horizontal
    STEPS_PER_MM_V = 200.0  # pasos por mm vertical
    
    # ---- VELOCIDADES (pasos/segundo) ----
    NORMAL_SPEED_H = 8000
    NORMAL_SPEED_V = 12000
    HOMING_SPEED_H = 3000   # Velocidad lenta para homing
    HOMING_SPEED_V = 8000
    
    # ---- HOMING ----
    HOMING_DISTANCE_H = 3000  # mm de movimiento para homing
    HOMING_DISTANCE_V = 5000  # mm de movimiento para homing
    HOME_OFFSET_H = 10        # mm de offset desde límites
    HOME_OFFSET_V = 10        # mm de offset desde límites
    
    # ---- WORKSPACE ----
    MAX_X = 1800  # mm
    MAX_Y = 1000  # mm
    
    # ---- LOGGING Y DEBUG ----
    VERBOSE_LOGGING = False   # Reducir mensajes spam
    SHOW_UART_EVENTS = False  # Mostrar eventos UART detallados
    SHOW_MOVEMENT_COMPLETE = True  # Mostrar completado de movimientos
    
    # =================================
    # MÉTODOS AUXILIARES PARA DIRECCIONES
    # =================================
    
    @classmethod
    def apply_x_direction(cls, distance):
        """Aplica inversión de eje X si está habilitada"""
        return distance if not cls.X_AXIS_INVERTED else -distance
    
    @classmethod
    def apply_y_direction(cls, distance):
        """Aplica inversión de eje Y si está habilitada"""
        return distance if not cls.Y_AXIS_INVERTED else -distance
    
    @classmethod
    def get_homing_direction_x(cls):
        """Dirección para ir hacia límite derecho (considerando inversión)"""
        # Queremos ir hacia la DERECHA (límite RIGHT)
        return cls.apply_x_direction(-cls.HOMING_DISTANCE_H)
    
    @classmethod
    def get_homing_direction_y(cls):
        """Dirección para ir hacia límite superior (considerando inversión)"""
        # Queremos ir hacia ARRIBA (límite UP)
        return cls.apply_y_direction(-cls.HOMING_DISTANCE_V)
    
    @classmethod
    def get_home_offset_x(cls):
        """Offset desde límite derecho hacia izquierda (considerando inversión)"""
        # Offset hacia la IZQUIERDA desde límite derecho
        return cls.apply_x_direction(cls.HOME_OFFSET_H)
    
    @classmethod
    def get_home_offset_y(cls):
        """Offset desde límite superior hacia abajo (considerando inversión)"""
        # Offset hacia ABAJO desde límite superior
        return cls.apply_y_direction(cls.HOME_OFFSET_V)
    
    @classmethod
    def get_workspace_measure_direction_x(cls):
        """Dirección para medir workspace horizontal (hacia izquierda)"""
        # Para medir, vamos hacia la IZQUIERDA (límite LEFT)
        return cls.apply_x_direction(cls.HOMING_DISTANCE_H)
    
    @classmethod
    def get_workspace_measure_direction_y(cls):
        """Dirección para medir workspace vertical (hacia abajo)"""
        # Para medir, vamos hacia ABAJO (límite DOWN)
        return cls.apply_y_direction(cls.HOMING_DISTANCE_V)
    
    @classmethod
    def display_x_position(cls, internal_x):
        """Convierte posición interna X a valor mostrado al usuario"""
        return -internal_x if cls.X_AXIS_INVERTED else internal_x
    
    @classmethod
    def display_y_position(cls, internal_y):
        """Convierte posición interna Y a valor mostrado al usuario"""
        return -internal_y if cls.Y_AXIS_INVERTED else internal_y
    
    @classmethod
    def display_x_distance(cls, internal_distance):
        """Convierte distancia interna X a valor mostrado al usuario"""
        return -internal_distance if cls.X_AXIS_INVERTED else internal_distance
    
    @classmethod
    def display_y_distance(cls, internal_distance):
        """Convierte distancia interna Y a valor mostrado al usuario"""
        return -internal_distance if cls.Y_AXIS_INVERTED else internal_distance
    
    # =================================
    # MÉTODOS AUXILIARES PARA PLATAFORMA
    # =================================
    
    @classmethod
    def get_serial_port(cls):
        """Obtiene el puerto serial apropiado según la plataforma configurada"""
        return cls.SERIAL_PORTS.get(cls.PLATFORM, cls.SERIAL_PORTS['WINDOWS'])
    
    @classmethod
    def auto_detect_platform(cls):
        """Detecta automáticamente la plataforma y actualiza PLATFORM"""
        import platform
        system = platform.system().lower()
        
        if system == 'windows':
            cls.PLATFORM = 'WINDOWS'
        elif system == 'linux':
            # En Raspberry Pi también es Linux
            cls.PLATFORM = 'RASPBERRY_PI'
        else:
            # Fallback a Windows por defecto
            cls.PLATFORM = 'WINDOWS'
        
        return cls.PLATFORM
    
    @classmethod
    def get_platform_info(cls):
        """Obtiene información de la plataforma actual"""
        import platform
        return {
            'configured_platform': cls.PLATFORM,
            'detected_system': platform.system(),
            'serial_port': cls.get_serial_port(),
            'auto_detect_result': cls.auto_detect_platform() if hasattr(cls, '_temp_auto_detect') else None
        }

# =================================
# CONFIGURACIÓN PARA IA Y CORRECCIÓN DE POSICIÓN
# =================================

# Parámetros para corrección de posición basada en IA
AI_TEST_PARAMS = {
    'camera_index': 0,  # Cámara disponible en índice 0
    'max_iterations': 10,
    'tolerance_mm': 1.0,
    'offset_x_mm': 40.0,  # Offset horizontal en milÃ­metros
    'offset_y_mm': -5.0   # Offset vertical en milÃ­metros
}