class RobotConfig:
    # Inversión de ejes
    X_AXIS_INVERTED = False  # False = normal (izquierda positivo)
    Y_AXIS_INVERTED = False  # False = normal (arriba negativo)

    # Plataforma
    PLATFORM = 'RASPBERRY_PI'  # 'WINDOWS' o 'RASPBERRY_PI'

    # Puertos seriales
    SERIAL_PORTS = {
        'WINDOWS': 'COM15',
        'RASPBERRY_PI': '/dev/ttyUSB0'
    }

    BAUD_RATE = 115200
    TIMEOUT = 2.0

    # Conversiones mecánicas
    STEPS_PER_MM_H = 40.0
    STEPS_PER_MM_V = 200.0

    # Velocidades (pasos/segundo)
    NORMAL_SPEED_H = 10000
    NORMAL_SPEED_V = 15000
    HOMING_SPEED_H = 3000
    HOMING_SPEED_V = 8000

    # Homing
    HOMING_DISTANCE_H = 3000  # mm
    HOMING_DISTANCE_V = 5000  # mm
    HOME_OFFSET_H = 10  # mm desde límites
    HOME_OFFSET_V = 10  # mm desde límites

    # Workspace
    MAX_X = 1800  # mm
    MAX_Y = 1000  # mm

    # Logging
    VERBOSE_LOGGING = False
    SHOW_UART_EVENTS = False
    SHOW_MOVEMENT_COMPLETE = True

    # Snapshots (debe coincidir con firmware)
    MAX_SNAPSHOTS = 30

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
        """Dirección hacia límite derecho"""
        return cls.apply_x_direction(-cls.HOMING_DISTANCE_H)

    @classmethod
    def get_homing_direction_y(cls):
        """Dirección hacia límite superior"""
        return cls.apply_y_direction(-cls.HOMING_DISTANCE_V)

    @classmethod
    def get_home_offset_x(cls):
        """Offset desde límite derecho hacia izquierda"""
        return cls.apply_x_direction(cls.HOME_OFFSET_H)

    @classmethod
    def get_home_offset_y(cls):
        """Offset desde límite superior hacia abajo"""
        return cls.apply_y_direction(cls.HOME_OFFSET_V)

    @classmethod
    def get_workspace_measure_direction_x(cls):
        """Dirección para medir workspace horizontal"""
        return cls.apply_x_direction(cls.HOMING_DISTANCE_H)

    @classmethod
    def get_workspace_measure_direction_y(cls):
        """Dirección para medir workspace vertical"""
        return cls.apply_y_direction(cls.HOMING_DISTANCE_V)

    @classmethod
    def display_x_position(cls, internal_x):
        """Convierte posición interna X a valor mostrado"""
        return -internal_x if cls.X_AXIS_INVERTED else internal_x

    @classmethod
    def display_y_position(cls, internal_y):
        """Convierte posición interna Y a valor mostrado"""
        return -internal_y if cls.Y_AXIS_INVERTED else internal_y

    @classmethod
    def display_x_distance(cls, internal_distance):
        """Convierte distancia interna X a valor mostrado"""
        return -internal_distance if cls.X_AXIS_INVERTED else internal_distance

    @classmethod
    def display_y_distance(cls, internal_distance):
        """Convierte distancia interna Y a valor mostrado"""
        return -internal_distance if cls.Y_AXIS_INVERTED else internal_distance

    @classmethod
    def get_serial_port(cls):
        """Obtiene el puerto serial según plataforma"""
        return cls.SERIAL_PORTS.get(cls.PLATFORM, cls.SERIAL_PORTS['WINDOWS'])

    @classmethod
    def auto_detect_platform(cls):
        """Detecta automáticamente la plataforma"""
        import platform
        system = platform.system().lower()

        if system == 'windows':
            cls.PLATFORM = 'WINDOWS'
        elif system == 'linux':
            cls.PLATFORM = 'RASPBERRY_PI'
        else:
            cls.PLATFORM = 'WINDOWS'

        return cls.PLATFORM

    @classmethod
    def get_platform_info(cls):
        """Información de la plataforma actual"""
        import platform
        return {
            'configured_platform': cls.PLATFORM,
            'detected_system': platform.system(),
            'serial_port': cls.get_serial_port(),
            'auto_detect_result': cls.auto_detect_platform() if hasattr(cls, '_temp_auto_detect') else None
        }

# Parámetros para corrección de posición con IA
AI_TEST_PARAMS = {
    'camera_index': 0,
    'max_iterations': 10,
    'tolerance_mm': 1.0,
    'offset_x_mm': -40.0,
    'offset_y_mm': -8.0
}
