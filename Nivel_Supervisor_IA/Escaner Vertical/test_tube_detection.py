"""
Test independiente para calibrar la detección de tubos verticales
Enfocado en análisis del canal S (Saturación) de HSV
"""
import sys
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.join(os.path.dirname(__file__),'..','..','Nivel_Supervisor'))

from tube_detector_vertical import (
    capture_image_for_tube_detection,
    detect_tube_position
)

def test_detection_debug():
    """Test de detección con debug completo - Enfocado en Canal S"""
    print("\n=== TEST DE DETECCIÓN - ANÁLISIS CANAL S ===")
    print("El tubo blanco de PVC tiene BAJA saturación")
    print("La madera del fondo tiene MAYOR saturación")
    print("-" * 60)

    image = capture_image_for_tube_detection(camera_index=0)

    if image is None:
        print("Error: No se pudo capturar imagen")
        return False

    # Detección con debug completo (muestra todos los filtros)
    result = detect_tube_position(image, debug=True)

    if result is not None:
        print(f"\n{'='*60}")
        print(f"✓ RESULTADO FINAL: TUBO DETECTADO en Y = {result} píxeles")
        print(f"{'='*60}")
        return True
    else:
        print(f"\n{'='*60}")
        print(f"✗ RESULTADO FINAL: No se detectó ningún tubo")
        print(f"{'='*60}")
        return False

def quick_saturation_test():
    """Test rápido para analizar el canal S visualmente"""
    print("\n=== TEST RÁPIDO: ANÁLISIS VISUAL CANAL S ===")
    print("Capturando imagen...")

    image = capture_image_for_tube_detection(camera_index=0)

    if image is None:
        print("Error: No se pudo capturar imagen")
        return

    # Convertir a HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    print("\nAnálisis del Canal S (Saturación):")
    print(f"  - Media: {np.mean(s):.1f}")
    print(f"  - Min: {np.min(s)}, Max: {np.max(s)}")
    print(f"  - Píxeles con S < 40 (blancos): {np.sum(s < 40)}")
    print(f"  - Píxeles con S > 40 (coloreados): {np.sum(s >= 40)}")

    # Crear visualización
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('ANÁLISIS CANAL S - Tubo Blanco vs Fondo', fontsize=16)

    axes[0,0].imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    axes[0,0].set_title('Imagen Original')
    axes[0,0].axis('off')

    axes[0,1].imshow(s, cmap='gray')
    axes[0,1].set_title('Canal S (Saturación)')
    axes[0,1].axis('off')

    axes[0,2].imshow(v, cmap='gray')
    axes[0,2].set_title('Canal V (Brillo)')
    axes[0,2].axis('off')

    # Umbrales en S
    _, s_thresh1 = cv2.threshold(255 - s, 180, 255, cv2.THRESH_BINARY)
    _, s_thresh2 = cv2.threshold(255 - s, 160, 255, cv2.THRESH_BINARY)
    _, s_thresh3 = cv2.threshold(255 - s, 140, 255, cv2.THRESH_BINARY)

    axes[1,0].imshow(s_thresh1, cmap='gray')
    axes[1,0].set_title(f'S Invertido > 180\n({cv2.countNonZero(s_thresh1)} px)')
    axes[1,0].axis('off')

    axes[1,1].imshow(s_thresh2, cmap='gray')
    axes[1,1].set_title(f'S Invertido > 160\n({cv2.countNonZero(s_thresh2)} px)')
    axes[1,1].axis('off')

    axes[1,2].imshow(s_thresh3, cmap='gray')
    axes[1,2].set_title(f'S Invertido > 140\n({cv2.countNonZero(s_thresh3)} px)')
    axes[1,2].axis('off')

    plt.tight_layout()
    plt.show()

    print("\nPresiona cualquier tecla en las ventanas para continuar...")

if __name__ == "__main__":
    print("=" * 70)
    print(" TEST DE DETECCIÓN DE TUBOS VERTICALES - ENFOQUE CANAL S")
    print("=" * 70)
    print("\nOpciones disponibles:")
    print("  1. Test completo con debug (recomendado)")
    print("  2. Análisis rápido del canal S")
    print()

    opcion = input("Selecciona opción (1/2) [1]: ").strip()

    if opcion == "2":
        quick_saturation_test()
    else:
        test_detection_debug()
