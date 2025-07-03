import os
from typing import Optional

class Settings:
    """Configuraciones de la aplicación"""
    
    # Base de datos
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./jardin_hidroponico.db")
    
    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Jardín Settings
    SECCION1_CAPACIDAD: int = int(os.getenv("SECCION1_CAPACIDAD", 5))
    SECCION2_CAPACIDAD: int = int(os.getenv("SECCION2_CAPACIDAD", 5))
    TIEMPO_ESCANEO_SEGUNDOS: int = int(os.getenv("TIEMPO_ESCANEO_SEGUNDOS", 2))
    TIEMPO_REFERENCIA_SEGUNDOS: int = int(os.getenv("TIEMPO_REFERENCIA_SEGUNDOS", 3))
    
    # Sensores Settings
    INTERVALO_SENSORES_MINUTOS: int = int(os.getenv("INTERVALO_SENSORES_MINUTOS", 15))
    TEMPERATURA_MIN: float = float(os.getenv("TEMPERATURA_MIN", 18.0))
    TEMPERATURA_MAX: float = float(os.getenv("TEMPERATURA_MAX", 35.0))
    HUMEDAD_MIN: float = float(os.getenv("HUMEDAD_MIN", 50.0))
    HUMEDAD_MAX: float = float(os.getenv("HUMEDAD_MAX", 90.0))
    PH_MIN: float = float(os.getenv("PH_MIN", 5.5))
    PH_MAX: float = float(os.getenv("PH_MAX", 8.0))
    
    # Seguridad (para futuras implementaciones)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "tu_clave_secreta_aqui")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", "jardin_hidroponico.log")

settings = Settings()

# Estados válidos para lechugas
ESTADOS_LECHUGA = {
    0: "vacío",
    1: "creciendo", 
    2: "listo"
}

# Estados válidos para el sistema
ESTADOS_SISTEMA = [
    "Conectado",
    "Desconectado", 
    "Error",
    "Mantenimiento"
]

# Comandos válidos
COMANDOS_VALIDOS = [
    "escanear",
    "referenciar", 
    "frenar",
    "apagar",
    "cosechar"
]

# Resultados válidos para acciones
RESULTADOS_ACCIONES = [
    "exitoso",
    "error",
    "en_proceso",
    "cancelado"
]