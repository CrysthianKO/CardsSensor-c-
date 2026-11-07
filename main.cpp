#include <chrono>
#include <gpiod.hpp>  // Header oficial do binding C++
#include <iostream>
#include <thread>

int main() {
  try {
    // 1. Instancia o controlador principal do Raspberry Pi (geralmente
    // gpiochip0 no Pi 3 B+)
    gpiod::chip chip("gpiochip0");

    // 2. Isola a linha 17
    gpiod::line linha_led = chip.get_line(17);

    // 3. Prepara a configuração de saída
    gpiod::line_request config;
    config.consumer = "blink_teste_led";
    config.request_type = gpiod::line_request::DIRECTION_OUTPUT;

    // 4. Requisita o acesso exclusivo ao kernel
    linha_led.request(config);

    // 5. Acende o LED (Nível Alto - 3.3V)
    std::cout << "LED Ligado!" << std::endl;
    linha_led.set_value(1);

    // Mantém a execução pausada por 3 segundos enquanto o LED brilha
    std::this_thread::sleep_for(std::chrono::seconds(3));

    // 6. Desliga o LED (Nível Baixo - 0V)
    std::cout << "LED Desligado!" << std::endl;
    linha_led.set_value(0);

    // Ao finalizar, o destrutor libera a linha automaticamente no kernel.
  } catch (const std::exception& e) {
    // Captura e exibe erros (como pino já em uso ou chip inexistente)
    std::cerr << "Falha no hardware: " << e.what() << std::endl;
    return 1;
  }

  return 0;
}
