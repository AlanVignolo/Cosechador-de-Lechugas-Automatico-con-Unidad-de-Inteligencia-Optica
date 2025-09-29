"""
Script de Detección de Bordes usando HSV + Threshold
Basado en el método de tape_detector_vertical/horizontal
"""

import cv2
import numpy as np
import os
from pathlib import Path


class EdgeDetectorHSV:
    def __init__(self, threshold_value=50, min_area=500):
        """
        Inicializa el detector de bordes
        
        Args:
            threshold_value: Umbral para detección (valores < threshold son considerados bordes)
            min_area: Área mínima para considerar un contorno válido
        """
        self.threshold_value = threshold_value
        self.min_area = min_area
        
    def detect_edges(self, image):
        """
        Detecta bordes usando múltiples métodos combinados con reducción de ruido
        Detecta tanto zonas verdes (lechuga) como zonas negras (cinta/vaso oscuro)
        Robusto contra sombras y variaciones de iluminación
        Alta definición en los bordes
        
        Returns:
            binary_img: Imagen binaria con bordes detectados
            contours: Lista de contornos encontrados
            mask_combined: Máscara combinada para análisis de conectividad
        """
        # Método 1: HSV para detectar vegetación verde (lechuga)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Rango ESTRICTO para detectar solo verde intenso (no sombras verdosas)
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([80, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        # Método 2: MEJORADO - Detectar zonas negras REALES, NO sombras
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        b, g, r = cv2.split(image)
        v_channel = hsv[:, :, 2]
        s_channel = hsv[:, :, 1]
        
        # 2A: Negro REAL debe ser MUY oscuro (no sombras grises)
        _, mask_very_dark_gray = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
        _, mask_very_dark_v = cv2.threshold(v_channel, 55, 255, cv2.THRESH_BINARY_INV)
        
        # 2B: Negro por análisis BGR - TODOS los canales deben ser MUY bajos
        mask_dark_b = cv2.inRange(b, 0, 65)
        mask_dark_g = cv2.inRange(g, 0, 65)
        mask_dark_r = cv2.inRange(r, 0, 65)
        
        mask_dark_bgr = cv2.bitwise_and(mask_dark_b, mask_dark_g)
        mask_dark_bgr = cv2.bitwise_and(mask_dark_bgr, mask_dark_r)
        
        # 2C: CRÍTICO - Las sombras tienen valores similares en R,G,B pero NO son negro
        mean_channels = (b.astype(np.float32) + g.astype(np.float32) + r.astype(np.float32)) / 3
        std_b = np.abs(b.astype(np.float32) - mean_channels)
        std_g = np.abs(g.astype(np.float32) - mean_channels)
        std_r = np.abs(r.astype(np.float32) - mean_channels)
        channel_variance = (std_b + std_g + std_r) / 3
        
        _, mask_low_variance = cv2.threshold(channel_variance.astype(np.uint8), 15, 255, cv2.THRESH_BINARY_INV)
        
        # 2D: Combinar: debe ser oscuro Y baja varianza Y saturación baja
        mask_dark_temp = cv2.bitwise_or(mask_very_dark_gray, mask_very_dark_v)
        mask_dark = cv2.bitwise_or(mask_dark_temp, mask_dark_bgr)
        
        # Filtro de saturación MUY ESTRICTO
        _, mask_very_low_sat = cv2.threshold(s_channel, 50, 255, cv2.THRESH_BINARY_INV)
        
        # Negro = (oscuro) AND (baja_saturación) AND (baja_variancia)
        mask_dark_filtered = cv2.bitwise_and(mask_dark, mask_very_low_sat)
        mask_dark_final = cv2.bitwise_and(mask_dark_filtered, mask_low_variance)
        
        # 2E: Eliminar sombras por rango de intensidad
        _, mask_not_shadow = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
        mask_not_shadow = cv2.bitwise_not(mask_not_shadow)
        mask_dark_final = cv2.bitwise_and(mask_dark_final, mask_not_shadow)
        
        # 2F: Detección Sobel SOLO en zonas MUY oscuras confirmadas
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_magnitude = np.sqrt(sobelx**2 + sobely**2)
        sobel_magnitude = np.uint8(sobel_magnitude / sobel_magnitude.max() * 255)
        
        _, edges_sobel = cv2.threshold(sobel_magnitude, 30, 255, cv2.THRESH_BINARY)
        edges_in_dark = cv2.bitwise_and(edges_sobel, mask_dark_final)
        
        kernel_edge_dilate = np.ones((3, 3), np.uint8)
        edges_dark_dilated = cv2.dilate(edges_in_dark, kernel_edge_dilate, iterations=1)
        
        mask_dark_with_edges = cv2.bitwise_or(mask_dark_final, edges_dark_dilated)
        
        # 2G: Detección específica de cinta negra DEBAJO del vaso
        h_img, w_img = gray.shape
        lower_half_mask = np.zeros_like(gray)
        lower_half_mask[h_img//2:, :] = 255
        
        _, mask_dark_permissive = cv2.threshold(gray, 75, 255, cv2.THRESH_BINARY_INV)
        mask_dark_lower = cv2.bitwise_and(mask_dark_permissive, lower_half_mask)
        
        _, mask_low_sat_permissive = cv2.threshold(s_channel, 70, 255, cv2.THRESH_BINARY_INV)
        mask_dark_lower = cv2.bitwise_and(mask_dark_lower, mask_low_sat_permissive)
        
        kernel_vertical = np.ones((15, 3), np.uint8)
        mask_dark_extended = cv2.dilate(mask_dark_final, kernel_vertical, iterations=2)
        
        mask_tape_candidate = cv2.bitwise_and(mask_dark_lower, mask_dark_extended)
        mask_dark_with_edges = cv2.bitwise_or(mask_dark_with_edges, mask_tape_candidate)
        
        # Método 3: Detección de verde por dominancia
        green_dominance = cv2.subtract(g, cv2.addWeighted(r, 0.5, b, 0.5, 0))
        _, mask_green_dominance = cv2.threshold(green_dominance, 20, 255, cv2.THRESH_BINARY)
        mask_green_final = cv2.bitwise_or(mask_green, mask_green_dominance)
        
        # Método 4: Eliminar fondo claro
        _, mask_bright = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        mask_not_bright = cv2.bitwise_not(mask_bright)
        
        # Combinar verde + negro (con bordes), excluyendo fondo
        mask_combined = cv2.bitwise_or(mask_green_final, mask_dark_with_edges)
        mask_combined = cv2.bitwise_and(mask_combined, mask_not_bright)
        
        # Morfología para cerrar gaps en objetos negros (vaso + cinta)
        kernel_small = np.ones((3, 3), np.uint8)
        kernel_large = np.ones((7, 7), np.uint8)
        
        # Cerrar gaps VERTICALMENTE primero
        kernel_vertical_close = np.ones((11, 5), np.uint8)
        mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_CLOSE, kernel_vertical_close, iterations=2)
        
        # Luego cerrar en todas direcciones
        mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_CLOSE, kernel_large, iterations=3)
        
        # Eliminar ruido pequeño
        mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_OPEN, kernel_small, iterations=1)
        
        # Detección de bordes finos con Canny
        blurred_fine = cv2.GaussianBlur(gray, (3, 3), 0.5)
        blurred_medium = cv2.GaussianBlur(gray, (5, 5), 1.0)
        
        edges_fine = cv2.Canny(blurred_fine, 20, 70)
        edges_major = cv2.Canny(blurred_medium, 40, 120)
        
        edges_combined = cv2.bitwise_or(edges_fine, edges_major)
        edges_masked = cv2.bitwise_and(edges_combined, mask_combined)
        
        # Dilatación de bordes para conectar
        kernel_edge = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges_masked, kernel_edge, iterations=1)
        
        # Combinar máscara + bordes
        binary_img = cv2.bitwise_or(mask_combined, edges_dilated)
        
        # Cierre final agresivo para unir vaso + cinta
        kernel_close = np.ones((9, 9), np.uint8)
        binary_img = cv2.morphologyEx(binary_img, cv2.MORPH_CLOSE, kernel_close, iterations=3)
        
        # Eliminar componentes pequeños
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
        
        binary_clean = np.zeros_like(binary_img)
        min_component_area = 2500
        
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_component_area:
                binary_clean[labels == i] = 255
        
        # Refinamiento final
        kernel_refine = np.ones((5, 5), np.uint8)
        binary_img = cv2.morphologyEx(binary_clean, cv2.MORPH_CLOSE, kernel_refine, iterations=2)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        
        # Suavizar contornos
        smoothed_contours = []
        for contour in contours:
            epsilon = 0.001 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            smoothed_contours.append(approx)
        
        return binary_img, smoothed_contours, mask_combined
    
    
    def analyze_contour(self, contour, img_width, img_height):
        """
        Analiza un contorno y extrae sus características
        
        Returns:
            dict con información del contorno
        """
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Calcular perímetro y circularidad
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
        else:
            circularity = 0
        
        # Calcular aspect ratio
        if h > 0:
            aspect_ratio = w / h
        else:
            aspect_ratio = 0
        
        # Calcular solidez (solidity)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidity = area / hull_area
        else:
            solidity = 0
        
        # Centralidad
        center_x = x + w // 2
        center_y = y + h // 2
        img_center_x = img_width // 2
        img_center_y = img_height // 2
        
        distance_to_center = np.sqrt((center_x - img_center_x)**2 + (center_y - img_center_y)**2)
        max_distance = np.sqrt(img_width**2 + img_height**2) / 2
        centrality = 1.0 - (distance_to_center / max_distance)
        
        # Compacidad (relación área/bbox)
        bbox_area = w * h
        if bbox_area > 0:
            compactness = area / bbox_area
        else:
            compactness = 0
        
        return {
            'contour': contour,
            'area': area,
            'bbox': (x, y, w, h),
            'center': (center_x, center_y),
            'circularity': circularity,
            'aspect_ratio': aspect_ratio,
            'solidity': solidity,
            'centrality': centrality,
            'compactness': compactness,
            'perimeter': perimeter
        }
    
    def calculate_rectangularity(self, image, contour):
        """Calcula qué tan rectangular es el contorno completo"""
        x, y, w, h = cv2.boundingRect(contour)
        
        bbox_area = w * h
        contour_area = cv2.contourArea(contour)
        
        if bbox_area == 0:
            return 0.0
        
        return contour_area / bbox_area
    
    def check_connectivity_to_center(self, binary_mask, contour, img_width, img_height):
        """
        Verifica si un contorno tiene conectividad verde desde su centroide hacia el centro de la imagen.
        Esto filtra hojas de lechugas vecinas que aparecen en los bordes sin estar conectadas al centro.
        
        Args:
            binary_mask: Máscara binaria con zonas verdes
            contour: Contorno a evaluar
            img_width, img_height: Dimensiones de la imagen
            
        Returns:
            connectivity_score: Valor entre 0 y 1 indicando conectividad al centro
        """
        img_center_x = img_width // 2
        img_center_y = img_height // 2
        
        # Obtener centro del contorno
        M = cv2.moments(contour)
        if M['m00'] == 0:
            return 0.0
            
        contour_center_x = int(M['m10'] / M['m00'])
        contour_center_y = int(M['m01'] / M['m00'])
        
        # Calcular distancia del contorno al centro de imagen
        distance_to_center = np.sqrt((contour_center_x - img_center_x)**2 + 
                                     (contour_center_y - img_center_y)**2)
        max_distance = np.sqrt(img_width**2 + img_height**2) / 2
        
        # Si el contorno ya está en el centro, es válido automáticamente
        if distance_to_center < max_distance * 0.3:  # Dentro del 30% central
            return 1.0
        
        # Para contornos alejados, verificar conectividad mediante muestreo de líneas
        num_samples = 8  # Número de líneas radiales a muestrear
        connected_lines = 0
        
        for i in range(num_samples):
            # Calcular punto intermedio en línea desde contorno hacia centro
            ratio = i / num_samples
            sample_x = int(contour_center_x + (img_center_x - contour_center_x) * ratio)
            sample_y = int(contour_center_y + (img_center_y - contour_center_y) * ratio)
            
            # Verificar si hay píxeles verdes en esta posición
            if 0 <= sample_x < img_width and 0 <= sample_y < img_height:
                if binary_mask[sample_y, sample_x] > 0:
                    connected_lines += 1
        
        # Score basado en cuántas líneas radiales tienen verde
        connectivity_score = connected_lines / num_samples
        
        # Verificar también con line iterator (más preciso)
        line_connectivity = self._check_line_connectivity(binary_mask, 
                                                          (contour_center_x, contour_center_y),
                                                          (img_center_x, img_center_y))
        
        # Combinar ambos métodos
        final_score = (connectivity_score * 0.5 + line_connectivity * 0.5)
        
        return final_score
    
    def _check_line_connectivity(self, binary_mask, start_point, end_point):
        """
        Verifica conectividad a lo largo de una línea usando Bresenham
        
        Returns:
            Porcentaje de píxeles verdes en la línea (0.0 a 1.0)
        """
        x0, y0 = start_point
        x1, y1 = end_point
        
        # Generar puntos en la línea (Bresenham)
        points = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        h, w = binary_mask.shape
        
        while True:
            if 0 <= x < w and 0 <= y < h:
                points.append((x, y))
            
            if x == x1 and y == y1:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
        
        if not points:
            return 0.0
        
        # Contar píxeles verdes en la línea
        green_pixels = sum(1 for (x, y) in points if binary_mask[y, x] > 0)
        
        # Retornar porcentaje de píxeles verdes
        return green_pixels / len(points)
    
    
    def calculate_rectangularity(self, image, contour):
        """Calcula qué tan rectangular es el contorno completo"""
        x, y, w, h = cv2.boundingRect(contour)
        
        bbox_area = w * h
        contour_area = cv2.contourArea(contour)
        
        if bbox_area == 0:
            return 0.0
        
        return contour_area / bbox_area
    
    def visualize_detection(self, image, contours, mask_green=None, show_all=True):
        """
        Visualiza la detección de bordes
        
        Args:
            image: Imagen original
            contours: Lista de contornos detectados
            mask_green: Máscara verde para análisis de conectividad
            show_all: Si True, muestra todos los contornos. Si False, solo el mejor
        
        Returns:
            result_img: Imagen con visualización
        """
        result_img = image.copy()
        h_img, w_img = image.shape[:2]
        img_center_x = w_img // 2
        img_center_y = h_img // 2
        
        # Filtrar contornos por área mínima
        valid_contours = [c for c in contours if cv2.contourArea(c) > self.min_area]
        
        if not valid_contours:
            cv2.putText(result_img, "NO SE DETECTARON CONTORNOS VALIDOS", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return result_img
        
        # Evaluar y ordenar contornos
        contour_data = []
        for contour in valid_contours:
            data = self.analyze_contour(contour, w_img, h_img)
            
            # NUEVO: Verificar conectividad al centro
            if mask_green is not None:
                connectivity = self.check_connectivity_to_center(mask_green, contour, w_img, h_img)
                data['connectivity'] = connectivity
            else:
                data['connectivity'] = 1.0  # Si no hay máscara, asumir conectado
            
            # Score compuesto MEJORADO con conectividad al centro
            score = (
                (data['area'] / (w_img * h_img)) * 0.35 +  # Área relativa (35%)
                data['compactness'] * 0.15 +               # Compacidad (15%)
                data['centrality'] * 0.15 +                # Centralidad (15%)
                data['solidity'] * 0.10 +                  # Solidez (10%)
                data['connectivity'] * 0.25                # CONECTIVIDAD AL CENTRO (25% - CRÍTICO)
            )
            
            data['score'] = score
            
            # FILTRO: Solo contornos con conectividad > 0.3 (30% de línea verde hacia centro)
            if data['connectivity'] >= 0.3:
                contour_data.append(data)
        
        if not contour_data:
            cv2.putText(result_img, "NO SE DETECTO CONTORNO VALIDO", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return result_img
        
        # Ordenar por score
        contour_data.sort(key=lambda x: x['score'], reverse=True)
        
        if show_all:
            # Dibujar todos los contornos válidos
            colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
            for i, data in enumerate(contour_data[:5]):  # Máximo 5 contornos
                color = colors[i % len(colors)]
                
                # Dibujar contorno completo
                cv2.drawContours(result_img, [data['contour']], -1, color, 3)
                
                # Bounding box
                x, y, w, h = data['bbox']
                cv2.rectangle(result_img, (x, y), (x + w, y + h), color, 2)
                
                # Centro
                cv2.circle(result_img, data['center'], 5, color, -1)
                
                # Texto con info
                text = f"#{i+1} Score:{data['score']:.2f} Conn:{data['connectivity']:.2f}"
                cv2.putText(result_img, text, (x, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        else:
            # Dibujar solo el mejor
            best = contour_data[0]
            
            # Contorno principal (verde grueso)
            cv2.drawContours(result_img, [best['contour']], -1, (0, 255, 0), 4)
            
            # Bounding box
            x, y, w, h = best['bbox']
            cv2.rectangle(result_img, (x, y), (x + w, y + h), (255, 0, 0), 3)
            
            # Centro
            cv2.circle(result_img, best['center'], 8, (0, 0, 255), -1)
            cv2.circle(result_img, best['center'], 12, (255, 255, 0), 2)
            
            # Líneas de cruz en el centro del contorno
            cx, cy = best['center']
            line_len = 20
            cv2.line(result_img, (cx - line_len, cy), (cx + line_len, cy), (0, 255, 255), 2)
            cv2.line(result_img, (cx, cy - line_len), (cx, cy + line_len), (0, 255, 255), 2)
            
            # NUEVO: Dibujar línea de conectividad al centro de imagen
            cv2.line(result_img, (cx, cy), (img_center_x, img_center_y), (255, 0, 255), 2)
            cv2.circle(result_img, (img_center_x, img_center_y), 10, (255, 0, 255), 2)
        
        # Líneas de referencia de la imagen
        cv2.line(result_img, (img_center_x, 0), (img_center_x, h_img), (128, 128, 128), 1, cv2.LINE_AA)
        cv2.line(result_img, (0, img_center_y), (w_img, img_center_y), (128, 128, 128), 1, cv2.LINE_AA)
        
        return result_img


def process_images(input_folder, output_folder, threshold=50, min_area=500, show_all=True):
    """
    Procesa todas las imágenes de una carpeta
    
    Args:
        input_folder: Carpeta con imágenes de entrada
        output_folder: Carpeta para guardar resultados
        threshold: Valor de umbral para detección
        min_area: Área mínima de contornos
        show_all: Si True, muestra todos los contornos; si False, solo el mejor
    """
    # Crear carpeta de salida si no existe
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Crear detector
    detector = EdgeDetectorHSV(threshold_value=threshold, min_area=min_area)
    
    # Extensiones de imagen soportadas
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    
    # Procesar cada imagen
    image_files = []
    for ext in image_extensions:
        image_files.extend(Path(input_folder).glob(f'*{ext}'))
        image_files.extend(Path(input_folder).glob(f'*{ext.upper()}'))
    
    if not image_files:
        print(f"No se encontraron imágenes en: {input_folder}")
        return
    
    print(f"\n{'='*60}")
    print(f"Procesando {len(image_files)} imágenes")
    print(f"Threshold: {threshold}, Área mínima: {min_area}")
    print(f"{'='*60}\n")
    
    for img_path in image_files:
        print(f"Procesando: {img_path.name}")
        
        # Leer imagen
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"  ❌ Error al leer imagen")
            continue
        
        # Detectar bordes
        binary_img, contours, mask_green = detector.detect_edges(image)
        
        # Visualizar (pasando máscara verde para análisis de conectividad)
        result_img = detector.visualize_detection(image, contours, mask_green, show_all=show_all)
        
        # Guardar resultados
        base_name = img_path.stem
        
        # Imagen con detección
        output_path = Path(output_folder) / f"{base_name}_detection.jpg"
        cv2.imwrite(str(output_path), result_img)
        
        # Imagen binaria (threshold)
        binary_path = Path(output_folder) / f"{base_name}_binary.jpg"
        cv2.imwrite(str(binary_path), binary_img)
        
        # Crear comparación lado a lado
        h, w = image.shape[:2]
        comparison = np.zeros((h, w*3, 3), dtype=np.uint8)
        comparison[:, :w] = image
        comparison[:, w:2*w] = cv2.cvtColor(binary_img, cv2.COLOR_GRAY2BGR)
        comparison[:, 2*w:] = result_img
        
        # Etiquetas (sin mucho texto)
        cv2.putText(comparison, "ORIGINAL", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(comparison, "THRESHOLD", (w + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(comparison, "DETECCION", (2*w + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        comparison_path = Path(output_folder) / f"{base_name}_comparison.jpg"
        cv2.imwrite(str(comparison_path), comparison)
        
        print(f"  ✅ Guardado: {output_path.name}")
        print(f"  ✅ Binaria: {binary_path.name}")
        print(f"  ✅ Comparación: {comparison_path.name}")
    
    print(f"\n{'='*60}")
    print(f"✅ Proceso completado. Resultados en: {output_folder}")
    print(f"{'='*60}\n")


def main():
    """Función principal"""
    
    # ========== CONFIGURACIÓN ==========
    # Modifica estos parámetros según tus necesidades
    
    INPUT_FOLDER = "/home/brenda/Documents/validation"     # Carpeta con tus imágenes
    OUTPUT_FOLDER = "/home/brenda/Documents/validation/bordes"  # Carpeta para resultados
    THRESHOLD = 50                        # Ya no se usa (se usa detección multi-método)
    MIN_AREA = 5000                       # Área mínima de contornos (aumentada para filtrar más ruido)
    SHOW_ALL = False                      # True: todos los contornos, False: solo el mejor
    
    # ===================================
    
    # Verificar carpeta de entrada
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Error: La carpeta '{INPUT_FOLDER}' no existe")
        print(f"   Créala y coloca tus imágenes allí")
        return
    
    # Procesar imágenes
    process_images(
        input_folder=INPUT_FOLDER,
        output_folder=OUTPUT_FOLDER,
        threshold=THRESHOLD,
        min_area=MIN_AREA,
        show_all=SHOW_ALL
    )


if __name__ == "__main__":
    main()