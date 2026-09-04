# Geliştirme Aşamaları (Milestones)

Bu belge, test istasyonunun geliştirilme sürecindeki referans noktalarını ve her aşamada **doğrulanan** teknik gerçekleri kaydeder. Yeni bir sorunla karşılaşıldığında "burası zaten çalışıyordu" demek için başvuru noktasıdır.

---

## M1 — Tek W5500 SPI doğrulaması ✅

**Hedef:** Bir W5500'ün SPI üzerinden konuştuğunu kanıtlamak.

- VERSIONR register'ı (0x0039) okundu → **0x04** (W5500 sabit değeri).
- Ham cevap `01 02 03 04` → byte hizası ve SPI mode 0 doğru.
- **Sonuç:** Chip yaşıyor, SPI + besleme + mode doğru.

---

## M2 — SPI hız tavanı ✅

**Hedef:** Kararlı çalışılabilecek maksimum SPI hızını bulmak.

- 1–20 MHz: 200/200 doğru okuma.
- 30 MHz: 0/200 (bozuluyor).
- **Sonuç:** Kararlı tavan **20 MHz**, üretim hızı **16 MHz** (güven payıyla). Prototip pertinaks + 22 AWG dupont ile.

---

## M3 — Tek W5500 PHY link ✅

**Hedef:** Ethernet PHY'nin gerçek link kurduğunu görmek.

- PHYCFGR (0x002E) okundu → link up, **100 Mbps, full-duplex**.
- **Sonuç:** Trafo + RJ45 + PHY sağlam, kablo/karşı taraf ile auto-negotiation başarılı.

---

## M4 — Çok chip'li GPIO-CS mimarisi ✅

**Hedef:** Donanım CS 2 tane (CE0/CE1) olduğu için 4 chip'i tek SPI bus'ta GPIO-CS ile sürmek.

- `dtoverlay=spi0-0cs` ile CE0/CE1 serbest bırakıldı (yoksa `Errno 16 busy`).
- gpiod v2 ile her chip'in CS'i manuel toggle edildi (ortak SPI, ayrı CS).
- 3 chip (A/B/C) aynı anda VERSIONR=0x04 verdi.
- **Sonuç:** GPIO-CS mimarisi çalışıyor; 4 chip'e ölçeklenebilir (sadece bir CS daha).

---

## M5 — LAN uçtan uca (statik IP + TCP connect) ✅

**Hedef:** W5500'ün modemin LAN portundan gerçekten paket geçirdiğini kanıtlamak.

- Her chip'e statik IP + benzersiz MAC verildi.
- Modem gateway'inin (192.168.1.1) port 80'ine TCP connect → **ESTABLISHED**.
- 3 chip birden modemin 3 ayrı LAN portundan geçti.
- **Sonuç:** PHY + L2(ARP) + L3(IP) + TCP dört katman çalışıyor. Pass/fail kriteri: ESTABLISHED = PASS, timeout = FAIL. (Ping'den daha güvenilir — bazı modem ICMP filtreler.)

---

## M6 — WAN reverse-DHCP ✅

**Hedef:** Modemin WAN portunun "dışarıdan IP alma" görevini test etmek.

- Modem WAN'ı DHCP **client**; Pi eth0 DHCP **sunucu** yapıldı (dnsmasq).
- Modem WAN → DHCP DISCOVER/OFFER/REQUEST/**ACK** → IP aldı.
- vendor class `dslforum.org` → gerçekten DSL modem WAN'ı.
- **Sonuç:** DHCPACK = WAN PASS. Zyxel varsayılanı DHCP olduğu için doğrudan çalışıyor. (NetworkManager eth0'ı düşürmesin diye `wan-test` sabit IP profili gerekli.)

---

## M7 — WiFi malfunction testi ✅

**Hedef:** RSSI seviyesi değil, WiFi'ın **çalışıp çalışmadığını** test etmek (istasyonda modem dibinde → seviye anlamsız).

- Scan (SSID yayında mı) + associate (bağlanabiliyor mu) + ping (veri geçiyor mu).
- Pi 3B+ sadece 2.4 GHz görür → test 2.4 üzerinden.
- Bağlantı için `sudo` gerekli (nmcli).
- **Sonuç:** Üçü de geçerse WiFi PASS. Seviye eşiği yok. Test sonrası wlan0 yönetim ağına döner.

---

## M8 — INA226 akım ölçümü ✅

**Hedef:** Modemin çektiği akımı ölçmek.

- INA226 I2C 0x44'te bulundu (Manufacturer ID 0x5449 = TI).
- High-side, 0.1Ω shunt (R100). İdle modem ~0.34–0.43 A okundu.
- **Sonuç:** Akım okunuyor. Şu an pass/fail'e dahil değil, her aşamada **base referans** olarak loglanıyor. Pencere (alt/üst eşik) yeterli sağlam modem ölçülünce tanımlanacak.

---

## M9 — Master test + akım her aşamada ✅

**Hedef:** Dört testi tek akışta, modem başına tek PASS/FAIL.

- Sıra: boot → idle akım → LAN(1..N) → WAN → WiFi → yük akım → sonuç.
- Sonuç = LAN & WAN & WiFi (AND). Akım her aşamada loglanıyor.
- Boot tespiti W5500 üzerinden (Pi Linux ağı modem LAN'ına bağlı değil).
- Ekrana + log dosyasına yazıyor (WiFi kopsa da sonuç kalır).

---

## M10 — Modem ID sistemi + terminal menü ✅

**Hedef:** Modem tipini ID ile seçmek; additive (yeni modem eklenebilir).

- `modems.json` — modem config'leri ID bazlı (Zyxel = ID 1).
- `run.py` — terminal menü: modem seç → test → renkli PASS/FAIL.
- Kod değişikliği olmadan yeni modem eklenebilir.

---

## Sıradaki (planlanan)

- [ ] **Akım pass/fail penceresi** — birkaç sağlam modem ölçüp idle/yük eşikleri tanımla.
- [ ] **4. LAN portu (D)** — 4 portlu modem gelince fiziksel bağla + test et (kod hazır).
- [ ] **Modem kimlik çekme** — MAC/seri no arayüzden okunup SAP'a kaydedilecek.
- [ ] **PCB** — pertinaks yerine KiCad breakout kartı üretimi.
- [ ] **WAN MAC loglama** — üretimde izlenebilirlik için (mekanizma hazır).
