#ifndef UART_DRIVER_H
#define UART_DRIVER_H

#include <stdint.h>
#include <stdbool.h>
#include "../config/command_protocol.h"

// Funciones principales
void uart_init(uint32_t baud_rate);
void uart_send_char(char c);
void uart_send_string(const char* str);
void uart_send_response(const char* response);
bool uart_data_available(void);
char uart_get_char(void);
void stepper_debug_info(void);

// Buffer circular para recepción
typedef struct {
	char buffer[UART_BUFFER_SIZE];
	volatile uint8_t head;
	volatile uint8_t tail;
	volatile bool command_ready;
} uart_buffer_t;

// Obtener comando completo
bool uart_get_command(char* dest, uint8_t max_len);

// Funciones helper para respuestas formateadas
void uart_send_position(float x, float y);
void uart_send_status(uint8_t state, float x, float y);
void uart_send_error(const char* error_msg);
void uart_set_command_callback(void (*callback)(void));
void uart_process_incoming(void);

#endif