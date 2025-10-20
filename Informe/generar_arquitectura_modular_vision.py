"""
Script para generar diagrama de arquitectura modular del sistema de visión.
Basado en los módulos reales del Nivel_Supervisor_IA.
Genera la imagen: arquitectura_modular_vision.png
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import os

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

# Crear figura
fig, ax = plt.subplots(1, 1, figsize=(12, 10))
ax.set_xlim(0, 12)
ax.set_ylim(0, 11)
ax.axis('off')

# Colores profesionales
color_detector = '#E3F2FD'    # Azul claro
color_clasificador = '#FFF9C4' # Amarillo claro
color_correccion = '#F3E5F5'  # Púrpura claro
color_hardware = '#E8F5E9'    # Verde claro
color_borde = '#2C3E50'       # Azul oscuro
color_flecha = '#34495E'      # Gris oscuro

# ==================== MÓDULO PRINCIPAL: CENTRO ====================
x_center = 6
y_center = 6

# Cuadro grande central: Sistema de Visión
rect_main = FancyBboxPatch((2, 3), 8, 6,
                           boxstyle="round,pad=0.15",
                           edgecolor=color_borde, facecolor='white',
                           linewidth=3, zorder=1)
ax.add_patch(rect_main)

ax.text(x_center, 8.6, 'SISTEMA DE VISIÓN POR COMPUTADORA',
        ha='center', va='center', fontsize=15, fontweight='bold',
        color=color_borde)

# ==================== MÓDULO 1: DETECTOR DE TUBOS ====================
x_tubos = 3.5
y_tubos = 7

rect_tubos = FancyBboxPatch((x_tubos - 1.3, y_tubos - 0.9), 2.6, 1.8,
                           boxstyle="round,pad=0.1",
                           edgecolor=color_borde, facecolor=color_detector,
                           linewidth=2.5, zorder=2)
ax.add_patch(rect_tubos)

ax.text(x_tubos, y_tubos + 0.65, 'Detector de Tubos',
        ha='center', va='center', fontsize=12, fontweight='bold',
        color=color_borde)

# Detalles del detector de tubos
details_tubos = [
    'Algoritmo: Canny + HSV',
    'Detección: Bordes PVC',
    'Salida: config_tubos.json'
]
for i, detail in enumerate(details_tubos):
    ax.text(x_tubos, y_tubos + 0.2 - i*0.3, detail,
            ha='center', va='center', fontsize=8, color='#424242')

# Icono: Escaneo Vertical
ax.text(x_tubos, y_tubos - 0.55, '↕ Escaneo Vertical',
        ha='center', va='center', fontsize=9, style='italic',
        color='#1976D2', fontweight='bold')

# ==================== MÓDULO 2: DETECTOR DE CINTAS ====================
x_cintas = 8.5
y_cintas = 7

rect_cintas = FancyBboxPatch((x_cintas - 1.3, y_cintas - 0.9), 2.6, 1.8,
                            boxstyle="round,pad=0.1",
                            edgecolor=color_borde, facecolor=color_correccion,
                            linewidth=2.5, zorder=2)
ax.add_patch(rect_cintas)

ax.text(x_cintas, y_cintas + 0.65, 'Detector de Cintas',
        ha='center', va='center', fontsize=12, fontweight='bold',
        color=color_borde)

# Detalles del detector de cintas
details_cintas = [
    'Algoritmo: Threshold HSV-V',
    'Detección: Cintas 18mm',
    'Salida: matriz_cintas.json'
]
for i, detail in enumerate(details_cintas):
    ax.text(x_cintas, y_cintas + 0.2 - i*0.3, detail,
            ha='center', va='center', fontsize=8, color='#424242')

# Contextos de uso
ax.text(x_cintas, y_cintas - 0.55, '3 Contextos:', 
        ha='center', va='center', fontsize=8, fontweight='bold', color='#7B1FA2')
ax.text(x_cintas, y_cintas - 0.7, 'H • V • Escaneo', 
        ha='center', va='center', fontsize=7, style='italic', color='#424242')

# ==================== MÓDULO 3: CLASIFICADOR ====================
x_clasif = 6
y_clasif = 4.5

rect_clasif = FancyBboxPatch((x_clasif - 1.5, y_clasif - 0.9), 3, 1.8,
                            boxstyle="round,pad=0.1",
                            edgecolor=color_borde, facecolor=color_clasificador,
                            linewidth=2.5, zorder=2)
ax.add_patch(rect_clasif)

ax.text(x_clasif, y_clasif + 0.65, 'Clasificador Morfológico',
        ha='center', va='center', fontsize=12, fontweight='bold',
        color=color_borde)

# Detalles del clasificador
details_clasif = [
    'Segmentación: Verde HSV',
    'Morfología: Cierre + Apertura',
    'Umbral: Área estadística'
]
for i, detail in enumerate(details_clasif):
    ax.text(x_clasif, y_clasif + 0.2 - i*0.3, detail,
            ha='center', va='center', fontsize=8, color='#424242')

# Estados de salida
ax.text(x_clasif, y_clasif - 0.55, 'LISTA • NO LISTA • VACÍO',
        ha='center', va='center', fontsize=9, style='italic',
        color='#F57C00', fontweight='bold')

# ==================== CORRECCIÓN DE POSICIÓN ====================
x_corr_h = 3.5
x_corr_v = 8.5
y_corr = 4.5

# Corrección Horizontal
rect_corr_h = FancyBboxPatch((x_corr_h - 0.9, y_corr - 0.5), 1.8, 1,
                            boxstyle="round,pad=0.08",
                            edgecolor='#1976D2', facecolor='#E3F2FD',
                            linewidth=2, linestyle='--', zorder=2)
ax.add_patch(rect_corr_h)
ax.text(x_corr_h, y_corr + 0.25, 'Corrección H',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#1976D2')
ax.text(x_corr_h, y_corr - 0.05, 'Centroide', 
        ha='center', va='center', fontsize=7, style='italic', color='#424242')
ax.text(x_corr_h, y_corr - 0.25, 'cinta vertical',
        ha='center', va='center', fontsize=7, style='italic', color='#424242')

# Corrección Vertical
rect_corr_v = FancyBboxPatch((x_corr_v - 0.9, y_corr - 0.5), 1.8, 1,
                            boxstyle="round,pad=0.08",
                            edgecolor='#7B1FA2', facecolor='#F3E5F5',
                            linewidth=2, linestyle='--', zorder=2)
ax.add_patch(rect_corr_v)
ax.text(x_corr_v, y_corr + 0.25, 'Corrección V',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#7B1FA2')
ax.text(x_corr_v, y_corr - 0.05, 'Arista base',
        ha='center', va='center', fontsize=7, style='italic', color='#424242')
ax.text(x_corr_v, y_corr - 0.25, 'cinta horizontal',
        ha='center', va='center', fontsize=7, style='italic', color='#424242')

# ==================== HARDWARE/PLATAFORMA ====================
y_hw = 2.2

rect_hw = FancyBboxPatch((2.5, y_hw - 0.6), 7, 1.2,
                        boxstyle="round,pad=0.1",
                        edgecolor=color_borde, facecolor=color_hardware,
                        linewidth=2.5, zorder=2)
ax.add_patch(rect_hw)

ax.text(x_center, y_hw + 0.35, 'PLATAFORMA DE HARDWARE',
        ha='center', va='center', fontsize=11, fontweight='bold',
        color=color_borde)

# Detalles de hardware
hw_details = [
    'Raspberry Pi 5 • ARM Cortex-A76 @ 2.4GHz • 8GB RAM',
    'OpenCV 4.x • NumPy • PySerial • V4L2'
]
for i, detail in enumerate(hw_details):
    ax.text(x_center, y_hw - 0.05 - i*0.25, detail,
            ha='center', va='center', fontsize=8, color='#424242')

# ==================== ENTRADA/SALIDA ====================
# Entrada: Cámara USB
x_cam = 1
y_cam = 6
circle_cam = Circle((x_cam, y_cam), 0.35, 
                    edgecolor=color_borde, facecolor='#FFEB3B',
                    linewidth=2, zorder=3)
ax.add_patch(circle_cam)
ax.text(x_cam, y_cam + 0.05, '📷', ha='center', va='center', fontsize=20)
ax.text(x_cam, y_cam - 0.6, 'Cámara USB', ha='center', va='center',
        fontsize=9, fontweight='bold', color=color_borde)

# Salida: Datos JSON
x_json = 11
y_json = 6
rect_json = FancyBboxPatch((x_json - 0.5, y_json - 0.35), 1, 0.7,
                          boxstyle="round,pad=0.08",
                          edgecolor=color_borde, facecolor='#4CAF50',
                          linewidth=2, zorder=3)
ax.add_patch(rect_json)
ax.text(x_json, y_json + 0.05, 'JSON', ha='center', va='center',
        fontsize=11, fontweight='bold', color='white')
ax.text(x_json, y_json - 0.6, 'Posiciones\nDetecciones', ha='center', va='center',
        fontsize=8, fontweight='bold', color=color_borde)

# ==================== FLECHAS DE FLUJO ====================
arrow_style = dict(arrowstyle='->', lw=2.5, color=color_flecha, 
                  connectionstyle="arc3,rad=0.2")

# Cámara → Detectores
ax.annotate('', xy=(2.2, y_tubos), xytext=(x_cam + 0.35, y_cam),
            arrowprops=arrow_style)
ax.annotate('', xy=(7.2, y_cintas), xytext=(x_cam + 0.35, y_cam),
            arrowprops=dict(arrowstyle='->', lw=2.5, color=color_flecha,
                          connectionstyle="arc3,rad=0.3"))

# Cámara → Clasificador
ax.annotate('', xy=(x_clasif - 1.2, y_clasif + 0.5), xytext=(x_cam + 0.35, y_cam - 0.3),
            arrowprops=dict(arrowstyle='->', lw=2.5, color=color_flecha,
                          connectionstyle="arc3,rad=-0.3"))

# Detectores → JSON
ax.annotate('', xy=(x_json - 0.5, y_json + 0.2), xytext=(x_tubos + 1.3, y_tubos),
            arrowprops=dict(arrowstyle='->', lw=2, color='#1976D2',
                          connectionstyle="arc3,rad=-0.3"))
ax.annotate('', xy=(x_json - 0.5, y_json - 0.2), xytext=(x_cintas + 1.3, y_cintas),
            arrowprops=dict(arrowstyle='->', lw=2, color='#7B1FA2',
                          connectionstyle="arc3,rad=0.3"))

# Clasificador → JSON
ax.annotate('', xy=(x_json - 0.5, y_json), xytext=(x_clasif + 1.5, y_clasif),
            arrowprops=dict(arrowstyle='->', lw=2, color='#F57C00'))

# Hardware soporta todo (líneas punteadas hacia arriba)
for x_pos in [x_tubos, x_clasif, x_cintas]:
    ax.plot([x_pos, x_pos], [y_hw + 0.6, 3.2], 
            color=color_borde, linestyle=':', linewidth=1.5, alpha=0.5)

# Etiquetas de flujo
ax.text(1.5, 6.8, 'Imagen', fontsize=8, color=color_flecha, 
        style='italic', rotation=15)
ax.text(9.8, 6.5, 'Datos', fontsize=8, color=color_flecha,
        style='italic')

plt.tight_layout()
output_path = 'imagenes/arquitectura_modular_vision.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
plt.show()
