#include "motion_profile.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdlib.h>
#include "../config/system_config.h"

static volatile uint32_t tick_counter = 0;

void motion_profile_tick(void) {
	tick_counter++;
}

void motion_profile_init(void) {
	tick_counter = 0;
}

uint32_t motion_profile_get_millis(void) {
	return tick_counter * 5;  // 200Hz = 5ms por tick
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
	profile->current_speed = 0;
	
	if (profile->total_steps == 0) {
		profile->state = PROFILE_IDLE;
		return;
	}
	
	// Calcular pasos para acelerar de 0 a max_speed
	uint32_t v_max = (uint32_t)max_speed;
	uint32_t accel = (uint32_t)acceleration;
	uint32_t steps_to_max = (v_max * v_max) / (2 * accel);
	
	// Limitar para evitar overflow
	if (steps_to_max > 100000L) steps_to_max = 100000L;
	
	// Decidir tipo de perfil
	if (profile->total_steps < (2 * steps_to_max)) {
		// Perfil triangular
		profile->accel_steps = profile->total_steps / 2;
		profile->decel_steps = profile->total_steps - profile->accel_steps;
		profile->constant_steps = 0;
		
		// Calcular velocidad máxima que alcanzaremos
		uint32_t v_peak_sq = 2 * accel * profile->accel_steps;
		uint32_t v_peak = 1;
		while (v_peak * v_peak < v_peak_sq && v_peak < max_speed) v_peak++;
		profile->target_speed = v_peak;
		} else {
		// Perfil trapezoidal
		profile->accel_steps = steps_to_max;
		profile->decel_steps = steps_to_max;
		profile->constant_steps = profile->total_steps - (2 * steps_to_max);
		profile->target_speed = max_speed;
	}
	
	profile->state = PROFILE_ACCELERATING;
	profile->last_update_ms = motion_profile_get_millis();
}

uint16_t motion_profile_update(motion_profile_t* profile, int32_t current_pos) {
	if (profile->state == PROFILE_IDLE || profile->state == PROFILE_COMPLETED) {
		return 0;
	}
	
	int32_t steps_remaining = abs(profile->target_position - current_pos);
	
	// Si llegamos EXACTAMENTE al objetivo
	if (steps_remaining == 0) {
		profile->current_speed = 0;
		profile->state = PROFILE_COMPLETED;
		return 0;
	}
	
	// Calcular velocidad objetivo basada en la posición
	uint16_t target_speed;
	int32_t steps_done = abs(current_pos - profile->start_position);
	
	// Determinar fase del movimiento
	if (steps_remaining <= profile->decel_steps) {
		// FASE DE DECELERACIÓN
		profile->state = PROFILE_DECELERATING;
		
		// CAMBIO: Cálculo más preciso para desaceleración
		if (steps_remaining > 2) {
			// v = sqrt(2 * a * d)
			uint32_t v_sq = 2UL * profile->acceleration * steps_remaining;
			uint32_t v = 0;
			
			// Calcular raíz cuadrada con más precisión
			uint32_t bit = 1UL << 30;
			while (bit > v_sq) bit >>= 2;
			
			while (bit != 0) {
				if (v_sq >= v + bit) {
					v_sq -= v + bit;
					v = (v >> 1) + bit;
					} else {
					v >>= 1;
				}
				bit >>= 2;
			}
			
			target_speed = v;
			
			// CAMBIO: Permitir velocidades muy bajas para desaceleración correcta
			if (target_speed < 50) target_speed = 50;
			} else {
			// Últimos 2 pasos - velocidad mínima
			target_speed = 50;
		}
	}
	else if (steps_done < profile->accel_steps) {
		// FASE DE ACELERACIÓN
		profile->state = PROFILE_ACCELERATING;
		
		// CAMBIO: Arranque desde velocidad muy baja
		if (steps_done < 5) {
			target_speed = 100;  // Arranque suave
			} else {
			// v = sqrt(2 * a * d)
			uint32_t v_sq = 2UL * profile->acceleration * steps_done;
			target_speed = 1;
			while (target_speed * target_speed < v_sq && target_speed < profile->target_speed) {
				target_speed++;
			}
		}
	}
	else {
		// FASE CONSTANTE
		profile->state = PROFILE_CONSTANT;
		target_speed = profile->target_speed;
	}
	
	// CAMBIO: Aplicar cambio más gradual
	int16_t diff = (int16_t)target_speed - (int16_t)profile->current_speed;
	
	if (diff > 0) {
		// Acelerando
		uint16_t max_inc = profile->acceleration / 100;  // Más suave
		if (max_inc < 5) max_inc = 5;
		if (max_inc > 100) max_inc = 100;
		
		if (diff > max_inc) {
			profile->current_speed += max_inc;
			} else {
			profile->current_speed = target_speed;
		}
		} else if (diff < 0) {
		// Decelerando - más agresivo
		uint16_t max_dec = profile->acceleration / 50;
		if (max_dec < 10) max_dec = 10;
		if (max_dec > 200) max_dec = 200;
		
		if (-diff > max_dec) {
			profile->current_speed -= max_dec;
			} else {
			profile->current_speed = target_speed;
		}
	}
	
	// Límites
	if (profile->current_speed > profile->max_speed) {
		profile->current_speed = profile->max_speed;
	}
	
	// CAMBIO: Asegurar velocidad mínima para que el timer funcione
	if (profile->current_speed < 50 && steps_remaining > 0) {
		profile->current_speed = 50;
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