#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>
#include <stdbool.h>

// Tipos de datos comunes
typedef enum {
	AXIS_X,
	AXIS_Y,
	AXIS_COUNT
} axis_t;

typedef enum {
	DIR_FORWARD = 0,
	DIR_REVERSE = 1
} direction_t;

typedef enum {
	MOTOR_IDLE,
	MOTOR_ACCEL,
	MOTOR_CONSTANT,
	MOTOR_DECEL,
	MOTOR_ERROR,
	MOTOR_HOMING
} motor_state_t;

// Estado del sistema completo
typedef enum {
	SYSTEM_IDLE,
	SYSTEM_MOVING,
	SYSTEM_HOMING,
	SYSTEM_ERROR,
	SYSTEM_EMERGENCY_STOP
} system_state_t;

// Estructura para posición
typedef struct {
	float x;        // mm
	float y;        // mm
	int32_t x_steps;    // pasos absolutos
	int32_t y_steps;    // pasos absolutos
} position_t;

// Estructura para el brazo
typedef struct {
	uint8_t servo1_angle;
	uint8_t servo2_angle;
	uint8_t gripper_percent;
} arm_position_t;

// Estructura para límites
typedef struct {
	bool x_min_hit;
	bool x_max_hit;
	bool y_min_hit;
	bool y_max_hit;
} limit_status_t;

// Punto de trayectoria
typedef struct {
	arm_position_t arm_pos;
	uint16_t duration_ms;   // Tiempo para llegar a esta posición
} trajectory_point_t;

// Macros útiles
#define CONSTRAIN(x, min, max) ((x) < (min) ? (min) : ((x) > (max) ? (max) : (x)))
#define ABS(x) ((x) < 0 ? -(x) : (x))
#define SIGN(x) ((x) > 0 ? 1 : ((x) < 0 ? -1 : 0))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

// Conversiones
#define MM_TO_STEPS_H(mm) ((int32_t)((mm) * STEPS_PER_MM_H))
#define MM_TO_STEPS_V(mm) ((int32_t)((mm) * STEPS_PER_MM_V))
#define STEPS_TO_MM_H(steps) ((float)(steps) / STEPS_PER_MM_H)
#define STEPS_TO_MM_V(steps) ((float)(steps) / STEPS_PER_MM_V)

#endif