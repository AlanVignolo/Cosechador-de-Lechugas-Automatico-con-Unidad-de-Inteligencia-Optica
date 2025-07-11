#ifndef SYSTEM_CONFIG_H
#define SYSTEM_CONFIG_H

// ========== FRECUENCIAS Y TIMING ==========
#ifndef F_CPU
#define F_CPU               16000000UL
#endif
#define UART_BAUD_RATE      115200

// ========== PAR�METROS MOTORES ==========
// Pasos por revoluci�n de los motores
#define STEPS_PER_REV_NEMA  200     // Motor NEMA t�pico
#define MICROSTEPS          8       // Configuraci�n TB6600
#define STEPS_PER_REV_TOTAL (STEPS_PER_REV_NEMA * MICROSTEPS)

// Relaciones mec�nicas
#define MM_PER_REV_BELT     40.0    // mm por revoluci�n en correa
#define MM_PER_REV_SCREW    8.0     // mm por revoluci�n varilla roscada
#define STEPS_PER_MM_H      (STEPS_PER_REV_TOTAL / MM_PER_REV_BELT)
#define STEPS_PER_MM_V      (STEPS_PER_REV_TOTAL / MM_PER_REV_SCREW)

// Velocidades m�ximas (pasos/segundo)
#define MAX_SPEED_H         8000
#define MAX_SPEED_V         12000
#define MIN_SPEED           500

// Aceleraciones (pasos/segundo�)
#define ACCEL_H             6000
#define ACCEL_V             6000

// ========== PAR�METROS SERVOS ==========
// Posiciones iniciales por defecto
#define SERVO1_DEFAULT_POS  90      // Posici�n inicial servo 1
#define SERVO2_DEFAULT_POS  90      // Posici�n inicial servo 2

// L�mites de movimiento (si quieres restringir el rango)
#define SERVO1_MIN_ANGLE    0       // �ngulo m�nimo servo 1
#define SERVO1_MAX_ANGLE    180     // �ngulo m�ximo servo 1
#define SERVO2_MIN_ANGLE    0       // �ngulo m�nimo servo 2
#define SERVO2_MAX_ANGLE    180     // �ngulo m�ximo servo 2

// Delays para secuencias
#define SERVO_DEFAULT_DELAY 500     // Delay por defecto entre movimientos (ms)
#define SERVO_MIN_DELAY     100     // Delay m�nimo permitido
#define SERVO_MAX_DELAY     5000    // Delay m�ximo permitido
#define SERVO_MAX_MOVE_TIME 10000   // 10 segundos m�ximo

// Configuraci�n de pulsos PWM para servos (en counts con TOP=39999)
// Ajustar estos valores si el servo no alcanza el rango completo
#define SERVO_PWM_MIN       1500    // 0.75ms - ajustar si no llega a 0�
#define SERVO_PWM_CENTER    3000    // 1.5ms - debe ser 90�
#define SERVO_PWM_MAX       4500    // 2.25ms - ajustar si no llega a 180�

// ========== PAR�METROS GRIPPER ==========
// Motor 28BYJ-48 tiene 2048 pasos/revoluci�n con reducci�n
#define GRIPPER_STEPS_PER_REV   2048
// Configuraci�n del gripper
#define GRIPPER_STEPS_TO_CLOSE  1700    // Pasos para cerrar completamente
#define GRIPPER_STEP_DELAY      500    // 2ms entre pasos (en microsegundos)
// Velocidades del gripper (en microsegundos)
#define GRIPPER_MIN_DELAY       2000    // 2ms m�nimo
#define GRIPPER_MAX_DELAY       10000   // 10ms m�ximo

#endif // SYSTEM_CONFIG_H