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

# Token baca opsional untuk API privat `/api/v1/publik/belum-lapor`.
# Halaman `/publik/*` di agri-pam.id dapat diakses publik tanpa token; bila token
# kosong, daftar region belum lapor diekstrak langsung dari DOM halaman.
READ_TOKEN = (os.environ.get("PUBLIC_READ_TOKEN") or "").strip()


WIB = timezone(timedelta(hours=7))

# Ditulis tetap di sini, bukan lewat `locale`: runner GitHub tidak menjamin locale Indonesia ada.
HARI_INDO = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN_INDO = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)

# 12 slot laporan per jam (BR-07), sama persis dengan JAM_SLOTS di packages/shared.
JAM_SLOTS = (
    "06.00", "07.00", "08.00", "09.00", "10.00", "11.00",
    "12.00", "13.00", "14.00", "15.00", "16.00", "17.30",
)


def get_wib_now():
    """
    Mengembalikan datetime saat ini dalam zona waktu Asia/Jakarta (WIB, UTC+7).
    BOT_NOW ("2026-11-24T19:30", dianggap WIB) memalsukan jamnya untuk menguji caption.
    """
    palsu = (os.environ.get("BOT_NOW") or "").strip()
    if palsu:
        return datetime.fromisoformat(palsu).replace(tzinfo=WIB)
    return datetime.now(timezone.utc).astimezone(WIB)


def tanggal_iso(dt):
    """YYYY-MM-DD, bentuk yang diminta halaman publik dan API."""
    return dt.strftime("%Y-%m-%d")


def tanggal_besok(now_wib):
    """Hari berikutnya dalam WIB. Rencana panen diisi malam sebelumnya (BR-17)."""
    return now_wib + timedelta(days=1)


def format_tanggal_indo(dt):
    """Contoh: "Senin, 24 November 2026"."""
    return f"{HARI_INDO[dt.weekday()]}, {dt.day} {BULAN_INDO[dt.month - 1]} {dt.year}"


def format_waktu_indo(dt):
    """Contoh: "Senin, 24 November 2026 pukul 11.05 WIB"."""
    return f"{format_tanggal_indo(dt)} pukul {dt.strftime('%H.%M')} WIB"


def slot_jatuh_tempo(now_wib):
    """
    Slot jam yang seharusnya sudah dilaporkan sekarang: satu jam ke belakang, jadi pukul
    11.xx memeriksa slot 10.00 dan 18.xx memeriksa 17.30. Di luar 07.00-18.00 WIB belum ada
    yang jatuh tempo. Cermin dari slotDue() di packages/shared/src/publik.ts.
    """
    jam = now_wib.hour
    if 7 <= jam <= 18:
        return JAM_SLOTS[jam - 7]
    return None


def dengan_tanggal(url, tanggal):
    """
    Menempelkan ?tanggal= pada URL halaman, menghormati query string yang sudah ada
    (siapkan_url_halaman bisa sudah menaruh ?token= di sana). Tanggal yang sudah dipatok di
    URL dibiarkan: itu pilihan sadar pemilik lewat repository variable, dan menimpanya
    diam-diam lebih berbahaya daripada mencatatnya di log.
    """
    if "tanggal=" in url:
        print("Info: URL halaman sudah memuat tanggal; nilai itu dipakai apa adanya.")
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}tanggal={tanggal}"


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


def ambil_screenshot(
    url,
    filename,
    wait_selector="table tbody tr",
    require_selector=True,
    extract_selector=None,
):
    """
    Mengambil screenshot halaman web menggunakan Playwright (Chromium headless)
    dengan viewport 1920x1080, menunggu elemen data muncul, lalu memberi jeda render.
    Jika `extract_selector` diberikan, mengekstrak daftar teks region unik dari DOM.
    """
    print("=== Memulai Proses Screenshot ===")
    # Token tidak ikut dicetak ke log.
    print(f"URL     : {url.split('?')[0]}")
    print(f"Output  : {filename}")

    start_time = time.time()
    extracted = []

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

                if extract_selector:
                    try:
                        raw_texts = page.locator(extract_selector).all_inner_texts()
                        cleaned_items = []
                        for txt in raw_texts:
                            cleaned = txt.strip().lstrip("◯✓").strip()
                            if cleaned:
                                cleaned_items.append(cleaned)
                        extracted = list(dict.fromkeys(cleaned_items))
                    except Exception as extract_err:
                        print(f"Info: Gagal membaca daftar region dari DOM ({extract_err}); lanjut dengan fallback.")

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
    return extracted


def ambil_belum_lapor(
    jenis, tanggal=None, fallback_regions=None, jam_fallback=None, dom_tersedia=True
):
    """
    Mengambil daftar region yang belum melapor dari API v2 bila PUBLIC_READ_TOKEN tersedia,
    dan otomatis fallback ke hasil ekstraksi DOM (`fallback_regions`) bila token kosong
    atau endpoint API privat menolak/gagal.

    Mengembalikan {"jam": slot | None, "regions": [...], "terbaca": bool}. `terbaca` False
    berarti daftarnya gagal dibaca, bukan bahwa semua sudah mengisi; caption harus
    membedakan keduanya. `jam_fallback` dipakai saat jawaban API tidak ada, dan
    `dom_tersedia` False untuk pemanggil yang tidak mengais DOM sama sekali (Rekap TK Panen),
    sehingga daftar kosongnya tidak disalahartikan sebagai "semua sudah mengisi".
    """
    print(f"=== Mengambil daftar region belum lapor ({jenis}) ===")
    if tanggal:
        print(f"Tanggal        : {tanggal}")
    if not READ_TOKEN:
        regions = list(fallback_regions or [])
        print("Info: 'PUBLIC_READ_TOKEN' tidak diisi; menggunakan hasil ekstraksi DOM halaman publik.")
        print(f"Belum lapor (DOM): {len(regions)} region\n")
        return {"jam": jam_fallback, "regions": regions, "terbaca": dom_tersedia}

    url = f"{BASE_URL}/api/v1/publik/belum-lapor"
    params = {"jenis": jenis}
    if tanggal:
        params["tanggal"] = tanggal

    def _fallback_atau_henti(pesan_error):
        if fallback_regions is not None:
            print(f"Info: {pesan_error}. Memakai hasil ekstraksi DOM ({len(fallback_regions)} region).\n")
            return {"jam": jam_fallback, "regions": list(fallback_regions), "terbaca": dom_tersedia}
        print(pesan_error)
        sys.exit(1)

    try:
        response = requests.get(
            url, params=params, headers={"X-Read-Token": READ_TOKEN}, timeout=30
        )
    except Exception as e:
        return _fallback_atau_henti(f"Error saat menghubungi API belum-lapor: {e}")

    if response.status_code != 200:
        return _fallback_atau_henti(f"Gagal membaca daftar belum lapor. HTTP {response.status_code}: {response.text}")

    try:
        data = response.json()
    except Exception:
        return _fallback_atau_henti(f"Jawaban API bukan JSON: {response.text}")

    regions = data.get("regions")
    if not isinstance(regions, list):
        return _fallback_atau_henti(f"Jawaban API tidak sesuai dugaan: {response.text}")

    jam = data.get("jam")
    if jenis == "realisasi" and jam_fallback is not None and jam != jam_fallback:
        # Server menurunkan `jam` dari jam yang sama dengan yang dipakainya menyaring data,
        # jadi menamai daftar ini dengan slot hitungan lokal akan salah saat menit berganti.
        print(f"Info: slot dari API ({jam}) berbeda dari hitungan lokal ({jam_fallback}); caption memakai nilai API.")
    print(f"Slot diperiksa : {jam}")
    print(f"Belum lapor    : {len(regions)} dari {data.get('total')} region\n")
    return {"jam": jam, "regions": regions, "terbaca": True}


