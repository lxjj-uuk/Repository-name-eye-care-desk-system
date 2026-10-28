#include "bsp_i2c.h"

#include <stdio.h>

#include "hi_errno.h"
#include "hi_i2c.h"
#include "hi_io.h"

#define BSP_I2C_IDX   HI_I2C_IDX_0
#define BSP_I2C_BAUD  100000

int bsp_i2c_init(void)
{
    hi_u32 ret;

    /* Puzhong Hi3861 IIC OLED header: GPIO9 = SCL, GPIO10 = SDA. */
    hi_io_set_pull(HI_IO_NAME_GPIO_9, HI_IO_PULL_UP);
    hi_io_set_func(HI_IO_NAME_GPIO_9, HI_IO_FUNC_GPIO_9_I2C0_SCL);
    hi_io_set_pull(HI_IO_NAME_GPIO_10, HI_IO_PULL_UP);
    hi_io_set_func(HI_IO_NAME_GPIO_10, HI_IO_FUNC_GPIO_10_I2C0_SDA);

    ret = hi_i2c_init(BSP_I2C_IDX, BSP_I2C_BAUD);
    if (ret != HI_ERR_SUCCESS) {
        printf("[i2c] init failed: 0x%x\n", ret);
        return -1;
    }
    return 0;
}

int bsp_i2c_write(uint8_t addr7, const uint8_t *data, uint32_t len)
{
    hi_i2c_data i2c_data = { 0 };

    if (data == NULL || len == 0) {
        return -1;
    }
    i2c_data.send_buf = (uint8_t *)data;
    i2c_data.send_len = len;
    if (hi_i2c_write(BSP_I2C_IDX, (hi_u16)(addr7 << 1), &i2c_data) != HI_ERR_SUCCESS) {
        return -1;
    }
    return 0;
}

int bsp_i2c_read(uint8_t addr7, uint8_t *data, uint32_t len)
{
    hi_i2c_data i2c_data = { 0 };

    if (data == NULL || len == 0) {
        return -1;
    }
    i2c_data.receive_buf = data;
    i2c_data.receive_len = len;
    if (hi_i2c_read(BSP_I2C_IDX, (hi_u16)((addr7 << 1) | 0x01), &i2c_data) != HI_ERR_SUCCESS) {
        return -1;
    }
    return 0;
}

void bsp_i2c_scan(void)
{
    uint8_t addr;
    uint8_t dummy = 0x00;
    int found = 0;

    printf("[i2c] scan 0x08..0x77:");
    for (addr = 0x08; addr <= 0x77; addr++) {
        if (bsp_i2c_write(addr, &dummy, 1) == 0) {
            printf(" 0x%02X", addr);
            found++;
        }
    }
    if (found == 0) {
        printf(" none");
    }
    printf("\n");
}
