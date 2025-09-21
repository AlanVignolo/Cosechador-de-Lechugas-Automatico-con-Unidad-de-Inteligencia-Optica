import logging
import threading
import time
import sys
import os
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple
from datetime import datetime

# Agregar directorios al path para importaciones
current_dir = os.path.dirname(os.path.abspath(__file__))
nivel_supervisor_dir = os.path.dirname(current_dir)
if nivel_supervisor_dir not in sys.path:
    sys.path.insert(0, nivel_supervisor_dir)

from controller.robot_controller import RobotController
from controller.command_manager import CommandManager
from config.robot_config import RobotConfig

# Agregar path para los módulos de IA
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Analizar Cultivo'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Escaner Horizontal'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor_IA', 'Escaner Vertical'))

# Importar módulos de configuración (siempre necesarios)
try:
    from configuracion_tubos import config_tubos
    from matriz_cintas import matriz_cintas
    CONFIG_MODULES_AVAILABLE = True
    print("✅ Módulos de configuración importados")
except ImportError as e:
    print(f"❌ Error importando módulos de configuración: {e}")
    CONFIG_MODULES_AVAILABLE = False
    # Crear módulos dummy básicos si no están disponibles
    class DummyConfig:
        @staticmethod
        def obtener_configuracion_tubos():
            return {1: {"nombre": "Tubo 1", "y_mm": 300}, 2: {"nombre": "Tubo 2", "y_mm": 600}}
        @staticmethod
        def hay_configuracion_desde_escaner():
            return False
    
    class DummyMatriz:
        @staticmethod
        def obtener_cintas_tubo(tubo_id):
            return []
        @staticmethod
        def obtener_todas_cintas():
            return {}
    
    config_tubos = DummyConfig()
    matriz_cintas = DummyMatriz()

# Importar funciones de IA (opcionales)
try:
    from tape_detector_horizontal import get_horizontal_correction_distance
    from tape_detector_vertical import get_vertical_correction_distance
    IA_CORRECTION_AVAILABLE = True
    print("✅ Módulos de corrección IA importados")
except ImportError as e:
    print(f"⚠️ Módulos de corrección IA no disponibles: {e}")
    IA_CORRECTION_AVAILABLE = False
    # Funciones dummy para corrección
    def get_horizontal_correction_distance(camera_index=0):
        return {'success': False, 'distance_pixels': 0, 'error': 'Módulo no disponible'}
    def get_vertical_correction_distance(camera_index=0):
        return {'success': False, 'distance_pixels': 0, 'error': 'Módulo no disponible'}

# Importar funciones de escáner (opcionales)
try:
    from escaner_standalone import scan_horizontal_with_live_camera
    from escaner_vertical import scan_vertical_manual
    SCANNER_MODULES_AVAILABLE = True
    print("✅ Módulos de escáner importados")
except ImportError as e:
    print(f"⚠️ Módulos de escáner no disponibles: {e}")
    SCANNER_MODULES_AVAILABLE = False
    # Funciones dummy para escáneres
    def scan_horizontal_with_live_camera(robot):
        print("⚠️ Escáner horizontal no disponible - simulando éxito")
        return True
    def scan_vertical_manual(robot):
        print("⚠️ Escáner vertical no disponible - simulando éxito")
        return True

class RobotState(Enum):
    """Estados de la máquina de estados del robot"""
    IDLE = "idle"
    HOMING = "homing"
    MAPEO_CULTIVO = "mapeo_cultivo"
    MAPEO_RECURSOS = "mapeo_recursos"
    CICLO_COSECHA = "ciclo_cosecha"
    ALINEADO_FINO = "alineado_fino"
    COSECHANDO = "cosechando"
    PLANTANDO = "plantando"
    MOVIENDO_A_CESTO = "moviendo_a_cesto"
    ERROR = "error"

class LettuceState(Enum):
    """Estados de las lechugas"""
    SIN_PLANTA = "sin_planta"
    NO_LISTA = "no_lista"
    LISTA = "lista"
    COSECHADA = "cosechada"

