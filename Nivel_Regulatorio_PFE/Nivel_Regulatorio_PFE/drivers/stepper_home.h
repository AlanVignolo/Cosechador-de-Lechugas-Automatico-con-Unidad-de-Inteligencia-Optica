#ifndef STEPPER_HOME_H
#define STEPPER_HOME_H

#include <stdbool.h>

void stepper_home_init(void);
void stepper_home_start(void);
void stepper_home_process(void);
bool stepper_is_homing(void);

#endif