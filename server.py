"""
Mahalliy kompyuterda Web-sahifani brauzerda va Telegram orqali ochish uchun server.
Cloudflare Tunnel orqali bepul xavfsiz HTTPS havolani yaratadi va Telegram WebApp'ga ulaydi.
Ishga tushirish: python server.py
"""
import http.server
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_PATH = os.path.join(BASE_DIR, "cloudflared.exe")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        # Telegram WebApp iframe uchun ruxsatlar
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def get_current_env_url() -> str:
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("WEB_APP_URL="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return ""


def update_env_url(url: str):
    """ .env faylidagi WEB_APP_URL ni yangilash """
    env_path = os.path.join(BASE_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.startswith("WEB_APP_URL="):
            new_lines.append(f"WEB_APP_URL={url}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"WEB_APP_URL={url}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def run_server():
    os.chdir(BASE_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)

    # Serverni alohida oqimda yurgizish
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    local_url = f"http://localhost:{PORT}"
    print("\n" + "=" * 65)
    print(f"✅ Mahalliy HTTP Server ishga tushdi: {local_url}")
    print("=" * 65)

    tunnel_proc = None
    public_url = None

    # Agar cloudflared.exe mavjud bo'lsa, Telegram uchun HTTPS tunnel ochamiz
    if os.path.exists(CLOUDFLARED_PATH):
        print("🌐 Telegram WebApp uchun xavfsiz HTTPS tunnel ochilmoqda...")
        try:
            tunnel_proc = subprocess.Popen(
                [CLOUDFLARED_PATH, "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            # URL chiqishini kutish
            start_time = time.time()
            while time.time() - start_time < 20:
                line = tunnel_proc.stdout.readline()
                if not line:
                    break
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    public_url = m.group(0)
                    break

            # Quvurning to'lib qolishi (pipe buffer deadlock) ning oldini olish uchun
            # qolgan chiqishlarni fonda o'qib turuvchi oqim yaratamiz:
            def _drain_tunnel_output(proc):
                try:
                    for _ in proc.stdout:
                        pass
                except Exception:
                    pass

            threading.Thread(target=_drain_tunnel_output, args=(tunnel_proc,), daemon=True).start()

            if public_url:
                cur_url = get_current_env_url()
                # Agar doimiy havola (surge.sh, netlify.app) bo'lsa, uni aslo o'chirmaymiz!
                if not cur_url or "trycloudflare" in cur_url:
                    update_env_url(public_url)
                    print("\n" + "🎉" * 25)
                    print(f"🚀 TELEGRAM UCHUN ONLAYN HTTPS MANZIL TAYYOR:")
                    print(f"👉 {public_url}")
                    print(f"Ushbu manzil Telegram botga ulandi!")
                    print("🎉" * 25 + "\n")
                else:
                    print("\n" + "🎉" * 25)
                    print(f"🌐 DOIMIY HOSTING FAOL: {cur_url}")
                    print(f"👉 Mahalliy sinov havolasi: {public_url}")
                    print("🎉" * 25 + "\n")
            else:
                print("⚠️ Tunnel havolasi olinmadi. Faqat lokal tarmoqda ishlaydi.")
        except Exception as e:
            print(f"⚠️ Tunnel ishga tushirishda xatolik: {e}")
    else:
        print("ℹ️ cloudflared.exe topilmadi. Faqat lokal ishlaydi.")

    print(f"👉 Kompyuteringizda ochish: {local_url}")
    if public_url:
        print(f"👉 Telegram / Telefon orqali ochish: {public_url}")
    print("\nDasturni to'xtatish uchun: Ctrl + C bosing\n" + "=" * 65)

    # Brauzerda ochish
    try:
        webbrowser.open(local_url)
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer to'xtatilmoqda...")
        if tunnel_proc:
            tunnel_proc.terminate()
        httpd.shutdown()
        print("Server to'xtatildi.")


if __name__ == "__main__":
    run_server()
