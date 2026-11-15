from gpiozero import DigitalInputDevice
from typing import Callable, Optional


class SensorInfravermelho:
    def __init__(self, pino_gpio: int = 17, tempo_debounce: float = 0.05):
        """
        Inicializa o sensor IR na saída digital (DO).
        :param pino_gpio: Número do pino BCM (ex: 17 para o pino físico 11).
        :param tempo_debounce: Tempo em segundos para evitar leituras falsas/ruído.
        """
        # pull_up=True porque a maioria dos módulos IR puxa o DO para LOW (0V) ao detectar
        self._sensor = DigitalInputDevice(
            pino_gpio, pull_up=True, bounce_time=tempo_debounce
        )

    @property
    def objeto_detectado(self) -> bool:
        """Retorna True enquanto houver um objeto na frente do sensor."""
        # A lógica é invertida: sinal ativo (LOW) significa objeto presente
        return not self._sensor.is_active

    def ao_detectar(self, callback: Callable[[], None]) -> None:
        """Registra uma função para rodar automaticamente no instante da detecção."""
        self._sensor.when_deactivated = callback

    def ao_afastar(self, callback: Callable[[], None]) -> None:
        """Registra uma função para rodar quando o objeto sair da frente."""
        self._sensor.when_activated = callback

    def fechar(self) -> None:
        """Libera o pino GPIO ao encerrar o jogo."""
        self._sensor.close()
