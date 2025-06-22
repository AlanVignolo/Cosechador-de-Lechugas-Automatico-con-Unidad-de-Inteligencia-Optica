# ==============================================================================
# SISTEMA COMPLETO DE ANÁLISIS DE LECHUGAS
# ==============================================================================

# PASO 1: Instalar las librerías necesarias
# pip install opencv-python scikit-learn numpy matplotlib

import cv2
import numpy as np
import os
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
import pickle
import json
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from pathlib import Path
import threading
import time

# ==============================================================================
# CLASE PRINCIPAL PARA ENTRENAR EL MODELO
# ==============================================================================

class LettuceAnalyzer:
    def __init__(self, database_path: str = "lettuce_database"):
        self.database_path = Path(database_path)
        self.ready_folder = self.database_path / "ready"
        self.not_ready_folder = self.database_path / "not_ready"
        self.model_path = self.database_path / "model.pkl"
        self.stats_path = self.database_path / "stats.json"
        
        # Crear carpetas si no existen
        self.ready_folder.mkdir(parents=True, exist_ok=True)
        self.not_ready_folder.mkdir(parents=True, exist_ok=True)
        
        self.classifier = None
        self.stats = None
        self.trained = False
        
        print(f"📁 Carpetas creadas:")
        print(f"   - Lechugas listas: {self.ready_folder}")
        print(f"   - Lechugas no listas: {self.not_ready_folder}")
    
    def extract_features(self, image_path: str) -> Dict:
        """Extrae características de color y tamaño de una imagen de lechuga"""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se pudo cargar la imagen: {image_path}")
        
        # Convertir a diferentes espacios de color
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        
        # Crear máscara para segmentar la lechuga (eliminar fondo)
        mask = self._create_lettuce_mask(hsv)
        
        # Calcular área de la lechuga
        area = cv2.countNonZero(mask)
        total_pixels = img.shape[0] * img.shape[1]
        area_ratio = area / total_pixels
        
        # Encontrar contornos para calcular dimensiones
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            diameter_estimate = max(w, h)
            return largest_contour
        else:
            diameter_estimate = 0
        
        # Extraer características de color solo de la región de la lechuga
        lettuce_pixels = img[mask > 0]
        
        if len(lettuce_pixels) == 0:
            return self._default_features()
        
        # Características de color en BGR
        mean_b, mean_g, mean_r = np.mean(lettuce_pixels, axis=0)
        std_b, std_g, std_r = np.std(lettuce_pixels, axis=0)
        
        # Características de color en HSV
        hsv_pixels = hsv[mask > 0]
        mean_h, mean_s, mean_v = np.mean(hsv_pixels, axis=0)
        std_h, std_s, std_v = np.std(hsv_pixels, axis=0)
        
        # Características de color en LAB
        lab_pixels = lab[mask > 0]
        mean_l, mean_a, mean_b_lab = np.mean(lab_pixels, axis=0)
        
        # Índice de verdor (más verde = más maduro generalmente)
        green_intensity = mean_g - (mean_r + mean_b) / 2
        
        # Análisis de distribución de colores dominantes
        dominant_colors = self._get_dominant_colors(lettuce_pixels)
        
        features = {
            # Características de tamaño
            'area_ratio': area_ratio,
            'diameter_estimate': diameter_estimate,
            'area_pixels': area,
            
            # Características de color BGR
            'mean_b': mean_b,
            'mean_g': mean_g,
            'mean_r': mean_r,
            'std_b': std_b,
            'std_g': std_g,
            'std_r': std_r,
            
            # Características de color HSV
            'mean_hue': mean_h,
            'mean_saturation': mean_s,
            'mean_value': mean_v,
            'std_hue': std_h,
            'std_saturation': std_s,
            'std_value': std_v,
            
            # Características de color LAB
            'mean_lightness': mean_l,
            'mean_a': mean_a,
            'mean_b_lab': mean_b_lab,
            
            # Índices derivados
            'green_intensity': green_intensity,
            'color_uniformity': 1 / (1 + np.mean([std_r, std_g, std_b])),
            
            # Colores dominantes
            'dominant_color_1_r': dominant_colors[0][0],
            'dominant_color_1_g': dominant_colors[0][1],
            'dominant_color_1_b': dominant_colors[0][2],
            'dominant_color_2_r': dominant_colors[1][0],
            'dominant_color_2_g': dominant_colors[1][1],
            'dominant_color_2_b': dominant_colors[1][2],
        }
        
        return features
    
    def _create_lettuce_mask(self, hsv_img):
        """Crea una máscara para segmentar la lechuga del fondo"""
        # Rango de colores verdes en HSV
        lower_green1 = np.array([35, 40, 40])
        upper_green1 = np.array([85, 255, 255])
        
        # Rango adicional para verdes más claros
        lower_green2 = np.array([25, 30, 30])
        upper_green2 = np.array([95, 255, 255])
        
        mask1 = cv2.inRange(hsv_img, lower_green1, upper_green1)
        mask2 = cv2.inRange(hsv_img, lower_green2, upper_green2)
        mask = cv2.bitwise_or(mask1, mask2)
        
        # Operaciones morfológicas para limpiar la máscara
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        return mask
    
    def _get_dominant_colors(self, pixels, k=3):
        """Obtiene los colores dominantes usando K-means"""
        if len(pixels) < k:
            return [(0, 0, 0)] * k
        
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(pixels)
        colors = kmeans.cluster_centers_.astype(int)
        
        return [tuple(color) for color in colors]
    
    def _default_features(self):
        """Retorna características por defecto cuando no se puede segmentar"""
        return {
            'area_ratio': 0, 'diameter_estimate': 0, 'area_pixels': 0,
            'mean_b': 0, 'mean_g': 0, 'mean_r': 0,
            'std_b': 0, 'std_g': 0, 'std_r': 0,
            'mean_hue': 0, 'mean_saturation': 0, 'mean_value': 0,
            'std_hue': 0, 'std_saturation': 0, 'std_value': 0,
            'mean_lightness': 0, 'mean_a': 0, 'mean_b_lab': 0,
            'green_intensity': 0, 'color_uniformity': 0,
            'dominant_color_1_r': 0, 'dominant_color_1_g': 0, 'dominant_color_1_b': 0,
            'dominant_color_2_r': 0, 'dominant_color_2_g': 0, 'dominant_color_2_b': 0,
        }
    
    # ==========================================
    # MÉTODO PRINCIPAL PARA ENTRENAR EL MODELO
    # ==========================================
    
    def process_database(self):
        """🎯 MÉTODO PRINCIPAL: Procesa todas las imágenes en la base de datos y entrena el modelo"""
        print("=" * 60)
        print("🚀 INICIANDO PROCESAMIENTO DE BASE DE DATOS")
        print("=" * 60)
        
        # Verificar que existan imágenes
        ready_images = list(self.ready_folder.glob("*.jpg")) + \
                      list(self.ready_folder.glob("*.png")) + \
                      list(self.ready_folder.glob("*.jpeg"))
        
        not_ready_images = list(self.not_ready_folder.glob("*.jpg")) + \
                          list(self.not_ready_folder.glob("*.png")) + \
                          list(self.not_ready_folder.glob("*.jpeg"))
        
        if len(ready_images) == 0 and len(not_ready_images) == 0:
            print("❌ ERROR: No se encontraron imágenes en las carpetas.")
            print("📂 Coloca las imágenes en:")
            print(f"   - {self.ready_folder}")
            print(f"   - {self.not_ready_folder}")
            return False
        
        print(f"📊 Imágenes encontradas:")
        print(f"   - Listas para cosechar: {len(ready_images)}")
        print(f"   - No listas: {len(not_ready_images)}")
        
        features_list = []
        labels = []
        
        # Procesar imágenes listas para cosechar
        print(f"\n🔄 Procesando imágenes LISTAS...")
        for i, img_path in enumerate(ready_images):
            try:
                features = self.extract_features(str(img_path))
                features_list.append(list(features.values()))
                labels.append(1)  # 1 = listo para cosechar
                print(f"   ✅ {i+1}/{len(ready_images)}: {img_path.name}")
            except Exception as e:
                print(f"   ❌ Error con {img_path.name}: {e}")
        
        # Procesar imágenes NO listas para cosechar
        print(f"\n🔄 Procesando imágenes NO LISTAS...")
        for i, img_path in enumerate(not_ready_images):
            try:
                features = self.extract_features(str(img_path))
                features_list.append(list(features.values()))
                labels.append(0)  # 0 = NO listo para cosechar
                print(f"   ✅ {i+1}/{len(not_ready_images)}: {img_path.name}")
            except Exception as e:
                print(f"   ❌ Error con {img_path.name}: {e}")
        
        if len(features_list) == 0:
            print("❌ ERROR: No se pudieron procesar imágenes válidas.")
            return False
        
        # Convertir a numpy arrays
        X = np.array(features_list)
        y = np.array(labels)
        
        # Calcular estadísticas
        ready_features = X[y == 1]
        not_ready_features = X[y == 0]
        
        self.stats = {
            'total_images': len(X),
            'ready_images': len(ready_features),
            'not_ready_images': len(not_ready_features),
            'ready_mean': np.mean(ready_features, axis=0).tolist() if len(ready_features) > 0 else [],
            'ready_std': np.std(ready_features, axis=0).tolist() if len(ready_features) > 0 else [],
            'not_ready_mean': np.mean(not_ready_features, axis=0).tolist() if len(not_ready_features) > 0 else [],
            'not_ready_std': np.std(not_ready_features, axis=0).tolist() if len(not_ready_features) > 0 else [],
            'feature_names': list(self._default_features().keys())
        }
        
        # Entrenar el clasificador
        print(f"\n🤖 Entrenando modelo de Machine Learning...")
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10,
            min_samples_split=5
        )
        self.classifier.fit(X, y)
        
        # Guardar modelo y estadísticas
        print(f"💾 Guardando modelo y estadísticas...")
        with open(self.model_path, 'wb') as f:
            pickle.dump(self.classifier, f)
        
        with open(self.stats_path, 'w') as f:
            json.dump(self.stats, f, indent=2)
        
        self.trained = True
        
        # Mostrar resultados finales
        accuracy = self.classifier.score(X, y)
        print("=" * 60)
        print("🎉 ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        print(f"📊 Total de imágenes procesadas: {len(X)}")
        print(f"✅ Imágenes listas: {len(ready_features)}")
        print(f"❌ Imágenes no listas: {len(not_ready_features)}")
        print(f"🎯 Precisión del modelo: {accuracy:.2%}")
        print(f"💾 Archivos guardados:")
        print(f"   - Modelo: {self.model_path}")
        print(f"   - Estadísticas: {self.stats_path}")
        print("=" * 60)
        
        return True

# ==============================================================================
# CLASE PARA ANÁLISIS EN TIEMPO REAL
# ==============================================================================

class RealTimeLettuceAnalyzer:
    def __init__(self, database_path: str = "lettuce_database"):
        self.database_path = Path(database_path)
        self.model_path = self.database_path / "model.pkl"
        self.stats_path = self.database_path / "stats.json"
        
        # Cargar modelo y estadísticas
        self.classifier = None
        self.stats = None
        self.ready_thresholds = {}
        self.load_model_and_stats()
        
        # Variables para análisis en tiempo real
        self.cap = None
        self.analyzing = False
        self.current_result = None
        self.frame_count = 0
        self.analysis_frequency = 30  # Analizar cada 30 frames
        
        # UI elementos
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.colors = {
            'ready': (0, 255, 0),      # Verde
            'not_ready': (0, 0, 255),  # Rojo
            'analyzing': (0, 255, 255), # Amarillo
            'text': (255, 255, 255),   # Blanco
            'bg': (0, 0, 0)            # Negro
        }
    
    def load_model_and_stats(self):
        """Carga el modelo entrenado y las estadísticas de la BD"""
        try:
            # Cargar modelo
            if self.model_path.exists():
                with open(self.model_path, 'rb') as f:
                    self.classifier = pickle.load(f)
                print("✅ Modelo cargado exitosamente")
            else:
                print("❌ No se encontró el modelo entrenado")
                return False
            
            # Cargar estadísticas
            if self.stats_path.exists():
                with open(self.stats_path, 'r') as f:
                    self.stats = json.load(f)
                print("✅ Estadísticas de BD cargadas")
                
                # Calcular umbrales basados en lechugas listas
                self._calculate_ready_thresholds()
            else:
                print("❌ No se encontraron estadísticas de la BD")
                return False
                
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            return False
        
        return True
    
    def _calculate_ready_thresholds(self):
        """Calcula umbrales basados en lechugas listas para cosechar"""
        if not self.stats or not self.stats.get('ready_mean'):
            return
        
        ready_mean = self.stats['ready_mean']
        ready_std = self.stats['ready_std']
        feature_names = self.stats['feature_names']
        
        # Definir umbrales críticos para características importantes
        critical_features = {
            'area_ratio': {'weight': 0.25, 'tolerance': 2.0},
            'diameter_estimate': {'weight': 0.20, 'tolerance': 1.5},
            'mean_g': {'weight': 0.15, 'tolerance': 1.5},
            'green_intensity': {'weight': 0.15, 'tolerance': 1.5},
            'mean_saturation': {'weight': 0.10, 'tolerance': 1.5},
            'color_uniformity': {'weight': 0.10, 'tolerance': 1.5},
            'mean_value': {'weight': 0.05, 'tolerance': 2.0}
        }
        
        self.ready_thresholds = {}
        for i, feature_name in enumerate(feature_names):
            if i < len(ready_mean) and feature_name in critical_features:
                mean_val = ready_mean[i]
                std_val = ready_std[i] if i < len(ready_std) else 1
                tolerance = critical_features[feature_name]['tolerance']
                weight = critical_features[feature_name]['weight']
                
                self.ready_thresholds[feature_name] = {
                    'mean': mean_val,
                    'std': std_val,
                    'min_threshold': mean_val - (tolerance * std_val),
                    'max_threshold': mean_val + (tolerance * std_val),
                    'weight': weight,
                    'tolerance': tolerance
                }
    
    def start_real_time_analysis(self, camera_index=0):
        """Inicia el análisis en tiempo real"""
        if not self.classifier or not self.stats:
            print("❌ Error: Modelo no cargado.")
            print("🔧 Ejecuta primero el entrenamiento del modelo")
            return
        
        print("🎥 Iniciando análisis en tiempo real...")
        print("⌨️ Controles: 'q' para salir, 'r' para reiniciar")
        
        # Resto del código de análisis en tiempo real...
        # (El código completo está en el artefacto anterior)

# ==============================================================================
# FUNCIONES PRINCIPALES PARA EJECUTAR EL SISTEMA
# ==============================================================================

def setup_and_train():
    """🎯 FUNCIÓN PRINCIPAL: Configurar y entrenar el modelo"""
    print("🌱 SISTEMA DE ANÁLISIS DE LECHUGAS")
    print("=" * 50)
    
    # Crear el analizador
    analyzer = LettuceAnalyzer("lettuce_database")
    
    print("\n📋 INSTRUCCIONES:")
    print("1. Coloca imágenes de lechugas LISTAS en:")
    print(f"   {analyzer.ready_folder}")
    print("2. Coloca imágenes de lechugas NO LISTAS en:")
    print(f"   {analyzer.not_ready_folder}")
    print("3. Ejecuta esta función para entrenar el modelo")
    
    # Verificar si ya existe un modelo
    if analyzer.model_path.exists():
        response = input("\n❓ Ya existe un modelo entrenado. ¿Reentrenar? (s/n): ")
        if response.lower() != 's':
            print("✅ Usando modelo existente")
            return analyzer
    
    # Entrenar el modelo
    success = analyzer.process_database()
    
    if success:
        print("\n🎉 ¡Sistema listo para usar!")
        print("💡 Ahora puedes ejecutar start_real_time_analysis()")
    else:
        print("\n❌ Error en el entrenamiento")
        print("🔧 Revisa que las imágenes estén en las carpetas correctas")
    
    return analyzer

def start_real_time_analysis():
    """🎥 FUNCIÓN PRINCIPAL: Iniciar análisis en tiempo real"""
    rt_analyzer = RealTimeLettuceAnalyzer("lettuce_database")
    
    if rt_analyzer.classifier:
        rt_analyzer.start_real_time_analysis(camera_index=0)
    else:
        print("❌ Primero ejecuta setup_and_train()")


def comparar_con_estadisticas(ruta_imagen: str, database_path: str = "lettuce_database"):
    analyzer = LettuceAnalyzer(database_path)
    
    # Cargar estadísticas
    stats_path = Path(database_path) / "stats.json"
    if not stats_path.exists():
        print("❌ No se encontró stats.json. Primero entrená con setup_and_train().")
        return

    with open(stats_path, "r") as f:
        stats = json.load(f)

    ready_mean = stats["ready_mean"]
    ready_std = stats["ready_std"]
    feature_names = stats["feature_names"]

    # Extraer características de la imagen
    features = analyzer.extract_features(ruta_imagen)
    feature_vector = np.array([features[f] for f in feature_names])

    # Evaluar con umbrales: dentro de ±2 desviaciones estándar
    resultado_final = True
    print(f"\n📊 Comparación con estadísticas de lechugas listas:\n")

    for i, nombre in enumerate(feature_names):
        valor = feature_vector[i]
        media = ready_mean[i]
        desvio = ready_std[i]
        min_aceptable = media - 2 * desvio
        max_aceptable = media + 2 * desvio

        en_rango = min_aceptable <= valor <= max_aceptable
        estado = "✅ OK" if en_rango else "❌ FUERA DE RANGO"

        print(f"{nombre:>25}: {valor:.2f} (esperado {media:.2f} ± {2*desvio:.2f}) --> {estado}")
        if not en_rango:
            resultado_final = False

    print("\n🟢 Resultado final:")
    if resultado_final:
        print("✅ La lechuga está LISTA para cosechar.")
    else:
        print("❌ La lechuga NO está lista todavía.")

def cargar_imagen(ruta):
    imagen = cv2.imread(ruta)
    if imagen is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen: {ruta}")
    return imagen

def recortar_con_margen(imagen, contorno, margen=20):
    x, y, w, h = cv2.boundingRect(contorno)
    x0 = max(0, x - margen)
    y0 = max(0, y - margen)
    x1 = min(imagen.shape[1], x + w + margen)
    y1 = min(imagen.shape[0], y + h + margen)
    recorte = imagen[y0:y1, x0:x1]

    contorno_ajustado = contorno.copy()
    contorno_ajustado[:, :, 0] -= x0
    contorno_ajustado[:, :, 1] -= y0

    return recorte, contorno_ajustado, (x0, y0)

def encontrar_extremos(contorno):
    puntos = contorno.reshape(-1, 2)

    punto_izq = tuple(puntos[puntos[:, 0].argmin()])
    punto_der = tuple(puntos[puntos[:, 0].argmax()])
    punto_sup = tuple(puntos[puntos[:, 1].argmin()])
    punto_inf = tuple(puntos[puntos[:, 1].argmax()])
    print(type(punto_der))
    return {
        'izq': punto_izq,
        'der': punto_der,
        'sup': punto_sup,
        'inf': punto_inf
    }
def distancia_cm(p1, p2, px_por_cm):
    dist_px = np.linalg.norm(np.array(p1) - np.array(p2))
    return round(dist_px / px_por_cm, 2)

def dibujar_mediciones(imagen, contorno, dimensiones):
    """Dibuja las líneas de medición perpendiculares en la imagen"""
    imagen_con_medidas = imagen.copy()
    
    # Dibujar contorno
    cv2.drawContours(imagen_con_medidas, [contorno], -1, (0, 255, 0), 2)
    
    # Dibujar puntos extremos
    extremos = dimensiones['extremos']['puntos']
    izq = extremos['izq']
    der = extremos['der']
    sup = extremos['sup']
    inf = extremos['inf']

    # Dibujar los puntos extremos
    for punto, color in [(izq, (0, 0, 255)), (der, (0, 0, 255)),
                         (sup, (255, 0, 255)), (inf, (255, 0, 255))]:
        cv2.circle(imagen_con_medidas, punto, 5, color, -1)
    
    # Dibujar línea horizontal entre izquierda y derecha (proyección en X)
    punto_h1 = (izq[0], der[1])  # misma Y
    punto_h2 = (der[0], der[1])
    cv2.line(imagen_con_medidas, punto_h1, punto_h2, (0, 0, 255), 2)

    # Dibujar línea vertical entre superior e inferior (proyección en Y)
    punto_v1 = (sup[0], sup[1])
    punto_v2 = (sup[0], inf[1])
    cv2.line(imagen_con_medidas, punto_v1, punto_v2, (255, 0, 255), 2)
    return imagen_con_medidas

def segmentar_verde(imagen):
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    verde_bajo = np.array([30, 40, 40])
    verde_alto = np.array([90, 255, 255])
    mascara = cv2.inRange(hsv, verde_bajo, verde_alto)
    kernel = np.ones((5, 5), np.uint8)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel)
    return mascara

