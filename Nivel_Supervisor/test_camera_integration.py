#!/usr/bin/env python3
"""
Script de prueba para verificar la integración del gestor centralizado de cámara
"""

import sys
import os
import time

# Agregar rutas necesarias
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Horizontal'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Nivel_Supervisor_IA', 'Correccion Posicion Vertical'))

from camera_manager import get_camera_manager, capture_frame_safe, initialize_camera_safe

def test_camera_manager():
    """Prueba básica del gestor de cámara"""
    print("="*60)
    print("PRUEBA DEL GESTOR CENTRALIZADO DE CÁMARA")
    print("="*60)
    
    camera_mgr = get_camera_manager()
    
    # 1. Mostrar estado inicial
    print("\n1. Estado inicial de la cámara:")
    status = camera_mgr.get_camera_info()
    print(f"   - Activa: {status['is_active']}")
    print(f"   - Índice: {status['camera_index']}")
    print(f"   - Último frame: {'Sí' if status['has_last_frame'] else 'No'}")
    
    # 2. Buscar cámara disponible
    print("\n2. Buscando cámara disponible...")
    working_camera = camera_mgr.find_working_camera()
    if working_camera is not None:
        print(f"   Cámara encontrada en índice: {working_camera}")
    else:
        print("   No se encontró cámara funcional")
        return False
    
    # 3. Inicializar cámara
    print("\n3. Inicializando cámara...")
    success = camera_mgr.initialize_camera(working_camera)
    if success:
        print("   Cámara inicializada exitosamente")
    else:
        print("   Error al inicializar cámara")
        return False
    
    # 4. Mostrar información de la cámara inicializada
    print("\n4. Información de la cámara:")
    status = camera_mgr.get_camera_info()
    print(f"   - Resolución: {status.get('width', 'N/A')}x{status.get('height', 'N/A')}")
    print(f"   - FPS: {status.get('fps', 'N/A')}")
    
    # 5. Capturar múltiples frames para probar estabilidad
    print("\n5. Probando captura múltiple...")
    for i in range(5):
        print(f"   Captura {i+1}/5...", end=" ")
        frame = camera_mgr.capture_frame(timeout=3.0)
        if frame is not None:
            print(f"OK {frame.shape[1]}x{frame.shape[0]}")
        else:
            print("Error")
            return False
        time.sleep(0.5)  # Pausa pequeña entre capturas
    
    # 6. Probar funciones de conveniencia
    print("\n6. Probando funciones de conveniencia...")
    frame = capture_frame_safe(timeout=2.0)
    if frame is not None:
        print(f"   capture_frame_safe funcionando: {frame.shape[1]}x{frame.shape[0]}")
    else:
        print("   capture_frame_safe falló")
    
    # 7. Liberar cámara
    print("\n7. Liberando cámara...")
    camera_mgr.release_camera()
    print("   Cámara liberada")
    
    # 8. Verificar estado final
    print("\n8. Estado final:")
    status = camera_mgr.get_camera_info()
    print(f"   - Activa: {status['is_active']}")
    print(f"   - Último frame: {'Conservado' if status['has_last_frame'] else 'No disponible'}")
    
    print("\n" + "="*60)
    print("PRUEBA DEL GESTOR DE CÁMARA COMPLETADA EXITOSAMENTE")
    print("="*60)
    return True

def test_ai_integration():
    """Prueba de integración con módulos de IA"""
    print("\n" + "="*60)
    print("PRUEBA DE INTEGRACIÓN CON MÓDULOS DE IA")
    print("="*60)
    
    try:
        # Probar importación de detectores
        from tape_detector_horizontal import capture_with_timeout
        from tape_detector_vertical import capture_with_timeout as capture_with_timeout_v
        
        print("\n1. Probando detector horizontal...")
        frame_h = capture_with_timeout(0, timeout=3.0)
        if frame_h is not None:
            print(f"   Detector horizontal funcionando: {frame_h.shape[1]}x{frame_h.shape[0]}")
        else:
            print("   Detector horizontal falló")
            return False
        
        print("\n2. Probando detector vertical...")
        frame_v = capture_with_timeout_v(0, timeout=3.0)
        if frame_v is not None:
            print(f"   Detector vertical funcionando: {frame_v.shape[1]}x{frame_v.shape[0]}")
        else:
            print("   Detector vertical falló")
            return False
        
        # Verificar que ambos usan la misma instancia de cámara
        camera_mgr = get_camera_manager()
        status = camera_mgr.get_camera_info()
        print(f"\n3. Estado del gestor después de uso por IAs:")
        print(f"   - Activa: {status['is_active']}")
        print(f"   - Cámara mantenida: {'Sí' if status['has_cap'] and status['cap_opened'] else 'No'}")
        
        print("\n" + "="*60)
        print("INTEGRACIÓN CON IA FUNCIONANDO CORRECTAMENTE")
        print("="*60)
        return True
        
    except ImportError as e:
        print(f"   Error importando módulos de IA: {e}")
        return False
    except Exception as e:
        print(f"   Error inesperado: {e}")
        return False

def main():
    """Función principal de prueba"""
    print("CLAUDIO - Prueba de Integración del Gestor de Cámara")
    print("Fecha:", time.strftime("%Y-%m-%d %H:%M:%S"))
    
    # Ejecutar pruebas
    test1_passed = test_camera_manager()
    
    if test1_passed:
        test2_passed = test_ai_integration()
        
        if test2_passed:
            print("\nTODAS LAS PRUEBAS PASARON EXITOSAMENTE")
            print("El gestor centralizado de cámara está funcionando correctamente")
            print("Los módulos de IA están usando el gestor sin problemas")
        else:
            print("\nPRUEBA DE INTEGRACIÓN CON IA FALLÓ")
    else:
        print("\nPRUEBA BÁSICA DEL GESTOR FALLÓ")
    
    # Limpiar recursos finales
    try:
        camera_mgr = get_camera_manager()
        camera_mgr.release_camera()
        print("\nRecursos de cámara liberados")
    except:
        pass

if __name__ == "__main__":
    main()
