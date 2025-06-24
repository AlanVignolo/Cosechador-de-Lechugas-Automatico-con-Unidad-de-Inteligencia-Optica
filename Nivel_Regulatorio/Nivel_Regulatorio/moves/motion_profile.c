#include "motion_profile.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdlib.h>
#include "../config/system_config.h"

// Usar el contador del Timer4 (100Hz) en lugar de Timer2
static volatile uint32_t tick_counter = 0;

// Función llamada desde Timer4 para incrementar contador
void motion_profile_tick(void) {
	tick_counter++;
}

void motion_profile_init(void) {
	// No inicializar ningún timer aquí
	// Timer4 ya se inicializa en stepper_init()
	tick_counter = 0;
}

uint32_t motion_profile_get_millis(void) {
	// Convertir ticks de 100Hz a milisegundos (1 tick = 10ms)
	return tick_counter * 10;
}

void motion_profile_setup(motion_profile_t* profile,
int32_t current_pos,
int32_t target_pos,
uint16_t max_speed,
uint16_t acceleration) {
	
	profile->start_position = current_pos;
	profile->target_position = target_pos;
	profile->total_steps = abs(target_pos - current_pos);
	
	profile->max_speed = max_speed;
	profile->acceleration = acceleration;
	profile->current_speed = MIN_SPEED;  // Empezar con velocidad mínima
	profile->target_speed = max_speed;
	
	if (profile->total_steps == 0) {
		profile->state = PROFILE_IDLE;
		return;
	}
	
	// Calcular distancia necesaria para acelerar hasta velocidad máxima
	uint32_t accel_distance = ((uint32_t)max_speed * max_speed) / (2 * acceleration);
	
	// Si la distancia total es menor que aceleración + deceleración, usar perfil triangular
	if (profile->total_steps < (2 * accel_distance)) {
		// Perfil triangular
		profile->accel_steps = profile->total_steps / 2;
		profile->decel_steps = profile->total_steps - profile->accel_steps;
		profile->constant_steps = 0;
		
		// Calcular velocidad máxima alcanzable
		uint32_t max_reached_squared = 2UL * acceleration * profile->accel_steps;
		uint16_t max_reached = MIN_SPEED;
		
		// Calcular raíz cuadrada aproximada
		while ((uint32_t)max_reached * max_reached < max_reached_squared) {
			max_reached++;
		}
		profile->target_speed = max_reached;
		
		} else {
		// Perfil trapezoidal
		profile->accel_steps = accel_distance;
		profile->decel_steps = accel_distance;
		profile->constant_steps = profile->total_steps - profile->accel_steps - profile->decel_steps;
		profile->target_speed = max_speed;
	}
	
	profile->state = PROFILE_ACCELERATING;
	profile->last_update_ms = motion_profile_get_millis();
}

uint16_t motion_profile_update(motion_profile_t* profile, int32_t current_pos) {
	if (profile->state == PROFILE_IDLE || profile->state == PROFILE_COMPLETED) {
		return 0;
	}
	
	// Calcular distancia recorrida desde el inicio
	int32_t distance_traveled = abs(current_pos - profile->start_position);
	int32_t distance_to_target = abs(profile->target_position - current_pos);
	
	// Si llegamos al objetivo
	if (distance_to_target == 0) {
		profile->current_speed = 0;
		profile->state = PROFILE_COMPLETED;
		return 0;
	}
	
	// Determinar en qué fase estamos basado en la distancia
	if (distance_traveled < profile->accel_steps) {
		// Fase de aceleración
		profile->state = PROFILE_ACCELERATING;
		
		// Calcular velocidad basada en la distancia recorrida
		// v = sqrt(2 * a * d) + v_inicial
		uint32_t speed_squared = 2UL * profile->acceleration * distance_traveled + (uint32_t)MIN_SPEED * MIN_SPEED;
		uint16_t new_speed = MIN_SPEED;
		
		while ((uint32_t)new_speed * new_speed < speed_squared) {
			new_speed++;
		}
		
		if (new_speed > profile->target_speed) {
			new_speed = profile->target_speed;
		}
		
		profile->current_speed = new_speed;
		
		} else if (distance_to_target <= profile->decel_steps) {
		// Fase de deceleración
		profile->state = PROFILE_DECELERATING;
		
		// Calcular velocidad necesaria para detenerse
		if (distance_to_target > 5) {  // Mantener velocidad mínima hasta muy cerca
			uint32_t target_speed_squared = 2UL * profile->acceleration * distance_to_target;
			uint16_t target_speed = MIN_SPEED;
			
			while ((uint32_t)target_speed * target_speed < target_speed_squared) {
				target_speed++;
			}
			
			if (target_speed < MIN_SPEED) {
				target_speed = MIN_SPEED;
			}
			
			profile->current_speed = target_speed;
			} else {
			profile->current_speed = MIN_SPEED;
		}
		
		} else {
		// Fase de velocidad constante
		profile->state = PROFILE_CONSTANT;
		profile->current_speed = profile->target_speed;
	}
	
	return profile->current_speed;
}

bool motion_profile_is_active(motion_profile_t* profile) {
	return (profile->state != PROFILE_IDLE && profile->state != PROFILE_COMPLETED);
}

void motion_profile_reset(motion_profile_t* profile) {
	profile->state = PROFILE_IDLE;
	profile->current_speed = 0;
	profile->target_speed = 0;
	profile->total_steps = 0;
}