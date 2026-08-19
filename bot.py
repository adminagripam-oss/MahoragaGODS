import os
import sys
import time
from datetime import datetime, timezone, timedelta
import requests
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright

# Muat environment variables dari file .env jika ada (sangat berguna untuk VPS)
if os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().strip("'").strip('"')
                        if not os.environ.get(key):
                            os.environ[key] = val
    except Exception as e:
        print(f"Warning: Gagal memuat file .env: {e}")

def get_wib_now():
    """
    Mengembalikan datetime saat ini dalam zona waktu Asia/Jakarta (WIB, UTC+7).
    """
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7)))

def ambil_screenshot(url, filename):
    """
    Mengambil screenshot halaman web menggunakan Playwright (Chromium headless)
    dengan viewport 1920x1080, menunggu networkidle (timeout 60s),
    dan memberikan jeda render selama 6 detik.
    Mendeteksi region yang belum mengisi data/laporan jika relevan.
    """
    print(f"=== Memulai Proses Screenshot ===")
    print(f"URL     : {url}")
    print(f"Output  : {filename}")
    
    start_time = time.time()
    warnings = []
    
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
            
            # 1. Deteksi warning untuk rekap-cro-fullscreen.html
            if "rekap-cro-fullscreen" in url:
                print("Mendeteksi region yang belum isi laporan per jam...")
                try:
                    # Pastikan tabel selesai dimuat
                    page.wait_for_function(
                        'document.getElementById("rekapCROBody") && '
                        'document.getElementById("rekapCROBody").innerText.indexOf("Memuat data...") === -1',
                        timeout=30000
                    )
                    
                    all_regions = [
                        "Aceh", "Sumatera Utara 1", "Sumatera Utara 2 Ex Torganda", "Riau 1",
                        "Riau 2", "Riau 3", "Riau 4", "Bangka Belitung", "Jambi", "Sumatera Barat",
                        "Sumatera Selatan", "Kalimantan Barat 1A", "Kalimantan Barat 1B", "Kalimantan Barat 2",
                        "Kalimantan Selatan 1", "Kalimantan Selatan 2", "Kalimantan Timur", "Kalimantan Utara",
                        "Kalimantan Tengah 1", "Kalimantan Tengah 3", "Kalimantan Tengah 2", "Sulawesi Tenggara",
                        "Sulawesi Tengah"
                    ]
                    cells = page.query_selector_all("#rekapCROBody td")
                    for cell in cells:
                        text = cell.inner_text().strip()
                        if text in all_regions:
                            class_attr = cell.get_attribute("class") or ""
                            if "bg-red-500" in class_attr:
                                warnings.append(text)
                except Exception as ex:
                    print(f"Gagal memparse warning rekap CRO: {ex}")
            
            # 2. Deteksi warning untuk table-modal-fullscreen.html
            elif "table-modal-fullscreen" in url:
                print("Mendeteksi region yang belum mengisi rencana panen...")
                try:
                    # Pastikan tabel selesai dimuat
                    page.wait_for_function(
                        'document.getElementById("modalTableBody") && '
                        'document.getElementById("modalTableBody").innerText.indexOf("Memuat data...") === -1',
                        timeout=30000
                    )
                    
                    rows = page.query_selector_all("#modalTableBody tr")
                    all_regions = [
                        "Aceh", "Sumatera Utara 1", "Sumatera Utara 2 Ex Torganda", "Riau 1",
                        "Riau 2", "Riau 3", "Riau 4", "Bangka Belitung", "Jambi", "Sumatera Barat",
                        "Sumatera Selatan", "Kalimantan Barat 1A", "Kalimantan Barat 1B", "Kalimantan Barat 2",
                        "Kalimantan Selatan 1", "Kalimantan Selatan 2", "Kalimantan Utara",
                        "Kalimantan Timur", "Kalimantan Tengah 1", "Kalimantan Tengah 2",
                        "Kalimantan Tengah 3", "Sulawesi Tengah", "Sulawesi Tenggara"
                    ]
                    for row in rows:
                        cells = row.query_selector_all("td")
                        if len(cells) >= 2:
                            region_cell = cells[1]
                            style = region_cell.get_attribute("style") or ""
                            text = region_cell.inner_text().strip()
                            if "b91c1c" in style or "◯" in text or "\u25CB" in text or "9711" in text:
                                # Cocokkan dengan region list untuk membersihkan icon status
                                for r in all_regions:
                                    if r in text:
                                        warnings.append(r)
                                        break
                except Exception as ex:
                    print(f"Gagal memparse warning rencana panen: {ex}")
            
            # 3. Deteksi warning untuk rekap_tk_panen.html
            elif "rekap_tk_panen" in url:
                print("Mendeteksi region yang belum mengisi ketersediaan TK Panen...")
                try:
                    # Pastikan tabel selesai dimuat
                    page.wait_for_selector("#monitoring-tk-table tbody tr", timeout=30000)
                    
                    rows = page.query_selector_all("#monitoring-tk-table tbody tr")
                    all_regions = [
                        "Aceh", "Sumut 1", "Sumut 2", "Riau 1",
                        "Riau 2", "Riau 3", "Riau 4", "Babel", "Jambi", "Sumbar",
                        "Sumsel", "Kalbar 1", "Kalbar 2", "Kalsel 1", "Kalsel 2",
                        "Kaltara", "Kaltim", "Kalteng 1", "Kalteng 2", "Kalteng 3",
                        "Sulteng", "Sultra",
                        # Fallbacks in case names are different
                        "Sumatera Utara 1", "Sumatera Utara 2 Ex Torganda", "Sumut 2 Ex Torganda",
                        "Bangka Belitung", "Sumatera Barat", "Sumatera Selatan",
                        "Kalimantan Barat 1A", "Kalimantan Barat 1B", "Kalimantan Barat 2",
                        "Kalimantan Selatan 1", "Kalimantan Selatan 2", "Kalimantan Utara",
                        "Kalimantan Timur", "Kalimantan Tengah 1", "Kalimantan Tengah 2",
                        "Kalimantan Tengah 3", "Sulawesi Tengah", "Sulawesi Tenggara"
                    ]
                    for row in rows:
                        class_attr = row.get_attribute("class") or ""
                        if "bg-red-50" in class_attr:
                            cells = row.query_selector_all("td")
                            for cell in cells:
                                text = cell.inner_text().strip()
                                for r in all_regions:
                                    if r.lower() == text.lower() or text.lower() == r.lower():
                                        warnings.append(r)
                                        break
                except Exception as ex:
                    print(f"Gagal memparse warning ketersediaan TK panen: {ex}")
            
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
    return warnings

