#ifndef COMMAND_PROTOCOL_H
#define COMMAND_PROTOCOL_H

// ========== PROTOCOLO DE COMUNICACIÓN ==========
// Formato de comandos desde Raspberry:
// <CMD:PARAM1,PARAM2,...>

// Comandos de entrada
#define CMD_MOVE_XY         'M'     // M:100.5,50.2 (x,y en mm)

// Respuestas al Raspberry
#define RSP_OK              "OK"

// Buffer para comunicacion
#define UART_BUFFER_SIZE    128

#endif