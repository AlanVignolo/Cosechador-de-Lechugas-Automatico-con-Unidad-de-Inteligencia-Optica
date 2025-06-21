#include "stepper_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "../config/system_config.h"

// Variables globales para los ejes
static stepper_axis_t horizontal_axis = {0};
static stepper_axis_t vertical_axis = {0};
static volatile bool timer1_active = false;
static volatile bool timer3_active = false;

// Función para calcular TOP value del timer basado en velocidad deseada
static uint16_t calculate_timer_top(uint16_t steps_per_second) {
	// Para Timer con prescaler 8: TOP = (F_CPU / (8 * 2 * freq)) - 1
	// Factor 2 porque necesitamos toggle (HIGH y LOW)
	return (F_CPU / (8UL * 2UL * steps_per_second)) - 1;
}

// Función para iniciar Timer1 (motores horizontales)
static void start_horizontal_movement(uint16_t speed) {
	if (speed == 0) return;
	
	uint16_t top_value = calculate_timer_top(speed);
	
	// Configurar Timer1 en modo CTC con toggle en OC1A y OC1B
	TCCR1A = (1 << COM1A0) | (1 << COM1B0);
	TCCR1B = (1 << WGM12) | (1 << CS11);
	
	OCR1A = top_value;
	OCR1B = top_value;
	
	TIMSK1 |= (1 << OCIE1A);
	timer1_active = true;
}

static void start_vertical_movement(uint16_t speed) {
	if (speed == 0) return;
	
	uint16_t top_value = calculate_timer_top(speed);
	
	TCCR3A = (1 << COM3A0);
	TCCR3B = (1 << WGM32) | (1 << CS31);
	
	OCR3A = top_value;
	TIMSK3 |= (1 << OCIE3A);
	timer3_active = true;
}
// ISR Timer1 - motores horizontales
ISR(TIMER1_COMPA_vect) {
	// Actualizar posición en cada step
	if (horizontal_axis.direction) {
		horizontal_axis.current_position++;
		} else {
		horizontal_axis.current_position--;
	}
	
	// Verificar si llegamos al objetivo
	if (horizontal_axis.current_position == horizontal_axis.target_position) {
		// Parar Timer1
		TCCR1B = 0;
		TIMSK1 &= ~(1 << OCIE1A);
		horizontal_axis.state = STEPPER_IDLE;
		timer1_active = false;
	}
}

// ISR Timer3 - motor vertical
ISR(TIMER3_COMPA_vect) {
	// Actualizar posición en cada step
	if (vertical_axis.direction) {
		vertical_axis.current_position++;
		} else {
		vertical_axis.current_position--;
	}
	
	// Verificar si llegamos al objetivo
	if (vertical_axis.current_position == vertical_axis.target_position) {
		// Parar Timer3
		TCCR3B = 0;
		TIMSK3 &= ~(1 << OCIE3A);
		vertical_axis.state = STEPPER_IDLE;
		timer3_active = false;
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
	
	// Inicializar estados por defecto
	horizontal_axis.max_speed = MAX_SPEED_H;
	horizontal_axis.acceleration = ACCEL_H;
	horizontal_axis.current_speed = MIN_SPEED;
	horizontal_axis.state = STEPPER_IDLE;
	
	vertical_axis.max_speed = MAX_SPEED_V;
	vertical_axis.acceleration = ACCEL_V;
	vertical_axis.current_speed = MIN_SPEED;
	vertical_axis.state = STEPPER_IDLE;
	
	// Deshabilitar motores por defecto
	stepper_enable_motors(false, false);
	
	// Configurar Timer1 para motores horizontales (inicialmente parado)
	TCCR1A = 0;
	TCCR1B = 0;
	
	// Configurar Timer3 para motor vertical (inicialmente parado)
	TCCR3A = 0;
	TCCR3B = 0;
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
	
	// Configurar direcciones (INVERTIDAS)
	if (h_pos > horizontal_axis.current_position) {
		horizontal_axis.direction = true;
		PORTA &= ~((1 << 0) | (1 << 2));  // DIR pins LOW (era HIGH)
		} else if (h_pos < horizontal_axis.current_position) {
		horizontal_axis.direction = false;
		PORTA |= (1 << 0) | (1 << 2);     // DIR pins HIGH (era LOW)
	}

	if (v_pos > vertical_axis.current_position) {
		vertical_axis.direction = true;
		PORTA &= ~(1 << 4);               // DIR pin LOW (era HIGH)
		} else if (v_pos < vertical_axis.current_position) {
		vertical_axis.direction = false;
		PORTA |= (1 << 4);                // DIR pin HIGH (era LOW)
	}
	
    if (h_pos != horizontal_axis.current_position && horizontal_axis.enabled) {
	    horizontal_axis.state = STEPPER_MOVING;
        start_horizontal_movement(horizontal_axis.max_speed);
    }
    
    if (v_pos != vertical_axis.current_position && vertical_axis.enabled) {
	    vertical_axis.state = STEPPER_MOVING;
	    start_vertical_movement(vertical_axis.max_speed);
    }
}

void stepper_stop_all(void) {
	// Parar timers
	TCCR1B = 0;
	TCCR3B = 0;
	
	// Deshabilitar interrupciones
	TIMSK1 &= ~(1 << OCIE1A);
	TIMSK3 &= ~(1 << OCIE3A);
	
	// Resetear estados
	horizontal_axis.state = STEPPER_IDLE;
	vertical_axis.state = STEPPER_IDLE;
	timer1_active = false;
	timer3_active = false;
}

bool stepper_is_moving(void) {
	return (horizontal_axis.state != STEPPER_IDLE || vertical_axis.state != STEPPER_IDLE);
}

void stepper_get_position(int32_t* h_pos, int32_t* v_pos) {
	*h_pos = horizontal_axis.current_position;
	*v_pos = vertical_axis.current_position;
}

void stepper_set_position(int32_t h_pos, int32_t v_pos) {
	horizontal_axis.current_position = h_pos;
	vertical_axis.current_position = v_pos;
}

void stepper_debug_info(void) {
	char debug_msg[100];
	
	snprintf(debug_msg, sizeof(debug_msg), "STEPS_PER_MM_H: %d", (int)STEPS_PER_MM_H);
	uart_send_response(debug_msg);
	
	snprintf(debug_msg, sizeof(debug_msg), "STEPS_PER_MM_V: %d", (int)STEPS_PER_MM_V);
	uart_send_response(debug_msg);
	
	snprintf(debug_msg, sizeof(debug_msg), "POS_H: %ld, POS_V: %ld",
	horizontal_axis.current_position, vertical_axis.current_position);
	uart_send_response(debug_msg);
}

void stepper_debug_motor_state(void) {
	char debug_msg[100];
	
	snprintf(debug_msg, sizeof(debug_msg), "H_ENABLED: %s, V_ENABLED: %s",
	horizontal_axis.enabled ? "YES" : "NO",
	vertical_axis.enabled ? "YES" : "NO");
	uart_send_response(debug_msg);
	
	snprintf(debug_msg, sizeof(debug_msg), "H_STATE: %d, V_STATE: %d",
	horizontal_axis.state, vertical_axis.state);
	uart_send_response(debug_msg);
	
	snprintf(debug_msg, sizeof(debug_msg), "TIMER1: %s, TIMER3: %s",
	timer1_active ? "ACTIVE" : "STOPPED",
	timer3_active ? "ACTIVE" : "STOPPED");
	uart_send_response(debug_msg);
}