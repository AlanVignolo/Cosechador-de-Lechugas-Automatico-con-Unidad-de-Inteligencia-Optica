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
    # Para tubos verticales, NO rotamos la imagen - mantenemos orientación original
    recorte_config = {
        'x_inicio': 0.2,
        'x_fin': 0.8,
        'y_inicio': 0.3,
        'y_fin': 0.7
    }
    
    frame = capture_with_timeout(camera_index, timeout=4.0)
    
    if frame is not None:
        # NO ROTAR - Para tubos verticales mantenemos orientación original
        # Los tubos se ven verticalmente y queremos detectar sus líneas horizontales
        
        alto, ancho = frame.shape[:2]
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        frame_recortado = frame[y1:y2, x1:x2]
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
    
    # PASO 2: Aplicar diferentes filtros para detectar tubos blancos
    filters = {}
    
    # Filtro 1: Objetos blancos brillantes (alto brillo, baja saturación)
    lower_white = np.array([0, 0, 180])      # HSV para blancos brillantes
    upper_white = np.array([180, 50, 255])
    filters['blancos_brillantes'] = cv2.inRange(hsv, lower_white, upper_white)
    
    # Filtro 2: Objetos claros (solo por brillo)
    _, filters['brillo_alto'] = cv2.threshold(v_channel, 160, 255, cv2.THRESH_BINARY)
    
    # Filtro 3: Objetos blancos opacos (baja saturación)
    _, filters['baja_saturacion'] = cv2.threshold(s_channel, 40, 255, cv2.THRESH_BINARY_INV)
    
    # Filtro 4: Combinación de brillo y saturación
    filters['blanco_opaco'] = cv2.bitwise_and(filters['brillo_alto'], filters['baja_saturacion'])
    
    # Filtro 5: Threshold simple en escala de grises para objetos claros
    _, filters['threshold_claro'] = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
    
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
    
    # PASO 3: Detectar líneas horizontales en cada filtro
    candidates = []
    
    for filter_name, binary_img in filters.items():
        if debug:
            print(f"\nAnalizando filtro: {filter_name}")
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            if debug:
                print(f"  No se encontraron contornos en {filter_name}")
            continue
        
        # Analizar cada contorno
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area < 200:  # Filtrar contornos muy pequeños
                continue
            
            # Obtener rectángulo delimitador
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calcular características del contorno
            aspect_ratio = w / h if h > 0 else 0
            extent = area / (w * h) if (w * h) > 0 else 0
            center_y = y + h // 2
            
            # Evaluar si parece parte de un tubo
            # Los tubos se ven como formas verticales (h > w) o cuadradas
            # Las líneas horizontales del tubo deberían ser más anchas que altas
            
            score = 0
            characteristics = []
            
            # Características positivas para tubos
            if 50 < area < 5000:  # Tamaño razonable
                score += 10
                characteristics.append(f"área_ok({area:.0f})")
            
            if extent > 0.3:  # Forma sólida
                score += 10
                characteristics.append(f"sólido({extent:.2f})")
            
            # Posición central (prefiero tubos cerca del centro)
            center_distance = abs(center_y - img_center_y)
            if center_distance < h_img * 0.3:  # Dentro del 30% central
                score += 15
                characteristics.append(f"centrado({center_distance:.0f}px)")
            
            # Bonus por tamaño apropiado para tubos
            if 30 < w < 200 and 30 < h < 300:
                score += 10
                characteristics.append("tamaño_tubo")
            
            if score > 15:  # Umbral mínimo para considerar candidato
                candidates.append({
                    'filter': filter_name,
                    'contour': contour,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'aspect_ratio': aspect_ratio,
                    'extent': extent,
                    'center_y': center_y,
                    'score': score,
                    'characteristics': characteristics
                })
                
                if debug:
                    print(f"  Candidato #{len(candidates)}: score={score}, características={characteristics}")
    
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
