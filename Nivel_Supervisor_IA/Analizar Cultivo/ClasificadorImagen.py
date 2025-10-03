"""
Clasificador de Imágenes basado en estadísticas de contornos
Clasifica entre: LECHUGAS, PLANTINES, VASOS (vacío)
"""

import cv2
import numpy as np
import json
from pathlib import Path
import os


class ImageClassifier:
    """
    Clasificador que usa estadísticas de contornos para clasificar imágenes
    """
    
    def __init__(self, edge_detector, stats_json_path=None):
        """
        Inicializa el clasificador
        
        Args:
            edge_detector: Instancia de EdgeDetectorOptimized
            stats_json_path: Ruta al JSON con estadísticas de entrenamiento
        """
        self.detector = edge_detector
        
        # Ruta al JSON de estadísticas
        if stats_json_path is None:
            # Usar ruta relativa al directorio actual
            current_dir = os.path.dirname(os.path.abspath(__file__))
            stats_json_path = os.path.join(current_dir, 'estadisticas_completas.json')
        
        self.stats_json_path = stats_json_path
        self.stats = None
        
        # Cargar estadísticas si existen
        if os.path.exists(self.stats_json_path):
            self.load_statistics()
        else:
            print(f"ADVERTENCIA: No se encontró archivo de estadísticas en: {stats_json_path}")
            print("El clasificador trabajará con valores predeterminados")
            self._create_default_stats()
    
    def load_statistics(self):
        """Carga las estadísticas desde el JSON"""
        try:
            with open(self.stats_json_path, 'r', encoding='utf-8') as f:
                self.stats = json.load(f)
            print(f"Estadísticas cargadas desde: {self.stats_json_path}")
        except Exception as e:
            print(f"Error cargando estadísticas: {e}")
            self._create_default_stats()
    
    def _create_default_stats(self):
        """Crea estadísticas predeterminadas basadas en valores típicos"""
        self.stats = {
            'LECHUGAS': {
                'green_ratio': {'mean': 0.65, 'std': 0.15},
                'black_ratio': {'mean': 0.35, 'std': 0.15},
                'total_pixels': {'mean': 50000, 'std': 20000}
            },
            'PLANTINES': {
                'green_ratio': {'mean': 0.45, 'std': 0.15},
                'black_ratio': {'mean': 0.55, 'std': 0.15},
                'total_pixels': {'mean': 30000, 'std': 15000}
            },
            'VASOS': {
                'green_ratio': {'mean': 0.05, 'std': 0.10},
                'black_ratio': {'mean': 0.95, 'std': 0.10},
                'total_pixels': {'mean': 15000, 'std': 10000}
            }
        }
    
    def classify_image(self, image_path, save_results=False, output_folder=None):
        """
        Clasifica una imagen
        
        Args:
            image_path: Ruta a la imagen
            save_results: Si True, guarda visualizaciones
            output_folder: Carpeta donde guardar resultados
        
        Returns:
            dict con resultado de clasificación
        """
        # Leer imagen
        image = cv2.imread(str(image_path))
        if image is None:
            return {'error': f'No se pudo leer la imagen: {image_path}'}
        
        # Aplicar recorte del 10% en cada lado
        h, w = image.shape[:2]
        margin_h = int(h * 0.10)
        margin_w = int(w * 0.10)
        image_cropped = image[margin_h:h-margin_h, margin_w:w-margin_w]
        
        # Detectar bordes y obtener contornos
        try:
            binary, contours = self.detector.detect_edges(image_cropped)
        except Exception as e:
            return {'error': f'Error en detección de bordes: {e}'}
        
        # Verificar si hay contornos
        if not contours or len(contours) == 0:
            return {
                'predicted_class': 'VASOS',
                'confidence': 0.95,
                'reason': 'No se detectaron contornos (vaso vacío)',
                'statistics': None
            }
        
        # Obtener estadísticas del contorno principal
        if not hasattr(self.detector, 'last_contour_stats') or not self.detector.last_contour_stats:
            return {'error': 'No se pudieron calcular estadísticas de contornos'}
        
        # Usar el primer contorno (el más relevante)
        contour_stats = self.detector.last_contour_stats[0]
        
        # Clasificar basándose en las estadísticas
        predicted_class, confidence = self._classify_by_stats(contour_stats)
        
        # Guardar resultados si se solicita
        if save_results:
            self._save_results(image_path, image_cropped, binary, predicted_class, 
                             confidence, contour_stats, output_folder)
        
        return {
            'predicted_class': predicted_class,
            'confidence': confidence,
            'statistics': contour_stats,
            'image_path': str(image_path)
        }
    
    def _classify_by_stats(self, contour_stats):
        """
        Clasifica basándose en estadísticas del contorno
        
        Returns:
            tuple: (clase_predicha, confianza)
        """
        green_ratio = contour_stats.get('green_ratio', 0)
        black_ratio = contour_stats.get('black_ratio', 0)
        total_pixels = contour_stats.get('green_pixels', 0) + contour_stats.get('black_pixels', 0)
        
        # Calcular distancias a cada clase (distancia euclidiana normalizada)
        distances = {}
        
        for class_name, class_stats in self.stats.items():
            # Distancia en green_ratio
            green_mean = class_stats['green_ratio']['mean']
            green_std = class_stats['green_ratio']['std']
            green_dist = abs(green_ratio - green_mean) / (green_std + 1e-6)
            
            # Distancia en black_ratio
            black_mean = class_stats['black_ratio']['mean']
            black_std = class_stats['black_ratio']['std']
            black_dist = abs(black_ratio - black_mean) / (black_std + 1e-6)
            
            # Distancia combinada (más peso a ratios de color)
            combined_dist = np.sqrt(green_dist**2 + black_dist**2)
            distances[class_name] = combined_dist
        
        # La clase con menor distancia es la predicha
        predicted_class = min(distances, key=distances.get)
        
        # Calcular confianza (inversa de la distancia, normalizada)
        min_dist = distances[predicted_class]
        max_dist = max(distances.values())
        
        # Confianza: 1.0 cuando dist=0, baja cuando dist es grande
        if max_dist > 0:
            confidence = 1.0 - (min_dist / (max_dist + min_dist))
        else:
            confidence = 1.0
        
        # Asegurar que la confianza esté entre 0.3 y 1.0
        confidence = max(0.3, min(1.0, confidence))
        
        return predicted_class, confidence
    
    def _save_results(self, image_path, image, binary, predicted_class, 
                     confidence, stats, output_folder):
        """Guarda visualizaciones de los resultados"""
        if output_folder is None:
            output_folder = os.path.dirname(image_path)
        
        os.makedirs(output_folder, exist_ok=True)
        
        base_name = Path(image_path).stem
        
        # Guardar imagen binaria
        binary_path = os.path.join(output_folder, f"{base_name}_binary.jpg")
        cv2.imwrite(binary_path, binary)
        
        # Crear visualización con resultado
        result_img = image.copy()
        h, w = result_img.shape[:2]
        
        # Agregar texto con resultado
        text = f"{predicted_class} ({confidence:.1%})"
        cv2.putText(result_img, text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        result_path = os.path.join(output_folder, f"{base_name}_result.jpg")
        cv2.imwrite(result_path, result_img)
    
    def print_classification_result(self, result):
        """Imprime el resultado de clasificación de forma legible"""
        if 'error' in result:
            print(f"ERROR: {result['error']}")
            return
        
        print("\n" + "="*70)
        print("RESULTADO DE CLASIFICACIÓN")
        print("="*70)
        print(f"Clase predicha: {result['predicted_class']}")
        print(f"Confianza: {result['confidence']:.1%}")
        
        if result.get('statistics'):
            stats = result['statistics']
            print(f"\nEstadísticas del contorno:")
            print(f"  Píxeles verdes: {stats.get('green_pixels', 0)}")
            print(f"  Píxeles negros: {stats.get('black_pixels', 0)}")
            print(f"  Ratio verde: {stats.get('green_ratio', 0):.2%}")
            print(f"  Ratio negro: {stats.get('black_ratio', 0):.2%}")
        
        print("="*70 + "\n")
