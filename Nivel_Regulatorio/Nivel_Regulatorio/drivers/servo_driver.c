#include "servo_driver.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include "../config/system_config.h"
#include <avr/eeprom.h>

// Direcciones EEPROM
#define EEPROM_SERVO1_POS  0x00
#define EEPROM_SERVO2_POS  0x01
#define EEPROM_MAGIC       0x02
#define EEPROM_MAGIC_VALUE 0xAA

// Variables para tiempo independiente con Timer2
static volatile uint32_t servo_millis = 0;

// Declaración adelantada
static void servo_save_positions(void);
static void servo_set_position_raw(uint8_t servo_num, uint8_t angle);

static servo_controller_t servo_ctrl = {0};

// ISR Timer2 - 1000Hz para actualización suave
ISR(TIMER2_COMPA_vect) {
	servo_millis++;
}

// Función para obtener tiempo en ms
static uint32_t servo_get_millis(void) {
	uint32_t ms;
	uint8_t oldSREG = SREG;
	cli();
	ms = servo_millis;
	SREG = oldSREG;
	return ms;
}

void servo_init(void) {
	// Configurar pines como salidas
	DDRL |= (1 << 3) | (1 << 4);  // Pin 46 (PL3/OC5A) y Pin 45 (PL4/OC5B)
	
	// Configurar Timer5 para PWM de servos 50Hz
	TCCR5A = (1 << COM5A1) | (1 << COM5B1) | (1 << WGM51);
	TCCR5B = (1 << WGM53) | (1 << WGM52) | (1 << CS51);  // Fast PWM, prescaler 8
	ICR5 = 39999;  // TOP value para 50Hz
	
	// Configurar Timer2 para 1000Hz (1ms)
	TCCR2A = (1 << WGM21);     // Modo CTC
	TCCR2B = (1 << CS22) | (1 << CS21) | (1 << CS20);  // Prescaler 1024
	OCR2A = 15;                 // 16MHz / 1024 / 16 = ~1000Hz
	TIMSK2 = (1 << OCIE2A);     // Habilitar interrupción
	
	// Inicializar en posición por defecto PRIMERO
	servo_ctrl.current_pos1 = SERVO1_DEFAULT_POS;
	servo_ctrl.current_pos2 = SERVO2_DEFAULT_POS;
	
	// Leer posiciones guardadas de EEPROM
	uint8_t magic = eeprom_read_byte((uint8_t*)EEPROM_MAGIC);
	
	if (magic == EEPROM_MAGIC_VALUE) {
		uint8_t saved_pos1 = eeprom_read_byte((uint8_t*)EEPROM_SERVO1_POS);
		uint8_t saved_pos2 = eeprom_read_byte((uint8_t*)EEPROM_SERVO2_POS);
		
		if (saved_pos1 <= 180 && saved_pos2 <= 180) {
			servo_ctrl.current_pos1 = saved_pos1;
			servo_ctrl.current_pos2 = saved_pos2;
		}
		} else {
		// Primera vez - guardar valores por defecto
		servo_save_positions();
	}
	
	// Mover a posición inicial
	servo_set_position_raw(1, servo_ctrl.current_pos1);
	servo_set_position_raw(2, servo_ctrl.current_pos2);
	
	servo_ctrl.state = SERVO_IDLE;
}

static void servo_save_positions(void) {
	eeprom_update_byte((uint8_t*)EEPROM_SERVO1_POS, servo_ctrl.current_pos1);
	eeprom_update_byte((uint8_t*)EEPROM_SERVO2_POS, servo_ctrl.current_pos2);
	eeprom_update_byte((uint8_t*)EEPROM_MAGIC, EEPROM_MAGIC_VALUE);
}

