#ifndef UART_DRIVER_H
#define UART_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

// Funciones principales
void uart_init(uint32_t baud_rate);
void uart_set_command_callback(void (*callback)(void));
void uart_send_char(char c);
void uart_send_string(const char* str);
void uart_send_response(const char* response);
bool uart_get_command(char* dest, uint8_t max_len);
void uart_send_system_status(void);

#endif