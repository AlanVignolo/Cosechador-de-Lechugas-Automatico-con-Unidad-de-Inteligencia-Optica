#include "gripper_driver.h"
#include <avr/io.h>
#include <util/delay.h>
#include <avr/eeprom.h>
#include "../config/system_config.h"

// Secuencia de 8 medios pasos (igual que Arduino)
static const uint8_t step_sequence[8][4] = {
	{1, 0, 0, 0},
	{1, 1, 0, 0},
	{0, 1, 0, 0},
	{0, 1, 1, 0},
	{0, 0, 1, 0},
	{0, 0, 1, 1},
	{0, 0, 0, 1},
	{1, 0, 0, 1}
};

// Variable global del controlador
static gripper_controller_t gripper = {0};

// Variables para control no bloqueante
static volatile uint16_t steps_to_do = 0;
static volatile int8_t step_direction = 0;  // 1=forward, -1=backward, 0=stop

// Contador simple para timing del gripper
static volatile uint16_t gripper_tick_counter = 0;
static uint16_t ticks_per_step = 200;  // Valor intermedio - ni muy rápido ni muy lento

// Direcciones EEPROM para gripper (continuar después de las del servo)
#define EEPROM_GRIPPER_STATE    0x03
#define EEPROM_GRIPPER_STEPS    0x04  // Para guardar posición exacta (2 bytes)
#define EEPROM_GRIPPER_MAGIC    0x06
#define GRIPPER_MAGIC_VALUE     0xBB

// Función para aplicar el patrón actual a los pines
static void apply_pattern(uint8_t pattern_index) {
	// Aplicar directamente a los bits correctos de PORTC
	if (step_sequence[pattern_index][0]) {
		PORTC |= (1 << 3);   // IN1 - PC3 (Pin 34)
		} else {
		PORTC &= ~(1 << 3);
	}
	
	if (step_sequence[pattern_index][1]) {
		PORTC |= (1 << 2);   // IN2 - PC2 (Pin 35)
		} else {
		PORTC &= ~(1 << 2);
	}
	
	if (step_sequence[pattern_index][2]) {
		PORTC |= (1 << 1);   // IN3 - PC1 (Pin 36)
		} else {
		PORTC &= ~(1 << 1);
	}
	
	if (step_sequence[pattern_index][3]) {
		PORTC |= (1 << 0);   // IN4 - PC0 (Pin 37)
		} else {
		PORTC &= ~(1 << 0);
	}
}

// Función para desactivar todas las bobinas
static void disable_motor(void) {
	PORTC &= ~((1 << 3) | (1 << 2) | (1 << 1) | (1 << 0));
}

void gripper_init(void) {
	// Configurar pines como salidas
	DDRC |= (1 << 3) | (1 << 2) | (1 << 1) | (1 << 0);  // PC3, PC2, PC1, PC0
	
	// Desactivar motor al inicio
	disable_motor();
	
	gripper.phase_index = 0;
	gripper.last_step_time = 0;
	gripper.step_delay_us = 3000;  // 3ms entre pasos
	
	steps_to_do = 0;
	step_direction = 0;
	gripper_tick_counter = 0;
	ticks_per_step = 200;
	
	gripper_load_state();
	
	if (gripper.state == GRIPPER_OPENING || gripper.state == GRIPPER_CLOSING) {
		gripper.state = (gripper.current_steps < GRIPPER_STEPS_TO_CLOSE / 2) ?
		GRIPPER_OPEN : GRIPPER_CLOSED;
	}
	
	steps_to_do = 0;
	step_direction = 0;
	
	uart_send_gripper_status();
	
	gripper.state = GRIPPER_OPEN;  // TEMPORAL
	gripper.current_steps = 0;     // TEMPORAL
	    
	// Cargar estado desde EEPROM
	gripper_load_state();
	    
	// ? DEBUG: Ver qué se cargó
	char debug_msg[128];
	snprintf(debug_msg, sizeof(debug_msg),
	"GRIPPER_INIT:state=%d,steps=%d,target_steps=%d",
	gripper.state, gripper.current_steps, GRIPPER_STEPS_TO_CLOSE);
	uart_send_response(debug_msg);
	    
	// Resetear variables globales
	steps_to_do = 0;
	step_direction = 0;
	gripper_tick_counter = 0;
	ticks_per_step = 200;
}
	
