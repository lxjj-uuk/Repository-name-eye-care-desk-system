#include "bsp_dht20.h"

#include <stdio.h>
#include <unistd.h>

#include "bsp_i2c.h"

#define DHT20_ADDR          0x38
#define DHT20_CMD_STATUS    0x71
#define DHT20_CMD_CAL       0xBE
#define DHT20_CMD_TRIGGER   0xAC

static int dht20_write(const uint8_t *buf, uint32_t len)
{
    return bsp_i2c_write(DHT20_ADDR, buf, len);
}

int dht20_init(void)
{
    uint8_t status_cmd = DHT20_CMD_STATUS;
    uint8_t status = 0;

    usleep(20 * 1000);
    if (dht20_write(&status_cmd, 1) != 0) {
        printf("[dht20] status write failed\n");
        return -1;
    }
    if (bsp_i2c_read(DHT20_ADDR, &status, 1) != 0) {
        printf("[dht20] status read failed\n");
        return -1;
    }

    if ((status & 0x80) != 0 || (status & 0x08) == 0) {
        uint8_t cal_cmd[3] = { DHT20_CMD_CAL, 0x08, 0x00 };
        if (dht20_write(cal_cmd, sizeof(cal_cmd)) != 0) {
            printf("[dht20] calibrate failed\n");
            return -1;
        }
        usleep(40 * 1000);
    }

    printf("[dht20] init ok, status=0x%02X\n", status);
    return 0;
}

int dht20_read(float *temp, float *humi)
{
    uint8_t trigger[3] = { DHT20_CMD_TRIGGER, 0x33, 0x00 };
    uint8_t buf[6] = { 0 };
    uint32_t humi_raw;
    uint32_t temp_raw;

    if (temp == NULL || humi == NULL) {
        return -1;
    }
    if (dht20_write(trigger, sizeof(trigger)) != 0) {
        return -1;
    }
    usleep(80 * 1000);
    if (bsp_i2c_read(DHT20_ADDR, buf, sizeof(buf)) != 0) {
        return -1;
    }
    if ((buf[0] & 0x80) != 0) {
        return -1;
    }

    humi_raw = ((uint32_t)buf[1] << 12) | ((uint32_t)buf[2] << 4) | (buf[3] >> 4);
    temp_raw = (((uint32_t)buf[3] & 0x0F) << 16) | ((uint32_t)buf[4] << 8) | buf[5];

    *humi = humi_raw * 100.0f / 1048576.0f;
    *temp = temp_raw * 200.0f / 1048576.0f - 50.0f;
    return 0;
}
