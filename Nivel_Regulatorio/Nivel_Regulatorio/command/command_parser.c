#include "command_parser.h"
#include "../drivers/uart_driver.h"
#include "../drivers/stepper_driver.h"
#include "../config/system_config.h"
#include "../config/command_protocol.h"
#include "../drivers/servo_driver.h"
#include "../limits/limit_switch.h"
#include "../drivers/gripper_driver.h"
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
			
			// Usar movimiento RELATIVO
			stepper_move_relative(h_steps_relative, v_steps_relative);
			
			snprintf(response, sizeof(response), "OK:MOVE_XY:%d,%d", x, y);
			} else {
			snprintf(response, sizeof(response), "ERR:INVALID_PARAMS_MOVE_XY:<%s>", cmd + 2);
		}
	}
	
	else if (cmd[0] == 'S') {  // CMD_STOP
		stepper_stop_all();
		snprintf(response, sizeof(response), "OK:STOP");
	}
	
	else if (cmd[0] == 'A' && cmd[1] == ':') {  // ARM smooth movement
		// Formato: A:angle1,angle2,time_ms
		// Ejemplo: A:45,90,2000 (mover servo1 a 45°, servo2 a 90° en 2 segundos)
		
		int values[3];
		int count = 0;
		char* ptr = (char*)(cmd + 2);
		
		// Parser simple para 3 valores
		while (*ptr && count < 3) {
			values[count] = atoi(ptr);
			count++;
			// Buscar siguiente número
			while (*ptr && *ptr != ',' && *ptr != '\0') ptr++;
			if (*ptr == ',') ptr++;
		}
		
		if (count == 3) {
			uint8_t angle1 = (uint8_t)values[0];
			uint8_t angle2 = (uint8_t)values[1];
			uint16_t time_ms = (uint16_t)values[2];
			
			// Validar tiempo
			if (time_ms > SERVO_MAX_MOVE_TIME) time_ms = SERVO_MAX_MOVE_TIME;
			
			servo_move_to(angle1, angle2, time_ms);
			
			if (time_ms == 0) {
				snprintf(response, sizeof(response), "OK:ARM_INSTANT:%d,%d", angle1, angle2);
				} else {
				snprintf(response, sizeof(response), "OK:ARM_SMOOTH:%d,%d,%d", angle1, angle2, time_ms);
			}
			} else {
			snprintf(response, sizeof(response), "ERR:INVALID_ARM_PARAMS");
		}
	}
	
	else if (cmd[0] == 'R' && cmd[1] == 'A') {  // Reset Arms
		// Resetear brazos a posición por defecto (90°)
		servo_set_position(1, 90);
		servo_set_position(2, 90);
		snprintf(response, sizeof(response), "OK:ARMS_RESET");
	}
	
	else if (cmd[0] == 'P' && cmd[1] == ':') {  // Position servo individual
		// Formato: P:servo_num,angle
		// Ejemplo: P:1,45 (servo 1 a 45 grados)
		int servo_num, angle;
		if (parse_two_integers(cmd + 2, &servo_num, &angle)) {
			if (servo_num == 1 || servo_num == 2) {
				servo_set_position(servo_num, angle);
				snprintf(response, sizeof(response), "OK:SERVO%d_POS:%d", servo_num, angle);
				} else {
				snprintf(response, sizeof(response), "ERR:INVALID_SERVO_NUM");
			}
			} else {
			snprintf(response, sizeof(response), "ERR:INVALID_PARAMS_POS");
		}
	}
	
	else if (cmd[0] == 'G' && cmd[1] == 'T') {  // GT - Toggle Gripper
		gripper_toggle();
		snprintf(response, sizeof(response), "OK:GRIPPER_TOGGLE");
	}
	
	else if (cmd[0] == 'V' && cmd[1] == ':') {
		int h_speed, v_speed;
		if (parse_two_integers(cmd + 2, &h_speed, &v_speed)) {
			if (h_speed > 0 && h_speed <= 15000) {
				horizontal_axis.max_speed = h_speed;
			}
			if (v_speed > 0 && v_speed <= 15000) {
				vertical_axis.max_speed = v_speed;
			}
			snprintf(response, sizeof(response), "OK:VELOCIDADES:%d,%d",
			horizontal_axis.max_speed, vertical_axis.max_speed);
			} else {
			snprintf(response, sizeof(response), "ERR:INVALID_PARAMS_VELOCIDADES");
		}
	}
	
	else if (cmd[0] == 'L') {
		limit_status_t status = limit_switch_get_status();
		snprintf(response, sizeof(response), "LIMITS:H_L=%d,H_R=%d,V_U=%d,V_D=%d",
		status.h_left_triggered ? 1 : 0,
		status.h_right_triggered ? 1 : 0,
		status.v_up_triggered ? 1 : 0,
		status.v_down_triggered ? 1 : 0);
	}
	
	else if (cmd[0] == 'Q') {  // Query - consultar estado actual
		// Obtener posiciones actuales de los servos
		uint8_t servo1_pos = servo_get_current_position(1);
		uint8_t servo2_pos = servo_get_current_position(2);
		
		snprintf(response, sizeof(response), "SERVO_POS:%d,%d", servo1_pos, servo2_pos);
	}
	
	else if (cmd[0] == 'G' && cmd[1] == '?') {
		gripper_state_t state = gripper_get_state();
		int16_t position = gripper_get_position();
	
		const char* state_str;
		switch(state) {
			case GRIPPER_OPEN: state_str = "OPEN"; break;
			case GRIPPER_CLOSED: state_str = "CLOSED"; break;
			case GRIPPER_OPENING: state_str = "OPENING"; break;
			case GRIPPER_CLOSING: state_str = "CLOSING"; break;
			default: state_str = "IDLE"; break;
		}
	
		snprintf(response, sizeof(response), "GRIPPER_STATUS:%s,%d", state_str, position);
	}
	
	else if (cmd[0] == 'C' && cmd[1] == 'S') {  // CS - Calibration Start
		stepper_start_calibration();
		snprintf(response, sizeof(response), "OK:CALIBRATION_STARTED");
	}

	else if (cmd[0] == 'C' && cmd[1] == 'E') {  // CE - Calibration End
		stepper_stop_calibration();
		snprintf(response, sizeof(response), "OK:CALIBRATION_ENDED");
	}
	
	else {
		snprintf(response, sizeof(response), "ERR:UNKNOWN_CMD:%s", cmd);
	}
	
	uart_send_response(response);
}