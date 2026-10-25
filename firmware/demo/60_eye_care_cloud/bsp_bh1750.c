#include "bsp_bh1750.h"

#include <stdio.h>
#include <unistd.h>

#include "bsp_i2c.h"

#define BH1750_ADDR_0X23  0x23
#define BH1750_ADDR_0X5C  0x5C
#define BH1750_POWER_ON   0x01
#define BH1750_CONT_H     0x10

static uint8_t g_bh1750_addr = BH1750_ADDR_0X23;
static int g_bh1750_ready = 0;

static int bh1750_try_addr(uint8_t addr)
{
    uint8_t cmd = BH1750_POWER_ON;

    if (bsp_i2c_write(addr, &cmd, 1) != 0) {
        return -1;
    }
    usleep(10 * 1000);
    cmd = BH1750_CONT_H;
    if (bsp_i2c_write(addr, &cmd, 1) != 0) {
        return -1;
    }
    usleep(120 * 1000);
    return 0;
}

int bh1750_init(void)
{
    if (bh1750_try_addr(BH1750_ADDR_0X23) == 0) {
        g_bh1750_addr = BH1750_ADDR_0X23;
        g_bh1750_ready = 1;
        printf("[bh1750] found at 0x23\n");
        return 0;
    }
    if (bh1750_try_addr(BH1750_ADDR_0X5C) == 0) {
        g_bh1750_addr = BH1750_ADDR_0X5C;
        g_bh1750_ready = 1;
        printf("[bh1750] found at 0x5C\n");
        return 0;
    }

    g_bh1750_ready = 0;
    printf("[bh1750] not found\n");
    return -1;
}

int bh1750_read_lux(float *lux)
{
    uint8_t buf[2] = { 0 };
    uint16_t raw;

    if (lux == NULL) {
        return -1;
    }
    if (!g_bh1750_ready && bh1750_init() != 0) {
        return -1;
    }
    if (bsp_i2c_read(g_bh1750_addr, buf, sizeof(buf)) != 0) {
        g_bh1750_ready = 0;
        return -1;
    }

    raw = ((uint16_t)buf[0] << 8) | buf[1];
    *lux = raw / 1.2f;
    return 0;
}
