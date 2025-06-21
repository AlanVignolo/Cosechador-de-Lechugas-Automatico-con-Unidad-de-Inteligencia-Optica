#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>

#include "config/hardware_config.h"
#include "config/system_config.h"
#include "utils/common.h"
#include "utils/pin_macros.h"

void system_init(void) {
	// Deshabilitar interrupciones durante configuraci�n
	cli();
	
	// TODO: Inicializar cada m�dulo
	
	// Habilitar interrupciones globales
	sei();
}

int main(void) {

	system_init();
	
	while (1) {
	}
}