def kirim_fonnte(file_path, caption, target_phone=None):
    """
    Mengirim file screenshot lokal ke WhatsApp via REST API Fonnte.
    """
    print(f"=== Memulai Pengiriman WhatsApp via Fonnte ===")
    wa_token = os.environ.get("WA_TOKEN")
    if not target_phone:
        target_phone = os.environ.get("TARGET_PHONE") or "120363410041245092@g.us"
    
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
        
        # Pengaman: Jalankan hanya antara jam 06:00 dan 18:00 WIB
        now_wib = get_wib_now()
        hour = now_wib.hour
        if not (6 <= hour <= 18):
            print(f"Bypass: Hourly report hanya aktif antara 06:00 - 18:00 WIB (Saat ini: {now_wib.strftime('%H:%M')} WIB)")
            sys.exit(0)
            
        date_str = now_wib.strftime("%d/%m/%Y")
        time_str = now_wib.strftime("%H:%M")
        
        if hour == 18:
            next_schedule_str = "besok pukul 06:00 WIB"
        else:
            next_wib = now_wib + timedelta(hours=1)
            next_schedule_str = f"pukul {next_wib.strftime('%H:%M')} WIB"
        
        # 1. Screenshot admin-screenshot.html -> kirim
        ambil_screenshot("https://agri-pam.id/admin-screenshot.html", "admin.jpg")
        caption_admin = (
            f"📊 [Grafik Rekap Total Panen per Jam]\n"
            f"📅 Data per: {date_str} - {time_str} WIB\n"
            f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
        )
        kirim_fonnte("admin.jpg", caption_admin)
        
        # 2. Jeda 3 detik
        print("Menunggu jeda 3 detik...")
        time.sleep(3)
        
        # 3. Screenshot rekap-cro-fullscreen.html -> kirim dengan deteksi warning
        late_regions = ambil_screenshot("https://agri-pam.id/rekap-cro-fullscreen.html", "rekap_cro.jpg")
        
        if late_regions:
            warning_text = "\n".join([f"⚠️ {r}" for r in late_regions])
        else:
            warning_text = "⚠️ (Semua region sudah mengisi)"
            
        caption_cro = (
            f"📑 [Tabel Rekap Total Panen per Jam]\n"
            f"📅 Data per: {date_str} - {time_str} WIB\n\n"
            f"⚠️ Region Belum Isi Laporan Panen per Jam:\n"
            f"{warning_text}\n\n"
            f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
        )
        kirim_fonnte("rekap_cro.jpg", caption_cro)
        
        # 4. Jeda 3 detik
        print("Menunggu jeda 3 detik...")
        time.sleep(3)
        
        # 5. Screenshot rekap_tk_panen.html -> kirim ke grup khusus dengan deteksi warning
        target_grup_tk = os.environ.get("TARGET_PHONE_TK") or "120363425038459858@g.us"
        late_regions_tk = ambil_screenshot("https://agri-pam.id/rekap_tk_panen.html", "rekap_tk_panen.jpg")
        
        if late_regions_tk:
            warning_text_tk = "\n".join([f"🔴 {r}" for r in late_regions_tk])
        else:
            warning_text_tk = "🔴 (Semua region sudah mengisi)"
            
        caption_tk = (
            f"📢 Update Regional Yang belum mengisi Ketersediaan TK Panen\n\n"
            f"{warning_text_tk}\n\n"
            f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
        )
        kirim_fonnte("rekap_tk_panen.jpg", caption_tk, target_phone=target_grup_tk)
        
    elif mode == "daily_2210":
        print("Menjalankan tugas: DAILY REPORT\n")
        
        now_wib = get_wib_now()
        date_str = now_wib.strftime("%d/%m/%Y")
        
        # Tentukan apakah pengiriman pagi (06:30) atau malam (22:30)
        hour = now_wib.hour
        if hour < 12:
            # Pagi
            caption_time = "06:30"
            next_schedule = "pukul 22:30 WIB."
        else:
            # Malam
            caption_time = "22:30"
            next_schedule = "besok pukul 06:30 WIB."
            
        # 1. Screenshot table-modal-fullscreen.html -> kirim dengan deteksi rencana panen yang belum terisi
        unfilled_plans = ambil_screenshot("https://agri-pam.id/table-modal-fullscreen.html", "table_modal.jpg")
        
        if unfilled_plans:
            warning_text = "\n".join([f"🔴 ◯{r}" for r in unfilled_plans])
        else:
            warning_text = "🔴 (Semua region sudah mengisi rencana)"
            
        caption_daily = (
            f"📢 [Tabel Rencana & Estimasi Panen]\n"
            f"📅 Data per: {date_str} - {caption_time} WIB\n\n"
            f"🔴 Region Belum Mengisi Rencana Panen:\n"
            f"{warning_text}\n\n"
            f"⏰ Laporan berikutnya dikirim otomatis {next_schedule}"
        )
        kirim_fonnte("table_modal.jpg", caption_daily)
        
    else:
        print(f"Error: Mode '{mode}' tidak valid.")
        print("Pilih antara 'hourly' atau 'daily_2210'.")
        sys.exit(1)
