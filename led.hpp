#pragma once
#include <gpiod.hpp>

class ControladorLed {
private:
    int pino_atual;
    
    gpiod::line_request controle;

    static gpiod::line_request iniciar_hardware(int pino);

public:
    ControladorLed(int pino);
    
    void ligar();
    void desligar();
};
