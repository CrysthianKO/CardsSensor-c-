#include <iostream>
#include <chrono>
#include <thread>
#include <gpiod.hpp> // Header v2

int main() {
    try {
        // 1. O "Formulário de Uso" (Identifica seu programa no sistema)
        gpiod::request_config req_cfg;
        req_cfg.set_consumer("scanner_cartas_led");

        // 2. O "Manual de Instruções" do pino
        gpiod::line_settings settings;
        settings.set_direction(gpiod::line::direction::OUTPUT);
        
        // 3. Associa a regra de saída ao GPIO 17
        gpiod::line_config line_cfg;
        line_cfg.add_line_settings(17, settings);

        // 4. Conecta-se ao Síndico (O controlador de pinos)
        // No Pi 3, os pinos da placa ficam geralmente em "gpiochip0".
        gpiod::chip chip("/dev/gpiochip0"); 

        // 5. Entrega os formulários e recebe o controle do pino validado
        auto controle_linhas = chip.request_lines(req_cfg, line_cfg);

        // 6. Chaveia fisicamente a energia (ACTIVE = 3.3V)
        std::cout << "LED Ligado!" << std::endl;
        controle_linhas.set_value(17, gpiod::line::value::ACTIVE);

        std::this_thread::sleep_for(std::chrono::seconds(3));

        // 7. Corta a energia (INACTIVE = 0V)
        std::cout << "LED Desligado!" << std::endl;
        controle_linhas.set_value(17, gpiod::line::value::INACTIVE);

        // O destrutor de controle_linhas liberará o GPIO 17 automaticamente aqui.
    } 
    catch (const std::exception& e) {
        std::cerr << "Falha no hardware: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
