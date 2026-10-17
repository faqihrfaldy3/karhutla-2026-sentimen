# Karhutla 2026: Analisis Sentimen Komentar YouTube

Analisis komentar publik YouTube tentang kebakaran hutan dan lahan (karhutla) Indonesia 2026, dikombinasikan dengan data dampak dari sumber resmi. Dibuat oleh [Faqih Rifaldy](https://www.linkedin.com/in/faqih-rifaldy3) sebagai bagian dari seri *Angkanya terbuka. Pantau, bandingkan, bagikan.*

## Temuan utama
- Dari sampel acak 400 komentar berlabel manual (dari 10.347 komentar bersih), **83,2% bernada negatif** (interval Wilson 95%: 79,3 sampai 86,6%).
- Model sentimen terpilih IndoBERTweet: macro-F1 0,76 (rentang 0,70 sampai 0,81), akurasi 85% pada validasi silang 5 lipatan berstrata.
- Model sasaran komentar (TF-IDF + Logistic Regression) hanya macro-F1 0,49: perlakukan sebagai perkiraan kasar.

Angka utama berasal dari sampel acak berlabel manual, bukan dari prediksi model, karena model cenderung melebihkan porsi negatif.

## Alur
1. `notebooks/01_pengumpulan_data.ipynb` + `src/collect_youtube_comments.py`: mengumpulkan komentar lewat YouTube Data API v3 (pengguna dianonimkan).
2. Pembersihan: hapus URL, mention, duplikat, komentar kurang dari 2 kata, promosi kanal (10.903 menjadi 10.347).
3. Pelabelan manual 700 komentar (400 acak, 100 kata kunci Menhut, 200 tambahan active learning untuk pelatihan). Lihat `docs/panduan_pelabelan.md`.
4. `notebooks/02_analisis_sentimen.ipynb`: TF-IDF + Logistic Regression vs IndoBERTweet, validasi silang, bootstrap, pemilihan model.

## Data
Teks komentar **tidak disertakan** untuk menghormati ketentuan YouTube API dan privasi pengguna. Yang tersedia:
- `data/labels/labels.csv`: ID komentar, ID video, label sentimen dan sasaran.
- `data/results/`: ringkasan hasil dan prediksi per komentar (tanpa teks).

Untuk mereplikasi, jalankan notebook 01 dengan API key sendiri.

## Keterbatasan
Hanya YouTube berbahasa Indonesia dari 60 video berita/opini (1 Agustus sampai 16 Oktober 2026). Bukan survei dan tidak mewakili seluruh masyarakat. Kesepakatan antar-pelabel (Cohen's kappa) belum diukur. Tren bulanan tidak boleh ditafsirkan sebagai perubahan opini karena komposisi video berubah.

## Cara menjalankan
Buka notebook di Google Colab. Simpan `YOUTUBE_API_KEY` di Colab Secrets. Jangan pernah menaruh API key di repositori.

## Sumber data dampak
SiPongi Kemenhut (via Databoks, 8 Okt 2026); Kompas.com (3 Okt 2026); Kemenkes (via iNews, 14 Okt 2026); KLH (via Katadata, 14 Okt 2026); CELIOS (via KabarBursa, 14 Okt 2026); Metro TV/Antara (18 Jun 2026); Nusantara Atlas.

## Lisensi
Kode: MIT.
