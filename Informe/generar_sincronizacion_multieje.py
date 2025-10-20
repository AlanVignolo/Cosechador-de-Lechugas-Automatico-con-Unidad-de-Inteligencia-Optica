"""
Script para generar diagrama de sincronización multi-eje.
Muestra 4 gráficos: arriba sin sincronizar, abajo sincronizado.
Genera la imagen: sincronizacion_multieje.png
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Crear directorio si no existe
os.makedirs('imagenes', exist_ok=True)

# Parámetros del movimiento - EJEMPLO REAL: DISTANCIAS DIFERENTES
d_horizontal = 400  # mm - Mayor distancia
d_vertical = 200    # mm - Menor distancia

# Velocidades máximas del firmware real (motion_profile_simple.h)
# SPEED_CRUISE_H = 15000 pasos/s / 40 pasos/mm = 375 mm/s = 0.375 m/s
# SPEED_CRUISE_V = 12000 pasos/s / 200 pasos/mm = 60 mm/s = 0.060 m/s
v_max_h = 0.375  # m/s horizontal (RÁPIDO)
v_max_v = 0.060  # m/s vertical (LENTO)

# Perfiles trapezoidales con 2 ACELERACIONES (suave y fuerte)
d_acel_suave = 5     # mm
d_acel_fuerte = 7.5  # mm
d_decel_fuerte = 7.5 # mm
d_decel_suave = 5    # mm

# Velocidades intermedias (EN m/s) - del firmware SPEED_LOW = 4000 pasos/s
# Horizontal: 4000 / 40 = 100 mm/s = 0.100 m/s
# Vertical: 4000 / 200 = 20 mm/s = 0.020 m/s
v_suave_h = 0.100   # m/s después de aceleración suave horizontal
v_suave_v = 0.020   # m/s después de aceleración suave vertical

# ========== SIN SINCRONIZAR - Terminan a distinto tiempo ==========
# Tiempos de aceleración/desaceleración (más cortos para ver diferencia)
t_acel_suave = 1.0    # Aceleración suave
t_acel_fuerte = 1.5   # Aceleración fuerte  
t_decel_fuerte = 1.5  # Desaceleración fuerte
t_decel_suave = 1.0   # Desaceleración suave

# Eje Horizontal (rápido) - termina PRIMERO
d_crucero_h_sin = d_horizontal - d_acel_suave - d_acel_fuerte - d_decel_fuerte - d_decel_suave
t_crucero_h = (d_crucero_h_sin / 1000.0) / v_max_h  # Convertir mm a m, dividir por m/s

t_total_h_sin = t_acel_suave + t_acel_fuerte + t_crucero_h + t_decel_fuerte + t_decel_suave

# Perfil con 2 aceleraciones
tiempo_h_sin = np.array([0, t_acel_suave, t_acel_suave + t_acel_fuerte, 
                         t_acel_suave + t_acel_fuerte + t_crucero_h,
                         t_acel_suave + t_acel_fuerte + t_crucero_h + t_decel_fuerte,
                         t_total_h_sin])
vel_h_sin = np.array([0, v_suave_h, v_max_h, v_max_h, v_suave_h, 0])

# Eje Vertical (lento) - tarda MÁS
d_crucero_v_sin = d_vertical - d_acel_suave - d_acel_fuerte - d_decel_fuerte - d_decel_suave
t_crucero_v = (d_crucero_v_sin / 1000.0) / v_max_v  # Convertir mm a m, dividir por m/s
t_total_v_sin = t_acel_suave + t_acel_fuerte + t_crucero_v + t_decel_fuerte + t_decel_suave

tiempo_v_sin = np.array([0, t_acel_suave, t_acel_suave + t_acel_fuerte,
                         t_acel_suave + t_acel_fuerte + t_crucero_v,
                         t_acel_suave + t_acel_fuerte + t_crucero_v + t_decel_fuerte,
                         t_total_v_sin])
vel_v_sin = np.array([0, v_suave_v, v_max_v, v_max_v, v_suave_v, 0])

# ========== SINCRONIZADO - Terminan al mismo tiempo ==========
# El eje horizontal REDUCE su velocidad para terminar al mismo tiempo que el vertical
t_total_sinc = t_total_v_sin  # Ambos terminan cuando el lento termina

# Calcular nueva velocidad máxima reducida para X
t_crucero_h_sinc = t_total_sinc - t_acel_suave - t_acel_fuerte - t_decel_fuerte - t_decel_suave
v_max_h_reducida = (d_crucero_h_sin / 1000.0) / t_crucero_h_sinc  # m/s - VELOCIDAD MENOR

# Recalcular velocidad intermedia proporcionalmente
v_suave_h_reducida = v_suave_h * (v_max_h_reducida / v_max_h)

tiempo_h_sinc = np.array([0, t_acel_suave, t_acel_suave + t_acel_fuerte,
                          t_acel_suave + t_acel_fuerte + t_crucero_h_sinc,
                          t_acel_suave + t_acel_fuerte + t_crucero_h_sinc + t_decel_fuerte,
                          t_total_sinc])
vel_h_sinc = np.array([0, v_suave_h_reducida, v_max_h_reducida, v_max_h_reducida, v_suave_h_reducida, 0])

# El eje vertical permanece igual
tiempo_v_sinc = tiempo_v_sin
vel_v_sinc = vel_v_sin

# ========== CREAR FIGURA CON 4 SUBPLOTS ==========
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 9))
# Sin título general según solicitud

# ========== ARRIBA IZQUIERDA: Eje X sin sincronizar ==========
ax1.plot(tiempo_h_sin, vel_h_sin, '-', linewidth=2, marker='o', markersize=5, color='#2C3E50')
ax1.fill_between(tiempo_h_sin, 0, vel_h_sin, alpha=0.15, color='#34495E')
ax1.grid(True, alpha=0.25, linestyle=':', color='gray')
ax1.set_xlabel('Tiempo (s)', fontsize=10)
ax1.set_ylabel('Velocidad (m/s)', fontsize=10)
ax1.set_title('Eje X (sin sincronizar)', fontsize=10, fontweight='bold')
# Usar MISMA escala de tiempo que los demás
ax1.set_xlim(0, max(t_total_h_sin, t_total_v_sin) + 0.5)
ax1.set_ylim(0, 0.4)  # m/s

# ========== ARRIBA DERECHA: Eje Y sin sincronizar ==========
ax2.plot(tiempo_v_sin, vel_v_sin, '-', linewidth=2, marker='s', markersize=5, color='#7F8C8D')
ax2.fill_between(tiempo_v_sin, 0, vel_v_sin, alpha=0.15, color='#95A5A6')
ax2.grid(True, alpha=0.25, linestyle=':', color='gray')
ax2.set_xlabel('Tiempo (s)', fontsize=10)
ax2.set_ylabel('Velocidad (m/s)', fontsize=10)
ax2.set_title('Eje Y (sin sincronizar)', fontsize=10, fontweight='bold')
ax2.set_xlim(0, max(t_total_h_sin, t_total_v_sin) + 0.5)
ax2.set_ylim(0, 0.4)  # m/s

# ========== ABAJO IZQUIERDA: Eje X sincronizado (velocidad reducida) ==========
ax3.plot(tiempo_h_sinc, vel_h_sinc, '-', linewidth=2, marker='o', markersize=5, color='#2C3E50')
ax3.fill_between(tiempo_h_sinc, 0, vel_h_sinc, alpha=0.15, color='#34495E')
ax3.grid(True, alpha=0.25, linestyle=':', color='gray')
ax3.set_xlabel('Tiempo (s)', fontsize=10)
ax3.set_ylabel('Velocidad (m/s)', fontsize=10)
ax3.set_title('Eje X (sincronizado - reducido)', fontsize=10, fontweight='bold')
ax3.set_xlim(0, max(t_total_h_sin, t_total_v_sin) + 0.5)
ax3.set_ylim(0, 0.4)  # m/s

# ========== ABAJO DERECHA: Eje Y sincronizado (igual que antes) ==========
ax4.plot(tiempo_v_sinc, vel_v_sinc, '-', linewidth=2, marker='s', markersize=5, color='#7F8C8D')
ax4.fill_between(tiempo_v_sinc, 0, vel_v_sinc, alpha=0.15, color='#95A5A6')
ax4.grid(True, alpha=0.25, linestyle=':', color='gray')
ax4.set_xlabel('Tiempo (s)', fontsize=10)
ax4.set_ylabel('Velocidad (m/s)', fontsize=10)
ax4.set_title('Eje Y (sincronizado - sin cambios)', fontsize=10, fontweight='bold')
ax4.set_xlim(0, max(t_total_h_sin, t_total_v_sin) + 0.5)
ax4.set_ylim(0, 0.4)  # m/s

# ========== VERIFICACIÓN DE DISTANCIAS ==========
print("\n" + "="*60)
print("VERIFICACIÓN DE DISTANCIAS RECORRIDAS")
print("="*60)

# Las distancias de aceleración/desaceleración son FIJAS
d_acel_decel_total = d_acel_suave + d_acel_fuerte + d_decel_fuerte + d_decel_suave

# Sin sincronizar - Eje X
d_crucero_calculado_x = v_max_h * t_crucero_h * 1000  # m/s * s * 1000 = mm
d_total_x_sin = d_acel_decel_total + d_crucero_calculado_x
print(f"\nSIN SINCRONIZAR:")
print(f"  Eje X:")
print(f"    Acel+Decel: {d_acel_decel_total:.1f} mm (fijo)")
print(f"    Crucero: {d_crucero_calculado_x:.1f} mm ({t_crucero_h:.2f}s a {v_max_h:.3f} m/s)")
print(f"    TOTAL: {d_total_x_sin:.1f} mm (objetivo: {d_horizontal} mm)")
print(f"    Tiempo: {t_total_h_sin:.2f} s")

# Sin sincronizar - Eje Y
d_crucero_calculado_y = v_max_v * t_crucero_v * 1000  # m/s * s * 1000 = mm
d_total_y_sin = d_acel_decel_total + d_crucero_calculado_y
print(f"  Eje Y:")
print(f"    Acel+Decel: {d_acel_decel_total:.1f} mm (fijo)")
print(f"    Crucero: {d_crucero_calculado_y:.1f} mm ({t_crucero_v:.2f}s a {v_max_v:.3f} m/s)")
print(f"    TOTAL: {d_total_y_sin:.1f} mm (objetivo: {d_vertical} mm)")
print(f"    Tiempo: {t_total_v_sin:.2f} s")

# Sincronizado - Eje X
d_crucero_calculado_x_sinc = v_max_h_reducida * t_crucero_h_sinc * 1000
d_total_x_sinc = d_acel_decel_total + d_crucero_calculado_x_sinc
print(f"\nSINCRONIZADO:")
print(f"  Eje X:")
print(f"    Acel+Decel: {d_acel_decel_total:.1f} mm (fijo)")
print(f"    Crucero: {d_crucero_calculado_x_sinc:.1f} mm ({t_crucero_h_sinc:.2f}s a {v_max_h_reducida:.3f} m/s)")
print(f"    TOTAL: {d_total_x_sinc:.1f} mm (objetivo: {d_horizontal} mm)")
print(f"    Tiempo: {t_total_sinc:.2f} s")
print(f"    Vel. crucero reducida: {v_max_h_reducida:.3f} m/s (original: {v_max_h:.3f} m/s)")

# Sincronizado - Eje Y (sin cambios)
d_total_y_sinc = d_total_y_sin
print(f"  Eje Y: {d_total_y_sinc:.1f} mm (igual que sin sincronizar)")
print(f"    Tiempo: {t_total_sinc:.2f} s")
print("="*60 + "\n")

plt.tight_layout()
output_path = 'imagenes/sincronizacion_multieje.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Diagrama generado exitosamente: {output_path}")
plt.show()
