#include "motion_profile.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdlib.h>
#include "../config/system_config.h"

// CAMBIO: Función para abs de int32_t
static int32_t abs32(int32_t x) {
	return (x < 0) ? -x : x;
}

static volatile uint32_t tick_counter = 0;

void motion_profile_tick(void) {
	tick_counter++;
}

void motion_profile_init(void) {
	tick_counter = 0;
}

uint32_t motion_profile_get_millis(void) {
	return tick_counter * 2;  // 500Hz = 2ms por tick
}

void motion_profile_setup(motion_profile_t* profile,
int32_t current_pos,
int32_t target_pos,
uint16_t max_speed,
uint16_t acceleration) {
	
	profile->start_position = current_pos;
	profile->target_position = target_pos;
	profile->total_steps = abs32(target_pos - current_pos);  // CAMBIO: usar abs32
	
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
	
	// Decidir tipo de perfil
	if (profile->total_steps < (2 * steps_to_max)) {
		// Perfil triangular
		profile->accel_steps = profile->total_steps / 2;
		profile->decel_steps = profile->total_steps - profile->accel_steps;
		profile->constant_steps = 0;
		
		// Calcular velocidad máxima que alcanzaremos
		uint64_t temp = (uint64_t)2 * accel * profile->accel_steps;
		uint32_t v_peak = 0;
		
		// Calcular raíz cuadrada
		uint32_t bit = 1UL << 15;
		while (bit > 0) {
			uint32_t test = v_peak + bit;
			if ((uint64_t)test * test <= temp) {
				v_peak = test;
			}
			bit >>= 1;
		}
		
		profile->target_speed = (v_peak < max_speed) ? v_peak : max_speed;
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
	
	int32_t steps_remaining = abs32(profile->target_position - current_pos);  // CAMBIO
	
	if (steps_remaining <= 1) {
		profile->current_speed = 0;
		profile->state = PROFILE_COMPLETED;
		return 0;
	}
	
	uint16_t target_speed;
	int32_t steps_done = abs32(current_pos - profile->start_position);  // CAMBIO
	
	// Resto del código igual...
	// Determinar fase del movimiento
	if (steps_remaining <= profile->decel_steps) {
		// FASE DE DECELERACIÓN
		profile->state = PROFILE_DECELERATING;
		
		if (steps_remaining > 2) {
			// v = sqrt(2 * a * d)
			uint64_t temp = (uint64_t)2 * profile->acceleration * steps_remaining;
			target_speed = 0;
			
			// Raíz cuadrada eficiente
			uint32_t bit = 1UL << 15;
			while (bit > 0) {
				uint32_t test = target_speed + bit;
				if ((uint64_t)test * test <= temp) {
					target_speed = test;
				}
				bit >>= 1;
			}
			
			if (target_speed < 50) target_speed = 50;
			} else {
			target_speed = 50;
		}
	}
	else if (steps_done < profile->accel_steps) {
		// FASE DE ACELERACIÓN
		profile->state = PROFILE_ACCELERATING;
		
		if (steps_done < 5) {
			target_speed = 100;
			} else {
			// v = sqrt(2 * a * d)
			uint64_t temp = (uint64_t)2 * profile->acceleration * steps_done;
			target_speed = 0;
			
			// Raíz cuadrada eficiente
			uint32_t bit = 1UL << 15;
			while (bit > 0) {
				uint32_t test = target_speed + bit;
				if ((uint64_t)test * test <= temp) {
					target_speed = test;
				}
				bit >>= 1;
			}
			
			if (target_speed > profile->target_speed) {
				target_speed = profile->target_speed;
			}
		}
	}
	else {
		// FASE CONSTANTE
		profile->state = PROFILE_CONSTANT;
		target_speed = profile->target_speed;
	}
	
	// Aplicar cambio gradual
	int16_t diff = (int16_t)target_speed - (int16_t)profile->current_speed;
	
	if (diff != 0) {
		uint16_t max_change = profile->acceleration / 500;
		
		if (max_change < 10) max_change = 10;
		
		if (diff > 0 && diff > max_change) {
			profile->current_speed += max_change;
			} else if (diff < 0 && -diff > max_change) {
			profile->current_speed -= max_change;
			} else {
			profile->current_speed = target_speed;
		}
	}
	
	if (profile->current_speed > profile->max_speed) {
		profile->current_speed = profile->max_speed;
	}
	
    // Evitar imponer velocidad mínima cuando estamos al final del movimiento
    if (steps_remaining > 1 && profile->current_speed < 50) {
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