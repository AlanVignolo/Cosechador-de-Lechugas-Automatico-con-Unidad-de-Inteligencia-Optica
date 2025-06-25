#include "stepper_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "../config/system_config.h"
#include <stdlib.h>

// Variables globales para los ejes (accesibles para debugging)
stepper_axis_t horizontal_axis = {0};
stepper_axis_t vertical_axis = {0};
static volatile bool update_speeds_flag = false;

// Variables para alternar HIGH/LOW en interrupciones
static volatile bool h_step_state = false;  // false=LOW, true=HIGH
static volatile bool v_step_state = false;  // false=LOW, true=HIGH

// Timer4 para actualización periódica de velocidades (50Hz - reducido de 100Hz)
ISR(TIMER4_COMPA_vect) {
	update_speeds_flag = true;
	motion_profile_tick();  // Incrementar contador para motion profile
}

// Función para calcular TOP value del timer basado en velocidad deseada
// IMPORTANTE: Calculamos para DOBLE frecuencia (para alternar HIGH/LOW)
static uint16_t calculate_timer_top(uint16_t steps_per_second) {
	if (steps_per_second == 0) return 0xFFFF;
	// Multiplicar por 2 porque cada paso necesita 2 interrupciones (HIGH + LOW)
	uint32_t top_value = (F_CPU / (8UL * steps_per_second * 2)) - 1;
	
	// Limitar a rango de 16 bits
	if (top_value > 0xFFFF) top_value = 0xFFFF;
	
	return (uint16_t)top_value;
}

// Función para actualizar velocidad del Timer1 (motores horizontales)
static void update_horizontal_speed(uint16_t speed) {
	if (speed == 0) {
		// Parar Timer1
		TCCR1B = 0;
		TIMSK1 &= ~(1 << OCIE1A);
		// Asegurar que los pines queden en LOW
		PORTB &= ~((1 << 5) | (1 << 6));  // Pins 11, 12 LOW
		h_step_state = false;
		return;
	}
	
	// Verificar velocidad mínima
	if (speed < MIN_SPEED) speed = MIN_SPEED;
	
	uint16_t top_value = calculate_timer_top(speed);
	
	// Actualizar OCR1A sin detener el timer (cambio suave)
	OCR1A = top_value;
	OCR1B = top_value;
	
	// Si el timer no está corriendo, iniciarlo
	if ((TCCR1B & 0x07) == 0) {
		TCCR1A = 0;
		TCCR1B = (1 << WGM12) | (1 << CS11); // Modo CTC, prescaler 8
		TIMSK1 |= (1 << OCIE1A);
		h_step_state = false;  // Empezar con LOW
	}
}

// Función para actualizar velocidad del Timer3 (motor vertical)
static void update_vertical_speed(uint16_t speed) {
	if (speed == 0) {
		// Parar Timer3
		TCCR3B = 0;
		TIMSK3 &= ~(1 << OCIE3A);
		// Asegurar que el pin quede en LOW
		PORTE &= ~(1 << 3);  // Pin 5 LOW
		v_step_state = false;
		return;
	}
	
	// Verificar velocidad mínima
	if (speed < MIN_SPEED) speed = MIN_SPEED;
	
	uint16_t top_value = calculate_timer_top(speed);
	
	// Actualizar OCR3A sin detener el timer
	OCR3A = top_value;
	
	// Si el timer no está corriendo, iniciarlo
	if ((TCCR3B & 0x07) == 0) {
		TCCR3A = 0;
		TCCR3B = (1 << WGM32) | (1 << CS31); // Modo CTC, prescaler 8
		TIMSK3 |= (1 << OCIE3A);
		v_step_state = false;  // Empezar con LOW
	}
}

// ISR Timer1 - motores horizontales (SIN DELAYS)
ISR(TIMER1_COMPA_vect) {
	// Alternar estado HIGH/LOW
	if (h_step_state) {
		// Era HIGH, ahora poner LOW
		PORTB &= ~((1 << 5) | (1 << 6));  // Pins 11, 12 LOW
		h_step_state = false;
		
		// Solo contar pasos cuando terminamos el pulso (flanco descendente)
		// Actualizar posición
		if (horizontal_axis.direction) {
			horizontal_axis.current_position++;
			} else {
			horizontal_axis.current_position--;
		}
		
		// Verificar si llegamos al objetivo
		if (horizontal_axis.current_position == horizontal_axis.target_position) {
			update_horizontal_speed(0);
			horizontal_axis.state = STEPPER_IDLE;
			motion_profile_reset(&horizontal_axis.profile);
		}
		} else {
		// Era LOW, ahora poner HIGH
		PORTB |= (1 << 5) | (1 << 6);     // Pins 11, 12 HIGH
		h_step_state = true;
	}
}

