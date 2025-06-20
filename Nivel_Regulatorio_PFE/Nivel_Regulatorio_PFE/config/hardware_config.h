#ifndef HARDWARE_CONFIG_H
#define HARDWARE_CONFIG_H

#include <avr/io.h>

// ========== MOTORES PAP TB6600 ==========
// Motor Horizontal 1
#define STEP_H1_DDR     DDRB
#define STEP_H1_PORT    PORTB
#define STEP_H1_PIN     PB5     // Pin 11 (OC1A)

#define DIR_H1_DDR      DDRA
#define DIR_H1_PORT     PORTA
#define DIR_H1_PIN      PA0     // Pin 22

#define ENABLE_H1_DDR   DDRA
#define ENABLE_H1_PORT  PORTA
#define ENABLE_H1_PIN   PA1     // Pin 23

// Motor Horizontal 2
#define STEP_H2_DDR     DDRB
#define STEP_H2_PORT    PORTB
#define STEP_H2_PIN     PB6     // Pin 12 (OC1B)

#define DIR_H2_DDR      DDRA
#define DIR_H2_PORT     PORTA
#define DIR_H2_PIN      PA2     // Pin 24

#define ENABLE_H2_DDR   DDRA
#define ENABLE_H2_PORT  PORTA
#define ENABLE_H2_PIN   PA3     // Pin 25

// Motor Vertical
#define STEP_V_DDR      DDRE
#define STEP_V_PORT     PORTE
#define STEP_V_PIN      PE3     // Pin 5 (OC3A)

#define DIR_V_DDR       DDRA
#define DIR_V_PORT      PORTA
#define DIR_V_PIN       PA4     // Pin 26

#define ENABLE_V_DDR    DDRA
#define ENABLE_V_PORT   PORTA
#define ENABLE_V_PIN    PA5     // Pin 27

// ========== ENCODERS KY-040 ==========
#define ENCODER_H_CLK   PD0     // Pin 2 (INT0)
#define ENCODER_H_DT    PA6     // Pin 28

#define ENCODER_V_CLK   PD1     // Pin 3 (INT1)
#define ENCODER_V_DT    PA7     // Pin 29

// ========== FINES DE CARRERA ==========
#define FC_H_LEFT_DDR   DDRC
#define FC_H_LEFT_PORT  PORTC
#define FC_H_LEFT_PIN   PINC
#define FC_H_LEFT       PC7     // Pin 30

#define FC_H_RIGHT_DDR  DDRC
#define FC_H_RIGHT_PORT PORTC
#define FC_H_RIGHT_PIN  PINC
#define FC_H_RIGHT      PC6     // Pin 31

#define FC_V_UP_DDR     DDRC
#define FC_V_UP_PORT    PORTC
#define FC_V_UP_PIN     PINC
#define FC_V_UP         PC5     // Pin 32

#define FC_V_DOWN_DDR   DDRC
#define FC_V_DOWN_PORT  PORTC
#define FC_V_DOWN_PIN   PINC
#define FC_V_DOWN       PC4     // Pin 33

// ========== SERVOS ==========
#define SERVO1_DDR      DDRB
#define SERVO1_PORT     PORTB
#define SERVO1_PIN      PB4     // Pin 10 (OC2A)

#define SERVO2_DDR      DDRH
#define SERVO2_PORT     PORTH
#define SERVO2_PIN      PH6     // Pin 9 (OC2B)

// ========== MOTOR 28BYJ-48 ==========
#define MOTOR_SMALL_DDR     DDRC
#define MOTOR_SMALL_PORT    PORTC
#define MOTOR_SMALL_IN1     PC3  // Pin 34
#define MOTOR_SMALL_IN2     PC2  // Pin 35
#define MOTOR_SMALL_IN3     PC1  // Pin 36
#define MOTOR_SMALL_IN4     PC0  // Pin 37

#endif