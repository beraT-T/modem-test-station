# Kullanım Kılavuzu — Donanım ve Kurulum

Bu belge test istasyonunun donanım bağlantılarını, kurulumunu ve sık karşılaşılan sorunların çözümünü açıklar.

---

## 1. Donanım listesi

| Parça | Adet | Not |
|---|---|---|
| Raspberry Pi 3B+ | 1 | Kontrolcü |
| W5500 Ethernet modülü | 4 | LAN portları için (üzerinde AMS1117-3.3 + HanRun trafo) |
| INA226 breakout | 1 | Akım ölçümü, 0.1Ω shunt (R100) |
| Harici 5V besleme | 1 | 4× W5500 için (Pi ayrı USB'den beslenir) |
| Pertinaks / breakout PCB | 1 | Bağlantı taşıyıcı (KiCad tasarımı `kicad/` altında) |
| 22 AWG kablo + dupont | — | Bağlantılar |

> Görsel: prototip kurulum → `images/rig_overview.jpg` *(eklenecek)*
> Görsel: 4× W5500 pertinaks → `images/w5500_board.jpg` *(eklenecek)*

---

## 2. Raspberry Pi ↔ W5500 pinout (4 port)

Tüm W5500'ler ortak SPI bus'ı paylaşır; her birinin CS'i ayrı GPIO'dur.

| İşlev | Pi fiziksel pin | BCM | W5500 |
|---|---|---|---|
| SCLK | 23 | GPIO11 | 4 chip ortak |
| MOSI | 19 | GPIO10 | 4 chip ortak |
| MISO | 21 | GPIO9 | 4 chip ortak |
| CS A | 24 | GPIO8 | A → SCS |
| CS B | 26 | GPIO7 | B → SCS |
| CS C | 22 | GPIO25 | C → SCS |
| CS D | 18 | GPIO24 | D → SCS |
| GND | 6, 9, 14, 20, 25 | — | 4 chip ortak |

**Her W5500 modülü:**
- SCLK / MOSI / MISO → yukarıdaki ortak hatlar
- SCS → kendi CS pini (A→24, B→26, C→22, D→18)
- VIN (5V) → harici 5V ray *(modül kendi 3.3V'unu AMS1117 ile üretir — 5V ver, 3.3V değil)*
- **GND → her iki GND pinini de bağla** (kritik, aşağıya bak)
- RST, INT → boş (test için gerekmez)

---

## 3. INA226 (akım) bağlantısı

High-side ölçüm, 12V besleme hattına seri:

**Güç tarafı:**
```
12V(+) → VIN+ → [shunt] → VIN- → modem(+)
12V(-) ────────────────────────→ modem(-)   [düz geçer, INA226'ya girmez]
```

**I2C tarafı (Pi'ye):**
| INA226 | Pi pin | BCM |
|---|---|---|
| VCC | 1 (3.3V) | — |
| GND | 9 (GND) | — |
| SDA | 3 | GPIO2 |
| SCL | 5 | GPIO3 |

> Sadece akım ölçüyoruz; 12V(−)'yi Pi GND'ye bağlamak **gerekmez** (high-side'da akım shunt farkından gelir). 12V(+)'yi **asla** Pi'nin güç pinlerine değdirme.

---

## 4. Güç mimarisi ve ortak GND

- **Pi:** ayrı USB adaptöründen 5V.
- **4× W5500:** harici 5V beslemeden (modüller kendi 3.3V'unu üretir).
- **Ortak GND:** Pi GND + harici 5V GND + INA226 GND (I2C) + 4 W5500 GND **tek düğümde** buluşmalı. SPI/I2C sinyalleri ortak referans olmadan çalışmaz.

---

## 5. Yazılım kurulumu

### 5.1 SPI'i 0 donanım CS ile aç
4 chip'i GPIO-CS ile sürmek için SPI'ın donanım CE pinlerini serbest bırakmak gerekir.

`/boot/firmware/config.txt` içinde:
```
# dtparam=spi=on           <- bunu kaldır/yorumla
dtoverlay=spi0-0cs         <- bunu ekle
```
Sonra `sudo reboot`. Kontrol: `ls /dev/spidev*` → sadece `spidev0.0` görünmeli.

### 5.2 I2C aç
```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
i2cdetect -y 1     # INA226 -> 0x44 gorunmeli
```

### 5.3 Paketler
```bash
sudo apt install -y python3-spidev python3-libgpiod i2c-tools dnsmasq
pip3 install smbus2 --break-system-packages
```

### 5.4 eth0 sabit IP (WAN reverse-DHCP)
```bash
sudo nmcli connection add type ethernet ifname eth0 con-name wan-test \
  ipv4.method manual ipv4.addresses 192.168.50.1/24 ipv6.method disabled autoconnect yes
```

### 5.5 Yönetim WiFi ağı
`src/modem_test.py` içinde `MGMT_SSID` / `MGMT_PASS` — Pi'nin test sonrası döneceği ağ. Ortam değişince güncelle.

---

## 6. Çalıştırma

```bash
sudo python3 src/run.py          # menü
# veya
sudo python3 src/modem_test.py --modem-id 1
```

Sonuç ekrana **ve** `~/modem_test.log`'a yazılır.

---

## 7. Sorun giderme

### W5500 chip'leri 0x00 / 0xFF veriyor, kararsız
En sık sebep: **oynak lehim / kontak** (özellikle yeni pertinaks). Belirti: aynı bağlantıyla arka arkaya farklı sonuç.

1. `python3 src/w5500_verify.py` çalıştır — hangi chip'ler sorunlu gör.
2. **Her W5500'ün iki GND pinini de bağla.** Tek GND oynaksa tüm bus kararsızlaşır — bu bizde ana sebepti.
3. Dokun-testi: aşağıdaki döngüyü çalıştırıp lehimlere hafifçe bastır, değer değişen nokta oynak lehimdir:
   ```bash
   watch -n 0.3 'python3 -c "import spidev; s=spidev.SpiDev(); s.open(0,0); s.max_speed_hz=4000000; s.mode=0; print(hex(s.xfer2([0,0x39,0,0])[3])); s.close()"'
   ```
4. Oynak lehimi havyayla yeniden ısıt (reflow).

> `0x00` genelde MISO/CS gelmiyor; `0xFF` genelde chip beslenmiyor veya o slotta modül yok.

### `Errno 16 Device or resource busy` (gpiod)
SPI hâlâ CE0/CE1'i rezerve ediyor. `dtoverlay=spi0-0cs` ekli mi ve reboot edildi mi kontrol et (adım 5.1).

### WAN DHCPACK gelmiyor
- eth0 IP'sini NetworkManager düşürmüş olabilir → `wan-test` profili aktif mi (`nmcli con show --active`).
- Modem WAN'ı PPPoE modundaysa DHCP denemez → arayüzden "Dynamic/DHCP" moduna al.

### WiFi SSID görünmüyor
- Pi 3B+ sadece 2.4 GHz görür; modem sadece 5 GHz yayınlıyorsa görünmez → modemin 2.4'ünü aç.
- `sudo nmcli dev wifi rescan ifname wlan0` ile taze tarama (cache eski olabilir).

### `associate: Not authorized to control networking`
Script'i `sudo` ile çalıştır (nmcli bağlantı kurmak için root ister).

---

## 8. PCB (KiCad)

Raspberry Pi breakout/shield tasarımı `kicad/` klasöründe. Kaynak proje dosyaları + üretim görselleri eklenecek.

> Görsel: PCB 3D render → `images/pcb_render.png` *(eklenecek)*
> Görsel: PCB şeması → `images/pcb_schematic.png` *(eklenecek)*

**PCB tasarım notları (prototipten çıkan dersler):**
- Her W5500'ün **iki GND pini** de ground plane'e bağlansın.
- SPI hatları (SCLK/MOSI/MISO) kısa ve mümkünse eşit uzunlukta.
- MISO ortak hattına 10k pull-up (opsiyonel, iyi pratik).
- 4 CS hattına 10k pull-up (boot sırasında belirsizliği önler).
- INA226 I2C ile W5500 SPI ayrı; çakışma yok.
