#include "motion_profile_simple.h"
#include <stdlib.h>

void simple_profile_init(simple_profile_t* profile) {
	profile->total_steps = 0;
	profile->steps_done = 0;
	profile->cruise_speed = 0;
	profile->current_speed = SPEED_START;
	profile->active = false;
}

void simple_profile_calculate(simple_profile_t* profile, int32_t steps, uint16_t cruise_speed) {
	profile->total_steps = abs(steps);
	profile->steps_done = 0;
	profile->cruise_speed = cruise_speed;
	profile->current_speed = SPEED_START;
	profile->active = true;

	// Usar distancias fijas de aceleración/desaceleración
	// Esto garantiza aceleraciones constantes

	if (profile->total_steps >= MIN_STEPS_FOR_TRAPEZOID) {
		// Movimiento largo - perfil trapezoidal completo
		// Aceleraciones y desaceleraciones con distancias fijas
		// La zona de crucero se ajusta según la distancia total
		profile->accel_soft_end = ACCEL_SOFT_STEPS;
		profile->accel_hard_end = ACCEL_SOFT_STEPS + ACCEL_HARD_STEPS;
		profile->decel_soft_start = profile->total_steps - DECEL_SOFT_STEPS;
		profile->decel_hard_start = profile->decel_soft_start - DECEL_HARD_STEPS;

	} else if (profile->total_steps >= 100) {
		// Movimiento medio - reducir velocidad crucero y ajustar distancias proporcionalmente
		profile->cruise_speed = (cruise_speed * 2) / 3;

		// Escalar las distancias de aceleración/desaceleración proporcionalmente
		float scale = (float)profile->total_steps / MIN_STEPS_FOR_TRAPEZOID;

		profile->accel_soft_end = (int32_t)(ACCEL_SOFT_STEPS * scale);
		profile->accel_hard_end = profile->accel_soft_end + (int32_t)(ACCEL_HARD_STEPS * scale);
		profile->decel_soft_start = profile->total_steps - (int32_t)(DECEL_SOFT_STEPS * scale);
		profile->decel_hard_start = profile->decel_soft_start - (int32_t)(DECEL_HARD_STEPS * scale);

	} else {
		// Movimiento muy corto - perfil simplificado
		profile->cruise_speed = SPEED_LOW;
		profile->accel_soft_end = profile->total_steps / 4;
		profile->accel_hard_end = profile->total_steps / 2;
		profile->decel_hard_start = profile->total_steps / 2;
		profile->decel_soft_start = (profile->total_steps * 3) / 4;
	}

	// Verificar que haya espacio para velocidad crucero
	if (profile->accel_hard_end >= profile->decel_hard_start) {
		// No hay espacio para velocidad crucero - perfil triangular
		uint32_t mid_point = profile->total_steps / 2;
		profile->accel_hard_end = mid_point;
		profile->decel_hard_start = mid_point;
	}
}

uint16_t simple_profile_get_speed(simple_profile_t* profile) {
	if (!profile->active) return 0;

	// Determinar velocidad según la zona actual
	if (profile->steps_done < profile->accel_soft_end) {
		// Zona 1: Aceleración suave - rampa lineal desde START a LOW
		int32_t progress = profile->steps_done;
		int32_t zone_length = profile->accel_soft_end;

		if (zone_length > 0) {
			profile->current_speed = SPEED_START +
			((SPEED_LOW - SPEED_START) * progress) / zone_length;
		}
	}
	else if (profile->steps_done < profile->accel_hard_end) {
		// Zona 2: Aceleración fuerte - rampa lineal desde LOW a CRUISE
		int32_t progress = profile->steps_done - profile->accel_soft_end;
		int32_t zone_length = profile->accel_hard_end - profile->accel_soft_end;

		if (zone_length > 0) {
			profile->current_speed = SPEED_LOW +
			((profile->cruise_speed - SPEED_LOW) * progress) / zone_length;
		}
	}
	else if (profile->steps_done < profile->decel_hard_start) {
		// Zona 3: Velocidad crucero constante
		profile->current_speed = profile->cruise_speed;
	}
	else if (profile->steps_done < profile->decel_soft_start) {
		// Zona 4: Desaceleración fuerte - rampa lineal desde CRUISE a LOW
		int32_t progress = profile->steps_done - profile->decel_hard_start;
		int32_t zone_length = profile->decel_soft_start - profile->decel_hard_start;

		if (zone_length > 0) {
			profile->current_speed = profile->cruise_speed -
			((profile->cruise_speed - SPEED_LOW) * progress) / zone_length;
		}
	}
	else {
		// Zona 5: Desaceleración suave - rampa lineal desde LOW a START
		int32_t progress = profile->steps_done - profile->decel_soft_start;
		int32_t zone_length = profile->total_steps - profile->decel_soft_start;

		if (zone_length > 0) {
			profile->current_speed = SPEED_LOW -
			((SPEED_LOW - SPEED_START) * progress) / zone_length;
			} else {
			profile->current_speed = SPEED_START;
		}
	}

	// Limitar velocidad a rangos seguros
	if (profile->current_speed < SPEED_START) {
		profile->current_speed = SPEED_START;
	}
	if (profile->current_speed > profile->cruise_speed) {
		profile->current_speed = profile->cruise_speed;
	}

	return profile->current_speed;
}

void simple_profile_stop(simple_profile_t* profile) {
	profile->active = false;
	profile->current_speed = SPEED_START;
	profile->steps_done = 0;
}
