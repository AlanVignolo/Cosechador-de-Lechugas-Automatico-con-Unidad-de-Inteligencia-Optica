"""
Generador del diagrama de Patrón de Barrido Serpiente
Muestra el recorrido del robot por las estaciones en patrón serpiente
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
import numpy as np

# Configuración de la figura
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(-1, 13)
ax.set_ylim(-1, 8)
ax.axis('off')

# Parámetros del sistema
filas = 6
columnas = 12
sep_x = 1.0  # Separación horizontal (150 mm normalizados)
sep_y = 1.0  # Separación vertical (200 mm normalizados)

# Colores
color_estacion_vacia = '#BDC3C7'  # Gris claro
color_estacion_lechuga = '#27AE60'  # Verde
color_trayectoria = '#E74C3C'  # Rojo
color_inicio = '#3498DB'  # Azul
color_flecha = '#2C3E50'  # Gris oscuro

# ===== TÍTULO =====
ax.text(6, 7.5, 'PATRÓN DE BARRIDO TIPO SERPIENTE',
        fontsize=16, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', edgecolor='black', linewidth=2))

ax.text(6, 7.1, 'Estrategia de exploración sistemática del entorno de cultivo',
        fontsize=11, ha='center', style='italic', color='gray')

# ===== GENERAR GRID DE ESTACIONES =====
# Patrón aleatorio de lechugas (60% probabilidad)
np.random.seed(42)
tiene_lechuga = np.random.random((filas, columnas)) > 0.4

# Dibujar estaciones
for fila in range(filas):
    for col in range(columnas):
        x = col * sep_x
        y = fila * sep_y

        # Color según estado
        if tiene_lechuga[fila, col]:
            color = color_estacion_lechuga
            marker = 'o'
            markersize = 100
        else:
            color = color_estacion_vacia
            marker = 's'
            markersize = 80

        ax.scatter(x, y, c=color, s=markersize, edgecolors='black', linewidth=1.5,
                   marker=marker, zorder=2, alpha=0.8)

# ===== GENERAR TRAYECTORIA SERPIENTE =====
trayectoria_x = []
trayectoria_y = []

for fila in range(filas):
    if fila % 2 == 0:  # Fila par: izquierda a derecha
        for col in range(columnas):
            trayectoria_x.append(col * sep_x)
            trayectoria_y.append(fila * sep_y)
    else:  # Fila impar: derecha a izquierda
        for col in range(columnas - 1, -1, -1):
            trayectoria_x.append(col * sep_x)
            trayectoria_y.append(fila * sep_y)

# Dibujar línea de trayectoria
ax.plot(trayectoria_x, trayectoria_y,
        color=color_trayectoria,
        linewidth=3,
        linestyle='-',
        alpha=0.7,
        zorder=1)

# ===== AGREGAR FLECHAS DIRECCIONALES =====
# Flechas cada 3 estaciones para claridad
for i in range(0, len(trayectoria_x) - 1, 3):
    x1, y1 = trayectoria_x[i], trayectoria_y[i]
    x2, y2 = trayectoria_x[i + 1], trayectoria_y[i + 1]

    # Calcular punto medio y dirección
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    dx = x2 - x1
    dy = y2 - y1

    # Flecha pequeña
    arrow = FancyArrowPatch(
        (mid_x - dx*0.1, mid_y - dy*0.1),
        (mid_x + dx*0.1, mid_y + dy*0.1),
        arrowstyle='->,head_width=0.15,head_length=0.2',
        color=color_flecha,
        linewidth=2,
        zorder=3
    )
    ax.add_patch(arrow)

# ===== MARCAR INICIO Y FIN =====
# Punto de inicio (0,0)
ax.scatter(0, 0, c=color_inicio, s=300, marker='*', edgecolors='black', linewidth=2, zorder=5)
ax.text(0, -0.35, 'INICIO\n(0,0)', fontsize=10, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.3', facecolor=color_inicio, edgecolor='black', alpha=0.7))

# Punto final (última posición)
x_fin = trayectoria_x[-1]
y_fin = trayectoria_y[-1]
ax.scatter(x_fin, y_fin, c='gold', s=300, marker='*', edgecolors='black', linewidth=2, zorder=5)
ax.text(x_fin, y_fin - 0.35, 'FIN', fontsize=10, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='gold', edgecolor='black', alpha=0.7))

# ===== LEYENDA =====
legend_x = -0.5
legend_y = 6.3

ax.text(legend_x + 0.5, legend_y + 0.3, 'LEYENDA', fontsize=11, fontweight='bold')

# Estación con lechuga
ax.scatter(legend_x, legend_y, c=color_estacion_lechuga, s=100, edgecolors='black',
           linewidth=1.5, marker='o')
ax.text(legend_x + 0.3, legend_y, 'Lechuga presente', fontsize=9, va='center')

# Estación vacía
ax.scatter(legend_x, legend_y - 0.4, c=color_estacion_vacia, s=100, edgecolors='black',
           linewidth=1.5, marker='s')
ax.text(legend_x + 0.3, legend_y - 0.4, 'Vaso vacío', fontsize=9, va='center')

# Trayectoria
ax.plot([legend_x - 0.1, legend_x + 0.1], [legend_y - 0.8, legend_y - 0.8],
        color=color_trayectoria, linewidth=3, alpha=0.7)
ax.text(legend_x + 0.3, legend_y - 0.8, 'Trayectoria robot', fontsize=9, va='center')

# ===== ANOTACIONES DE DIMENSIONES =====
# Dimensión horizontal
ax.annotate('', xy=(11*sep_x, -0.5), xytext=(0, -0.5),
            arrowprops=dict(arrowstyle='<->', lw=2, color='black'))
ax.text(5.5, -0.7, '1800 mm (12 estaciones × 150 mm)', fontsize=9, ha='center', fontweight='bold')

# Dimensión vertical
ax.annotate('', xy=(-0.5, 5*sep_y), xytext=(-0.5, 0),
            arrowprops=dict(arrowstyle='<->', lw=2, color='black'))
ax.text(-0.9, 2.5, '1200 mm\n(6 filas × 200 mm)', fontsize=9, ha='center', fontweight='bold', rotation=90, va='center')

# ===== VENTAJAS DEL PATRÓN =====
ventajas_x = 9.5
ventajas_y = 6.3

ax.text(ventajas_x + 1.2, ventajas_y + 0.3, 'VENTAJAS', fontsize=11, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', edgecolor='black', linewidth=1.5))

ventajas = [
    '✓ Minimiza movimientos en Y (eje lento)',
    '✓ Solo 5 incrementos verticales',
    '✓ Sin retornos largos',
    '✓ Transiciones suaves entre filas',
    '✓ Tiempo estimado: ~210 segundos'
]

y_ventaja = ventajas_y - 0.1
for ventaja in ventajas:
    ax.text(ventajas_x, y_ventaja, ventaja, fontsize=8, ha='left', va='top')
    y_ventaja -= 0.35

# ===== COMPARACIÓN =====
ax.text(6, -0.95, 'Alternativa (barrido unidireccional): requiere 5 retornos completos → +25% tiempo',
        fontsize=9, ha='center', style='italic', color='darkred',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='mistyrose', edgecolor='red', linewidth=1))

# ===== INDICADORES DE FILA =====
for fila in range(filas):
    direccion = '→' if fila % 2 == 0 else '←'
    ax.text(-0.7, fila * sep_y, f'Fila {fila+1}\n{direccion}', fontsize=8, ha='right', va='center',
            fontweight='bold', color='darkblue')

plt.tight_layout()
plt.savefig('Informe/imagenes/patron_barrido_serpiente.png', dpi=300, bbox_inches='tight', facecolor='white')
print("✓ Diagrama guardado: Informe/imagenes/patron_barrido_serpiente.png")
plt.close()
