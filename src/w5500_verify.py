#!/usr/bin/env python3
# 4x W5500 VERSIONR testi (0x04 beklenir)
# spi0-0cs modu + gpiod v2 manuel CS
# Pertinaks/baglanti degisiminden sonra dort chip'i hizlica dogrular.

import spidev, gpiod, time
from gpiod.line import Direction, Value

# CS haritasi: isim -> BCM GPIO (fiziksel pin)
CS_MAP = {
    "A": 8,    # pin 24
    "B": 7,    # pin 26
    "C": 25,   # pin 22
    "D": 24,   # pin 18
}
CHIP   = "/dev/gpiochip0"
SPI_HZ = 16_000_000
EXPECT = 0x04

spi = spidev.SpiDev(); spi.open(0, 0)
spi.max_speed_hz = SPI_HZ; spi.mode = 0; spi.no_cs = True

lines = gpiod.request_lines(
    CHIP, consumer="w5500-4",
    config={tuple(CS_MAP.values()): gpiod.LineSettings(
        direction=Direction.OUTPUT, output_value=Value.ACTIVE)},
)

def read_versionr(cs):
    lines.set_value(cs, Value.INACTIVE)
    r = spi.xfer2([0x00, 0x39, 0x00, 0x00])   # VERSIONR @ 0x0039, common blok
    lines.set_value(cs, Value.ACTIVE)
    return r[3]

def read_phy(cs):
    lines.set_value(cs, Value.INACTIVE)
    r = spi.xfer2([0x00, 0x2E, 0x00, 0x00])   # PHYCFGR @ 0x002E
    lines.set_value(cs, Value.ACTIVE)
    return r[3]

print("4x W5500 dogrulama (VERSIONR=0x04 beklenir)")
print("="*52)
all_ok = True
for name, gpio in CS_MAP.items():
    v = read_versionr(gpio)
    ok = (v == EXPECT)
    all_ok = all_ok and ok
    phy = read_phy(gpio)
    link = "LINK UP" if (phy & 0x01) else "link yok"
    spd  = "100M" if (phy & 0x02) else "10M"
    print("W5500 %s (GPIO%-2d/pin%2s): VER=%s  %s   [PHY: %s %s]" % (
        name, gpio,
        {8:"24",7:"26",25:"22",24:"18"}[gpio],
        hex(v), "OK" if ok else "!! HATA",
        link, spd if (phy & 0x01) else ""))
    time.sleep(0.03)

print("="*52)
print("SONUC:", "4 chip de saglam" if all_ok else "en az 1 chip SORUNLU")

lines.release(); spi.close()