def kirim_fonnte(file_path, caption, target_phone=None):
    """
    Mengirim file screenshot lokal ke WhatsApp via REST API Fonnte.
    """
    print("=== Memulai Pengiriman WhatsApp via Fonnte ===")
    wa_token = (os.environ.get("WA_TOKEN") or "").strip()
    if not target_phone:
        target_phone = (os.environ.get("TARGET_PHONE") or "").strip() or "120363410041245092@g.us"

    # Diperiksa sebelum WA_TOKEN: tanpa ini caption tidak pernah sempat tercetak saat diuji,
    # karena skrip berhenti lebih dulu pada token yang kosong.
    if (os.environ.get("DRY_RUN") or "").strip().lower() in ("1", "true", "yes", "on"):
        ukuran = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        print("--- DRY RUN, tidak ada yang dikirim ---")
        print(f"Target : {target_phone}")
        print(f"Berkas : {file_path} ({ukuran // 1024} KB)")
        print(f"Caption:\n{caption}")
        print("--------------------------------------\n")
        return

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
    """
    Teks jadwal laporan hourly berikutnya. Menitnya dibulatkan ke awal jam karena cron
    memicu pada awal jam, bukan pada menit bot ini kebetulan jalan.
    """
    current_time_val = now_wib.hour * 100 + now_wib.minute
    if current_time_val >= 2300:
        return "besok pukul 06.00 WIB"
    next_wib = now_wib + timedelta(hours=1)
    next_time_val = next_wib.hour * 100 + next_wib.minute
    if next_time_val > 2300:
        return "besok pukul 06.00 WIB"
    return f"pukul {next_wib.strftime('%H')}.00 WIB"