// ISR Timer3 - motor vertical (SIN DELAYS)
ISR(TIMER3_COMPA_vect) {
	// Alternar estado HIGH/LOW
	if (v_step_state) {
		// Era HIGH, ahora poner LOW
		PORTE &= ~(1 << 3);  // Pin 5 LOW
		v_step_state = false;
		
		// Solo contar pasos cuando terminamos el pulso (flanco descendente)
		// Actualizar posición
		if (vertical_axis.direction) {
			vertical_axis.current_position++;
			} else {
			vertical_axis.current_position--;
		}
		
		// Verificar si llegamos al objetivo
		if (vertical_axis.current_position == vertical_axis.target_position) {
			update_vertical_speed(0);
			vertical_axis.state = STEPPER_IDLE;
			motion_profile_reset(&vertical_axis.profile);
		}
		} else {
		// Era LOW, ahora poner HIGH
		PORTE |= (1 << 3);   // Pin 5 HIGH
		v_step_state = true;
	}
}

void stepper_init(void) {
	// Configurar pines como salidas
	// Motor Horizontal 1
	DDRB |= (1 << 5);  // Pin 11 (PB5)
	DDRA |= (1 << 0);  // Pin 22 (PA0)
	DDRA |= (1 << 1);  // Pin 23 (PA1)
	
	// Motor Horizontal 2
	DDRB |= (1 << 6);  // Pin 12 (PB6)
	DDRA |= (1 << 2);  // Pin 24 (PA2)
	DDRA |= (1 << 3);  // Pin 25 (PA3)
	
	// Motor Vertical
	DDRE |= (1 << 3);  // Pin 5 (PE3)
	DDRA |= (1 << 4);  // Pin 26 (PA4)
	DDRA |= (1 << 5);  // Pin 27 (PA5)
	
	// Asegurar que todos los pines STEP empiecen en LOW
	PORTB &= ~((1 << 5) | (1 << 6));  // Pins 11, 12 LOW
	PORTE &= ~(1 << 3);               // Pin 5 LOW
	
	// Inicializar estados de alternancia
	h_step_state = false;
	v_step_state = false;
	
	// Inicializar módulo de motion profile
	motion_profile_init();
	
	// Inicializar estados por defecto
	horizontal_axis.max_speed = MAX_SPEED_H;
	horizontal_axis.acceleration = ACCEL_H;
	horizontal_axis.current_speed = 0;
	horizontal_axis.state = STEPPER_IDLE;
	
	vertical_axis.max_speed = MAX_SPEED_V;
	vertical_axis.acceleration = ACCEL_V;
	vertical_axis.current_speed = 0;
	vertical_axis.state = STEPPER_IDLE;
	
	// Deshabilitar motores por defecto
	stepper_enable_motors(false, false);
	
	// Configurar Timer4 para actualización de velocidades (50Hz - REDUCIDO)
	// Timer4 es de 16 bits en ATmega2560
	TCCR4A = 0;
	TCCR4B = (1 << WGM42) | (1 << CS42); // CTC mode, prescaler 256
	OCR4A = 1249; // 16MHz / 256 / 1250 = 50Hz (era 624 para 100Hz)
	TIMSK4 = (1 << OCIE4A);
}

void stepper_enable_motors(bool h_enable, bool v_enable) {
	// ENABLE es activo bajo en TB6600
	if (h_enable) {
		PORTA &= ~((1 << 1) | (1 << 3));  // Pins 23, 25 LOW = enabled
		horizontal_axis.enabled = true;
		} else {
		PORTA |= (1 << 1) | (1 << 3);     // Pins 23, 25 HIGH = disabled
		horizontal_axis.enabled = false;
	}
	
	if (v_enable) {
		PORTA &= ~(1 << 5);               // Pin 27 LOW = enabled
		vertical_axis.enabled = true;
		} else {
		PORTA |= (1 << 5);                // Pin 27 HIGH = disabled
		vertical_axis.enabled = false;
	}
}

void stepper_move_relative(int32_t h_steps, int32_t v_steps) {
	stepper_move_absolute(
	horizontal_axis.current_position + h_steps,
	vertical_axis.current_position + v_steps
	);
}

