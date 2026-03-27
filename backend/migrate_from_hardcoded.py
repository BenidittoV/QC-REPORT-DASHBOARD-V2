"""
Migrasi dari auth hardcoded ke database.

Yang dilakukan script ini:
1. Membuat tabel jika belum ada
2. Menambahkan user Admin default
3. Memindahkan seluruh TL legacy hardcoded ke tabel users
"""

from init_db import main

if __name__ == "__main__":
    main()
