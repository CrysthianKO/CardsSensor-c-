from gpiozero import DigitalInputDevice, DigitalOutputDevice
from typing import Callable
import time


class ControladorHardware:
    def __init__(
        self,
        pino_led: int = 17,  # Pino físico 11
        pino_vcc_ir: int = 27,  # Pino físico 13
        pino_do_ir: int = 22,  # Pino físico 15
        tempo_debounce: float = 0.01,
    ):
        # 1. Configura LED e Alimentação do Sensor como saídas digitais
        self.led = DigitalOutputDevice(pino_led, initial_value=False)
        self.vcc_ir = DigitalOutputDevice(pino_vcc_ir, initial_value=True)

        # Pequena pausa para estabilizar a tensão no sensor antes de ler
        time.sleep(0.05)

        # 2. Configura a leitura do sensor (DO)
        self.sensor_ir = DigitalInputDevice(
            pino_do_ir, pull_up=True, bounce_time=tempo_debounce
        )

    def ligar_led(self) -> None:
        self.led.on()

    def desligar_led(self) -> None:
        self.led.off()

    def ligar_sensor(self) -> None:
        self.vcc_ir.on()

    def desligar_sensor(self) -> None:
        self.vcc_ir.off()

    @property
    def carta_presente(self) -> bool:
        return not self.sensor_ir.is_active

    def ao_detectar_carta(self, callback: Callable[[], None]) -> None:
        self.sensor_ir.when_deactivated = callback

    def ao_remover_carta(self, callback: Callable[[], None]) -> None:
        self.sensor_ir.when_activated = callback

    def encerrar(self) -> None:
        """Desliga tudo e libera todos os pinos GPIO."""
        self.led.off()
        self.vcc_ir.off()
        self.led.close()
        self.vcc_ir.close()
        self.sensor_ir.close()
