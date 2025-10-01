"""
Test simple para verificar import del escáner vertical automático
"""
import sys
import os

print("="*60)
print("TEST DE IMPORT - Escáner Vertical Automático")
print("="*60)

# Agregar paths necesarios
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Nivel_Supervisor', 'config'))

print("\n1. Probando imports básicos...")
try:
    import cv2
    print("   ✓ cv2 OK")
except Exception as e:
    print(f"   ✗ cv2 ERROR: {e}")

try:
    import numpy as np
    print("   ✓ numpy OK")
except Exception as e:
    print(f"   ✗ numpy ERROR: {e}")

try:
    from camera_manager import get_camera_manager
    print("   ✓ camera_manager OK")
except Exception as e:
    print(f"   ✗ camera_manager ERROR: {e}")

try:
    from config.robot_config import RobotConfig
    print("   ✓ RobotConfig OK")
except Exception as e:
    print(f"   ✗ RobotConfig ERROR: {e}")

print("\n2. Probando import del detector...")
try:
    from detector_canny_s_combinado import detectar_lineas_tubo
    print("   ✓ detector_canny_s_combinado OK")
except Exception as e:
    print(f"   ✗ detector_canny_s_combinado ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n3. Probando import del escáner vertical...")
try:
    from escaner_vertical import scan_vertical_with_flags
    print("   ✓ escaner_vertical OK")
    print(f"   ✓ Función scan_vertical_with_flags importada: {scan_vertical_with_flags}")
except Exception as e:
    print(f"   ✗ escaner_vertical ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test completado")
print("="*60)
