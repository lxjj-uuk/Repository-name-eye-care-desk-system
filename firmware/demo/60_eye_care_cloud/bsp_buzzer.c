#include "bsp_buzzer.h"

#include <unistd.h>

#include "hi_gpio.h"
#include "hi_io.h"

#define BUZZER_PIN         HI_IO_NAME_GPIO_14
#define BUZZER_GPIO_FUN    HI_IO_FUNC_GPIO_14_GPIO

void buzzer_init(void)
{
    hi_gpio_init();
    hi_io_set_func(BUZZER_PIN, BUZZER_GPIO_FUN);
    hi_io_set_pull(BUZZER_PIN, HI_IO_PULL_UP);
    hi_gpio_set_dir(BUZZER_PIN, HI_GPIO_DIR_OUT);
    buzzer_off();
}

void buzzer_on(void)
{
    /* The external buzzer module is active-low. */
    hi_gpio_set_ouput_val(BUZZER_PIN, HI_GPIO_VALUE0);
}

void buzzer_off(void)
{
    hi_gpio_set_ouput_val(BUZZER_PIN, HI_GPIO_VALUE1);
}

void buzzer_beep(uint32_t ms)
{
    if (ms == 0) {
        return;
    }

    /* MH-FMD is active-low: hold the input low for the requested duration. */
    buzzer_on();
    usleep(ms * 1000U);
    buzzer_off();
}
