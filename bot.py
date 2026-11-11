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

# Alamat aplikasi. Arahkan ke subdomain uji lebih dulu lewat AGRIPAM_BASE_URL,
# misalnya https://v2.agri-pam.id, sebelum domain utama ditukar.
BASE_URL = (os.environ.get("AGRIPAM_BASE_URL") or "https://agri-pam.id").rstrip("/")

# Token baca halaman publik v2 (PUBLIC_READ_TOKEN milik API). Tanpa token,
# halaman publik tidak memuat data dan endpoint belum-lapor menjawab 401.
READ_TOKEN = os.environ.get("PUBLIC_READ_TOKEN") or ""

# Halaman grafik "Rekap Total Panen per Jam" belum punya padanan di v2:
# admin-screenshot.html memakai sesi admin palsu sehingga tidak dimigrasi.
# Isi GRAFIK_URL bila halaman penggantinya sudah ada; bila kosong, langkah itu dilewati.
GRAFIK_URL = os.environ.get("GRAFIK_URL") or ""


def get_wib_now():
    """
    Mengembalikan datetime saat ini dalam zona waktu Asia/Jakarta (WIB, UTC+7).
    """
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7)))


def halaman_publik(path):
    """Alamat halaman publik v2 lengkap dengan token baca."""
    return f"{BASE_URL}/publik/{path}?token={READ_TOKEN}"


def ambil_screenshot(url, filename):
    """
    Mengambil screenshot halaman web menggunakan Playwright (Chromium headless)
    dengan viewport 1920x1080, menunggu tabel terisi, lalu memberi jeda render.
    """
    print("=== Memulai Proses Screenshot ===")
    # Token tidak ikut dicetak ke log.
    print(f"URL     : {url.split('?')[0]}")
    print(f"Output  : {filename}")

    start_time = time.time()

    try:
        with sync_playwright() as p:
            print("Membuka browser Chromium headless...")
            browser = p.chromium.launch(headless=True)

            print("Membuat halaman baru dengan viewport 1920x1080...")
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            print("Membuka URL dan menunggu load (maksimal 60 detik)...")
            page.goto(url, wait_until="load", timeout=60000)

            # Halaman v2 mengambil datanya setelah render pertama; tunggu baris tabel muncul.
            print("Menunggu tabel terisi (maksimal 30 detik)...")
            page.wait_for_selector("table tbody tr", timeout=30000)

            print("Menunggu 6 detik tambahan untuk render data...")
            time.sleep(6)

            page.screenshot(path=filename, type="jpeg")
            print(f"Screenshot berhasil disimpan di: {filename}")

            browser.close()
    except Exception as e:
        print(f"Error saat mengambil screenshot: {e}")
        # Hentikan eksekusi jika screenshot gagal, agar tidak mengirim gambar kosong/lama
        sys.exit(1)

    duration = time.time() - start_time
    print(f"Proses screenshot selesai dalam {duration:.2f} detik.\n")


