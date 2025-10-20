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

# Crear figura
fig, ax = plt.subplots(1, 1, figsize=(12, 10))
ax.set_xlim(0, 12)
ax.set_ylim(0, 11)
ax.axis('off')

# Colores profesionales para tesis
color_procesos = '#E3F2FD'     # Azul muy claro
color_robot = '#FFF9C4'        # Amarillo claro
color_control = '#F3E5F5'      # Púrpura claro
color_hardware = '#E8F5E9'     # Verde claro
color_borde = '#2C3E50'        # Azul oscuro
color_flecha = '#34495E'       # Gris oscuro

# Dimensiones base
layer_width = 10
layer_height = 1.6
x_start = 1
y_spacing = 0.4

# ==================== CAPA 4: PROCESOS (Top) ====================
y_procesos = 8.5
rect_procesos = FancyBboxPatch((x_start, y_procesos), layer_width, layer_height,
                               boxstyle="square,pad=0", 
                               edgecolor=color_borde, facecolor=color_procesos, 
                               linewidth=2.5, zorder=2)
ax.add_patch(rect_procesos)

# Título de capa
ax.text(x_start + layer_width/2, y_procesos + layer_height - 0.3, 
        'Capa de Procesos', 
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulo único centrado
ax.text(x_start + layer_width/2, y_procesos + 0.5, 
        'workflow_orchestrator.py', 
        ha='center', va='center', fontsize=11,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                 edgecolor=color_borde, linewidth=1.5))

# Descripción de procesos
processes_text = 'homing • calibración • mapeo • cosecha'
ax.text(x_start + layer_width/2, y_procesos + 0.15, processes_text,
        ha='center', va='center', fontsize=8, style='italic', color='#555555')

# ==================== CAPA 3: ROBOT ====================
y_robot = y_procesos - layer_height - y_spacing
rect_robot = FancyBboxPatch((x_start, y_robot), layer_width, layer_height,
                           boxstyle="square,pad=0", 
                           edgecolor=color_borde, facecolor=color_robot, 
                           linewidth=2.5, zorder=2)
ax.add_patch(rect_robot)

