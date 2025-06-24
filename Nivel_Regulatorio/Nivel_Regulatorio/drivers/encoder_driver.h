#ifndef ENCODER_DRIVER_H
#define ENCODER_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

// Pines de los encoders (según tu código de Arduino)
#define ENC_H_CLK_PIN    2    // Horizontal CLK (INT4/PE4)
#define ENC_H_DT_PIN     28   // Horizontal DT (PA6)
#define ENC_V_CLK_PIN    3    // Vertical CLK (INT5/PE5)
#define ENC_V_DT_PIN     29   // Vertical DT (PA7)

// Estructura para cada encoder
typedef struct {
	volatile int32_t position;     // Posición actual del encoder
	volatile uint8_t last_state;   // Último estado para detectar cambios
	bool enabled;                  // Encoder habilitado
} encoder_t;

// Funciones principales
void encoder_init(void);
void encoder_reset_position(bool reset_h, bool reset_v);
void encoder_get_positions(int32_t* h_pos, int32_t* v_pos);

// Funciones para debug/comparación
void encoder_send_comparison_data(void);
void encoder_debug_raw_states(void);  // NUEVA función de debug

#endif