"""
Script para generar diagrama de arquitectura en capas del nivel regulatorio.
Genera la imagen: arquitectura_regulatorio_capas.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.lines as mlines
import os

# Configuración de la figura con estilo profesional
fig, ax = plt.subplots(figsize=(10, 9))
ax.set_xlim(0, 10)
ax.set_ylim(0, 11)
ax.axis('off')

# Colores profesionales para tesis (escala de grises y azul oscuro)
color_aplicacion = '#E8EEF7'  # Azul muy claro
color_control = '#F5F5F5'     # Gris muy claro
color_drivers = '#FAFAFA'     # Gris casi blanco
color_hardware = '#FFFFFF'    # Blanco
color_borde = '#2C3E50'       # Azul oscuro profesional

# Dimensiones y posiciones - rectángulos 30% más pequeños
layer_height = 1.26  # 1.8 * 0.7
layer_width = 5.25   # 7.5 * 0.7
x_start = 2.375
y_start = 1.5

# ==================== CAPA 3: CAPA DE APLICACIÓN ====================
y_app = y_start + 2 * (layer_height + 0.5)
rect_app = FancyBboxPatch((x_start, y_app), layer_width, layer_height,
                          boxstyle="square,pad=0", 
                          edgecolor=color_borde, facecolor=color_aplicacion, 
                          linewidth=2, zorder=2)
ax.add_patch(rect_app)

# Título de la capa - 30% más grande
ax.text(x_start + layer_width/2, y_app + layer_height - 0.15, 
        'Capa de Aplicación',
        ha='center', va='center', fontsize=15.6, fontweight='bold',
        color='#000000')

# Módulos de la capa de aplicación - UNO DEBAJO DEL OTRO
modules_app = [
    'Protocolo UART',
    'Analizador sintáctico',
    'Gestor de comandos'
]
x_mod = x_start + layer_width/2 - 1.5  # Centrado
y_spacing = 0.25
for i, module in enumerate(modules_app):
    y_mod = y_app + 0.15 + i * y_spacing
    box = FancyBboxPatch((x_mod, y_mod), 3.0, 0.20,
                         boxstyle="square,pad=0",
                         edgecolor=color_borde, facecolor='white',
                         linewidth=1.2)
    ax.add_patch(box)
    ax.text(x_mod + 1.5, y_mod + 0.10, module,
            ha='center', va='center', fontsize=10, color='#000000')

# ==================== CAPA 2: CAPA DE CONTROL DE MOVIMIENTO ====================
y_control = y_start + (layer_height + 0.5)
rect_control = FancyBboxPatch((x_start, y_control), layer_width, layer_height,
                              boxstyle="square,pad=0",
                              edgecolor=color_borde, facecolor=color_control,
                              linewidth=2, zorder=2)
ax.add_patch(rect_control)

# Título de la capa - 30% más grande
ax.text(x_start + layer_width/2, y_control + layer_height - 0.15,
        'Capa de Control de Movimiento',
        ha='center', va='center', fontsize=15.6, fontweight='bold',
        color='#000000')

# Módulos de la capa de control - UNO DEBAJO DEL OTRO
modules_control = [
    'Perfiles de velocidad',
    'Coordinación ejes',
    'Generación trayectorias'
]
x_mod = x_start + layer_width/2 - 1.5
for i, module in enumerate(modules_control):
    y_mod_ctrl = y_control + 0.15 + i * y_spacing
    box = FancyBboxPatch((x_mod, y_mod_ctrl), 3.0, 0.20,
                         boxstyle="square,pad=0",
                         edgecolor=color_borde, facecolor='white',
                         linewidth=1.2)
    ax.add_patch(box)
    ax.text(x_mod + 1.5, y_mod_ctrl + 0.10, module,
            ha='center', va='center', fontsize=10, color='#000000')

# ==================== CAPA 1: CAPA DE CONTROLADORES DE HARDWARE ====================
y_drivers = y_start
rect_drivers = FancyBboxPatch((x_start, y_drivers), layer_width, layer_height,
                              boxstyle="square,pad=0",
                              edgecolor=color_borde, facecolor=color_drivers,
                              linewidth=2, zorder=2)
ax.add_patch(rect_drivers)

# Título de la capa - 30% más grande
ax.text(x_start + layer_width/2, y_drivers + layer_height - 0.15,
        'Capa de Controladores de Hardware',
        ha='center', va='center', fontsize=15.6, fontweight='bold',
        color='#000000')

# Módulos de la capa de drivers - UNO DEBAJO DEL OTRO
modules_drivers = [
    'Timer/PWM',
    'UART Driver',
    'GPIO Control'
]
x_mod = x_start + layer_width/2 - 1.5
for i, module in enumerate(modules_drivers):
    y_mod_drv = y_drivers + 0.15 + i * y_spacing
    box = FancyBboxPatch((x_mod, y_mod_drv), 3.0, 0.20,
                         boxstyle="square,pad=0",
                         edgecolor=color_borde, facecolor='white',
                         linewidth=1.2)
    ax.add_patch(box)
    ax.text(x_mod + 1.5, y_mod_drv + 0.10, module,
            ha='center', va='center', fontsize=10, color='#000000')

# ==================== HARDWARE FÍSICO ====================
y_hw = y_drivers - 0.9
rect_hw = FancyBboxPatch((x_start, y_hw), layer_width, 0.6,
                         boxstyle="square,pad=0",
                         edgecolor=color_borde, facecolor=color_hardware,
                         linewidth=1.5, linestyle='--', zorder=2)
ax.add_patch(rect_hw)
ax.text(x_start + layer_width/2, y_hw + 0.3,
        'Hardware Físico',
        ha='center', va='center', fontsize=10,
        color='#000000')

# ==================== FLECHAS DE FLUJO - TODAS DEL MISMO TAMAÑO ====================
# Flechas entre capas (bidireccionales)
x_arrow = x_start + layer_width/2
arrow_style = dict(arrowstyle='<->', lw=2, color='#000000')

# Aplicación <-> Control
ax.annotate('', xy=(x_arrow, y_control + layer_height), 
            xytext=(x_arrow, y_app),
            arrowprops=arrow_style)

# Control <-> Drivers
ax.annotate('', xy=(x_arrow, y_drivers + layer_height), 
            xytext=(x_arrow, y_control),
            arrowprops=arrow_style)

# Drivers <-> Hardware (misma longitud que las demás)
ax.annotate('', xy=(x_arrow, y_hw + 0.5), 
            xytext=(x_arrow, y_drivers),
            arrowprops=arrow_style)

# ==================== ENTRADA/SALIDA EXTERNA ====================
# Entrada desde supervisor (arriba)
x_input = x_start - 0.7
y_input = y_app + layer_height/2
ax.text(x_input, y_input, 'Nivel\nSupervisor',
        ha='center', va='center', fontsize=9,
        bbox=dict(boxstyle='square,pad=0.25', facecolor='white', 
                  edgecolor=color_borde, linewidth=1.2))
ax.annotate('', xy=(x_start, y_input), xytext=(x_input + 0.35, y_input),
            arrowprops=dict(arrowstyle='->', lw=1.8, color='#000000'))

# Salida hacia supervisor (respuestas)
x_output = x_start + layer_width + 0.7
ax.text(x_output, y_input, 'Respuestas\ny Eventos',
        ha='center', va='center', fontsize=9,
        bbox=dict(boxstyle='square,pad=0.25', facecolor='white',
                  edgecolor=color_borde, linewidth=1.2))
ax.annotate('', xy=(x_output - 0.35, y_input), xytext=(x_start + layer_width, y_input),
            arrowprops=dict(arrowstyle='->', lw=1.8, color='#000000'))

# Sin título principal (se quita según solicitud)

# Ajustar límites finales
ax.set_xlim(-0.3, 10.3)
ax.set_ylim(y_hw - 0.5, y_app + layer_height + 1)

# Guardar figura
plt.tight_layout()
output_path = 'imagenes/arquitectura_regulatorio_capas.png'

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
plt.show()
