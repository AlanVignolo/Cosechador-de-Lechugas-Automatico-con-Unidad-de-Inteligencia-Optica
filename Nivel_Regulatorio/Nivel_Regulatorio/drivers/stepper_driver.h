#ifndef STEPPER_DRIVER_H
#define STEPPER_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

// Configuración de pines
#define MOTOR_H1_STEP_PIN    11  // OC1A
#define MOTOR_H1_DIR_PIN     22
#define MOTOR_H1_ENABLE_PIN  23

#define MOTOR_H2_STEP_PIN    12  // OC1B
#define MOTOR_H2_DIR_PIN     24
#define MOTOR_H2_ENABLE_PIN  25

#define MOTOR_V_STEP_PIN     5   // OC3A
#define MOTOR_V_DIR_PIN      26
#define MOTOR_V_ENABLE_PIN   27

// Estados de movimiento
typedef enum {
	STEPPER_IDLE = 0,
	STEPPER_MOVING,
	STEPPER_ACCELERATING,
	STEPPER_DECELERATING
} stepper_state_t;

// Estructura para cada eje
typedef struct {
	int32_t current_position;    // Posición actual en pasos
	int32_t target_position;     // Posición objetivo
	uint16_t current_speed;      // Velocidad actual (pasos/segundo)
	uint16_t max_speed;          // Velocidad máxima
	uint16_t acceleration;       // Aceleración (pasos/segundo²)
	stepper_state_t state;       // Estado actual
	bool direction;              // true = positivo, false = negativo
	bool enabled;                // Motor habilitado
} stepper_axis_t;

// Funciones principales
void stepper_init(void);
void stepper_enable_motors(bool h_enable, bool v_enable);
void stepper_set_speed(uint16_t h_speed, uint16_t v_speed);
void stepper_move_relative(int32_t h_steps, int32_t v_steps);
void stepper_move_absolute(int32_t h_pos, int32_t v_pos);
void stepper_stop_all(void);
bool stepper_is_moving(void);

// Funciones de estado
void stepper_get_position(int32_t* h_pos, int32_t* v_pos);
void stepper_set_position(int32_t h_pos, int32_t v_pos);

void stepper_debug_motor_state(void);
#endif