@dataclass
class RobotStatistics:
    """Estadísticas del robot"""
    inicio_total_timestamp: Optional[str] = None
    lechugas_cosechadas: int = 0
    plantines_plantados: int = 0
    total_tubos_procesados: int = 0
    tiempo_total_operacion: float = 0.0
    errores_recuperados: int = 0
    
    def reset_totals(self):
        """Resetear contadores para inicio total"""
        self.inicio_total_timestamp = datetime.now().isoformat()
        self.lechugas_cosechadas = 0
        self.plantines_plantados = 0
        self.total_tubos_procesados = 0
        self.tiempo_total_operacion = 0.0
        self.errores_recuperados = 0

@dataclass
class ResourcePositions:
    """Posiciones de recursos auxiliares"""
    plantines: Optional[Tuple[float, float]] = None  # (x, y)
    cesto: Optional[Tuple[float, float]] = None      # (x, y)
    
    def has_all_resources(self) -> bool:
        """Verificar si tenemos todas las posiciones de recursos"""
        return self.plantines is not None and self.cesto is not None


class RobotStateMachine:
    """Máquina de estados principal del robot CLAUDIO"""
    
    def __init__(self, robot: RobotController):
        self.robot = robot
        self.logger = logging.getLogger(__name__)
        
        # Estado actual
        self.current_state = RobotState.IDLE
        self.state_start_time = time.time()
        
        # Datos del sistema
        self.statistics = RobotStatistics()
        self.resources = ResourcePositions()
        self.current_tube_index = 0
        self.current_lettuce_index = 0
        
        # Configuración
        self.alignment_tolerance_mm = 1.0
        self.max_alignment_iterations = 5
        
        # Persistencia
        self.state_file = os.path.join(os.path.dirname(__file__), "robot_state_data.json")
        self._load_state_data()
        
        # Control de operación
        self.operation_active = False
        self.stop_requested = threading.Event()
    
    def _load_state_data(self):
        """Cargar datos persistentes del estado"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Cargar estadísticas
                if 'statistics' in data:
                    stats_data = data['statistics']
                    self.statistics = RobotStatistics(**stats_data)
                
                # Cargar posiciones de recursos
                if 'resources' in data:
                    res_data = data['resources']
                    self.resources = ResourcePositions(
                        plantines=tuple(res_data['plantines']) if res_data.get('plantines') else None,
                        cesto=tuple(res_data['cesto']) if res_data.get('cesto') else None
                    )
                    
        except Exception as e:
            self.logger.warning(f"Error cargando datos de estado: {e}")
    
    def _save_state_data(self):
        """Guardar datos persistentes del estado"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'current_state': self.current_state.value,
                'statistics': {
                    'inicio_total_timestamp': self.statistics.inicio_total_timestamp,
                    'lechugas_cosechadas': self.statistics.lechugas_cosechadas,
                    'plantines_plantados': self.statistics.plantines_plantados,
                    'total_tubos_procesados': self.statistics.total_tubos_procesados,
                    'tiempo_total_operacion': self.statistics.tiempo_total_operacion,
                    'errores_recuperados': self.statistics.errores_recuperados
                },
                'resources': {
                    'plantines': list(self.resources.plantines) if self.resources.plantines else None,
                    'cesto': list(self.resources.cesto) if self.resources.cesto else None
                }
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Error guardando datos de estado: {e}")
    
    def transition_to(self, new_state: RobotState):
        """Transición segura entre estados"""
        self.logger.info(f"Transición: {self.current_state.value} → {new_state.value}")
        self.current_state = new_state
        self.state_start_time = time.time()
        self._save_state_data()
    
    def get_status(self) -> Dict:
        """Obtener estado completo del sistema"""
        return {
            'current_state': self.current_state.value,
            'operation_active': self.operation_active,
            'robot_status': self.robot.get_status(),
            'statistics': {
                'inicio_total': self.statistics.inicio_total_timestamp,
                'lechugas_cosechadas': self.statistics.lechugas_cosechadas,
                'plantines_plantados': self.statistics.plantines_plantados,
                'tubos_procesados': self.statistics.total_tubos_procesados,
                'tiempo_operacion': self.statistics.tiempo_total_operacion,
                'errores_recuperados': self.statistics.errores_recuperados
            },
            'resources': {
                'plantines': self.resources.plantines,
                'cesto': self.resources.cesto,
                'all_mapped': self.resources.has_all_resources()
            },
            'tubes_config': config_tubos.obtener_configuracion_tubos(),
            'current_progress': {
                'tube_index': self.current_tube_index,
                'lettuce_index': self.current_lettuce_index
            }
        }
    
    # =============================================================================
    # MÉTODOS PRINCIPALES DE LA INTERFAZ DE USUARIO
    # =============================================================================
    
    def inicio_total(self) -> bool:
        """
        Secuencia completa: Homing + Mapeo de Cultivo + Mapeo de Recursos + Ciclo de Cosecha
        """
        print("\n" + "="*60)
        print("🚀 INICIO TOTAL - SECUENCIA COMPLETA")
        print("="*60)
        print("Esta secuencia realizará:")
        print("1. Homing y calibración del workspace")
        print("2. Mapeo de cultivo (detección de tubos y lechugas)")
        print("3. Mapeo de recursos (plantines y cesto)")
        print("4. Ciclo de cosecha automatizado")
        print("-"*60)
        
        # Resetear estadísticas
        self.statistics.reset_totals()
        operation_start = time.time()
        
        try:
            # 1. HOMING
            if not self._execute_homing():
                return False
            
            # 2. MAPEO DE CULTIVO
            if not self._execute_mapeo_cultivo():
                return False
            
            # 3. MAPEO DE RECURSOS
            if not self._execute_mapeo_recursos():
                return False
            
            # 4. CICLO DE COSECHA
            if not self._execute_ciclo_cosecha():
                return False
            
            # Finalización exitosa
            self.statistics.tiempo_total_operacion = time.time() - operation_start
            self.transition_to(RobotState.IDLE)
            
            print("\n✅ INICIO TOTAL COMPLETADO EXITOSAMENTE")
            print(f"⏱️ Tiempo total: {self.statistics.tiempo_total_operacion:.1f} segundos")
            print(f"🥬 Lechugas cosechadas: {self.statistics.lechugas_cosechadas}")
            print(f"🌱 Plantines plantados: {self.statistics.plantines_plantados}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en inicio total: {e}")
            self.transition_to(RobotState.ERROR)
            return False
    
    def escaner_diario(self) -> bool:
        """
        Escaneo diario: Solo ciclo de cosecha usando mapeo existente
        """
        print("\n" + "="*60)
        print("🔄 ESCANER DIARIO - CICLO DE COSECHA")
        print("="*60)
        print("Usando configuración existente de tubos y recursos")
        
        # Verificar que tenemos la configuración necesaria
        if not config_tubos.hay_configuracion_desde_escaner():
            print("⚠️ No hay configuración de tubos desde escáner vertical")
            print("Se recomienda ejecutar 'inicio_total' primero")
            if input("¿Continuar de todas formas? (s/N): ").lower() != 's':
                return False
        
        if not self.resources.has_all_resources():
            print("⚠️ No hay posiciones de recursos mapeadas")
            print("Se recomienda ejecutar 'inicio_total' primero")
            if input("¿Continuar de todas formas? (s/N): ").lower() != 's':
                return False
        
        try:
            # Verificar homing
            if not self.robot.is_homed:
                print("🏠 Robot necesita homing...")
                if not self._execute_homing():
                    return False
            
            # Ejecutar ciclo de cosecha
            operation_start = time.time()
            if not self._execute_ciclo_cosecha():
                return False
            
            # Estadísticas
            operation_time = time.time() - operation_start
            self.statistics.tiempo_total_operacion += operation_time
            
            print("\n✅ ESCANER DIARIO COMPLETADO")
            print(f"⏱️ Tiempo: {operation_time:.1f} segundos")
            print(f"🥬 Lechugas procesadas hoy: {self.statistics.lechugas_cosechadas}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en escaner diario: {e}")
            self.transition_to(RobotState.ERROR)
            return False
    
    def mostrar_datos(self):
        """
        Mostrar debug completo del sistema
        """
        print("\n" + "="*80)
        print("📊 DATOS COMPLETOS DEL SISTEMA CLAUDIO")
        print("="*80)
        
        # Estado del robot
        robot_status = self.robot.get_status()
        print(f"\n🤖 ESTADO DEL ROBOT:")
        print(f"   Estado actual: {self.current_state.value}")
        print(f"   Homed: {'✅ SÍ' if robot_status['homed'] else '❌ NO'}")
        print(f"   Posición: X={robot_status['position']['x']:.1f}mm, Y={robot_status['position']['y']:.1f}mm")
        print(f"   Brazo: {robot_status['arm']}")
        print(f"   Gripper: {robot_status['gripper']}")
        
        # Hardware status
        print(f"\n💻 HARDWARE:")
        try:
            from camera_manager import get_camera_manager
            camera_mgr = get_camera_manager()
            print(f"   Cámara: {'✅ OK' if camera_mgr.is_initialized else '❌ ERROR'}")
        except:
            print(f"   Cámara: ❓ NO DISPONIBLE")
        
        print(f"   Robot: {'✅ OK' if robot_status['homed'] else '⚠️ SIN HOMING'}")
        
        # Configuración de tubos
        print(f"\n🌿 CONFIGURACIÓN DE TUBOS:")
        tubos_config = config_tubos.obtener_configuracion_tubos()
        num_tubos = len(tubos_config)
        print(f"   Número de tubos: {num_tubos}")
        print(f"   Fuente: {'Escáner vertical' if config_tubos.hay_configuracion_desde_escaner() else 'Por defecto'}")
        
        for tubo_id, config in tubos_config.items():
            print(f"   {config['nombre']}: Y={config['y_mm']}mm")
        
        # Matriz de plantas
        print(f"\n🥬 MATRIZ DE PLANTAS:")
        todas_cintas = matriz_cintas.obtener_todas_cintas()
        total_plantas = 0
        
        for tubo_id, data in todas_cintas.items():
            num_plantas = len(data['cintas'])
            total_plantas += num_plantas
            print(f"   {data['nombre']}: {num_plantas} plantas detectadas")
            
            if num_plantas > 0:
                for cinta in data['cintas'][:3]:  # Mostrar solo las primeras 3
                    print(f"      - X={cinta['x_mm']}mm, Y={cinta['y_mm']}mm")
                if num_plantas > 3:
                    print(f"      ... y {num_plantas - 3} más")
        
        print(f"   TOTAL: {total_plantas} plantas en matriz")
        
        # Recursos
        print(f"\n🛠️ RECURSOS:")
        if self.resources.plantines:
            print(f"   Plantines: X={self.resources.plantines[0]:.1f}mm, Y={self.resources.plantines[1]:.1f}mm")
        else:
            print(f"   Plantines: ❌ NO MAPEADOS")
            
        if self.resources.cesto:
            print(f"   Cesto: X={self.resources.cesto[0]:.1f}mm, Y={self.resources.cesto[1]:.1f}mm")
        else:
            print(f"   Cesto: ❌ NO MAPEADO")
        
        # Estadísticas
        print(f"\n📈 ESTADÍSTICAS:")
        if self.statistics.inicio_total_timestamp:
            print(f"   Último inicio total: {self.statistics.inicio_total_timestamp}")
        else:
            print(f"   Inicio total: ❌ NUNCA EJECUTADO")
            
        print(f"   Lechugas cosechadas: {self.statistics.lechugas_cosechadas}")
        print(f"   Plantines plantados: {self.statistics.plantines_plantados}")
        print(f"   Tubos procesados: {self.statistics.total_tubos_procesados}")
        print(f"   Tiempo total de operación: {self.statistics.tiempo_total_operacion:.1f}s")
        print(f"   Errores recuperados: {self.statistics.errores_recuperados}")
        
        # Workspace
        workspace = getattr(self.robot, 'workspace_limits', None)
        if workspace:
            print(f"\n📐 WORKSPACE:")
            print(f"   Horizontal: {workspace.get('horizontal_mm', 'N/A')}mm")
            print(f"   Vertical: {workspace.get('vertical_mm', 'N/A')}mm")
        
        print("="*80)
    
    # =============================================================================
    # MÉTODOS INTERNOS DE EJECUCIÓN (SIMPLIFICADOS)
    # =============================================================================
    
    def _execute_homing(self) -> bool:
        """Ejecutar homing COMPLETO con calibración del workspace"""
        self.transition_to(RobotState.HOMING)
        print("\n🏠 EJECUTANDO HOMING COMPLETO (CON CALIBRACIÓN DEL WORKSPACE)...")
        
        try:
            # Solo hacer homing completo (incluye básico + calibración)
            result = self.robot.calibrate_workspace()
            if not result["success"]:
                print(f"❌ Error en homing completo: {result['message']}")
                return False
            
            print("✅ Homing completo realizado")
            
            # Forzar actualización del workspace desde el robot
            workspace = getattr(self.robot, 'workspace_limits', {})
            if not workspace:
                # Si no está disponible, intentar obtenerlo directamente
                self.robot._update_workspace_limits()
                workspace = getattr(self.robot, 'workspace_limits', {})
            
            print(f"📐 Workspace medido: H={workspace.get('horizontal_mm', 'N/A')}mm, V={workspace.get('vertical_mm', 'N/A')}mm")
            
            # Verificar que el workspace se calibró correctamente
            if not workspace or workspace.get('horizontal_mm', 0) <= 0:
                print("❌ Error: El workspace no se calibró correctamente")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en homing completo: {e}")
            return False
    
    def _execute_mapeo_cultivo(self) -> bool:
        """Ejecutar mapeo de cultivo (tubos + lechugas)"""
        self.transition_to(RobotState.MAPEO_CULTIVO)
        print("\n🌿 EJECUTANDO MAPEO DE CULTIVO...")
        
        try:
            # 1. Detección de tubos (escáner vertical)
            print("📍 PASO 1: Detectando posiciones de tubos con IA vertical...")
            success = scan_vertical_manual(self.robot)
            if not success:
                print("❌ Error en escáner vertical")
                return False
            print("✅ Tubos detectados y configuración actualizada")
            
            # 2. Homing normal después del escáner vertical
            print("📍 PASO 2: Homing normal post-escáner...")
            result = self.robot.home_robot()
            if not result["success"]:
                print(f"❌ Error en homing post-escáner: {result['message']}")
                return False
            print("✅ Robot en origen (0,0)")
            
            # 3. Obtener configuración de tubos actualizada
            tubos_config = config_tubos.obtener_configuracion_tubos()
            print(f"📋 Tubos detectados: {len(tubos_config)}")
            
            # Verificar que se detectaron tubos
            if len(tubos_config) == 0:
                print("❌ No se detectaron tubos en el escáner vertical")
                print("🏠 Regresando al origen (0,0) y terminando secuencia...")
                
                # Regresar al origen
                current_pos = self.robot.get_status()['position']
                move_x = 0 - current_pos['x']
                move_y = 0 - current_pos['y']
                
                if abs(move_x) > 0.1 or abs(move_y) > 0.1:  # Solo mover si no estamos ya en origen
                    result = self.robot.cmd.move_xy(move_x, move_y)
                    if result["success"]:
                        self.robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=30.0)
                
                print("❌ MAPEO DE CULTIVO FALLÓ - NO HAY TUBOS DETECTADOS")
                return False
            
            # 4. Escaneado horizontal en cada tubo
            for tubo_id, config in tubos_config.items():
                print(f"\n🔍 PASO 3.{tubo_id}: Escaneando {config['nombre']}...")
                
                # Mover al tubo usando movimiento relativo
                current_pos = self.robot.get_status()['position']
                target_x = 0  # Siempre ir a X=0 para cada tubo
                target_y = config['y_mm']
                
                # Calcular movimiento relativo
                move_x = target_x - current_pos['x']
                move_y = target_y - current_pos['y']
                
                print(f"   📍 Moviendo a {config['nombre']}: relativo ({move_x:.1f}, {move_y:.1f})mm")
                result = self.robot.cmd.move_xy(move_x, move_y)
                if not result["success"]:
                    print(f"❌ Error moviendo a {config['nombre']}: {result}")
                    return False
                
                # Esperar que llegue
                if not self.robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=30.0):
                    print(f"❌ Timeout moviendo a {config['nombre']}")
                    return False
                
                # Hacer escáner horizontal con workspace completo
                print(f"   🔍 Iniciando escáner horizontal en {config['nombre']}...")
                success = self._scan_horizontal_with_workspace(tubo_id)
                if not success:
                    print(f"⚠️ Error escaneando {config['nombre']}")
                    continue
                
                print(f"✅ {config['nombre']} completado")
            
            print("✅ Mapeo de cultivo completado")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en mapeo de cultivo: {e}")
            return False
    
    def _scan_horizontal_with_workspace(self, tubo_id: int) -> bool:
        """Escáner horizontal usando distancia completa del workspace"""
        try:
            # Obtener límites del workspace con varios intentos
            workspace = getattr(self.robot, 'workspace_limits', {})
            
            # Si no está disponible, intentar forzar actualización
            if not workspace:
                try:
                    self.robot._update_workspace_limits()
                    workspace = getattr(self.robot, 'workspace_limits', {})
                except:
                    pass
            
            horizontal_mm = workspace.get('horizontal_mm', 0)
            
            if horizontal_mm <= 0:
                print("❌ No hay información del workspace - ejecutar homing completo primero")
                print(f"   Debug: workspace = {workspace}")
                return False
            
            print(f"   📐 Usando workspace: {horizontal_mm}mm horizontal")
            
            # Configurar para escáner (velocidad reducida)
            print("   ⚙️ Configurando velocidades para escáner...")
            result = self.robot.cmd.set_velocities(2000, 3000)  # Velocidad reducida
            if not result["success"]:
                print(f"   ⚠️ Error configurando velocidades: {result}")
            
            # Mover toda la distancia horizontal usando movimiento relativo
            print(f"   ➡️ Moviendo {horizontal_mm}mm hacia la izquierda...")
            result = self.robot.cmd.move_xy(-horizontal_mm, 0)  # Negativo = izquierda
            if not result["success"]:
                print(f"❌ Error en movimiento horizontal: {result}")
                return False
            
            # Esperar que complete el movimiento
            if not self.robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=60.0):
                print("❌ Timeout en movimiento horizontal")
                return False
            
            # Restaurar velocidades normales
            print("   ⚙️ Restaurando velocidades normales...")
            result = self.robot.cmd.set_velocities(8000, 12000)
            if not result["success"]:
                print(f"   ⚠️ Error restaurando velocidades: {result}")
            
            # Volver al inicio del tubo (X=0) usando movimiento relativo
            print(f"   ⬅️ Regresando al inicio del tubo...")
            result = self.robot.cmd.move_xy(horizontal_mm, 0)  # Positivo = derecha
            if not result["success"]:
                print(f"❌ Error regresando al inicio: {result}")
                return False
            
            # Esperar que complete el regreso
            if not self.robot.cmd.uart.wait_for_action_completion("STEPPER_MOVE", timeout=60.0):
                print("❌ Timeout regresando al inicio")
                return False
            
            print(f"   ✅ Escáner horizontal completado en tubo {tubo_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en escáner horizontal: {e}")
            return False
    
    def _execute_mapeo_recursos(self) -> bool:
        """Ejecutar mapeo de recursos (plantines + cesto)"""
        self.transition_to(RobotState.MAPEO_RECURSOS)
        print("\n🛠️ EJECUTANDO MAPEO DE RECURSOS...")
        
        try:
            print("📍 Mapeo manual de recursos:")
            
            # Plantines
            print("🌱 Detectando plantines...")
            plantines_y = float(input("Ingrese posición Y de plantines (mm): "))
            current_pos = self.robot.get_status()['position']
            self.resources.plantines = (current_pos['x'], plantines_y)
            
            # Cesto
            print("🗑️ Detectando cesto...")
            cesto_y = float(input("Ingrese posición Y del cesto (mm): "))
            self.resources.cesto = (current_pos['x'], cesto_y)
            
            self._save_state_data()
            print("✅ Mapeo de recursos completado")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en mapeo de recursos: {e}")
            return False
    
    def _execute_ciclo_cosecha(self) -> bool:
        """Ejecutar ciclo principal de cosecha"""
        self.transition_to(RobotState.CICLO_COSECHA)
        print("\n🚜 EJECUTANDO CICLO DE COSECHA...")
        
        try:
            tubos_config = config_tubos.obtener_configuracion_tubos()
            
            for tubo_id, config in tubos_config.items():
                print(f"\n📋 Procesando {config['nombre']}...")
                
                lechugas = matriz_cintas.obtener_cintas_tubo(tubo_id)
                if not lechugas:
                    print(f"   ⚠️ No hay lechugas mapeadas en {config['nombre']}")
                    continue
                
                for idx, lechuga in enumerate(lechugas):
                    print(f"\n🥬 EVALUANDO LECHUGA #{idx+1}")
                    print(f"   Posición: X={lechuga['x_mm']}mm, Y={lechuga['y_mm']}mm")
                    print("   Estados: 1=Sin planta, 2=No lista, 3=Lista, 4=Cosechada")
                    
                    try:
                        opcion = input("   Estado (1-4): ").strip()
                        if opcion == '3':  # Lista para cosechar
                            print("   🚜 Simulando cosecha...")
                            self.statistics.lechugas_cosechadas += 1
                        elif opcion == '1':  # Sin planta
                            print("   🌱 Simulando plantación...")
                            self.statistics.plantines_plantados += 1
                        else:
                            print("   ⏭️ Saltando...")
                    except KeyboardInterrupt:
                        print("   Escaneo interrumpido")
                        return False
                
                self.statistics.total_tubos_procesados += 1
            
            print("✅ Ciclo de cosecha completado")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en ciclo de cosecha: {e}")
            return False
    
    def stop_operation(self):
        """Solicitar parada de la operación actual"""
        self.stop_requested.set()
        print("⏹️ Parada solicitada - completando operación actual...")
    
    def reset_stop_request(self):
        """Resetear solicitud de parada"""
        self.stop_requested.clear()


def main():
    """Función main para pruebas directas del archivo"""
    print("🤖 MÁQUINA DE ESTADOS CLAUDIO - MODO PRUEBA")
    print("="*50)
    print("Este archivo está diseñado para ser importado,")
    print("no para ejecutarse directamente.")
    print("\nPara usar la máquina de estados:")
    print("1. Importar en main_robot.py:")
    print("   from controller.robot_state_machine import RobotStateMachine")
    print("2. Crear instancia:")
    print("   state_machine = RobotStateMachine(robot)")
    print("3. Usar métodos:")
    print("   - state_machine.inicio_total()")
    print("   - state_machine.escaner_diario()")
    print("   - state_machine.mostrar_datos()")
    print("="*50)


if __name__ == "__main__":
    main()
