# 📊 Web Screenshot & WhatsApp Automation Bot

Bot otomatis berbasis Python yang berfungsi untuk mengambil screenshot halaman web menggunakan **Playwright** dan mengirimkannya ke WhatsApp melalui **Fonnte API**. Proyek ini dikonfigurasi untuk berjalan secara terjadwal maupun manual menggunakan **GitHub Actions**.

---

## 🛠️ Persyaratan Sistem

- Python 3.10+
- Token Fonnte (dapat diperoleh dari dashboard [Fonnte](https://fonnte.com))
- Target WhatsApp (Nomor HP atau ID Grup)

---

## ⚙️ Konfigurasi Environment & Secrets

### 🔑 1. Setup GitHub Repository Secrets (Untuk GitHub Actions)
Agar bot dapat berjalan otomatis di GitHub Actions, Anda perlu menambahkan kredensial berikut ke **Secrets** repository GitHub Anda:

1. Masuk ke repository GitHub Anda.
2. Buka menu **Settings** > **Secrets and variables** > **Actions**.
3. Klik tombol **New repository secret**.
4. Tambahkan secrets berikut:
   - **`WA_TOKEN`**: API Token dari Fonnte Anda.
   - **`PUBLIC_READ_TOKEN`** (opsional): Token baca API privat `/api/v1/publik/belum-lapor`. Halaman `/publik/*` dapat diakses tanpa login/token; jika secret ini kosong, bot otomatis membaca daftar region belum lapor dari hasil render DOM halaman.
   - **`TARGET_PHONE`** (opsional): Target ID WhatsApp (nomor telepon dengan kode negara atau ID grup). Jika dikosongkan, bot akan menggunakan fallback default grup `120363410041245092@g.us`.
   - **`TARGET_PHONE_TK`** (opsional): Target ID grup khusus Rekap TK Panen (default: `120363425038459858@g.us`).

### 🌐 Mengganti Domain atau Link Halaman
Untuk mengganti nama domain utama (misalnya ke `http://localhost:5173` atau domain baru):
- **Via GitHub Actions**: Buka **Settings** > **Secrets and variables** > **Actions** > tab **Variables**, lalu atur variabel **`AGRIPAM_BASE_URL`** (default: `https://agri-pam.id`).
- **Via Lokal / VPS**: Ubah `AGRIPAM_BASE_URL` di file `.env` (lihat `.env.example`), atau ubah default `BASE_URL` di bagian atas `bot.py`.
- Untuk mengubah tautan halaman tertentu saja, lihat konstanta `GRAFIK_URL`, `REKAP_CRO_URL`, `RENCANA_ESTIMASI_URL`, dan `REKAP_TK_PANEN_URL` di bagian atas `bot.py` (masing-masing juga bisa di-override melalui environment variable).

### 💻 2. Setup Pengujian Lokal (Local Testing)
Untuk menjalankan script secara lokal, ikuti langkah-langkah berikut:

1. **Clone repository ini** ke komputer Anda.
2. **Buat Virtual Environment** (opsional tapi direkomendasikan):
   ```bash
   python -m venv .venv
   # Aktifkan virtual environment
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
3. **Install Dependensi**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
4. **Set Environment Variables** sebelum menjalankan script (atau salin `.env.example` menjadi `.env`):
   - **Windows (PowerShell)**:
     ```powershell
     $env:WA_TOKEN="TokenFonnteAnda"
     $env:TARGET_PHONE="120363410041245092@g.us"
     # Opsional:
     # $env:PUBLIC_READ_TOKEN="TokenBacaPublikAnda"
     # $env:AGRIPAM_BASE_URL="http://localhost:5173"
     ```
   - **Linux / macOS (Bash)**:
     ```bash
     export WA_TOKEN="TokenFonnteAnda"
     export TARGET_PHONE="120363410041245092@g.us"
     # Opsional:
     # export PUBLIC_READ_TOKEN="TokenBacaPublikAnda"
     # export AGRIPAM_BASE_URL="http://localhost:5173"
     ```
5. **Jalankan Script**:
   - Untuk laporan per jam:
     ```bash
     python bot.py hourly
     ```
   - Untuk laporan harian (Rencana & Estimasi):
     ```bash
     python bot.py daily_2210
     ```
   - Untuk laporan Rekap TK Panen secara manual:
     ```bash
     python bot.py tk_panen
     ```

6. **Mencoba tanpa mengirim ke grup**. Dua variabel khusus pengujian, keduanya mati bila tidak diisi:
   - `DRY_RUN=1` mencetak target, berkas, dan caption utuh ke layar lalu berhenti sebelum memanggil Fonnte. Tidak perlu `WA_TOKEN`.
   - `BOT_NOW=2026-11-24T19:30` memalsukan jam (dianggap WIB), supaya ketiga cabang caption rekap-cro bisa dilihat tanpa menunggu jamnya.

   ```bash
   DRY_RUN=1 BOT_NOW=2026-11-24T11:05 AGRIPAM_BASE_URL=http://localhost:5173 python bot.py hourly
   DRY_RUN=1 BOT_NOW=2026-11-24T22:05 AGRIPAM_BASE_URL=http://localhost:5173 python bot.py daily_2210
   ```

   Untuk mencoba pengiriman sungguhan, arahkan `TARGET_PHONE` ke nomor WhatsApp penguji, bukan ke id grup.

---

## ⏳ Jadwal Otomatis (GitHub Actions Workflows)

Proyek ini dilengkapi dengan 2 workflow otomatis:

1. **Hourly Report** (`.github/workflows/hourly_report.yml`)
   - **Jadwal (`repository_dispatch` / manual `workflow_dispatch`)**: tiap jam, 06.00 sampai 23.00 WIB. Di luar rentang itu `bot.py hourly` keluar diam-diam dengan kode 0.
   - **Tugas**:
     1. Screenshot `https://agri-pam.id/publik/grafik-jam` (Grafik Rekap Total Panen per Jam; dapat dilewati jika `GRAFIK_URL=off`).
     2. Jeda 3 detik.
     3. Ambil daftar region belum lapor (`realisasi`) dari `/api/v1/publik/belum-lapor` & screenshot `https://agri-pam.id/publik/rekap-cro` (Tabel Rekap Total Panen per Jam).
     4. *(Opsional)* Screenshot `https://agri-pam.id/publik/rekap-tk-panen` ke grup khusus jika `ENABLE_TK_PANEN=true` (nonaktif by default; dapat juga dijalankan manual via `python bot.py tk_panen`).
   - **Slot jam dalam caption**: caption menyebut slot yang sedang dipantau, diambil dari `jam` pada jawaban API. Slot jatuh tempo satu jam ke belakang, jadi pukul 11.xx memeriksa slot 10.00 dan 18.xx memeriksa 17.30. Di luar 07.00 sampai 18.00 WIB belum ada slot yang jatuh tempo, dan caption menulis "Belum ada jam laporan yang jatuh tempo." alih-alih mengaku semua regional sudah mengisi.

2. **Daily Report** (`.github/workflows/daily_report.yml`)
   - **Jadwal (`repository_dispatch` / manual `workflow_dispatch`)**: pukul 21.00, 22.00, dan 23.00 WIB.
   - **Tugas**:
     1. Ambil daftar region belum mengisi rencana (`estimasi`) dari `/api/v1/publik/belum-lapor` & screenshot `https://agri-pam.id/publik/rencana-estimasi` (Tabel Rencana & Estimasi Panen).
   - **Melaporkan H+1**: laporan malam ini mengingatkan regional mengisi rencana panen **hari berikutnya**, jadi screenshot dan daftar "belum mengisi" memakai tanggal besok (`?tanggal=`). Karena itu `RENCANA_ESTIMASI_URL` tidak boleh memuat `tanggal=`; bila dipatok di sana, nilai itulah yang dipakai dan bot hanya mencatatnya di log.

---

## 🚀 Memicu Workflow Secara Manual (Manual Trigger)

Jika Anda ingin menjalankan bot secara langsung tanpa menunggu jadwal otomatis:

1. Buka tab **Actions** di repository GitHub Anda.
2. Di panel sebelah kiri, pilih workflow yang ingin dijalankan (**Hourly Report** atau **Daily Report**).
3. Klik dropdown **Run workflow** di sebelah kanan atas daftar eksekusi.
4. Klik tombol **Run workflow** berwarna hijau.
