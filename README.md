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
   - **`TARGET_PHONE`**: Target ID WhatsApp (nomor telepon dengan kode negara atau ID grup, contoh: `628123456789` atau `120363431116867451@g.us`). Jika dikosongkan, bot akan otomatis menggunakan fallback default grup `120363431116867451@g.us`.

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
4. **Set Environment Variables** sebelum menjalankan script:
   - **Windows (PowerShell)**:
     ```powershell
     $env:WA_TOKEN="TokenFonnteAnda"
     $env:TARGET_PHONE="120363431116867451@g.us"
     ```
   - **Linux / macOS (Bash)**:
     ```bash
     export WA_TOKEN="TokenFonnteAnda"
     export TARGET_PHONE="120363431116867451@g.us"
     ```
5. **Jalankan Script**:
   - Untuk laporan per jam:
     ```bash
     python bot.py hourly
     ```
   - Untuk laporan harian pukul 22:10 WIB:
     ```bash
     python bot.py daily_2210
     ```

---

## ⏳ Jadwal Otomatis (GitHub Actions Workflows)

Proyek ini dilengkapi dengan 2 workflow otomatis:

1. **Hourly Report** (`.github/workflows/hourly_report.yml`)
   - **Jadwal (Cron)**: Setiap jam tepat (`0 * * * *`).
   - **Tugas**:
     1. Screenshot `https://agri-pam.id/admin-screenshot.html` (dikirim dengan caption: *Update Laporan Per Jam (Admin)*).
     2. Jeda 3 detik.
     3. Screenshot `https://agri-pam.id/rekap-cro-fullscreen.html` (dikirim dengan caption: *Update Laporan Per Jam (Rekap CRO)*).
     4. Jeda 3 detik.
     5. Screenshot `https://agri-pam.id/rekap_tk_panen.html` (dikirim ke grup khusus `120363425038459858@g.us` dengan caption: *Update Regional Yang belum mengisi Ketersediaan TK Panen*).

2. **Daily Report** (`.github/workflows/daily_report.yml`)
   - **Jadwal (Cron)**: Setiap hari pukul 22:10 WIB / 15:10 UTC (`10 15 * * *`).
   - **Tugas**:
     1. Screenshot `https://agri-pam.id/table-modal-fullscreen.html` (dikirim dengan caption: *Laporan Harian (Table Modal) - 22:10 WIB*).

---

## 🚀 Memicu Workflow Secara Manual (Manual Trigger)

Jika Anda ingin menjalankan bot secara langsung tanpa menunggu jadwal otomatis:

1. Buka tab **Actions** di repository GitHub Anda.
2. Di panel sebelah kiri, pilih workflow yang ingin dijalankan (**Hourly Report** atau **Daily Report**).
3. Klik dropdown **Run workflow** di sebelah kanan atas daftar eksekusi.
4. Klik tombol **Run workflow** berwarna hijau.
