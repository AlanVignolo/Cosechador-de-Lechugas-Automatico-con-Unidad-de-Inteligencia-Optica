from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Schemas para Estado del Jardín
class EstadoJardinBase(BaseModel):
    seccion1_estados: List[int]
    seccion2_estados: List[int]
    lechugas_cosechadas: int = 0
    tiempo_medio_crecimiento: str = "45 días"
    estado_sistema: str = "Conectado"

class EstadoJardinCreate(EstadoJardinBase):
    pass

class EstadoJardinResponse(EstadoJardinBase):
    id: int
    timestamp: datetime
    
    class Config:
        orm_mode = True

# Schemas para Comandos
class ComandoBase(BaseModel):
    comando: str  # escanear, referenciar, frenar, apagar
    parametros: Optional[dict] = None

class ComandoCreate(ComandoBase):
    pass

class ComandoResponse(BaseModel):
    id: int
    comando: str
    estado: str
    timestamp_creado: datetime
    resultado: Optional[str] = None
    
    class Config:
        from_attributes = True

# Schemas para Historial
class HistorialAccionBase(BaseModel):
    accion: str
    descripcion: str
    resultado: str = "exitoso"
    usuario: str = "sistema"
    detalles: Optional[str] = None

class HistorialAccionCreate(HistorialAccionBase):
    pass

class HistorialAccionResponse(HistorialAccionBase):
    id: int
    timestamp: datetime
    
    class Config:
        orm_mode = True

# Schemas para Sensores
class LecturaSensorBase(BaseModel):
    temperatura: Optional[float] = None
    humedad: Optional[float] = None
    ph_agua: Optional[float] = None
    nivel_agua: Optional[float] = None
    luz_ambiente: Optional[float] = None

class LecturaSensorCreate(LecturaSensorBase):
    pass

class LecturaSensorResponse(LecturaSensorBase):
    id: int
    timestamp: datetime
    
    class Config:
        orm_mode = True

# Schemas para Configuraciones
class ConfiguracionBase(BaseModel):
    clave: str
    valor: str
    descripcion: Optional[str] = None

class ConfiguracionCreate(ConfiguracionBase):
    pass

class ConfiguracionResponse(ConfiguracionBase):
    id: int
    timestamp_update: datetime
    
    class Config:
        orm_mode = True

# Respuestas generales
class ResponseMessage(BaseModel):
    message: str
    success: bool
    data: Optional[dict] = None

class EstadoCompleto(BaseModel):
    """Estado completo del jardín para Android"""
    jardin: EstadoJardinResponse
    sensores: Optional[LecturaSensorResponse] = None
    comandos_pendientes: List[ComandoResponse] = []
    ultimo_historial: List[HistorialAccionResponse] = []