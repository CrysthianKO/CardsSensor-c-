#include "led.hpp"

gpiod::line_request ControladorLed::iniciar_hardware(int pino) {
    gpiod::chip chip("/dev/gpiochip0");
    gpiod::line_settings settings;
    settings.set_direction(gpiod::line::direction::OUTPUT);
    
    return chip.prepare_request()
        .set_consumer("operador_led")
        .add_line_settings(pino, settings)
        .do_request();
}

ControladorLed::ControladorLed(int pino) : pino_atual(pino), controle(iniciar_hardware(pino)) {
}

void ControladorLed::ligar() {
    controle.set_value(pino_atual, gpiod::line::value::ACTIVE);
}

void ControladorLed::desligar() {
    controle.set_value(pino_atual, gpiod::line::value::INACTIVE);
}
