#include "stepper_speed.h"
#include "timer_control.h"

extern stepper_motor_t motor_h1, motor_h2, motor_v;

static uint32_t calculate_speed(stepper_motor_t* motor) {
	int32_t distance = abs(motor->target_position - motor->current_position);
	uint32_t decel_distance = (motor->current_speed * motor->current_speed) /
	(2 * motor->acceleration);
	
	if (distance <= decel_distance && motor->state != MOTOR_DECEL) {
		motor->state = MOTOR_DECEL;
	}
	
	switch (motor->state) {
		case MOTOR_ACCEL:
		if (motor->current_speed < motor->target_speed) {
			motor->current_speed += motor->acceleration / 100;
			if (motor->current_speed > motor->target_speed) {
				motor->current_speed = motor->target_speed;
				motor->state = MOTOR_CONSTANT;
			}
		}
		break;
		
		case MOTOR_DECEL:
		if (motor->current_speed > MIN_SPEED) {
			motor->current_speed -= motor->acceleration / 100;
			if (motor->current_speed < MIN_SPEED) {
				motor->current_speed = MIN_SPEED;
			}
		}
		break;
	}
	
	return motor->current_speed;
}

void stepper_update_speed_h(void) {
	uint32_t new_speed = calculate_speed(&motor_h1);
	motor_h2.current_speed = new_speed;
	timer1_set_frequency(new_speed);
}

void stepper_update_speed_v(void) {
	uint32_t new_speed = calculate_speed(&motor_v);
	timer3_set_frequency(new_speed);
}