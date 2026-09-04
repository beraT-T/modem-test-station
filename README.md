# Modem Test İstasyonu

Konveyör bandından geçen modemlerin **elektriksel ve bağlantısal** olarak otomatik test edilmesi için Raspberry Pi tabanlı test sistemi. Modemin LAN portları, WAN portu, WiFi'ı ve çektiği akım tek istasyonda kontrol edilir; sonuç tek **PASS / FAIL** olarak üretilir.

Türk Telekom × Pievision Ar-Ge projesi kapsamında geliştirilmiştir.

---

## Ne yapar?

Bir modem test istasyonuna yerleştirilir, operatör bağlar ve reset'ler; Raspberry Pi sırayla:

| Aşama | Ne test edilir | Nasıl |
|---|---|---|
| Boot | Modem açıldı mı | W5500 üzerinden gateway'e TCP |
| İdle akım | Boştaki güç tüketimi | INA226 (sadece loglanır) |
| LAN A/B/C/D | Her LAN portu ayrı ayrı | 4× W5500, statik IP + TCP connect |
| WAN | Dış internet girişi | Pi eth0 reverse-DHCP (Pi sunucu olur, modem lease alır) |
| WiFi | Kablosuz malfunction | wlan0 scan + associate + ping |
| Yük akım | Yük altında güç | INA226 (sadece loglanır) |
| Sonuç | LAN & WAN & WiFi | Hepsi PASS ise MODEM PASS |

> **Not:** Akım şu an pass/fail'e dahil değil — her aşamada **base referans** olarak loglanır. Yeterli sağlam modem ölçülüp normal aralık çıkarılınca pencere (alt/üst eşik) tanımlanacak.

---

## Donanım mimarisi

Her test farklı bir kanaldan gider, dördü birbirinden bağımsızdır:

```
                    Raspberry Pi 3B+
                          |
   +----------+-----------+-----------+-------------+
   |          |           |           |             |
 SPI bus   eth0        wlan0        I2C           (USB güç, ayrı)
   |          |           |           |
4× W5500   WAN portu   WiFi 2.4G   INA226
(LAN A-D)  (rev-DHCP)  (scan+assoc) (akım, high-side shunt)
   |          |           |           |
   +----------+-----> TEST EDİLEN MODEM <----------+
```

- **LAN:** 4× W5500 Ethernet modülü, ortak SPI bus, her chip ayrı GPIO-CS. Modemin her LAN portuna bir W5500 kablosu.
- **WAN:** Pi'nin dahili Ethernet portu. Modem WAN'ı DHCP client olduğu için Pi burada DHCP **sunucu** olur (reverse-DHCP).
- **WiFi:** Pi'nin dahili WiFi'ı (wlan0), 2.4 GHz. Modeme associate olup ping atar.
- **Akım:** INA226 (I2C), 12V besleme hattına high-side shunt ile seri.

Detaylı pinout ve bağlantılar için: [`docs/KULLANIM_KILAVUZU.md`](docs/KULLANIM_KILAVUZU.md)

---

## Kurulum

Raspberry Pi OS (Bookworm) üzerinde:

```bash
# SPI'i 0 donanim CS ile ac (4 chip'i GPIO-CS ile surmek icin)
# /boot/firmware/config.txt icinde:  dtoverlay=spi0-0cs   (dtparam=spi=on yerine)
# I2C'yi ac:  sudo raspi-config nonint do_i2c 0

sudo apt update
sudo apt install -y python3-spidev python3-libgpiod i2c-tools dnsmasq
pip3 install smbus2 --break-system-packages

# eth0 icin sabit IP profili (WAN reverse-DHCP)
sudo nmcli connection add type ethernet ifname eth0 con-name wan-test \
  ipv4.method manual ipv4.addresses 192.168.50.1/24 ipv6.method disabled autoconnect yes
```

### Gizli config (şifreler)
Şifreler `config.local.json`'da tutulur (git'e girmez). Örnekten kopyalayıp doldur:
```bash
cp src/config.example.json src/config.local.json
# sonra src/config.local.json icine yonetim agi + modem WiFi sifrelerini yaz
```

---

## Kullanım

### Menü ile (önerilen)
```bash
sudo python3 src/run.py
```
Modem tipini seç → Enter → test çalışır → büyük renkli PASS/FAIL.

### Doğrudan
```bash
sudo python3 src/modem_test.py --modem-id 1
```

### Sadece W5500 chip'lerini doğrula (bağlantı sorunu ararken)
```bash
python3 src/w5500_verify.py
```

> **WiFi uyarısı:** Test WiFi adımında `wlan0`'ı yönetim ağından koparıp modeme bağlanır. SSH ile çalışıyorsan o an bağlantın düşebilir — **sonuç `~/modem_test.log`'a yazılır**, kaybolmaz. Monitör+klavye ile çalışıyorsan bir sorun olmaz.

---

## Yeni modem ekleme

Modem tanımları [`src/modems.json`](src/modems.json) içinde ID'ye göre tutulur. Zyxel = ID 1. Yeni modem eklemek için sonraki ID'yi ekle:

```json
"2": {
  "isim": "Yeni Modem Adi",
  "lan_port_count": 4,
  "lan_gateway": "192.168.1.1",
  "wifi_ssid": "reset sonrasi SSID",
  "wifi_pass": "sifre",
  "wifi_gw": "192.168.1.1",
  "notlar": "MAC prefix, reset yontemi vb."
}
```

Kod değişikliği gerekmez; menü otomatik olarak yeni modemi listeler.

---

## Dosya yapısı

```
modem-test-station/
├── README.md                    # bu dosya
├── src/
│   ├── run.py                   # terminal menü (modem seç → test → PASS/FAIL)
│   ├── modem_test.py            # ana test motoru (4 aşama + akım log)
│   ├── modems.json              # modem tanımları (ID bazlı, additive)
│   └── w5500_verify.py          # 4× W5500 hızlı chip doğrulama
├── docs/
│   ├── KULLANIM_KILAVUZU.md     # kurulum, pinout, pertinaks, sorun giderme
│   └── MILESTONES.md            # geliştirme aşamaları / referans noktaları
├── images/                      # donanım fotoğrafları, şemalar
└── kicad/                       # KiCad PCB proje dosyaları (Pi breakout shield)
```

---

## Doğrulanmış teknik notlar

Geliştirme sırasında test edilerek sabitlenen değerler:

- **SPI hızı:** 16 MHz (kararlı tavan 20 MHz; 30 MHz'de bozuluyor). Prototip pertinaks + 22 AWG dupont ile.
- **W5500 CS:** Donanım CS 2 tane (CE0/CE1) yetmediği için 4'ü de GPIO-CS. `dtoverlay=spi0-0cs` şart.
- **W5500 GND:** Modüldeki **iki GND pinini de bağla** — tek GND oynak kontağa açık, kararsızlığa yol açar.
- **INA226:** high-side, 0.1Ω shunt (R100). Sadece akım için 12V(−) ortak GND'ye bağlanması gerekmez.
- **WAN:** Zyxel varsayılanı DHCP; reverse-DHCP testi doğrudan çalışır.
- **WiFi:** Pi 3B+ sadece 2.4 GHz görür. Test 2.4 GHz üzerinden. RSSI seviye eşiği yok (istasyonda hep güçlü) — sadece "çalışıyor mu" testi.

---

## Lisans

İç kullanım / Ar-Ge. (Lisans eklenecek.)
