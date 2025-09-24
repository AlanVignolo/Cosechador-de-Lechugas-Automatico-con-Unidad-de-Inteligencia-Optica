from .arm_states import ARM_STATES, MOVEMENT_TIMING

class TrajectoryDefinitions:
    """Definición de todas las trayectorias del brazo"""
    
    @staticmethod
    def get_trajectory(from_state: str, to_state: str, lechuga_on: bool = True) -> dict:
        """Obtener trayectoria entre dos estados
        
        Args:
            from_state: Estado origen
            to_state: Estado destino
            lechuga_on: True si el robot tiene lechuga, False si no la tiene
        """
        # Caso especial: mover_lechuga -> recoger_lechuga depende de lechuga_on
        if from_state == "mover_lechuga" and to_state == "recoger_lechuga":
            if lechuga_on:
                # Tiene lechuga: usar trayectoria normal (depositar)
                return TrajectoryDefinitions.mover_lechuga_to_recoger_lechuga_with_lettuce()
            else:
                # No tiene lechuga: usar trayectoria especial (recoger)
                return TrajectoryDefinitions.mover_lechuga_to_recoger_lechuga_no_lettuce()
        
        # Caso especial: recoger_lechuga -> mover_lechuga depende de lechuga_on
        if from_state == "recoger_lechuga" and to_state == "mover_lechuga":
            if lechuga_on:
                # Tiene lechuga: usar trayectoria normal (ya existe)
                return TrajectoryDefinitions.recoger_lechuga_to_mover_lechuga()
            else:
                # No tiene lechuga: usar trayectoria especial (nueva)
                return TrajectoryDefinitions.recoger_lechuga_to_mover_lechuga_no_lettuce()
        
        trajectory_name = f"{from_state}_to_{to_state}"
        
        # Buscar trayectoria específica
        if hasattr(TrajectoryDefinitions, trajectory_name):
            return getattr(TrajectoryDefinitions, trajectory_name)()
        
        # Buscar trayectoria genérica (any_to_X)
        generic_name = f"any_to_{to_state}"
        if hasattr(TrajectoryDefinitions, generic_name):
            return getattr(TrajectoryDefinitions, generic_name)()
        
        return None
    
    @staticmethod
    def get_available_trajectories() -> list:
        """Listar todas las trayectorias disponibles"""
        methods = [method for method in dir(TrajectoryDefinitions) 
                  if not method.startswith('_') and 'to_' in method]
        return methods

    # ===============================================
    # TRAYECTORIAS DINÁMICAS (usan ARM_STATES)
    # ===============================================
    
    @staticmethod
    def movimiento_to_recoger_lechuga():
        """Ir de posición segura a recoger lechuga"""
        target_state = ARM_STATES["recoger_lechuga"]
        
        return {
            "name": "movimiento_to_recoger_lechuga",
            "description": "Secuencia para ir a recoger una lechuga",
            "estimated_time": 4.5,
            "steps": [
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "Asegurar gripper abierto antes de mover"
                },
                {
                    "type": "arm_move",
                    "servo1": 0,
                    "servo2": 120,
                    "time_ms": 1500,
                    "description": "Elevar brazo a posición intermedia"
                },
                {
                    "type": "arm_move", 
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 1500,
                    "description": "Extender a posición de recolección"
                },
                {
                    "type": "gripper",
                    "action": "close",
                    "description": "CERRAR gripper para agarrar lechuga (AL FINAL)"
                }
            ]
        }

    @staticmethod
    def any_to_movimiento():
        """Ir a posición segura desde cualquier estado"""
        target_state = ARM_STATES["movimiento"]
        
        return {
            "name": "any_to_movimiento",
            "description": "Retornar a posición segura para movimiento X-Y",
            "estimated_time": 2.5,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 4000,
                    "description": "Retraer brazo a posición segura"
                },
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "ABRIR gripper al llegar a posición segura"
                }
            ]
        }
        
    @staticmethod
    def any_to_mover_lechuga():
        """Ir a posición segura desde cualquier estado"""
        target_state = ARM_STATES["mover_lechuga"]
        
        return {
            "name": "any_to_mover_lechuga",
            "description": "Ir a posición de transporte (con lechuga)",
            "estimated_time": 1,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 4000,
                    "description": "Retraer brazo a posición segura"
                }
            ]
        }

    @staticmethod
    def recoger_lechuga_to_mover_lechuga():
        """Cambiar a posición de transporte (gripper ya está cerrado)"""
        target_state = ARM_STATES["mover_lechuga"]
        initial_state = ARM_STATES["recoger_lechuga"]
        return {
            "name": "recoger_lechuga_to_mover_lechuga",
            "description": "Ir directamente a posición de transporte (con lechuga)",
            "estimated_time": 1.5,
            "steps": [
                # {
                #     "type": "arm_move",
                #     "servo1": initial_state["servo1"] - abs((initial_state["servo1"]-target_state["servo1"])/2),
                #     "servo2": target_state["servo2"],
                #     "time_ms": 1000,
                #     "description": "Mover a posición de transporte seguro - 1er movimiento(gripper cerrado)"
                # },
                {
                    "type": "gripper",
                    "action": "close",
                    "description": "Cerrar gripper por las dudas"
                },
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 1500,
                    "description": "Mover a posición de transporte seguro - 2do movimiento (gripper cerrado)"
                }
            ]
        }

    @staticmethod
    def recoger_lechuga_to_mover_lechuga_no_lettuce():
        """Cambiar a posición de transporte (cuando NO tiene lechuga - gripper abierto)"""
        target_state = ARM_STATES["mover_lechuga"]
        initial_state = ARM_STATES["recoger_lechuga"]
        return {
            "name": "recoger_lechuga_to_mover_lechuga_no_lettuce",
            "description": "Ir a posición de transporte (SIN lechuga - gripper abierto)",
            "estimated_time": 1.5,
            "steps": [
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "Abrir gripper (no hay lechuga)"
                },
                {
                    "type": "arm_move",
                    "servo1": 0,
                    "servo2": 120,
                    "time_ms": 2500,
                    "description": "Elevar brazo a posición intermedia"
                },
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 1500,
                    "description": "Mover a posición de transporte (gripper abierto)"
                }
            ]
        }

    @staticmethod
    def mover_lechuga_to_depositar_lechuga():
        """Ir a posición para depositar lechuga"""
        target_state = ARM_STATES["depositar_lechuga"]
        
        return {
            "name": "mover_lechuga_to_depositar_lechuga", 
            "description": "Posicionar para soltar lechuga",
            "estimated_time": 3.0,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 5500,
                    "description": "Posicionar sobre zona de depósito"
                },
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "ABRIR gripper para soltar lechuga"
                }
            ]
        }
        
    @staticmethod
    def mover_lechuga_to_recoger_lechuga_with_lettuce():
        """Ir a posición para depositar lechuga (cuando SI tiene lechuga)"""
        target_state = ARM_STATES["recoger_lechuga"]
        
        return {
            "name": "mover_lechuga_to_recoger_lechuga_with_lettuce", 
            "description": "Posicionar para depositar lechuga (con lechuga)",
            "estimated_time": 3.0,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"] + 20,
                    "time_ms": 3000,
                    "description": "Posicionar sobre zona de depósito"
                },
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 1000,
                    "description": "Posicionar sobre zona de depósito"
                },
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "ABRIR gripper para soltar lechuga"
                }
            ]
        }
    
    @staticmethod
    def mover_lechuga_to_recoger_lechuga_no_lettuce():
        """Ir a posición para recoger lechuga (cuando NO tiene lechuga)"""
        target_state = ARM_STATES["recoger_lechuga"]
        
        return {
            "name": "mover_lechuga_to_recoger_lechuga_no_lettuce", 
            "description": "Posicionar para recoger lechuga (sin lechuga)",
            "estimated_time": 4.0,
            "steps": [
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "Asegurar gripper abierto antes de mover"
                },
                {
                    "type": "arm_move",
                    "servo1": 0,
                    "servo2": 120,
                    "time_ms": 2500,
                    "description": "Elevar brazo a posición intermedia"
                },
                {
                    "type": "arm_move",
                    "servo1": target_state["servo1"],
                    "servo2": target_state["servo2"],
                    "time_ms": 1500,
                    "description": "Extender a posición de recolección"
                },
                {
                    "type": "gripper",
                    "action": "close",
                    "description": "CERRAR gripper para agarrar lechuga"
                }
            ]
        }
    
    @staticmethod
    def any_to_recoger_lechuga():
        """Ir a recoger lechuga desde cualquier estado"""
        target_state = ARM_STATES["recoger_lechuga"]
        
        return {
            "name": "any_to_recoger_lechuga",
            "description": "Ir a recoger pasando por posición segura",
            "estimated_time": 6.0,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": 0,
                    "servo2": 0,
                    "time_ms": 4000,
                    "description": "Ir primero a posición segura"
                },
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "Asegurar gripper abierto"
                },
                {
                    "type": "arm_move",
                    "servo1": 0,
                    "servo2": 120,
                    "time_ms": 1000,
                    "description": "Elevar brazo"
                },
                {
                    "type": "arm_move", 
                    "servo1": target_state["servo1"],  # DINÁMICO
                    "servo2": target_state["servo2"],  # DINÁMICO
                    "time_ms": 1500,
                    "description": "Extender a posición de recolección"
                },
                {
                    "type": "gripper",
                    "action": "close",
                    "description": "Cerrar gripper"
                }
            ]
        }
    
    
    @staticmethod
    def recoger_lechuga_to_movimiento():
        """Ir de recoger lechuga a posición segura (inversa de movimiento_to_recoger_lechuga)"""
        safe_state = ARM_STATES["movimiento"]
        
        return {
            "name": "recoger_lechuga_to_movimiento",
            "description": "Retornar a posición segura desde recoger lechuga",
            "estimated_time": 4.0,
            "steps": [
                                {
                    "type": "gripper",
                    "action": "open",
                    "description": "Abrir gripper"
                },
                {
                    "type": "arm_move",
                    "servo1": 10,
                    "servo2": 120,
                    "time_ms": 3000,
                    "description": "Retraer a posición intermedia segura"
                },
                {
                    "type": "arm_move",
                    "servo1": safe_state["servo1"],  # 10
                    "servo2": safe_state["servo2"],  # 10
                    "time_ms": 4000,
                    "description": "Bajar a posición segura final"
                }
            ]
        }
    @staticmethod
    def mover_lechuga_to_movimiento():
        """Ir de mover lechuga a posición segura"""
        safe_state = ARM_STATES["movimiento"]

        return {
            "name": "mover_lechuga_to_movimiento",
            "description": "Ir a posición segura desde transporte",
            "estimated_time": 3.0,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": 0,
                    "servo2": 90,
                    "time_ms": 3000,
                    "description": "Ir a posición intermedia"
                },
                {
                    "type": "arm_move",
                    "servo1": safe_state["servo1"],
                    "servo2": safe_state["servo2"],
                    "time_ms": 3000,
                    "description": "Llegar a posición segura"
                },
                {
                    "type": "gripper",
                    "action": "open",
                    "description": "Abrir gripper en posición segura"
                }
            ]
        }

    @staticmethod
    def depositar_lechuga_to_movimiento():
        """Ir de depositar lechuga a posición segura"""
        safe_state = ARM_STATES["movimiento"]
        
        return {
            "name": "depositar_lechuga_to_movimiento",
            "description": "Ir a posición segura desde depósito",
            "estimated_time": 2.5,
            "steps": [
                {
                    "type": "arm_move",
                    "servo1": safe_state["servo1"],
                    "servo2": safe_state["servo2"],
                    "time_ms": 1500,
                    "description": "Ir directamente a posición segura"
                }
                # Gripper ya está abierto desde depositar, no necesita acción
            ]
        }

