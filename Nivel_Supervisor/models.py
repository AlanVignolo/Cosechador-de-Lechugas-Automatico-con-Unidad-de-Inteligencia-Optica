from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()

class EstadoJardin(Base):
    """Estado actual del jardín hidropónico"""
    __tablename__ = "estados_jardin"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Estados de las secciones (JSON string de arrays)
    seccion1_estados = Column(String(50))  # [2,1,2,0,1] como string
    seccion2_estados = Column(String(50))  # [1,2,1,2,0] como string
    
    # Información general
    lechugas_cosechadas = Column(Integer, default=0)
    tiempo_medio_crecimiento = Column(String(20), default="45 días")
    estado_sistema = Column(String(20), default="Conectado")  # Conectado, Desconectado, Error
    
    def set_seccion1(self, estados_array):
        """Convierte array a JSON string"""
        self.seccion1_estados = json.dumps(estados_array)
    
    def get_seccion1(self):
        """Convierte JSON string a array"""
        return json.loads(self.seccion1_estados) if self.seccion1_estados else [0,0,0,0,0]
    
    def set_seccion2(self, estados_array):
        """Convierte array a JSON string"""
        self.seccion2_estados = json.dumps(estados_array)
    
    def get_seccion2(self):
        """Convierte JSON string a array"""
        return json.loads(self.seccion2_estados) if self.seccion2_estados else [0,0,0,0,0]

class HistorialAcciones(Base):
    """Historial de todas las acciones realizadas"""
    __tablename__ = "historial_acciones"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    accion = Column(String(50))  # escanear, cosechar, referenciar, frenar, apagar
    descripcion = Column(Text)
    resultado = Column(String(20))  # exitoso, error, en_proceso
    usuario = Column(String(50), default="sistema")
    detalles = Column(Text)  # JSON con detalles adicionales

class LecturasSensores(Base):
    """Lecturas de sensores del sistema"""
    __tablename__ = "lecturas_sensores"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    temperatura = Column(Float)
    humedad = Column(Float)
    ph_agua = Column(Float)
    nivel_agua = Column(Float)
    luz_ambiente = Column(Float)

class Configuraciones(Base):
    """Configuraciones del sistema"""
    __tablename__ = "configuraciones"
    
    id = Column(Integer, primary_key=True, index=True)
    clave = Column(String(50), unique=True)
    valor = Column(String(200))
    descripcion = Column(Text)
    timestamp_update = Column(DateTime, default=datetime.utcnow)

class ComandosPendientes(Base):
    """Cola de comandos pendientes de ejecutar"""
    __tablename__ = "comandos_pendientes"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp_creado = Column(DateTime, default=datetime.utcnow)
    comando = Column(String(50))  # escanear, referenciar, frenar, apagar
    parametros = Column(Text)  # JSON con parámetros
    estado = Column(String(20), default="pendiente")  # pendiente, ejecutando, completado, error
    resultado = Column(Text)

# Configuración de la base de datos
DATABASE_URL = "sqlite:///./jardin_hidroponico.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Crear todas las tablas"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()