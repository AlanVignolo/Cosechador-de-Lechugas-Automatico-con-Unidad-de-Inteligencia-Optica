#include "stepper_home.h"
#include "stepper_driver.h"
#include "timer_control.h"
#include "uart_driver.h"

typedef enum {
	HOME_IDLE,
	HOME_X_FIND,
	HOME_X_BACKOFF,
	HOME_Y_FIND,
	HOME_Y_BACKOFF
} home_state_t;

static home_state_t state = HOME_IDLE;
static uint32_t backoff_count = 0;

void stepper_home_init(void) {
	state = HOME_IDLE;
}

void stepper_home_start(void) {
	if (state != HOME_IDLE) return;
	
	state = HOME_X_FIND;
	uart_send_response("HOMING");
	
	// Configurar para buscar límite X
	// ... código de configuración ...
}

void stepper_home_process(void) {
	// Procesar estados de homing
	// ... máquina de estados ...
}

bool stepper_is_homing(void) {
	return state != HOME_IDLE;
}