#include "motion_profile.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdlib.h>
#include "../config/system_config.h"

// Usar el contador del Timer4 (50Hz)
static volatile uint32_t tick_counter = 0;

// Función llamada desde Timer4 para incrementar contador
void motion_profile_tick(void) {
	tick_counter++;
}

void motion_profile_init(void) {
	tick_counter = 0;
}

uint32_t motion_profile_get_millis(void) {
	// Convertir ticks de 50Hz a milisegundos (1 tick = 20ms)
	return tick_counter * 20;
}

// Función para calcular raíz cuadrada precisa
static uint32_t sqrt_precise(uint32_t value) {
	if (value == 0) return 0;
	if (value == 1) return 1;
	
	uint32_t x = value;
	uint32_t y = (x + 1) / 2;
	
	// Método de Newton-Raphson (máximo 10 iteraciones)
	for (int i = 0; i < 10 && y < x; i++) {
		x = y;
		y = (x + value / x) / 2;
	}
	
	return x;
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
	profile->current_speed = MIN_SPEED;
	
	if (profile->total_steps == 0) {
		profile->state = PROFILE_IDLE;
		return;
	}
	
	// Calcular distancia para acelerar desde MIN_SPEED hasta max_speed
	// d = (v_max² - v_min²) / (2*a)
	uint32_t v_max_sq = (uint32_t)max_speed * max_speed;
	uint32_t v_min_sq = (uint32_t)MIN_SPEED * MIN_SPEED;
	uint32_t accel_distance = (v_max_sq - v_min_sq) / (2UL * acceleration);
	
	// DECISIÓN CRÍTICA: ¿Trapezoidal o Triangular?
	uint32_t min_distance_for_trapezoid = 2 * accel_distance;
	
	if (profile->total_steps <= min_distance_for_trapezoid) {
		// **PERFIL TRIANGULAR** - No hay espacio para velocidad constante
		profile->accel_steps = profile->total_steps / 2;
		profile->decel_steps = profile->total_steps - profile->accel_steps;
		profile->constant_steps = 0;
		
		// Calcular velocidad máxima alcanzable en perfil triangular
		// v_max_triangular = sqrt(v_min² + 2*a*d_accel)
		uint32_t max_reachable_sq = v_min_sq + 2UL * acceleration * profile->accel_steps;
		profile->target_speed = sqrt_precise(max_reachable_sq);
		
		// Nunca exceder la velocidad máxima configurada
		if (profile->target_speed > max_speed) {
			profile->target_speed = max_speed;
		}
		} else {
		// **PERFIL TRAPEZOIDAL** - Hay espacio para velocidad constante
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
	
	// Calcular distancias - CLAVE PARA EL FUNCIONAMIENTO CORRECTO
	int32_t distance_from_start = abs(current_pos - profile->start_position);
	int32_t remaining_steps = abs(profile->target_position - current_pos);
	
	// Si llegamos al objetivo
	if (remaining_steps == 0) {
		profile->current_speed = 0;
		profile->state = PROFILE_COMPLETED;
		return 0;
	}
	
	uint16_t new_speed = profile->current_speed;
	
	// **LÓGICA DE ESTADOS CLARA Y ROBUSTA**
	switch (profile->state) {
		
		case PROFILE_ACCELERATING: {
			// ¿Debemos pasar a deceleración YA?
			if (remaining_steps <= profile->decel_steps) {
				profile->state = PROFILE_DECELERATING;
				// Calcular velocidad de deceleración inmediatamente
				goto calculate_decel_speed;
			}
			
			// ¿Llegamos al final de la aceleración?
			if (distance_from_start >= profile->accel_steps) {
				if (profile->constant_steps > 0) {
					// Hay fase constante
					profile->state = PROFILE_CONSTANT;
					new_speed = profile->target_speed;
					} else {
					// No hay fase constante, ir directo a deceleración
					profile->state = PROFILE_DECELERATING;
					goto calculate_decel_speed;
				}
				} else {
				// Continuar acelerando
				// v = sqrt(v_min² + 2*a*d)
				uint32_t v_min_sq = (uint32_t)MIN_SPEED * MIN_SPEED;
				uint32_t speed_sq = v_min_sq + 2UL * profile->acceleration * distance_from_start;
				new_speed = sqrt_precise(speed_sq);
				
				// Limitar a velocidad objetivo
				if (new_speed > profile->target_speed) {
					new_speed = profile->target_speed;
				}
			}
			break;
		}
		
		case PROFILE_CONSTANT: {
			// ¿Es hora de decelerar?
			if (remaining_steps <= profile->decel_steps) {
				profile->state = PROFILE_DECELERATING;
				goto calculate_decel_speed;
				} else {
				// Mantener velocidad constante
				new_speed = profile->target_speed;
			}
			break;
		}
		
		case PROFILE_DECELERATING: {
			calculate_decel_speed:
			// Calcular velocidad para decelerar suavemente hasta el final
			if (remaining_steps > 3) {
				// v = sqrt(v_min² + 2*a*d_restante)
				uint32_t v_min_sq = (uint32_t)MIN_SPEED * MIN_SPEED;
				uint32_t speed_sq = v_min_sq + 2UL * profile->acceleration * remaining_steps;
				new_speed = sqrt_precise(speed_sq);
				
				// Nunca bajar de velocidad mínima
				if (new_speed < MIN_SPEED) {
					new_speed = MIN_SPEED;
				}
				} else {
				// Muy cerca del objetivo, usar velocidad mínima
				new_speed = MIN_SPEED;
			}
			break;
		}
		
		default:
		new_speed = MIN_SPEED;
		break;
	}
	
	// **FILTRO SUAVE** - Evitar cambios abruptos
	int16_t speed_diff = (int16_t)new_speed - (int16_t)profile->current_speed;
	const uint16_t MAX_SPEED_CHANGE = 150; // Permitir cambios un poco más grandes
	
	if (speed_diff > MAX_SPEED_CHANGE) {
		new_speed = profile->current_speed + MAX_SPEED_CHANGE;
		} else if (speed_diff < -MAX_SPEED_CHANGE) {
		new_speed = profile->current_speed - MAX_SPEED_CHANGE;
	}
	
	// Aplicar límites finales
	if (new_speed < MIN_SPEED) new_speed = MIN_SPEED;
	if (new_speed > profile->target_speed) new_speed = profile->target_speed;
	
	profile->current_speed = new_speed;
	return new_speed;
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