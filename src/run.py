#!/usr/bin/env python3
# ============================================================
# MODEM TEST - Terminal Menu (SSH / HDMI)
# Modem sec -> test calistir -> buyuk renkli PASS/FAIL goster
# Calistir: sudo python3 run.py
# ============================================================

import json, os, sys

# ANSI renkler
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

def load_modems():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modems.json")
    with open(path) as f:
        return json.load(f).get("modemler", {})

def banner():
    print(B + "="*50 + X)
    print(B + "        MODEM TEST ISTASYONU" + X)
    print(B + "="*50 + X)

def show_result(overall, results):
    print()
    for k in sorted(results):
        c = G if results[k] else R
        print("   %-10s %s%s%s" % (k, c, "PASS" if results[k] else "FAIL", X))
    print()
    if overall:
        print(G + B + "   +--------------------------+")
        print(       "   |        M O D E M         |")
        print(       "   |         P A S S          |")
        print(       "   +--------------------------+" + X)
    else:
        print(R + B + "   +--------------------------+")
        print(       "   |        M O D E M         |")
        print(       "   |         F A I L          |")
        print(       "   +--------------------------+" + X)
    print()

def main():
    if os.geteuid() != 0:
        print(Y + "!! 'sudo python3 run.py' ile calistir (WiFi/WAN root ister)." + X)
        # devam et, kullanici gorur

    import modem_test  # ayni klasordeki test motoru

    while True:
        banner()
        modemler = load_modems()
        if not modemler:
            print(R + "modems.json'da modem yok." + X); return
        print("  Modem sec:\n")
        ids = sorted(modemler.keys(), key=lambda x: int(x))
        for i in ids:
            m = modemler[i]
            print("   [%s] %-18s (%d LAN, SSID: %s)"
                  % (i, m["isim"], m["lan_port_count"], m["wifi_ssid"]))
        print("   [q] cikis\n")

        sec = input("  Secim: ").strip().lower()
        if sec == "q":
            print("cikiliyor."); return
        if sec not in modemler:
            print(R + "  Gecersiz secim.\n" + X); continue

        m = modemler[sec]
        print("\n" + B + ">> %s test ediliyor... (WiFi adiminda SSH kopabilir, log dosyasi kalir)" % m["isim"] + X)
        input("   Modem bagli ve hazir mi? Enter'a bas...")

        try:
            overall, results = modem_test.run_test(sec)
            show_result(overall, results)
        except Exception as e:
            print(R + "  TEST HATASI: %s" % e + X)

        again = input("  Baska test? (e/h): ").strip().lower()
        if again != "e":
            print("cikiliyor."); return
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
