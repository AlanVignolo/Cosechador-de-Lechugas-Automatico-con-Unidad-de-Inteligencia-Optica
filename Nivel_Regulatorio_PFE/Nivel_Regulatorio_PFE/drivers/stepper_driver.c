#include "stepper_driver.h"
#include "timer_control.h"
#include "uart_driver.h"
#include "config/hardware_config.h"
#include "config/system_config.h"
#include "utils/pin_macros.h"
#include <stdlib.h>

// Instancias de motores
static stepper_motor_t motor_h1;
static stepper_motor_t motor_h2;
static stepper_motor_t motor_v;

// Controlador de movimiento
static motion_controller_t motion;

// === INICIALIZACIÓN ===

static void init_motor_pins(stepper_motor_t* motor) {
	SET_OUTPUT(*(motor->step_port - 1), motor->step_pin);
	SET_OUTPUT(*(motor->dir_port - 1), motor->dir_pin);
	SET_OUTPUT(*(motor->enable_port - 1), motor->enable_pin);
	
	SET_BIT(*motor->enable_port, motor->enable_pin);  // Disabled
	CLEAR_BIT(*motor->step_port, motor->step_pin);
	CLEAR_BIT(*motor->dir_port, motor->dir_pin);
}

void stepper_init(void) {
	// Motor H1
	motor_h1.step_port = &STEP_H1_PORT;
	motor_h1.step_pin = STEP_H1_PIN;
	motor_h1.dir_port = &DIR_H1_PORT;
	motor_h1.dir_pin = DIR_H1_PIN;
	motor_h1.enable_port = &ENABLE_H1_PORT;
	motor_h1.enable_pin = ENABLE_H1_PIN;
	motor_h1.max_speed = MAX_SPEED_H;
	motor_h1.acceleration = ACCEL_H;
	init_motor_pins(&motor_h1);
	
	// Motor H2
	motor_h2.step_port = &STEP_H2_PORT;
	motor_h2.step_pin = STEP_H2_PIN;
	motor_h2.dir_port = &DIR_H2_PORT;
	motor_h2.dir_pin = DIR_H2_PIN;
	motor_h2.enable_port = &ENABLE_H2_PORT;
	motor_h2.enable_pin = ENABLE_H2_PIN;
	motor_h2.max_speed = MAX_SPEED_H;
	motor_h2.acceleration = ACCEL_H;
	init_motor_pins(&motor_h2);
	
	// Motor V
	motor_v.step_port = &STEP_V_PORT;
	motor_v.step_pin = STEP_V_PIN;
	motor_v.dir_port = &DIR_V_PORT;
	motor_v.dir_pin = DIR_V_PIN;
	motor_v.enable_port = &ENABLE_V_PORT;
	motor_v.enable_pin = ENABLE_V_PIN;
	motor_v.max_speed = MAX_SPEED_V;
	motor_v.acceleration = ACCEL_V;
	init_motor_pins(&motor_v);
	
	// Controlador
	motion.motor_h1 = &motor_h1;
	motion.motor_h2 = &motor_h2;
	motion.motor_v = &motor_v;
	motion.limits_enabled = true;
	
	// Callbacks
	timer1_set_callback(stepper_h_isr_callback);
	timer3_set_callback(stepper_v_isr_callback);
}

// === CONTROL BÁSICO ===

void stepper_enable_all(bool enable) {
	if (enable) {
		CLEAR_BIT(*motor_h1.enable_port, motor_h1.enable_pin);
		CLEAR_BIT(*motor_h2.enable_port, motor_h2.enable_pin);
		CLEAR_BIT(*motor_v.enable_port, motor_v.enable_pin);
		} else {
		SET_BIT(*motor_h1.enable_port, motor_h1.enable_pin);
		SET_BIT(*motor_h2.enable_port, motor_h2.enable_pin);
		SET_BIT(*motor_v.enable_port, motor_v.enable_pin);
	}
	
	motor_h1.enabled = enable;
	motor_h2.enabled = enable;
	motor_v.enabled = enable;
}

void stepper_emergency_stop(void) {
	timer1_enable(false);
	timer3_enable(false);
	
	motor_h1.state = MOTOR_IDLE;
	motor_h2.state = MOTOR_IDLE;
	motor_v.state = MOTOR_IDLE;
	
	stepper_enable_all(false);
	uart_send_response("ESTOP");
}

// === MOVIMIENTO ===