static void servo_set_position_raw(uint8_t servo_num, uint8_t angle) {
	// Aplicar límites
	if (servo_num == 1) {
		if (angle < SERVO1_MIN_ANGLE) angle = SERVO1_MIN_ANGLE;
		if (angle > SERVO1_MAX_ANGLE) angle = SERVO1_MAX_ANGLE;
		} else if (servo_num == 2) {
		if (angle < SERVO2_MIN_ANGLE) angle = SERVO2_MIN_ANGLE;
		if (angle > SERVO2_MAX_ANGLE) angle = SERVO2_MAX_ANGLE;
	}
	
	// PWM para rango completo 180°
	// La mayoría de servos usan 1ms-2ms, pero algunos necesitan 0.5ms-2.5ms
	// Vamos a usar un rango intermedio: 0.75ms-2.25ms
	// Con TOP=39999 y 50Hz:
	// 0.75ms = 1500 counts (0°)
	// 1.5ms = 3000 counts (90°)
	// 2.25ms = 4500 counts (180°)
	
	uint16_t min_count = SERVO_PWM_MIN;
	uint16_t max_count = SERVO_PWM_MAX;
	
	uint16_t ocr_value = min_count +
	((uint32_t)(max_count - min_count) * angle) / 180;
	
	if (servo_num == 1) {
		OCR5A = ocr_value;
		} else if (servo_num == 2) {
		OCR5B = ocr_value;
	}
	
	char msg[64];
	snprintf(msg, sizeof(msg), "SERVO_CHANGED:%d,%d", servo_num, angle);
	uart_send_response(msg);
}

void servo_set_position(uint8_t servo_num, uint8_t angle) {
	servo_set_position_raw(servo_num, angle);
	
	if (servo_num == 1) {
		servo_ctrl.current_pos1 = angle;
		} else if (servo_num == 2) {
		servo_ctrl.current_pos2 = angle;
	}
	
	servo_save_positions();
}

void servo_move_to(uint8_t angle1, uint8_t angle2, uint16_t time_ms) {
	// Aplicar límites
	if (angle1 < SERVO1_MIN_ANGLE) angle1 = SERVO1_MIN_ANGLE;
	if (angle1 > SERVO1_MAX_ANGLE) angle1 = SERVO1_MAX_ANGLE;
	if (angle2 < SERVO2_MIN_ANGLE) angle2 = SERVO2_MIN_ANGLE;
	if (angle2 > SERVO2_MAX_ANGLE) angle2 = SERVO2_MAX_ANGLE;
	
	if (time_ms == 0) {
		// Movimiento instantáneo
		servo_ctrl.current_pos1 = angle1;
		servo_ctrl.current_pos2 = angle2;
		servo_set_position_raw(1, angle1);
		servo_set_position_raw(2, angle2);
		servo_save_positions();
		servo_ctrl.state = SERVO_IDLE;
		} else {
		// CRÍTICO: Asegurar que start_pos use las posiciones ACTUALES
		servo_ctrl.start_pos1 = servo_ctrl.current_pos1;
		servo_ctrl.start_pos2 = servo_ctrl.current_pos2;
		servo_ctrl.target_pos1 = angle1;
		servo_ctrl.target_pos2 = angle2;
		servo_ctrl.start_time_ms = servo_get_millis();
		servo_ctrl.duration_ms = time_ms;
		servo_ctrl.state = SERVO_MOVING;
	}
}

void servo_update(void) {
	if (servo_ctrl.state != SERVO_MOVING) return;
	
	uint32_t current_time = servo_get_millis();
	uint32_t elapsed_time = current_time - servo_ctrl.start_time_ms;
	
	if (elapsed_time >= servo_ctrl.duration_ms) {
		// Movimiento completado
		servo_ctrl.current_pos1 = servo_ctrl.target_pos1;
		servo_ctrl.current_pos2 = servo_ctrl.target_pos2;
		servo_set_position_raw(1, servo_ctrl.target_pos1);
		servo_set_position_raw(2, servo_ctrl.target_pos2);
		servo_save_positions();
		servo_ctrl.state = SERVO_IDLE;
		} else {
		// Interpolación lineal
		float progress = (float)elapsed_time / (float)servo_ctrl.duration_ms;
		
		// Calcular posiciones actuales
		uint8_t new_pos1 = servo_ctrl.start_pos1 +
		(uint8_t)((servo_ctrl.target_pos1 - servo_ctrl.start_pos1) * progress);
		uint8_t new_pos2 = servo_ctrl.start_pos2 +
		(uint8_t)((servo_ctrl.target_pos2 - servo_ctrl.start_pos2) * progress);
		
		if (new_pos1 != servo_ctrl.current_pos1 || new_pos2 != servo_ctrl.current_pos2) {
			servo_ctrl.current_pos1 = new_pos1;
			servo_ctrl.current_pos2 = new_pos2;
			servo_set_position_raw(1, new_pos1);
			servo_set_position_raw(2, new_pos2);
		}
	}
}

bool servo_is_busy(void) {
	return (servo_ctrl.state == SERVO_MOVING);
}

uint8_t servo_get_current_position(uint8_t servo_num) {
	return (servo_num == 1) ? servo_ctrl.current_pos1 : servo_ctrl.current_pos2;
}