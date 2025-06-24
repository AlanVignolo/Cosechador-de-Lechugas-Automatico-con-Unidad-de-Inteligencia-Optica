#ifndef STEPPER_DRIVER_H
#define STEPPER_DRIVER_H

#include <stdint.h>
#include <stdbool.h>
#include "../moves/motion_profile.h"

// Estados del motor
typedef enum {
	STEPPER_IDLE,
	STEPPER_MOVING,
	STEPPER_HOMING,
	STEPPER_ERROR
} stepper_state_t;

// Estructura para cada eje
typedef struct {
	// Posiciones
	volatile int32_t current_position;
	int32_t target_position;
	
	// Velocidades y aceleración
	uint16_t max_speed;
	uint16_t acceleration;
	volatile uint16_t current_speed;
	
	// Estado y control
	stepper_state_t state;
	bool enabled;
	bool direction;
	
	// Perfil de movimiento
	motion_profile_t profile;
	
} stepper_axis_t;

// Funciones públicas
void stepper_init(void);
void stepper_enable_motors(bool h_enable, bool v_enable);
void stepper_set_speed(uint16_t h_speed, uint16_t v_speed);
void stepper_move_relative(int32_t h_steps, int32_t v_steps);
void stepper_move_absolute(int32_t h_pos, int32_t v_pos);
void stepper_stop_all(void);
bool stepper_is_moving(void);
void stepper_get_position(int32_t* h_pos, int32_t* v_pos);
void stepper_set_position(int32_t h_pos, int32_t v_pos);

// Función para actualizar perfiles de velocidad (llamada periódicamente)
void stepper_update_profiles(void);

#endif // STEPPER_DRIVER_H