#ifndef COMMAND_PROTOCOL_H
#define COMMAND_PROTOCOL_H

// ========== PROTOCOLO DE COMUNICACIÓN ==========
// Formato de comandos desde Raspberry:
// <CMD:PARAM1,PARAM2,...>\n

// Comandos de entrada
#define CMD_MOVE_XY         'M'     // M:100.5,50.2 (x,y en mm)
#define CMD_HOME            'H'     // H (sin parámetros)
#define CMD_ARM_POSITION    'A'     // A:RETRACTED
#define CMD_ARM_TRAJECTORY  'T'     // T:90,45,0;95,50,0;... (servo1,servo2,gripper)
#define CMD_STOP            'S'     // S (parada de emergencia)
#define CMD_STATUS          '?'     // ? (solicitar estado)
#define CMD_GRIPPER         'G'     // G:OPEN o G:CLOSE
#define CMD_SET_SPEED       'V'     // V:50 (% de velocidad máxima)

// Respuestas al Raspberry
#define RSP_OK              "OK"
#define RSP_ERROR           "ERR"
#define RSP_MOVING          "MOV"
#define RSP_ARRIVED         "ARR"
#define RSP_LIMIT_HIT       "LIM"
#define RSP_HOME_COMPLETE   "HOM"
#define RSP_ARM_POSITION    "ARM"

// Posiciones de brazo predefinidas
#define ARM_POS_STR_RETRACTED   "RETRACTED"
#define ARM_POS_STR_EXTENDED    "EXTENDED"
#define ARM_POS_STR_COLLECTING  "COLLECTING"
#define ARM_POS_STR_DROPPING    "DROPPING"
#define ARM_POS_STR_HANGING     "HANGING"

// Buffer para comunicacion
#define UART_BUFFER_SIZE    128
#define MAX_TRAJECTORY_POINTS 20

#endif