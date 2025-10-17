#ifndef MOTION_PROFILE_SIMPLE_H
#define MOTION_PROFILE_SIMPLE_H

#include <stdint.h>
#include <stdbool.h>

// Configuración de velocidades (en pasos/segundo)
#define SPEED_START      2000    // Velocidad inicial/final
#define SPEED_LOW        4000    // Velocidad baja (transición)
#define SPEED_CRUISE_H   15000   // Velocidad crucero horizontal
#define SPEED_CRUISE_V   12000   // Velocidad crucero vertical

// Distancias fijas de aceleración/desaceleración (en pasos)
// Esto garantiza aceleraciones constantes independientemente de la distancia total
#define ACCEL_SOFT_STEPS     200   // Pasos para aceleración suave (START -> LOW)
#define ACCEL_HARD_STEPS     300   // Pasos para aceleración fuerte (LOW -> CRUISE)
#define DECEL_HARD_STEPS     300   // Pasos para desaceleración fuerte (CRUISE -> LOW)
#define DECEL_SOFT_STEPS     200   // Pasos para desaceleración suave (LOW -> START)

// Total de pasos mínimos para perfil trapezoidal completo
#define MIN_STEPS_FOR_TRAPEZOID  (ACCEL_SOFT_STEPS + ACCEL_HARD_STEPS + DECEL_HARD_STEPS + DECEL_SOFT_STEPS)

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
