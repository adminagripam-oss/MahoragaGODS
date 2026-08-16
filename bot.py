import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

def ambil_screenshot(url, filename):
    """
    Mengambil screenshot halaman web menggunakan Playwright (Chromium headless)
    dengan viewport 1920x1080, menunggu networkidle (timeout 60s),
    dan memberikan jeda render selama 6 detik.
    """
    print(f"=== Memulai Proses Screenshot ===")
    print(f"URL     : {url}")
    print(f"Output  : {filename}")
    
    start_time = time.time()
    try:
        with sync_playwright() as p:
            print("Membuka browser Chromium headless...")
            browser = p.chromium.launch(headless=True)
            
            # Setup viewport 1920x1080
            print("Membuat halaman baru dengan viewport 1920x1080...")
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            
            # Navigasi ke URL dengan timeout 60 detik (60000 ms) dan tunggu networkidle
            print("Membuka URL dan menunggu networkidle (maksimal 60 detik)...")
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Jeda tambahan 6 detik untuk render grafik/tabel
            print("Halaman idle. Menunggu 6 detik tambahan untuk render data...")
            time.sleep(6)
            
            # Ambil screenshot (format JPEG)
            page.screenshot(path=filename, type="jpeg")
            print(f"Screenshot berhasil disimpan di: {filename}")
            
            browser.close()
    except Exception as e:
        print(f"Error saat mengambil screenshot: {e}")
        # Hentikan eksekusi jika screenshot gagal, agar tidak mengirim gambar kosong/lama
        sys.exit(1)
        
    duration = time.time() - start_time
    print(f"Proses screenshot selesai dalam {duration:.2f} detik.\n")

def kirim_fonnte(file_path, caption):
    """
    Mengirim file screenshot lokal ke WhatsApp via REST API Fonnte.
    """
    print(f"=== Memulai Pengiriman WhatsApp via Fonnte ===")
    wa_token = os.environ.get("WA_TOKEN")
    target_phone = os.environ.get("TARGET_PHONE") or "120363431116867451@g.us"
    
    if not wa_token:
        print("Error: Kredensial 'WA_TOKEN' tidak ditemukan di Environment Variables!")
        sys.exit(1)
        
    print(f"File   : {file_path}")
    print(f"Target : {target_phone}")
    
    url = "https://api.fonnte.com/send"
    headers = {
        "Authorization": wa_token
    }
    payload = {
        "target": target_phone,
        "message": caption
    }
    
    if not os.path.exists(file_path):
        print(f"Error: File lokal '{file_path}' tidak ditemukan!")
        sys.exit(1)
        
    try:
        print(f"Mengirim POST request ke {url}...")
        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, "image/jpeg")
            }
            response = requests.post(url, data=payload, files=files, headers=headers)
            
            # Logging status respons HTTP
            print(f"HTTP Status Code : {response.status_code}")
            print(f"HTTP Response Body: {response.text}")
            
            try:
                res_data = response.json()
            except Exception:
                res_data = {}
                
            if response.status_code == 200 and res_data.get("status") is True:
                print("Laporan berhasil dikirim ke WhatsApp via Fonnte.")
            else:
                print(f"Gagal mengirim laporan! Status HTTP: {response.status_code}, Status Fonnte: {res_data.get('status')}")
                sys.exit(1)
    except Exception as e:
        print(f"Error terjadi saat menghubungi API Fonnte: {e}")
        sys.exit(1)
    print("==============================================\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Argumen mode diperlukan!")
        print("Penggunaan: python bot.py [hourly|daily_2210]")
        sys.exit(1)
        
    mode = sys.argv[1]
    
    if mode == "hourly":
        print("Menjalankan tugas: HOURLY REPORT\n")
        # 1. Screenshot admin-screenshot.html -> kirim
        ambil_screenshot("https://agri-pam.id/admin-screenshot.html", "admin.jpg")
        kirim_fonnte("admin.jpg", "📊 *Update Laporan Per Jam (Admin)*")
        
        # 2. Jeda 3 detik
        print("Menunggu jeda 3 detik...")
        time.sleep(3)
        
        # 3. Screenshot rekap-cro-fullscreen.html -> kirim
        ambil_screenshot("https://agri-pam.id/rekap-cro-fullscreen.html", "rekap_cro.jpg")
        kirim_fonnte("rekap_cro.jpg", "📊 *Update Laporan Per Jam (Rekap CRO)*")
        
    elif mode == "daily_2210":
        print("Menjalankan tugas: DAILY REPORT 22:10 WIB\n")
        # 1. Screenshot table-modal-fullscreen.html -> kirim
        ambil_screenshot("https://agri-pam.id/table-modal-fullscreen.html", "table_modal.jpg")
        kirim_fonnte("table_modal.jpg", "📌 *Laporan Harian (Table Modal) - 22:10 WIB*")
        
    else:
        print(f"Error: Mode '{mode}' tidak valid.")
        print("Pilih antara 'hourly' atau 'daily_2210'.")
        sys.exit(1)