void uart_send_gripper_status(void) {
	const char* state_str;
	switch(gripper.state) {
		case GRIPPER_OPEN: state_str = "OPEN"; break;
		case GRIPPER_CLOSED: state_str = "CLOSED"; break;
		case GRIPPER_OPENING: state_str = "OPENING"; break;
		case GRIPPER_CLOSING: state_str = "CLOSING"; break;
		default: state_str = "IDLE"; break;
	}
	
	char msg[64];
	snprintf(msg, sizeof(msg), "GRIPPER_STATUS:%s,%d", state_str, gripper.current_steps);
	uart_send_response(msg);
}

void gripper_open(void) {
	if (gripper.state == GRIPPER_OPEN) {
		uart_send_response("GRIPPER_ALREADY_OPEN");
		return;
	}
	
	steps_to_do = 0;
	step_direction = 0;
	
	steps_to_do = GRIPPER_STEPS_TO_CLOSE - gripper.current_steps;
	step_direction = 1;
	gripper.state = GRIPPER_OPENING;
	gripper.target_state = GRIPPER_OPEN;
	gripper_tick_counter = 0;
	
	uart_send_response("GRIPPER_ACTION_STARTED:OPENING");
}

void gripper_close(void) {
	if (gripper.state == GRIPPER_CLOSED) {
		uart_send_response("GRIPPER_ALREADY_CLOSED");
		return;
	}
	
	steps_to_do = 0;
	step_direction = 0;
	
	steps_to_do = gripper.current_steps;
	step_direction = -1;
	gripper.state = GRIPPER_CLOSING;
	gripper.target_state = GRIPPER_CLOSED;
	gripper_tick_counter = 0;
	
	uart_send_response("GRIPPER_ACTION_STARTED:CLOSING");
}

void gripper_toggle(void) {
	if (gripper.state == GRIPPER_OPENING || gripper.state == GRIPPER_CLOSING) {
		uart_send_response("GRIPPER_BUSY");
		return;
	}
	
	if (gripper.state == GRIPPER_CLOSED || gripper.current_steps < GRIPPER_STEPS_TO_CLOSE / 2) {
		steps_to_do = GRIPPER_STEPS_TO_CLOSE - gripper.current_steps;
		step_direction = 1;
		gripper.state = GRIPPER_OPENING;
		gripper.target_state = GRIPPER_OPEN;
		uart_send_response("GRIPPER_ACTION_STARTED:OPENING");
		} else {
		steps_to_do = gripper.current_steps;
		step_direction = -1;
		gripper.state = GRIPPER_CLOSING;
		gripper.target_state = GRIPPER_CLOSED;
		uart_send_response("GRIPPER_ACTION_STARTED:CLOSING");
	}
	
	gripper_tick_counter = 0;
}

