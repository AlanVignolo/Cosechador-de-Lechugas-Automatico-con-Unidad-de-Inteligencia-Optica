# Estados base del brazo
ARM_STATES = {
    "movimiento": {
        "servo1": 10,
        "servo2": 10,
        "gripper": "any"
    },
    
    "recoger_lechuga": {
        "servo1": 100,
        "servo2": 80,
        "gripper": "open"
    },
    
    "mover_lechuga": {
        "servo1": 50,
        "servo2": 160,
        "gripper": "closed"
    },
    
    "depositar_lechuga": {
        "description": "Posición para soltar lechuga",
        "servo1": 90,
        "servo2": 20,
        "gripper": "open"
    }
}

# Configuración de tiempos
MOVEMENT_TIMING = {
    "gripper_open_time": 2.0,     # segundos para abrir gripper
    "gripper_close_time": 2.0,    # segundos para cerrar gripper
    "arm_move_buffer": 0.5,       # tiempo extra después de movimiento
    "safety_delay": 0.3,          # delay entre pasos
    "default_move_time": 1000     # tiempo por defecto para movimientos (ms)
}