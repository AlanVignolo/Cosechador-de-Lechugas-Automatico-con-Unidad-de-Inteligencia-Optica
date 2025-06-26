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

#endif