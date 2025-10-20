"""
Script para generar diagrama de flujo del proceso de cosecha interactiva.
Basado en el código real de workflow_orchestrator.py - función cosecha_interactiva()
Genera la imagen: diagrama_flujo_cosecha.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import os

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

# Crear figura
fig, ax = plt.subplots(1, 1, figsize=(11, 14))
ax.set_xlim(0, 11)
ax.set_ylim(0, 15)
ax.axis('off')

# Colores profesionales
color_inicio = '#4CAF50'      # Verde - inicio/fin
color_proceso = '#2196F3'     # Azul - proceso
color_decision = '#FF9800'    # Naranja - decisión
color_accion = '#9C27B0'      # Púrpura - acción crítica
color_texto = '#212121'       # Negro texto
color_borde = '#424242'       # Gris oscuro

def draw_box(ax, x, y, width, height, text, color, fontsize=9):
    """Dibuja caja rectangular con texto"""
    box = FancyBboxPatch((x - width/2, y - height/2), width, height,
                         boxstyle="round,pad=0.1",
                         edgecolor=color_borde, facecolor=color,
                         linewidth=2)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center', 
            fontsize=fontsize, color=color_texto, fontweight='bold',
            wrap=True)

def draw_diamond(ax, x, y, width, height, text, color, fontsize=8):
    """Dibuja rombo de decisión con texto"""
    points = [(x, y + height/2), (x + width/2, y), 
              (x, y - height/2), (x - width/2, y)]
    diamond = mpatches.Polygon(points, closed=True,
                              edgecolor=color_borde, facecolor=color,
                              linewidth=2)
    ax.add_patch(diamond)
    # Dividir texto en líneas
    lines = text.split('\n')
    for i, line in enumerate(lines):
        offset = (i - (len(lines)-1)/2) * 0.15
        ax.text(x, y + offset, line, ha='center', va='center',
                fontsize=fontsize, color=color_texto, fontweight='bold')

def draw_arrow(ax, x1, y1, x2, y2, label=''):
    """Dibuja flecha con etiqueta opcional"""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', lw=2, color=color_borde))
    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x + 0.3, mid_y, label, fontsize=8, 
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                         edgecolor=color_borde, linewidth=1))

# Posiciones X
x_center = 5.5
x_left = 2.5
x_right = 8.5

# ==================== FLUJO PRINCIPAL ====================

# Inicio
y_pos = 14
draw_box(ax, x_center, y_pos, 2.5, 0.5, 'INICIO', color_inicio, 10)

# Paso 1: Cargar mapas
y_pos -= 1
draw_arrow(ax, x_center, y_pos + 1, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3.5, 0.5, 'Cargar tubos y cintas\n(JSON)', color_proceso)

# Paso 2: Verificar homing
y_pos -= 1
draw_arrow(ax, x_center, y_pos + 1, x_center, y_pos + 0.4)
draw_diamond(ax, x_center, y_pos, 2, 0.8, '¿Robot\nhomed?', color_decision)
draw_arrow(ax, x_center - 1, y_pos, x_left, y_pos, 'NO')
draw_arrow(ax, x_center, y_pos - 0.4, x_center, y_pos - 0.9, 'SÍ')

# Sub-proceso homing (izquierda)
draw_box(ax, x_left, y_pos, 2.2, 0.4, 'Ejecutar homing', color_proceso, 8)
draw_arrow(ax, x_left, y_pos - 0.2, x_left, y_pos - 0.8)
draw_arrow(ax, x_left, y_pos - 0.8, x_center, y_pos - 0.8)

# Paso 3: Brazo a mover_lechuga
y_pos -= 1.2
draw_box(ax, x_center, y_pos, 3, 0.5, 'Brazo → mover_lechuga\n(posición segura)', color_proceso)

# Paso 4: Loop por tubos
y_pos -= 1
draw_arrow(ax, x_center, y_pos + 1, x_center, y_pos + 0.3)
draw_box(ax, x_center, y_pos, 2.5, 0.5, 'Para cada tubo', color_proceso)

# Paso 5: Loop por cintas
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 2.8, 0.5, 'Para cada cinta del tubo', color_proceso)

# Paso 6: Navegar a posición
y_pos -= 0.9
draw_arrow(ax, x_center, y_pos + 0.9, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3.2, 0.5, 'Mover a (X_cinta, Y_tubo)', color_proceso)

# Paso 7: Clasificar con IA
y_pos -= 0.9
draw_arrow(ax, x_center, y_pos + 0.9, x_center, y_pos + 0.4)
draw_diamond(ax, x_center, y_pos, 2.3, 0.8, 'Clasificar IA:\n¿Estado?', color_decision)

# Opciones de clasificación
# VACÍO (izquierda)
draw_arrow(ax, x_center - 1.15, y_pos, x_left, y_pos, 'VACÍO')
draw_box(ax, x_left, y_pos, 1.8, 0.4, 'Continuar', color_proceso, 8)
draw_arrow(ax, x_left, y_pos - 0.2, x_left, y_pos - 1.2)
draw_arrow(ax, x_left, y_pos - 1.2, x_center, y_pos - 1.2)

# NO LISTA (derecha)
draw_arrow(ax, x_center + 1.15, y_pos, x_right, y_pos, 'NO\nLISTA')
draw_box(ax, x_right, y_pos, 1.8, 0.4, 'Continuar', color_proceso, 8)
draw_arrow(ax, x_right, y_pos - 0.2, x_right, y_pos - 1.2)
draw_arrow(ax, x_right, y_pos - 1.2, x_center, y_pos - 1.2)

# LISTA (centro - continúa abajo)
draw_arrow(ax, x_center, y_pos - 0.4, x_center, y_pos - 0.8, 'LISTA')

# Paso 8: Posicionamiento fino con IA
y_pos -= 1.1
draw_box(ax, x_center, y_pos, 3.5, 0.5, 'Corrección posición\nIA (H + V)', color_accion)

# Paso 9: Recoger
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3.2, 0.5, 'Brazo → recoger_lechuga\n(extender + cerrar gripper)', color_accion)

# Paso 10: Transportar
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3, 0.5, 'Brazo → mover_lechuga\n(con planta)', color_accion)

# Paso 11: Ir a depósito
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3.2, 0.5, 'Mover a zona depósito\n(X_fin, Y_fin-250mm)', color_proceso)

# Paso 12: Depositar
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3.2, 0.5, 'Brazo → depositar_lechuga\n(inclinar + abrir gripper)', color_accion)

# Paso 13: Volver a mover_lechuga
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 3, 0.5, 'Brazo → mover_lechuga\n(sin planta)', color_accion)

# Unir con loop (flecha de retorno)
draw_arrow(ax, x_center, y_pos - 0.25, x_center, y_pos - 1.2)

# Paso 14: Más cintas?
y_pos -= 1.5
draw_diamond(ax, x_center, y_pos, 2, 0.6, '¿Más\ncintas?', color_decision, 8)
# Flecha de retorno al loop de cintas
arrow_return = mpatches.FancyArrowPatch((x_center + 1, y_pos), (x_center + 2.5, y_pos),
                                       connectionstyle="arc3,rad=1.5",
                                       arrowstyle='->', mutation_scale=20, 
                                       linewidth=2, color=color_borde)
ax.add_patch(arrow_return)
ax.text(x_center + 2.8, y_pos + 1.5, 'SÍ', fontsize=8, fontweight='bold')

# Línea que sube y conecta con loop de cintas
ax.plot([x_center + 2.5, x_center + 2.5, x_center], 
        [y_pos, y_pos + 5.5, y_pos + 5.5], 
        'k-', linewidth=2, color=color_borde)
ax.arrow(x_center + 0.1, y_pos + 5.5, -0.1, 0, head_width=0.15, 
         head_length=0.1, fc=color_borde, ec=color_borde)

# Paso 15: Retorno a origen
draw_arrow(ax, x_center, y_pos - 0.3, x_center, y_pos - 0.8, 'NO')
y_pos -= 1.1
draw_box(ax, x_center, y_pos, 2.8, 0.5, 'Volver a (0, 0)', color_proceso)

# Fin
y_pos -= 0.8
draw_arrow(ax, x_center, y_pos + 0.8, x_center, y_pos + 0.25)
draw_box(ax, x_center, y_pos, 2.5, 0.5, 'FIN', color_inicio, 10)

plt.tight_layout()
output_path = 'imagenes/diagrama_flujo_cosecha.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
plt.show()
