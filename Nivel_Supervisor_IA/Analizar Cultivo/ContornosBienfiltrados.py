"""
Detector de Bordes OPTIMIZADO - Versión Simplificada
Enfoque: Menos filtros, más precisos
"""

import cv2
import numpy as np
from pathlib import Path


class EdgeDetectorOptimized:
    def __init__(self):
        self.steps = {}
        
    def save_step(self, name, image, description=""):
        self.steps[name] = {'image': image.copy(), 'description': description}
    
    def detect_edges(self, image):
        """Detección optimizada con menos filtros"""
        print("\n" + "="*70)
        print("DETECCIÓN OPTIMIZADA")
        print("="*70)
        
        # ============= PREPARACIÓN =============
        h_img, w_img = image.shape[:2]
        
        # Aumentar brillo suavemente
        brighter = cv2.convertScaleAbs(image, alpha=1.15, beta=30)
        #self.save_step("01_brighter", brighter, "Brillo aumentado")
        
        hsv = cv2.cvtColor(brighter, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(brighter, cv2.COLOR_BGR2GRAY)
        b, g, r = cv2.split(brighter)
        h, s, v = cv2.split(hsv)
        
        #self.save_step("02_gray", gray, "Escala de grises")
        
        # ============= NEGRO MEJORADO =============
        print("\n[1] Detección de NEGRO mejorada")
        
        # Método 1: Valores muy bajos (más permisivo)
        mask_black_v = (v < 70).astype(np.uint8) * 255  # Era 50, ahora 70
        mask_black_gray = (gray < 65).astype(np.uint8) * 255  # Era 45, ahora 65
        
        # Combinar con OR (más permisivo)
        mask_black = cv2.bitwise_or(mask_black_v, mask_black_gray)
        #self.save_step("03_black_basic", mask_black, "Negro básico (V<70 OR Gray<65)")
        
        # Filtro de saturación suave (evitar grises puros)
        mask_not_pure_gray = (s > 15).astype(np.uint8) * 255
        mask_black = cv2.bitwise_or(mask_black, 
                                     cv2.bitwise_and(mask_black, mask_not_pure_gray))
        
        # Limpieza suave
        kernel_small = np.ones((3, 3), np.uint8)
        mask_black = cv2.morphologyEx(mask_black, cv2.MORPH_OPEN, kernel_small, iterations=2)
        mask_black = cv2.morphologyEx(mask_black, cv2.MORPH_CLOSE, kernel_small, iterations=2)
        #self.save_step("04_black_cleaned", mask_black, "Negro limpiado")
        
        # Extensión de negro por conectividad vertical
        mask_black_extended = self.extend_black_vertically(mask_black, gray, h_img)
        s#elf.save_step("05_black_extended", mask_black_extended, "Negro extendido verticalmente")
        
        # ============= VERDE MEJORADO =============
        print("\n[2] Detección de VERDE mejorada")
        
        # HSV más amplio (incluye verdes claros y amarillentos)
        lower_green = np.array([30, 25, 30])  # H más bajo, S más bajo
        upper_green = np.array([95, 255, 255])  # H más alto
        mask_green_hsv = cv2.inRange(hsv, lower_green, upper_green)
        #self.save_step("06_green_hsv", mask_green_hsv, "Verde HSV amplio")
        
        # RGB: dominancia moderada
        green_dominance = (g > r * 1.05) & (g > b * 1.05) & (g > 35)
        mask_green_rgb = green_dominance.astype(np.uint8) * 255
        #self.save_step("07_green_rgb", mask_green_rgb, "Verde RGB")
        
        # Combinar
        mask_green = cv2.bitwise_or(mask_green_hsv, mask_green_rgb)
        
        # Filtro anti-madera (solo lo muy obvio)
        mask_wood = ((h >= 8) & (h <= 35) & (s < 55) & (v > 80)).astype(np.uint8) * 255
        mask_green = cv2.bitwise_and(mask_green, cv2.bitwise_not(mask_wood))
        #self.save_step("08_green_no_wood", mask_green, "Verde sin madera")
        
        # Limpieza
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_OPEN, kernel_small, iterations=2)
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel_small, iterations=2)
        #self.save_step("09_green_cleaned", mask_green, "Verde limpiado")
        
        # ============= COMBINACIÓN =============
        print("\n[3] Combinación")
        
        mask_combined = cv2.bitwise_or(mask_black_extended, mask_green)
        #self.save_step("10_combined", mask_combined, "Negro + Verde")
        
        # Filtros básicos de fondo
        mask_not_white = ((gray < 170) | (s > 35)).astype(np.uint8) * 255
        mask_combined = cv2.bitwise_and(mask_combined, mask_not_white)
        #self.save_step("11_no_white", mask_combined, "Sin blanco")
        
        # Morfología final
        kernel_medium = np.ones((5, 5), np.uint8)
        mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_CLOSE, 
                                         kernel_medium, iterations=2)
        #self.save_step("12_morph_close", mask_combined, "Cierre morfológico")
        
        kernel_vertical = np.ones((7, 3), np.uint8)
        mask_combined = cv2.morphologyEx(mask_combined, cv2.MORPH_CLOSE, 
                                         kernel_vertical, iterations=1)
        #self.save_step("13_morph_vertical", mask_combined, "Cierre vertical")
        
        # ============= CANNY Y BORDES (MEJORADO) =============
        print("\n[4] Bordes Canny (solo en vacíos pequeños)")
        
        blurred = cv2.GaussianBlur(gray, (3, 3), 0.5)
        edges = cv2.Canny(blurred, 35, 85)
        #self.save_step("14_canny_edges", edges, "Bordes Canny brutos")
        
        # NUEVO: Solo aplicar Canny en VACÍOS dentro de la máscara
        # Invertir máscara para encontrar huecos
        mask_inverted = cv2.bitwise_not(mask_combined)
        #self.save_step("15_mask_inverted", mask_inverted, "Vacíos en la máscara")
        
        # Encontrar componentes de vacíos
        num_holes, labels_holes, stats_holes, _ = cv2.connectedComponentsWithStats(
            mask_inverted, connectivity=8)
        
        # Solo aplicar Canny en huecos PEQUEÑOS (posibles grietas)
        max_hole_area = int(h_img * w_img * 0.02)  # 2% del área total
        mask_small_holes = np.zeros_like(mask_inverted)
        
        for i in range(1, num_holes):
            area = stats_holes[i, cv2.CC_STAT_AREA]
            if area < max_hole_area:  # Solo huecos pequeños
                mask_small_holes[labels_holes == i] = 255
        
        #self.save_step("16_small_holes", mask_small_holes,  Descomentar todos los save_Step para ver img paso a paso de filtros
        #              "Huecos pequeños donde aplicar Canny")
        
        # Aplicar Canny SOLO en huecos pequeños
        edges_masked = cv2.bitwise_and(edges, mask_small_holes)
        #self.save_step("17_canny_masked", edges_masked, "Canny SOLO en huecos pequeños")
        
        kernel_edge = np.ones((2, 2), np.uint8)
        edges_dilated = cv2.dilate(edges_masked, kernel_edge, iterations=1)
        #self.save_step("18_canny_dilated", edges_dilated, "Canny dilatado")
        
        binary = cv2.bitwise_or(mask_combined, edges_dilated)
        #self.save_step("19_binary_with_edges", binary, "Máscara + Canny en huecos pequeños")
        
        # ============= COMPONENTES =============
        print("\n[5] Filtrado de componentes")
        
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        print(f"  Componentes detectados: {num_labels-1}")
        
        # Visualización de componentes
        components_colored = np.zeros((binary.shape[0], binary.shape[1], 3), dtype=np.uint8)
        np.random.seed(42)
        colors = np.random.randint(50, 255, size=(num_labels, 3), dtype=np.uint8)
        colors[0] = [0, 0, 0]
        
        for i in range(num_labels):
            components_colored[labels == i] = colors[i]
        
        #self.save_step("20_components_colored", components_colored,
        #              f"Componentes detectados ({num_labels-1})")
        
        # Área mínima adaptativa (basada en tamaño de imagen)
        min_area = int(h_img * w_img * 0.005)  # 0.5% del área total
        max_area = int(h_img * w_img * 0.6)    # 60% del área total
        
        binary_filtered = np.zeros_like(binary)
        kept = 0
        
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if min_area <= area <= max_area:
                binary_filtered[labels == i] = 255
                kept += 1
        
        print(f"  Componentes mantenidos: {kept}")
        #self.save_step("21_components_filtered", binary_filtered, 
        #              f"Filtrados por área ({kept} mantenidos)")
        
        # Refinamiento final
        binary_filtered = cv2.morphologyEx(binary_filtered, cv2.MORPH_CLOSE, 
                                          kernel_small, iterations=1)
        #self.save_step("22_final_binary", binary_filtered, "Imagen binaria FINAL")
        
        # ============= CONTORNOS CON DOBLE FILTRO =============
        print("\n[6] Contornos con filtro de bordes mejorado")
        
        contours, _ = cv2.findContours(binary_filtered, cv2.RETR_EXTERNAL, 
                                       cv2.CHAIN_APPROX_NONE)
        print(f"  Contornos detectados: {len(contours)}")
        
        # Filtrar contornos
        center_point = (w_img // 2, h_img // 2)
        filtered_contours = []
        rejection_reasons = []
        
        for idx, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            # Verificar si el contorno encierra el centro
            contains_center = cv2.pointPolygonTest(contour, center_point, False) >= 0
            
            if contains_center:
                # Si encierra el centro, SIEMPRE se mantiene
                filtered_contours.append(contour)
                print(f"    ✓ Contorno {idx+1}: Mantiene (encierra centro, área={int(area)})")
            else:
                # Verificar si toca bordes de la IMAGEN (no el margen)
                touches_image_border = self.touches_image_border(contour, h_img, w_img)
                
                if touches_image_border:
                    rejection_reasons.append(f"Contorno {idx+1}: toca borde de imagen")
                    print(f"    ✗ Contorno {idx+1}: Descartado (toca borde imagen, área={int(area)})")
                    continue
                
                # Verificar distancia al margen interno
                if self.is_contour_away_from_edges(contour, h_img, w_img, margin_percent=0.12):
                    filtered_contours.append(contour)
                    print(f"    ✓ Contorno {idx+1}: Mantiene (alejado de bordes, área={int(area)})")
                else:
                    rejection_reasons.append(f"Contorno {idx+1}: cerca del margen interno")
                    print(f"    ✗ Contorno {idx+1}: Descartado (cerca margen, área={int(area)})")
        
        print(f"  Contornos después de filtro: {len(filtered_contours)}")
        
        # Crear set de IDs para comparación rápida
        filtered_contour_ids = set(id(c) for c in filtered_contours)
        
        # Visualizar contornos descartados con razones
        contours_before = image.copy()
        for idx, contour in enumerate(contours):
            # Rojo para descartados, verde para mantenidos
            if id(contour) in filtered_contour_ids:
                cv2.drawContours(contours_before, [contour], -1, (0, 255, 0), 2)
            else:
                cv2.drawContours(contours_before, [contour], -1, (0, 0, 255), 2)
        
        # Dibujar margen y centro
        margin_h = int(h_img * 0.12)
        margin_w = int(w_img * 0.12)
        cv2.rectangle(contours_before, (margin_w, margin_h), 
                     (w_img-margin_w, h_img-margin_h), (255, 128, 0), 2)
        cv2.circle(contours_before, center_point, 10, (255, 0, 255), -1)
        
        #self.save_step("23_contours_with_filter", contours_before, 
        #              f"Verde=mantiene, Rojo=descarta ({len(filtered_contours)}/{len(contours)})")
        
        # Suavizado adaptativo
        smoothed_contours = []
        for contour in filtered_contours:
            perimeter = cv2.arcLength(contour, True)
            epsilon = 0.002 * perimeter
            approx = cv2.approxPolyDP(contour, epsilon, True)
            smoothed_contours.append(approx)
        contour_stats = self.analyze_contours_statistics(
        smoothed_contours, mask_green, mask_black_extended, image, gray)

        result = image.copy()
        cv2.drawContours(result, smoothed_contours, -1, (0, 255, 255), 2)
        cv2.circle(result, center_point, 10, (255, 0, 255), -1)
        self.save_step("24_contours_final", result, 
              f"Contornos FINALES ({len(smoothed_contours)})")
        
        print("\n" + "="*70)
        print(f"COMPLETADO: {len(self.steps)} pasos")
        print("="*70)
        
        return binary_filtered, smoothed_contours
    
    def extend_black_vertically(self, mask_black, gray, height):
        """Extiende regiones negras verticalmente para capturar bordes completos"""
        mask_extended = mask_black.copy()
        
        # Para cada columna, si hay píxeles negros, conectarlos verticalmente
        for col in range(mask_black.shape[1]):
            black_pixels = np.where(mask_black[:, col] > 0)[0]
            
            if len(black_pixels) > 1:
                min_y = black_pixels.min()
                max_y = black_pixels.max()
                gap = max_y - min_y
                
                # Si el gap es razonable y la región intermedia es oscura
                if gap < height * 0.25:  # Menos del 25% de la altura
                    intermediate = gray[min_y:max_y+1, col]
                    if np.mean(intermediate) < 85:  # Región oscura
                        mask_extended[min_y:max_y+1, col] = 255
        
        # Limpieza
        kernel = np.ones((5, 3), np.uint8)
        mask_extended = cv2.morphologyEx(mask_extended, cv2.MORPH_CLOSE, kernel)
        
        return mask_extended
    
    def touches_image_border(self, contour, height, width, border_pixels=5):
        """
        Verifica si un contorno TOCA el borde exacto de la imagen.
        border_pixels: margen de píxeles del borde (default=5)
        """
        # Obtener todos los puntos del contorno
        points = contour.reshape(-1, 2)
        
        # Verificar si algún punto toca el borde
        touches_top = np.any(points[:, 1] <= border_pixels)
        touches_bottom = np.any(points[:, 1] >= (height - border_pixels - 1))
        touches_left = np.any(points[:, 0] <= border_pixels)
        touches_right = np.any(points[:, 0] >= (width - border_pixels - 1))
        
        return touches_top or touches_bottom or touches_left or touches_right
    
    def is_contour_away_from_edges(self, contour, height, width, margin_percent=0.15):
        """
        Verifica si un contorno está alejado de los bordes de la imagen.
        margin_percent: porcentaje del borde a considerar (0.15 = 15%)
        """
        margin_h = int(height * margin_percent)
        margin_w = int(width * margin_percent)
        
        # Obtener bounding box del contorno
        x, y, w, h = cv2.boundingRect(contour)
        
        # Verificar si toca alguno de los bordes
        touches_top = y < margin_h
        touches_bottom = (y + h) > (height - margin_h)
        touches_left = x < margin_w
        touches_right = (x + w) > (width - margin_w)
        
        # Si toca cualquier borde, NO está alejado
        if touches_top or touches_bottom or touches_left or touches_right:
            return False
        
        return True
    
    def analyze_contours_statistics(self, contours, mask_green, mask_black, image, gray):
        """
        Analiza estadísticas de píxeles dentro de cada contorno.
        Retorna lista de diccionarios con estadísticas.
        """
        stats_list = []
        
        print("\n" + "="*70)
        print("ESTADÍSTICAS POR CONTORNO")
        print("="*70)
        
        for idx, contour in enumerate(contours):
            # Crear máscara para este contorno
            mask_contour = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask_contour, [contour], -1, 255, -1)
            
            # Contar píxeles totales
            total_pixels = np.sum(mask_contour > 0)
            
            # Contar píxeles verdes
            green_pixels = np.sum((mask_contour > 0) & (mask_green > 0))
            green_ratio = green_pixels / total_pixels if total_pixels > 0 else 0
            
            # Contar píxeles negros
            black_pixels = np.sum((mask_contour > 0) & (mask_black > 0))
            black_ratio = black_pixels / total_pixels if total_pixels > 0 else 0
            
            # Calcular media y desviación estándar de intensidad
            pixels_in_contour = gray[mask_contour > 0]
            mean_intensity = np.mean(pixels_in_contour) if len(pixels_in_contour) > 0 else 0
            std_intensity = np.std(pixels_in_contour) if len(pixels_in_contour) > 0 else 0
            
            # Clasificar según proporciones
            contour_class = self.classify_contour(green_ratio, black_ratio, mean_intensity)
            
            stats = {
                'id': idx + 1,
                'area': cv2.contourArea(contour),
                'total_pixels': total_pixels,
                'green_pixels': green_pixels,
                'green_ratio': green_ratio,
                'black_pixels': black_pixels,
                'black_ratio': black_ratio,
                'mean_intensity': mean_intensity,
                'std_intensity': std_intensity,
                'class': contour_class
            }
            
            stats_list.append(stats)
            
            # Imprimir estadísticas
            print(f"\nContorno {idx+1}:")
            print(f"  Área: {stats['area']:.0f} px²")
            print(f"  Píxeles totales: {total_pixels}")
            print(f"  Píxeles verdes: {green_pixels} ({green_ratio:.1%})")
            print(f"  Píxeles negros: {black_pixels} ({black_ratio:.1%})")
            print(f"  Media intensidad: {mean_intensity:.1f}")
            print(f"  Desv. estándar: {std_intensity:.1f}")
            print(f"  Clasificación: {contour_class}")
        
        print("\n" + "="*70)
        
        # ⭐ LÍNEA CRÍTICA PARA EL ANÁLISIS ESTADÍSTICO ⭐
        self.last_contour_stats = stats_list
        
        return stats_list

    def classify_contour(self, green_ratio, black_ratio, mean_intensity):
        """
        Clasifica el contorno según las proporciones de colores.
        """
        # Lechuga: Alto porcentaje de verde (>40%)
        if green_ratio > 0.40:
            if green_ratio > 0.70:
                return "LECHUGA_GRANDE"
            else:
                return "LECHUGA_MEDIA"
        
        # Vaso/Plantín: Alto porcentaje de negro (>20%) o baja intensidad
        elif black_ratio > 0.20 or mean_intensity < 80:
            if black_ratio > 0.40:
                return "VASO_NEGRO"
            else:
                return "VASO_MIXTO"
        
        # Indeterminado: No cumple criterios claros
        else:
            if mean_intensity > 150:
                return "FONDO_CLARO"
            else:
                return "INDETERMINADO"

    def create_center_region_mask(self, height, width, strict=True):
        """Crea máscara de región central - ESTRICTA para eliminar objetos alejados"""
        mask = np.zeros((height, width), dtype=np.uint8)
        
        if strict:
            # Región central más pequeña (50% del centro)
            y_margin = int(height * 0.25)
            x_margin = int(width * 0.25)
        else:
            # Región central normal (60% del centro)
            y_margin = int(height * 0.2)
            x_margin = int(width * 0.2)
        
        mask[y_margin:height-y_margin, x_margin:width-x_margin] = 255
        
        # Suavizar bordes menos (transición más abrupta)
        mask = cv2.GaussianBlur(mask, (31, 31), 0)
        
        return mask
    
    def save_all_steps(self, output_folder, image_name):
        """Guarda pasos y resumen"""
        base_folder = Path(output_folder) / image_name
        steps_folder = base_folder / 'steps'
        summary_folder = base_folder / 'summary'
        
        steps_folder.mkdir(parents=True, exist_ok=True)
        summary_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"\nGuardando en: {base_folder}")
        
        # Guardar pasos individuales
        for step_name, step_data in self.steps.items():
            step_path = steps_folder / f"{step_name}.jpg"
            img = step_data['image']
            
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
            # Añadir texto
            img_annotated = img.copy()
            cv2.rectangle(img_annotated, (5, 5), (min(img.shape[1]-5, 700), 60),
                         (0, 0, 0), -1)
            cv2.putText(img_annotated, step_name, (15, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(img_annotated, step_data['description'][:80], (15, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            
            cv2.imwrite(str(step_path), img_annotated)
        
        # Crear grid resumen
        self.create_summary_grid(summary_folder, image_name)
        
        print(f"✓ Guardado completo")
    
    def create_summary_grid(self, summary_folder, image_name):
        """Grid resumen con pasos clave"""
        key_steps = [
            '01_brighter', '09_green_cleaned', '05_black_extended', '10_combined',
            '14_canny_edges', '16_small_holes', '19_binary_with_edges', '22_final_binary',
            '20_components_colored', '23_contours_with_filter', '24_contours_final'
        ]
        
        # Grid 3x4 (12 espacios)
        while len(key_steps) < 12:
            key_steps.append(key_steps[-1])
        
        target_w, target_h = 400, 300
        grid = np.zeros((target_h * 3, target_w * 4, 3), dtype=np.uint8)
        
        for idx, step_name in enumerate(key_steps[:12]):
            if step_name not in self.steps:
                continue
            
            img = self.steps[step_name]['image']
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
            img_resized = cv2.resize(img, (target_w, target_h))
            
            # Añadir título
            cv2.rectangle(img_resized, (0, 0), (target_w, 30), (0, 0, 0), -1)
            cv2.putText(img_resized, step_name, (10, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            row = idx // 4
            col = idx % 4
            y1 = row * target_h
            x1 = col * target_w
            
            grid[y1:y1+target_h, x1:x1+target_w] = img_resized
        
        grid_path = summary_folder / f"{image_name}_summary_grid.jpg"
        cv2.imwrite(str(grid_path), grid)
        print(f"  ✓ Grid: {grid_path.name}")


def process_images(input_folder, output_folder):
    """Procesa todas las imágenes"""
    detector = EdgeDetectorOptimized()
    
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        image_files.extend(Path(input_folder).glob(f'*{ext}'))
        image_files.extend(Path(input_folder).glob(f'*{ext.upper()}'))
    
    if not image_files:
        print(f"❌ No hay imágenes en: {input_folder}")
        return
    
    print(f"\nProcesando {len(image_files)} imágenes...")
    
    for img_path in image_files:
        print(f"\n{'#'*70}")
        print(f"# {img_path.name}")
        print(f"{'#'*70}")
        
        image = cv2.imread(str(img_path))
        if image is None:
            continue
        
        detector.steps = {}
        binary, contours = detector.detect_edges(image)
        detector.save_all_steps(output_folder, img_path.stem)


# CONFIGURACIÓN
INPUT_FOLDER = '/home/brenda/Documents/BD_ORIGINALES/recortadas/vasos'
OUTPUT_FOLDER = "/home/brenda/Documents/validation/contornosvasos"

if __name__ == "__main__":
    process_images(INPUT_FOLDER, OUTPUT_FOLDER)