static void set_motor_direction(stepper_motor_t* motor, direction_t dir) {
	motor->direction = dir;
	if (dir == DIR_FORWARD) {
		CLEAR_BIT(*motor->dir_port, motor->dir_pin);
		} else {
		SET_BIT(*motor->dir_port, motor->dir_pin);
	}
}

void stepper_move_to_xy(float x_mm, float y_mm) {
	// Validar
	if (x_mm < 0 || x_mm > MAX_X_MM || y_mm < 0 || y_mm > MAX_Y_MM) {
		uart_send_error("ERR:BOUNDS");
		return;
	}
	
	// Calcular pasos
	int32_t x_steps = MM_TO_STEPS_H(x_mm);
	int32_t y_steps = MM_TO_STEPS_V(y_mm);
	
	// Configurar horizontal
	motor_h1.target_position = x_steps;
	motor_h2.target_position = x_steps;
	motor_h1.target_speed = MAX_SPEED_H * 0.8;
	motor_h2.target_speed = motor_h1.target_speed;
	
	direction_t h_dir = (x_steps > motor_h1.current_position) ? DIR_FORWARD : DIR_REVERSE;
	set_motor_direction(&motor_h1, h_dir);
	set_motor_direction(&motor_h2, h_dir);
	
	// Configurar vertical
	motor_v.target_position = y_steps;
	motor_v.target_speed = MAX_SPEED_V * 0.8;
	
	direction_t v_dir = (y_steps > motor_v.current_position) ? DIR_FORWARD : DIR_REVERSE;
	set_motor_direction(&motor_v, v_dir);
	
	// Activar
	stepper_enable_all(true);
	
	if (motor_h1.target_position != motor_h1.current_position) {
		motor_h1.state = MOTOR_ACCEL;
		motor_h2.state = MOTOR_ACCEL;
		timer1_set_frequency(MIN_SPEED);
		timer1_enable(true);
	}
	
	if (motor_v.target_position != motor_v.current_position) {
		motor_v.state = MOTOR_ACCEL;
		timer3_set_frequency(MIN_SPEED);
		timer3_enable(true);
	}
	
	uart_send_response("MOV");
}

// === ISR CALLBACKS ===

void stepper_h_isr_callback(void) {
	static uint32_t step_count = 0;
	
	// Toggle pins
	TOGGLE_BIT(*motor_h1.step_port, motor_h1.step_pin);
	TOGGLE_BIT(*motor_h2.step_port, motor_h2.step_pin);
	
	// Contar solo en flanco alto
	if (!READ_BIT(*motor_h1.step_port, motor_h1.step_pin)) {
		return;
	}
	
	// Actualizar posición
	if (motor_h1.direction == DIR_FORWARD) {
		motor_h1.current_position++;
		motor_h2.current_position++;
		} else {
		motor_h1.current_position--;
		motor_h2.current_position--;
	}
	
	// Verificar llegada
	if (motor_h1.current_position == motor_h1.target_position) {
		timer1_enable(false);
		motor_h1.state = MOTOR_IDLE;
		motor_h2.state = MOTOR_IDLE;
		if (motor_v.state == MOTOR_IDLE) {
			uart_send_response("ARR");
		}
	}
	
	// Ajustar velocidad cada 100 pasos
	if (++step_count >= 100) {
		step_count = 0;
		stepper_update_speed_h();
	}
}

void stepper_v_isr_callback(void) {
	static uint32_t step_count = 0;
	
	TOGGLE_BIT(*motor_v.step_port, motor_v.step_pin);
	
	if (!READ_BIT(*motor_v.step_port, motor_v.step_pin)) {
		return;
	}
	
	if (motor_v.direction == DIR_FORWARD) {
		motor_v.current_position++;
		} else {
		motor_v.current_position--;
	}
	
	if (motor_v.current_position == motor_v.target_position) {
		timer3_enable(false);
		motor_v.state = MOTOR_IDLE;
		if (motor_h1.state == MOTOR_IDLE) {
			uart_send_response("ARR");
		}
	}
	
	if (++step_count >= 100) {
		step_count = 0;
		stepper_update_speed_v();
	}
}

// === ESTADO ===

void stepper_get_position(float* x_mm, float* y_mm) {
	*x_mm = STEPS_TO_MM_H(motor_h1.current_position);
	*y_mm = STEPS_TO_MM_V(motor_v.current_position);
}

bool stepper_is_moving(void) {
	return (motor_h1.state != MOTOR_IDLE || motor_v.state != MOTOR_IDLE);
}