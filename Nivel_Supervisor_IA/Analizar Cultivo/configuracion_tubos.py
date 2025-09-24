"""
Sistema de Configuración Dinámica de Tubos para Robot CLAUDIO
Gestiona las posiciones Y de los tubos detectadas por el escáner vertical
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class ConfiguracionTubos:
    def __init__(self, archivo_config="configuracion_tubos.json"):
        self.archivo_config = os.path.join(os.path.dirname(__file__), archivo_config)
        self.configuracion = self._cargar_configuracion()
    
    def _cargar_configuracion(self) -> Dict:
        """Cargar configuración existente o crear configuración por defecto"""
        try:
            if os.path.exists(self.archivo_config):
                with open(self.archivo_config, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return self._crear_configuracion_por_defecto()
        except Exception as e:
            print(f"Error cargando configuración de tubos: {e}")
            return self._crear_configuracion_por_defecto()
    
    def _crear_configuracion_por_defecto(self) -> Dict:
        """Crear configuración por defecto con 2 tubos"""
        return {
            "metadata": {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "source": "default"
            },
            "tubos": {
                "1": {"y_mm": 300.0, "nombre": "Tubo 1", "origen": "defecto"},
                "2": {"y_mm": 600.0, "nombre": "Tubo 2", "origen": "defecto"}
            }
        }
    
    def guardar_configuracion(self):
        """Guardar configuración en archivo JSON"""
        try:
            self.configuracion["metadata"]["last_updated"] = datetime.now().isoformat()
            
            with open(self.archivo_config, 'w', encoding='utf-8') as f:
                json.dump(self.configuracion, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error guardando configuración de tubos: {e}")
            return False
    
    def actualizar_desde_escaner_vertical(self, posiciones_y: List[float]):
        """
        Actualizar configuración de tubos basada en resultados del escáner vertical
        
        Args:
            posiciones_y: Lista de posiciones Y detectadas por el escáner vertical (en mm)
        """
        if not posiciones_y:
            print("No hay posiciones Y para actualizar")
            return False
        
        # Ordenar posiciones de menor a mayor (de arriba hacia abajo)
        posiciones_ordenadas = sorted(posiciones_y)
        
        # Limpiar configuración actual
        self.configuracion["tubos"] = {}
        
        # Crear configuración para cada posición detectada
        for i, pos_y in enumerate(posiciones_ordenadas, 1):
            tubo_id = str(i)
            self.configuracion["tubos"][tubo_id] = {
                "y_mm": round(float(pos_y), 1),
                "nombre": f"Tubo {i}",
                "origen": "escaner_vertical"
            }
        
        # Actualizar metadata
        self.configuracion["metadata"]["source"] = "escaner_vertical"
        self.configuracion["metadata"]["num_tubos"] = len(posiciones_ordenadas)
        self.configuracion["metadata"]["scan_timestamp"] = datetime.now().isoformat()
        
        if self.guardar_configuracion():
            print(f"Configuración actualizada con {len(posiciones_ordenadas)} tubos desde escáner vertical")
            self.mostrar_configuracion_actual()
            return True
        
        return False
    
    def obtener_configuracion_tubos(self) -> Dict:
        """Obtener configuración actual de tubos"""
        tubos_config = {}
        
        for tubo_id, data in self.configuracion["tubos"].items():
            tubos_config[int(tubo_id)] = {
                "y_mm": data["y_mm"],
                "nombre": data["nombre"]
            }
        
        return tubos_config
    
    def obtener_numero_tubos(self) -> int:
        """Obtener número total de tubos configurados"""
        return len(self.configuracion["tubos"])
    
    def mostrar_configuracion_actual(self):
        """Mostrar configuración actual de tubos"""
        print("\n" + "="*50)
        print("CONFIGURACIÓN ACTUAL DE TUBOS")
        print("="*50)
        
        source = self.configuracion["metadata"].get("source", "unknown")
        last_updated = self.configuracion["metadata"].get("last_updated", "N/A")
        
        print(f"Fuente: {source}")
        print(f"Última actualización: {last_updated}")
        print(f"Número de tubos: {len(self.configuracion['tubos'])}")
        print("-"*50)
        
        for tubo_id, data in self.configuracion["tubos"].items():
            origen = data.get("origen", "unknown")
            print(f"{data['nombre']}: Y={data['y_mm']}mm (fuente: {origen})")
        
        print("="*50)
    
    def hay_configuracion_desde_escaner(self) -> bool:
        """Verificar si la configuración proviene del escáner vertical"""
        return self.configuracion["metadata"].get("source") == "escaner_vertical"
    
    def resetear_a_defecto(self):
        """Resetear configuración a valores por defecto"""
        self.configuracion = self._crear_configuracion_por_defecto()
        
        if self.guardar_configuracion():
            print("Configuración reseteada a valores por defecto")
            return True
        
        return False

# Instancia global para uso fácil
config_tubos = ConfiguracionTubos()

if __name__ == "__main__":
    # Test del sistema
    config_tubos.mostrar_configuracion_actual()