# ===============================================
# FUNCIONES UTILITARIAS
# ===============================================

def validate_trajectory(trajectory: dict) -> bool:
    """Validar que una trayectoria esté bien formada"""
    required_fields = ["name", "description", "steps"]
    
    for field in required_fields:
        if field not in trajectory:
            return False
    
    for step in trajectory["steps"]:
        if "type" not in step or "description" not in step:
            return False
        
        if step["type"] == "arm_move":
            required_arm_fields = ["servo1", "servo2", "time_ms"]
            if not all(field in step for field in required_arm_fields):
                return False
        
        elif step["type"] == "gripper":
            if "action" not in step or step["action"] not in ["open", "close"]:
                return False
    
    return True

def get_trajectory_time_estimate(trajectory: dict) -> float:
    """Calcular tiempo estimado de una trayectoria"""
    if "estimated_time" in trajectory:
        return trajectory["estimated_time"]
    
    # Calcular basado en los pasos
    total_time = 0
    for step in trajectory["steps"]:
        if step["type"] == "arm_move":
            total_time += (step["time_ms"] / 1000.0) + MOVEMENT_TIMING["arm_move_buffer"]
        elif step["type"] == "gripper":
            if step["action"] == "open":
                total_time += MOVEMENT_TIMING["gripper_open_time"]
            else:
                total_time += MOVEMENT_TIMING["gripper_close_time"]
        
        total_time += MOVEMENT_TIMING["safety_delay"]
    
    return total_time

def list_all_states() -> list:
    """Listar todos los estados disponibles"""
    return list(ARM_STATES.keys())

def list_all_trajectories() -> list:
    """Listar todas las trayectorias disponibles"""
    return TrajectoryDefinitions.get_available_trajectories()