# Título de capa
ax.text(x_start + layer_width/2, y_robot + layer_height - 0.3, 
        'Capa de Robot', 
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulos de robot (3 módulos lado a lado)
robot_modules = [
    ('ArmController', 'arm_controller.py'),
    ('ArmStates', 'arm_states.py'),
    ('Trajectories', 'trajectories.py')
]
x_module_start = x_start + 0.8
module_spacing = 3.0
for i, (name, file) in enumerate(robot_modules):
    x_pos = x_module_start + i * module_spacing
    ax.text(x_pos, y_robot + 0.65, name, 
            ha='center', va='center', fontsize=10, fontweight='bold',
            color=color_borde)
    ax.text(x_pos, y_robot + 0.35, file, 
            ha='center', va='center', fontsize=8, style='italic',
            color='#666666')

# ==================== CAPA 2: CONTROL ====================
y_control = y_robot - layer_height - y_spacing
rect_control = FancyBboxPatch((x_start, y_control), layer_width, layer_height,
                             boxstyle="square,pad=0", 
                             edgecolor=color_borde, facecolor=color_control, 
                             linewidth=2.5, zorder=2)
ax.add_patch(rect_control)

# Título de capa
ax.text(x_start + layer_width/2, y_control + layer_height - 0.3, 
        'Capa de Control', 
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulos de control (2 módulos principales)
control_modules = [
    ('RobotController', 'robot_controller.py', 'Tracking posición • Callbacks • Persistencia'),
    ('CameraManager', 'camera_manager.py', 'Singleton • Acceso exclusivo • V4L2')
]
x_ctrl_start = x_start + 1.5
ctrl_spacing = 4.5
for i, (name, file, desc) in enumerate(control_modules):
    x_pos = x_ctrl_start + i * ctrl_spacing
    ax.text(x_pos, y_control + 0.85, name, 
            ha='center', va='center', fontsize=10, fontweight='bold',
            color=color_borde)
    ax.text(x_pos, y_control + 0.58, file, 
            ha='center', va='center', fontsize=8, style='italic',
            color='#666666')
    ax.text(x_pos, y_control + 0.25, desc, 
            ha='center', va='center', fontsize=7, color='#888888')

# ==================== CAPA 1: HARDWARE ====================
y_hardware = y_control - layer_height - y_spacing
rect_hardware = FancyBboxPatch((x_start, y_hardware), layer_width, layer_height,
                              boxstyle="square,pad=0", 
                              edgecolor=color_borde, facecolor=color_hardware, 
                              linewidth=2.5, zorder=2)
ax.add_patch(rect_hardware)

# Título de capa
ax.text(x_start + layer_width/2, y_hardware + layer_height - 0.3, 
        'Capa de Hardware', 
        ha='center', va='center', fontsize=14, fontweight='bold',
        color=color_borde)

# Módulos de hardware (2 módulos principales)
hardware_modules = [
    ('UARTManager', 'uart_manager.py', 'Serial USB • Callbacks • Async'),
    ('CommandManager', 'command_manager.py', 'Comandos estructurados • Protocolo')
]
x_hw_start = x_start + 1.5
hw_spacing = 4.5
for i, (name, file, desc) in enumerate(hardware_modules):
    x_pos = x_hw_start + i * hw_spacing
    ax.text(x_pos, y_hardware + 0.85, name, 
            ha='center', va='center', fontsize=10, fontweight='bold',
            color=color_borde)
    ax.text(x_pos, y_hardware + 0.58, file, 
            ha='center', va='center', fontsize=8, style='italic',
            color='#666666')
    ax.text(x_pos, y_hardware + 0.25, desc, 
            ha='center', va='center', fontsize=7, color='#888888')

# ==================== NIVEL REGULATORIO (firmware) ====================
y_firmware = y_hardware - 1.2
rect_firmware = FancyBboxPatch((x_start, y_firmware), layer_width, 0.8,
                              boxstyle="square,pad=0", 
                              edgecolor=color_borde, facecolor='#FAFAFA', 
                              linewidth=2, linestyle='--', zorder=2)
ax.add_patch(rect_firmware)
ax.text(x_start + layer_width/2, y_firmware + 0.4, 
        'Nivel Regulatorio (Firmware C - ATmega2560)', 
        ha='center', va='center', fontsize=12, fontweight='bold',
        color='#666666')

# ==================== SISTEMA IA/VISION ====================
y_ia = y_firmware - 1.0
rect_ia = FancyBboxPatch((x_start, y_ia), layer_width, 0.8,
                        boxstyle="square,pad=0", 
                        edgecolor=color_borde, facecolor='#FFF3E0', 
                        linewidth=2, linestyle=':', zorder=2)
ax.add_patch(rect_ia)
ax.text(x_start + layer_width/2, y_ia + 0.4, 
        'Sistema de IA y Visión por Computadora (OpenCV)', 
        ha='center', va='center', fontsize=12, fontweight='bold',
        color='#E65100')

# ==================== FLECHAS DE FLUJO ====================
# Estilo de flechas
arrow_style = dict(arrowstyle='->', lw=2.5, color=color_flecha, connectionstyle="arc3,rad=0")
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
ax.annotate('', xy=(x_arrow, y_firmware + 0.8), 
            xytext=(x_arrow, y_hardware),
            arrowprops=arrow_style_bi)
ax.text(x_arrow + 0.3, (y_hardware + y_firmware + 0.8)/2, 'UART\n115200', 
        fontsize=8, color='#666666', ha='left', va='center')

# Procesos <-> IA (flecha lateral)
x_ia_arrow = x_start + layer_width + 0.5
ax.annotate('', xy=(x_ia_arrow, y_ia + 0.4), 
            xytext=(x_ia_arrow, y_procesos + 0.5),
            arrowprops=dict(arrowstyle='<->', lw=2, color='#E65100', 
                          connectionstyle="arc3,rad=.3"))
ax.text(x_ia_arrow + 0.2, (y_procesos + y_ia)/2, 'Invocación\nDirecta', 
        fontsize=8, color='#E65100', ha='left', va='center')

plt.tight_layout()
output_path = 'imagenes/arquitectura_modulos_supervisor.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
plt.show()
