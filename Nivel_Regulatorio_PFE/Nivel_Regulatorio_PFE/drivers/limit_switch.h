#ifndef LIMIT_SWITCH_H
#define LIMIT_SWITCH_H

#include <stdbool.h>
#include "utils/common.h"
void limit_switch_init(void);
void limit_switch_update(void);
limit_status_t limit_switch_get_status(void);
void limit_switch_enable_interrupts(bool enable);

#endif

// drivers/limit_switch.c
#include "limit_switch.h"
#include "config/hardware_config.h"
#include "utils/pin_macros.h"
#include <avr/interrupt.h>
#include <util/delay.h>

static volatile limit_status_t limits = {false, false, false, false};
static volatile uint8_t debounce_counter[4] = {0, 0, 0, 0};

void limit_switch_init(void) {
	// Configurar pines como entrada con pull-up
	SET_INPUT(FC_H_LEFT_DDR, FC_H_LEFT);
	SET_INPUT(FC_H_RIGHT_DDR, FC_H_RIGHT);
	SET_INPUT(FC_V_UP_DDR, FC_V_UP);
	SET_INPUT(FC_V_DOWN_DDR, FC_V_DOWN);
	
	ENABLE_PULLUP(FC_H_LEFT_PORT, FC_H_LEFT);
	ENABLE_PULLUP(FC_H_RIGHT_PORT, FC_H_RIGHT);
	ENABLE_PULLUP(FC_V_UP_PORT, FC_V_UP);
	ENABLE_PULLUP(FC_V_DOWN_PORT, FC_V_DOWN);
	
	// Configurar interrupciones por cambio de pin (PCINT)
	// Los pines están en PORTC (PCINT8-15)
	PCICR |= (1 << PCIE1);  // Habilitar PCINT para PORTC
	PCMSK1 |= (1 << PCINT15) | (1 << PCINT14) |
	(1 << PCINT13) | (1 << PCINT12);  // PC7-PC4
}

void limit_switch_update(void) {
	// Leer estado actual (activo bajo)
	bool x_min = !(FC_H_LEFT_PIN & (1 << FC_H_LEFT));
	bool x_max = !(FC_H_RIGHT_PIN & (1 << FC_H_RIGHT));
	bool y_max = !(FC_V_UP_PIN & (1 << FC_V_UP));
	bool y_min = !(FC_V_DOWN_PIN & (1 << FC_V_DOWN));
	
	// Aplicar debounce simple
	static uint8_t count = 0;
	if (++count >= 10) {
		count = 0;
		limits.x_min_hit = x_min;
		limits.x_max_hit = x_max;
		limits.y_min_hit = y_min;
		limits.y_max_hit = y_max;
	}
}

limit_status_t limit_switch_get_status(void) {
	limit_status_t status;
	cli();
	status = limits;
	sei();
	return status;
}

// ISR para cambios en los fines de carrera
ISR(PCINT1_vect) {
	// Actualizar estado inmediatamente para respuesta rápida
	limits.x_min_hit = !(FC_H_LEFT_PIN & (1 << FC_H_LEFT));
	limits.x_max_hit = !(FC_H_RIGHT_PIN & (1 << FC_H_RIGHT));
	limits.y_max_hit = !(FC_V_UP_PIN & (1 << FC_V_UP));
	limits.y_min_hit = !(FC_V_DOWN_PIN & (1 << FC_V_DOWN));
	
	// Notificar si se activó algún límite
	if (limits.x_min_hit || limits.x_max_hit ||
	limits.y_min_hit || limits.y_max_hit) {
	}
}