void gripper_update(void) {
	if (steps_to_do == 0 || step_direction == 0) {
		if (gripper.state == GRIPPER_OPENING || gripper.state == GRIPPER_CLOSING) {
			disable_motor();
			gripper.state = gripper.target_state;
			gripper_save_state();
			
			if (gripper.state == GRIPPER_OPEN) {
				uart_send_response("GRIPPER_ACTION_COMPLETED:OPEN");
				} else if (gripper.state == GRIPPER_CLOSED) {
				uart_send_response("GRIPPER_ACTION_COMPLETED:CLOSED");
			}
		}
		return;
	}
	
	gripper_tick_counter++;
	
	if (gripper_tick_counter < ticks_per_step) {
		apply_pattern(gripper.phase_index);
		return;
	}
	
	gripper_tick_counter = 0;
	
	if (step_direction > 0) {
		gripper.phase_index = (gripper.phase_index + 1) % 8;
		gripper.current_steps++;
		} else {
		if (gripper.phase_index == 0) {
			gripper.phase_index = 7;
			} else {
			gripper.phase_index--;
		}
		gripper.current_steps--;
	}
	
	if (gripper.current_steps < 0) gripper.current_steps = 0;
	if (gripper.current_steps > GRIPPER_STEPS_TO_CLOSE) gripper.current_steps = GRIPPER_STEPS_TO_CLOSE;
	
	apply_pattern(gripper.phase_index);
	
	for(volatile uint16_t i = 0; i < 1000; i++) {
		__asm__ __volatile__ ("nop");
	}
	
	steps_to_do--;
	
	if (steps_to_do == 0) {
		disable_motor();
		step_direction = 0;
		gripper.state = gripper.target_state;
		gripper_save_state();
		
		if (gripper.state == GRIPPER_OPEN) {
			uart_send_response("GRIPPER_ACTION_COMPLETED:OPEN");
			} else if (gripper.state == GRIPPER_CLOSED) {
			uart_send_response("GRIPPER_ACTION_COMPLETED:CLOSED");
		}
	}
}

void gripper_stop(void) {
	disable_motor();
	steps_to_do = 0;
	step_direction = 0;
	
	// Determinar estado actual basado en posición
	if (gripper.current_steps < GRIPPER_STEPS_TO_CLOSE / 2) {
		gripper.state = GRIPPER_OPEN;
		} else {
		gripper.state = GRIPPER_CLOSED;
	}
}

bool gripper_is_busy(void) {
	return (steps_to_do > 0);
}

gripper_state_t gripper_get_state(void) {
	return gripper.state;
}

int16_t gripper_get_position(void) {
	return gripper.current_steps;
}

void gripper_set_speed(uint16_t delay_ms) {
	// Ajustar ticks_per_step basado en el delay deseado
	if (delay_ms < 2) delay_ms = 2;
	if (delay_ms > 10) delay_ms = 10;
	
	// Para 3ms de delay, queremos ~200 ticks
	ticks_per_step = delay_ms * 67;  // ~200 para 3ms
}

static void gripper_save_state(void) {
	eeprom_update_byte((uint8_t*)EEPROM_GRIPPER_STATE, (uint8_t)gripper.state);
	eeprom_update_word((uint16_t*)EEPROM_GRIPPER_STEPS, (uint16_t)gripper.current_steps);
	eeprom_update_byte((uint8_t*)EEPROM_GRIPPER_MAGIC, GRIPPER_MAGIC_VALUE);
}

static void gripper_load_state(void) {
	uint8_t magic = eeprom_read_byte((uint8_t*)EEPROM_GRIPPER_MAGIC);
	
	if (magic == GRIPPER_MAGIC_VALUE) {
		uint8_t saved_state = eeprom_read_byte((uint8_t*)EEPROM_GRIPPER_STATE);
		uint16_t saved_steps = eeprom_read_word((uint16_t*)EEPROM_GRIPPER_STEPS);
		
		// ? DEBUG
		char debug_msg[64];
		snprintf(debug_msg, sizeof(debug_msg),
		"EEPROM_LOAD:state=%d,steps=%d", saved_state, saved_steps);
		uart_send_response(debug_msg);
		
		if (saved_steps <= GRIPPER_STEPS_TO_CLOSE) {
			gripper.current_steps = saved_steps;
			gripper.state = (gripper_state_t)saved_state;
			gripper.target_state = gripper.state;
		}
		} else {
		// Primera vez - estado inicial cerrado
		gripper.state = GRIPPER_CLOSED;
		gripper.target_state = GRIPPER_CLOSED;
		gripper.current_steps = GRIPPER_STEPS_TO_CLOSE;
		gripper_save_state();
		
		uart_send_response("EEPROM_FIRST_TIME:CLOSED");
	}
}