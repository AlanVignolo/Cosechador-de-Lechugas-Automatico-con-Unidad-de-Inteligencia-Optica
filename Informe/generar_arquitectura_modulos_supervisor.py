"""
Script para generar diagrama de arquitectura modular del nivel supervisor.
Basado en el código real del sistema CLAUDIO.
Genera la imagen: arquitectura_modulos_supervisor.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

# Crear figura más compacta
fig, ax = plt.subplots(1, 1, figsize=(10, 8))
ax.set_xlim(0, 10)
ax.set_ylim(0, 8)
ax.axis('off')

# Colores profesionales para tesis
color_procesos = '#E3F2FD'     # Azul muy claro
color_robot = '#FFF9C4'        # Amarillo claro
color_control = '#F3E5F5'      # Púrpura claro
color_hardware = '#E8F5E9'     # Verde claro
color_borde = '#2C3E50'        # Azul oscuro
color_flecha = '#34495E'       # Gris oscuro

# Dimensiones base - más compactas
layer_width = 9
layer_height = 1.3
x_start = 0.5
y_spacing = 0.4

# ==================== CAPA 4: PROCESOS (Top) ====================
y_procesos = 6.4
rect_procesos = FancyBboxPatch((x_start, y_procesos), layer_width, layer_height,
                               boxstyle="square,pad=0",
                               edgecolor=color_borde, facecolor=color_procesos,
                               linewidth=2.5, zorder=2)
ax.add_patch(rect_procesos)

# Título de capa
ax.text(x_start + layer_width/2, y_procesos + layer_height - 0.2,
        'Capa de Procesos',
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Descripción de procesos
ax.text(x_start + layer_width/2, y_procesos + layer_height/2 - 0.15,
        'homing • calibración • mapeo • cosecha',
        ha='center', va='center', fontsize=13, fontweight='bold',
        color=color_borde)

# ==================== CAPA 3: ROBOT ====================
y_robot = y_procesos - layer_height - y_spacing
rect_robot = FancyBboxPatch((x_start, y_robot), layer_width, layer_height,
                           boxstyle="square,pad=0",
                           edgecolor=color_borde, facecolor=color_robot,
                           linewidth=2.5, zorder=2)
ax.add_patch(rect_robot)

# Título de capa
ax.text(x_start + layer_width/2, y_robot + layer_height - 0.2,
        'Capa de Robot',
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulos de robot (3 módulos lado a lado) - centrados
robot_modules = ['Control de robot serie', 'Estados del robot', 'Generación de trayectorias']
module_width = layer_width / 3
for i, name in enumerate(robot_modules):
    x_pos = x_start + (i + 0.5) * module_width
    ax.text(x_pos, y_robot + layer_height/2 - 0.1, name,
            ha='center', va='center', fontsize=13, fontweight='bold',
            color=color_borde)

# ==================== CAPA 2: CONTROL ====================
y_control = y_robot - layer_height - y_spacing
rect_control = FancyBboxPatch((x_start, y_control), layer_width, layer_height,
                             boxstyle="square,pad=0",
                             edgecolor=color_borde, facecolor=color_control,
                             linewidth=2.5, zorder=2)
ax.add_patch(rect_control)

# Título de capa
ax.text(x_start + layer_width/2, y_control + layer_height - 0.2,
        'Capa de Control',
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulos de control (2 módulos) - centrados
control_modules = ['Controlador del robot', 'Gestor de cámara']
module_width = layer_width / 2
for i, name in enumerate(control_modules):
    x_pos = x_start + (i + 0.5) * module_width
    ax.text(x_pos, y_control + layer_height/2 - 0.1, name,
            ha='center', va='center', fontsize=13, fontweight='bold',
            color=color_borde)

# ==================== CAPA 1: HARDWARE ====================
y_hardware = y_control - layer_height - y_spacing
rect_hardware = FancyBboxPatch((x_start, y_hardware), layer_width, layer_height,
                              boxstyle="square,pad=0",
                              edgecolor=color_borde, facecolor=color_hardware,
                              linewidth=2.5, zorder=2)
ax.add_patch(rect_hardware)

# Título de capa
ax.text(x_start + layer_width/2, y_hardware + layer_height - 0.2,
        'Capa de Hardware',
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulos de hardware (2 módulos) - centrados
hardware_modules = ['Gestor de comunicación UART', 'Gestor de comandos']
module_width = layer_width / 2
for i, name in enumerate(hardware_modules):
    x_pos = x_start + (i + 0.5) * module_width
    ax.text(x_pos, y_hardware + layer_height/2 - 0.1, name,
            ha='center', va='center', fontsize=13, fontweight='bold',
            color=color_borde)

# ==================== NIVEL REGULATORIO (firmware) ====================
y_firmware = y_hardware - layer_height - y_spacing
rect_firmware = FancyBboxPatch((x_start, y_firmware), layer_width, layer_height,
                              boxstyle="square,pad=0",
                              edgecolor=color_borde, facecolor='#FAFAFA',
                              linewidth=2, linestyle='--', zorder=2)
ax.add_patch(rect_firmware)
ax.text(x_start + layer_width/2, y_firmware + layer_height/2,
        'Nivel Regulatorio',
        ha='center', va='center', fontsize=14, fontweight='bold',
        color='#666666')

# ==================== FLECHAS DE FLUJO ====================
# Estilo de flechas
arrow_style_bi = dict(arrowstyle='<->', lw=2.5, color=color_flecha, connectionstyle="arc3,rad=0")

x_arrow = x_start + layer_width/2

# Procesos -> Robot
ax.annotate('', xy=(x_arrow, y_robot + layer_height),
            xytext=(x_arrow, y_procesos),
            arrowprops=arrow_style_bi)

# Robot -> Control
ax.annotate('', xy=(x_arrow, y_control + layer_height),
            xytext=(x_arrow, y_robot),
            arrowprops=arrow_style_bi)

# Control -> Hardware
ax.annotate('', xy=(x_arrow, y_hardware + layer_height),
            xytext=(x_arrow, y_control),
            arrowprops=arrow_style_bi)

# Hardware -> Firmware
ax.annotate('', xy=(x_arrow, y_firmware + layer_height),
            xytext=(x_arrow, y_hardware),
            arrowprops=arrow_style_bi)

plt.tight_layout()
output_path = 'imagenes/arquitectura_modulos_supervisor.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white', pad_inches=0.1)
print(f"Diagrama generado exitosamente: {output_path}")
plt.close()
