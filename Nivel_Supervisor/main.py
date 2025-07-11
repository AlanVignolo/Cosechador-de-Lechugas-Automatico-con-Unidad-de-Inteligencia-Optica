from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
from pydantic import BaseModel
import logging
import json
from typing import List
import asyncio
from threading import Thread
import queue

from controller.uart_manager import UARTManager
from controller.command_manager import CommandManager
from controller.robot_controller import RobotController
from config.robot_config import RobotConfig

update_queue = queue.Queue()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instancia global del robot
robot_controller = None
robot_connected = False

# Lista de conexiones WebSocket activas
active_websockets: List[WebSocket] = []

async def broadcast_robot_status():
    """Enviar estado actual del robot a todas las conexiones WebSocket"""
    if not robot_controller or not active_websockets:
        return
    
    try:
        status = robot_controller.get_status()
        arm_status = robot_controller.arm.get_current_state()
        
        message = {
            "type": "robot_status",
            "data": {
                "homed": status["homed"],
                "position": status["position"],
                "arm": {
                    "servo1": arm_status["position"][0],
                    "servo2": arm_status["position"][1],
                    "state": arm_status["state"]
                },
                "gripper": arm_status["gripper"]
            }
        }
        
        # Enviar a todas las conexiones activas
        disconnected = []
        for websocket in active_websockets:
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(websocket)
        
        # Limpiar conexiones desconectadas
        for ws in disconnected:
            active_websockets.remove(ws)
            
    except Exception as e:
        logger.error(f"Error broadcasting status: {e}")

def setup_robot_callbacks():
    """Configurar callbacks para eventos del robot"""
    if not robot_controller:
        return
    
    # Callback para cuando servos se mueven
    def on_servo_completed(message: str):
        logger.info(f"Servo completado: {message}")
        update_queue.put("servo_update")
    
    # Callback para cuando gripper cambia
    def on_gripper_completed(message: str):
        logger.info(f"Gripper completado: {message}")
        update_queue.put("gripper_update")
    
    # Callback para cuando steppers se mueven
    def on_stepper_completed(message: str):
        logger.info(f"Stepper completado: {message}")
        update_queue.put("stepper_update")
    
    # Configurar callbacks
    robot_controller.cmd.uart.set_servo_callbacks(None, on_servo_completed)
    robot_controller.cmd.uart.set_gripper_callbacks(None, on_gripper_completed)
    robot_controller.cmd.uart.set_stepper_callbacks(None, on_stepper_completed)

