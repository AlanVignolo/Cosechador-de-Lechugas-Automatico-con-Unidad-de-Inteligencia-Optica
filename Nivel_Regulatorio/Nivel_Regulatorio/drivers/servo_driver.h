#ifndef SERVO_DRIVER_H
#define SERVO_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

// Configuración de servos - Timer5
#define SERVO1_PIN          46  // PL3/OC5A
#define SERVO2_PIN          45  // PL4/OC5B

// Estados del controlador de servos
typedef enum {
	SERVO_IDLE,
	SERVO_MOVING
} servo_state_t;

// Estructura para interpolación suave
typedef struct {
	// Posiciones
	uint8_t start_pos1;
	uint8_t start_pos2;
	uint8_t target_pos1;
	uint8_t target_pos2;
	uint8_t current_pos1;
	uint8_t current_pos2;
	
	// Control de tiempo
	uint32_t start_time_ms;
	uint32_t duration_ms;
	
	servo_state_t state;
} servo_controller_t;

// Funciones públicas
void servo_init(void);
void servo_set_position(uint8_t servo_num, uint8_t angle);
void servo_move_to(uint8_t angle1, uint8_t angle2, uint16_t time_ms);
void servo_update(void);
bool servo_is_busy(void);
uint8_t servo_get_current_position(uint8_t servo_num);

#endif