#include <iostream>
#include <chrono>
#include <thread>
#include <gpiod.hpp> // Header v2

int main() {
    try {
        // 1. Conecta-se ao Síndico (O controlador de pinos principal)
        gpiod::chip chip("/dev/gpiochip0"); 

        // 2. Cria as configurações para o pino (Direção: Saída)
        gpiod::line_settings settings;
        settings.set_direction(gpiod::line::direction::OUTPUT);
        
        // 3. Usa o construtor (Builder) para preparar a requisição do GPIO 17
        auto controle_linhas = chip.prepare_request()
            .set_consumer("scanner_cartas_led")
            .add_line_settings(17, settings)
            .do_request(); // Efetiva o bloqueio no Kernel

        // 4. Chaveia fisicamente a energia (ACTIVE = 3.3V)
        std::cout << "LED Ligado!" << std::endl;
        controle_linhas.set_value(17, gpiod::line::value::ACTIVE);

        std::this_thread::sleep_for(std::chrono::seconds(3));

        // 5. Corta a energia (INACTIVE = 0V)
        std::cout << "LED Desligado!" << std::endl;
        controle_linhas.set_value(17, gpiod::line::value::INACTIVE);

    } 
    catch (const std::exception& e) {
        std::cerr << "Falha no hardware: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