def jalankan_tk_panen(now_wib, next_schedule_str):
    """Mengambil screenshot Rekap TK Panen (/publik/rekap-tk-panen) dan mengirim ke grup TK."""
    waktu_str = format_waktu_indo(now_wib)
    target_grup_tk = (os.environ.get("TARGET_PHONE_TK") or "").strip() or "120363425038459858@g.us"
    tk_jenis = (os.environ.get("TK_PANEN_BELUM_LAPOR_JENIS") or "").strip()

    # Halaman ini tidak menerima ?tanggal=, jadi selalu hari ini.
    ambil_screenshot(REKAP_TK_PANEN_URL, "rekap_tk_panen.jpg")

    blok = ""
    if tk_jenis:
        # dom_tersedia=False: tidak ada pengaisan DOM di sini, jadi daftar kosong dari API yang
        # gagal berarti "tidak terbaca", bukan "semua sudah mengisi".
        hasil = ambil_belum_lapor(tk_jenis, fallback_regions=[], dom_tersedia=False)
        if not hasil["terbaca"]:
            blok = "\nDaftar regional yang belum mengisi tidak dapat dibaca kali ini.\n"
        elif hasil["regions"]:
            daftar = "\n".join(f"- {r}" for r in hasil["regions"])
            blok = f"\nRegional yang belum mengisi ketersediaan TK panen:\n{daftar}\n"
        else:
            blok = "\nSemua regional sudah mengisi ketersediaan TK panen.\n"

    caption_tk = (
        f"*Rekap Ketersediaan TK Panen*\n"
        f"Data per {waktu_str}.\n"
        f"{blok}"
        f"Bot mengirim laporan berikutnya {next_schedule_str}."
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

        waktu_str = format_waktu_indo(now_wib)
        slot_lokal = slot_jatuh_tempo(now_wib)
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
                f"*Grafik Rekap Total Panen per Jam*\n"
                f"Data per {waktu_str}.\n"
                f"Bot mengirim laporan berikutnya {next_schedule_str}."
            )
            kirim_fonnte("admin.jpg", caption_admin)

            print("Menunggu jeda 3 detik...")
            time.sleep(3)
        else:
            print("Lewati grafik rekap: GRAFIK_URL dinonaktifkan.\n")

        # 2. Tabel rekap per jam (/publik/rekap-cro), dengan daftar region belum lapor dari API/DOM
        dom_late_regions = ambil_screenshot(
            REKAP_CRO_URL,
            "rekap_cro.jpg",
            extract_selector="[data-belum-lapor]",
        )
        hasil_cro = ambil_belum_lapor(
            "realisasi", fallback_regions=dom_late_regions, jam_fallback=slot_lokal
        )
        slot = hasil_cro["jam"]

        # Bercabang pada ada-tidaknya slot, bukan pada daftar yang kosong: mode ini jalan
        # 06.00-23.00 WIB sedangkan slot baru jatuh tempo 07.00-18.00, jadi di luar itu daftar
        # selalu kosong dan "semua sudah mengisi" akan menjadi kabar yang keliru.
        if slot is None:
            blok = "Belum ada jam laporan yang jatuh tempo."
        elif not hasil_cro["terbaca"]:
            blok = f"Daftar regional yang belum melaporkan slot jam {slot} tidak dapat dibaca kali ini."
        elif hasil_cro["regions"]:
            daftar = "\n".join(f"- {r}" for r in hasil_cro["regions"])
            blok = f"Regional yang belum melaporkan slot jam {slot}:\n{daftar}"
        else:
            blok = f"Semua regional sudah melaporkan slot jam {slot}."

        caption_cro = (
            f"*Tabel Rekap Total Panen per Jam*\n"
            f"Data per {waktu_str}.\n\n"
            f"{blok}\n\n"
            f"Bot mengirim laporan berikutnya {next_schedule_str}."
        )
        kirim_fonnte("rekap_cro.jpg", caption_cro)

        # 3. Rekap TK Panen (/publik/rekap-tk-panen) - opsional, aktifkan dengan ENABLE_TK_PANEN=true
        if os.environ.get("ENABLE_TK_PANEN", "").lower() in ("1", "true", "yes", "on"):
            print("Menunggu jeda 3 detik...")
            time.sleep(3)
            jalankan_tk_panen(now_wib, next_schedule_str)

    elif mode == "daily_2210":
        print("Menjalankan tugas: DAILY REPORT\n")

        now_wib = get_wib_now()
        waktu_str = format_waktu_indo(now_wib)

        # Laporan malam ini mengingatkan regional mengisi rencana panen HARI BERIKUTNYA, jadi
        # gambar dan daftarnya memakai tanggal besok (BR-17: server menerima estimasi untuk
        # hari ini dan besok). Satu variabel dipakai keduanya supaya tidak mungkin berbeda hari.
        besok = tanggal_besok(now_wib)
        besok_iso = tanggal_iso(besok)
        besok_str = format_tanggal_indo(besok)
        print(f"Rencana yang dilaporkan: {besok_str} ({besok_iso})\n")

        # Tentukan apakah pengiriman jam 21.00, 22.00, atau 23.00 WIB
        current_time_val = now_wib.hour * 100 + now_wib.minute
        if current_time_val <= 2130:
            next_schedule = "pukul 22.00 WIB"
        elif current_time_val <= 2230:
            next_schedule = "pukul 23.00 WIB"
        else:
            next_schedule = "besok pukul 21.00 WIB"

        # Tabel rencana & estimasi (/publik/rencana-estimasi), dengan daftar region belum mengisi dari API/DOM
        dom_unfilled_plans = ambil_screenshot(
            dengan_tanggal(RENCANA_ESTIMASI_URL, besok_iso),
            "table_modal.jpg",
            extract_selector="[data-belum-isi]",
        )
        hasil_rencana = ambil_belum_lapor(
            "estimasi", tanggal=besok_iso, fallback_regions=dom_unfilled_plans
        )

        if not hasil_rencana["terbaca"]:
            blok = f"Daftar regional yang belum mengisi rencana panen {besok_str} tidak dapat dibaca kali ini."
        elif hasil_rencana["regions"]:
            daftar = "\n".join(f"- {r}" for r in hasil_rencana["regions"])
            blok = f"Regional yang belum mengisi rencana panen {besok_str}:\n{daftar}"
        else:
            blok = f"Semua regional sudah mengisi rencana panen {besok_str}."

        # Tanggalnya ditulis lengkap, bukan kata "besok", supaya pesan tetap benar bila dibaca
        # setelah tengah malam.
        caption_daily = (
            f"*Tabel Rencana & Estimasi Panen*\n"
            f"Rencana panen untuk {besok_str}.\n"
            f"Data per {waktu_str}.\n\n"
            f"{blok}\n\n"
            f"Bot mengirim laporan berikutnya {next_schedule}."
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
