import cv2
import os

def main():
    # Abrir la cámara
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No se pudo abrir la cámara")
        return
    
    # Configurar la resolución de la cámara (opcional)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Contador para nombres de archivo
    contador = 865
    carpeta = "capturas_plantines_2"
    os.makedirs(carpeta, exist_ok=True)
    
    # Parámetros de recorte (ajustables según necesidad)
    # Valores entre 0.0 y 1.0 que representan porcentajes de la imagen
    recorte_config = {
        'x_inicio': 0,    # 10% desde la izquierda
        'x_fin': 1,       # 90% del ancho (deja 10% a la derecha)
        'y_inicio': 0.2,    # 20% desde arriba
        'y_fin': 0.8        # 80% del alto (deja 20% abajo)
    }
    
    print("Controles:")
    print("- Presiona 'c' para capturar imagen")
    print("- Presiona 'q' para salir")
    print("- Presiona 'r' para resetear configuración de recorte")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo capturar el frame")
            break
        
        # Rotar la imagen 90° a la izquierda (contrahorario)
        frame_rotado = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Obtener dimensiones después de la rotación
        alto, ancho = frame_rotado.shape[:2]
        
        # Calcular coordenadas de recorte basadas en los porcentajes
        x1 = int(ancho * recorte_config['x_inicio'])
        x2 = int(ancho * recorte_config['x_fin'])
        y1 = int(alto * recorte_config['y_inicio'])
        y2 = int(alto * recorte_config['y_fin'])
        
        # Asegurar que las coordenadas estén dentro de los límites
        x1 = max(0, min(x1, ancho-1))
        x2 = max(x1+1, min(x2, ancho))
        y1 = max(0, min(y1, alto-1))
        y2 = max(y1+1, min(y2, alto))
        
        # Crear una copia para mostrar el área de recorte
        frame_preview = frame_rotado.copy()
        
        # Dibujar rectángulo que muestra el área de recorte
        cv2.rectangle(frame_preview, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Recortar la imagen
        frame_recortado = frame_rotado[y1:y2, x1:x2]
        
        # Redimensionar para mostrar si es necesario
        preview_height = 400
        if frame_preview.shape[0] > preview_height:
            aspect_ratio = frame_preview.shape[1] / frame_preview.shape[0]
            preview_width = int(preview_height * aspect_ratio)
            frame_preview = cv2.resize(frame_preview, (preview_width, preview_height))
        
        # Mostrar la vista previa con el rectángulo de recorte
        cv2.imshow("Vista previa - Area de recorte en verde", frame_preview)
        
        # Mostrar la imagen recortada en una ventana separada
        if frame_recortado.size > 0:
            cv2.imshow("Imagen recortada - 'c' capturar, 'q' salir", frame_recortado)
        
        # Esperar tecla
        key = cv2.waitKey(1) & 0xFF
        
        # Capturar imagen
        # Capturar imagen
        if key == ord('c'):
            if frame_recortado.size > 0:
                if contador % 2 == 0:  # PAR → test
                    nombre_archivo = os.path.join(carpeta, f"plantin_test_{contador:03d}.jpg")
                else:  # IMPAR → normal
                    nombre_archivo = os.path.join(carpeta, f"plantin_training{contador:03d}.jpg")
                
                cv2.imwrite(nombre_archivo, frame_recortado)
                print(f"Foto guardada: {nombre_archivo}")
                print(f"Dimensiones: {frame_recortado.shape[1]}x{frame_recortado.shape[0]} píxeles")
                
                contador += 1
            else:
                print("Error: El área de recorte es inválida")
        
        # Salir
        elif key == ord('q'):
            break
        
        # Ajustes de recorte con las teclas numéricas
            step = 0.05  # Paso de ajuste (5%)
        
        # Mostrar ayuda
        elif key == ord('h'):
            print("\n--- AYUDA ---")
            print("c: Capturar imagen")
            print("q: Salir")
            print("h: Mostrar esta ayuda")
            print("---------------\n")
    
    # Liberar recursos
    cap.release()
    cv2.destroyAllWindows()
    print(f"\nSe capturaron {contador-1} imágenes en la carpeta '{carpeta}'")

if __name__ == "__main__":
    main()