def ambil_belum_lapor(jenis, tanggal=None):
    """
    Mengambil daftar region yang belum melapor dari API v2.

    Daftar ini dulu disusun dengan membaca DOM halaman lama (class bg-red-500 dan
    sejenisnya) dan setiap galat parsing ditelan. Cara itu gagal diam-diam begitu
    tampilan berubah: daftarnya menjadi kosong dan caption menyatakan semua region
    sudah mengisi. Sekarang datanya dari API, dan kegagalan menghentikan proses.
    """
    print(f"=== Mengambil daftar region belum lapor ({jenis}) ===")
    if not READ_TOKEN:
        print("Error: 'PUBLIC_READ_TOKEN' tidak ditemukan di Environment Variables!")
        sys.exit(1)

    url = f"{BASE_URL}/api/v1/publik/belum-lapor"
    params = {"jenis": jenis}
    if tanggal:
        params["tanggal"] = tanggal

    try:
        response = requests.get(
            url, params=params, headers={"X-Read-Token": READ_TOKEN}, timeout=30
        )
    except Exception as e:
        print(f"Error saat menghubungi API belum-lapor: {e}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"Gagal membaca daftar belum lapor. HTTP {response.status_code}: {response.text}")
        sys.exit(1)

    try:
        data = response.json()
    except Exception:
        print(f"Jawaban API bukan JSON: {response.text}")
        sys.exit(1)

    regions = data.get("regions")
    if not isinstance(regions, list):
        print(f"Jawaban API tidak sesuai dugaan: {response.text}")
        sys.exit(1)

    print(f"Slot diperiksa : {data.get('jam')}")
    print(f"Belum lapor    : {len(regions)} dari {data.get('total')} region\n")
    return regions


def kirim_fonnte(file_path, caption, target_phone=None):
    """
    Mengirim file screenshot lokal ke WhatsApp via REST API Fonnte.
    """
    print("=== Memulai Pengiriman WhatsApp via Fonnte ===")
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
    print(f"Aplikasi: {BASE_URL}\n")

    if mode == "hourly":
        print("Menjalankan tugas: HOURLY REPORT\n")

        # Pengaman: Jalankan hanya antara jam 06:00 dan 23:00 WIB
        now_wib = get_wib_now()
        current_time_val = now_wib.hour * 100 + now_wib.minute
        if not (600 <= current_time_val <= 2300):
            print(f"Bypass: Hourly report hanya aktif antara 06:00 - 23:00 WIB (Saat ini: {now_wib.strftime('%H:%M')} WIB)")
            sys.exit(0)

        date_str = now_wib.strftime("%d/%m/%Y")
        time_str = now_wib.strftime("%H:%M")

        # Tentukan jadwal berikutnya
        if current_time_val >= 2300:
            next_schedule_str = "besok pukul 06:00 WIB"
        else:
            next_wib = now_wib + timedelta(hours=1)
            next_time_val = next_wib.hour * 100 + next_wib.minute
            if next_time_val > 2300:
                next_schedule_str = "besok pukul 06:00 WIB"
            else:
                next_schedule_str = f"pukul {next_wib.strftime('%H:%M')} WIB"

        # 1. Grafik rekap total panen per jam, hanya bila halaman penggantinya sudah ada
        if GRAFIK_URL:
            ambil_screenshot(GRAFIK_URL, "admin.jpg")
            caption_admin = (
                f"📊 [Grafik Rekap Total Panen per Jam]\n"
                f"📅 Data per: {date_str} - {time_str} WIB\n"
                f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
            )
            kirim_fonnte("admin.jpg", caption_admin)

            print("Menunggu jeda 3 detik...")
            time.sleep(3)
        else:
            print("Lewati grafik rekap: GRAFIK_URL belum diisi (halaman pengganti belum ada).\n")

        # 2. Tabel rekap per jam, dengan daftar region belum lapor dari API
        late_regions = ambil_belum_lapor("realisasi")
        ambil_screenshot(halaman_publik("rekap-cro"), "rekap_cro.jpg")

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

    elif mode == "daily_2210":
        print("Menjalankan tugas: DAILY REPORT\n")

        now_wib = get_wib_now()
        date_str = now_wib.strftime("%d/%m/%Y")

        # Tentukan apakah pengiriman jam 21:00, 22:00, atau 23:00 WIB
        current_time_val = now_wib.hour * 100 + now_wib.minute
        caption_time = now_wib.strftime("%H:%M")

        if current_time_val <= 2130:
            next_schedule = "pukul 22:00 WIB."
        elif current_time_val <= 2230:
            next_schedule = "pukul 23:00 WIB."
        else:
            next_schedule = "besok pukul 21:00 WIB."

        # Tabel rencana & estimasi, dengan daftar region belum mengisi dari API
        unfilled_plans = ambil_belum_lapor("estimasi")
        ambil_screenshot(halaman_publik("rencana-estimasi"), "table_modal.jpg")

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
