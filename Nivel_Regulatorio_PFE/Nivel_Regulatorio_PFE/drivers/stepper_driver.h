#ifndef STEPPER_DRIVER_H
#define STEPPER_DRIVER_H

#include <stdint.h>
#include <stdbool.h>
#include "utils/common.h"

// Estructura para cada motor stepper
typedef struct {
	// Posición
	int32_t current_position;    // Posición actual en pasos
	int32_t target_position;     // Posición objetivo en pasos
	
	// Velocidad
	uint32_t current_speed;      // Velocidad actual (pasos/seg)
	uint32_t target_speed;       // Velocidad objetivo
	uint32_t max_speed;          // Velocidad máxima permitida
	
	// Aceleración
	uint32_t acceleration;       // Pasos/seg²
	uint32_t decel_start_pos;    // Posición donde empezar a frenar
	
	// Estado
	motor_state_t state;
	direction_t direction;
	bool enabled;
	
	// Configuración de pines
	volatile uint8_t* step_port;
	uint8_t step_pin;
	volatile uint8_t* dir_port;
	uint8_t dir_pin;
	volatile uint8_t* enable_port;
	uint8_t enable_pin;
	
} stepper_motor_t;

// Estructura para control coordinado de ejes
typedef struct {
	stepper_motor_t* motor_h1;   // Motor horizontal 1
	stepper_motor_t* motor_h2;   // Motor horizontal 2
	stepper_motor_t* motor_v;    // Motor vertical
	
	// Para movimiento coordinado
	float target_x_mm;
	float target_y_mm;
	float current_x_mm;
	float current_y_mm;
	
	// Límites
	limit_status_t limits;
	bool limits_enabled;
	
} motion_controller_t;

// === Funciones básicas ===
void stepper_init(void);
void stepper_enable_all(bool enable);
void stepper_emergency_stop(void);

// === Control individual de motores ===
void stepper_set_target_position(stepper_motor_t* motor, int32_t position);
void stepper_set_speed(stepper_motor_t* motor, uint32_t speed);
void stepper_set_acceleration(stepper_motor_t* motor, uint32_t accel);

// === Movimiento coordinado ===
void stepper_move_to_xy(float x_mm, float y_mm);
void stepper_home_all(void);
bool stepper_is_moving(void);

// === Callbacks para timers ===
void stepper_h_isr_callback(void);
void stepper_v_isr_callback(void);

// === Obtener estado ===
void stepper_get_position(float* x_mm, float* y_mm);
motor_state_t stepper_get_state(void);

#endif