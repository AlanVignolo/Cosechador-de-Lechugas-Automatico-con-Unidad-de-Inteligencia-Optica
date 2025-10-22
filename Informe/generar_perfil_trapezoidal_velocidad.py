"""
Script para generar diagrama del perfil trapezoidal de velocidad.
Genera la imagen: perfil_trapezoidal_velocidad.png
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

# Parámetros del movimiento
# Distancias para cada fase (mm)
d_arranque = 0
d_acel_suave = 2.5
d_acel_fuerte = 13.3
d_crucero = 218.4  # Variable según distancia total (250mm - 31.6mm de accel/decel)
d_decel_fuerte = 13.3
d_decel_suave = 2.5
d_total = d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte + d_decel_suave

# Velocidades en cada fase (m/s) - Eje Horizontal
v_inicio = 0.0125
v_fin_suave = 0.050
v_max = 0.250  # Velocidad de crucero horizontal

# Crear perfil de posición - AGREGANDO PUNTO EN 0
distancias = [0,
              0,  # Punto inicial en velocidad 0
              d_acel_suave,
              d_acel_suave + d_acel_fuerte,
              d_acel_suave + d_acel_fuerte + d_crucero,
              d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte,
              d_total,
              d_total]  # Punto final en velocidad 0

# Velocidades correspondientes - AGREGANDO 0 AL INICIO Y FINAL
velocidades = [0, v_inicio, v_fin_suave, v_max, v_max, v_fin_suave, v_inicio, 0]

# Crear figura con estilo profesional
fig, ax1 = plt.subplots(1, 1, figsize=(10, 6))

# ========== GRÁFICO: VELOCIDAD vs DISTANCIA ==========
ax1.plot(distancias, velocidades, 'k-', linewidth=2, marker='o', markersize=6, color='#2C3E50')
ax1.fill_between(distancias, 0, velocidades, alpha=0.15, color='#34495E')
ax1.grid(True, alpha=0.25, linestyle=':', color='gray')
ax1.set_xlabel('Distancia (mm)', fontsize=12)
ax1.set_ylabel('Velocidad (m/s)', fontsize=12)
# Sin título según solicitud

# Anotaciones de fases - MAS GRANDES Y BIEN SEPARADAS
y_label_alta = v_max + 0.06
y_label_baja = v_max + 0.02
# Alternando posiciones para evitar superposición
ax1.text(d_acel_suave/2, y_label_baja, 'Acel.\nsuave', ha='center', fontsize=11, color='#2C3E50', fontweight='bold')
ax1.text(d_acel_suave + d_acel_fuerte/2, y_label_alta, 'Acel.\nfuerte', ha='center', fontsize=11, color='#2C3E50', fontweight='bold')
ax1.text(d_acel_suave + d_acel_fuerte + d_crucero/2, y_label_baja, 'Crucero', ha='center', fontsize=12, color='#2C3E50', fontweight='bold')
ax1.text(d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte/2, y_label_alta, 'Decel.\nfuerte', ha='center', fontsize=11, color='#2C3E50', fontweight='bold')
ax1.text(d_total - d_decel_suave/2, y_label_baja, 'Decel.\nsuave', ha='center', fontsize=11, color='#2C3E50', fontweight='bold')

# Líneas verticales separadoras - discretas
for d in [d_acel_suave, d_acel_suave + d_acel_fuerte, 
          d_acel_suave + d_acel_fuerte + d_crucero,
          d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte]:
    ax1.axvline(d, color='gray', linestyle=':', alpha=0.3, linewidth=0.8)

ax1.set_ylim(0, v_max + 0.15)

# Sin nota al pie según solicitud

plt.tight_layout()
output_path = 'imagenes/perfil_trapezoidal_velocidad.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
# plt.show()  # Comentado para no mostrar ventana interactiva
plt.close()
