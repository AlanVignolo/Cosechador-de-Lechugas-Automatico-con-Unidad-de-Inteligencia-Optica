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
d_acel_suave = 2.5
d_acel_fuerte = 13.3
d_crucero = 218.4  # Movimiento largo
d_decel_fuerte = 13.3
d_decel_suave = 2.5
d_total_trap = d_acel_suave + d_acel_fuerte + d_crucero + d_decel_fuerte + d_decel_suave

# Velocidades
v_inicio = 0.0125
v_fin_suave = 0.050
v_max = 0.250  # Alcanza velocidad máxima

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

# ========== PERFIL TRIANGULAR SIMÉTRICO (Movimiento corto: 25mm) ==========
# Perfil simétrico con 2 fases de aceleración (suave y fuerte) como el trapezoidal
# pero sin fase de crucero. DEBE SER TOTALMENTE SIMÉTRICO.
d_total_tri = 25  # Movimiento corto

# Para que sea simétrico: aceleración + desaceleración deben ser iguales
# Total: 25mm → cada mitad debe ser 12.5mm
d_mitad_tri = d_total_tri / 2.0  # 12.5 mm

# Usar proporciones de las fases del trapezoidal pero escaladas
# En el trapezoidal: acel_suave=2.5mm, acel_fuerte=13.3mm → total=15.8mm
# Escalar proporcionalmente para que sumen 12.5mm cada mitad
escala = d_mitad_tri / (d_acel_suave + d_acel_fuerte)
d_acel_suave_tri = d_acel_suave * escala
d_acel_fuerte_tri = d_acel_fuerte * escala

# Desaceleración IDÉNTICA (simétrico)
d_decel_fuerte_tri = d_acel_fuerte_tri
d_decel_suave_tri = d_acel_suave_tri

# Calcular velocidad pico en el punto medio usando las mismas aceleraciones
# Fase 1: arranque a v_fin_suave (acel suave)
a_suave = 0.050  # m/s² = 50 mm/s²
v_1 = (v_inicio**2 + 2 * a_suave * (d_acel_suave_tri / 1000.0))**0.5

# Fase 2: v_fin_suave a v_pico (acel fuerte)
a_fuerte = 0.1875  # m/s² = 187.5 mm/s²
v_pico_tri = (v_1**2 + 2 * a_fuerte * (d_acel_fuerte_tri / 1000.0))**0.5

# Perfil simétrico con 7 puntos:
# Distancia: 0, 0, acel_suave, acel_suave+acel_fuerte (MITAD), +decel_fuerte, 25, 25
# Velocidad: 0, v_inicio, v_fin_suave, v_pico, v_fin_suave, v_inicio, 0
#                  └─────────────────────────┘
#                         SIMÉTRICO ✓

# AGREGANDO PUNTO EN 0 AL INICIO Y FINAL
distancias_tri = [0, 0,
                  d_acel_suave_tri,
                  d_acel_suave_tri + d_acel_fuerte_tri,  # 12.5mm - PUNTO MEDIO
                  d_acel_suave_tri + d_acel_fuerte_tri + d_decel_fuerte_tri,
                  d_total_tri, d_total_tri]
velocidades_tri = [0, v_inicio, v_fin_suave, v_pico_tri, v_fin_suave, v_inicio, 0]

ax2.plot(distancias_tri, velocidades_tri, '-', linewidth=2, marker='o', markersize=5, color='#2C3E50')
ax2.fill_between(distancias_tri, 0, velocidades_tri, alpha=0.15, color='#34495E')
ax2.grid(True, alpha=0.25, linestyle=':', color='gray')
ax2.set_xlabel('Distancia (mm)', fontsize=10)
ax2.set_ylabel('Velocidad (m/s)', fontsize=10)
ax2.text(d_total_tri/2, v_max * 0.95, 'Perfil Triangular Simétrico (25 mm)',
         ha='center', fontsize=10, fontweight='bold', color='#2C3E50')

# Anotar que no hay crucero y que es simétrico
ax2.text(d_total_tri/2, v_pico_tri/2, 'Sin crucero\n(Aceleración simétrica)',
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
# plt.show()  # Comentado para no mostrar ventana interactiva
plt.close()
