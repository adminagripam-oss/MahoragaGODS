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

# ==============================================================================
# KONFIGURASI DOMAIN & TAUTAN HALAMAN
# Untuk mengganti domain utama (mis. ke http://localhost:5173 atau domain baru),
# ubah AGRIPAM_BASE_URL di .env / GitHub Repository Variables, atau ubah nilai
# default di BASE_URL bawah ini.
# ==============================================================================
BASE_URL = (os.environ.get("AGRIPAM_BASE_URL") or "").strip().rstrip("/") or "https://agri-pam.id"

# Token baca halaman publik v2 (PUBLIC_READ_TOKEN milik API). Tanpa token,
# halaman publik tidak memuat data dan endpoint belum-lapor menjawab 401.
READ_TOKEN = (os.environ.get("PUBLIC_READ_TOKEN") or "").strip()


def get_wib_now():
    """
    Mengembalikan datetime saat ini dalam zona waktu Asia/Jakarta (WIB, UTC+7).
    """
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7)))


def halaman_publik(path):
    """Alamat halaman publik v2 lengkap dengan token baca."""
    clean_path = path.lstrip("/")
    if READ_TOKEN:
        return f"{BASE_URL}/publik/{clean_path}?token={READ_TOKEN}"
    return f"{BASE_URL}/publik/{clean_path}"


def siapkan_url_halaman(env_name, default_path):
    """Ambil URL halaman dari env var atau bangun otomatis dari BASE_URL + READ_TOKEN."""
    override = (os.environ.get(env_name) or "").strip()
    if not override:
        return halaman_publik(default_path)
    if env_name == "GRAFIK_URL" and override.lower() in ("off", "none", "false", "0"):
        return override
    if READ_TOKEN and "/publik/" in override and "token=" not in override:
        sep = "&" if "?" in override else "?"
        return f"{override}{sep}token={READ_TOKEN}"
    return override


# Tautan tiap halaman publik (otomatis mengikuti BASE_URL & PUBLIC_READ_TOKEN,
# dan bisa di-override per halaman melalui environment variable jika diperlukan).
GRAFIK_URL = siapkan_url_halaman("GRAFIK_URL", "grafik-jam")
REKAP_CRO_URL = siapkan_url_halaman("REKAP_CRO_URL", "rekap-cro")
RENCANA_ESTIMASI_URL = siapkan_url_halaman("RENCANA_ESTIMASI_URL", "rencana-estimasi")
REKAP_TK_PANEN_URL = siapkan_url_halaman("REKAP_TK_PANEN_URL", "rekap-tk-panen")


def pastikan_read_token():
    """Hentikan eksekusi lebih awal jika PUBLIC_READ_TOKEN belum diisi."""
    if not READ_TOKEN:
        print("Error: 'PUBLIC_READ_TOKEN' tidak ditemukan di Environment Variables!")
        sys.exit(1)


