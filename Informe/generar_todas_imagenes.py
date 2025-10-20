"""
Script maestro para generar todas las imágenes del informe.
Ejecuta todos los generadores de diagramas.
"""

import os
import subprocess
import sys

# Lista de scripts a ejecutar
scripts = [
    'generar_arquitectura_regulatorio_capas.py',
    'generar_perfil_trapezoidal_velocidad.py',
    'generar_perfil_trapezoidal_triangular.py',
    'generar_sincronizacion_multieje.py'
]

print("=" * 70)
print("GENERADOR DE IMÁGENES PARA EL INFORME")
print("=" * 70)
print()

# Crear directorio de imágenes si no existe
os.makedirs('imagenes', exist_ok=True)
print("✓ Directorio 'imagenes' verificado/creado")
print()

# Ejecutar cada script
for i, script in enumerate(scripts, 1):
    print(f"[{i}/{len(scripts)}] Ejecutando {script}...")
    print("-" * 70)
    
    try:
        # Ejecutar el script
        result = subprocess.run([sys.executable, script], 
                              capture_output=True, 
                              text=True,
                              timeout=30)
        
        if result.returncode == 0:
            print(f"✓ {script} completado exitosamente")
            if result.stdout:
                print(f"  {result.stdout.strip()}")
        else:
            print(f"✗ Error en {script}")
            if result.stderr:
                print(f"  Error: {result.stderr}")
    
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout en {script} (más de 30 segundos)")
    except Exception as e:
        print(f"✗ Excepción en {script}: {e}")
    
    print()

print("=" * 70)
print("PROCESO COMPLETADO")
print("=" * 70)
print()
print("Imágenes generadas en el directorio 'imagenes/':")
imagenes_esperadas = [
    'arquitectura_regulatorio_capas.png',
    'perfil_trapezoidal_velocidad.png',
    'perfil_trapezoidal_triangular.png',
    'sincronizacion_multieje.png'
]

for img in imagenes_esperadas:
    path = os.path.join('imagenes', img)
    if os.path.exists(path):
        size = os.path.getsize(path) / 1024  # KB
        print(f"  ✓ {img} ({size:.1f} KB)")
    else:
        print(f"  ✗ {img} (no encontrada)")

print()
print("Puedes usar estas imágenes en tu informe LaTeX.")
