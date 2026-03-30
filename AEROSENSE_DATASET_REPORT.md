# AeroSense Dataset Report (aerosense_train_40k)

Bu rapor, `data/models/aerosense_train_40k.csv` veri setine yaptığın doğrulama kontrollerini ve ilk eğitim/smoke test sonuçlarını özetler.

## 1) Dosya / Şema

- Dosya: `data/models/aerosense_train_40k.csv`
- Sütunlar: `sicaklik, mq7, mq135, toz`
- Satır sayısı: `40,000`
- Sütun sayısı: `4`

## 2) Veri Temizliği Kontrolleri

- NaN sayısı:
  - `sicaklik: 0`
  - `mq7: 0`
  - `mq135: 0`
  - `toz: 0`
- Negatif değer var mı? `Hayır`
  - `sicaklik < 0`: False
  - `mq7 < 0`: False
  - `mq135 < 0`: False
  - `toz < 0`: False

### Min / Max

| Kolon | Min | Max |
|---|---:|---:|
| `sicaklik` | 0.199585 | 45.878129 |
| `mq7` | 0.000060 | 0.119656 |
| `mq135` | 0.00013 | 14.79000 |
| `toz` | 0.00050 | 2.31366 |

## 3) AQI Sınıf Dağılımı (0-5)

Etiketler, uygulamadaki gibi şu dönüşümlerle türetiliyor:
- `co_ppm_est = mq7 * 100`
- `nox_ppm_est = mq135 * 100`
- `pm25_est = toz * 50`
- `aqi = rule_based_aqi_index(estimates)`

Sınıf dağılımı:

- `0`: 627
- `1`: 9,584
- `2`: 14,515
- `3`: 11,459
- `4`: 1,871
- `5`: 1,944

Yorum: Tek bir sınıfa aşırı yığılma yok; özellikle `1-3` bantları baskın, `0,4,5` sınıfları da var. Bu etiket üretiminin mantıklı çalıştığını gösterir.

## 4) Türetilmiş Değerler (Percentiles) — Örnek Üzerinden

`data/models/aerosense_train_40k.csv` içinden `n=20000` örnek alınarak `raw_to_estimates` ile türetilen değerlerin percentiles(1/5/50/95/99) sonuçları:

- `co_ppm_est`:
  - 1%: 0.22381395
  - 5%: 0.4
  - 50%: 0.881
  - 95%: 3.3
  - 99%: 5.5
- `nox_ppm_est`:
  - 1%: 3.32267941
  - 5%: 11.12231338
  - 50%: 38.25009636
  - 95%: 402.3041072
  - 99%: 734.36390513
- `pm25_est`:
  - 1%: 0.43755153
  - 5%: 0.65795
  - 50%: 31.1785
  - 95%: 66.80564253
  - 99%: 79.88500602
- `temp_c`:
  - 1%: 4.1
  - 5%: 6.2
  - 50%: 20.036
  - 95%: 36.26308606
  - 99%: 37.9

Yorum (özet):
- `nox_ppm_est` dağılımı kuyrukta çok yükseliyor (95% ve üstü yüzdeliklerde yüzlerce ppm).
- Bu durum, kural motorunda bazı örneklerin daha yüksek AQI sınıflarına gitmesine katkı verir.
- `co_ppm_est` ise üst bantlarda daha sınırlı kalıyor; dolayısıyla CO çoğu örnekte ana itici olmayabilir.

## 5) Smoke Test (Model Eğitimi)

Smoke amacıyla `aerosense_train_smoke.csv` oluşturuldu:

- Dosya: `data/models/aerosense_train_smoke.csv`
- Satır: `8000`
- Komut:

```bash
python3 scripts/train_model.py --csv data/models/aerosense_train_smoke.csv --format aerosense
```

Smoke test çıktısı:
- `AQI siniflandirici dogruluk: 0.9981`
- `Ozellikler: ['sicaklik', 'mq7', 'mq135', 'toz']`
- `Kaydedildi: /home/karotum/AIRQUALITY-AI/data/models/aerosense_model.joblib`
- `Anomali: /home/karotum/AIRQUALITY-AI/data/models/anomaly_iforest.joblib`

Yorum:
- Bu doğruluk çok yüksek görünüyor; burada etiketler zaten `rule_based_aqi_index` ile aynı feature-türetilmiş değerlerden üretildiği için “kendini etiketleyen” bir öğrenme senaryosu var.
- Ayrıca augmentation tarafında `replace=True` kullanıldığı için benzer örneklerin train/test ayrımı öncesi/sonrası yanlış yönetilirse leakage oluşabilir.

## 6) Overfit/Ezber Riskini Azaltma (Öneri)

En doğru yaklaşım:
1. Önce `combined_df` içinden **train/test split** yap.
2. **Augmentation sadece train tarafında** uygulanacak.
3. Aug’suz `test` ile gerçek genelleme kontrolü yapılacak (holdout).

Bu adımı yapmak istersen, mevcut dataset oluşturma kodunu senin akışına göre (train/test öncesi augmentation kaldırarak) tek parça güncelleyip yine dosya üretecek şekilde düzenleyebiliriz.

## 7) Bir Sonraki Adım (Pratik)

1. `aerosense_train_40k.csv` tam eğitimini yaptıktan sonra:
   - `curl -X POST http://127.0.0.1:38471/api/model/reload`
2. Modelin “confidence=72 sabit” kalıp kalmadığını gözlemle (72 sabit kalmamalı).
3. Mümkünse holdout ile performans ölçümü ekle.

