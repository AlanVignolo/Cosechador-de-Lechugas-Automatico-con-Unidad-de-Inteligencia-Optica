#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>

#include "config/hardware_config.h"
#include "config/system_config.h"
#include "utils/common.h"
#include "utils/pin_macros.h"

void system_init(void) {
	// Deshabilitar interrupciones durante configuración
	cli();
	
	// TODO: Inicializar cada módulo
	// timer_init();
	// stepper_init();
	// servo_init();
	// encoder_init();
	// uart_init(UART_BAUD_RATE);
	
	// Habilitar interrupciones globales
	sei();
}

int main(void) {

	system_init();
	
	while (1) {
	}
}