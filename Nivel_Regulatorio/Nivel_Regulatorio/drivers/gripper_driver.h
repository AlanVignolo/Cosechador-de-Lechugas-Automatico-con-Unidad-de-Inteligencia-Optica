#ifndef GRIPPER_DRIVER_H
#define GRIPPER_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

// Pines del motor 28BYJ-48
#define GRIPPER_IN1_PIN     34  // PC3
#define GRIPPER_IN2_PIN     35  // PC2
#define GRIPPER_IN3_PIN     36  // PC1
#define GRIPPER_IN4_PIN     37  // PC0

// Estados del gripper
typedef enum {
	GRIPPER_OPEN,
	GRIPPER_CLOSED,
	GRIPPER_OPENING,
	GRIPPER_CLOSING,
	GRIPPER_IDLE
} gripper_state_t;

// Estructura del controlador
typedef struct {
	gripper_state_t state;
	gripper_state_t target_state;
	int16_t current_steps;      // Pasos actuales desde cerrado (0)
	uint8_t phase_index;        // Índice actual en la secuencia
	uint32_t last_step_time;    // Para control de velocidad
	uint16_t step_delay_us;     // Microsegundos entre pasos
} gripper_controller_t;

// Funciones públicas
void gripper_init(void);
void gripper_open(void);
void gripper_close(void);
void gripper_update(void);
bool gripper_is_busy(void);
gripper_state_t gripper_get_state(void);
void gripper_stop(void);
void gripper_set_speed(uint16_t delay_ms);  // Nueva función
int16_t gripper_get_position(void);         // Función para obtener posición
static void gripper_save_state(void);
static void gripper_load_state(void);
void uart_send_gripper_status(void);
void gripper_toggle(void);

#endif