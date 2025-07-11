#include "stepper_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "../config/system_config.h"
#include <stdlib.h>
#include "../limits/limit_switch.h"

// Variables para modo calibración
static bool calibration_mode = false;
static int32_t calibration_step_counter = 0;

// Variables globales para los ejes (accesibles para debugging)
stepper_axis_t horizontal_axis = {0};
stepper_axis_t vertical_axis = {0};
static volatile bool update_speeds_flag = false;

// Variables para alternar HIGH/LOW en interrupciones
static volatile bool h_step_state = false;  // false=LOW, true=HIGH
static volatile bool v_step_state = false;  // false=LOW, true=HIGH

static int32_t abs32(int32_t x) {
	return (x < 0) ? -x : x;
}

// Timer4 para actualización periódica de velocidades (200Hz)
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
	
	// CAMBIO: No forzar velocidad mínima
	// if (speed < MIN_SPEED) speed = MIN_SPEED;
	
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
	
	// CAMBIO: No forzar velocidad mínima
	// if (speed < MIN_SPEED) speed = MIN_SPEED;
	
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
	if (h_step_state) {
		PORTB &= ~((1 << 5) | (1 << 6));
		h_step_state = false;
		
		if (horizontal_axis.direction) {
			horizontal_axis.current_position++;
			} else {
			horizontal_axis.current_position--;
		}
		
		if (calibration_mode) {
			calibration_step_counter++;
		}
		
		if (horizontal_axis.current_position == horizontal_axis.target_position) {
			update_horizontal_speed(0);
			horizontal_axis.state = STEPPER_IDLE;
			motion_profile_reset(&horizontal_axis.profile);
			
			if (vertical_axis.state == STEPPER_IDLE) {
				char msg[64];
				snprintf(msg, sizeof(msg), "STEPPER_MOVE_COMPLETED:%ld,%ld",
				horizontal_axis.current_position, vertical_axis.current_position);
				uart_send_response(msg);
			}
			stepper_stop_horizontal();
		}
		} else {
		PORTB |= (1 << 5) | (1 << 6);
		h_step_state = true;
	}
}

