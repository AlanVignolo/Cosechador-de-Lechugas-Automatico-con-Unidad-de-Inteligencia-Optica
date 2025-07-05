from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn
from datetime import datetime
from typing import List

from models import get_db, create_tables, EstadoJardin, HistorialAcciones, ComandosPendientes, LecturasSensores
from api.schemas import *
from jardin_service import jardin_service

# Crear tablas al iniciar
create_tables()

app = FastAPI(
    title="CLAUDIO - API Jardín Hidropónico",
    description="API para controlar y monitorear el jardín hidropónico de lechugas",
    version="1.0.0"
)

# Configurar CORS para permitir conexiones desde Android
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios exactos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_model=ResponseMessage)
async def root():
    """Endpoint raíz para verificar que la API está funcionando"""
    return ResponseMessage(
        message="CLAUDIO - API Jardín Hidropónico está funcionando",
        success=True,
        data={"version": "1.0.0", "timestamp": datetime.now().isoformat()}
    )

@app.get("/estado", response_model=EstadoCompleto)
async def obtener_estado_completo(db: Session = Depends(get_db)):
    """Obtiene el estado completo del jardín para Android"""
    try:
        # Estado del jardín
        jardin_estado = jardin_service.obtener_estado_actual(db)
        
        # Últimas lecturas de sensores
        sensor_lectura = db.query(LecturasSensores).order_by(LecturasSensores.timestamp.desc()).first()
        
        # Comandos pendientes
        comandos_pendientes = db.query(ComandosPendientes).filter(
            ComandosPendientes.estado.in_(["pendiente", "ejecutando"])
        ).all()
        
        # Último historial (10 registros)
        historial = jardin_service.obtener_historial(db, limite=10)
        
        return EstadoCompleto(
            jardin=jardin_estado,
            sensores=sensor_lectura,
            comandos_pendientes=comandos_pendientes,
            ultimo_historial=historial
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado: {str(e)}")

@app.get("/estado/jardin", response_model=EstadoJardinResponse)
async def obtener_estado_jardin(db: Session = Depends(get_db)):
    """Obtiene solo el estado del jardín"""
    return jardin_service.obtener_estado_actual(db)

@app.post("/comando/escanear", response_model=ResponseMessage)
async def comando_escanear(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ejecuta el comando de escaneo"""
    try:
        resultado = jardin_service.ejecutar_comando_escanear(db)
        return ResponseMessage(
            message=resultado["message"],
            success=resultado["success"],
            data=resultado.get("data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando escaneo: {str(e)}")

@app.post("/comando/referenciar", response_model=ResponseMessage)
async def comando_referenciar(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ejecuta el comando de referenciación"""
    try:
        resultado = jardin_service.ejecutar_comando_referenciar(db)
        return ResponseMessage(
            message=resultado["message"],
            success=resultado["success"],
            data=resultado.get("data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando referenciación: {str(e)}")

@app.post("/comando/frenar", response_model=ResponseMessage)
async def comando_frenar(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ejecuta el comando de freno"""
    try:
        resultado = jardin_service.ejecutar_comando_frenar(db)
        return ResponseMessage(
            message=resultado["message"],
            success=resultado["success"],
            data=resultado.get("data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando freno: {str(e)}")

@app.post("/comando/apagar", response_model=ResponseMessage)
async def comando_apagar(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ejecuta el comando de apagado"""
    try:
        resultado = jardin_service.ejecutar_comando_apagar(db)
        return ResponseMessage(
            message=resultado["message"],
            success=resultado["success"],
            data=resultado.get("data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando apagado: {str(e)}")

@app.post("/cosechar", response_model=ResponseMessage)
async def cosechar_lechuga(seccion: int, posicion: int, db: Session = Depends(get_db)):
    """Cosecha una lechuga específica"""
    if seccion not in [1, 2]:
        raise HTTPException(status_code=400, detail="Sección debe ser 1 o 2")
    
    if posicion < 0 or posicion > 4:
        raise HTTPException(status_code=400, detail="Posición debe estar entre 0 y 4")
    
    try:
        resultado = jardin_service.cosechar_lechuga(db, seccion, posicion)
        return ResponseMessage(
            message=resultado["message"],
            success=resultado["success"],
            data=resultado.get("data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cosechando lechuga: {str(e)}")

@app.get("/historial", response_model=List[HistorialAccionResponse])
async def obtener_historial(limite: int = 50, db: Session = Depends(get_db)):
    """Obtiene el historial de acciones"""
    return jardin_service.obtener_historial(db, limite)

@app.get("/sensores", response_model=LecturaSensorResponse)
async def obtener_lecturas_sensores(db: Session = Depends(get_db)):
    """Obtiene las últimas lecturas de sensores"""
    lectura = db.query(LecturasSensores).order_by(LecturasSensores.timestamp.desc()).first()
    if not lectura:
        # Simular una lectura si no existe
        lectura = jardin_service.simular_lectura_sensores(db)
    return lectura

@app.post("/sensores", response_model=ResponseMessage)
async def registrar_lectura_sensores(lectura: LecturaSensorCreate, db: Session = Depends(get_db)):
    """Registra una nueva lectura de sensores"""
    try:
        nueva_lectura = LecturasSensores(**lectura.dict())
        db.add(nueva_lectura)
        db.commit()
        db.refresh(nueva_lectura)
        
        return ResponseMessage(
            message="Lectura de sensores registrada exitosamente",
            success=True,
            data={"id": nueva_lectura.id, "timestamp": nueva_lectura.timestamp.isoformat()}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando lectura: {str(e)}")

@app.put("/estado/jardin", response_model=EstadoJardinResponse)
async def actualizar_estado_jardin(estado: EstadoJardinCreate, db: Session = Depends(get_db)):
    """Actualiza el estado del jardín manualmente"""
    try:
        nuevo_estado = jardin_service.actualizar_estado_jardin(
            db, 
            estado.seccion1_estados, 
            estado.seccion2_estados, 
            estado.lechugas_cosechadas
        )
        
        jardin_service.registrar_accion(
            db, 
            "actualizacion_manual", 
            "Estado del jardín actualizado manualmente", 
            "exitoso"
        )
        
        return nuevo_estado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando estado: {str(e)}")

@app.get("/comandos/pendientes", response_model=List[ComandoResponse])
async def obtener_comandos_pendientes(db: Session = Depends(get_db)):
    """Obtiene los comandos pendientes de ejecutar"""
    return db.query(ComandosPendientes).filter(
        ComandosPendientes.estado.in_(["pendiente", "ejecutando"])
    ).all()

@app.get("/health")
async def health_check():
    """Endpoint para verificar la salud del sistema"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sistema_activo": jardin_service.sistema_activo,
        "ultimo_escaneo": jardin_service.ultimo_escaneo.isoformat() if jardin_service.ultimo_escaneo else None
    }

if __name__ == "__main__":
    print("🌱 Iniciando CLAUDIO - API Jardín Hidropónico")
    print("📱 La API estará disponible en: http://localhost:8000")
    print("📖 Documentación automática en: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )