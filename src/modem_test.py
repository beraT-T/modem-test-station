#!/usr/bin/env python3
# ============================================================
# MODEM TEST - Master Script
# Akis: boot -> idle akim -> LAN(1..N) -> WAN -> WiFi -> yuk akim -> sonuc
# Sonuc = LAN & WAN & WiFi (akim simdilik sadece loglanir - base referans)
#
# Modem config'leri modems.json'dan gelir (ID ile secilir).
# Calistir:
#   sudo python3 modem_test.py --modem-id 1
#   (ya da menuden: sudo python3 run.py)
#
# Cikti: ekrana + LOGFILE
# NOT: WiFi adiminda wlan0 yonetim agindan kopar; log dosyasi kalir.
# ============================================================

import spidev, gpiod, time, subprocess, sys, os, re, json, argparse
from gpiod.line import Direction, Value
from datetime import datetime

# ---------------- SABIT DONANIM PARAMETRELERI ----------------
# (Bunlar donanima bagli, modemden bagimsiz - degismez)
LOGFILE   = os.path.expanduser("~/modem_test.log")

# W5500 / LAN - 4 chip tanimli, secilen modemin lan_port_count kadari kullanilir
# isim: (CS gpio [BCM], IP son okteti)
ALL_CHIPS = {
    "A": (8,  201),   # CE0    / pin 24
    "B": (7,  202),   # CE1    / pin 26
    "C": (25, 203),   # GPIO25 / pin 22
    "D": (24, 204),   # GPIO24 / pin 18
}
SPI_HZ    = 16_000_000       # dogrulanmis uretim hizi (tavan 20 MHz)
GPIOCHIP  = "/dev/gpiochip0"
LAN_SUB   = [255,255,255,0]
LAN_PORT  = 80               # TCP connect hedef portu (modem web arayuzu)

# WAN (eth0 reverse-DHCP) - donanim sabit
WAN_IF    = "eth0"
WAN_RANGE = "192.168.50.100,192.168.50.150"
WAN_WAIT  = 25               # saniye, DHCPACK bekleme

# WiFi arayuzu
WIFI_IF   = "wlan0"

# Yonetim agi + gizli degerler config.local.json'dan gelir (git'e girmez).
# Ornek icin config.example.json'a bak.
def _load_local_config():
    import json
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json")
    try:
        with open(p) as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit("HATA: config.local.json yok. config.example.json'i kopyalayip doldur:\n"
                         "  cp src/config.example.json src/config.local.json  (sonra sifreleri yaz)")

_CFG = _load_local_config()
MGMT_SSID = _CFG.get("mgmt_ssid", "")
MGMT_PASS = _CFG.get("mgmt_pass", "")

# INA226 (akim - sadece log, base referans)
INA_BUS   = 1
INA_ADDR  = 0x44
SHUNT_OHM = 0.1

# ---------------- LOG ----------------
_logf = open(LOGFILE, "a")
def log(msg=""):
    print(msg)
    _logf.write(msg + "\n"); _logf.flush()

def hdr(t):
    log("\n" + "="*56); log(t); log("="*56)

# ---------------- MODEM CONFIG (modems.json) ----------------
def load_modem(modem_id):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modems.json")
    with open(path) as f:
        data = json.load(f)
    modemler = data.get("modemler", {})
    key = str(modem_id)
    if key not in modemler:
        raise SystemExit("HATA: %s ID'li modem modems.json'da yok. Mevcut ID'ler: %s"
                         % (key, ", ".join(sorted(modemler.keys()))))
    return modemler[key]

# ---------------- INA226 ----------------
_ina_bus = None
def ina_init():
    global _ina_bus
    try:
        import smbus2
        _ina_bus = smbus2.SMBus(INA_BUS)
        return True
    except Exception:
        _ina_bus = None
        return False

def read_current():
    if _ina_bus is None: return None
    try:
        d = _ina_bus.read_i2c_block_data(INA_ADDR, 0x01, 2)
        raw = (d[0]<<8)|d[1]
        if raw > 32767: raw -= 65536
        return (raw*0.0025/1000.0)/SHUNT_OHM
    except Exception:
        return None

def log_current(asama):
    c = read_current()
    if c is not None:
        log("    [akim @ %-10s] %6.3f A (%.1f mA)" % (asama, c, c*1000))
    else:
        log("    [akim @ %-10s] OKUNAMADI" % asama)
    return c

# ---------------- W5500 / LAN ----------------
class W5500:
    def __init__(self, chips):
        self.chips = chips
        self.spi = spidev.SpiDev(); self.spi.open(0,0)
        self.spi.max_speed_hz = SPI_HZ; self.spi.mode = 0; self.spi.no_cs = True
        cs = tuple(v[0] for v in chips.values())
        self.lines = gpiod.request_lines(GPIOCHIP, consumer="modemtest",
            config={cs: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)})
    def wr(self, cs, addr, bsb, data):
        self.lines.set_value(cs, Value.INACTIVE)
        self.spi.xfer2([(addr>>8)&0xFF, addr&0xFF, bsb|0x04]+list(data))
        self.lines.set_value(cs, Value.ACTIVE)
    def rd(self, cs, addr, bsb, n=1):
        self.lines.set_value(cs, Value.INACTIVE)
        r = self.spi.xfer2([(addr>>8)&0xFF, addr&0xFF, bsb|0x00]+[0]*n)
        self.lines.set_value(cs, Value.ACTIVE)
        return r[3:]
    def version(self, cs):  return self.rd(cs, 0x0039, 0x00)[0]
    def phy_link(self, cs): return self.rd(cs, 0x002E, 0x00)[0] & 0x01
    def setup_net(self, cs, last, gw, net):
        self.wr(cs, 0x0001, 0x00, gw)
        self.wr(cs, 0x0005, 0x00, LAN_SUB)
        self.wr(cs, 0x0009, 0x00, [0x00,0x08,0xDC,0x01,0x02,last])
        self.wr(cs, 0x000F, 0x00, net+[last])
    def tcp_test(self, cs, gw):
        sr = (0x01) << 3
        self.wr(cs, 0x0000, sr, [0x01])
        self.wr(cs, 0x0004, sr, [0x30,0x39])
        self.wr(cs, 0x0001, sr, [0x01]); time.sleep(0.01)
        if self.rd(cs, 0x0003, sr)[0] != 0x13: return False
        self.wr(cs, 0x000C, sr, gw)
        self.wr(cs, 0x0010, sr, [(LAN_PORT>>8)&0xFF, LAN_PORT&0xFF])
        self.wr(cs, 0x0001, sr, [0x04])
        for _ in range(50):
            st = self.rd(cs, 0x0003, sr)[0]
            if st == 0x17:
                self.wr(cs, 0x0001, sr, [0x08]); return True
            if st == 0x00: return True
            time.sleep(0.05)
        return False
    def close(self):
        self.lines.release(); self.spi.close()

# ---------------- shell helper ----------------
def sh(cmd, timeout=40):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"

# ============================================================
# ANA AKIS
# ============================================================
def run_test(modem_id):
    m = load_modem(modem_id)
    lan_count = m["lan_port_count"]
    chip_order = ["A","B","C","D"][:lan_count]
    chips = {k: ALL_CHIPS[k] for k in chip_order}
    lan_gw_list = [int(x) for x in m["lan_gateway"].split(".")]
    lan_net = lan_gw_list[:3]
    lan_gw_str = m["lan_gateway"]
    wifi_ssid = m["wifi_ssid"]; wifi_pass = m["wifi_pass"]; wifi_gw = m["wifi_gw"]
    if wifi_pass == "__CONFIG__":
        wifi_pass = _CFG.get("modem_wifi_pass", {}).get(str(modem_id), "")

    if os.geteuid() != 0:
        log("!! UYARI: root degil. WiFi/WAN adimlari basarisiz olabilir. 'sudo' ile calistir.")

    hdr("MODEM TEST  %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log("    Modem ID %s: %s" % (modem_id, m["isim"]))
    log("    LAN port sayisi: %d  (aktif chip'ler: %s)" % (lan_count, ", ".join(chip_order)))
    log("    WAN: 1 port (varsayiliyor)")
    ina_ok = ina_init()
    log("    INA226: %s" % ("hazir (her asamada akim loglanacak)" if ina_ok else "YOK"))
    results = {}

    w = W5500(chips)

    # 0) BOOT bekle (W5500 A -> gateway TCP)
    hdr("[0] BOOT bekleniyor (W5500 A -> gateway %s:%d)" % (lan_gw_str, LAN_PORT))
    boot_cs, boot_last = chips["A"]
    booted = False
    for i in range(30):
        if w.version(boot_cs)==0x04 and w.phy_link(boot_cs):
            w.setup_net(boot_cs, boot_last, lan_gw_list, lan_net)
            if w.tcp_test(boot_cs, lan_gw_list):
                log("    boot OK (%d. denemede)" % (i+1)); booted=True; break
        time.sleep(1)
    if not booted: log("    !! boot tespit edilemedi, yine de devam ediliyor")
    log_current("boot")

    # 1) IDLE akim
    hdr("[1] IDLE akim (INA226)"); log_current("idle")

    # 2) LAN portlari
    hdr("[2] LAN portlari (W5500 %s)" % "/".join(chip_order))
    for name in chip_order:
        cs, last = chips[name]
        if w.version(cs) != 0x04:
            log("    LAN %s: chip yok -> FAIL" % name)
            results["LAN_"+name]=False; log_current("LAN_"+name); continue
        if not w.phy_link(cs):
            log("    LAN %s: PHY link YOK -> FAIL" % name)
            results["LAN_"+name]=False; log_current("LAN_"+name); continue
        w.setup_net(cs, last, lan_gw_list, lan_net)
        ok = w.tcp_test(cs, lan_gw_list)
        log("    LAN %s: link OK, TCP %s -> %s" % (name, "OK" if ok else "FAIL", "PASS" if ok else "FAIL"))
        results["LAN_"+name]=ok; log_current("LAN_"+name)
    w.close()

    # 3) WAN
    hdr("[3] WAN portu (eth0 reverse-DHCP)")
    sh("nmcli connection up wan-test ifname %s" % WAN_IF); time.sleep(1)
    sh("pkill dnsmasq 2>/dev/null"); time.sleep(1)
    leasefile = "/tmp/wan_lease.log"; sh("rm -f %s" % leasefile)
    dcmd = ("dnsmasq --interface=%s --bind-interfaces --except-interface=lo "
            "--no-hosts --no-resolv --dhcp-range=%s,255.255.255.0,2m "
            "--dhcp-authoritative --log-dhcp --log-facility=%s"
            % (WAN_IF, WAN_RANGE, leasefile))
    subprocess.Popen(dcmd, shell=True)
    log("    dnsmasq basladi, DHCPACK bekleniyor (%ds)..." % WAN_WAIT)
    wan_ok=False; wan_mac=""
    for _ in range(WAN_WAIT):
        time.sleep(1)
        rc,out,_ = sh("grep DHCPACK %s 2>/dev/null" % leasefile, timeout=3)
        if out:
            wan_ok=True
            mm=re.search(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})', out)
            wan_mac=mm.group(1) if mm else ""
            break
    sh("pkill dnsmasq 2>/dev/null")
    log("    WAN: %s %s" % ("DHCPACK alindi -> PASS" if wan_ok else "DHCPACK YOK -> FAIL",
                            "(MAC %s)"%wan_mac if wan_mac else ""))
    results["WAN"]=wan_ok; log_current("WAN")

    # 4) WiFi
    hdr("[4] WiFi (wlan0 scan+associate+ping)")
    sh("nmcli dev wifi rescan ifname %s" % WIFI_IF); time.sleep(5)
    _,out,_ = sh("nmcli -t -f SSID dev wifi list ifname %s" % WIFI_IF)
    scan_ok = any(l==wifi_ssid for l in out.splitlines())
    log("    scan: %s" % ("SSID bulundu" if scan_ok else "SSID YOK"))
    assoc_ok=ping_ok=False
    if scan_ok:
        sh("nmcli connection delete wifi-test 2>/dev/null")
        rc,o,e = sh("nmcli dev wifi connect '%s' password '%s' ifname %s name wifi-test"
                    % (wifi_ssid, wifi_pass, WIFI_IF)); time.sleep(3)
        assoc_ok = (rc==0 and ("activated" in o.lower() or "connected" in o.lower()))
        log("    associate: %s" % ("OK" if assoc_ok else "FAIL - "+(e or o)))
        if assoc_ok:
            log_current("WiFi_assoc")
            rc,_,_ = sh("ping -c3 -W2 -I %s %s" % (WIFI_IF, wifi_gw))
            ping_ok=(rc==0); log("    ping: %s" % ("OK" if ping_ok else "FAIL"))
    results["WiFi"] = scan_ok and assoc_ok and ping_ok
    log_current("WiFi")
    sh("nmcli connection delete wifi-test 2>/dev/null")
    # yonetim agina don
    log("    yonetim agina donuluyor: %s" % MGMT_SSID)
    rc,o,e = sh("nmcli connection up '%s' ifname %s" % (MGMT_SSID, WIFI_IF))
    if rc != 0:
        rc,o,e = sh("nmcli dev wifi connect '%s' password '%s' ifname %s" % (MGMT_SSID, MGMT_PASS, WIFI_IF))
    log("    yonetim agi: %s" % ("BAGLANDI" if rc==0 else "BAGLANAMADI - "+(e or o)))

    # 5) YUK akim
    hdr("[5] YUK akim (INA226)"); log_current("yuk")

    # 6) SONUC
    hdr("[6] SONUC")
    for k in sorted(results):
        log("    %-8s: %s" % (k, "PASS" if results[k] else "FAIL"))
    overall = all(results.values())
    log("-"*56)
    log("    MODEM: %s" % ("PASS" if overall else "FAIL"))
    log("    (akim pass/fail'e dahil degil, base referans olarak loglandi)")
    hdr("TEST BITTI")
    if _ina_bus is not None: _ina_bus.close()
    return overall, results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modem-id", required=True, help="modems.json'daki modem ID (or. 1)")
    args = ap.parse_args()
    try:
        overall, _ = run_test(args.modem_id)
        sys.exit(0 if overall else 1)
    finally:
        _logf.close()

if __name__ == "__main__":
    main()
