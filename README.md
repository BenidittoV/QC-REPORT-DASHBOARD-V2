# QC Dashboard Upgrade — Database + Role + Admin Page

Project ini adalah upgrade dari versi lama yang masih:
- login hardcoded
- file Excel hanya disimpan sementara / in-memory
- belum ada database
- belum ada halaman admin

## Struktur Folder

```text
qc_dashboard_db_upgrade/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── admin.py
│   │   │   ├── auth.py
│   │   │   └── dashboard.py
│   │   ├── services/
│   │   │   ├── analytics_service.py
│   │   │   ├── file_service.py
│   │   │   └── legacy_logic.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── deps.py
│   │   ├── legacy_seed.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   └── seed.py
│   ├── storage/
│   │   ├── admin/
│   │   └── manual/
│   ├── .env.example
│   ├── init_db.py
│   ├── main.py
│   ├── migrate_from_hardcoded.py
│   ├── railway.json
│   ├── render.yaml
│   └── requirements.txt
├── frontend/
│   ├── admin.html
│   ├── admin.js
│   ├── app.js
│   ├── config.example.js
│   ├── config.js
│   ├── index.html
│   ├── netlify.toml
│   ├── style.css
│   └── vercel.json
└── README.md
```

---

## Keputusan Desain yang Penting

### 1. Saya menambahkan kolom `tl_name` di tabel `users`
Secara requirement awal, tabel users hanya punya:
- id
- username
- password
- role

Masalahnya: itu **tidak cukup** untuk mengunci login TL ke nama TL yang ada di Excel.

Contoh:
- username login: `Elbina`
- nama TL di file Excel: `Elbina Debora`

Tanpa kolom `tl_name`, backend tidak punya cara yang stabil untuk tahu bahwa user `Elbina` harus dibatasi ke data `Elbina Debora`.

Karena itu, saya tambahkan:
- `tl_name` (nullable untuk admin, wajib untuk TL)

Ini bukan tambahan kosmetik. Ini kebutuhan teknis.

### 2. Tetap hanya ada 2 tabel utama
- `users`
- `files`

Jadi requirement “2 tabel utama” tetap terpenuhi.

---

## Teknologi

### Backend
- FastAPI
- SQLAlchemy
- Passlib + bcrypt
- itsdangerous (session token)
- pandas/openpyxl untuk membaca Excel

### Frontend
- HTML + CSS + JavaScript biasa
- Tema visual tetap dekat dengan style lama

### Database
- Lokal: SQLite
- Online: PostgreSQL (Neon / Supabase)

---

## Skema Database

### Table `users`
- `id`
- `username`
- `password_hash`
- `role` (`admin` / `tl`)
- `tl_name`
- `created_at`

### Table `files`
- `id`
- `file_name`
- `original_name`
- `file_path`
- `upload_date`
- `uploaded_by`
- `source_type` (`admin` / `tl_manual`)
- `is_active`

---

## Flow User

### Admin
Admin bisa:
- login ke halaman admin
- CRUD user TL
- upload file Excel admin
- rename file
- delete file

### TL
TL tidak bisa masuk admin page.

TL hanya bisa:
- pilih file dari admin lewat dropdown `Pilih Berkas / Tanggal`
- upload file manual miliknya sendiri
- lihat dashboard sesuai `tl_name` miliknya

---

## Migrasi dari Sistem Hardcoded ke Database

### Sebelum migrasi
Versi lama menyimpan:
- password user di Python
- mapping username -> TL name di Python

### Setelah migrasi
Semua itu dipindah ke database `users`.

### Langkah migrasi
1. Jalankan pembuatan database:
   ```bash
   cd backend
   python init_db.py
   ```

2. Script tersebut akan:
   - membuat tabel
   - menambahkan admin default:
     - username: `Admin`
     - password: `berijalan2154acc`
     - role: `admin`
   - memindahkan seluruh TL legacy hardcoded ke database

3. Setelah itu login **tidak lagi** membaca hardcode, tetapi membaca tabel `users`.

