import os
from pathlib import Path
from PIL import Image
import logging

# Configurar logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def verificar_y_eliminar_corruptas(dataset_dir, extensiones_validas={'.jpg', '.jpeg', '.png'}):
    dataset_dir = Path(dataset_dir)
    total = 0
    corruptas = 0

    if not dataset_dir.exists():
        logging.error(f"Directorio no encontrado: {dataset_dir}")
        return

    logging.info(f"Verificando imágenes en: {dataset_dir}")

    for class_dir in dataset_dir.iterdir():
        if class_dir.is_dir():
            logging.info(f"Clase: {class_dir.name}")
            for image_path in class_dir.glob("*"):
                if image_path.suffix.lower() not in extensiones_validas:
                    logging.warning(f"[{class_dir.name}] Archivo ignorado (extensión inválida): {image_path.name}")
                    continue

                total += 1
                try:
                    with Image.open(image_path) as img:
                        img.verify()
                except Exception as e:
                    logging.error(f"[{class_dir.name}] Imagen corrupta: {image_path.name} | {e}")
                    corruptas += 1
                    try:
                        image_path.unlink()  # Eliminar la imagen corrupta
                        logging.info(f"Imagen eliminada: {image_path}")
                    except Exception as del_error:
                        logging.error(f"No se pudo eliminar {image_path}: {del_error}")

    logging.info(f"\nTotal de imágenes: {total}")
    logging.info(f"Imágenes corruptas eliminadas: {corruptas}")
    logging.info(f"Imágenes válidas restantes: {total - corruptas}")

# CAMBIÁ ESTA RUTA POR TU DATASET REAL
ruta_dataset = "/home/raspberryAlan/proyecto_final/Claudio/Cosechador-de-Lechugas-Automatico-con-Unidad-de-Inteligencia-Optica/Nivel_Supervisor_IA/Analizar Cultivo/Lechugas"
verificar_y_eliminar_corruptas(ruta_dataset)
