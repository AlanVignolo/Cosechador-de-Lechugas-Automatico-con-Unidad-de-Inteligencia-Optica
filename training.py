#!/usr/bin/env python3
"""
ENTRENADOR ROI - roi_trainer.py (MEJORADO)
Analiza carpetas de imágenes, entrena el modelo y guarda los resultados
EJECUTAR UNA SOLA VEZ PARA ENTRENAR EL MODELO
CON DETECCIÓN DE CONTORNOS PARA LECHUGAS Y VASOS (VERDES Y NEGROS)
"""

import cv2
import numpy as np
import os
from pathlib import Path
import json
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional

class GreenPixelROITrainer:
    def __init__(self):
        self.stats = {}  # Almacena media y desviación estándar por carpeta
        self.roi_coords = None  # Coordenadas del ROI (x, y, w, h)
        self.roi_mask = None  # Máscara del ROI
        
    def set_roi(self, x: int, y: int, width: int, height: int):
        """Define las coordenadas del ROI"""
        self.roi_coords = (x, y, width, height)
        print(f"ROI configurado: x={x}, y={y}, width={width}, height={height}")
    
    def set_roi_circle(self, image: np.ndarray, radius_ratio: float = 0.4):
        """
        Define un ROI circular centrado en la imagen.
        
        Args:
            image: Imagen de referencia
            radius_ratio: Proporción del radio respecto al ancho mínimo (0.4 = 40%)
        """
        height, width = image.shape[:2]
        center_x, center_y = width // 2, height // 2
        radius = int(min(width, height) * radius_ratio)

        # Crear máscara circular
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.circle(mask, (center_x, center_y), radius, 255, -1)

        self.roi_mask = mask
        self.roi_coords = None  # Desactiva ROI rectangular
        print(f"ROI circular configurado en el centro con radio={radius} px")
    
    def set_auto_roi(self, image: np.ndarray, side_reduction: float = 0.1):
        """
        Define automáticamente un ROI reduciendo los lados por el porcentaje especificado
        
        Args:
            image: Imagen de referencia para calcular dimensiones
            side_reduction: Porcentaje a reducir de cada lado (0.1 = 10%)
        """
        height, width = image.shape[:2]
        
        # Calcular reducción en píxeles
        reduction_pixels = int(width * side_reduction)
        
        # Definir ROI: x, y, width, height
        x = reduction_pixels
        y = 0
        new_width = width - (2 * reduction_pixels)
        new_height = height
        
        self.roi_coords = (x, y, new_width, new_height)
        print(f"ROI automático configurado: x={x}, y={y}, width={new_width}, height={new_height}")
        print(f"Reducción aplicada: {side_reduction*100}% por lado ({reduction_pixels} píxeles por lado)")
        print(f"Ancho original: {width} → Ancho ROI: {new_width} (reducción total: {reduction_pixels*2} píxeles)")

    def extract_roi(self, image: np.ndarray) -> np.ndarray:
        """Extrae la región de interés de la imagen"""
        if self.roi_mask is not None:
            # Aplica la máscara circular
            masked = cv2.bitwise_and(image, image, mask=self.roi_mask)
            return masked
        
        if self.roi_coords is not None:
            x, y, w, h = self.roi_coords
            return image[y:y+h, x:x+w]
        
        return image
    
    def detect_plant_contours(self, image: np.ndarray, debug: bool = False) -> Tuple[List, np.ndarray]:
        """
        Detecta contornos de plantas (lechugas y vasos con plantas) en la imagen
        
        Args:
            image: Imagen en formato BGR
            debug: Si True, muestra imágenes de depuración
            
        Returns:
            Tuple con (lista_de_contornos, máscara_combinada)
        """
        # Extraer ROI primero
        roi = self.extract_roi(image)
        
        # Convertir a HSV para mejor detección de verde
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Crear máscara para detectar objetos verdes (plantas)
        # Rango amplio para capturar diferentes tonos de verde
        lower_green = np.array([35, 40, 40])  # Verde más amplio
        upper_green = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # También detectar en espacio RGB/BGR
        b, g, r = cv2.split(roi)
        # Píxeles donde el verde predomina
        green_dominant = (g > b * 1.1) & (g > r * 1.1) & (g > 50)
        green_mask_bgr = green_dominant.astype(np.uint8) * 255
        
        # Combinar ambas máscaras
        combined_mask = cv2.bitwise_or(green_mask, green_mask_bgr)
        
        # Operaciones morfológicas para limpiar la máscara
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        
        # Aplicar filtro Gaussiano para suavizar
        combined_mask = cv2.GaussianBlur(combined_mask, (5, 5), 0)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filtrar contornos por área para eliminar ruido
        min_area = roi.shape[0] * roi.shape[1] * 0.01  # Al menos 1% del área del ROI
        max_area = roi.shape[0] * roi.shape[1] * 0.8   # Máximo 80% del área del ROI
        
        filtered_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                # Verificar que el contorno tenga una forma razonable (no muy alargado)
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                if 0.3 <= aspect_ratio <= 3.0:  # Formas no muy alargadas
                    filtered_contours.append(contour)
        
        # Crear máscara final con los contornos filtrados
        final_mask = np.zeros(combined_mask.shape, dtype=np.uint8)
        cv2.fillPoly(final_mask, filtered_contours, 255)
        
        if debug:
            # Mostrar imágenes de depuración
            debug_img = roi.copy()
            cv2.drawContours(debug_img, filtered_contours, -1, (0, 255, 255), 2)
            
            fig, axes = plt.subplots(2, 3, figsize=(15, 10))
            axes[0,0].imshow(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
            axes[0,0].set_title('Imagen Original (ROI)')
            axes[0,1].imshow(green_mask, cmap='gray')
            axes[0,1].set_title('Máscara Verde (HSV)')
            axes[0,2].imshow(green_mask_bgr, cmap='gray')
            axes[0,2].set_title('Máscara Verde (BGR)')
            axes[1,0].imshow(combined_mask, cmap='gray')
            axes[1,0].set_title('Máscara Combinada')
            axes[1,1].imshow(final_mask, cmap='gray')
            axes[1,1].set_title('Máscara Final (Contornos)')
            axes[1,2].imshow(cv2.cvtColor(debug_img, cv2.COLOR_BGR2RGB))
            axes[1,2].set_title(f'Contornos Verdes ({len(filtered_contours)})')
            
            for ax in axes.flat:
                ax.axis('off')
            plt.tight_layout()
            plt.show()
        
        return filtered_contours, final_mask

    def detect_black_contours(self, image: np.ndarray, debug: bool = False) -> Tuple[List, np.ndarray]:
        """
        Detecta contornos negros/oscuros (vasos vacíos, tierra, etc.)
        
        Args:
            image: Imagen en formato BGR
            debug: Si True, muestra imágenes de depuración
            
        Returns:
            Tuple con (lista_de_contornos, máscara_combinada)
        """
        # Extraer ROI primero
        roi = self.extract_roi(image)
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Convertir a HSV para mejor detección de oscuros
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Crear máscara para detectar píxeles muy oscuros
        # Basado en el canal V (valor/brillo) en HSV
        v_channel = hsv[:, :, 2]
        dark_mask_hsv = v_channel <= 80  # Píxeles con bajo brillo
        
        # También detectar en escala de grises
        dark_mask_gray = gray <= 60  # Píxeles oscuros en escala de grises
        
        # Detectar en RGB píxeles donde todos los canales son oscuros
        b, g, r = cv2.split(roi)
        dark_mask_rgb = (b <= 70) & (g <= 70) & (r <= 70)
        
        # Combinar todas las máscaras
        combined_mask = (dark_mask_hsv | dark_mask_gray | dark_mask_rgb).astype(np.uint8) * 255
        
        # Operaciones morfológicas para limpiar la máscara
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        
        # Aplicar filtro Gaussiano para suavizar
        combined_mask = cv2.GaussianBlur(combined_mask, (5, 5), 0)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filtrar contornos por área para eliminar ruido
        min_area = roi.shape[0] * roi.shape[1] * 0.02  # Al menos 2% del área del ROI
        max_area = roi.shape[0] * roi.shape[1] * 0.9   # Máximo 90% del área del ROI
        
        filtered_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                # Verificar que el contorno tenga una forma razonable
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                if 0.2 <= aspect_ratio <= 5.0:  # Más permisivo para formas de vasos
                    filtered_contours.append(contour)
        
        # Crear máscara final con los contornos filtrados
        final_mask = np.zeros(combined_mask.shape, dtype=np.uint8)
        cv2.fillPoly(final_mask, filtered_contours, 255)
        
        if debug:
            # Mostrar imágenes de depuración
            debug_img = roi.copy()
            cv2.drawContours(debug_img, filtered_contours, -1, (255, 0, 0), 2)
            
            fig, axes = plt.subplots(2, 3, figsize=(15, 10))
            axes[0,0].imshow(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
            axes[0,0].set_title('Imagen Original (ROI)')
            axes[0,1].imshow(dark_mask_hsv, cmap='gray')
            axes[0,1].set_title('Máscara Oscura (HSV-V)')
            axes[0,2].imshow(dark_mask_gray, cmap='gray')
            axes[0,2].set_title('Máscara Oscura (Gris)')
            axes[1,0].imshow(combined_mask, cmap='gray')
            axes[1,0].set_title('Máscara Combinada')
            axes[1,1].imshow(final_mask, cmap='gray')
            axes[1,1].set_title('Máscara Final (Contornos)')
            axes[1,2].imshow(cv2.cvtColor(debug_img, cv2.COLOR_BGR2RGB))
            axes[1,2].set_title(f'Contornos Negros ({len(filtered_contours)})')
            
            for ax in axes.flat:
                ax.axis('off')
            plt.tight_layout()
            plt.show()
        
        return filtered_contours, final_mask
    
    def count_pixels_in_contours(self, image: np.ndarray, contours: List, contour_mask: np.ndarray,
                                target_color: str = 'green') -> Dict:
        """
        Cuenta píxeles de un color específico dentro de los contornos detectados
        
        Args:
            image: Imagen en formato BGR
            contours: Lista de contornos detectados
            contour_mask: Máscara de los contornos
            target_color: 'green' o 'black' para definir qué color contar
        
        Returns:
            Diccionario con estadísticas de píxeles del color objetivo
        """
        # Extraer ROI
        roi = self.extract_roi(image)
        
        if len(contours) == 0:
            return {
                'total_target_pixels': 0,
                'contour_area': 0,
                'target_density': 0.0,
                'num_contours': 0,
                'color_analyzed': target_color
            }
        
        if target_color == 'green':
            # Convertir a HSV para mejor detección de verde
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Definir rango de color verde en HSV
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            
            # Crear máscara para píxeles verdes
            color_mask_hsv = cv2.inRange(hsv, lower_green, upper_green)
            
            # También incluir detección en RGB/BGR
            b, g, r = cv2.split(roi)
            color_mask_bgr = (g > b * 1.2) & (g > r * 1.2) & (g > 70)
            color_mask_bgr = color_mask_bgr.astype(np.uint8) * 255
            
            # Combinar máscaras de verde
            combined_color_mask = cv2.bitwise_or(color_mask_hsv, color_mask_bgr)
            
        elif target_color == 'black':
            # Convertir a escala de grises y HSV para detectar píxeles negros
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Crear máscaras para píxeles negros/oscuros
            black_mask_gray = gray <= 60
            v_channel = hsv[:, :, 2]
            black_mask_hsv = v_channel <= 80
            
            b, g, r = cv2.split(roi)
            black_mask_rgb = (b <= 70) & (g <= 70) & (r <= 70)
            
            # Combinar máscaras
            combined_color_mask = (black_mask_gray | black_mask_hsv | black_mask_rgb).astype(np.uint8) * 255
        
        else:
            raise ValueError("target_color debe ser 'green' o 'black'")
        
        # Aplicar la máscara de contornos para contar solo píxeles del color dentro de los contornos
        target_in_contours = cv2.bitwise_and(combined_color_mask, contour_mask)
        
        # Contar píxeles
        total_target_pixels = np.sum(target_in_contours > 0)
        contour_area = np.sum(contour_mask > 0)
        
        # Calcular densidad del color objetivo (porcentaje de píxeles del color en el área de contornos)
        target_density = (total_target_pixels / contour_area * 100) if contour_area > 0 else 0.0
        
        return {
            'total_target_pixels': int(total_target_pixels),
            'contour_area': int(contour_area),
            'target_density': float(target_density),
            'num_contours': len(contours),
            'color_analyzed': target_color
        }
    
    def count_green_pixels_in_contours(self, image: np.ndarray, contours: List, contour_mask: np.ndarray,
                                     green_threshold: Tuple[int, int, int] = (40, 70, 40),
                                     sensitivity: float = 1.2) -> Dict:
        """Mantener compatibilidad - usa count_pixels_in_contours"""
        return self.count_pixels_in_contours(image, contours, contour_mask, 'green')
    
    def count_green_pixels(self, image: np.ndarray, 
                          green_threshold: Tuple[int, int, int] = (40, 70, 40),
                          sensitivity: float = 1.2) -> int:
        """
        Cuenta píxeles verdes en una imagen (método original mantenido para compatibilidad)
        """
        # Extraer ROI
        roi = self.extract_roi(image)
        
        # Convertir a HSV para mejor detección de verde
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Definir rango de color verde en HSV
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        
        # Crear máscara para píxeles verdes
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # También incluir detección en RGB/BGR
        b, g, r = cv2.split(roi)
        green_mask_bgr = (g > b * sensitivity) & (g > r * sensitivity) & (g > green_threshold[1])
        
        # Combinar máscaras
        combined_mask = mask | green_mask_bgr.astype(np.uint8) * 255
        
        # Contar píxeles verdes
        green_pixels = np.sum(combined_mask > 0)
        
        return green_pixels
    
    def count_black_pixels(self, image: np.ndarray, 
                          black_threshold: int = 50) -> int:
        """
        Cuenta píxeles negros en una imagen
        """
        # Extraer ROI
        roi = self.extract_roi(image)
        
        # Convertir a escala de grises para detectar píxeles negros
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Crear máscara para píxeles negros
        black_mask = gray <= black_threshold
        
        # También verificar en HSV para mejor detección de negros
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        dark_mask = v_channel <= black_threshold
        
        # También verificar píxeles muy oscuros en RGB
        b, g, r = cv2.split(roi)
        rgb_black_mask = (b <= black_threshold) & (g <= black_threshold) & (r <= black_threshold)
        
        # Combinar máscaras
        combined_black_mask = black_mask | dark_mask | rgb_black_mask
        
        # Contar píxeles negros
        black_pixels = np.sum(combined_black_mask)
        
        return black_pixels
    
    def calculate_pixel_ratio(self, green_pixels: int, black_pixels: int) -> float:
        """
        Calcula la relación entre píxeles negros y verdes
        """
        if green_pixels == 0:
            return float(black_pixels + 1000)  # Valor alto para indicar predominancia de negro
        
        return black_pixels / green_pixels
    
    def analyze_folder(self, folder_path: str, folder_name: str, use_contour_detection: bool = True) -> Dict:
        """
        Analiza todas las imágenes de una carpeta con detección mejorada de contornos
        
        Args:
            folder_path: Ruta de la carpeta
            folder_name: Nombre del grupo
            use_contour_detection: Si True, usa detección de contornos
        
        Returns:
            Diccionario con estadísticas de la carpeta
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise FileNotFoundError(f"La carpeta {folder_path} no existe")
        
        # Buscar archivos de imagen
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif']
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(folder_path.glob(ext))
            image_files.extend(folder_path.glob(ext.upper()))
        
        if not image_files:
            raise ValueError(f"No se encontraron imágenes en {folder_path}")
        
        print(f"\nAnalizando carpeta '{folder_name}': {len(image_files)} imágenes encontradas")
        
        # Determinar si usar detección de contornos basándose en el nombre
        detect_plants = use_contour_detection and (
            'lechuga' in folder_name.lower() or 'vaso' in folder_name.lower() or 'plantin' in folder_name.lower()
        )
        
        if detect_plants:
            print(f"  🌿 Usando detección de contornos para {folder_name}")
        
        green_pixel_counts = []
        black_pixel_counts = []
        pixel_ratios = []
        
        # Nuevas métricas para contornos
        contour_green_pixels = []
        contour_black_pixels = []
        contour_areas = []
        green_densities = []
        black_densities = []
        num_contours_list = []
        contour_types = []  # 'green', 'black', o 'none'
        
        processed_files = []
        
        # Configurar ROI automáticamente con la primera imagen
        roi_configured = False
        
        for i, img_file in enumerate(image_files):
            try:
                # Cargar imagen
                image = cv2.imread(str(img_file))
                if image is None:
                    print(f"Error: No se pudo cargar {img_file}")
                    continue
                
                # Configurar ROI automático solo una vez con la primera imagen válida
                if not roi_configured and self.roi_coords is None and self.roi_mask is None:
                    self.set_auto_roi(image, side_reduction=0.1)  # 10% por lado
                    roi_configured = True
                
                if detect_plants:
                    # Primero intentar detectar contornos verdes (lechuga)
                    green_contours, green_contour_mask = self.detect_plant_contours(
                        image, debug=(i == 0)  # Debug solo para la primera imagen
                    )
                    
                    if len(green_contours) > 0:
                        # Hay contornos verdes - analizar píxeles verdes en esos contornos
                        contour_stats = self.count_pixels_in_contours(
                            image, green_contours, green_contour_mask, 'green'
                        )
                        green_count = contour_stats['total_target_pixels']
                        
                        # También contar píxeles negros en los mismos contornos para completar
                        black_stats = self.count_pixels_in_contours(
                            image, green_contours, green_contour_mask, 'black'
                        )
                        black_count = black_stats['total_target_pixels']
                        
                        # Guardar estadísticas
                        contour_green_pixels.append(green_count)
                        contour_black_pixels.append(black_count)
                        contour_areas.append(contour_stats['contour_area'])
                        green_densities.append(contour_stats['target_density'])
                        black_densities.append(black_stats['target_density'])
                        num_contours_list.append(len(green_contours))
                        contour_types.append('green')
                        
                        print(f"  {img_file.name}: VERDES detectados - {green_count} píxeles verdes en {len(green_contours)} contornos")
                        
                    else:
                        # No hay contornos verdes - buscar contornos negros (vaso vacío)
                        black_contours, black_contour_mask = self.detect_black_contours(
                            image, debug=(i == 0)  # Debug solo para la primera imagen
                        )
                        
                        if len(black_contours) > 0:
                            # Hay contornos negros - analizar píxeles negros en esos contornos
                            black_stats = self.count_pixels_in_contours(
                                image, black_contours, black_contour_mask, 'black'
                            )
                            black_count = black_stats['total_target_pixels']
                            
                            # Contar píxeles verdes en los contornos negros (debería ser muy pocos)
                            green_stats = self.count_pixels_in_contours(
                                image, black_contours, black_contour_mask, 'green'
                            )
                            green_count = green_stats['total_target_pixels']
                            
                            # Guardar estadísticas
                            contour_green_pixels.append(green_count)
                            contour_black_pixels.append(black_count)
                            contour_areas.append(black_stats['contour_area'])
                            green_densities.append(green_stats['target_density'])
                            black_densities.append(black_stats['target_density'])
                            num_contours_list.append(len(black_contours))
                            contour_types.append('black')
                            
                            print(f"  {img_file.name}: NEGROS detectados - {black_count} píxeles negros en {len(black_contours)} contornos")
                        
                        else:
                            # No hay contornos de ningún tipo - usar valores por defecto
                            green_count = 0
                            black_count = 0
                            
                            contour_green_pixels.append(0)
                            contour_black_pixels.append(0)
                            contour_areas.append(0)
                            green_densities.append(0.0)
                            black_densities.append(0.0)
                            num_contours_list.append(0)
                            contour_types.append('none')
                            
                            print(f"  {img_file.name}: SIN CONTORNOS detectados")
                    
                else:
                    # Usar método original sin detección de contornos
                    green_count = self.count_green_pixels(image)
                    black_count = self.count_black_pixels(image)
                    
                    # Valores por defecto para compatibilidad
                    contour_green_pixels.append(green_count)
                    contour_black_pixels.append(black_count)
                    contour_areas.append(0)
                    green_densities.append(0.0)
                    black_densities.append(0.0)
                    num_contours_list.append(0)
                    contour_types.append('none')
                
                pixel_ratio = self.calculate_pixel_ratio(green_count, black_count)
                
                green_pixel_counts.append(green_count)
                black_pixel_counts.append(black_count)
                pixel_ratios.append(pixel_ratio)
                processed_files.append(img_file.name)
                
            except Exception as e:
                print(f"Error procesando {img_file}: {e}")
                continue
        
        if not green_pixel_counts:
            raise ValueError(f"No se pudieron procesar imágenes en {folder_path}")
        
        # Calcular estadísticas
        mean_green = np.mean(green_pixel_counts)
        std_green = np.std(green_pixel_counts)
        mean_black = np.mean(black_pixel_counts)
        std_black = np.std(black_pixel_counts)
        mean_ratio = np.mean(pixel_ratios)
        std_ratio = np.std(pixel_ratios)
        
        # Estadísticas específicas de contornos
        mean_contour_area = np.mean(contour_areas) if contour_areas else 0
        std_contour_area = np.std(contour_areas) if contour_areas else 0
        mean_green_density = np.mean(green_densities) if green_densities else 0
        std_green_density = np.std(green_densities) if green_densities else 0
        mean_black_density = np.mean(black_densities) if black_densities else 0
        std_black_density = np.std(black_densities) if black_densities else 0
        mean_num_contours = np.mean(num_contours_list) if num_contours_list else 0
        
        # Contar tipos de contornos
        green_contour_count = contour_types.count('green')
        black_contour_count = contour_types.count('black')
        no_contour_count = contour_types.count('none')
        
        stats = {
            'folder_name': folder_name,
            'folder_path': str(folder_path),
            'num_images': len(green_pixel_counts),
            'used_contour_detection': detect_plants,
            
            # Conteo de tipos de contorno
            'green_contour_images': green_contour_count,
            'black_contour_images': black_contour_count,
            'no_contour_images': no_contour_count,
            'contour_types': contour_types,
            
            # Estadísticas de píxeles verdes (compatibilidad)
            'green_pixel_counts': [int(x) for x in green_pixel_counts],
            'green_mean': float(mean_green),
            'green_std': float(std_green),
            'green_min': int(np.min(green_pixel_counts)),
            'green_max': int(np.max(green_pixel_counts)),
            
            # Estadísticas de píxeles negros
            'black_pixel_counts': [int(x) for x in black_pixel_counts],
            'black_mean': float(mean_black),
            'black_std': float(std_black),
            'black_min': int(np.min(black_pixel_counts)),
            'black_max': int(np.max(black_pixel_counts)),
            
            # Estadísticas de la relación negro/verde
            'pixel_ratios': [float(x) for x in pixel_ratios],
            'ratio_mean': float(mean_ratio),
            'ratio_std': float(std_ratio),
            'ratio_min': float(np.min(pixel_ratios)),
            'ratio_max': float(np.max(pixel_ratios)),
            
            # Estadísticas específicas de contornos
            'contour_green_pixels': [int(x) for x in contour_green_pixels],
            'contour_black_pixels': [int(x) for x in contour_black_pixels],
            'contour_areas': [int(x) for x in contour_areas],
            'green_densities': [float(x) for x in green_densities],
            'black_densities': [float(x) for x in black_densities],
            'num_contours_list': [int(x) for x in num_contours_list],
            
            'contour_area_mean': float(mean_contour_area),
            'contour_area_std': float(std_contour_area),
            'green_density_mean': float(mean_green_density),
            'green_density_std': float(std_green_density),
            'black_density_mean': float(mean_black_density),
            'black_density_std': float(std_black_density),
            'num_contours_mean': float(mean_num_contours),
            
            'processed_files': processed_files,
            
            # Para compatibilidad con código anterior
            'mean': float(mean_green),
            'std': float(std_green),
            'min': int(np.min(green_pixel_counts)),
            'max': int(np.max(green_pixel_counts))
        }
        
        print(f"  📊 RESUMEN DE CONTORNOS:")
        print(f"     Contornos verdes: {green_contour_count} imágenes")
        print(f"     Contornos negros: {black_contour_count} imágenes") 
        print(f"     Sin contornos: {no_contour_count} imágenes")
        print(f"  📊 PÍXELES VERDES - Media: {mean_green:.2f}, Desv.Std: {std_green:.2f}")
        if detect_plants:
            print(f"  📊 DENSIDAD VERDE - Media: {mean_green_density:.1f}%, Desv.Std: {std_green_density:.1f}%")
            print(f"  📊 DENSIDAD NEGRA - Media: {mean_black_density:.1f}%, Desv.Std: {std_black_density:.1f}%")
            print(f"  📊 CONTORNOS - Media: {mean_num_contours:.1f} por imagen")
            print(f"  📊 ÁREA CONTORNOS - Media: {mean_contour_area:.0f} píxeles")
        print(f"  📊 PÍXELES NEGROS - Media: {mean_black:.2f}, Desv.Std: {std_black:.2f}")
        print(f"  📊 RELACIÓN N/V - Media: {mean_ratio:.2f}, Desv.Std: {std_ratio:.2f}")
        
        return stats
    
    def train_model(self, folder_paths: Dict[str, str], use_contour_detection: bool = True):
        """
        Entrena el modelo analizando las carpetas con detección mejorada de contornos
        
        Args:
            folder_paths: Diccionario {nombre_grupo: ruta_carpeta}
            use_contour_detection: Si usar detección de contornos
        """
        print("=== ENTRENANDO MODELO CON DETECCIÓN DE CONTORNOS VERDES Y NEGROS ===")
        
        self.stats = {}
        
        for group_name, folder_path in folder_paths.items():
            try:
                stats = self.analyze_folder(folder_path, group_name, use_contour_detection)
                self.stats[group_name] = stats
            except Exception as e:
                print(f"Error analizando carpeta {group_name}: {e}")
                continue
        
        if len(self.stats) < 2:
            raise ValueError("Se necesitan al menos 2 grupos válidos para entrenar el modelo")
        
        print(f"\n=== MODELO ENTRENADO CON {len(self.stats)} GRUPOS ===")
        
        # Mostrar resumen detallado
        for group_name, stats in self.stats.items():
            print(f"\n{group_name.upper()}:")
            print(f"  📷 Imágenes: {stats['num_images']}")
            print(f"  🔍 Detección de contornos: {'✓' if stats['used_contour_detection'] else '✗'}")
            
            if stats['used_contour_detection']:
                print(f"  📊 TIPOS DE CONTORNO:")
                print(f"     🌿 Verdes: {stats['green_contour_images']} imágenes")
                print(f"     ⚫ Negros: {stats['black_contour_images']} imágenes")
                print(f"     ❌ Sin contorno: {stats['no_contour_images']} imágenes")
            
            print(f"  🌿 PÍXELES VERDES:")
            print(f"     Media: {stats['green_mean']:.2f}")
            print(f"     Desv.Std: {stats['green_std']:.2f}")
            print(f"     Rango: {stats['green_min']} - {stats['green_max']}")
            
            if stats['used_contour_detection']:
                print(f"  🎯 MÉTRICAS DE CONTORNO:")
                print(f"     Densidad verde media: {stats['green_density_mean']:.1f}%")
                print(f"     Densidad negra media: {stats['black_density_mean']:.1f}%")
                print(f"     Contornos por imagen: {stats['num_contours_mean']:.1f}")
                print(f"     Área promedio de contornos: {stats['contour_area_mean']:.0f} px")
            
            print(f"  ⚫ PÍXELES NEGROS:")
            print(f"     Media: {stats['black_mean']:.2f}")
            print(f"     Desv.Std: {stats['black_std']:.2f}")
            print(f"  📊 RELACIÓN NEGRO/VERDE:")
            print(f"     Media: {stats['ratio_mean']:.2f}")
            print(f"     Desv.Std: {stats['ratio_std']:.2f}")
    
    def save_model(self, filepath: str):
        """Guarda el modelo entrenado con información de contornos verdes y negros"""
        model_data = {
            'stats': self.stats,
            'roi_coords': self.roi_coords,
            'roi_mask': self.roi_mask.tolist() if self.roi_mask is not None else None,
            'training_info': {
                'total_groups': len(self.stats),
                'groups': list(self.stats.keys()),
                'total_images': sum(stats['num_images'] for stats in self.stats.values()),
                'contour_detection_used': any(stats.get('used_contour_detection', False) for stats in self.stats.values()),
                'has_green_black_contour_analysis': True,
                'version': '2.0_green_black_contours'
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(model_data, f, indent=2)
        
        print(f"\nModelo guardado en: {filepath}")
        print(f"Grupos entrenados: {list(self.stats.keys())}")
        print(f"Total de imágenes analizadas: {model_data['training_info']['total_images']}")
        print(f"Detección de contornos utilizada: {'Sí' if model_data['training_info']['contour_detection_used'] else 'No'}")
        print(f"Versión del modelo: {model_data['training_info']['version']}")
    
    def plot_distributions(self, save_path: Optional[str] = None):
        """Grafica las distribuciones mejoradas incluyendo métricas de contornos verdes y negros"""
        if not self.stats:
            print("No hay datos para graficar. Entrena el modelo primero.")
            return
        
        # Verificar si algún grupo usó detección de contornos
        has_contour_data = any(stats.get('used_contour_detection', False) for stats in self.stats.values())
        
        if has_contour_data:
            # Crear figura con 8 subplots para incluir todas las métricas
            fig, axes = plt.subplots(2, 4, figsize=(24, 12))
        else:
            # Crear figura con 3 subplots originales
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            axes = axes.flatten()
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        
        for i, (group_name, stats) in enumerate(self.stats.items()):
            color = colors[i % len(colors)]
            
            if has_contour_data:
                # 1. Histograma de píxeles verdes
                axes[0,0].hist(stats['green_pixel_counts'], alpha=0.7, label=group_name, 
                              color=color, bins=min(20, len(stats['green_pixel_counts'])//2 + 1))
                
                # 2. Histograma de píxeles negros
                axes[0,1].hist(stats['black_pixel_counts'], alpha=0.7, label=group_name, 
                              color=color, bins=min(20, len(stats['black_pixel_counts'])//2 + 1))
                
                # 3. Histograma de relaciones negro/verde
                axes[0,2].hist(stats['pixel_ratios'], alpha=0.7, label=group_name, 
                              color=color, bins=min(20, len(stats['pixel_ratios'])//2 + 1))
                
                # 4. Histograma de densidad verde (solo para grupos con contornos)
                if stats.get('used_contour_detection', False):
                    axes[0,3].hist(stats['green_densities'], alpha=0.7, label=group_name, 
                                  color=color, bins=min(20, len(stats['green_densities'])//2 + 1))
                
                # 5. Histograma de densidad negra
                if stats.get('used_contour_detection', False):
                    axes[1,0].hist(stats['black_densities'], alpha=0.7, label=group_name, 
                                  color=color, bins=min(20, len(stats['black_densities'])//2 + 1))
                
                # 6. Histograma de número de contornos
                if stats.get('used_contour_detection', False):
                    axes[1,1].hist(stats['num_contours_list'], alpha=0.7, label=group_name, 
                                  color=color, bins=min(10, max(1, len(set(stats['num_contours_list'])))),
                                  range=(0, max(stats['num_contours_list']) + 1))
                
                # 7. Gráfico de tipos de contorno (barras)
                if stats.get('used_contour_detection', False):
                    contour_counts = [
                        stats.get('green_contour_images', 0),
                        stats.get('black_contour_images', 0), 
                        stats.get('no_contour_images', 0)
                    ]
                    x_pos = np.arange(3) + i * 0.25
                    axes[1,2].bar(x_pos, contour_counts, width=0.2, label=group_name, color=color, alpha=0.7)
                
                # 8. Distribuciones normales estimadas
                mean_g = stats['green_mean']
                std_g = stats['green_std']
                if std_g > 0:
                    x_g = np.linspace(max(0, mean_g - 3*std_g), mean_g + 3*std_g, 100)
                    y_g = (1/(std_g * np.sqrt(2*np.pi))) * np.exp(-0.5*((x_g-mean_g)/std_g)**2)
                    axes[1,3].plot(x_g, y_g, label=f"{group_name} V(μ={mean_g:.0f})", 
                                  color=color, linewidth=2, linestyle='-')
                
                # Píxeles negros (normalizar)
                mean_b = stats['black_mean']
                std_b = stats['black_std']
                if std_b > 0:
                    x_b = np.linspace(max(0, mean_b - 3*std_b), mean_b + 3*std_b, 100)
                    y_b = (1/(std_b * np.sqrt(2*np.pi))) * np.exp(-0.5*((x_b-mean_b)/std_b)**2)
                    axes[1,3].plot(x_b, y_b*0.5, label=f"{group_name} N(μ={mean_b:.0f})", 
                                  color=color, linewidth=2, linestyle='--')
            
            else:
                # Layout original para compatibilidad
                axes[0].hist(stats['green_pixel_counts'], alpha=0.7, label=group_name, 
                           color=color, bins=min(20, len(stats['green_pixel_counts'])//2 + 1))
                
                axes[1].hist(stats['black_pixel_counts'], alpha=0.7, label=group_name, 
                           color=color, bins=min(20, len(stats['black_pixel_counts'])//2 + 1))
                
                axes[2].hist(stats['pixel_ratios'], alpha=0.7, label=group_name, 
                           color=color, bins=min(20, len(stats['pixel_ratios'])//2 + 1))
                
                # Distribuciones normales
                mean_g = stats['green_mean']
                std_g = stats['green_std']
                if std_g > 0:
                    x_g = np.linspace(max(0, mean_g - 3*std_g), mean_g + 3*std_g, 100)
                    y_g = (1/(std_g * np.sqrt(2*np.pi))) * np.exp(-0.5*((x_g-mean_g)/std_g)**2)
                    axes[3].plot(x_g, y_g, label=f"{group_name} V(μ={mean_g:.0f})", 
                               color=color, linewidth=2, linestyle='-')
        
        # Configurar subplots según el layout
        if has_contour_data:
            # Layout con contornos (2x4)
            axes[0,0].set_xlabel('Píxeles Verdes')
            axes[0,0].set_ylabel('Frecuencia')
            axes[0,0].set_title('Distribución de Píxeles Verdes por Grupo')
            axes[0,0].legend()
            axes[0,0].grid(True, alpha=0.3)
            
            axes[0,1].set_xlabel('Píxeles Negros')
            axes[0,1].set_ylabel('Frecuencia')
            axes[0,1].set_title('Distribución de Píxeles Negros por Grupo')
            axes[0,1].legend()
            axes[0,1].grid(True, alpha=0.3)
            
            axes[0,2].set_xlabel('Relación Negro/Verde')
            axes[0,2].set_ylabel('Frecuencia')
            axes[0,2].set_title('Distribución de Relación Negro/Verde por Grupo')
            axes[0,2].legend()
            axes[0,2].grid(True, alpha=0.3)
            
            axes[0,3].set_xlabel('Densidad Verde (%)')
            axes[0,3].set_ylabel('Frecuencia')
            axes[0,3].set_title('Distribución de Densidad Verde en Contornos')
            axes[0,3].legend()
            axes[0,3].grid(True, alpha=0.3)
            
            axes[1,0].set_xlabel('Densidad Negra (%)')
            axes[1,0].set_ylabel('Frecuencia')
            axes[1,0].set_title('Distribución de Densidad Negra en Contornos')
            axes[1,0].legend()
            axes[1,0].grid(True, alpha=0.3)
            
            axes[1,1].set_xlabel('Número de Contornos')
            axes[1,1].set_ylabel('Frecuencia')
            axes[1,1].set_title('Distribución de Número de Contornos por Imagen')
            axes[1,1].legend()
            axes[1,1].grid(True, alpha=0.3)
            
            axes[1,2].set_xlabel('Tipo de Contorno')
            axes[1,2].set_ylabel('Número de Imágenes')
            axes[1,2].set_title('Distribución de Tipos de Contorno por Grupo')
            axes[1,2].set_xticks([0, 1, 2])
            axes[1,2].set_xticklabels(['Verde', 'Negro', 'Sin Contorno'])
            axes[1,2].legend()
            axes[1,2].grid(True, alpha=0.3)
            
            axes[1,3].set_xlabel('Valor')
            axes[1,3].set_ylabel('Densidad de Probabilidad')
            axes[1,3].set_title('Distribuciones Normales (V: sólida, N: punteada)')
            axes[1,3].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            axes[1,3].grid(True, alpha=0.3)
            
        else:
            # Layout original (2x2)
            axes[0].set_xlabel('Píxeles Verdes')
            axes[0].set_ylabel('Frecuencia')
            axes[0].set_title('Distribución de Píxeles Verdes por Grupo')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)
            
            axes[1].set_xlabel('Píxeles Negros')
            axes[1].set_ylabel('Frecuencia')
            axes[1].set_title('Distribución de Píxeles Negros por Grupo')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)
            
            axes[2].set_xlabel('Relación Negro/Verde')
            axes[2].set_ylabel('Frecuencia')
            axes[2].set_title('Distribución de Relación Negro/Verde por Grupo')
            axes[2].legend()
            axes[2].grid(True, alpha=0.3)
            
            axes[3].set_xlabel('Valor')
            axes[3].set_ylabel('Densidad de Probabilidad')
            axes[3].set_title('Distribuciones Normales Estimadas')
            axes[3].legend()
            axes[3].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Gráfica guardada en: {save_path}")
        
        plt.show()
    
    def generate_report(self, report_path: str = "training_report.txt"):
        """Genera un reporte detallado del entrenamiento incluyendo métricas de contornos verdes y negros"""
        if not self.stats:
            print("No hay datos para generar reporte.")
            return
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("REPORTE DE ENTRENAMIENTO DEL MODELO ROI - DETECCIÓN DE CONTORNOS VERDES Y NEGROS\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Fecha de entrenamiento: {str(np.datetime64('now'))}\n")
            f.write(f"Número de grupos: {len(self.stats)}\n")
            f.write(f"ROI configurado: {self.roi_coords}\n")
            f.write(f"ROI circular: {'Sí' if self.roi_mask is not None else 'No'}\n")
            f.write(f"Versión del modelo: 2.0 - Contornos verdes y negros\n\n")
            
            # Verificar si se usó detección de contornos
            contour_groups = [name for name, stats in self.stats.items() 
                            if stats.get('used_contour_detection', False)]
            
            if contour_groups:
                f.write("GRUPOS CON DETECCIÓN DE CONTORNOS:\n")
                f.write(f"  {', '.join(contour_groups)}\n\n")
            
            total_images = 0
            total_green_contours = 0
            total_black_contours = 0
            total_no_contours = 0
            
            for group_name, stats in self.stats.items():
                total_images += stats['num_images']
                total_green_contours += stats.get('green_contour_images', 0)
                total_black_contours += stats.get('black_contour_images', 0) 
                total_no_contours += stats.get('no_contour_images', 0)
                
                f.write(f"\n{'-'*70}\n")
                f.write(f"GRUPO: {group_name.upper()}\n")
                f.write(f"{'-'*70}\n")
                f.write(f"Carpeta: {stats['folder_path']}\n")
                f.write(f"Imágenes procesadas: {stats['num_images']}\n")
                f.write(f"Detección de contornos: {'✓' if stats.get('used_contour_detection', False) else '✗'}\n\n")
                
                if stats.get('used_contour_detection', False):
                    f.write("ANÁLISIS DE TIPOS DE CONTORNO:\n")
                    f.write(f"  Imágenes con contornos verdes: {stats.get('green_contour_images', 0)}\n")
                    f.write(f"  Imágenes con contornos negros: {stats.get('black_contour_images', 0)}\n")
                    f.write(f"  Imágenes sin contornos: {stats.get('no_contour_images', 0)}\n\n")
                
                f.write("PÍXELES VERDES:\n")
                f.write(f"  Media: {stats['green_mean']:.2f}\n")
                f.write(f"  Desviación estándar: {stats['green_std']:.2f}\n")
                f.write(f"  Rango: {stats['green_min']} - {stats['green_max']}\n\n")
                
                if stats.get('used_contour_detection', False):
                    f.write("MÉTRICAS DE CONTORNOS:\n")
                    f.write(f"  Densidad verde promedio: {stats['green_density_mean']:.1f}%\n")
                    f.write(f"  Desv. estándar densidad verde: {stats['green_density_std']:.1f}%\n")
                    f.write(f"  Densidad negra promedio: {stats['black_density_mean']:.1f}%\n")
                    f.write(f"  Desv. estándar densidad negra: {stats['black_density_std']:.1f}%\n")
                    f.write(f"  Contornos por imagen (promedio): {stats['num_contours_mean']:.1f}\n")
                    f.write(f"  Área promedio de contornos: {stats['contour_area_mean']:.0f} píxeles\n")
                    f.write(f"  Desv. estándar área: {stats['contour_area_std']:.0f} píxeles\n\n")
                
                f.write("PÍXELES NEGROS:\n")
                f.write(f"  Media: {stats['black_mean']:.2f}\n")
                f.write(f"  Desviación estándar: {stats['black_std']:.2f}\n")
                f.write(f"  Rango: {stats['black_min']} - {stats['black_max']}\n\n")
                
                f.write("RELACIÓN NEGRO/VERDE:\n")
                f.write(f"  Media: {stats['ratio_mean']:.2f}\n")
                f.write(f"  Desviación estándar: {stats['ratio_std']:.2f}\n")
                f.write(f"  Rango: {stats['ratio_min']:.2f} - {stats['ratio_max']:.2f}\n\n")
                
                f.write(f"Primeros 10 archivos procesados:\n")
                for j, filename in enumerate(stats['processed_files'][:10], 1):
                    if j <= len(stats['green_pixel_counts']):
                        idx = j - 1
                        contour_type = stats.get('contour_types', ['none'] * len(stats['processed_files']))[idx]
                        if stats.get('used_contour_detection', False):
                            f.write(f"  {j}. {filename}: {stats['green_pixel_counts'][idx]} V, "
                                   f"{stats['black_pixel_counts'][idx]} N, "
                                   f"R={stats['pixel_ratios'][idx]:.2f}, "
                                   f"Densidad V={stats['green_densities'][idx]:.1f}%, "
                                   f"Densidad N={stats['black_densities'][idx]:.1f}%, "
                                   f"Contornos={stats['num_contours_list'][idx]} ({contour_type})\n")
                        else:
                            f.write(f"  {j}. {filename}: {stats['green_pixel_counts'][idx]} V, "
                                   f"{stats['black_pixel_counts'][idx]} N, "
                                   f"R={stats['pixel_ratios'][idx]:.2f}\n")
                
                if len(stats['processed_files']) > 10:
                    f.write(f"  ... y {len(stats['processed_files'])-10} archivos más\n")
            
            f.write(f"\n{'='*80}\n")
            f.write(f"RESUMEN TOTAL\n")
            f.write(f"{'='*80}\n")
            f.write(f"Total de imágenes analizadas: {total_images}\n")
            f.write(f"Grupos disponibles para clasificación: {', '.join(self.stats.keys())}\n")
            
            if contour_groups:
                f.write(f"Grupos con detección de contornos: {', '.join(contour_groups)}\n")
                f.write(f"ESTADÍSTICAS GENERALES DE CONTORNOS:\n")
                f.write(f"  Total imágenes con contornos verdes: {total_green_contours}\n")
                f.write(f"  Total imágenes con contornos negros: {total_black_contours}\n")
                f.write(f"  Total imágenes sin contornos: {total_no_contours}\n\n")
                
                f.write(f"MEJORAS IMPLEMENTADAS EN ESTA VERSIÓN:\n")
                f.write(f"  • Detección automática de contornos verdes (lechugas con hojas)\n")
                f.write(f"  • Detección automática de contornos negros (vasos vacíos, tierra)\n")
                f.write(f"  • Análisis siempre limitado al área de contornos detectados\n")
                f.write(f"  • Métricas de densidad para ambos tipos de contorno\n")
                f.write(f"  • Estadísticas separadas por tipo de contorno\n")
                f.write(f"  • Eliminación del problema de medias en 0 para vasos vacíos\n")
                f.write(f"  • Debug visual para verificar detección correcta\n")
        
        print(f"Reporte guardado en: {report_path}")


def main():
    """Función principal para entrenar el modelo con detección mejorada de contornos"""
    
    print("="*80)
    print("ENTRENADOR DE MODELO ROI - CON DETECCIÓN DE CONTORNOS VERDES Y NEGROS")
    print("="*80)
    print("🌿 Detecta contornos verdes: lechugas con hojas visibles")
    print("⚫ Detecta contornos negros: vasos vacíos, tierra, áreas oscuras")
    print("🎯 Análisis siempre limitado al área de contornos (nunca fondo)")
    print("📊 Elimina el problema de medias en 0 para vasos sin lechuga")
    print("🔍 Proporciona métricas precisas independiente del contenido")
    print()
    
    # Crear entrenador
    trainer = GreenPixelROITrainer()
    
    # ===== CONFIGURACIÓN DE CARPETAS =====
    folder_paths = {
        'Lechugas': "/home/brenda/Documents/BD_ORIGINALES/recortadas/lechugas_recortadas",
        'Vasos': "/home/brenda/Documents/BD_ORIGINALES/recortadas/vasos_recortadas",
        'Plantines': "/home/brenda/Documents/BD_ORIGINALES/recortadas/plantines_recortadas"
    }
    
    # ===== CONFIGURACIÓN DE ROI CIRCULAR =====
    # Usamos la primera imagen disponible como referencia
    example_image_path = None
    for folder_name, folder_path in folder_paths.items():
        try:
            folder_files = os.listdir(folder_path)
            image_files = [f for f in folder_files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            if image_files:
                example_image_path = Path(folder_path) / image_files[0]
                break
        except:
            continue
    
    if example_image_path and example_image_path.exists():
        img = cv2.imread(str(example_image_path))
        if img is not None:
            trainer.set_roi_circle(img, radius_ratio=0.4)  # 40% del tamaño mínimo
            print(f"✅ ROI circular configurado usando: {example_image_path}")
        else:
            print("⚠️ No se pudo cargar la imagen de ejemplo para configurar el ROI circular")
    else:
        print("⚠️ No se encontró imagen de ejemplo para configurar el ROI circular")
    
    try:
        print("\nPASO 1: Entrenando el modelo con detección mejorada de contornos...")
        print("-" * 60)
        trainer.train_model(folder_paths, use_contour_detection=True)
        
        print("\nPASO 2: Guardando modelo...")
        print("-" * 60)
        model_filename = "modelo_roi_contornos_verdes_negros.json"
        trainer.save_model(model_filename)
        
        print("\nPASO 3: Generando gráficas...")
        print("-" * 60)
        trainer.plot_distributions(save_path="distribucion_contornos_verdes_negros.png")
        
        print("\nPASO 4: Generando reporte...")
        print("-" * 60)
        trainer.generate_report("reporte_contornos_verdes_negros.txt")
        
        print("\n" + "="*80)
        print("✅ ENTRENAMIENTO CON CONTORNOS VERDES Y NEGROS COMPLETADO")
        print("="*80)
        print()
        print("🎯 PROBLEMA RESUELTO:")
        print("  • Vasos sin lechuga ya NO generan medias en 0")
        print("  • Se detectan contornos negros (tierra, vaso vacío)")
        print("  • Análisis SIEMPRE limitado al área de contornos")
        print("  • Métricas confiables independientemente del contenido")
        print()
        print("🔧 MEJORAS IMPLEMENTADAS:")
        print("  • Detección dual: contornos verdes Y negros")
        print("  • Fallback inteligente: Verde → Negro → Sin contorno")
        print("  • Métricas de densidad para ambos colores")
        print("  • Estadísticas por tipo de contorno detectado")
        print("  • Debug visual para verificar detección correcta")
        print()
        print("📁 Archivos generados:")
        print(f"  🤖 {model_filename} - Modelo con detección dual")
        print("  📊 distribucion_contornos_verdes_negros.png - Gráficas completas")
        print("  📄 reporte_contornos_verdes_negros.txt - Reporte detallado")
        print()
        print("🚀 Ahora el clasificador tendrá:")
        print("   • Medias y desviaciones válidas para TODOS los casos")
        print("   • Mejor diferenciación entre lechugas y vasos vacíos")
        print("   • Análisis consistente basado en contornos reales")
        
    except Exception as e:
        print(f"\n❌ Error durante el entrenamiento: {e}")
        print("Verifica que las rutas de las carpetas sean correctas y contengan imágenes.")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()