#include "drivers/uart_driver.h"
#include "command/command_parser.h"
#include "config/system_config.h"
#include "drivers/stepper_driver.h"
#include <avr/interrupt.h>

static void on_uart_command_ready(void) {
	char cmd[UART_BUFFER_SIZE];
	if (uart_get_command(cmd, sizeof(cmd))) {
		uart_parse_command(cmd);
	}
}

int main(void)
{
	uart_init(UART_BAUD_RATE);
	stepper_init();
	uart_set_command_callback(on_uart_command_ready);
	sei();
	
	uart_send_response("SYSTEM_READY");
	
	while (1)
	{	}
}