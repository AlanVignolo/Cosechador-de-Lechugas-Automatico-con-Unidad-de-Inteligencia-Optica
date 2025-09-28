"""
Detector de Tubos Vertical - Sistema de detección específico para tubos blancos opacos
Versión con debug visual paso a paso para ajustar filtros y parámetros
"""

import cv2
import numpy as np
import json
import matplotlib.pyplot as plt
import threading
import time
import os
import sys
from typing import List, Tuple, Optional, Dict, Any

# Importar el gestor de cámara centralizado
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
from camera_manager import get_camera_manager

# Cache global para recordar qué cámara funciona
_working_camera_cache = None

def capture_new_image(camera_index=0):
    """Alias para capture_image_for_tube_detection - mantiene compatibilidad"""
    return capture_image_for_tube_detection(camera_index)

def scan_available_cameras():
    """Escanea cámaras disponibles en el sistema"""
    available_cameras = []
    
    print("Escaneando cámaras disponibles...")
    
    # Probar diferentes índices
    for i in range(10):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    available_cameras.append({
                        'index': i,
                        'resolution': f"{w}x{h}",
                        'working': True
                    })
                    print(f"Cámara {i}: {w}x{h} - FUNCIONAL")
                else:
                    available_cameras.append({
                        'index': i,
                        'resolution': "Error al capturar",
                        'working': False
                    })
                    print(f"Cámara {i}: Abierta pero no captura")
                cap.release()
        except Exception as e:
            continue
    
    if not available_cameras:
        print("No se encontraron cámaras funcionales")
    
    return available_cameras

def capture_with_timeout(camera_index, timeout=5.0):
    """Captura frame usando el gestor centralizado de cámara"""
    camera_mgr = get_camera_manager()
    
    # Adquirir uso temporal de cámara para captura puntual
    if not camera_mgr.acquire("tube_detector_vertical"):
        print(f"Error: No se pudo adquirir cámara {camera_index}")
        return None
    try:
        # Capturar frame (sin iniciar stream)
        frame = camera_mgr.capture_frame(timeout=timeout, max_retries=3)
        if frame is not None:
            print(f"Frame capturado exitosamente")
        else:
            print(f"Error: No se pudo capturar frame")
        return frame
    finally:
        camera_mgr.release("tube_detector_vertical")

def capture_image_for_tube_detection(camera_index=0, max_retries=1):
    """Captura una imagen para detección de tubos usando el gestor centralizado"""
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        # ROTAR 90° - La cámara está a 90° igual que en el detector horizontal
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        alto, ancho = frame_rotado.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        return frame_recortado
    
    return None

