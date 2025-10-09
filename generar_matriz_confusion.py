import numpy as np
import matplotlib.pyplot as plt

# Crear matriz de confusión genérica para marco teórico
# Filas: Clase Real, Columnas: Clase Predicha
# Clases genéricas: A, B, C

cm = np.array([
    [85,  8,  7],   # Clase A
    [10, 82,  8],   # Clase B
    [ 5,  6, 89]    # Clase C
])

clases = ['Clase A', 'Clase B', 'Clase C']

# Crear figura con matplotlib
fig, ax = plt.subplots(figsize=(10, 9))

# Crear heatmap manualmente
cax = ax.matshow(cm, cmap='Blues', vmin=0, vmax=100)
cbar = fig.colorbar(cax, label='Numero de muestras', fraction=0.046, pad=0.04)
cbar.ax.tick_params(labelsize=11)

# Añadir valores en cada celda
for i in range(len(clases)):
    for j in range(len(clases)):
        text_color = 'white' if cm[i, j] > 50 else 'black'
        ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                fontsize=22, fontweight='bold', color=text_color)

# Configurar ejes
ax.set_xticks(range(len(clases)))
ax.set_yticks(range(len(clases)))
ax.set_xticklabels(clases, fontsize=13, fontweight='bold')
ax.set_yticklabels(clases, fontsize=13, fontweight='bold')

# Etiquetas
ax.set_xlabel('Clase Predicha', fontsize=15, fontweight='bold', labelpad=12)
ax.set_ylabel('Clase Real', fontsize=15, fontweight='bold', labelpad=12)
ax.set_title('Matriz de Confusion para Clasificacion Multiclase',
             fontsize=17, fontweight='bold', pad=25)

# Mover xlabel arriba
ax.xaxis.set_label_position('top')
ax.xaxis.tick_top()

# Añadir líneas de separación
for i in range(len(clases) + 1):
    ax.axhline(i - 0.5, color='white', linewidth=3)
    ax.axvline(i - 0.5, color='white', linewidth=3)

# Ajustar layout
plt.tight_layout()

# Guardar imagen
plt.savefig('Informe/imagenes/matriz_confusion_ejemplo.png', dpi=300, bbox_inches='tight', facecolor='white')
print("OK - Imagen guardada en: Informe/imagenes/matriz_confusion_ejemplo.png")

# Mostrar estadísticas
print("\n=== Estadisticas de Clasificacion ===")
accuracy = np.trace(cm) / np.sum(cm)
print(f"Exactitud (Accuracy): {accuracy:.2%}")

for i, clase in enumerate(clases):
    precision = cm[i,i] / np.sum(cm[:,i]) if np.sum(cm[:,i]) > 0 else 0
    recall = cm[i,i] / np.sum(cm[i,:]) if np.sum(cm[i,:]) > 0 else 0
    print(f"\n{clase}:")
    print(f"  Precision: {precision:.2%}")
    print(f"  Recall: {recall:.2%}")

print("\nMatriz de confusion:")
print(cm)

plt.close()
print("\nListo! Abre la imagen en: Informe/imagenes/matriz_confusion_ejemplo.png")
