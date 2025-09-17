#include "limit_switch.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "../drivers/stepper_driver.h"

static limit_status_t limits = {false, false, false, false};

void limit_switch_init(void) {
	// Configurar pines como entradas con pull-up interno
	// Pins 30-33 est�n en PORTC bits 7-4
	DDRC &= ~((1 << 7) | (1 << 6) | (1 << 5) | (1 << 4));  // Entradas
	PORTC |= (1 << 7) | (1 << 6) | (1 << 5) | (1 << 4);    // Pull-up activado
	
	// Peque�o delay para estabilizar
	for(volatile uint16_t i = 0; i < 1000; i++);
	
	// Leer estado inicial
	limit_switch_update();
}

void limit_switch_update(void) {
	// Leer estado de los switches (activo bajo - presionado = 0)
	uint8_t pinc_state = PINC;
	
	// Actualizar estados con debounce simple
	static uint8_t debounce_counter[4] = {0, 0, 0, 0};
	const uint8_t DEBOUNCE_THRESHOLD = 6;
	
	// H Left (Pin 30 - PC7)
	if (!(pinc_state & (1 << 7))) {
		if (debounce_counter[0] < DEBOUNCE_THRESHOLD) {
			debounce_counter[0]++;
			if (debounce_counter[0] == DEBOUNCE_THRESHOLD) {
				limits.h_left_triggered = true;
				
				// Reportar posici�n cuando toca l�mite
				char pos_msg[64];
				snprintf(pos_msg, sizeof(pos_msg), "POSITION_AT_LIMIT:H=%ld,V=%ld",
				horizontal_axis.current_position, vertical_axis.current_position);
				uart_send_response(pos_msg);
				uart_send_response("LIMIT_H_LEFT_TRIGGERED");
				
				// Terminar calibraci�n autom�ticamente
				stepper_stop_calibration();
                
                if (horizontal_axis.direction) {  // true = izquierda (AJUSTADO)
                    // ENVIAR SNAPSHOTS ANTES DE PARAR (si los hay)
                    extern uint8_t snapshot_count;
                    extern progress_snapshot_t snapshots[];
                    if (snapshot_count > 0) {
                        char snapshot_msg[256];
                        int offset = snprintf(snapshot_msg, sizeof(snapshot_msg), "MOVEMENT_SNAPSHOTS:");
                        for (uint8_t i = 0; i < snapshot_count && i < MAX_SNAPSHOTS; i++) {
                            offset += snprintf(snapshot_msg + offset, sizeof(snapshot_msg) - offset,
                                               "S%d=%ld,%ld;", i+1, snapshots[i].h_mm, snapshots[i].v_mm);
                        }
                        uart_send_response(snapshot_msg);
                        // Resetear snapshots despu�s de enviar
                        snapshot_count = 0;
                    }
                    stepper_stop_horizontal();
                }
			}
		}
		} else {
		debounce_counter[0] = 0;
		limits.h_left_triggered = false;
	}
	
	// H Right (Pin 31 - PC6)
	if (!(pinc_state & (1 << 6))) {
		if (debounce_counter[1] < DEBOUNCE_THRESHOLD) {
			debounce_counter[1]++;
			if (debounce_counter[1] == DEBOUNCE_THRESHOLD) {
				limits.h_right_triggered = true;
				
				// Reportar posici�n cuando toca l�mite
				char pos_msg[64];
				snprintf(pos_msg, sizeof(pos_msg), "POSITION_AT_LIMIT:H=%ld,V=%ld",
				horizontal_axis.current_position, vertical_axis.current_position);
				uart_send_response(pos_msg);
				uart_send_response("LIMIT_H_RIGHT_TRIGGERED");
				
				// Terminar calibraci�n autom�ticamente
				stepper_stop_calibration();
                
                if (!horizontal_axis.direction) {  // false = derecha (AJUSTADO)
                    // ENVIAR SNAPSHOTS ANTES DE PARAR (si los hay)
                    extern uint8_t snapshot_count;
                    extern progress_snapshot_t snapshots[];
                    if (snapshot_count > 0) {
                        char snapshot_msg[256];
                        int offset = snprintf(snapshot_msg, sizeof(snapshot_msg), "MOVEMENT_SNAPSHOTS:");
                        for (uint8_t i = 0; i < snapshot_count && i < MAX_SNAPSHOTS; i++) {
                            offset += snprintf(snapshot_msg + offset, sizeof(snapshot_msg) - offset,
                                               "S%d=%ld,%ld;", i+1, snapshots[i].h_mm, snapshots[i].v_mm);
                        }
                        uart_send_response(snapshot_msg);
                        // Resetear snapshots despu�s de enviar
                        snapshot_count = 0;
                    }
                    stepper_stop_horizontal();
                }
			}
		}
		} else {
		debounce_counter[1] = 0;
		limits.h_right_triggered = false;
	}
	
	// V Down (Pin 32 - PC5)
	if (!(pinc_state & (1 << 5))) {
		if (debounce_counter[2] < DEBOUNCE_THRESHOLD) {
			debounce_counter[2]++;
			if (debounce_counter[2] == DEBOUNCE_THRESHOLD) {
				limits.v_down_triggered = true;
				
				// Reportar posici�n cuando toca l�mite
				char pos_msg[64];
				snprintf(pos_msg, sizeof(pos_msg), "POSITION_AT_LIMIT:H=%ld,V=%ld",
				horizontal_axis.current_position, vertical_axis.current_position);
				uart_send_response(pos_msg);
				uart_send_response("LIMIT_V_DOWN_TRIGGERED");
				
				// Terminar calibraci�n autom�ticamente
				stepper_stop_calibration();
                
                if (vertical_axis.direction) {
                    // ENVIAR SNAPSHOTS ANTES DE PARAR (si los hay)
                    extern uint8_t snapshot_count;
                    extern progress_snapshot_t snapshots[];
                    if (snapshot_count > 0) {
                        char snapshot_msg[256];
                        int offset = snprintf(snapshot_msg, sizeof(snapshot_msg), "MOVEMENT_SNAPSHOTS:");
                        for (uint8_t i = 0; i < snapshot_count && i < MAX_SNAPSHOTS; i++) {
                            offset += snprintf(snapshot_msg + offset, sizeof(snapshot_msg) - offset,
                                               "S%d=%ld,%ld;", i+1, snapshots[i].h_mm, snapshots[i].v_mm);
                        }
                        uart_send_response(snapshot_msg);
                        // Resetear snapshots despu�s de enviar
                        snapshot_count = 0;
                    }
                    stepper_stop_vertical();
                }
			}
		}
		} else {
		debounce_counter[2] = 0;
		limits.v_down_triggered = false;
	}
	
	// V Up (Pin 33 - PC4)
	if (!(pinc_state & (1 << 4))) {
		if (debounce_counter[3] < DEBOUNCE_THRESHOLD) {
			debounce_counter[3]++;
			if (debounce_counter[3] == DEBOUNCE_THRESHOLD) {
				limits.v_up_triggered = true;
				
				// Reportar posici�n cuando toca l�mite
				char pos_msg[64];
				snprintf(pos_msg, sizeof(pos_msg), "POSITION_AT_LIMIT:H=%ld,V=%ld",
				horizontal_axis.current_position, vertical_axis.current_position);
				uart_send_response(pos_msg);
				uart_send_response("LIMIT_V_UP_TRIGGERED");
				
				// Terminar calibraci�n autom�ticamente
				stepper_stop_calibration();
                
                if (!vertical_axis.direction) {
                    // ENVIAR SNAPSHOTS ANTES DE PARAR (si los hay)
                    extern uint8_t snapshot_count;
                    extern progress_snapshot_t snapshots[];
                    if (snapshot_count > 0) {
                        char snapshot_msg[256];
                        int offset = snprintf(snapshot_msg, sizeof(snapshot_msg), "MOVEMENT_SNAPSHOTS:");
                        for (uint8_t i = 0; i < snapshot_count && i < MAX_SNAPSHOTS; i++) {
                            offset += snprintf(snapshot_msg + offset, sizeof(snapshot_msg) - offset,
                                               "S%d=%ld,%ld;", i+1, snapshots[i].h_mm, snapshots[i].v_mm);
                        }
                        uart_send_response(snapshot_msg);
                        // Resetear snapshots despu�s de enviar
                        snapshot_count = 0;
                    }
                    stepper_stop_vertical();
                }
			}
		}
		} else {
		debounce_counter[3] = 0;
		limits.v_up_triggered = false;
	}
}

bool limit_switch_check_h_movement(bool direction) {
	// Verificar si el movimiento horizontal está permitido
	// AJUSTADO: direction=true es izquierda, direction=false es derecha
	if (direction && limits.h_left_triggered) {
		return false;  // No permitir movimiento a la izquierda si está activado LEFT
	}
	if (!direction && limits.h_right_triggered) {
		return false;  // No permitir movimiento a la derecha si está activado RIGHT
	}
	return true;  // Movimiento permitido
}

bool limit_switch_check_v_movement(bool direction) {
	// Verificar si el movimiento vertical está permitido
	if (!direction && limits.v_up_triggered) {
		return false;  // No permitir movimiento hacia ARRIBA si est� activado UP
	}
	if (direction && limits.v_down_triggered) {
		return false;  // No permitir movimiento hacia ABAJO si est� activado DOWN
	}
	return true;  // Movimiento permitido
}

limit_status_t limit_switch_get_status(void) {
	return limits;
}

void limit_switch_emergency_stop(void) {
	// Detener todos los movimientos inmediatamente
	stepper_stop_all();
}