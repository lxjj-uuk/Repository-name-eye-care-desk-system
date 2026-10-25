#ifndef BSP_BH1750_H
#define BSP_BH1750_H

#include <stdint.h>

int bh1750_init(void);
int bh1750_read_lux(float *lux);

#endif
