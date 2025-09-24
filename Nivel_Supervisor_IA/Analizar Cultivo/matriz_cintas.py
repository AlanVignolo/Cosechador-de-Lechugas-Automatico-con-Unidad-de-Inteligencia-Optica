"""
Sistema de Matriz de Cintas para Robot CLAUDIO
Guarda posiciones x,y de cada cinta detectada por tubo
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class MatrizCintas:
    def __init__(self, archivo_matriz="matriz_cintas.json"):
        self.archivo_matriz = os.path.join(os.path.dirname(__file__), archivo_matriz)
        self.tubos = self._cargar_matriz()
        
        # Cargar configuración dinámica de tubos
        from configuracion_tubos import config_tubos
        self.config_tubos = config_tubos
        self.configuracion_tubos = self.config_tubos.obtener_configuracion_tubos()
    
    def _cargar_matriz(self) -> Dict:
        """Cargar matriz existente o crear nueva"""
        try:
            if os.path.exists(self.archivo_matriz):
                with open(self.archivo_matriz, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return self._crear_matriz_vacia()
        except Exception as e:
            print(f"Error cargando matriz: {e}")
            return self._crear_matriz_vacia()
    
    def _crear_matriz_vacia(self) -> Dict:
        """Crear estructura de matriz vacía usando configuración dinámica"""
        tubos_dict = {}
        
        # Usar configuración dinámica si está disponible
        try:
            from configuracion_tubos import config_tubos
            configuracion = config_tubos.obtener_configuracion_tubos()
            
            for tubo_id, config in configuracion.items():
                tubos_dict[str(tubo_id)] = {
                    "y_mm": config["y_mm"], 
                    "cintas": [], 
                    "last_scan": None
                }
        except:
            # Fallback a configuración por defecto
            tubos_dict = {
                "1": {"y_mm": 300, "cintas": [], "last_scan": None},
                "2": {"y_mm": 600, "cintas": [], "last_scan": None}
            }
        
        return {
            "metadata": {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            },
            "tubos": tubos_dict
        }
    
    def guardar_matriz(self):
        """Guardar matriz en archivo JSON"""
        try:
            self.tubos["metadata"]["last_updated"] = datetime.now().isoformat()
            
            with open(self.archivo_matriz, 'w', encoding='utf-8') as f:
                json.dump(self.tubos, f, indent=2, ensure_ascii=False)
            
            print(f"Matriz guardada en: {self.archivo_matriz}")
            return True
        except Exception as e:
            print(f"Error guardando matriz: {e}")
            return False
    
    def guardar_cintas_tubo(self, tubo_id: int, cintas_detectadas: List[Dict]):
        """Guardar cintas detectadas para un tubo específico"""
        tubo_str = str(tubo_id)
        
        if tubo_str not in self.tubos["tubos"]:
            print(f"Error: Tubo {tubo_id} no existe")
            return False
        
        # Actualizar configuración dinámica
        self.configuracion_tubos = self.config_tubos.obtener_configuracion_tubos()
        
        # Preparar datos de cintas
        cintas_procesadas = []
        for i, cinta in enumerate(cintas_detectadas, 1):
            cinta_data = {
                "id": i,
                "x_mm": round(cinta.get('position_mm', 0), 1),
                "y_mm": self.configuracion_tubos[tubo_id]["y_mm"],
                "timestamp": datetime.now().isoformat(),
                "flags": cinta.get('flags', {}),
                "muestras": cinta.get('positions_sampled', 0)
            }
            cintas_procesadas.append(cinta_data)
        
        # Actualizar tubo
        self.tubos["tubos"][tubo_str]["cintas"] = cintas_procesadas
        self.tubos["tubos"][tubo_str]["last_scan"] = datetime.now().isoformat()
        
        # Guardar archivo
        if self.guardar_matriz():
            print(f"{len(cintas_procesadas)} cintas guardadas para {self.configuracion_tubos[tubo_id]['nombre']}")
            return True
        
        return False
    
    def obtener_cintas_tubo(self, tubo_id: int) -> List[Dict]:
        """Obtener cintas de un tubo específico"""
        tubo_str = str(tubo_id)
        
        if tubo_str in self.tubos["tubos"]:
            return self.tubos["tubos"][tubo_str]["cintas"]
        
        return []
    
    def obtener_todas_cintas(self) -> Dict:
        """Obtener todas las cintas de todos los tubos"""
        todas_cintas = {}
        
        # Actualizar configuración dinámica
        self.configuracion_tubos = self.config_tubos.obtener_configuracion_tubos()
        
        for tubo_id, config in self.configuracion_tubos.items():
            cintas = self.obtener_cintas_tubo(tubo_id)
            todas_cintas[tubo_id] = {
                "nombre": config["nombre"],
                "y_mm": config["y_mm"],
                "cintas": cintas,
                "total": len(cintas)
            }
        
        return todas_cintas
    
    def mostrar_resumen(self):
        """Mostrar resumen de la matriz completa"""
        print("\n" + "="*60)
        print("RESUMEN DE MATRIZ DE CINTAS")
        print("="*60)
        
        todas_cintas = self.obtener_todas_cintas()
        total_general = 0
        
        for tubo_id, data in todas_cintas.items():
            print(f"\n{data['nombre']} (Y={data['y_mm']}mm):")
            if data['cintas']:
                for cinta in data['cintas']:
                    print(f"   Cinta #{cinta['id']}: X={cinta['x_mm']}mm, Y={cinta['y_mm']}mm")
                print(f"   Total: {data['total']} cintas")
                total_general += data['total']
            else:
                print("   Sin cintas escaneadas")
        
        print(f"\nTOTAL GENERAL: {total_general} cintas detectadas")
        
        # Información de archivo
        if os.path.exists(self.archivo_matriz):
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.archivo_matriz))
            print(f"📁 Archivo: {self.archivo_matriz}")
            print(f"🕒 Última actualización: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return todas_cintas
    
    def limpiar_tubo(self, tubo_id: int):
        """Limpiar datos de un tubo específico"""
        tubo_str = str(tubo_id)
        
        if tubo_str in self.tubos["tubos"]:
            self.tubos["tubos"][tubo_str]["cintas"] = []
            self.tubos["tubos"][tubo_str]["last_scan"] = None
            
            # Actualizar configuración dinámica
            self.configuracion_tubos = self.config_tubos.obtener_configuracion_tubos()
            
            if self.guardar_matriz():
                print(f"Datos del {self.configuracion_tubos[tubo_id]['nombre']} limpiados")
                return True
        
        return False
    
    def limpiar_todo(self):
        """Limpiar toda la matriz"""
        self.tubos = self._crear_matriz_vacia()
        
        if self.guardar_matriz():
            print("🧹 Matriz completamente limpiada")
            return True
        
        return False

# Instancia global para uso fácil
matriz_cintas = MatrizCintas()

if __name__ == "__main__":
    # Test del sistema
    matriz_cintas.mostrar_resumen()
