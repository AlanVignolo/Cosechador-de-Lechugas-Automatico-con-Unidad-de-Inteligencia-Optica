#include "drivers/uart_driver.h"
#include "command/command_parser.h"
#include "config/system_config.h"
#include "config/command_protocol.h"
#include "drivers/stepper_driver.h"
#include <avr/interrupt.h>

static void on_uart_command_ready(void) {
	char cmd[UART_BUFFER_SIZE];
	if (uart_get_command(cmd, sizeof(cmd))) {
		uart_parse_command(cmd);
	}
}

int main(void) {
	// Inicializar UART
	uart_init(UART_BAUD_RATE);
	
	// Inicializar steppers (incluye motion profile)
	stepper_init();
	
	// Configurar callback de comandos
	uart_set_command_callback(on_uart_command_ready);
	
	// Habilitar interrupciones globales
	sei();
	
	// Notificar que el sistema está listo
	uart_send_response("SYSTEM_READY");
	
	// Loop principal
	while (1) {
		// Actualizar perfiles de velocidad
		stepper_update_profiles();
	}
}