def detect_tube_lines_debug(image, debug=True):
    """
    Detectar líneas horizontales de tubo con debug paso a paso
    Enfoque: detectar las líneas horizontales características del tubo opaco
    """
    
    if image is None:
        return []
    
    if debug:
        print("\n=== DETECTOR DE TUBOS VERTICALES ===")
        print("Objetivo: Detectar líneas horizontales del tubo opaco")
        print("Características: Tubo blanco opaco con tapas brillantes")
    
    h_img, w_img = image.shape[:2]
    img_center_y = h_img // 2
    
    # PASO 1: Preparar diferentes versiones de la imagen para análisis
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Canales individuales
    h_channel = hsv[:,:,0]  # Matiz
    s_channel = hsv[:,:,1]  # Saturación  
    v_channel = hsv[:,:,2]  # Brillo
    
    if debug:
        print(f"Imagen: {w_img}x{h_img}")
        print("Preparando filtros para detección de tubos blancos...")
        
        # Mostrar imagen original y canales
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('PASO 1: Análisis de Imagen Original', fontsize=14)
        
        axes[0,0].imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        axes[0,0].set_title('Original')
        axes[0,0].axis('off')
        
        axes[0,1].imshow(gray, cmap='gray')
        axes[0,1].set_title('Escala de Grises')
        axes[0,1].axis('off')
        
        axes[0,2].imshow(hsv)
        axes[0,2].set_title('HSV')
        axes[0,2].axis('off')
        
        axes[1,0].imshow(h_channel, cmap='hsv')
        axes[1,0].set_title('Canal H (Matiz)')
        axes[1,0].axis('off')
        
        axes[1,1].imshow(s_channel, cmap='gray')
        axes[1,1].set_title('Canal S (Saturación)')
        axes[1,1].axis('off')
        
        axes[1,2].imshow(v_channel, cmap='gray')
        axes[1,2].set_title('Canal V (Brillo)')
        axes[1,2].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    # PASO 2: Los filtros que funcionaban + detección de líneas rectangulares
    filters = {}
    
    # Filtro 1: Baja saturación estricta (el que tomaba bien el extremo del tubo)
    _, filters['baja_saturacion_estricta'] = cv2.threshold(s_channel, 25, 255, cv2.THRESH_BINARY_INV)
    
    # Filtro 2: Baja saturación limpia (el otro que funcionaba)
    _, temp_sat = cv2.threshold(s_channel, 30, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    filters['baja_saturacion_limpia'] = cv2.morphologyEx(temp_sat, cv2.MORPH_OPEN, kernel)
    
    if debug:
        print("PASO 2: Aplicando filtros para detección de tubos blancos")
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('PASO 2: Filtros para Tubos Blancos', fontsize=14)
        
        filter_names = list(filters.keys())
        for i, (name, filtered) in enumerate(filters.items()):
            if i < 6:  # Mostrar solo los primeros 6 filtros
                row, col = divmod(i, 3)
                axes[row, col].imshow(filtered, cmap='gray')
                axes[row, col].set_title(f'{name}\n{np.sum(filtered > 0)} píxeles blancos')
                axes[row, col].axis('off')
        
        # Ocultar ejes no usados
        for i in range(len(filters), 6):
            row, col = divmod(i, 3)
            axes[row, col].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    # PASO 3: Buscar rectángulos específicos - TUBO (horizontal) y TAPA (vertical)
    candidates = []
    
    for filter_name, binary_img in filters.items():
        if debug:
            pixels_blancos = cv2.countNonZero(binary_img)
            print(f"\n{filter_name}: {pixels_blancos} píxeles blancos")
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            if debug:
                print(f"  No se encontraron contornos en {filter_name}")
            continue
        
        # NUEVA LÓGICA: Buscar rectángulos específicos
        rectangulos_encontrados = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:  # Filtrar contornos muy pequeños
                continue
            
            # Obtener rectángulo delimitador
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # CLASIFICAR TIPO DE RECTÁNGULO
            tipo_rectangulo = None
            score = 0
            characteristics = []
            
            # TUBO: Rectángulo horizontal (w > h)
            if aspect_ratio > 1.5:  # Claramente horizontal
                tipo_rectangulo = "TUBO_HORIZONTAL"
                score += 25
                characteristics.append(f"tubo_horizontal({aspect_ratio:.1f})")
                
                # Bonus si está en posición central
                center_y = y + h // 2
                center_distance = abs(center_y - img_center_y)
                if center_distance < h_img * 0.4:
                    score += 20
                    characteristics.append("centrado")
                
                # Tamaño apropiado para tubo
                if 50 < w < 300 and 20 < h < 100:
                    score += 15
                    characteristics.append("tamaño_tubo_ok")
                    
            # TAPA: Rectángulo vertical (h > w)  
            elif aspect_ratio < 0.8:  # Claramente vertical
                tipo_rectangulo = "TAPA_VERTICAL"
                score += 20
                characteristics.append(f"tapa_vertical({aspect_ratio:.1f})")
                
                # Tamaño apropiado para tapa
                if 20 < w < 80 and 40 < h < 120:
                    score += 15
                    characteristics.append("tamaño_tapa_ok")
                    
                # Posición apropiada para tapa (puede estar arriba o abajo del tubo)
                center_y = y + h // 2
                if center_y < h_img * 0.7:  # No muy abajo
                    score += 10
                    characteristics.append("posición_tapa")
            
            # CUADRADO: Puede ser parte del tubo
            elif 0.8 <= aspect_ratio <= 1.2:
                tipo_rectangulo = "CUADRADO"
                score += 10
                characteristics.append(f"cuadrado({aspect_ratio:.1f})")
            
            # Bonus por filtro que funcionaba
            if 'baja_saturacion' in filter_name:
                score += 10
                characteristics.append("filtro_bueno")
            
            # Solo considerar candidatos con score mínimo
            if score > 15:
                rectangulos_encontrados.append({
                    'filter': filter_name,
                    'tipo': tipo_rectangulo,
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'aspect_ratio': aspect_ratio,
                    'center_y': y + h // 2,
                    'score': score,
                    'characteristics': characteristics
                })
        
        # Agregar a candidatos globales
        candidates.extend(rectangulos_encontrados)
        
        if debug:
            print(f"  {len(contours)} contornos totales")
            for rect in rectangulos_encontrados:
                print(f"    {rect['tipo']}: score={rect['score']}, {rect['characteristics']}")
        
        # PASO 3.5: Buscar combinaciones TUBO + TAPA
        tubos = [r for r in rectangulos_encontrados if r['tipo'] == 'TUBO_HORIZONTAL']
        tapas = [r for r in rectangulos_encontrados if r['tipo'] == 'TAPA_VERTICAL']
        
        if tubos and tapas and debug:
            print(f"  ¡COMBINACIÓN DETECTADA! {len(tubos)} tubos + {len(tapas)} tapas")
            
            # Buscar tapa cerca de tubo
            for tubo in tubos:
                tx, ty, tw, th = tubo['bbox']
                tubo_center_y = ty + th // 2
                
                for tapa in tapas:
                    px, py, pw, ph = tapa['bbox']
                    tapa_center_y = py + ph // 2
                    
                    distancia_y = abs(tubo_center_y - tapa_center_y)
                    if distancia_y < 50:  # Tapa cerca del tubo
                        # Bonus especial para combinación
                        tubo['score'] += 30
                        tapa['score'] += 25
                        tubo['characteristics'].append("con_tapa_cercana")
                        tapa['characteristics'].append("cerca_de_tubo")
                        
                        if debug:
                            print(f"    Tapa a {distancia_y}px del tubo - ¡BONUS!")
    
    if debug:
        print(f"\nPASO 3: {len(candidates)} candidatos rectangulares encontrados")
    
    # PASO 4: Mostrar mejores candidatos
    if debug and candidates:
        print(f"\nPASO 3: Encontrados {len(candidates)} candidatos")
        
        # Ordenar por score
        candidates.sort(key=lambda c: c['score'], reverse=True)
        
        # Mostrar top 6 candidatos
        top_candidates = candidates[:6]
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('PASO 3: Mejores Candidatos de Tubos', fontsize=14)
        
        for i, candidate in enumerate(top_candidates):
            if i < 6:
                row, col = divmod(i, 3)
                
                # Crear imagen del candidato
                x, y, w, h = candidate['bbox']
                candidate_img = image.copy()
                cv2.rectangle(candidate_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.circle(candidate_img, (x + w//2, candidate['center_y']), 5, (255, 0, 0), -1)
                
                axes[row, col].imshow(cv2.cvtColor(candidate_img, cv2.COLOR_BGR2RGB))
                axes[row, col].set_title(f"#{i+1}: {candidate['filter']}\nScore: {candidate['score']}")
                axes[row, col].axis('off')
        
        # Ocultar ejes no usados
        for i in range(len(top_candidates), 6):
            row, col = divmod(i, 3)
            axes[row, col].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    if debug:
        print(f"\nRESULTADO: {len(candidates)} candidatos encontrados")
        if candidates:
            best = candidates[0]
            print(f"Mejor candidato: filtro='{best['filter']}', score={best['score']}, centro_y={best['center_y']}")
    
    return candidates

def detect_tube_position(image, debug=False):
    """
    Función principal para detectar posición Y del tubo
    Retorna la coordenada Y del centro del tubo detectado
    """
    candidates = detect_tube_lines_debug(image, debug=debug)
    
    if candidates:
        # Retornar la coordenada Y del mejor candidato
        best_candidate = candidates[0]
        return best_candidate['center_y']
    
    return None

def test_tube_detection():
    """Función de test para calibrar la detección de tubos"""
    print("=== TEST DE DETECCIÓN DE TUBOS ===")
    print("Capturando imagen para análisis...")
    
    # Capturar imagen
    image = capture_image_for_tube_detection(camera_index=0)
    
    if image is None:
        print("Error: No se pudo capturar imagen")
        return
    
    print("Imagen capturada. Analizando con debug habilitado...")
    
    # Ejecutar detección con debug completo
    result = detect_tube_position(image, debug=True)
    
    if result is not None:
        print(f"\nTUBO DETECTADO en Y = {result} píxeles")
    else:
        print("\nNo se detectó ningún tubo")
    
    print("\nTest completado. Revisa las imágenes mostradas para ajustar parámetros.")

if __name__ == "__main__":
    print("=== DETECTOR DE TUBOS VERTICAL ===")
    print("Ejecuta test_tube_detection() para probar la detección")
    
    # Permitir ejecución directa del test
    test_tube_detection()