void stepper_move_absolute(int32_t h_pos, int32_t v_pos) {
	// Parar cualquier movimiento previo
	stepper_stop_all();
	
	// Configurar objetivos
	horizontal_axis.target_position = h_pos;
	vertical_axis.target_position = v_pos;
	
	// Configurar direcciones
	if (h_pos > horizontal_axis.current_position) {
		horizontal_axis.direction = true;
		PORTA &= ~(1 << 0);  // DIR1 LOW
		PORTA |= (1 << 2);   // DIR2 HIGH
		} else if (h_pos < horizontal_axis.current_position) {
		horizontal_axis.direction = false;
		PORTA |= (1 << 0);   // DIR1 HIGH
		PORTA &= ~(1 << 2);  // DIR2 LOW
	}

	if (v_pos > vertical_axis.current_position) {
		vertical_axis.direction = true;
		PORTA &= ~(1 << 4);  // DIR pin LOW
		} else if (v_pos < vertical_axis.current_position) {
		vertical_axis.direction = false;
		PORTA |= (1 << 4);   // DIR pin HIGH
	}
	
	// Configurar perfiles de movimiento si hay movimiento que hacer
	if (h_pos != horizontal_axis.current_position && horizontal_axis.enabled) {
		motion_profile_setup(&horizontal_axis.profile,
		horizontal_axis.current_position,
		h_pos,
		horizontal_axis.max_speed,
		horizontal_axis.acceleration);
		horizontal_axis.state = STEPPER_MOVING;
		horizontal_axis.current_speed = MIN_SPEED;
		// Iniciar movimiento con velocidad mínima
		update_horizontal_speed(MIN_SPEED);
	}
	
	if (v_pos != vertical_axis.current_position && vertical_axis.enabled) {
		motion_profile_setup(&vertical_axis.profile,
		vertical_axis.current_position,
		v_pos,
		vertical_axis.max_speed,
		vertical_axis.acceleration);
		vertical_axis.state = STEPPER_MOVING;
		vertical_axis.current_speed = MIN_SPEED;
		// Iniciar movimiento con velocidad mínima
		update_vertical_speed(MIN_SPEED);
	}
}

void stepper_stop_all(void) {
	// Parar timers
	update_horizontal_speed(0);
	update_vertical_speed(0);
	
	// Resetear estados y perfiles
	horizontal_axis.state = STEPPER_IDLE;
	vertical_axis.state = STEPPER_IDLE;
	motion_profile_reset(&horizontal_axis.profile);
	motion_profile_reset(&vertical_axis.profile);
}

bool stepper_is_moving(void) {
	return (horizontal_axis.state != STEPPER_IDLE ||
	vertical_axis.state != STEPPER_IDLE);
}

void stepper_get_position(int32_t* h_pos, int32_t* v_pos) {
	*h_pos = horizontal_axis.current_position;
	*v_pos = vertical_axis.current_position;
}

void stepper_set_position(int32_t h_pos, int32_t v_pos) {
	horizontal_axis.current_position = h_pos;
	vertical_axis.current_position = v_pos;
}

// Función para actualizar perfiles de velocidad (MENOS FRECUENTE)
void stepper_update_profiles(void) {
	if (!update_speeds_flag) return;
	update_speeds_flag = false;
	
	// Actualizar perfil horizontal si está en movimiento
	if (motion_profile_is_active(&horizontal_axis.profile)) {
		uint16_t new_speed = motion_profile_update(&horizontal_axis.profile,
		horizontal_axis.current_position);
		
		// Solo cambiar velocidad si hay diferencia significativa (filtro adicional)
		if (abs((int16_t)new_speed - (int16_t)horizontal_axis.current_speed) > 10) {
			horizontal_axis.current_speed = new_speed;
			update_horizontal_speed(new_speed);
		}
	}
	
	// Actualizar perfil vertical si está en movimiento
	if (motion_profile_is_active(&vertical_axis.profile)) {
		uint16_t new_speed = motion_profile_update(&vertical_axis.profile,
		vertical_axis.current_position);
		
		// Solo cambiar velocidad si hay diferencia significativa (filtro adicional)
		if (abs((int16_t)new_speed - (int16_t)vertical_axis.current_speed) > 10) {
			vertical_axis.current_speed = new_speed;
			update_vertical_speed(new_speed);
		}
	}
	
	// Llamar función de debugging
	extern void debug_motion_profiles(void);
}