### Jika ingin menjalankan migrasi ulang
Gunakan:
```bash
python migrate_from_hardcoded.py
```

---

## Cara Menjalankan Lokal

## 1) Backend

Masuk ke folder backend:

```bash
cd backend
```

Buat virtual environment:

### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

### Mac/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

Copy env:

### Windows CMD
```bash
copy .env.example .env
```

### PowerShell
```powershell
Copy-Item .env.example .env
```

### Mac/Linux
```bash
cp .env.example .env
```

Inisialisasi database:

```bash
python init_db.py
```

Jalankan backend:

```bash
uvicorn main:app --reload
```

Backend aktif di:
```text
http://localhost:8000
```

Swagger docs:
```text
http://localhost:8000/docs
```

---

## 2) Frontend

Masuk ke folder frontend:

```bash
cd frontend
```

Buka `config.js`, lalu pastikan:

```javascript
window.APP_CONFIG = {
  API_BASE_URL: 'http://localhost:8000'
};
```

Lalu jalankan frontend dengan static server.

### Opsi cepat pakai Python
```bash
python -m http.server 5500
```

Akses:
```text
http://localhost:5500
```

---

## Cara Testing

## Test 1 — Login admin
Gunakan:
- username: `Admin`
- password: `berijalan2154acc`

Hasil:
- harus diarahkan ke `admin.html`

## Test 2 — Login TL
Gunakan salah satu user legacy.
Contoh:
- username: `Elbina`
- password: sesuai seed di database

Hasil:
- masuk ke halaman dashboard TL
- hanya melihat data TL yang terkunci ke `tl_name`

## Test 3 — Upload file admin
Masuk ke halaman admin:
- isi nama file
- upload Excel
- file harus muncul di tabel files
- file itu harus muncul di dropdown TL

## Test 4 — Upload manual TL
Login sebagai TL:
- upload file manual
- file itu langsung jadi file aktif
- dashboard harus memproses file tersebut

## Test 5 — CRUD user TL
Admin:
- tambah user TL baru
- edit username / password / tl_name
- hapus user selain Admin default

---

## Endpoint Utama

## Auth
- `POST /login`
- `POST /logout`
- `GET /auth/me`

## Dashboard / TL
- `GET /files/available`
- `POST /upload`
- `GET /meta`
- `POST /process`
- `GET /detail-agent`
- `GET /priority-agent-detail`

## Admin
- `GET /admin/dashboard`
- `GET /admin/users`
- `POST /admin/users`
- `PUT /admin/users/{id}`
- `DELETE /admin/users/{id}`
- `GET /admin/files`
- `POST /admin/files`
- `PUT /admin/files/{id}`
- `DELETE /admin/files/{id}`

---

## Penjelasan Database — SQLite vs PostgreSQL

## SQLite
Pakai SQLite jika:
- development lokal
- pengguna sedikit
- mau setup paling cepat

Contoh `DATABASE_URL`:
```env
DATABASE_URL=sqlite:///./app.db
```

Kelebihan:
- gratis
- tanpa instal server database
- paling cepat untuk local prototype

Kekurangan:
- tidak ideal untuk multi-user production skala serius

## PostgreSQL
Pakai PostgreSQL jika:
- online deployment
- multi-user
- butuh database production yang lebih benar

Contoh `DATABASE_URL`:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

---

## Setup PostgreSQL Gratis — Neon / Supabase

## Opsi A — Neon
1. Buat project di Neon
2. Copy connection string Postgres
3. Ganti `DATABASE_URL` di backend `.env`
4. Pastikan format untuk SQLAlchemy adalah:
   ```env
   DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
   ```

## Opsi B — Supabase
1. Buat project di Supabase
2. Ambil connection string Postgres
3. Jika string dimulai dengan `postgres://`, ubah menjadi `postgresql://` untuk SQLAlchemy
4. Paste ke `.env` sebagai `DATABASE_URL`

---

