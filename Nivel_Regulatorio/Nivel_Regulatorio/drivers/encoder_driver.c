#include "encoder_driver.h"
#include "uart_driver.h"
#include "stepper_driver.h"
#include "../config/system_config.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdio.h>

// Variables globales para encoders
static encoder_t horizontal_encoder = {0, 0, false};
static encoder_t vertical_encoder = {0, 0, false};

// Tabla de estados para decodificación de encoder (mismo que Arduino IDE)
static const int8_t encoder_table[] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

void encoder_init(void) {
	// CORRECCIÓN CRÍTICA: Usar configuración idéntica a Arduino IDE
	
	// Pin 2 (PE4) - INT4 para CLK horizontal
	DDRE &= ~(1 << 4);
	PORTE |= (1 << 4);  // Pull-up habilitado
	
	// Pin 28 (PA6) - DT Horizontal
	DDRA &= ~(1 << 6);
	PORTA |= (1 << 6);  // Pull-up habilitado
	
	// Pin 3 (PE5) - INT5 para CLK vertical
	DDRE &= ~(1 << 5);
	PORTE |= (1 << 5);  // Pull-up habilitado
	
	// Pin 29 (PA7) - DT Vertical
	DDRA &= ~(1 << 7);
	PORTA |= (1 << 7);  // Pull-up habilitado
	
	// Leer estados iniciales EXACTAMENTE como Arduino IDE
	uint8_t h_clk = (PINE & (1 << 4)) ? 1 : 0;
	uint8_t h_dt = (PINA & (1 << 6)) ? 1 : 0;
	horizontal_encoder.last_state = (h_clk << 1) | h_dt;
	
	uint8_t v_clk = (PINE & (1 << 5)) ? 1 : 0;
	uint8_t v_dt = (PINA & (1 << 7)) ? 1 : 0;
	vertical_encoder.last_state = (v_clk << 1) | v_dt;
	
	// CORRECCIÓN 1: Deshabilitar interrupciones durante configuración
	cli();
	
	// CORRECCIÓN 2: Configuración EICRB correcta (era el problema principal)
	// INT4 (Pin 2) - CUALQUIER CAMBIO (exactamente como Arduino IDE)
	EICRB &= ~((1 << ISC41) | (1 << ISC40));  // Limpiar bits primero
	EICRB |= (1 << ISC40);                    // ISC40=1, ISC41=0 = ANY CHANGE
	
	// INT5 (Pin 3) - CUALQUIER CAMBIO (exactamente como Arduino IDE)
	EICRB &= ~((1 << ISC51) | (1 << ISC50));  // Limpiar bits primero
	EICRB |= (1 << ISC50);                    // ISC50=1, ISC51=0 = ANY CHANGE
	
	// CORRECCIÓN 3: Habilitar interrupciones al final
	EIMSK |= (1 << INT4) | (1 << INT5);
	
	// Resetear posiciones
	horizontal_encoder.position = 0;
	vertical_encoder.position = 0;
	horizontal_encoder.enabled = true;
	vertical_encoder.enabled = true;
	
	sei();  // Rehabilitar interrupciones globales
}

void encoder_reset_position(bool reset_h, bool reset_v) {
	// Operación atómica
	cli();
	if (reset_h) {
		horizontal_encoder.position = 0;
	}
	if (reset_v) {
		vertical_encoder.position = 0;
	}
	sei();
}

void encoder_get_positions(int32_t* h_pos, int32_t* v_pos) {
	// Lectura atómica
	cli();
	*h_pos = horizontal_encoder.position;
	*v_pos = vertical_encoder.position;
	sei();
}

void encoder_send_comparison_data(void) {
	int32_t stepper_h, stepper_v;
	int32_t encoder_h, encoder_v;
	
	// Obtener posiciones de motores
	stepper_get_position(&stepper_h, &stepper_v);
	
	// Obtener posiciones de encoders
	encoder_get_positions(&encoder_h, &encoder_v);
	
	// Enviar solo los datos raw - Python hará los cálculos
	char response[200];
	snprintf(response, sizeof(response),
	"COMPARISON:MOTOR_H:%ld,ENC_H:%ld,MOTOR_V:%ld,ENC_V:%ld",
	stepper_h, encoder_h, stepper_v, encoder_v);
	
	uart_send_response(response);
	
	// Enviar información adicional simple
	if (encoder_h != 0) {
		snprintf(response, sizeof(response), "RATIO_DATA_H:%ld,%ld", stepper_h, encoder_h);
		uart_send_response(response);
		} else {
		uart_send_response("RATIO_H:N/A");
	}
	
	if (encoder_v != 0) {
		snprintf(response, sizeof(response), "RATIO_DATA_V:%ld,%ld", stepper_v, encoder_v);
		uart_send_response(response);
		} else {
		uart_send_response("RATIO_V:N/A");
	}
}

void encoder_debug_raw_states(void) {
	// Leer estados actuales de los pines
	uint8_t h_clk = (PINE & (1 << 4)) ? 1 : 0;
	uint8_t h_dt = (PINA & (1 << 6)) ? 1 : 0;
	uint8_t v_clk = (PINE & (1 << 5)) ? 1 : 0;
	uint8_t v_dt = (PINA & (1 << 7)) ? 1 : 0;
	
	char response[128];
	snprintf(response, sizeof(response),
	"RAW_STATES:H_CLK:%d,H_DT:%d,V_CLK:%d,V_DT:%d",
	h_clk, h_dt, v_clk, v_dt);
	uart_send_response(response);
	
	snprintf(response, sizeof(response),
	"ENCODER_ENABLED:H:%s,V:%s",
	horizontal_encoder.enabled ? "YES" : "NO",
	vertical_encoder.enabled ? "YES" : "NO");
	uart_send_response(response);
	
	snprintf(response, sizeof(response),
	"LAST_STATES:H:%d,V:%d",
	horizontal_encoder.last_state, vertical_encoder.last_state);
	uart_send_response(response);
	
	// Debug adicional de configuración de interrupciones
	snprintf(response, sizeof(response),
	"INT_CONFIG:EICRB:0x%02X,EIMSK:0x%02X",
	EICRB, EIMSK);
	uart_send_response(response);
}

// ISR para encoder horizontal (INT4 - Pin 2) - OPTIMIZADA
ISR(INT4_vect) {
	if (!horizontal_encoder.enabled) return;
	
	// Lectura directa y rápida (como Arduino IDE)
	uint8_t clk = (PINE & (1 << 4)) ? 1 : 0;
	uint8_t dt = (PINA & (1 << 6)) ? 1 : 0;
	uint8_t current_state = (clk << 1) | dt;
	
	// Usar tabla de lookup (idéntico a Arduino IDE)
	uint8_t index = (horizontal_encoder.last_state << 2) | current_state;
	horizontal_encoder.position += encoder_table[index];
	horizontal_encoder.last_state = current_state;
}

// ISR para encoder vertical (INT5 - Pin 3) - OPTIMIZADA
ISR(INT5_vect) {
	if (!vertical_encoder.enabled) return;
	
	// Lectura directa y rápida (como Arduino IDE)
	uint8_t clk = (PINE & (1 << 5)) ? 1 : 0;
	uint8_t dt = (PINA & (1 << 7)) ? 1 : 0;
	uint8_t current_state = (clk << 1) | dt;
	
	// Usar tabla de lookup (idéntico a Arduino IDE)
	uint8_t index = (vertical_encoder.last_state << 2) | current_state;
	vertical_encoder.position += encoder_table[index];
	vertical_encoder.last_state = current_state;
}