def ambil_screenshot(url, filename, wait_selector="table tbody tr", require_selector=True):
    """
    Mengambil screenshot halaman web menggunakan Playwright (Chromium headless)
    dengan viewport 1920x1080, menunggu elemen data muncul, lalu memberi jeda render.
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
            try:
                print("Membuat halaman baru dengan viewport 1920x1080...")
                page = browser.new_page(viewport={"width": 1920, "height": 1080})

                print("Membuka URL dan menunggu load (maksimal 60 detik)...")
                response = page.goto(url, wait_until="load", timeout=60000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status} saat membuka halaman")

                # Halaman v2 mengambil datanya setelah render pertama; tunggu elemen data muncul.
                if wait_selector:
                    timeout_ms = 30000 if require_selector else 15000
                    print(f"Menunggu elemen data muncul (maksimal {timeout_ms // 1000} detik)...")
                    try:
                        page.wait_for_selector(wait_selector, timeout=timeout_ms)
                    except Exception as wait_err:
                        if require_selector:
                            raise
                        print(f"Info: Elemen '{wait_selector}' belum terdeteksi ({wait_err}); lanjut menunggu render...")

                print("Menunggu 6 detik tambahan untuk render data...")
                time.sleep(6)

                page.screenshot(path=filename, type="jpeg")
                print(f"Screenshot berhasil disimpan di: {filename}")
            finally:
                browser.close()
    except Exception as e:
        err_msg = str(e)
        if READ_TOKEN:
            err_msg = err_msg.replace(READ_TOKEN, "***")
        print(f"Error saat mengambil screenshot: {err_msg}")
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
    pastikan_read_token()

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
    wa_token = (os.environ.get("WA_TOKEN") or "").strip()
    if not target_phone:
        target_phone = (os.environ.get("TARGET_PHONE") or "").strip() or "120363410041245092@g.us"

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
            response = requests.post(url, data=payload, files=files, headers=headers, timeout=60)

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


def hitung_jadwal_hourly_berikutnya(now_wib):
    """Menentukan teks jadwal laporan hourly berikutnya."""
    current_time_val = now_wib.hour * 100 + now_wib.minute
    if current_time_val >= 2300:
        return "besok pukul 06:00 WIB"
    next_wib = now_wib + timedelta(hours=1)
    next_time_val = next_wib.hour * 100 + next_wib.minute
    if next_time_val > 2300:
        return "besok pukul 06:00 WIB"
    return f"pukul {next_wib.strftime('%H:%M')} WIB"


def jalankan_tk_panen(now_wib, next_schedule_str):
    """Mengambil screenshot Rekap TK Panen (/publik/rekap-tk-panen) dan mengirim ke grup TK."""
    pastikan_read_token()
    date_str = now_wib.strftime("%d/%m/%Y")
    time_str = now_wib.strftime("%H:%M")
    target_grup_tk = (os.environ.get("TARGET_PHONE_TK") or "").strip() or "120363425038459858@g.us"
    tk_jenis = (os.environ.get("TK_PANEN_BELUM_LAPOR_JENIS") or "").strip()

    warning_section = ""
    if tk_jenis:
        late_regions_tk = ambil_belum_lapor(tk_jenis)
        if late_regions_tk:
            warning_text_tk = "\n".join([f"🔴 {r}" for r in late_regions_tk])
        else:
            warning_text_tk = "🔴 (Semua region sudah mengisi)"
        warning_section = f"\n{warning_text_tk}\n"

    ambil_screenshot(REKAP_TK_PANEN_URL, "rekap_tk_panen.jpg")
    if warning_section:
        caption_tk = (
            f"📢 Update Regional Yang belum mengisi Ketersediaan TK Panen\n"
            f"{warning_section}\n"
            f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
        )
    else:
        caption_tk = (
            f"📢 [Rekap Ketersediaan TK Panen]\n"
            f"📅 Data per: {date_str} - {time_str} WIB\n"
            f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
        )
    kirim_fonnte("rekap_tk_panen.jpg", caption_tk, target_phone=target_grup_tk)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Argumen mode diperlukan!")
        print("Penggunaan: python bot.py [hourly|daily_2210|tk_panen]")
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

        pastikan_read_token()

        date_str = now_wib.strftime("%d/%m/%Y")
        time_str = now_wib.strftime("%H:%M")
        next_schedule_str = hitung_jadwal_hourly_berikutnya(now_wib)

        # 1. Grafik rekap total panen per jam (/publik/grafik-jam)
        if GRAFIK_URL and GRAFIK_URL.lower() not in ("off", "none", "false", "0"):
            ambil_screenshot(
                GRAFIK_URL,
                "admin.jpg",
                wait_selector=".recharts-surface, canvas, .apexcharts-canvas, table tbody tr",
                require_selector="/publik/" in GRAFIK_URL,
            )
            caption_admin = (
                f"📊 [Grafik Rekap Total Panen per Jam]\n"
                f"📅 Data per: {date_str} - {time_str} WIB\n"
                f"⏰ Laporan berikutnya dikirim otomatis {next_schedule_str}."
            )
            kirim_fonnte("admin.jpg", caption_admin)

            print("Menunggu jeda 3 detik...")
            time.sleep(3)
        else:
            print("Lewati grafik rekap: GRAFIK_URL dinonaktifkan.\n")

        # 2. Tabel rekap per jam (/publik/rekap-cro), dengan daftar region belum lapor dari API
        late_regions = ambil_belum_lapor("realisasi")
        ambil_screenshot(REKAP_CRO_URL, "rekap_cro.jpg")

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

        # 3. Rekap TK Panen (/publik/rekap-tk-panen) - opsional, aktifkan dengan ENABLE_TK_PANEN=true
        if os.environ.get("ENABLE_TK_PANEN", "").lower() in ("1", "true", "yes", "on"):
            print("Menunggu jeda 3 detik...")
            time.sleep(3)
            jalankan_tk_panen(now_wib, next_schedule_str)

    elif mode == "daily_2210":
        print("Menjalankan tugas: DAILY REPORT\n")

        pastikan_read_token()

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

        # Tabel rencana & estimasi (/publik/rencana-estimasi), dengan daftar region belum mengisi dari API
        unfilled_plans = ambil_belum_lapor("estimasi")
        ambil_screenshot(RENCANA_ESTIMASI_URL, "table_modal.jpg")

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

    elif mode == "tk_panen":
        print("Menjalankan tugas: REKAP TK PANEN\n")
        now_wib = get_wib_now()
        next_schedule_str = hitung_jadwal_hourly_berikutnya(now_wib)
        jalankan_tk_panen(now_wib, next_schedule_str)

    else:
        print(f"Error: Mode '{mode}' tidak valid.")
        print("Pilih antara 'hourly', 'daily_2210', atau 'tk_panen'.")
        sys.exit(1)
