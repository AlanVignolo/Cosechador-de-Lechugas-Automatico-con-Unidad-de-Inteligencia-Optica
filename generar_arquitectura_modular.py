"""
Generador del diagrama de Arquitectura Modular del Sistema de IA
Muestra los 4 módulos principales y el flujo de información entre ellos
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.lines as mlines

# Configuración de la figura
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# Colores
color_modulo1 = '#4A90E2'  # Azul
color_modulo2 = '#50C878'  # Verde
color_modulo3 = '#F5A623'  # Naranja
color_modulo4 = '#9B59B6'  # Morado
color_supervisor = '#E74C3C'  # Rojo
color_flecha = '#2C3E50'   # Gris oscuro

# Función para crear módulo con estilo
def crear_modulo(x, y, ancho, alto, color, titulo, contenido, ax):
    # Caja principal con borde redondeado
    box = FancyBboxPatch((x, y), ancho, alto,
                          boxstyle="round,pad=0.1",
                          edgecolor='black',
                          facecolor=color,
                          linewidth=2.5,
                          alpha=0.85)
    ax.add_patch(box)

    # Título en negrita
    ax.text(x + ancho/2, y + alto - 0.3,
            titulo,
            fontsize=13,
            fontweight='bold',
            ha='center',
            va='top',
            color='white')

    # Contenido (líneas múltiples)
    y_text = y + alto - 0.7
    for linea in contenido:
        ax.text(x + ancho/2, y_text,
                linea,
                fontsize=9,
                ha='center',
                va='top',
                color='white')
        y_text -= 0.3

# Función para crear flecha con etiqueta
def crear_flecha(x1, y1, x2, y2, label, ax, curvatura=0):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle='->,head_width=0.4,head_length=0.6',
        color=color_flecha,
        linewidth=2.5,
        connectionstyle=f"arc3,rad={curvatura}",
        zorder=1
    )
    ax.add_patch(arrow)

    # Etiqueta en el medio de la flecha
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(mid_x, mid_y + 0.2,
                label,
                fontsize=8,
                ha='center',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', linewidth=1))

# ===== MÓDULOS =====

# Módulo 1: Sistema de Posicionamiento Visual (arriba izquierda)
crear_modulo(0.5, 7, 2.2, 2.2, color_modulo1,
             'Sistema de\nPosicionamiento Visual',
             ['Detector de', 'Marcadores', 'Corrección XY', 'Precisión <1mm'],
             ax)

# Módulo 2: Sistema de Clasificación (arriba derecha)
crear_modulo(3.3, 7, 2.2, 2.2, color_modulo2,
             'Sistema de\nClasificación',
             ['Segmentación HSV', 'Análisis morfológico', 'Lechuga/Vaso', 'Exactitud 97%'],
             ax)

# Módulo 3: Sistema de Mapeo (abajo izquierda)
crear_modulo(0.5, 3.5, 2.2, 2.2, color_modulo3,
             'Sistema de\nMapeo Autónomo',
             ['Escaneo sistemático', 'Detector de tubos', 'Registro espacial', 'Base de datos'],
             ax)

# Módulo 4: Optimización de Trayectorias (abajo derecha)
crear_modulo(3.3, 3.5, 2.2, 2.2, color_modulo4,
             'Optimización de\nTrayectorias',
             ['Algoritmo TSP', 'Patrón serpiente', 'Minimiza tiempo', 'Ruta óptima'],
             ax)

# Sistema Supervisor (centro)
crear_modulo(6.5, 5, 3, 3.5, color_supervisor,
             'SISTEMA SUPERVISOR',
             ['Raspberry Pi 4', 'Python + OpenCV', 'Coordinación módulos', 'Toma de decisiones', 'Control de flujo', 'Gestión estados'],
             ax)

# ===== FLECHAS DE FLUJO =====

# Mapeo -> Optimización
crear_flecha(1.6, 3.5, 4.4, 3.5, 'Matriz\nestaciones', ax, curvatura=-0.3)

# Optimización -> Supervisor
crear_flecha(5.5, 4.6, 6.5, 6.2, 'Ruta\nóptima', ax)

# Supervisor -> Posicionamiento
crear_flecha(6.5, 7.5, 2.7, 8.1, 'Comandos\nmovimiento', ax, curvatura=0.3)

# Posicionamiento -> Supervisor
crear_flecha(1.6, 7.5, 6.5, 7.8, 'Desviación\n(mm)', ax, curvatura=-0.3)

# Supervisor -> Clasificación
crear_flecha(8, 8, 5.5, 8.5, 'Solicitud\nclasificación', ax, curvatura=0.3)

# Clasificación -> Supervisor
crear_flecha(4.4, 7.5, 7.5, 7.2, 'Resultado\nLechuga/Vaso', ax, curvatura=-0.3)

# Supervisor -> Mapeo (inicio)
crear_flecha(7.5, 5, 1.6, 5.6, 'Iniciar\nmapeo', ax, curvatura=0.3)

# Mapeo -> Supervisor
crear_flecha(2.2, 5.6, 6.5, 6.8, 'Posiciones\ndetectadas', ax, curvatura=-0.3)

# ===== TÍTULO Y LEYENDA =====
ax.text(5, 9.6, 'ARQUITECTURA MODULAR DEL SISTEMA DE INTELIGENCIA ARTIFICIAL',
        fontsize=16, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', edgecolor='black', linewidth=2))

# Ecuación del flujo
ax.text(5, 2.5, 'Flujo de operación:',
        fontsize=11, fontweight='bold', ha='center')
ax.text(5, 2,
        'Mapeo → Posicionamiento → Clasificación → Decisión',
        fontsize=11, ha='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', edgecolor='black', linewidth=1.5))

# Notas técnicas
ax.text(5, 0.8,
        'Latencia total pipeline: 155 ms | Frecuencia operación: 6.5 Hz',
        fontsize=9, ha='center', style='italic', color='gray')

ax.text(5, 0.3,
        'Plataforma: Raspberry Pi 4 (ARM Cortex-A72, 4GB RAM) | Software: Python 3.9, OpenCV 4.5, NumPy 1.21',
        fontsize=8, ha='center', style='italic', color='gray')

plt.tight_layout()
plt.savefig('Informe/imagenes/arquitectura_modular_ia.png', dpi=300, bbox_inches='tight', facecolor='white')
print("✓ Diagrama guardado: Informe/imagenes/arquitectura_modular_ia.png")
plt.close()
