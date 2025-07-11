#ifndef MOTION_PROFILE_H
#define MOTION_PROFILE_H

#include <stdint.h>
#include <stdbool.h>

// Estados del perfil de movimiento
typedef enum {
	PROFILE_IDLE,
	PROFILE_ACCELERATING,
	PROFILE_CONSTANT,
	PROFILE_DECELERATING,
	PROFILE_COMPLETED
} profile_state_t;

// Estructura para manejar el perfil de cada eje
typedef struct {
	// Parámetros del movimiento
	int32_t start_position;
	int32_t target_position;
	int32_t total_steps;
	
	// Velocidades
	uint16_t current_speed;
	uint16_t target_speed;
	uint16_t max_speed;
	uint16_t acceleration;
	
	// Estado del perfil
	profile_state_t state;
	
	// Distancias para cada fase
	int32_t accel_steps;
	int32_t decel_steps;
	int32_t constant_steps;
	
	// Posición donde empieza la deceleración
	int32_t decel_start_pos;
	
	// Control de tiempo
	uint32_t last_update_ms;
	
} motion_profile_t;

// Inicializar el módulo de perfil de movimiento
void motion_profile_init(void);

// Configurar un nuevo movimiento para un eje
void motion_profile_setup(motion_profile_t* profile,
int32_t current_pos,
int32_t target_pos,
uint16_t max_speed,
uint16_t acceleration);

// Actualizar el perfil y obtener la velocidad actual
uint16_t motion_profile_update(motion_profile_t* profile, int32_t current_pos);

// Verificar si el perfil está activo
bool motion_profile_is_active(motion_profile_t* profile);

// Resetear el perfil
void motion_profile_reset(motion_profile_t* profile);

// Obtener el tiempo actual en ms (para sincronización)
uint32_t motion_profile_get_millis(void);

void motion_profile_tick(void);

#endif // MOTION_PROFILE_H