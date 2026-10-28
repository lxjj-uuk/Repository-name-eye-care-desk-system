#ifndef BSP_DHT20_H
#define BSP_DHT20_H

#include <stdint.h>

int dht20_init(void);
int dht20_read(float *temp, float *humi);

#endif
