#include "bsp_pir.h"

#include "hi_errno.h"
#include "hi_gpio.h"
#include "hi_io.h"

#define PIR_PIN       HI_IO_NAME_GPIO_8
#define PIR_GPIO_FUN  HI_IO_FUNC_GPIO_8_GPIO

void pir_init(void)
{
    hi_gpio_init();
    hi_io_set_func(PIR_PIN, PIR_GPIO_FUN);
    hi_io_set_pull(PIR_PIN, HI_IO_PULL_DOWN);
    hi_gpio_set_dir(PIR_PIN, HI_GPIO_DIR_IN);
}

int pir_read(void)
{
    hi_gpio_value value = HI_GPIO_VALUE0;

    if (hi_gpio_get_input_val(PIR_PIN, &value) != HI_ERR_SUCCESS) {
        return 0;
    }
    return value == HI_GPIO_VALUE1 ? 1 : 0;
}