ISR(TIMER3_COMPA_vect) {
	if (v_step_state) {
		PORTE &= ~(1 << 3);
		v_step_state = false;
		
		if (vertical_axis.direction) {
			vertical_axis.current_position++;
			} else {
			vertical_axis.current_position--;
		}
		
		if (calibration_mode) {
			calibration_step_counter++;
		}
		
		if (vertical_axis.current_position == vertical_axis.target_position) {
			update_vertical_speed(0);
			vertical_axis.state = STEPPER_IDLE;
			motion_profile_reset(&vertical_axis.profile);
			
			if (horizontal_axis.state == STEPPER_IDLE) {
				char msg[64];
				snprintf(msg, sizeof(msg), "STEPPER_MOVE_COMPLETED:%ld,%ld",
				horizontal_axis.current_position, vertical_axis.current_position);
				uart_send_response(msg);
			}
			stepper_stop_vertical();
		}
		} else {
		PORTE |= (1 << 3);
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
	
	// Inicializar módulo de fines de carrera
	limit_switch_init();
	
	// Inicializar estados por defecto
	horizontal_axis.max_speed = MAX_SPEED_H;
	horizontal_axis.acceleration = ACCEL_H;
	horizontal_axis.current_speed = 0;
	horizontal_axis.state = STEPPER_IDLE;
	
	vertical_axis.max_speed = MAX_SPEED_V;
	vertical_axis.acceleration = ACCEL_V;
	vertical_axis.current_speed = 0;
	vertical_axis.state = STEPPER_IDLE;
	
	// Configurar Timer4 para actualización de velocidades (200Hz)
	// Timer4 es de 16 bits en ATmega2560
    TCCR4A = 0;
    TCCR4B = (1 << WGM42) | (1 << CS42); // CTC mode, prescaler 256
    OCR4A = 124; // 16MHz / 256 / 125 = 500Hz (era 311 para 200Hz)
    TIMSK4 = (1 << OCIE4A);

	// Habilitar motores por defecto
	stepper_enable_motors(true, true);
}

void stepper_stop_horizontal(void) {
	update_horizontal_speed(0);
	horizontal_axis.state = STEPPER_IDLE;
	horizontal_axis.target_position = horizontal_axis.current_position;
	motion_profile_reset(&horizontal_axis.profile);
}

void stepper_stop_vertical(void) {
	update_vertical_speed(0);
	vertical_axis.state = STEPPER_IDLE;
	vertical_axis.target_position = vertical_axis.current_position;
	motion_profile_reset(&vertical_axis.profile);
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
	stepper_stop_all();
	
	horizontal_axis.target_position = h_pos;
	vertical_axis.target_position = v_pos;
	
	int32_t h_distance = abs32(h_pos - horizontal_axis.current_position);
	int32_t v_distance = abs32(v_pos - vertical_axis.current_position);
	
	if (h_pos > horizontal_axis.current_position) {
		horizontal_axis.direction = true;
		PORTA &= ~(1 << 0);
		PORTA |= (1 << 2);
		} else if (h_pos < horizontal_axis.current_position) {
		horizontal_axis.direction = false;
		PORTA |= (1 << 0);
		PORTA &= ~(1 << 2);
	}

	if (v_pos > vertical_axis.current_position) {
		vertical_axis.direction = true;
		PORTA &= ~(1 << 4);
		} else if (v_pos < vertical_axis.current_position) {
		vertical_axis.direction = false;
		PORTA |= (1 << 4);
	}
	
	uint16_t h_speed_adjusted = horizontal_axis.max_speed;
	uint16_t v_speed_adjusted = vertical_axis.max_speed;
	
	if (h_distance > 0 && v_distance > 0 && horizontal_axis.enabled && vertical_axis.enabled) {
		if (h_distance > v_distance) {
			v_speed_adjusted = (uint32_t)horizontal_axis.max_speed * v_distance / h_distance;
			h_speed_adjusted = horizontal_axis.max_speed;
			
			if (v_speed_adjusted < 1000) v_speed_adjusted = 1000;
			
			if (v_speed_adjusted > vertical_axis.max_speed) {
				h_speed_adjusted = (uint32_t)horizontal_axis.max_speed * vertical_axis.max_speed / v_speed_adjusted;
				v_speed_adjusted = vertical_axis.max_speed;
			}
			} else if (v_distance > h_distance) {
			h_speed_adjusted = (uint32_t)vertical_axis.max_speed * h_distance / v_distance;
			v_speed_adjusted = vertical_axis.max_speed;
			
			if (h_speed_adjusted < 1000) h_speed_adjusted = 1000;
			
			if (h_speed_adjusted > horizontal_axis.max_speed) {
				v_speed_adjusted = (uint32_t)vertical_axis.max_speed * horizontal_axis.max_speed / h_speed_adjusted;
				h_speed_adjusted = horizontal_axis.max_speed;
			}
		}
	}
	
	bool movement_started = false;
	
	if (h_distance > 0 && horizontal_axis.enabled) {
		bool h_dir = (h_pos > horizontal_axis.current_position);
		if (!limit_switch_check_h_movement(h_dir)) {
			horizontal_axis.target_position = horizontal_axis.current_position;
			h_distance = 0;
			} else {
			motion_profile_setup(&horizontal_axis.profile,
			horizontal_axis.current_position,
			h_pos,
			h_speed_adjusted,
			horizontal_axis.acceleration);
			horizontal_axis.state = STEPPER_MOVING;
			horizontal_axis.current_speed = 0;
			movement_started = true;
		}
	}
	
	if (v_distance > 0 && vertical_axis.enabled) {
		bool v_dir = (v_pos > vertical_axis.current_position);
		if (!limit_switch_check_v_movement(v_dir)) {
			vertical_axis.target_position = vertical_axis.current_position;
			v_distance = 0;
			} else {
			motion_profile_setup(&vertical_axis.profile,
			vertical_axis.current_position,
			v_pos,
			v_speed_adjusted,
			vertical_axis.acceleration);
			vertical_axis.state = STEPPER_MOVING;
			vertical_axis.current_speed = 0;
			movement_started = true;
		}
	}
	
	if (movement_started) {
		char msg[64];
		snprintf(msg, sizeof(msg), "STEPPER_MOVE_STARTED:%ld,%ld", h_pos, v_pos);
		uart_send_response(msg);
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
	
	limit_switch_update();
	
	// Actualizar perfil horizontal si está en movimiento
	if (motion_profile_is_active(&horizontal_axis.profile)) {
		uint16_t new_speed = motion_profile_update(&horizontal_axis.profile,
		horizontal_axis.current_position);
		
		// CAMBIO: Solo actualizar si hay cambio significativo o si estamos arrancando
		if (new_speed != horizontal_axis.current_speed || horizontal_axis.current_speed == 0) {
			horizontal_axis.current_speed = new_speed;
			update_horizontal_speed(new_speed);
		}
	}
	
	// Actualizar perfil vertical si está en movimiento
	if (motion_profile_is_active(&vertical_axis.profile)) {
		uint16_t new_speed = motion_profile_update(&vertical_axis.profile,
		vertical_axis.current_position);
		
		// CAMBIO: Solo actualizar si hay cambio significativo o si estamos arrancando
		if (new_speed != vertical_axis.current_speed || vertical_axis.current_speed == 0) {
			vertical_axis.current_speed = new_speed;
			update_vertical_speed(new_speed);
		}
	}
}

void stepper_start_calibration(void) {
	calibration_mode = true;
	calibration_step_counter = 0;
	uart_send_response("CALIBRATION_STARTED");
}

void stepper_stop_calibration(void) {
	calibration_mode = false;
	
	char report_msg[64];
	snprintf(report_msg, sizeof(report_msg), "CALIBRATION_COMPLETED:%ld", calibration_step_counter);
	uart_send_response(report_msg);
	
	calibration_step_counter = 0;
}