def process_updates():
    """Procesar actualizaciones en un hilo separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def process_loop():
        while True:
            try:
                # Esperar por actualizaciones
                await asyncio.sleep(0.1)
                
                # Procesar todas las actualizaciones pendientes
                while not update_queue.empty():
                    try:
                        update_queue.get_nowait()
                        await broadcast_robot_status()
                    except queue.Empty:
                        break
                        
            except Exception as e:
                logger.error(f"Error en process_loop: {e}")
    
    loop.run_until_complete(process_loop())

def initialize_robot():
    global robot_controller, robot_connected
    try:
        uart = UARTManager(RobotConfig.SERIAL_PORT, RobotConfig.BAUD_RATE)
        if uart.connect():
            cmd_manager = CommandManager(uart)
            robot_controller = RobotController(cmd_manager)
            robot_connected = True
            
            # Configurar callbacks para eventos automáticos
            setup_robot_callbacks()
            
            # Iniciar hilo de procesamiento de actualizaciones
            update_thread = Thread(target=process_updates, daemon=True)
            update_thread.start()
            
            logger.info("✅ Robot conectado exitosamente")
            return True
        else:
            logger.error("❌ No se pudo conectar al robot")
            return False
    except Exception as e:
        logger.error(f"❌ Error conectando robot: {e}")
        return False

def get_robot_controller():
    global robot_controller
    if robot_controller is None:
        if not initialize_robot():
            raise HTTPException(status_code=503, detail="Robot no conectado")
    return robot_controller

# Schemas
class MoveRequest(BaseModel):
    x: float
    y: float

class ArmMoveRequest(BaseModel):
    servo1: int
    servo2: int
    time_ms: int

class RobotStatusResponse(BaseModel):
    homed: bool
    position: dict
    arm: dict
    gripper: str

class ResponseMessage(BaseModel):
    message: str
    success: bool
    data: dict = None

app = FastAPI(
    title="CLAUDIO - Robot Controller API",
    description="API para controlar robot físico con WebSockets",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Iniciando conexión con robot...")
    initialize_robot()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info(f"Nueva conexión WebSocket. Total: {len(active_websockets)}")
    
    try:
        # Enviar estado inicial
        await broadcast_robot_status()
        
        # Mantener conexión activa
        while True:
            # Recibir mensajes del cliente (opcional)
            data = await websocket.receive_text()
            logger.debug(f"Mensaje recibido: {data}")
            
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        logger.info(f"Conexión WebSocket cerrada. Total: {len(active_websockets)}")

@app.get("/", response_model=ResponseMessage)
async def root():
    return ResponseMessage(
        message="CLAUDIO - Robot Controller API funcionando",
        success=True,
        data={
            "version": "2.0.0", 
            "timestamp": datetime.now().isoformat(),
            "robot_connected": robot_connected,
            "websocket_connections": len(active_websockets)
        }
    )

@app.get("/robot/status", response_model=RobotStatusResponse)
async def get_robot_status():
    try:
        robot = get_robot_controller()
        status = robot.get_status()
        arm_status = robot.arm.get_current_state()
        
        return RobotStatusResponse(
            homed=status["homed"],
            position=status["position"],
            arm={
                "servo1": arm_status["position"][0],
                "servo2": arm_status["position"][1],
                "state": arm_status["state"]
            },
            gripper=arm_status["gripper"]
        )
    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        raise HTTPException(status_code=503, detail=f"Error obteniendo estado del robot: {str(e)}")

@app.post("/robot/move", response_model=ResponseMessage)
async def move_robot(request: MoveRequest):
    try:
        robot = get_robot_controller()
        result = robot.move_to_absolute(request.x, request.y)
        
        # No necesitamos broadcast aquí, el callback lo hará automáticamente
        return ResponseMessage(
            message=result["message"],
            success=result["success"],
            data={"x": request.x, "y": request.y}
        )
    except Exception as e:
        logger.error(f"Error moviendo robot: {e}")
        raise HTTPException(status_code=500, detail=f"Error moviendo robot: {str(e)}")

@app.post("/robot/home", response_model=ResponseMessage)
async def home_robot():
    try:
        robot = get_robot_controller()
        result = robot.home_robot()
        
        return ResponseMessage(
            message=result["message"],
            success=result["success"],
            data=result.get("position")
        )
    except Exception as e:
        logger.error(f"Error en homing: {e}")
        raise HTTPException(status_code=500, detail=f"Error en homing: {str(e)}")

@app.post("/robot/arm/move", response_model=ResponseMessage)
async def move_arm(request: ArmMoveRequest):
    try:
        robot = get_robot_controller()
        result = robot.cmd.move_arm(request.servo1, request.servo2, request.time_ms)
        
        return ResponseMessage(
            message=f"Brazo moviéndose a ({request.servo1}°, {request.servo2}°)",
            success=result["success"],
            data={
                "servo1": request.servo1,
                "servo2": request.servo2,
                "time_ms": request.time_ms
            }
        )
    except Exception as e:
        logger.error(f"Error moviendo brazo: {e}")
        raise HTTPException(status_code=500, detail=f"Error moviendo brazo: {str(e)}")

@app.post("/robot/arm/state/{state}", response_model=ResponseMessage)
async def change_arm_state(state: str):
    try:
        robot = get_robot_controller()
        result = robot.arm.change_state(state)
        
        return ResponseMessage(
            message=result["message"],
            success=result["success"],
            data={"target_state": state}
        )
    except Exception as e:
        logger.error(f"Error cambiando estado del brazo: {e}")
        raise HTTPException(status_code=500, detail=f"Error cambiando estado del brazo: {str(e)}")

@app.post("/robot/gripper/open", response_model=ResponseMessage)
async def open_gripper():
    try:
        robot = get_robot_controller()
        
        # Consultar estado actual
        gripper_status = robot.cmd.get_gripper_status()
        if gripper_status["success"] and "GRIPPER_STATUS:" in gripper_status["response"]:
            current_state = gripper_status["response"].split("GRIPPER_STATUS:")[1].split(",")[0].lower()
            
            if current_state == "open":
                return ResponseMessage(
                    message="Gripper ya está abierto",
                    success=True,
                    data={"action": "no_change", "state": "open"}
                )
        
        # Solo abrir si está cerrado
        result = robot.cmd.gripper_toggle()
        
        return ResponseMessage(
            message="Gripper abierto",
            success=result["success"],
            data={"action": "opened"}
        )
    except Exception as e:
        logger.error(f"Error abriendo gripper: {e}")
        raise HTTPException(status_code=500, detail=f"Error abriendo gripper: {str(e)}")

@app.post("/robot/gripper/close", response_model=ResponseMessage)
async def close_gripper():
    try:
        robot = get_robot_controller()
        
        # Consultar estado actual
        gripper_status = robot.cmd.get_gripper_status()
        if gripper_status["success"] and "GRIPPER_STATUS:" in gripper_status["response"]:
            current_state = gripper_status["response"].split("GRIPPER_STATUS:")[1].split(",")[0].lower()
            
            if current_state == "closed":
                return ResponseMessage(
                    message="Gripper ya está cerrado",
                    success=True,
                    data={"action": "no_change", "state": "closed"}
                )
        
        # Solo cerrar si está abierto
        result = robot.cmd.gripper_toggle()
        
        return ResponseMessage(
            message="Gripper cerrado",
            success=result["success"],
            data={"action": "closed"}
        )
    except Exception as e:
        logger.error(f"Error cerrando gripper: {e}")
        raise HTTPException(status_code=500, detail=f"Error cerrando gripper: {str(e)}")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "robot_connected": robot_connected,
        "websocket_connections": len(active_websockets)
    }

if __name__ == "__main__":
    print("🚀 CLAUDIO - Robot Controller API con WebSockets")
    print("📱 La API estará disponible en: http://localhost:8000")
    print("📖 Documentación automática en: http://localhost:8000/docs")
    print("🔌 WebSocket endpoint: ws://localhost:8000/ws")
    print("🤖 Conectando robot físico...")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )