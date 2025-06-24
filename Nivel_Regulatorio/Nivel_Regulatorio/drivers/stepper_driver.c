#include "stepper_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "../config/system_config.h"
#include <util/delay.h>
#include <stdlib.h>

// Variables globales para los ejes
static stepper_axis_t horizontal_axis = {0};
static stepper_axis_t vertical_axis = {0};
static volatile bool update_speeds_flag = false;

// Timer4 para actualización periódica de velocidades (100Hz)
ISR(TIMER4_COMPA_vect) {
	update_speeds_flag = true;
	motion_profile_tick();  // Incrementar contador para motion profile
}

// Función para calcular TOP value del timer basado en velocidad deseada
static uint16_t calculate_timer_top(uint16_t steps_per_second) {
	if (steps_per_second == 0) return 0xFFFF;
	return (F_CPU / (8UL * steps_per_second)) - 1;
}

// Función para actualizar velocidad del Timer1 (motores horizontales)
static void update_horizontal_speed(uint16_t speed) {
	if (speed == 0) {
		// Parar Timer1
		TCCR1B = 0;
		TIMSK1 &= ~(1 << OCIE1A);
		return;
	}
	
	uint16_t top_value = calculate_timer_top(speed);
	
	// Actualizar OCR1A sin detener el timer (cambio suave)
	OCR1A = top_value;
	OCR1B = top_value;
	
	// Si el timer no está corriendo, iniciarlo
	if ((TCCR1B & 0x07) == 0) {
		TCCR1A = 0;
		TCCR1B = (1 << WGM12) | (1 << CS11); // Modo CTC, prescaler 8
		TIMSK1 |= (1 << OCIE1A);
	}
}

// Función para actualizar velocidad del Timer3 (motor vertical)
static void update_vertical_speed(uint16_t speed) {
	if (speed == 0) {
		// Parar Timer3
		TCCR3B = 0;
		TIMSK3 &= ~(1 << OCIE3A);
		return;
	}
	
	uint16_t top_value = calculate_timer_top(speed);
	
	// Actualizar OCR3A sin detener el timer
	OCR3A = top_value;
	
	// Si el timer no está corriendo, iniciarlo
	if ((TCCR3B & 0x07) == 0) {
		TCCR3A = 0;
		TCCR3B = (1 << WGM32) | (1 << CS31); // Modo CTC, prescaler 8
		TIMSK3 |= (1 << OCIE3A);
	}
}

// ISR Timer1 - motores horizontales
ISR(TIMER1_COMPA_vect) {
	// Generar pulso manualmente
	PORTB |= (1 << 5);  // Pin 11 HIGH
	PORTB |= (1 << 6);  // Pin 12 HIGH
	
	_delay_us(2);
	
	PORTB &= ~(1 << 5); // Pin 11 LOW
	PORTB &= ~(1 << 6); // Pin 12 LOW
	
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
}

// ISR Timer3 - motor vertical
ISR(TIMER3_COMPA_vect) {
	// Generar pulso manualmente
	PORTE |= (1 << 3); // Pin 5 HIGH
	
	_delay_us(2);
	
	PORTE &= ~(1 << 3); // Pin 5 LOW
	
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
	
	// Configurar Timer4 para actualización de velocidades (100Hz)
	// Timer4 es de 16 bits en ATmega2560
	TCCR4A = 0;
	TCCR4B = (1 << WGM42) | (1 << CS42); // CTC mode, prescaler 256
	OCR4A = 624; // 16MHz / 256 / 625 = 100Hz
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

void stepper_set_speed(uint16_t h_speed, uint16_t v_speed) {
	if (h_speed > 0 && h_speed <= MAX_SPEED_H) {
		horizontal_axis.max_speed = h_speed;
	}
	if (v_speed > 0 && v_speed <= MAX_SPEED_V) {
		vertical_axis.max_speed = v_speed;
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

// Función para actualizar perfiles de velocidad
void stepper_update_profiles(void) {
	if (!update_speeds_flag) return;
	update_speeds_flag = false;
	
	// Actualizar perfil horizontal si está en movimiento
	if (motion_profile_is_active(&horizontal_axis.profile)) {
		uint16_t new_speed = motion_profile_update(&horizontal_axis.profile,
		horizontal_axis.current_position);
		if (new_speed != horizontal_axis.current_speed) {
			horizontal_axis.current_speed = new_speed;
			update_horizontal_speed(new_speed);
		}
	}
	
	// Actualizar perfil vertical si está en movimiento
	if (motion_profile_is_active(&vertical_axis.profile)) {
		uint16_t new_speed = motion_profile_update(&vertical_axis.profile,
		vertical_axis.current_position);
		if (new_speed != vertical_axis.current_speed) {
			vertical_axis.current_speed = new_speed;
			update_vertical_speed(new_speed);
		}
	}
}