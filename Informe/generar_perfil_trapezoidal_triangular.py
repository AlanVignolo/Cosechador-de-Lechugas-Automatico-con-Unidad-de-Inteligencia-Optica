"""
Script para generar comparación entre perfil trapezoidal y triangular.
Genera la imagen: perfil_trapezoidal_triangular.png
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

# Crear figura con estilo profesional
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# ========== PERFIL TRAPEZOIDAL (Movimiento largo: 250mm) ==========
# Distancias para cada fase
d_acel_suave = 5
d_acel_fuerte = 7.5
d_crucero = 225  # Movimiento largo
d_decel_fuerte = 7.5
d_decel_suave = 5
d_total_trap = d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte + d_decel_suave

# Velocidades
v_inicio = 0.05
v_fin_suave = 0.10
v_max = 0.375  # Alcanza velocidad máxima

# AGREGANDO PUNTO EN 0 AL INICIO Y FINAL
distancias_trap = [0, 0, d_acel_suave, d_acel_suave + d_acel_fuerte,
                   d_acel_suave + d_acel_fuerte + d_crucero,
                   d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte,
                   d_total_trap, d_total_trap]
velocidades_trap = [0, v_inicio, v_fin_suave, v_max, v_max, v_fin_suave, v_inicio, 0]

ax1.plot(distancias_trap, velocidades_trap, '-', linewidth=2, marker='o', markersize=5, color='#2C3E50')
ax1.fill_between(distancias_trap, 0, velocidades_trap, alpha=0.15, color='#34495E')
ax1.grid(True, alpha=0.25, linestyle=':', color='gray')
ax1.set_xlabel('Distancia (mm)', fontsize=10)
ax1.set_ylabel('Velocidad (m/s)', fontsize=10)
ax1.text(d_total_trap/2, v_max * 0.95, 'Perfil Trapezoidal (250 mm)', 
         ha='center', fontsize=10, fontweight='bold', color='#2C3E50')

# Anotar zona de crucero - discreto
ax1.annotate('', xy=(d_acel_suave + d_acel_fuerte + d_crucero, v_max), 
             xytext=(d_acel_suave + d_acel_fuerte, v_max),
             arrowprops=dict(arrowstyle='<->', lw=1.2, color='#2C3E50'))
ax1.text(d_acel_suave + d_acel_fuerte + d_crucero/2, v_max + 0.025,
         f'Crucero: {d_crucero} mm', ha='center', fontsize=8, 
         color='#2C3E50')

ax1.set_ylim(0, v_max + 0.1)

# ========== PERFIL CUASI-TRIANGULAR (Movimiento corto: 25mm) ==========
# No es triangular puro, tiene 2 fases de acel/decel (suave y fuerte)
d_total_tri = 25  # Movimiento corto
d_acel_suave_tri = 5
d_acel_fuerte_tri = 7.5
# No hay crucero, pasa directo a desacelerar
d_decel_fuerte_tri = 7.5
d_decel_suave_tri = 5

# Velocidad máxima alcanzada (menor que v_max porque no hay crucero)
v_pico = 0.20  # No alcanza v_max porque debe frenar antes

# AGREGANDO PUNTO EN 0 AL INICIO Y FINAL
distancias_tri = [0, 0,
                  d_acel_suave_tri,
                  d_acel_suave_tri + d_acel_fuerte_tri,
                  d_acel_suave_tri + d_acel_fuerte_tri + d_decel_fuerte_tri,
                  d_total_tri, d_total_tri]
velocidades_tri = [0, v_inicio, v_fin_suave, v_pico, v_fin_suave, v_inicio, 0]

ax2.plot(distancias_tri, velocidades_tri, '-', linewidth=2, marker='o', markersize=5, color='#2C3E50')
ax2.fill_between(distancias_tri, 0, velocidades_tri, alpha=0.15, color='#34495E')
ax2.grid(True, alpha=0.25, linestyle=':', color='gray')
ax2.set_xlabel('Distancia (mm)', fontsize=10)
ax2.set_ylabel('Velocidad (m/s)', fontsize=10)
ax2.text(d_total_tri/2, v_max * 0.95, 'Perfil Cuasi-Triangular (25 mm)', 
         ha='center', fontsize=10, fontweight='bold', color='#2C3E50')

# Anotar que no hay crucero
ax2.text(d_total_tri/2, v_pico/2, 'Sin crucero', 
         ha='center', fontsize=9, color='#555555', style='italic')

# Línea de v_max para referencia
ax2.axhline(v_max, color='gray', linestyle='--', alpha=0.4, linewidth=1)
ax2.text(1, v_max + 0.01, f'$v_{{max}}$ = {v_max} m/s', 
         fontsize=8, color='#555555')

ax2.set_ylim(0, v_max + 0.1)

# Sin título general según solicitud

plt.tight_layout(rect=[0, 0.03, 1, 0.96])
output_path = 'imagenes/perfil_trapezoidal_triangular.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
plt.show()
