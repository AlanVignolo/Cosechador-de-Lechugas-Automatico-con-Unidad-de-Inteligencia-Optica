"""
API SIMPLE PARA CLASIFICAR IMÁGENES
Importa este módulo desde cualquier script para clasificar imágenes individuales
INCLUYE RECORTE AUTOMÁTICO DEL 10% EN CADA LADO
"""

import sys
from pathlib import Path

# Importar el clasificador original
from ClasificadorImagen import ImageClassifier
from ContornosBienfiltrados import EdgeDetectorOptimized


class ClasificadorSimple:
    """
    Interfaz simplificada para clasificar imágenes desde otros scripts
    Aplica recorte automático del 10% en cada lado
    """
    
    def __init__(self, stats_json_path=None):
        """
        Inicializa el clasificador
        
        Args:
            stats_json_path: Ruta al JSON de estadísticas (opcional)
                           Si no se proporciona, usa la ruta por defecto
        """
        # Ruta por defecto al JSON de estadísticas
        if stats_json_path is None:
            stats_json_path = '/home/brenda/Documents/validation/estadisticas_grupos/estadisticas_completas.json'
        
        self.stats_json_path = stats_json_path
        
        # Inicializar detector y clasificador
        print("Inicializando clasificador...")
        self.detector = EdgeDetectorOptimized()
        self.classifier = ImageClassifier(self.detector, self.stats_json_path)
        print("✓ Clasificador listo (recorte automático: 10%)\n")
    
    def clasificar(self, imagen_path, guardar_resultados=False, carpeta_salida=None):
        """
        Clasifica una imagen (aplica recorte automático del 10%)
        
        Args:
            imagen_path: Ruta a la imagen (str o Path)
            guardar_resultados: Si True, guarda visualización y estadísticas
            carpeta_salida: Dónde guardar resultados (None = junto a la imagen)
        
        Returns:
            dict con:
                - clase: Nombre de la clase predicha
                - confianza: Porcentaje de confianza
                - detalles: Dict completo con toda la información
        """
        # Clasificar (el recorte del 10% se aplica automáticamente)
        resultado = self.classifier.classify_image(
            str(imagen_path),
            save_results=guardar_resultados,
            output_folder=carpeta_salida
        )
        
        # Verificar errores
        if 'error' in resultado:
            return {
                'clase': None,
                'confianza': 0,
                'error': resultado['error'],
                'detalles': resultado
            }
        
        # Retornar formato simplificado
        return {
            'clase': resultado['predicted_class'],
            'confianza': resultado['confidence'],
            'detalles': resultado
        }
    
    def clasificar_y_mostrar(self, imagen_path, guardar_resultados=False):
        """
        Clasifica una imagen y muestra el resultado en consola
        
        Args:
            imagen_path: Ruta a la imagen
            guardar_resultados: Si guardar archivos de resultado
        
        Returns:
            dict con resultado
        """
        resultado = self.clasificar(imagen_path, guardar_resultados)
        
        # Mostrar resultado
        self.classifier.print_classification_result(resultado['detalles'])
        
        return resultado


# ============================================================================
# FUNCIÓN RÁPIDA PARA USO DIRECTO
# ============================================================================

def clasificar_imagen(imagen_path, stats_json=None, guardar=False):
    """
    Función rápida para clasificar una imagen sin crear objeto
    Aplica recorte automático del 10% en cada lado
    
    Args:
        imagen_path: Ruta a la imagen
        stats_json: Ruta al JSON de estadísticas (None = usa default)
        guardar: Si guardar resultados visuales
    
    Returns:
        dict con 'clase', 'confianza', 'detalles'
    
    Ejemplo:
        resultado = clasificar_imagen('mi_imagen.jpg')
        print(f"Clase: {resultado['clase']}")
        print(f"Confianza: {resultado['confianza']:.1f}%")
    """
    clasificador = ClasificadorSimple(stats_json)
    return clasificador.clasificar(imagen_path, guardar_resultados=guardar)


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                    CLASIFICADOR - API SIMPLE                          ║
║                  Recorte automático: 10% cada lado                    ║
╚═══════════════════════════════════════════════════════════════════════╝

Ejemplo de uso desde otro script:

    from clasificador_api import clasificar_imagen
    
    resultado = clasificar_imagen('mi_foto.jpg')
    print(f"Clase: {resultado['clase']}")
    print(f"Confianza: {resultado['confianza']:.1f}%")

""")
    
    # Ejemplo con imagen
    if len(sys.argv) > 1:
        imagen = sys.argv[1]
        print(f"Clasificando: {imagen}\n")
        resultado = clasificar_imagen(imagen, guardar=True)
        
        if resultado['clase']:
            print(f"\n{'='*70}")
            print(f"✓ RESULTADO FINAL")
            print(f"{'='*70}")
            print(f"  Clase: {resultado['clase']}")
            print(f"  Confianza: {resultado['confianza']:.1f}%")
        else:
            print(f"\n❌ Error: {resultado.get('error', 'Error desconocido')}")
    else:
        print("💡 Uso desde línea de comandos:")
        print("   python clasificador_api.py ruta/a/imagen.jpg")
        print("\n💡 O importa desde otro script (ver ejemplo arriba)")