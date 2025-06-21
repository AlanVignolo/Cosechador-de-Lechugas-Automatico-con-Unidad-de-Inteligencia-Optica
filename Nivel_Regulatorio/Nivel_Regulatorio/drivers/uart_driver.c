#include "uart_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdio.h>
#include <string.h>
#include "../config/system_config.h"

static uart_buffer_t rx_buffer = {.head = 0, .tail = 0, .command_ready = false};
static void (*command_ready_callback)(void) = NULL;
static char command_buffer[UART_BUFFER_SIZE];
static uint8_t cmd_index = 0;
static bool cmd_started = false;

void uart_init(uint32_t baud_rate) {
	// Calcular UBRR con mejor precisión para ATmega2560
	uint16_t ubrr_value;
	
	// Para 115200 baud con 16MHz, usar UBRR = 8 pero con U2X para mejor precisión
	if (baud_rate == 115200) {
		// Usar modo de doble velocidad para mejor precisión
		UCSR0A = (1 << U2X0);
		ubrr_value = (F_CPU / (8UL * baud_rate)) - 1;  // U2X=1, divisor es 8
		} else {
		UCSR0A = 0;
		ubrr_value = (F_CPU / (16UL * baud_rate)) - 1; // U2X=0, divisor es 16
	}
	
	// Configurar baud rate
	UBRR0H = (uint8_t)(ubrr_value >> 8);
	UBRR0L = (uint8_t)ubrr_value;
	
	// Habilitar transmisor, receptor e interrupción RX
	UCSR0B = (1 << RXEN0) | (1 << TXEN0) | (1 << RXCIE0);
	
	// Configurar formato: 8 bits, 1 stop, sin paridad
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
	
	// Limpiar buffers y variables
	rx_buffer.head = 0;
	rx_buffer.tail = 0;
	rx_buffer.command_ready = false;
	cmd_index = 0;
	cmd_started = false;
	
	// Limpiar cualquier dato pendiente
	while (UCSR0A & (1 << RXC0)) {
		volatile uint8_t dummy = UDR0;
		(void)dummy; // Evitar warning
	}
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

// Procesar comandos en el loop principal
void uart_process_incoming(void) {
	while (rx_buffer.head != rx_buffer.tail) {
		char c = uart_get_char();
		
		if (c == '<') {
			cmd_started = true;
			cmd_index = 0;
		}
		else if ((c == '>' || c == '\n' || c == '\r') && cmd_started) {
			// Comando completo recibido
			command_buffer[cmd_index] = '\0';
			rx_buffer.command_ready = true;
			cmd_started = false;
			
			// Notificar callback si existe
			if (command_ready_callback) {
				command_ready_callback();
			}
			break; // Procesar un comando por vez
		}
		else if (cmd_started && c != '\n' && c != '\r') {
			// Agregar carácter al comando (ignorar \n y \r)
			if (cmd_index < UART_BUFFER_SIZE - 1) {
				command_buffer[cmd_index++] = c;
			}
			else {
				// Buffer overflow - reiniciar
				cmd_started = false;
				cmd_index = 0;
			}
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