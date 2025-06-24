#ifndef SYSTEM_CONFIG_H
#define SYSTEM_CONFIG_H

// ========== FRECUENCIAS Y TIMING ==========
#ifndef F_CPU
#define F_CPU               16000000UL
#endif
#define UART_BAUD_RATE      115200

// ========== PARÁMETROS MOTORES ==========
// Pasos por revolución de los motores
#define STEPS_PER_REV_NEMA  200     // Motor NEMA típico
#define MICROSTEPS          8      // Configuración TB6600
#define STEPS_PER_REV_TOTAL (STEPS_PER_REV_NEMA * MICROSTEPS)

// Motor gripper
#define STEPS_PER_REV_28BYJ 2048    // Pasos completos del 28BYJ-48

// Relaciones mecánicas
#define MM_PER_REV_BELT     40.0    // mm por revolución en correa
#define MM_PER_REV_SCREW    8.0     // mm por revolución varilla roscada
#define STEPS_PER_MM_H      (STEPS_PER_REV_TOTAL / MM_PER_REV_BELT)
#define STEPS_PER_MM_V      (STEPS_PER_REV_TOTAL / MM_PER_REV_SCREW)

// Velocidades máximas (pasos/segundo)
#define MAX_SPEED_H         10000
#define MAX_SPEED_V         16000
#define MIN_SPEED           500

// Aceleraciones (pasos/segundo²)
#define ACCEL_H             4000
#define ACCEL_V             4800

// ========== CONFIGURACIÓN SERVOS ==========
#define SERVO_MIN_US        1000    // Microsegundos
#define SERVO_MAX_US        2000
#define SERVO_CENTER_US     1500

// ========== CONFIGURACIÓN ENCODERS ==========
#define ENCODER_PPR         600     // Pulsos por revolución
#define ENCODER_MM_PER_PULSE_H (MM_PER_REV_BELT / ENCODER_PPR)
#define ENCODER_MM_PER_PULSE_V (MM_PER_REV_SCREW / ENCODER_PPR)

// ========== POSICIONES BRAZO PREDEFINIDAS ==========
// Servo 1 (base), Servo 2 (codo), Gripper (0=cerrado, 100=abierto)
#define ARM_POS_RETRACTED_S1    90
#define ARM_POS_RETRACTED_S2    45
#define ARM_POS_RETRACTED_GRIP  0

#define ARM_POS_EXTENDED_S1     90
#define ARM_POS_EXTENDED_S2     135
#define ARM_POS_EXTENDED_GRIP   0

#define ARM_POS_COLLECTING_S1   90
#define ARM_POS_COLLECTING_S2   90
#define ARM_POS_COLLECTING_GRIP 100

#define ARM_POS_DROPPING_S1     90
#define ARM_POS_DROPPING_S2     120
#define ARM_POS_DROPPING_GRIP   0

#define ARM_POS_HANGING_S1      90
#define ARM_POS_HANGING_S2      180
#define ARM_POS_HANGING_GRIP    50

// ========== TIMEOUTS Y DELAYS ==========
#define DEBOUNCE_TIME_MS        20      // Anti-rebote fines de carrera

#endif