#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "cmsis_os2.h"
#include "hi_gpio.h"
#include "hi_io.h"
#include "hi_uart.h"
#include "ohos_init.h"

#include "bsp_bh1750.h"
#include "bsp_buzzer.h"
#include "bsp_dht20.h"
#include "bsp_i2c.h"
#include "bsp_pir.h"

#define TASK_STACK_SIZE        8192
#define SAMPLE_INTERVAL_S      2
#define LUX_DARK_THRESHOLD     150.0f

static int g_sit_cont_seconds = 0;
static int g_sit_total_seconds = 0;
static int g_seconds_since_motion = 0;

static void bridge_uart_init(void)
{
    hi_uart_attribute uart_param = {
        .baud_rate = 115200,
        .data_bits = 8,
        .stop_bits = 1,
        .parity = 0,
    };
    hi_uart_extra_attr extra = {0};

    hi_io_set_func(HI_IO_NAME_GPIO_11, HI_IO_FUNC_GPIO_11_UART2_TXD);
    hi_io_set_func(HI_IO_NAME_GPIO_12, HI_IO_FUNC_GPIO_12_UART2_RXD);
    extra.tx_block = HI_UART_BLOCK_STATE_NONE_BLOCK;
    extra.rx_block = HI_UART_BLOCK_STATE_NONE_BLOCK;
    extra.tx_buf_size = 64;
    extra.rx_buf_size = 128;
    if (hi_uart_init(HI_UART_IDX_2, &uart_param, &extra) != HI_ERR_SUCCESS) {
        printf("[eye-care] UART2 init failed\n");
    }
}

static void handle_bridge_commands(void)
{
    char buffer[64] = {0};
    hi_s32 length = hi_uart_read(HI_UART_IDX_2, (hi_u8 *)buffer,
                                 sizeof(buffer) - 1);

    if (length <= 0) {
        return;
    }
    buffer[length] = '\0';
    if (strstr(buffer, "BUZZ,") == NULL) {
        return;
    }
    if (strstr(buffer, "double") != NULL) {
        buzzer_beep(180);
        usleep(180 * 1000);
        buzzer_beep(180);
    } else if (strstr(buffer, "long") != NULL) {
        buzzer_beep(1000);
    } else {
        buzzer_beep(200);
    }
    printf("[eye-care] UART command handled\n");
}

static void update_health(int occupied, float lux, int *sit_cont_min,
                          int *sit_total_min, int *last_motion_min,
                          float *risk, const char **risk_level)
{
    if (occupied) {
        g_sit_cont_seconds += SAMPLE_INTERVAL_S;
        g_sit_total_seconds += SAMPLE_INTERVAL_S;
        g_seconds_since_motion = 0;
    } else {
        g_seconds_since_motion += SAMPLE_INTERVAL_S;
        if (g_seconds_since_motion >= 60) {
            g_sit_cont_seconds = 0;
        }
    }

    *sit_cont_min = g_sit_cont_seconds / 60;
    *sit_total_min = g_sit_total_seconds / 60;
    *last_motion_min = g_seconds_since_motion / 60;

    *risk = 0.1f;
    if (lux < LUX_DARK_THRESHOLD) {
        *risk += 0.3f;
    } else if (lux > 1000.0f) {
        *risk += 0.15f;
    }
    *risk += (float)*sit_cont_min / 150.0f;
    if (*risk > 0.99f) {
        *risk = 0.99f;
    }

    if ((*sit_cont_min >= 60) || (*risk >= 0.7f)) {
        *risk_level = "high";
    } else if ((*sit_cont_min >= 45) || (*risk >= 0.4f)) {
        *risk_level = "medium";
    } else {
        *risk_level = "low";
    }
}

static void eye_care_task(void)
{
    int bh1750_ok;
    int dht20_ok;

    printf("\n===== eye care sensor test =====\n");
    bsp_i2c_init();
    bsp_i2c_scan();

    bh1750_ok = bh1750_init();
    dht20_ok = dht20_init();
    pir_init();
    buzzer_init();
    bridge_uart_init();
    printf("[eye-care] buzzer self-test\n");
    buzzer_beep(500);

    printf("[eye-care] init: bh1750=%d dht20=%d\n", bh1750_ok, dht20_ok);
    printf("[eye-care] PIR warm-up: keep the sensor still for 30-60 seconds\n");
    sleep(5);

    while (1) {
        float lux = 0.0f;
        float temp = 0.0f;
        float humi = 0.0f;
        int lux_ret;
        int dht_ret;
        int occupied;
        int sit_cont_min;
        int sit_total_min;
        int last_motion_min;
        float risk;
        const char *risk_level;

        handle_bridge_commands();
        lux_ret = bh1750_read_lux(&lux);
        dht_ret = dht20_read(&temp, &humi);
        occupied = pir_read();
        update_health(occupied, lux, &sit_cont_min, &sit_total_min,
                      &last_motion_min, &risk, &risk_level);

        printf("[eye-care] lux=%7.1f(%d) temp=%5.1f rh=%5.1f(%d) occupied=%d "
               "sit=%d total=%d last_motion=%d risk=%.2f risk_level=%s\n",
               lux, lux_ret, temp, humi, dht_ret, occupied, sit_cont_min,
               sit_total_min, last_motion_min, risk, risk_level);

        if (lux_ret == 0 && lux < LUX_DARK_THRESHOLD) {
            buzzer_beep(120);
        }
        sleep(SAMPLE_INTERVAL_S);
    }
}

static void eye_care_demo(void)
{
    osThreadAttr_t attr = {0};

    attr.name = "EyeCareTask";
    attr.stack_size = TASK_STACK_SIZE;
    attr.priority = osPriorityNormal;
    if (osThreadNew((osThreadFunc_t)eye_care_task, NULL, &attr) == NULL) {
        printf("[eye-care] create task failed\n");
    }
}

SYS_RUN(eye_care_demo);
