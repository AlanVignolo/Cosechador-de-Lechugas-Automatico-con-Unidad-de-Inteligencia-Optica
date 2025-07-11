#ifndef LIMIT_SWITCH_H
#define LIMIT_SWITCH_H

#include <stdint.h>
#include <stdbool.h>

// Definición de pines
#define LIMIT_H_LEFT_PIN    30  // PC7
#define LIMIT_H_RIGHT_PIN   31  // PC6
#define LIMIT_V_UP_PIN      32  // PC5
#define LIMIT_V_DOWN_PIN    33  // PC4

// Estados de los límites
typedef struct {
	bool h_left_triggered;
	bool h_right_triggered;
	bool v_up_triggered;
	bool v_down_triggered;
} limit_status_t;

// Funciones públicas
void limit_switch_init(void);
void limit_switch_update(void);
bool limit_switch_check_h_movement(bool direction);  // true = derecha/positivo
bool limit_switch_check_v_movement(bool direction);  // true = arriba/positivo
limit_status_t limit_switch_get_status(void);
void limit_switch_emergency_stop(void);

#endif