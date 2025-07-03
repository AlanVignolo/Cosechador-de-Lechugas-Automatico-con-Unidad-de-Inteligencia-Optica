#include "gripper_driver.h"
#include <avr/io.h>
#include <util/delay.h>
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
	
	// Estado inicial
	gripper.state = GRIPPER_OPEN;
	gripper.target_state = GRIPPER_OPEN;
	gripper.current_steps = 0;
	gripper.phase_index = 0;
	gripper.last_step_time = 0;
	gripper.step_delay_us = 3000;  // 3ms entre pasos
	
	steps_to_do = 0;
	step_direction = 0;
	gripper_tick_counter = 0;
	ticks_per_step = 200;  // Valor intermedio
}

void gripper_open(void) {
	if (gripper.state == GRIPPER_OPEN || gripper.state == GRIPPER_OPENING) {
		return;
	}
	
	// Configurar para abrir
	steps_to_do = gripper.current_steps;
	step_direction = -1;  // Backward
	gripper.state = GRIPPER_OPENING;
	gripper.target_state = GRIPPER_OPEN;
	gripper_tick_counter = 0;  // Reset counter
}

void gripper_close(void) {
	if (gripper.state == GRIPPER_CLOSED || gripper.state == GRIPPER_CLOSING) {
		return;
	}
	
	// Configurar para cerrar
	steps_to_do = GRIPPER_STEPS_TO_CLOSE - gripper.current_steps;
	step_direction = 1;  // Forward
	gripper.state = GRIPPER_CLOSING;
	gripper.target_state = GRIPPER_CLOSED;
	gripper_tick_counter = 0;  // Reset counter
}

void gripper_update(void) {
	// Si no hay trabajo que hacer, salir
	if (steps_to_do == 0 || step_direction == 0) {
		if (gripper.state == GRIPPER_OPENING || gripper.state == GRIPPER_CLOSING) {
			// Movimiento completado
			disable_motor();
			gripper.state = gripper.target_state;
		}
		return;
	}
	
	// Incrementar contador
	gripper_tick_counter++;
	
	// Verificar si es tiempo de dar un paso
	if (gripper_tick_counter < ticks_per_step) {
		// Mantener el patrón actual aplicado
		apply_pattern(gripper.phase_index);
		return;
	}
	
	// Reset counter
	gripper_tick_counter = 0;
	
	// Avanzar al siguiente paso
	if (step_direction > 0) {
		// Forward
		gripper.phase_index = (gripper.phase_index + 1) % 8;
		gripper.current_steps++;
		} else {
		// Backward
		if (gripper.phase_index == 0) {
			gripper.phase_index = 7;
			} else {
			gripper.phase_index--;
		}
		gripper.current_steps--;
	}
	
	// Aplicar el nuevo patrón
	apply_pattern(gripper.phase_index);
	
	// NUEVO: Pequeño delay para estabilizar el motor
	// Esto asegura que el patrón se mantenga el tiempo suficiente
	for(volatile uint16_t i = 0; i < 1000; i++) {
		__asm__ __volatile__ ("nop");
	}
	
	// Decrementar contador
	steps_to_do--;
	
	// Si llegamos al final, detener
	if (steps_to_do == 0) {
		disable_motor();
		step_direction = 0;
		gripper.state = gripper.target_state;
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