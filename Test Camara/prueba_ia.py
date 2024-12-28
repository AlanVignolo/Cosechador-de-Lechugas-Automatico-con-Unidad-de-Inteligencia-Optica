import cv2
import numpy as np
import os
from datetime import datetime

def crear_directorio_resultados():
    """Directorio para los resultados en cada iteracion de prueba"""
    timestamp = datetime.now().strftime("%d_%m_%H_%M")
    directorio = f"Resultados {timestamp} hs."
    os.makedirs(directorio, exist_ok=True)
    return directorio

def clasificar_verde(h, s, v):
    """
    Clasificación detallada del verde basada en HSV
    H (Hue): 35-85 es el rango del verde
    S (Saturación): Indica la pureza del color
    V (Valor): Indica el brillo
    """
    # Clasificación del verde
    if s < 40:  # Muy poca saturación
        return "verde blanquecino (inmaduro)"
    elif s > 150:  # Alta saturación
        if v < 100:
            return "verde intenso oscuro (óptimo para cosecha)"
        else:
            return "verde intenso brillante (casi listo)"
    else:  # Saturación media
        if v < 80:
            return "verde opaco (revisar planta)"
        elif v < 120:
            return "verde medio (en desarrollo)"
        else:
            return "verde claro (inmaduro)"

def analizar_lechuga(imagen_path, pixeles_por_cm=None):
    """
    Analiza una imagen de lechuga para determinar su altura y color
    pixeles_por_cm: factor de conversión de píxeles a centímetros
    """
    # Crear directorio para resultados
    dir_resultados = crear_directorio_resultados()
    
    # Leer la imagen
    imagen = cv2.imread(imagen_path)
    if imagen is None:
        return "Error: No se pudo cargar la imagen"
    
    # Guardar imagen original
    cv2.imwrite(os.path.join(dir_resultados, '1_imagen_original.jpg'), imagen)
    
    alto_original, ancho_original = imagen.shape[:2]
    print(f"Dimensiones de la imagen: {ancho_original}x{alto_original}")
    
    # Convertir a HSV
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    # Guardar componentes HSV por separado
    cv2.imwrite(os.path.join(dir_resultados, '2_canal_hue.jpg'), hsv[:,:,0])
    cv2.imwrite(os.path.join(dir_resultados, '2_canal_saturation.jpg'), hsv[:,:,1])
    cv2.imwrite(os.path.join(dir_resultados, '2_canal_value.jpg'), hsv[:,:,2])
    
    # Definir rango de color verde
    verde_bajo = np.array([35, 30, 30])
    verde_alto = np.array([85, 255, 255])
    
    # Crear máscara para detectar verde
    mascara = cv2.inRange(hsv, verde_bajo, verde_alto)
    cv2.imwrite(os.path.join(dir_resultados, '3_mascara_verde.jpg'), mascara)
    
    # Aplicar operaciones morfológicas para mejorar la máscara
    kernel = np.ones((5,5), np.uint8)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel)
    cv2.imwrite(os.path.join(dir_resultados, '4_mascara_procesada.jpg'), mascara)
    
    # Encontrar contornos
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contornos:
        return "No se detectó planta en la imagen"
    
    # Dibujar contornos encontrados
    imagen_contornos = imagen.copy()
    cv2.drawContours(imagen_contornos, contornos, -1, (0,255,0), 2)
    cv2.imwrite(os.path.join(dir_resultados, '5_todos_contornos.jpg'), imagen_contornos)
    
    # Encontrar el contorno más grande
    contorno_planta = max(contornos, key=cv2.contourArea)
    
    # Usar minAreaRect para obtener un rectángulo rotado que se ajuste mejor
    rect = cv2.minAreaRect(contorno_planta)
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    
    # Calcular altura usando el rectángulo rotado
    _, (width, height), angle = rect
    altura_pixeles = max(width, height)  # Tomamos la dimensión más larga
    
    # Dibujar el contorno y el rectángulo rotado
    imagen_contorno_mayor = imagen.copy()
    cv2.drawContours(imagen_contorno_mayor, [contorno_planta], -1, (0,255,0), 2)
    cv2.drawContours(imagen_contorno_mayor, [box], 0, (0,0,255), 2)
    cv2.imwrite(os.path.join(dir_resultados, '6_contorno_mayor.jpg'), imagen_contorno_mayor)
    
    # Analizar color
    mascara_planta = np.zeros_like(mascara)
    cv2.drawContours(mascara_planta, [contorno_planta], -1, 255, -1)
    cv2.imwrite(os.path.join(dir_resultados, '7_mascara_planta_final.jpg'), mascara_planta)
    
    # Obtener valores HSV promedio de la planta
    hsv_promedio = cv2.mean(hsv, mask=mascara_planta)[:3]
    
    # Análisis detallado del color
    h, s, v = hsv_promedio
    color = clasificar_verde(h, s, v)
    
    # Calcular histograma de tonos verdes para análisis más detallado
    hist_verde = cv2.calcHist([hsv], [0], mascara_planta, [50], [35,85])
    pico_verde = np.argmax(hist_verde) + 35  # Tono de verde más común
    
    try:
        # Dibujar resultados en la imagen
        imagen_resultado = imagen.copy()
        # Dibujar el rectángulo rotado
        cv2.drawContours(imagen_resultado, [box], 0, (0,0,255), 2)
        
        # Agregar texto con medidas y clasificación
        texto_altura = f"Altura: {altura_pixeles:.1f}px"
        if pixeles_por_cm:
            altura_cm = altura_pixeles / pixeles_por_cm
            texto_altura += f" ({altura_cm:.1f}cm)"
            
        cv2.putText(imagen_resultado, texto_altura, 
                   (int(box[0][0]), int(box[0][1]-30)), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)
        
        cv2.putText(imagen_resultado, f"Estado: {color}", 
                   (int(box[0][0]), int(box[0][1]-60)), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)
        
        cv2.imwrite(os.path.join(dir_resultados, '8_resultado_final.jpg'), imagen_resultado)
        
    except Exception as e:
        print(f"Error al dibujar resultados: {e}")
        return "Error al procesar la imagen"
    
    # Preparar resultados con información más detallada
    resultados = {
        'altura_pixeles': altura_pixeles,
        'altura_cm': altura_cm if pixeles_por_cm else None,
        'color': color,
        'hsv_promedio': hsv_promedio,
        'tono_verde_dominante': pico_verde,
        'angulo_planta': angle,
        'area_planta': cv2.contourArea(contorno_planta),
        'directorio_resultados': dir_resultados
    }
    
    return resultados

