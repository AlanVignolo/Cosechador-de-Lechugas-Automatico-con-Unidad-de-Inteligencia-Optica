"""
IA Simplificada para Detección de Cintas Negras
Detector básico y eficiente para cintas negras en tubo horizontal
"""

import cv2
import numpy as np
import time

class SimpleTapeDetector:
    def __init__(self):
        self.last_detection_position = None
        self.detection_cooldown_mm = 50
        
    def detect_tape_in_frame(self, frame):
        """
        Detecta cinta negra en el frame usando métodos simples pero efectivos
        Retorna: {'detected': bool, 'center_x': int, 'confidence': float}
        """
        try:
            if frame is None:
                return {'detected': False, 'center_x': 0, 'confidence': 0.0}
            
            # Convertir a escala de grises
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Aplicar threshold para detectar objetos oscuros (cintas negras)
            # Valores bajos = negro, valores altos = blanco/fondo
            _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return {'detected': False, 'center_x': 0, 'confidence': 0.0}
            
            # Filtrar contornos por área mínima
            min_area = 200  # Área mínima para considerar como cinta
            valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
            
            if not valid_contours:
                return {'detected': False, 'center_x': 0, 'confidence': 0.0}
            
            # Encontrar el contorno más central y con mejor forma
            frame_center_x = frame.shape[1] // 2
            frame_center_y = frame.shape[0] // 2
            
            best_contour = None
            best_score = 0
            
            for contour in valid_contours:
                # Calcular bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                center_x = x + w // 2
                center_y = y + h // 2
                
                # Filtros básicos para forma de cinta
                aspect_ratio = h / w if w > 0 else 0
                area_ratio = cv2.contourArea(contour) / (w * h) if w * h > 0 else 0
                
                # Preferir contornos verticales (cintas) y bien formados
                if 1.5 <= aspect_ratio <= 8.0 and area_ratio >= 0.3:
                    # Calcular distancia al centro
                    distance_to_center = abs(center_x - frame_center_x)
                    
                    # Score: priorizar cercanía al centro y buena forma
                    centrality_score = max(0, 1.0 - distance_to_center / frame_center_x)
                    form_score = min(area_ratio, 1.0)
                    
                    total_score = centrality_score * 0.7 + form_score * 0.3
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_contour = contour
            
            if best_contour is not None:
                # Calcular centro del mejor contorno
                x, y, w, h = cv2.boundingRect(best_contour)
                center_x = x + w // 2
                
                # Solo detectar si está cerca del centro (±40 píxeles)
                distance_from_center = abs(center_x - frame_center_x)
                if distance_from_center <= 40:
                    return {
                        'detected': True,
                        'center_x': center_x,
                        'confidence': best_score,
                        'bounding_rect': (x, y, w, h)
                    }
            
            return {'detected': False, 'center_x': 0, 'confidence': 0.0}
            
        except Exception as e:
            print(f"Error en detección: {e}")
            return {'detected': False, 'center_x': 0, 'confidence': 0.0}
    
    def should_record_detection(self, current_position_mm):
        """Verificar si debe registrar la detección (cooldown)"""
        if self.last_detection_position is None:
            return True
        
        distance_since_last = abs(current_position_mm - self.last_detection_position)
        return distance_since_last >= self.detection_cooldown_mm
    
    def record_detection(self, position_mm):
        """Registrar que se hizo una detección en esta posición"""
        self.last_detection_position = position_mm
    
    def draw_detection(self, frame, detection_result):
        """Dibujar la detección en el frame"""
        if detection_result['detected']:
            center_x = detection_result['center_x']
            confidence = detection_result['confidence']
            
            # Dibujar círculo en el centro detectado
            cv2.circle(frame, (center_x, frame.shape[0]//2), 8, (0, 255, 0), 3)
            
            # Dibujar rectángulo si está disponible
            if 'bounding_rect' in detection_result:
                x, y, w, h = detection_result['bounding_rect']
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Mostrar confianza
            cv2.putText(frame, f"CINTA {confidence:.2f}", 
                       (center_x-30, frame.shape[0]//2-20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return frame

def test_simple_detector():
    """Función de prueba para el detector simple"""
    print("=== PROBANDO DETECTOR SIMPLE DE CINTAS ===")
    
    detector = SimpleTapeDetector()
    
    # Simular algunas detecciones
    test_frame = np.zeros((200, 300, 3), dtype=np.uint8)
    
    # Dibujar una "cinta" negra vertical en el centro
    cv2.rectangle(test_frame, (140, 50), (160, 150), (0, 0, 0), -1)
    
    result = detector.detect_tape_in_frame(test_frame)
    print(f"Resultado de prueba: {result}")
    
    return detector

if __name__ == "__main__":
    test_simple_detector()
