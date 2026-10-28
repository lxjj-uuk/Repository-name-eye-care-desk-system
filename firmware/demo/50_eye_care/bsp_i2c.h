#ifndef BSP_I2C_H
#define BSP_I2C_H

#include <stdint.h>

int bsp_i2c_init(void);
int bsp_i2c_write(uint8_t addr7, const uint8_t *data, uint32_t len);
int bsp_i2c_read(uint8_t addr7, uint8_t *data, uint32_t len);
void bsp_i2c_scan(void);

#endif
