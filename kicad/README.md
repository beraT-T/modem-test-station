# KiCad PCB — Raspberry Pi Breakout / Shield

Modem test istasyonu için Pi breakout kartı KiCad proje dosyaları.

## İçerik (eklenecek)
- `*.kicad_pro` — proje dosyası
- `*.kicad_sch` — şema
- `*.kicad_pcb` — PCB layout
- `gerbers/` — üretim dosyaları
- BOM

## Tasarım notları
Prototipten çıkan dersler (detay: `../docs/KULLANIM_KILAVUZU.md` bölüm 8):
- Her W5500'ün **iki GND pini** de ground plane'e.
- SPI hatları kısa/eşit, MISO + CS hatlarına 10k pull-up.
- 4 W5500 için harici 5V giriş, INA226 I2C hattı ayrı.
