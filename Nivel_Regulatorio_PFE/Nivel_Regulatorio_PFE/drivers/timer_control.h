#ifndef TIMER_CONTROL_H
#define TIMER_CONTROL_H

#include <stdint.h>
#include <stdbool.h>

// Callbacks para ISR de cada timer
typedef void (*timer_callback_t)(void);

// Inicialización de timers
void timer1_init_stepper(void);   // Timer1 para steppers horizontales
void timer3_init_stepper(void);   // Timer3 para stepper vertical
void timer2_init_servo(void);     // Timer2 para servos

// Control de frecuencia para steppers
void timer1_set_frequency(uint32_t freq_hz);
void timer3_set_frequency(uint32_t freq_hz);

// Control PWM para servos
void timer2_set_servo1_us(uint16_t microseconds);
void timer2_set_servo2_us(uint16_t microseconds);

// Habilitar/deshabilitar timers
void timer1_enable(bool enable);
void timer3_enable(bool enable);

// Registrar callbacks
void timer1_set_callback(timer_callback_t callback);
void timer3_set_callback(timer_callback_t callback);

#endif