#!/usr/bin/env python3
"""
Script para inicializar la base de datos y datos de prueba
"""

from .models import create_tables, SessionLocal, EstadoJardin, HistorialAcciones, Configuraciones, LecturasSensores
from jardin_service import jardin_service
from datetime import datetime, timedelta
import random

def init_database():
    """Inicializar base de datos con datos de prueba"""
    print("🗄️  Creando tablas de base de datos...")
    create_tables()
    
    db = SessionLocal()
    
    try:
        # Verificar si ya hay datos
        estado_existente = db.query(EstadoJardin).first()
        if estado_existente:
            print("✅ Base de datos ya inicializada")
            return
        
        print("🌱 Creando estado inicial del jardín...")
        
        # Crear estado inicial
        estado_inicial = EstadoJardin(
            lechugas_cosechadas=3,
            tiempo_medio_crecimiento="42 días", 
            estado_sistema="Conectado"
        )
        estado_inicial.set_seccion1([2, 1, 2, 0, 1])  # Ejemplo: 2 listas, 2 creciendo, 1 vacío
        estado_inicial.set_seccion2([1, 2, 1, 2, 0])  # Ejemplo: 2 listas, 2 creciendo, 1 vacío
        
        db.add(estado_inicial)
        db.commit()
        
        print("📖 Creando historial de prueba...")
        
        # Crear historial de ejemplo
        acciones_ejemplo = [
            ("inicializacion", "Sistema inicializado correctamente", "exitoso"),
            ("escanear", "Escaneo inicial del jardín", "exitoso"),
            ("referenciar", "Sistema referenciado en posición home", "exitoso"),
            ("escanear", "Detectadas 2 lechugas listas para cosechar", "exitoso"),
            ("cosechar", "Lechuga cosechada en sección 1, posición 0", "exitoso"),
        ]
        
        base_time = datetime.now() - timedelta(hours=2)
        
        for i, (accion, descripcion, resultado) in enumerate(acciones_ejemplo):
            historial = HistorialAcciones(
                timestamp=base_time + timedelta(minutes=i*15),
                accion=accion,
                descripcion=descripcion,
                resultado=resultado,
                usuario="sistema"
            )
            db.add(historial)
        
        print("⚙️  Creando configuraciones...")
        
        # Crear configuraciones
        configuraciones_ejemplo = [
            ("tiempo_riego", "300", "Tiempo de riego en segundos"),
            ("temperatura_objetivo", "25", "Temperatura objetivo en °C"),
            ("humedad_objetivo", "70", "Humedad objetivo en %"),
            ("ph_objetivo", "6.5", "pH objetivo del agua"),
            ("intervalo_escaneo", "3600", "Intervalo entre escaneos automáticos en segundos"),
        ]
        
        for clave, valor, descripcion in configuraciones_ejemplo:
            config = Configuraciones(
                clave=clave,
                valor=valor,
                descripcion=descripcion
            )
            db.add(config)
        
        print("🌡️  Creando lecturas de sensores...")
        
        # Crear lecturas de sensores de ejemplo
        for i in range(5):
            lectura = LecturasSensores(
                timestamp=datetime.now() - timedelta(hours=i),
                temperatura=random.uniform(22, 28),
                humedad=random.uniform(65, 75),
                ph_agua=random.uniform(6.0, 7.0),
                nivel_agua=random.uniform(80, 95),
                luz_ambiente=random.uniform(400, 600)
            )
            db.add(lectura)
        
        db.commit()
        
        print("✅ Base de datos inicializada exitosamente!")
        print(f"📊 Estado del jardín: {estado_inicial.get_seccion1()} | {estado_inicial.get_seccion2()}")
        print(f"🥬 Lechugas cosechadas: {estado_inicial.lechugas_cosechadas}")
        print(f"⏱️  Tiempo medio: {estado_inicial.tiempo_medio_crecimiento}")
        
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        db.rollback()
    finally:
        db.close()

def mostrar_estado_actual():
    """Mostrar el estado actual del jardín"""
    db = SessionLocal()
    try:
        estado = jardin_service.obtener_estado_actual(db)
        print("\n🌱 Estado actual del jardín:")
        print(f"   Sección 1: {estado.get_seccion1()}")
        print(f"   Sección 2: {estado.get_seccion2()}")
        print(f"   Lechugas cosechadas: {estado.lechugas_cosechadas}")
        print(f"   Tiempo medio: {estado.tiempo_medio_crecimiento}")
        print(f"   Estado sistema: {estado.estado_sistema}")
        print(f"   Timestamp: {estado.timestamp}")
        
        # Mostrar últimas acciones
        historial = jardin_service.obtener_historial(db, limite=3)
        print("\n📖 Últimas acciones:")
        for accion in historial:
            print(f"   {accion.timestamp.strftime('%H:%M')} - {accion.accion}: {accion.descripcion} ({accion.resultado})")
            
    except Exception as e:
        print(f"❌ Error obteniendo estado: {e}")
    finally:
        db.close()

def test_comandos():
    """Probar los comandos básicos"""
    db = SessionLocal()
    try:
        print("\n🧪 Probando comandos...")
        
        # Probar escaneo
        print("   Ejecutando escaneo...")
        resultado = jardin_service.ejecutar_comando_escanear(db)
        print(f"   Resultado: {resultado['message']}")
        
        # Probar referenciación
        print("   Ejecutando referenciación...")
        resultado = jardin_service.ejecutar_comando_referenciar(db)
        print(f"   Resultado: {resultado['message']}")
        
        print("✅ Comandos probados exitosamente!")
        
    except Exception as e:
        print(f"❌ Error probando comandos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Inicializando CLAUDIO - Jardín Hidropónico")
    print("=" * 50)
    
    init_database()
    mostrar_estado_actual()
    test_comandos()
    
    print("\n🎉 ¡Listo! Puedes ejecutar la API con:")
    print("   python main.py")
    print("\n📖 Documentación en: http://localhost:8000/docs")