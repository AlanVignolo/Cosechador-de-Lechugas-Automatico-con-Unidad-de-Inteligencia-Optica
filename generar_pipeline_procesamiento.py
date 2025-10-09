"""
Generador del diagrama de Pipeline de Procesamiento Completo
Muestra las 7 etapas secuenciales con sus tiempos de ejecución
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Configuración de la figura
fig, ax = plt.subplots(figsize=(16, 10))
ax.set_xlim(0, 16)
ax.set_ylim(0, 10)
ax.axis('off')

# Colores por etapa
colores = [
    '#3498DB',  # Azul - Adquisición
    '#2ECC71',  # Verde - Preprocesamiento
    '#F39C12',  # Naranja - Segmentación
    '#9B59B6',  # Morado - Morfología
    '#E74C3C',  # Rojo - Contornos
    '#1ABC9C',  # Turquesa - Descriptores
    '#34495E'   # Gris oscuro - Decisión
]

# Datos de las 7 etapas
etapas = [
    {
        'nombre': 'ADQUISICIÓN',
        'descripcion': ['Captura RGB', '1920×1080 px', 'USB 2.0'],
        'tiempo': '50 ms',
        'detalles': 'Cámara USB'
    },
    {
        'nombre': 'PREPROCESAMIENTO',
        'descripcion': ['Conversión', 'RGB → HSV', 'Vectorización'],
        'tiempo': '15 ms',
        'detalles': 'OpenCV optimizado'
    },
    {
        'nombre': 'SEGMENTACIÓN',
        'descripcion': ['Umbralización', 'Canal V o HSV', 'Máscara binaria'],
        'tiempo': '20 ms',
        'detalles': 'Adaptativo por módulo'
    },
    {
        'nombre': 'MORFOLOGÍA',
        'descripcion': ['Cierre 3×3', 'Apertura 3×3', 'Refinamiento'],
        'tiempo': '25 ms',
        'detalles': 'Elimina ruido'
    },
    {
        'nombre': 'CONTORNOS',
        'descripcion': ['Suzuki-Abe', 'Externos', 'Compresión'],
        'tiempo': '30 ms',
        'detalles': 'Detección fronteras'
    },
    {
        'nombre': 'DESCRIPTORES',
        'descripcion': ['Área', 'Centroide', 'Perímetro'],
        'tiempo': '10 ms',
        'detalles': 'Momentos de imagen'
    },
    {
        'nombre': 'DECISIÓN',
        'descripcion': ['Clasificación', 'Comando', 'Salida'],
        'tiempo': '5 ms',
        'detalles': 'Lógica de control'
    }
]

# Función para crear etapa del pipeline
def crear_etapa_pipeline(x, y, ancho, alto, color, etapa_data, numero, ax):
    # Caja principal
    box = FancyBboxPatch((x, y), ancho, alto,
                          boxstyle="round,pad=0.08",
                          edgecolor='black',
                          facecolor=color,
                          linewidth=2.5,
                          alpha=0.9)
    ax.add_patch(box)

    # Número de etapa
    ax.text(x + 0.3, y + alto - 0.3,
            f'{numero}',
            fontsize=18,
            fontweight='bold',
            ha='center',
            va='center',
            color='white',
            bbox=dict(boxstyle='circle,pad=0.15', facecolor='black', edgecolor='white', linewidth=2))

    # Nombre de la etapa
    ax.text(x + ancho/2, y + alto - 0.4,
            etapa_data['nombre'],
            fontsize=12,
            fontweight='bold',
            ha='center',
            va='top',
            color='white')

    # Descripción (3 líneas)
    y_desc = y + alto - 0.8
    for linea in etapa_data['descripcion']:
        ax.text(x + ancho/2, y_desc,
                linea,
                fontsize=9,
                ha='center',
                va='top',
                color='white')
        y_desc -= 0.25

    # Tiempo de ejecución (destacado)
    ax.text(x + ancho/2, y + 0.5,
            etapa_data['tiempo'],
            fontsize=13,
            fontweight='bold',
            ha='center',
            va='center',
            color='yellow',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))

    # Detalles técnicos
    ax.text(x + ancho/2, y + 0.1,
            etapa_data['detalles'],
            fontsize=7,
            ha='center',
            va='bottom',
            color='white',
            style='italic')

# Función para crear flecha entre etapas
def crear_flecha_pipeline(x1, y1, x2, y2, ax):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle='->,head_width=0.4,head_length=0.5',
        color='black',
        linewidth=3,
        zorder=1
    )
    ax.add_patch(arrow)

# ===== TÍTULO PRINCIPAL =====
ax.text(8, 9.3, 'PIPELINE COMPLETO DE PROCESAMIENTO DE IMÁGENES',
        fontsize=18, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.6', facecolor='lightgray', edgecolor='black', linewidth=3))

ax.text(8, 8.8, 'Transformación secuencial de imagen cruda a comando de acción',
        fontsize=11, ha='center', style='italic', color='gray')

# ===== DIBUJAR ETAPAS =====

# Primera fila: Etapas 1-4
y_fila1 = 6
x_start = 1
ancho_etapa = 3
alto_etapa = 2
espacio = 0.3

for i in range(4):
    x = x_start + i * (ancho_etapa + espacio)
    crear_etapa_pipeline(x, y_fila1, ancho_etapa, alto_etapa, colores[i], etapas[i], i+1, ax)

    # Flechas entre etapas
    if i < 3:
        x1 = x + ancho_etapa
        x2 = x + ancho_etapa + espacio
        y_flecha = y_fila1 + alto_etapa / 2
        crear_flecha_pipeline(x1, y_flecha, x2, y_flecha, ax)

# Flecha hacia abajo de etapa 4 a 5
crear_flecha_pipeline(x_start + 3*(ancho_etapa + espacio) + ancho_etapa/2, y_fila1,
                      x_start + 3*(ancho_etapa + espacio) + ancho_etapa/2, y_fila1 - 1, ax)

# Segunda fila: Etapas 5-7 (orden inverso visualmente)
y_fila2 = 3
for i in range(3):
    idx = 6 - i  # Índice inverso (6, 5, 4)
    x = x_start + i * (ancho_etapa + espacio)
    crear_etapa_pipeline(x, y_fila2, ancho_etapa, alto_etapa, colores[idx], etapas[idx], idx+1, ax)

    # Flechas entre etapas (dirección inversa)
    if i < 2:
        x1 = x + ancho_etapa
        x2 = x + ancho_etapa + espacio
        y_flecha = y_fila2 + alto_etapa / 2
        crear_flecha_pipeline(x1, y_flecha, x2, y_flecha, ax)

# Flecha de conexión entre filas (etapa 4 a etapa 5)
crear_flecha_pipeline(x_start + 3*(ancho_etapa + espacio) + ancho_etapa/2, y_fila1 - 1,
                      x_start + 2*(ancho_etapa + espacio) + ancho_etapa/2, y_fila2 + alto_etapa, ax)

# ===== RESUMEN TEMPORAL =====
ax.text(8, 1.8, 'TIEMPO TOTAL DE PROCESAMIENTO',
        fontsize=13, fontweight='bold', ha='center')

ax.text(8, 1.3,
        'T_total = 50 + 15 + 20 + 25 + 30 + 10 + 5 = 155 ms',
        fontsize=12, ha='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', edgecolor='black', linewidth=2))

ax.text(8, 0.8,
        'Frecuencia de operación: f = 1/0.155 ≈ 6.5 Hz',
        fontsize=11, ha='center', fontweight='bold', color='darkgreen')

# ===== LEYENDA Y NOTAS =====
ax.text(8, 0.3,
        'Compatible con control en tiempo real: Velocidad robot 5-10 cm/s → Desplazamiento 7.75-15.5 mm entre capturas',
        fontsize=9, ha='center', style='italic', color='gray')

# Indicador de adaptabilidad
ax.text(14.5, 6,
        'ADAPTABILIDAD\nPOR MÓDULO',
        fontsize=10, fontweight='bold', ha='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightblue', edgecolor='black', linewidth=2))

ax.text(14.5, 5.2,
        'Posicionamiento:\nCanal V + Umbral 50',
        fontsize=8, ha='center')

ax.text(14.5, 4.5,
        'Clasificación:\nRango HSV verde',
        fontsize=8, ha='center')

plt.tight_layout()
plt.savefig('Informe/imagenes/pipeline_procesamiento_completo.png', dpi=300, bbox_inches='tight', facecolor='white')
print("✓ Diagrama guardado: Informe/imagenes/pipeline_procesamiento_completo.png")
plt.close()
