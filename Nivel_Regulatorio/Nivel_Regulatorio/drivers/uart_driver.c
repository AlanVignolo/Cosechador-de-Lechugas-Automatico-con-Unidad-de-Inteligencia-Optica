#include "uart_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdio.h>
#include <string.h>
#include "../config/system_config.h"
#include "../config/command_protocol.h"
#include "../drivers/gripper_driver.h"

static void (*command_ready_callback)(void) = NULL;
static char command_buffer[UART_BUFFER_SIZE];
static uint8_t cmd_index = 0;
static bool cmd_started = false;

void uart_init(uint32_t baud_rate) {
	uint16_t ubrr_value;
	
	if (baud_rate == 115200) {
		UCSR0A = (1 << U2X0);
		ubrr_value = (F_CPU / (8UL * baud_rate)) - 1;
		} else {
		UCSR0A = 0;
		ubrr_value = (F_CPU / (16UL * baud_rate)) - 1;
	}
	
	UBRR0H = (uint8_t)(ubrr_value >> 8);
	UBRR0L = (uint8_t)ubrr_value;
	
	UCSR0B = (1 << RXEN0) | (1 << TXEN0) | (1 << RXCIE0);
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
	
	cmd_index = 0;
	cmd_started = false;
	
	while (UCSR0A & (1 << RXC0)) {
		volatile uint8_t dummy = UDR0;
		(void)dummy;
	}
	
	uart_send_response("SYSTEM_INITIALIZED");
	uart_send_system_status();
}

void uart_set_command_callback(void (*callback)(void)) {
	command_ready_callback = callback;
}

void uart_send_char(char c) {
	// Esperar a que el buffer esté vacío
	while (!(UCSR0A & (1 << UDRE0)));
	UDR0 = c;
}

void uart_send_string(const char* str) {
	while (*str) {
		uart_send_char(*str++);
	}
}

void uart_send_response(const char* response) {
	uart_send_string(response);
	uart_send_string("\r\n");
}

bool uart_get_command(char* dest, uint8_t max_len) {
	// En esta implementación, el comando ya está en command_buffer
	// cuando se llama el callback
	strncpy(dest, command_buffer, max_len - 1);
	dest[max_len - 1] = '\0';
	return true;
}

ISR(USART0_RX_vect) {
	char received = UDR0;
	
	if (received == '<') {
		cmd_started = true;
		cmd_index = 0;
	}
	else if (received == '>' && cmd_started) {
		// Comando completo - procesar inmediatamente
		command_buffer[cmd_index] = '\0';
		cmd_started = false;
		
		// Llamar callback directamente desde ISR (será rápido)
		if (command_ready_callback) {
			command_ready_callback();
		}
	}
	else if (cmd_started && cmd_index < UART_BUFFER_SIZE - 1) {
		// Solo agregar caracteres válidos (no \n, \r)
		if (received != '\n' && received != '\r') {
			command_buffer[cmd_index++] = received;
		}
	}
	
	// Si hay overflow, resetear
	if (cmd_index >= UART_BUFFER_SIZE - 1) {
		cmd_started = false;
		cmd_index = 0;
	}
}

void uart_send_system_status(void) {
	// Obtener posiciones actuales
	uint8_t servo1_pos = servo_get_current_position(1);
	uint8_t servo2_pos = servo_get_current_position(2);
	
	// Obtener estado del gripper
	gripper_state_t gripper_state = gripper_get_state();
	int16_t gripper_pos = gripper_get_position();
	
	const char* gripper_str;
	switch(gripper_state) {
		case GRIPPER_OPEN: gripper_str = "OPEN"; break;
		case GRIPPER_CLOSED: gripper_str = "CLOSED"; break;
		case GRIPPER_OPENING: gripper_str = "OPENING"; break;
		case GRIPPER_CLOSING: gripper_str = "CLOSING"; break;
		default: gripper_str = "IDLE"; break;
	}
	
	// Enviar estado completo
	char status_msg[128];
	snprintf(status_msg, sizeof(status_msg),
	"SYSTEM_STATUS:SERVO1=%d,SERVO2=%d,GRIPPER=%s,GRIPPER_POS=%d",
	servo1_pos, servo2_pos, gripper_str, gripper_pos);
	
	uart_send_response(status_msg);
}