class RobotConfig:
    # Comunicación
    SERIAL_PORT = 'COM15'  # Configurar según sistema
    BAUD_RATE = 115200
    TIMEOUT = 2.0
    
    # Conversiones mecánicas
    STEPS_PER_MM_H = 40.0  # pasos por mm horizontal
    STEPS_PER_MM_V = 200.0  # pasos por mm vertical
    
    # Velocidades (pasos/segundo)
    NORMAL_SPEED_H = 8000
    NORMAL_SPEED_V = 12000
    HOMING_SPEED_H = 3000   # Velocidad lenta para homing
    HOMING_SPEED_V = 8000
    
    # Homing
    HOMING_DISTANCE_H = 3000  # mm, moverse hacia la DERECHA (X positivo)
    HOMING_DISTANCE_V = 5000  # mm, moverse hacia ARRIBA (Y negativo)
    HOME_OFFSET_H = 10        # mm, offset hacia la IZQUIERDA desde límite derecho (X negativo)
    HOME_OFFSET_V = 10        # mm, offset hacia ABAJO desde límite superior (Y positivo)
    
    # Límites del workspace
    MAX_X = 1800  # mm
    MAX_Y = 1000  # mm