## Deploy Online — Rekomendasi Jalur yang Paling Masuk Akal

### Rekomendasi final
- Backend: Render
- Frontend: Vercel
- Database: Neon

Ini paling sederhana untuk stack HTML/JS + FastAPI + PostgreSQL.

---

## Deploy Backend ke Render

### Persiapan
Push folder project ke GitHub.

### Langkah
1. Buat Web Service baru di Render
2. Connect repository GitHub
3. Set root directory ke:
   ```text
   backend
   ```
4. Build command:
   ```text
   pip install -r requirements.txt
   ```
5. Start command:
   ```text
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. Tambahkan environment variables:
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `CORS_ORIGINS`

### Contoh nilai env
```env
SECRET_KEY=isi-random-panjang
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
CORS_ORIGINS=https://frontend-anda.vercel.app
```

### Setelah deploy
Buka:
```text
https://nama-backend-anda.onrender.com/docs
```

Kalau docs terbuka, backend sudah hidup.

---

## Deploy Backend ke Railway (alternatif)

1. Buat project baru di Railway
2. Deploy dari GitHub repo
3. Set service ke folder `backend`
4. Tambahkan env:
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `CORS_ORIGINS`
5. Railway akan build dan menjalankan:
   ```text
   uvicorn main:app --host 0.0.0.0 --port ${PORT}
   ```

---

## Deploy Frontend ke Vercel

Karena frontend ini static HTML/JS/CSS, prosesnya sederhana.

### Langkah
1. Buat project baru di Vercel
2. Import repo GitHub
3. Set Root Directory ke:
   ```text
   frontend
   ```
4. Tidak perlu build rumit
5. Deploy

### Penting
Sebelum deploy, ubah `frontend/config.js`:

```javascript
window.APP_CONFIG = {
  API_BASE_URL: 'https://nama-backend-anda.onrender.com'
};
```

Lalu commit dan push lagi.

---

## Deploy Frontend ke Netlify (alternatif)

1. Buat site baru di Netlify
2. Hubungkan ke repo
3. Set base directory:
   ```text
   frontend
   ```
4. Publish directory:
   ```text
   .
   ```
5. Deploy

Tetap ubah `config.js` agar menunjuk ke backend online.

---

## Cara Connect Frontend ↔ Backend

Kunci koneksi ada di file:

```text
frontend/config.js
```

Lokal:
```javascript
window.APP_CONFIG = {
  API_BASE_URL: 'http://localhost:8000'
};
```

Online:
```javascript
window.APP_CONFIG = {
  API_BASE_URL: 'https://nama-backend-anda.onrender.com'
};
```

Kalau frontend beda domain dengan backend, backend harus punya `CORS_ORIGINS` yang mengizinkan domain frontend.

Contoh:
```env
CORS_ORIGINS=https://frontend-anda.vercel.app
```

Kalau lebih dari satu domain:
```env
CORS_ORIGINS=https://frontend-anda.vercel.app,https://frontend-anda.netlify.app
```

---

## Catatan Keamanan

Sudah diperbaiki:
- password tidak disimpan plaintext di database
- password disimpan hashed dengan bcrypt
- role admin dan tl dipisah
- endpoint admin diproteksi role
- login tidak lagi hardcoded
- file TL tidak bisa dipakai TL lain
- TL hanya bisa pakai:
  - file admin
  - file manual miliknya sendiri

Yang masih harus Anda pahami:
- token masih model sederhana berbasis signed session token
- untuk production besar, bisa dinaikkan ke JWT + refresh token + HTTPS only cookie
- SQLite cocok untuk lokal, bukan pilihan terbaik untuk production multi-user

---

## Saran Lanjutan

Kalau project ini akan dipakai serius, langkah berikutnya seharusnya:
1. pindah penuh ke PostgreSQL
2. tambah audit log
3. tambah reset password admin
4. tambah pagination untuk tabel admin
5. tambah validasi struktur Excel sebelum file aktif dipakai
6. tambah preview file sebelum dipublikasikan ke TL

