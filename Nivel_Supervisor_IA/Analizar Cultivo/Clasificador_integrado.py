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
        # Ruta por defecto al JSON de estadísticas (relativa al archivo actual)
        if stats_json_path is None:
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            stats_json_path = os.path.join(current_dir, 'estadisticas_completas.json')

        self.stats_json_path = stats_json_path

        # Inicializar detector y clasificador (silencioso)
        self.detector = EdgeDetectorOptimized()
        self.classifier = ImageClassifier(self.detector, self.stats_json_path)
    
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
# FUNCIÓN RÁPIDA PARA USO DIRECTO (CON SINGLETON)
# ============================================================================

# Singleton global del clasificador
_clasificador_singleton = None

def clasificar_imagen(imagen_path, stats_json=None, guardar=False, debug=False):
    """
    Función rápida para clasificar una imagen sin crear objeto
    Aplica recorte automático del 10% en cada lado
    Usa un singleton para evitar reinicializar el clasificador en cada llamada

    Args:
        imagen_path: Ruta a la imagen
        stats_json: Ruta al JSON de estadísticas (None = usa default)
        guardar: Si guardar resultados visuales
        debug: Si mostrar visualización paso a paso (default: False)

    Returns:
        dict con 'clase', 'confianza', 'detalles'

    Ejemplo:
        resultado = clasificar_imagen('mi_imagen.jpg')
        print(f"Clase: {resultado['clase']}")
        print(f"Confianza: {resultado['confianza']:.1f}%")
    """
    global _clasificador_singleton

    # Inicializar solo la primera vez
    if _clasificador_singleton is None:
        _clasificador_singleton = ClasificadorSimple(stats_json)

    resultado = _clasificador_singleton.clasificar(imagen_path, guardar_resultados=guardar)

    # Modo debug: mostrar pasos del procesamiento
    if debug and resultado['clase'] is not None:
        import cv2
        import os

        # Cargar imagen
        img = cv2.imread(str(imagen_path))
        if img is not None:
            # 1. Imagen original
            cv2.imshow("DEBUG CLASIFICACION: 1. IMAGEN ORIGINAL", img)
            cv2.resizeWindow("DEBUG CLASIFICACION: 1. IMAGEN ORIGINAL", 800, 600)
            print("1. Imagen original capturada - Presiona 'c' para continuar...")
            while True:
                if cv2.waitKey(1) & 0xFF == ord('c'):
                    break
            cv2.destroyAllWindows()

            # 2. Recorte 10%
            alto, ancho = img.shape[:2]
            margin_h = int(alto * 0.10)
            margin_w = int(ancho * 0.10)
            img_recortada = img[margin_h:alto-margin_h, margin_w:ancho-margin_w]

            cv2.imshow("DEBUG CLASIFICACION: 2. RECORTE 10%", img_recortada)
            cv2.resizeWindow("DEBUG CLASIFICACION: 2. RECORTE 10%", 800, 600)
            print("2. Imagen con recorte del 10% aplicado - Presiona 'c' para continuar...")
            while True:
                if cv2.waitKey(1) & 0xFF == ord('c'):
                    break
            cv2.destroyAllWindows()

            # 3. Conversión a HSV y extracción de canal V
            hsv = cv2.cvtColor(img_recortada, cv2.COLOR_BGR2HSV)
            v_channel = hsv[:,:,2]

            cv2.imshow("DEBUG CLASIFICACION: 3. CANAL V (BRILLO)", v_channel)
            cv2.resizeWindow("DEBUG CLASIFICACION: 3. CANAL V (BRILLO)", 800, 600)
            print("3. Canal V extraído (brillo) - Presiona 'c' para continuar...")
            while True:
                if cv2.waitKey(1) & 0xFF == ord('c'):
                    break
            cv2.destroyAllWindows()

            # 4. Aplicar Canny para detección de bordes
            edges = cv2.Canny(v_channel, 50, 150)

            cv2.imshow("DEBUG CLASIFICACION: 4. BORDES DETECTADOS (CANNY)", edges)
            cv2.resizeWindow("DEBUG CLASIFICACION: 4. BORDES DETECTADOS (CANNY)", 800, 600)
            print("4. Bordes detectados con filtro Canny - Presiona 'c' para continuar...")
            while True:
                if cv2.waitKey(1) & 0xFF == ord('c'):
                    break
            cv2.destroyAllWindows()

            # 5. Encontrar contornos
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            img_contours = img_recortada.copy()
            cv2.drawContours(img_contours, contours, -1, (0, 255, 0), 2)

            cv2.imshow("DEBUG CLASIFICACION: 5. CONTORNOS DETECTADOS", img_contours)
            cv2.resizeWindow("DEBUG CLASIFICACION: 5. CONTORNOS DETECTADOS", 800, 600)
            print(f"5. Contornos detectados ({len(contours)} contornos) - Presiona 'c' para continuar...")
            while True:
                if cv2.waitKey(1) & 0xFF == ord('c'):
                    break
            cv2.destroyAllWindows()

    return resultado


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