#ifndef BSP_BUZZER_H
#define BSP_BUZZER_H

#include <stdint.h>

void buzzer_init(void);
void buzzer_on(void);
void buzzer_off(void);
void buzzer_beep(uint32_t ms);

#endif
