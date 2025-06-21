#include "timer_control.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "config/hardware_config.h"
#include "config/system_config.h"

// Callbacks
static volatile timer_callback_t timer1_callback = NULL;
static volatile timer_callback_t timer3_callback = NULL;

// === TIMER 1 - Steppers Horizontales ===
void timer1_init_stepper(void) {
	// Modo CTC (Clear Timer on Compare Match)
	TCCR1A = 0;
	TCCR1B = (1 << WGM12);  // Modo CTC
	
	// Configurar pines OC1A y OC1B como salida
	SET_OUTPUT(STEP_H1_DDR, STEP_H1_PIN);
	SET_OUTPUT(STEP_H2_DDR, STEP_H2_PIN);
	
	// Inicializar con frecuencia baja
	timer1_set_frequency(1000);
	
	// Habilitar interrupción por comparación
	TIMSK1 = (1 << OCIE1A);
}

void timer1_set_frequency(uint32_t freq_hz) {
	if (freq_hz == 0) {
		timer1_enable(false);
		return;
	}
	
	// Calcular prescaler y valor OCR
	uint32_t ocr_value;
	uint8_t prescaler_bits;
	
	// Frecuencia = F_CPU / (2 * prescaler * (OCR + 1))
	// Para toggle automático del pin
	
	if (freq_hz > 2000) {
		// Prescaler = 1
		prescaler_bits = (1 << CS10);
		ocr_value = (F_CPU / (2UL * freq_hz)) - 1;
	}
	else if (freq_hz > 250) {
		// Prescaler = 8
		prescaler_bits = (1 << CS11);
		ocr_value = (F_CPU / (16UL * freq_hz)) - 1;
	}
	else {
		// Prescaler = 64
		prescaler_bits = (1 << CS11) | (1 << CS10);
		ocr_value = (F_CPU / (128UL * freq_hz)) - 1;
	}
	
	// Aplicar configuración
	TCCR1B = (TCCR1B & 0xF8) | prescaler_bits | (1 << WGM12);
	OCR1A = ocr_value;
}

void timer1_enable(bool enable) {
	if (enable) {
		TCCR1B |= (1 << CS10);  // Activar con prescaler configurado
		} else {
		TCCR1B &= ~((1 << CS12) | (1 << CS11) | (1 << CS10));  // Detener timer
	}
}

void timer1_set_callback(timer_callback_t callback) {
	timer1_callback = callback;
}

// ISR Timer1
ISR(TIMER1_COMPA_vect) {
	// Toggle de pines de step (si están configurados para eso)
	// O llamar al callback
	if (timer1_callback) {
		timer1_callback();
	}
}

// === TIMER 3 - Stepper Vertical ===
void timer3_init_stepper(void) {
	// Modo CTC
	TCCR3A = 0;
	TCCR3B = (1 << WGM32);
	
	// Configurar pin OC3A como salida
	SET_OUTPUT(STEP_V_DDR, STEP_V_PIN);
	
	// Inicializar con frecuencia baja
	timer3_set_frequency(1000);
	
	// Habilitar interrupción
	TIMSK3 = (1 << OCIE3A);
}

void timer3_set_frequency(uint32_t freq_hz) {
	if (freq_hz == 0) {
		timer3_enable(false);
		return;
	}
	
	uint32_t ocr_value;
	uint8_t prescaler_bits;
	
	if (freq_hz > 2000) {
		prescaler_bits = (1 << CS30);
		ocr_value = (F_CPU / (2UL * freq_hz)) - 1;
	}
	else if (freq_hz > 250) {
		prescaler_bits = (1 << CS31);
		ocr_value = (F_CPU / (16UL * freq_hz)) - 1;
	}
	else {
		prescaler_bits = (1 << CS31) | (1 << CS30);
		ocr_value = (F_CPU / (128UL * freq_hz)) - 1;
	}
	
	TCCR3B = (TCCR3B & 0xF8) | prescaler_bits | (1 << WGM32);
	OCR3A = ocr_value;
}

void timer3_enable(bool enable) {
	if (enable) {
		TCCR3B |= (1 << CS30);
		} else {
		TCCR3B &= ~((1 << CS32) | (1 << CS31) | (1 << CS30));
	}
}

void timer3_set_callback(timer_callback_t callback) {
	timer3_callback = callback;
}

ISR(TIMER3_COMPA_vect) {
	if (timer3_callback) {
		timer3_callback();
	}
}

// === TIMER 2 - Servos ===
void timer2_init_servo(void) {
	// Fast PWM mode, TOP = ICR
	// Frecuencia = 50Hz para servos
	
	// Configurar pines como salida
	SET_OUTPUT(SERVO1_DDR, SERVO1_PIN);
	SET_OUTPUT(SERVO2_DDR, SERVO2_PIN);
	
	// Modo Fast PWM, prescaler 64
	// Para 50Hz con prescaler 64: TOP = 4999
	TCCR2A = (1 << WGM21) | (1 << WGM20);
	TCCR2B = (1 << WGM22) | (1 << CS22);  // Prescaler 64
	
	// Configurar para 50Hz
	OCR2A = 250;  // TOP value para ~50Hz
	
	// Habilitar salidas PWM
	TCCR2A |= (1 << COM2A1) | (1 << COM2B1);
	
	// Posición central inicial
	timer2_set_servo1_us(SERVO_CENTER_US);
	timer2_set_servo2_us(SERVO_CENTER_US);
}

void timer2_set_servo1_us(uint16_t microseconds) {
	// Convertir microsegundos a valor OCR
	// Con prescaler 64 y 16MHz: 1us = 0.25 ticks
	uint8_t ocr_value = (microseconds / 4);
	OCR2A = CONSTRAIN(ocr_value, 62, 125);  // ~1000-2000us
}

void timer2_set_servo2_us(uint16_t microseconds) {
	uint8_t ocr_value = (microseconds / 4);
	OCR2B = CONSTRAIN(ocr_value, 62, 125);
}