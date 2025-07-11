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
#define MICROSTEPS          8       // Configuración TB6600
#define STEPS_PER_REV_TOTAL (STEPS_PER_REV_NEMA * MICROSTEPS)

// Relaciones mecánicas
#define MM_PER_REV_BELT     40.0    // mm por revolución en correa
#define MM_PER_REV_SCREW    8.0     // mm por revolución varilla roscada
#define STEPS_PER_MM_H      (STEPS_PER_REV_TOTAL / MM_PER_REV_BELT)
#define STEPS_PER_MM_V      (STEPS_PER_REV_TOTAL / MM_PER_REV_SCREW)

// Velocidades máximas (pasos/segundo)
#define MAX_SPEED_H         8000
#define MAX_SPEED_V         12000
#define MIN_SPEED           500

// Aceleraciones (pasos/segundo²)
#define ACCEL_H             6000
#define ACCEL_V             6000

// ========== PARÁMETROS SERVOS ==========
// Posiciones iniciales por defecto
#define SERVO1_DEFAULT_POS  90      // Posición inicial servo 1
#define SERVO2_DEFAULT_POS  90      // Posición inicial servo 2

// Límites de movimiento (si quieres restringir el rango)
#define SERVO1_MIN_ANGLE    0       // Ángulo mínimo servo 1
#define SERVO1_MAX_ANGLE    180     // Ángulo máximo servo 1
#define SERVO2_MIN_ANGLE    0       // Ángulo mínimo servo 2
#define SERVO2_MAX_ANGLE    180     // Ángulo máximo servo 2

// Delays para secuencias
#define SERVO_DEFAULT_DELAY 500     // Delay por defecto entre movimientos (ms)
#define SERVO_MIN_DELAY     100     // Delay mínimo permitido
#define SERVO_MAX_DELAY     5000    // Delay máximo permitido
#define SERVO_MAX_MOVE_TIME 10000   // 10 segundos máximo

// Configuración de pulsos PWM para servos (en counts con TOP=39999)
// Ajustar estos valores si el servo no alcanza el rango completo
#define SERVO_PWM_MIN       1500    // 0.75ms - ajustar si no llega a 0°
#define SERVO_PWM_CENTER    3000    // 1.5ms - debe ser 90°
#define SERVO_PWM_MAX       4500    // 2.25ms - ajustar si no llega a 180°

// ========== PARÁMETROS GRIPPER ==========
// Motor 28BYJ-48 tiene 2048 pasos/revolución con reducción
#define GRIPPER_STEPS_PER_REV   2048
// Configuración del gripper
#define GRIPPER_STEPS_TO_CLOSE  1700    // Pasos para cerrar completamente
#define GRIPPER_STEP_DELAY      500    // 2ms entre pasos (en microsegundos)
// Velocidades del gripper (en microsegundos)
#define GRIPPER_MIN_DELAY       2000    // 2ms mínimo
#define GRIPPER_MAX_DELAY       10000   // 10ms máximo

#endif // SYSTEM_CONFIG_H