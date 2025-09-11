import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.model_selection import train_test_split
import json
from pathlib import Path
import argparse
import logging
from datetime import datetime
import pickle

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LettuceDetector:
    def __init__(self, model_path=None):
        self.model = None
        self.class_names = ['lechuga_lista', 'lechuga_no_lista']
        self.history = None
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
            logger.info(f"Modelo cargado desde {model_path}")
        
    def create_model(self, input_shape=(224, 224, 3), num_classes=None):
        """Crea el modelo CNN para detección de lechugas"""
        if num_classes is None:
            if not self.class_names:
                raise ValueError("No se puede determinar el número de clases. Asegúrate de crear los generadores primero.")
            num_classes = len(self.class_names)
        model = keras.Sequential([
            # Bloque convolucional 1
            layers.Conv2D(32, (3, 3), activation='relu', input_shape=input_shape),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Bloque convolucional 2
            layers.Conv2D(64, (3, 3), activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Bloque convolucional 3
            layers.Conv2D(128, (3, 3), activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Bloque convolucional 4
            layers.Conv2D(256, (3, 3), activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D((2, 2)),
            layers.Dropout(0.25),
            
            # Capas densas
            layers.Flatten(),
            layers.Dense(512, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(256, activation='relu'),
            layers.Dropout(0.5),
            layers.Dense(num_classes, activation='softmax')
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        self.model = model
        logger.info("Modelo creado exitosamente")
        return model
    
    def preprocess_image(self, image_path, target_size=(224, 224)):
        """Preprocesa una imagen para el modelo"""
        try:
            if isinstance(image_path, str):
                img = cv2.imread(image_path)
                if img is None:
                    raise ValueError(f"No se pudo cargar la imagen: {image_path}")
            else:
                img = image_path
            
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, target_size)
            img = img.astype('float32') / 255.0
            return img
        except Exception as e:
            logger.error(f"Error al preprocesar imagen: {e}")
            raise
    
    def verify_dataset_structure(self, data_dir):
        """Verifica que el dataset tenga la estructura correcta"""
        data_path = Path(data_dir)
        if not data_path.exists():
            raise ValueError(f"El directorio {data_dir} no existe")
        
        class_dirs = [d for d in data_path.iterdir() if d.is_dir()]
        if len(class_dirs) == 0:
            raise ValueError(f"No se encontraron subdirectorios de clases en {data_dir}")
        
        total_images = 0
        for class_dir in class_dirs:
            images = list(class_dir.glob('*.jpg')) + list(class_dir.glob('*.png')) + list(class_dir.glob('*.jpeg'))
            logger.info(f"Clase '{class_dir.name}': {len(images)} imágenes")
            total_images += len(images)
        
        if total_images == 0:
            raise ValueError("No se encontraron imágenes en el dataset")
        
        logger.info(f"Dataset verificado: {len(class_dirs)} clases, {total_images} imágenes totales")
        return True
    
    def create_data_generator(self, data_dir, batch_size=32, validation_split=0.2):
        """Crea generadores de datos con aumentación"""
        self.verify_dataset_structure(data_dir)
        
        datagen = keras.preprocessing.image.ImageDataGenerator(
            rescale=1./255,
            rotation_range=20,
            width_shift_range=0.2,
            height_shift_range=0.2,
            horizontal_flip=True,
            zoom_range=0.2,
            brightness_range=[0.8, 1.2],
            validation_split=validation_split
        )
        
        train_generator = datagen.flow_from_directory(
            data_dir,
            target_size=(224, 224),
            batch_size=batch_size,
            class_mode='categorical',
            subset='training',
            shuffle=True
        )
        
        validation_generator = datagen.flow_from_directory(
            data_dir,
            target_size=(224, 224),
            batch_size=batch_size,
            class_mode='categorical',
            subset='validation',
            shuffle=False
        )
        
        # Actualizar class_names con las clases encontradas
        self.class_names = list(train_generator.class_indices.keys())
        logger.info(f"Clases detectadas: {self.class_names}")
        
        return train_generator, validation_generator
    
    def train_model(self, data_dir, epochs=50, batch_size=32, save_path='models/'):
        """Entrena el modelo"""
        # Crear directorio de modelos si no existe
        os.makedirs(save_path, exist_ok=True)
        train_gen, val_gen = self.create_data_generator(data_dir, batch_size)

        if self.model is None:
            self.create_model(num_classes=len(self.class_names))

        #if self.model is None:
          #  self.create_model()
        
        #train_gen, val_gen = self.create_data_generator(data_dir, batch_size)
        
        # Nombre único para el modelo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"lettuce_model_{timestamp}.h5"
        model_path = os.path.join(save_path, model_name)
        
        # Callbacks
        callbacks = [
            keras.callbacks.ModelCheckpoint(
                model_path,
                save_best_only=True,
                monitor='val_accuracy',
                verbose=1
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.2,
                patience=5,
                min_lr=0.0001,
                verbose=1
            ),
            keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True,
                verbose=1
            )
        ]
        
        logger.info(f"Iniciando entrenamiento por {epochs} epochs...")
        history = self.model.fit(
            train_gen,
            epochs=epochs,
            validation_data=val_gen,
            callbacks=callbacks,
            verbose=1
        )
        
        self.history = history
        
        # Guardar historial de entrenamiento
        history_path = os.path.join(save_path, f"history_{timestamp}.pkl")
        with open(history_path, 'wb') as f:
            pickle.dump(history.history, f)
        
        # Guardar información de las clases
        class_info = {
            'class_names': self.class_names,
            'class_indices': train_gen.class_indices
        }
        info_path = os.path.join(save_path, f"class_info_{timestamp}.json")
        with open(info_path, 'w') as f:
            json.dump(class_info, f, indent=2)
        
        logger.info(f"Entrenamiento completado. Modelo guardado en: {model_path}")
        return history, model_path
    
    def load_model(self, model_path):
        """Carga un modelo previamente entrenado"""
        try:
            self.model = keras.models.load_model(model_path)
            logger.info(f"Modelo cargado exitosamente desde: {model_path}")
            
            # Intentar cargar información de clases
            model_dir = os.path.dirname(model_path)
            class_info_files = [f for f in os.listdir(model_dir) if f.startswith('class_info_') and f.endswith('.json')]
            
            if class_info_files:
                info_path = os.path.join(model_dir, class_info_files[-1])  # Tomar el más reciente
                with open(info_path, 'r') as f:
                    class_info = json.load(f)
                    self.class_names = class_info['class_names']
                    logger.info(f"Clases cargadas: {self.class_names}")
            
        except Exception as e:
            logger.error(f"Error al cargar modelo: {e}")
            raise
    
    def evaluate_model(self, test_dir, batch_size=32):
        """Evalúa el modelo en un conjunto de prueba"""
        if self.model is None:
            raise ValueError("No hay modelo cargado")
        
        test_datagen = keras.preprocessing.image.ImageDataGenerator(rescale=1./255)
        test_generator = test_datagen.flow_from_directory(
            test_dir,
            target_size=(224, 224),
            batch_size=batch_size,
            class_mode='categorical',
            shuffle=False
        )
        
        logger.info("Evaluando modelo...")
        evaluation = self.model.evaluate(test_generator, verbose=1)
        
        results = {
            'test_loss': evaluation[0],
            'test_accuracy': evaluation[1]
        }
        
        logger.info(f"Resultados de evaluación: Loss={results['test_loss']:.4f}, Accuracy={results['test_accuracy']:.4f}")
        return results
    
    def detect_lettuce_features(self, image_path):
        """Detecta características específicas de las lechugas"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"No se pudo cargar la imagen: {image_path}")
                
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Rango de color verde para lechugas (mejorado)
            lower_green = np.array([25, 40, 40])
            upper_green = np.array([85, 255, 255])
            
            mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Aplicar operaciones morfológicas para limpiar la máscara
            kernel = np.ones((3,3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            features = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 500:  # Filtrar contornos pequeños
                    perimeter = cv2.arcLength(contour, True)
                    
                    # Aproximar forma
                    epsilon = 0.02 * perimeter
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    
                    # Calcular circularidad
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                    else:
                        circularity = 0
                    
                    # Bounding box
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h if h > 0 else 0
                    
                    features.append({
                        'area': area,
                        'perimeter': perimeter,
                        'circularity': circularity,
                        'aspect_ratio': aspect_ratio,
                        'vertices': len(approx),
                        'bbox': (x, y, w, h),
                        'contour': contour
                    })
            
            return features, img, mask
            
        except Exception as e:
            logger.error(f"Error en detección de características: {e}")
            raise
    
    def predict_image(self, image_path, return_features=True):
        """Predice la clase de una imagen"""
        if self.model is None:
            raise ValueError("Modelo no entrenado. Carga un modelo o ejecuta train_model() primero.")
        
        try:
            img = self.preprocess_image(image_path)
            img = np.expand_dims(img, axis=0)
            
            prediction = self.model.predict(img, verbose=0)
            predicted_class = np.argmax(prediction[0])
            confidence = prediction[0][predicted_class]
            
            result = {
                'imagen': os.path.basename(image_path) if isinstance(image_path, str) else 'imagen_procesada',
                'clase_predicha': self.class_names[predicted_class],
                'confianza': float(confidence),
                'probabilidades': {self.class_names[i]: float(prediction[0][i]) for i in range(len(self.class_names))}
            }
            
            # Análisis adicional de características
            if return_features:
                try:
                    features, _, _ = self.detect_lettuce_features(image_path)
                    result.update({
                        'num_contornos_detectados': len(features),
                        'caracteristicas_detectadas': features[:5]  # Primeras 5 características
                    })
                except Exception as e:
                    logger.warning(f"No se pudieron extraer características: {e}")
                    result.update({
                        'num_contornos_detectados': 0,
                        'caracteristicas_detectadas': []
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error en predicción: {e}")
            raise
    
    def predict_batch(self, image_paths, batch_size=32):
        """Predice múltiples imágenes de una vez"""
        if self.model is None:
            raise ValueError("Modelo no entrenado.")
        
        results = []
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i+batch_size]
            batch_images = []
            valid_paths = []
            
            for path in batch_paths:
                try:
                    img = self.preprocess_image(path)
                    batch_images.append(img)
                    valid_paths.append(path)
                except Exception as e:
                    logger.warning(f"Error procesando {path}: {e}")
            
            if batch_images:
                batch_array = np.array(batch_images)
                predictions = self.model.predict(batch_array, verbose=0)
                
                for j, (path, pred) in enumerate(zip(valid_paths, predictions)):
                    predicted_class = np.argmax(pred)
                    confidence = pred[predicted_class]
                    
                    result = {
                        'imagen': os.path.basename(path),
                        'clase_predicha': self.class_names[predicted_class],
                        'confianza': float(confidence),
                        'probabilidades': {self.class_names[k]: float(pred[k]) for k in range(len(self.class_names))}
                    }
                    results.append(result)
        
        return results
    
    def visualize_detection(self, image_path, save_path=None):
        """Visualiza la detección en la imagen"""
        try:
            features, img, mask = self.detect_lettuce_features(image_path)
            
            # Crear visualización
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            
            # Imagen original
            axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            axes[0].set_title('Imagen Original')
            axes[0].axis('off')
            
            # Máscara de color
            axes[1].imshow(mask, cmap='gray')
            axes[1].set_title('Máscara Verde')
            axes[1].axis('off')
            
            # Imagen con contornos detectados
            img_contours = img.copy()
            for feature in features:
                cv2.drawContours(img_contours, [feature['contour']], -1, (0, 255, 0), 2)
                x, y, w, h = feature['bbox']
                cv2.rectangle(img_contours, (x, y), (x+w, y+h), (255, 0, 0), 2)
                
                # Añadir información del área
                cv2.putText(img_contours, f"A:{int(feature['area'])}", 
                           (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            axes[2].imshow(cv2.cvtColor(img_contours, cv2.COLOR_BGR2RGB))
            axes[2].set_title(f'Contornos Detectados ({len(features)})')
            axes[2].axis('off')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches='tight')
                logger.info(f"Visualización guardada en: {save_path}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"Error en visualización: {e}")
            raise
    
    def plot_training_history(self, save_path=None):
        """Grafica el historial de entrenamiento"""
        if self.history is None:
            logger.warning("No hay historial de entrenamiento disponible")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # Accuracy
        ax1.plot(self.history.history['accuracy'], label='Entrenamiento')
        ax1.plot(self.history.history['val_accuracy'], label='Validación')
        ax1.set_title('Accuracy del Modelo')
        ax1.set_xlabel('Época')
        ax1.set_ylabel('Accuracy')
        ax1.legend()
        ax1.grid(True)
        
        # Loss
        ax2.plot(self.history.history['loss'], label='Entrenamiento')
        ax2.plot(self.history.history['val_loss'], label='Validación')
        ax2.set_title('Loss del Modelo')
        ax2.set_xlabel('Época')
        ax2.set_ylabel('Loss')
        ax2.legend()
        ax2.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Gráfico guardado en: {save_path}")
        
        plt.show()

# Función mejorada para organizar el dataset
def organize_dataset(source_folder, output_folder):
    """Organiza las imágenes en la estructura correcta para entrenamiento"""
    classes = ['lechuga_lista', 'lechuga_no_lista', 'no_lechuga']
    
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for class_name in classes:
        class_path = output_path / class_name
        class_path.mkdir(parents=True, exist_ok=True)
    
    print("Estructura de carpetas creada:")
    print(f"{output_folder}/")
    for class_name in classes:
        print(f"  ├── {class_name}/")
        print(f"      └── (colocar aquí las imágenes de {class_name})")
    
    # Crear archivo README con instrucciones
    readme_content = """
# Dataset de Lechugas

## Estructura del dataset:
- lechuga_lista/: Imágenes de lechugas listas para cosecha
- lechuga_no_lista/: Imágenes de lechugas no listas para cosecha  
- no_lechuga/: Imágenes que no contienen lechugas

## Instrucciones:
1. Coloca las imágenes en sus respectivas carpetas
2. Formatos soportados: .jpg, .jpeg, .png
3. Se recomienda al menos 100 imágenes por clase
4. Las imágenes serán redimensionadas automáticamente a 224x224

## Uso:
```python
detector = LettuceDetector()
history, model_path = detector.train_model('dataset_lechugas', epochs=50)
```
    """
    
    readme_path = output_path / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    logger.info(f"Dataset organizado en: {output_folder}")
    return output_folder

def main():
    """Función principal con argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description='Detector de Lechugas')
    parser.add_argument('--mode', choices=['organize', 'train', 'predict', 'evaluate'], 
                       required=True, help='Modo de operación')
    parser.add_argument('--data_dir', type=str, help='Directorio del dataset')
    parser.add_argument('--model_path', type=str, help='Ruta del modelo')
    parser.add_argument('--image_path', type=str, help='Ruta de la imagen para predicción')
    parser.add_argument('--epochs', type=int, default=50, help='Número de épocas')
    parser.add_argument('--batch_size', type=int, default=32, help='Tamaño del batch')
    parser.add_argument('--output_dir', type=str, default='results/', help='Directorio de salida')
    
    args = parser.parse_args()
    
    # Crear directorio de salida
    os.makedirs(args.output_dir, exist_ok=True)
    
    if args.mode == 'organize':
        if not args.data_dir:
            logger.error("Se requiere --data_dir para organizar dataset")
            return
        organize_dataset(args.data_dir, 'dataset_lechugas')
    
    elif args.mode == 'train':
        if not args.data_dir:
            logger.error("Se requiere --data_dir para entrenar")
            return
        
        detector = LettuceDetector()
        history, model_path = detector.train_model(
            args.data_dir, 
            epochs=args.epochs, 
            batch_size=args.batch_size,
            save_path=args.output_dir
        )
        
        # Guardar gráfico de entrenamiento
        plot_path = os.path.join(args.output_dir, 'training_history.png')
        detector.plot_training_history(plot_path)
    
    elif args.mode == 'predict':
        if not args.model_path or not args.image_path:
            logger.error("Se requiere --model_path y --image_path para predecir")
            return
        
        detector = LettuceDetector(args.model_path)
        result = detector.predict_image(args.image_path)
        
        print("\n=== RESULTADO DE PREDICCIÓN ===")
        print(f"Imagen: {result['imagen']}")
        print(f"Clase predicha: {result['clase_predicha']}")
        print(f"Confianza: {result['confianza']:.4f}")
        print(f"Contornos detectados: {result['num_contornos_detectados']}")
        
        # Guardar visualización
        vis_path = os.path.join(args.output_dir, f"detection_{os.path.basename(args.image_path)}")
        detector.visualize_detection(args.image_path, vis_path)
        
        # Guardar resultado en JSON
        result_path = os.path.join(args.output_dir, 'prediction_result.json')
        with open(result_path, 'w') as f:
            json.dump(result, f, indent=2)
    
    elif args.mode == 'evaluate':
        if not args.model_path or not args.data_dir:
            logger.error("Se requiere --model_path y --data_dir para evaluar")
            return
        
        detector = LettuceDetector(args.model_path)
        results = detector.evaluate_model(args.data_dir, args.batch_size)
        
        print(f"\n=== RESULTADOS DE EVALUACIÓN ===")
        print(f"Loss: {results['test_loss']:.4f}")
        print(f"Accuracy: {results['test_accuracy']:.4f}")

# Ejemplo de uso interactivo
if __name__ == "__main__":
    # Si no hay argumentos, ejecutar modo interactivo
    import sys
    if len(sys.argv) == 1:
        print("=== DETECTOR DE LECHUGAS ===")
        print("1. Organizar dataset")
        print("2. Entrenar modelo")
        print("3. Predecir imagen")
        print("4. Cargar modelo existente")
        
        choice = input("Selecciona una opción (1-4): ")
        
        if choice == '1':
            source = input("Directorio de imágenes origen: ")
            output = input("Directorio de salida [dataset_lechugas]: ") or "dataset_lechugas"
            organize_dataset(source, output)
        
        elif choice == '2':
            data_dir = "/home/raspberryAlan/proyecto_final/Claudio/Cosechador-de-Lechugas-Automatico-con-Unidad-de-Inteligencia-Optica/Nivel_Supervisor_IA/Analizar Cultivo/Lechugas"
            epochs = int(input("Número de épocas [50]: ") or "50")
            
            detector = LettuceDetector()
            history, model_path = detector.train_model(data_dir, epochs=epochs)
            detector.plot_training_history()
            print(f"Modelo guardado en: {model_path}")
        
        elif choice == '3':
            model_path = input("Ruta del modelo: ")
            image_path = input("Ruta de la imagen: ")
            
            detector = LettuceDetector(model_path)
            result = detector.predict_image(image_path)
            
            print(f"\nClase predicha: {result['clase_predicha']}")
            print(f"Confianza: {result['confianza']:.4f}")
            
            show_vis = input("¿Mostrar visualización? (s/n): ")
            if show_vis.lower() == 's':
                detector.visualize_detection(image_path)
        
        elif choice == '4':
            model_path = input("Ruta del modelo: ")
            detector = LettuceDetector(model_path)
            print(f"Modelo cargado. Clases: {detector.class_names}")
    
    else:
        main()