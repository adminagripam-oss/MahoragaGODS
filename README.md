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
   - **`PUBLIC_READ_TOKEN`**: Token baca halaman publik v2 dan API `/api/v1/publik/belum-lapor`.
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
     $env:PUBLIC_READ_TOKEN="TokenBacaPublikAnda"
     $env:TARGET_PHONE="120363410041245092@g.us"
     # Opsional untuk pengujian lokal:
     # $env:AGRIPAM_BASE_URL="http://localhost:5173"
     ```
   - **Linux / macOS (Bash)**:
     ```bash
     export WA_TOKEN="TokenFonnteAnda"
     export PUBLIC_READ_TOKEN="TokenBacaPublikAnda"
     export TARGET_PHONE="120363410041245092@g.us"
     # Opsional untuk pengujian lokal:
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

---

## ⏳ Jadwal Otomatis (GitHub Actions Workflows)

Proyek ini dilengkapi dengan 2 workflow otomatis:

1. **Hourly Report** (`.github/workflows/hourly_report.yml`)
   - **Jadwal (`repository_dispatch` / manual `workflow_dispatch`)**:
   - **Tugas**:
     1. Screenshot `https://agri-pam.id/publik/grafik-jam` (Grafik Rekap Total Panen per Jam; dapat dilewati jika `GRAFIK_URL=off`).
     2. Jeda 3 detik.
     3. Ambil daftar region belum lapor (`realisasi`) dari `/api/v1/publik/belum-lapor` & screenshot `https://agri-pam.id/publik/rekap-cro` (Tabel Rekap Total Panen per Jam).
     4. *(Opsional)* Screenshot `https://agri-pam.id/publik/rekap-tk-panen` ke grup khusus jika `ENABLE_TK_PANEN=true` (nonaktif by default; dapat juga dijalankan manual via `python bot.py tk_panen`).

2. **Daily Report** (`.github/workflows/daily_report.yml`)
   - **Jadwal (`repository_dispatch` / manual `workflow_dispatch`)**:
   - **Tugas**:
     1. Ambil daftar region belum mengisi rencana (`estimasi`) dari `/api/v1/publik/belum-lapor` & screenshot `https://agri-pam.id/publik/rencana-estimasi` (Tabel Rencana & Estimasi Panen).

---

## 🚀 Memicu Workflow Secara Manual (Manual Trigger)

Jika Anda ingin menjalankan bot secara langsung tanpa menunggu jadwal otomatis:

1. Buka tab **Actions** di repository GitHub Anda.
2. Di panel sebelah kiri, pilih workflow yang ingin dijalankan (**Hourly Report** atau **Daily Report**).
3. Klik dropdown **Run workflow** di sebelah kanan atas daftar eksekusi.
4. Klik tombol **Run workflow** berwarna hijau.