def main():
    # Factor de conversión (necesitas calibrarlo con una medida conocida)
    PIXELES_POR_CM = 20
    
    try:
        # Analizar imagen
        resultados = analizar_lechuga('foto_prueba.jpg', PIXELES_POR_CM)
        
        # Mostrar resultados
        if isinstance(resultados, dict):
            print("\nResultados del análisis:")
            print(f"Altura en píxeles: {resultados['altura_pixeles']:.1f}")
            if resultados['altura_cm']:
                print(f"Altura aproximada: {resultados['altura_cm']:.1f} cm")
            print(f"Color: {resultados['color']}")
            print(f"Ángulo de la planta: {resultados['angulo_planta']:.1f}°")
            print(f"Área de la planta: {resultados['area_planta']:.1f} píxeles²")
            print(f"Tono verde dominante: {resultados['tono_verde_dominante']}")
            print(f"\nImágenes guardadas en: {resultados['directorio_resultados']}")
            print("Se han guardado las siguientes imágenes:")
            print("1. Imagen original")
            print("2. Canales HSV")
            print("3. Máscara de color verde")
            print("4. Máscara procesada")
            print("5. Todos los contornos")
            print("6. Contorno mayor")
            print("7. Máscara final")
            print("8. Resultado final")
        else:
            print(resultados)
            
    except Exception as e:
        print(f"Error en el programa principal: {e}")

if __name__ == "__main__":
    main()