def obtener_contorno_principal(mascara):
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None
    return max(contornos, key=cv2.contourArea)

# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    px_por_cm = 24.61
    print("🌱 BIENVENIDO AL SISTEMA DE ANÁLISIS DE LECHUGAS")
    print("=" * 60)
    print("📋 OPCIONES:")
    print("1. setup_and_train() - Entrenar el modelo con tus imágenes")
    print("2. start_real_time_analysis() - Análisis en tiempo real")
    print("=" * 60)
    ruta_lechuga = "/home/brenda/Documents/plantin.jpg"
    img = cargar_imagen(ruta_lechuga)
    mascara = segmentar_verde(img)
    contorno = obtener_contorno_principal(mascara)
    
    recorte, contorno_recortado, offset = recortar_con_margen(img, contorno)
    extremos = encontrar_extremos(contorno_recortado)

    izq = extremos['izq']
    der = extremos['der']
    sup = extremos['sup']
    inf = extremos['inf']
    extremos = {
        'izq': izq,
        'der': der,
        'sup': sup,
        'inf': inf
    }

        

        # Convertir a centímetros
    medidas_cm = {
        'horizontal': distancia_cm(izq, der, px_por_cm),
        'vertical': distancia_cm(sup, inf, px_por_cm)
    }
    dimensiones = {
        'extremos': {
        'puntos': extremos
        },
        'medidas_cm': medidas_cm
    }


    print("🥬 Tamaño real de la lechuga:")
    print(f"↔️ Ancho (izq-der): {medidas_cm['horizontal']} cm")
    print(f"↕️ Alto  (sup-inf): {medidas_cm['vertical']} cm")

        # 4. Mostrar resultados
    img_resultado = dibujar_mediciones(recorte, contorno_recortado, dimensiones)
    plt.figure(figsize=(10, 6))
    plt.imshow(cv2.cvtColor(img_resultado, cv2.COLOR_BGR2RGB))
    plt.title("Lechuga recortada con medidas")
    plt.axis('off')
    plt.show()

    cv2.imwrite("lechuga_con_medidas_recortada.png", img_resultado)
    print("💾 Imagen guardada como 'lechuga_con_medidas_recortada.png'")
    print(extremos)
    # Opción por defecto: entrenar modelo
    print("\n🚀 Ejecutando entrenamiento automático...")
    analyzer = setup_and_train()
    comparar_con_estadisticas(ruta_lechuga)
