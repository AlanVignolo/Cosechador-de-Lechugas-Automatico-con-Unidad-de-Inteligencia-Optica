#include "command_parser.h"
#include "../drivers/uart_driver.h"
#include "../drivers/stepper_driver.h"
#include "../config/system_config.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

// Parser manual simple para dos números
static bool parse_two_integers(const char* str, int* x, int* y) {
	char temp_str[32];
	char* comma_pos;
	
	// Copiar string para modificarlo
	strncpy(temp_str, str, sizeof(temp_str) - 1);
	temp_str[sizeof(temp_str) - 1] = '\0';
	
	// Buscar la coma
	comma_pos = strchr(temp_str, ',');
	if (!comma_pos) return false;
	
	// Dividir en dos strings
	*comma_pos = '\0';  // Terminar primer número
	
	// Convertir usando atoi
	*x = atoi(temp_str);
	*y = atoi(comma_pos + 1);
	
	return true;
}

void uart_parse_command(const char* cmd) {
	char response[128];
	
	if (cmd[0] == CMD_MOVE_XY && cmd[1] == ':') {
		int x, y;
		if (parse_two_integers(cmd + 2, &x, &y)) {
			// Convertir mm a pasos (RELATIVO)
			int32_t h_steps_relative = (int32_t)(x * STEPS_PER_MM_H);
			int32_t v_steps_relative = (int32_t)(y * STEPS_PER_MM_V);
			
			// Habilitar motores solo si hay movimiento que hacer
			bool need_h_move = (h_steps_relative != 0);
			bool need_v_move = (v_steps_relative != 0);
			
			stepper_enable_motors(need_h_move, need_v_move);
			
			// Usar movimiento RELATIVO
			stepper_move_relative(h_steps_relative, v_steps_relative);
			
			snprintf(response, sizeof(response), "OK:MOVE_XY:%d,%d", x, y);
			} else {
			snprintf(response, sizeof(response), "ERR:INVALID_PARAMS_MOVE_XY:<%s>", cmd + 2);
		}
	}
	else if (cmd[0] == 'D') {  // Comando debug
		stepper_debug_info();  // Solo llamar la función
		snprintf(response, sizeof(response), "OK:DEBUG");
	}
	else if (cmd[0] == 'E') {  // Debug extendido
		stepper_debug_motor_state();
		snprintf(response, sizeof(response), "OK:DEBUG_STATE");
	}
    else if (cmd[0] == CMD_STOP) {
	    stepper_stop_all();
	    snprintf(response, sizeof(response), "OK:STOP");
    }
	else if (cmd[0] == CMD_HOME) {
		snprintf(response, sizeof(response), "OK:HOME");
	}
	else if (cmd[0] == CMD_STATUS) {
		snprintf(response, sizeof(response), "OK:STATUS:IDLE:0,0");
	}
	else if (cmd[0] == CMD_ARM_POSITION && cmd[1] == ':') {
		snprintf(response, sizeof(response), "OK:ARM_POSITION:%s", cmd + 2);
	}
	else if (cmd[0] == CMD_GRIPPER && cmd[1] == ':') {
		snprintf(response, sizeof(response), "OK:GRIPPER:%s", cmd + 2);
	}
	else if (cmd[0] == CMD_SET_SPEED && cmd[1] == ':') {
		int speed = atoi(cmd + 2);
		snprintf(response, sizeof(response), "OK:SET_SPEED:%d", speed);
	}
	else if (cmd[0] == CMD_ARM_TRAJECTORY && cmd[1] == ':') {
		snprintf(response, sizeof(response), "OK:ARM_TRAJECTORY:%s", cmd + 2);
	}
	else {
		snprintf(response, sizeof(response), "ERR:UNKNOWN_CMD:%s", cmd);
	}
	
	uart_send_response(response);
}