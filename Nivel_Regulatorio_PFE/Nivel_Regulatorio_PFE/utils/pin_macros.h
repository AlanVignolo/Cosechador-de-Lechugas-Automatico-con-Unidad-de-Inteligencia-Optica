#ifndef PIN_MACROS_H
#define PIN_MACROS_H

// Macros para manejo de pines
#define SET_BIT(port, bit)      ((port) |= (1 << (bit)))
#define CLEAR_BIT(port, bit)    ((port) &= ~(1 << (bit)))
#define TOGGLE_BIT(port, bit)   ((port) ^= (1 << (bit)))
#define READ_BIT(pin, bit)      (((pin) >> (bit)) & 0x01)

// Configuración de pines
#define SET_OUTPUT(ddr, bit)    SET_BIT(ddr, bit)
#define SET_INPUT(ddr, bit)     CLEAR_BIT(ddr, bit)
#define ENABLE_PULLUP(port, bit) SET_BIT(port, bit)

// Estados
#define HIGH    1
#define LOW     0

#endif