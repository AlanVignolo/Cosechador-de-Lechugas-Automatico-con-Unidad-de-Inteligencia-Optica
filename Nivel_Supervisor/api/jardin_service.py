import json
import time
import threading
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import EstadoJardin, HistorialAcciones, ComandosPendientes, LecturasSensores
from typing import List, Dict, Optional
import random

class JardinHidroponicoService:
    """Servicio principal para manejar el jardín hidropónico"""
    
    def __init__(self):
        self.sistema_activo = True
        self.ultimo_escaneo = None
        self.referenciado = False
        
    def obtener_estado_actual(self, db: Session) -> EstadoJardin:
        """Obtiene el estado más reciente del jardín"""
        estado = db.query(EstadoJardin).order_by(EstadoJardin.timestamp.desc()).first()
        
        if not estado:
            # Crear estado inicial si no existe
            estado = self.crear_estado_inicial(db)
        
        return estado
    
    def crear_estado_inicial(self, db: Session) -> EstadoJardin:
        """Crea el estado inicial del jardín"""
        estado_inicial = EstadoJardin(
            lechugas_cosechadas=0,
            tiempo_medio_crecimiento="45 días",
            estado_sistema="Conectado"
        )
        estado_inicial.set_seccion1([2, 1, 2, 0, 1])  # Estado ejemplo
        estado_inicial.set_seccion2([1, 2, 1, 2, 0])  # Estado ejemplo
        
        db.add(estado_inicial)
        db.commit()
        db.refresh(estado_inicial)
        
        self.registrar_accion(db, "inicializacion", "Sistema inicializado", "exitoso")
        return estado_inicial
    
    def actualizar_estado_jardin(self, db: Session, seccion1: List[int], seccion2: List[int], 
                                lechugas_cosechadas: Optional[int] = None) -> EstadoJardin:
        """Actualiza el estado del jardín"""
        estado_actual = self.obtener_estado_actual(db)
        
        nuevo_estado = EstadoJardin(
            lechugas_cosechadas=lechugas_cosechadas or estado_actual.lechugas_cosechadas,
            tiempo_medio_crecimiento=estado_actual.tiempo_medio_crecimiento,
            estado_sistema=estado_actual.estado_sistema
        )
        nuevo_estado.set_seccion1(seccion1)
        nuevo_estado.set_seccion2(seccion2)
        
        db.add(nuevo_estado)
        db.commit()
        db.refresh(nuevo_estado)
        
        return nuevo_estado
    
    def ejecutar_comando_escanear(self, db: Session) -> Dict:
        """Simula el escaneo del jardín"""
        try:
            self.registrar_accion(db, "escanear", "Iniciando escaneo del jardín", "en_proceso")
            
            # Simular tiempo de escaneo
            time.sleep(2)
            
            # Simular detección de cambios
            estado_actual = self.obtener_estado_actual(db)
            seccion1 = estado_actual.get_seccion1()
            seccion2 = estado_actual.get_seccion2()
            
            # Simular crecimiento aleatorio
            cambios = False
            for i in range(len(seccion1)):
                if seccion1[i] == 1 and random.random() < 0.3:  # 30% chance de madurar
                    seccion1[i] = 2
                    cambios = True
            
            for i in range(len(seccion2)):
                if seccion2[i] == 1 and random.random() < 0.3:
                    seccion2[i] = 2
                    cambios = True
            
            if cambios:
                self.actualizar_estado_jardin(db, seccion1, seccion2)
            
            self.ultimo_escaneo = datetime.now()
            resultado = {
                "lechugas_detectadas": sum(1 for x in seccion1 + seccion2 if x > 0),
                "lechugas_listas": sum(1 for x in seccion1 + seccion2 if x == 2),
                "cambios_detectados": cambios,
                "timestamp": self.ultimo_escaneo.isoformat()
            }
            
            self.registrar_accion(db, "escanear", f"Escaneo completado. {resultado['lechugas_listas']} lechugas listas", "exitoso", json.dumps(resultado))
            
            return {
                "success": True,
                "message": "Escaneo completado exitosamente",
                "data": resultado
            }
            
        except Exception as e:
            self.registrar_accion(db, "escanear", f"Error durante escaneo: {str(e)}", "error")
            return {
                "success": False,
                "message": f"Error durante escaneo: {str(e)}"
            }
    
    def ejecutar_comando_referenciar(self, db: Session) -> Dict:
        """Ejecuta el comando de referenciación del sistema"""
        try:
            self.registrar_accion(db, "referenciar", "Iniciando referenciación del sistema", "en_proceso")
            
            # Simular proceso de referenciación
            time.sleep(3)
            
            self.referenciado = True
            resultado = {
                "posicion_inicial": "establecida",
                "calibracion": "completada",
                "timestamp": datetime.now().isoformat()
            }
            
            self.registrar_accion(db, "referenciar", "Sistema referenciado correctamente", "exitoso", json.dumps(resultado))
            
            return {
                "success": True,
                "message": "Sistema referenciado exitosamente",
                "data": resultado
            }
            
        except Exception as e:
            self.registrar_accion(db, "referenciar", f"Error durante referenciación: {str(e)}", "error")
            return {
                "success": False,
                "message": f"Error durante referenciación: {str(e)}"
            }
    
    def ejecutar_comando_frenar(self, db: Session) -> Dict:
        """Ejecuta el comando de freno del sistema"""
        try:
            self.registrar_accion(db, "frenar", "Frenando sistema", "en_proceso")
            
            # Simular frenado
            time.sleep(1)
            
            resultado = {
                "motores": "detenidos",
                "movimiento": "frenado",
                "timestamp": datetime.now().isoformat()
            }
            
            self.registrar_accion(db, "frenar", "Sistema frenado exitosamente", "exitoso", json.dumps(resultado))
            
            return {
                "success": True,
                "message": "Sistema frenado exitosamente",
                "data": resultado
            }
            
        except Exception as e:
            self.registrar_accion(db, "frenar", f"Error durante frenado: {str(e)}", "error")
            return {
                "success": False,
                "message": f"Error durante frenado: {str(e)}"
            }
    
    def ejecutar_comando_apagar(self, db: Session) -> Dict:
        """Ejecuta el comando de apagado del sistema"""
        try:
            self.registrar_accion(db, "apagar", "Iniciando secuencia de apagado", "en_proceso")
            
            # Simular secuencia de apagado
            time.sleep(2)
            
            self.sistema_activo = False
            
            # Actualizar estado del sistema
            estado_actual = self.obtener_estado_actual(db)
            nuevo_estado = EstadoJardin(
                lechugas_cosechadas=estado_actual.lechugas_cosechadas,
                tiempo_medio_crecimiento=estado_actual.tiempo_medio_crecimiento,
                estado_sistema="Desconectado"
            )
            nuevo_estado.set_seccion1(estado_actual.get_seccion1())
            nuevo_estado.set_seccion2(estado_actual.get_seccion2())
            
            db.add(nuevo_estado)
            db.commit()
            
            resultado = {
                "sistema": "apagado",
                "timestamp": datetime.now().isoformat()
            }
            
            self.registrar_accion(db, "apagar", "Sistema apagado exitosamente", "exitoso", json.dumps(resultado))
            
            return {
                "success": True,
                "message": "Sistema apagado exitosamente",
                "data": resultado
            }
            
        except Exception as e:
            self.registrar_accion(db, "apagar", f"Error durante apagado: {str(e)}", "error")
            return {
                "success": False,
                "message": f"Error durante apagado: {str(e)}"
            }
    
    def cosechar_lechuga(self, db: Session, seccion: int, posicion: int) -> Dict:
        """Cosecha una lechuga específica"""
        try:
            estado_actual = self.obtener_estado_actual(db)
            
            if seccion == 1:
                estados = estado_actual.get_seccion1()
            else:
                estados = estado_actual.get_seccion2()
            
            if posicion >= len(estados) or estados[posicion] != 2:
                return {
                    "success": False,
                    "message": "No hay lechuga lista en esa posición"
                }
            
            # Marcar como vacío y aumentar contador
            estados[posicion] = 0
            lechugas_cosechadas = estado_actual.lechugas_cosechadas + 1
            
            if seccion == 1:
                self.actualizar_estado_jardin(db, estados, estado_actual.get_seccion2(), lechugas_cosechadas)
            else:
                self.actualizar_estado_jardin(db, estado_actual.get_seccion1(), estados, lechugas_cosechadas)
            
            resultado = {
                "seccion": seccion,
                "posicion": posicion,
                "total_cosechadas": lechugas_cosechadas,
                "timestamp": datetime.now().isoformat()
            }
            
            self.registrar_accion(db, "cosechar", f"Lechuga cosechada en sección {seccion}, posición {posicion}", "exitoso", json.dumps(resultado))
            
            return {
                "success": True,
                "message": "Lechuga cosechada exitosamente",
                "data": resultado
            }
            
        except Exception as e:
            self.registrar_accion(db, "cosechar", f"Error durante cosecha: {str(e)}", "error")
            return {
                "success": False,
                "message": f"Error durante cosecha: {str(e)}"
            }
    
    def registrar_accion(self, db: Session, accion: str, descripcion: str, resultado: str, detalles: str = None):
        """Registra una acción en el historial"""
        historial = HistorialAcciones(
            accion=accion,
            descripcion=descripcion,
            resultado=resultado,
            detalles=detalles
        )
        db.add(historial)
        db.commit()
    
    def obtener_historial(self, db: Session, limite: int = 50) -> List[HistorialAcciones]:
        """Obtiene el historial de acciones"""
        return db.query(HistorialAcciones).order_by(HistorialAcciones.timestamp.desc()).limit(limite).all()
    
    def simular_lectura_sensores(self, db: Session):
        """Simula lecturas de sensores"""
        lectura = LecturasSensores(
            temperatura=random.uniform(20, 30),
            humedad=random.uniform(60, 80),
            ph_agua=random.uniform(6.0, 7.5),
            nivel_agua=random.uniform(70, 100),
            luz_ambiente=random.uniform(300, 800)
        )
        db.add(lectura)
        db.commit()
        return lectura

# Instancia global del servicio
jardin_service = JardinHidroponicoService()