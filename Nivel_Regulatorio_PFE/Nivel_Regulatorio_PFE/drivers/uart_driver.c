#include "uart_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdio.h>
#include <string.h>

// Buffer de recepción
static uart_buffer_t rx_buffer = {.head = 0, .tail = 0, .command_ready = false};

// Buffer temporal para comandos
static char command_buffer[UART_BUFFER_SIZE];
static uint8_t cmd_index = 0;
static bool cmd_started = false;

void uart_init(uint32_t baud_rate) {
	// Calcular valor UBRR
	uint16_t ubrr_value = (F_CPU / (16UL * baud_rate)) - 1;
	
	// Configurar baud rate
	UBRR0H = (uint8_t)(ubrr_value >> 8);
	UBRR0L = (uint8_t)ubrr_value;
	
	// Habilitar transmisor y receptor
	UCSR0B = (1 << RXEN0) | (1 << TXEN0) | (1 << RXCIE0);
	
	// Configurar formato: 8 bits, 1 stop, sin paridad
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
	
	// Limpiar buffers
	rx_buffer.head = 0;
	rx_buffer.tail = 0;
	rx_buffer.command_ready = false;
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

bool uart_data_available(void) {
	return (rx_buffer.head != rx_buffer.tail) || rx_buffer.command_ready;
}

char uart_get_char(void) {
	if (rx_buffer.head == rx_buffer.tail) {
		return 0;
	}
	
	uint8_t tail = rx_buffer.tail;
	char c = rx_buffer.buffer[tail];
	rx_buffer.tail = (tail + 1) % UART_BUFFER_SIZE;
	
	return c;
}

bool uart_get_command(char* dest, uint8_t max_len) {
	if (!rx_buffer.command_ready) {
		return false;
	}
	
	// Copiar comando
	strncpy(dest, command_buffer, max_len - 1);
	dest[max_len - 1] = '\0';
	
	// Limpiar flag
	rx_buffer.command_ready = false;
	
	return true;
}

// ISR para recepción UART
ISR(USART0_RX_vect) {
	char received = UDR0;
	
	// Agregar al buffer circular
	uint8_t next_head = (rx_buffer.head + 1) % UART_BUFFER_SIZE;
	if (next_head != rx_buffer.tail) {
		rx_buffer.buffer[rx_buffer.head] = received;
		rx_buffer.head = next_head;
	}
	
	// Procesar protocolo <comando>
	if (received == '<') {
		cmd_started = true;
		cmd_index = 0;
	}
	else if (cmd_started) {
		if (received == '>') {
			command_buffer[cmd_index] = '\0';
			rx_buffer.command_ready = true;
			cmd_started = false;
		}
		else if (cmd_index < UART_BUFFER_SIZE - 1) {
			command_buffer[cmd_index++] = received;
		}
		else {
			// Buffer overflow - reiniciar
			cmd_started = false;
			cmd_index = 0;
		}
	}
}

// Funciones helper para respuestas
void uart_send_position(float x, float y) {
	char buffer[64];
	snprintf(buffer, sizeof(buffer), "POS:%.2f,%.2f", x, y);
	uart_send_response(buffer);
}

void uart_send_status(uint8_t state, float x, float y) {
	char buffer[80];
	const char* state_str[] = {"IDLE", "MOVING", "HOMING", "ERROR", "ESTOP"};
	snprintf(buffer, sizeof(buffer), "STATUS:%s,%.2f,%.2f",
	state_str[state], x, y);
	uart_send_response(buffer);
}

void uart_send_error(const char* error_msg) {
	uart_send_response(error_msg);
}