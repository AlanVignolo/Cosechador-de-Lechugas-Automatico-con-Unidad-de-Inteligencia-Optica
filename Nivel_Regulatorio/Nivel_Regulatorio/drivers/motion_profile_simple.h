#ifndef MOTION_PROFILE_SIMPLE_H
#define MOTION_PROFILE_SIMPLE_H

#include <stdint.h>
#include <stdbool.h>

// Configuración de velocidades (en pasos/segundo)
#define SPEED_START      2000    // Velocidad inicial/final (más rápido)
#define SPEED_LOW        4000    // Velocidad baja (transición)
#define SPEED_CRUISE_H   15000   // Velocidad crucero horizontal
#define SPEED_CRUISE_V   12000   // Velocidad crucero vertical

// Segmentos del perfil (en porcentaje del total)
#define ACCEL_SOFT_PERCENT    15  // Primeros 15% aceleración suave
#define ACCEL_HARD_PERCENT    10  // Siguientes 10% aceleración fuerte
#define DECEL_HARD_PERCENT    10  // 10% desaceleración fuerte
#define DECEL_SOFT_PERCENT    15  // Últimos 15% desaceleración suave
// El resto (50%) es velocidad crucero

// Intervalos de actualización (en pasos)
#define SPEED_UPDATE_INTERVAL  10  // Actualizar cada 10 pasos

typedef struct {
	// Configuración del movimiento
	int32_t total_steps;
	int32_t steps_done;
	uint16_t cruise_speed;
	
	// Umbrales precalculados
	int32_t accel_soft_end;    // Fin de aceleración suave
	int32_t accel_hard_end;    // Fin de aceleración fuerte
	int32_t decel_hard_start;  // Inicio de desaceleración fuerte
	int32_t decel_soft_start;  // Inicio de desaceleración suave
	
	// Estado actual
	uint16_t current_speed;
	bool active;
} simple_profile_t;

// Funciones públicas
void simple_profile_init(simple_profile_t* profile);
void simple_profile_calculate(simple_profile_t* profile, int32_t steps, uint16_t cruise_speed);
uint16_t simple_profile_get_speed(simple_profile_t* profile);
void simple_profile_stop(simple_profile_t* profile);

#endif