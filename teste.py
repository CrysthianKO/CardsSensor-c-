from gpiozero import DigitalInputDevice, DigitalOutputDevice
import time

# Mapeamento BCM dos pinos físicos 11, 13 e 15
led = DigitalOutputDevice(17)  # Pino 11 -> LED branco
vcc_ir = DigitalOutputDevice(27)  # Pino 13 -> Alimentação (VCC) do sensor IR
sensor_ir = DigitalInputDevice(22, pull_up=True)  # Pino 15 -> Saída (DO) do sensor IR

# Liga o LED e energiza o sensor infravermelho
led.on()
vcc_ir.on()
time.sleep(0.1)  # Pequena pausa para estabilizar o sensor

print("LED e Sensor IR ligados. Aproxime a carta (Ctrl+C para sair)...")

try:
    while True:
        # O sensor IR envia LOW (is_active == False) quando detecta algo
        if not sensor_ir.is_active:
            print("Carta detectada!")
        else:
            print("Livre")

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nEncerrando...")

finally:
    # Desliga tudo e libera os pinos ao sair
    led.off()
    vcc_ir.off()
    led.close()
    vcc_ir.close()
    sensor_ir.close()
