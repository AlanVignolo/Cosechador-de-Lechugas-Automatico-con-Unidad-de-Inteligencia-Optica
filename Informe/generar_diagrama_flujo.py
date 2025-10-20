import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Configuración de la figura (horizontal)
fig, ax = plt.subplots(figsize=(16, 3))
ax.set_xlim(0, 16)
ax.set_ylim(0, 3)
ax.axis('off')

# Definir los pasos del flujo
pasos = [
    "Recepción del mensaje por UART",
    "Análisis sintáctico",
    "Configuración de perfil de movimiento",
    "Generación de interrupciones",
    "Emisión de pulsos hacia drivers",
    "Notificación de finalización al supervisor"
]

# Configuración de posiciones (horizontal)
num_pasos = len(pasos)
x_start = 1.5
x_step = 2.4
y_text = 1.5
y_numero = 2.2

# Colores
color_flecha = '#1976D2'
color_texto = '#263238'
color_numero = '#1976D2'

# Dibujar pasos con números y flechas
for i, paso in enumerate(pasos):
    x_pos = x_start + i * x_step

    # Dibujar número
    ax.text(x_pos, y_numero, f"{i+1}.",
            ha='center', va='center',
            fontsize=16, fontweight='bold',
            color=color_numero)

    # Agregar texto del paso
    ax.text(x_pos, y_text, paso,
            ha='center', va='center',
            fontsize=12, fontweight='normal',
            color=color_texto,
            wrap=True)

    # Dibujar flecha hacia el siguiente paso (excepto el último)
    if i < num_pasos - 1:
        arrow = FancyArrowPatch(
            (x_pos + 0.6, y_text),
            (x_pos + x_step - 0.6, y_text),
            arrowstyle='->,head_width=0.4,head_length=0.4',
            color=color_flecha,
            linewidth=2.5,
            zorder=1
        )
        ax.add_patch(arrow)

# Título
plt.title('Flujo de Procesamiento del Nivel Regulatorio',
          fontsize=14, fontweight='bold', pad=15, color='#263238')

# Guardar la imagen
plt.tight_layout()
plt.savefig('imagenes/flujo_nivel_regulatorio.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("Imagen generada exitosamente: imagenes/flujo_nivel_regulatorio.png")

plt.close()
