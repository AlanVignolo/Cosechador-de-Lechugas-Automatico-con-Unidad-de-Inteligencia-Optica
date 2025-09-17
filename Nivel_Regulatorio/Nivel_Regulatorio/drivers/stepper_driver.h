#ifndef STEPPER_DRIVER_H
#define STEPPER_DRIVER_H

#include <stdint.h>
#include <stdbool.h>
#include "../moves/motion_profile.h"

// Estados del stepper
typedef enum {
	STEPPER_IDLE = 0,
	STEPPER_MOVING,
	STEPPER_HOMING,
	STEPPER_ERROR
} stepper_state_t;

// Estructura para cada eje del stepper
typedef struct {
	int32_t current_position;
	int32_t target_position;
	uint16_t current_speed;
	uint16_t max_speed;
	uint16_t acceleration;
	bool direction;           // true = positivo, false = negativo
	bool enabled;
	stepper_state_t state;
	motion_profile_t profile;
} stepper_axis_t;

// Variables globales accesibles (para debugging)
extern stepper_axis_t horizontal_axis;
extern stepper_axis_t vertical_axis;
extern volatile int32_t relative_h_counter;
extern volatile int32_t relative_v_counter;

// Sistema de snapshots de progreso
#define MAX_SNAPSHOTS 30
typedef struct {
	int32_t h_mm;
	int32_t v_mm;
	int32_t h_steps;
	int32_t v_steps;
} progress_snapshot_t;

extern progress_snapshot_t snapshots[MAX_SNAPSHOTS];
extern uint8_t snapshot_count;

// Funciones públicas
void stepper_init(void);
void stepper_enable_motors(bool h_enable, bool v_enable);
void stepper_set_speed(uint16_t h_speed, uint16_t v_speed);
void stepper_move_relative(int32_t h_steps, int32_t v_steps);
void stepper_move_absolute(int32_t h_pos, int32_t v_pos);
void stepper_stop_all(void);
void stepper_stop_silent(void);
bool stepper_is_moving(void);
void stepper_get_position(int32_t* h_pos, int32_t* v_pos);
void stepper_set_position(int32_t h_pos, int32_t v_pos);
void stepper_update_profiles(void);
static int32_t abs32(int32_t x);
void stepper_stop_horizontal(void);
void stepper_stop_vertical(void);
void stepper_start_calibration(void);
void stepper_stop_calibration(void);
#endif