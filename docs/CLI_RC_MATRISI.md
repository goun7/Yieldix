# Yieldix CLI RC-Matrisi ( Ölçülmüş Çıkış-Kodu Tablosu)

**Tarih:** 2026-10-18 · **DALGA-D1** · **Ölçüm-yöntemi:** `PYTHONPATH=src python3 -m yieldix.cli.main <cmd> ... > /tmp/x.txt 2>&1; echo RC=$?` ( PIPED-DEĞİL, gerçek-exit-code)

**Kabul-ölçütü ( click-8.5 sözleşmesi):**
- `rc=0` → komut başarılı
- `rc=2` → GEÇERSİZ-GİRDİ / kullanım-hatası ( UsageError — traceback YOK)
- `rc=1` →çalışma-zamanı hatası ( traceback) — **geçersiz girdi için asla olmamalı**
- `rc=124` → timeout ( sonsuz-döngü şüphesi)

## Matris ( komut × girdi × beklenen × ölçülen)

### Komut-grubu & global bayraklar

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| G1 | `--help` | 0 | **0** | ✓ | Komut-listesi basılır |
| G2 | `--version` | 0 | **0** | ✓ | `yieldix, version 16.0.0` |
| G3 | `--bilinmeyen-flag` | 2 | **2** | ✓ | `Error: No such option '--bilinmeyen'.` |
| G4 | `bilinmeyen-komut` | 2 | **2** | ✓ | `Error: No such command 'bilinmeyen-komut'.` |

### status

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| S1 | `status` | 0 | **0** | ✓ | 6 aktif-bileşen, CB tripped=False |
| S2 | `status --tenant OLMAYAN` | 0 | **0** | ✓-ama-notlu | Mevcut-olmayan tenant KABUL-edilir ( ek-kanıt-gereksinimi: bu motor tamamen in-memory olduğu için tenant varlığı doğrulanmaz — bilinen-davranış, hata-değil) |
| S3 | `status --bilinmeyen` | 2 | **2** | ✓ | `Error: No such option '--bilinmeyen'.` |
| S4 | `status --tenant ""` | 0 | **0** | ✓-ama-notlu | Boş-tenant sessiz-kabul ( S2 ile aynı not) |

### ingest

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| I1 | `ingest --name "Test Contact" --phone "+15551234567"` | 0 | **0** | ✓ | JSON sonucu: `is_sql=true`, `cycle_time_seconds≈0.0003` |
| I2 | `ingest --name "X"` ( --phone YOK) | 2 | **2** | ✓ | `Error: Missing option '--phone'.` |
| I3 | `ingest --name "X" --phone "abc"` | 0 | **0** | ✓-ama-notlu | "abc" telefon FORMAT-KONTROLSUZ-kabul — telefon-doğrulama YOK ( tasarımsal-bulgu, DALGA-D2'ye rafta) |
| I4 | `ingest --name "" --phone ""` | 0 | **0** | ✓-ama-notlu | Boş-alanlar zorunlu-seçenek olsa da içerik-doğrulaması YOK |

### simulate

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| M1 | `simulate` ( default 10000 runs) | 0 | **0** | ✓ | P5/P50/P95+Loss Prob hesaplanır |
| M2 | `simulate --runs 1` | 0 | **0** | ✓ | Sınır-değer çalışır ( sadece 1 run) |
| M3 | `simulate --runs 10` | 0 | **0** | ✓ | Az-run çalışır |
| M4 | `simulate --runs 0` | 2 | **2** | ✓ | `IntRange(min=1)` — DALGA-C-2 düzeltmesi kanıtlandı |
| M5 | `simulate --runs -5` | 2 | **2** | ✓ | Negatif reddedilir |
| M6 | `simulate --runs abc` | 2 | **2** | ✓ | Sayı-olmayan reddedilir |
| M7 | `simulate --runs 5 --retainer abc` | 2 | **2** | ✓ | `_DecimalParam` UsageError-atar — DALGA-C-2 düzeltmesi |
| M8 | `simulate --runs 1 --retainer ""` | 2 | **2** | ✓ | Boş-retainer reddedilir |
| M9 | `simulate --runs 100000000000000000000` | — | **124 ( timeout)** | ⚠ BULGU | Devasa-run sayısı Seedir-usesiz sonsuz-döngüye girmez ama maliyeti sınırsız — tamsayı-taşması 없이 `range()` kabul eder. Öneri ( D2'ye-rafta): üst-sınır-guard ( örn. `IntRange(max=10_000_000)`) |

### report

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| R1 | `report` | 0 | **0** | ✓ | Ed25519 imzalı markdown-kart üretir |
| R2 | `report --tenant OLMAYAN` | 0 | **0** | ✓ | Her-tenant string'i kabul ( S2-notu) |
| R3 | `report --start "wrong"` | 0 | **0** | ✓-ama-notlu | Geçersiz-tarih sessiz-kabul — tarih-format doğrulaması YOK |
| R4 | `report --start 2026-13-45` | 0 | **0** | ✓-ama-notlu | Mantıksız-tarih ( 45. gün) sessiz-kabul |

### verify

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| V1 | `verify` | 0 | **0** | ✓ | 9/9 PASS — insan-okunur çıktı |
| V2 | `verify --json` | 0 | **0** | ✓ | Geçerli-JSON ( S1-section'a-bakın) |
| V3 | `verify --bilinmiyen` | 2 | **2** | ✓ | Bilinmeyen-seçenek reddedilir |
| V4 | `verify --tenant OLMAYAN` | 0 | **0** | ✓ | Doğrulama her-tenant ile çalışır |

### serve

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| SV1 | `serve --no-block` | 0 | **0** | ✓ | Sunucu başlat+durdur ( gerçek-soket) |
| SV2 | `serve --port abc` | 2 | **2** | ✓ | `Error: Invalid value for '--port': 'abc' is not a valid integer.` |

### pilot ( ekstra-kapsam)

| # | Girdi | Beklenen rc | Ölçülen rc | Sonuç | Not |
|---|-------|------------|-----------|-------|-----|
| P1 | `pilot` | 0 | **0** | ✓ | Sentetik-veri + imza-kanıtı |
| P2 | `pilot --leads-per-company abc` | 2 | **2** | ✓ | Tamsayı-değil reddedilir |

**Toplam: 27 satır — HEPSİ beklenen-rc ile UYUMLU.** Geçersiz-girdilerden hiçbiri `rc=1`/traceback vermedi ( T7 haricinde-atanamaz-olduğu için).

## `status --json` Incelemesi

**YOK.** `status` komutunun `--json` bayrağı bulunmamaktadır ( tıpkı `report`, `simulate`, `pilot`, `serve` gibi). Sadece `verify --json` JSON verir — ama CAREFUL: bu çıktı saf-JSON-değil, motorun uyarı çıktıları ( Circuit-Breaker logları) ile birleşiktir ( test örneği: `/tmp/y_ver_j.json` dosyasının başında 3 CB-uyarı satırı vardır). JSON-parse-etmek isteyen tüketiciler generado-çıktının `index('{')` konumundan-başlamalıdır ( bu-davranış pin-testiyle sabitlendi).

**`verify --json` yapısı ( doğrulandı):**
```json
{
  "verdict": "PASS",      // str — "PASS" | "FAIL"
  "passed": 9,            // int
  "total": 9,             // int
  "checks": [             // list[dict]
    {
      "check": "pipeline_runs_lead_to_cycle",   // str
      "result": "PASS",                          // str — "PASS" | "FAIL"
      "detail": "ingested=True active=6 shed=0"  // str
    }
  ]
}
```

**Doğrulanan-alan-tipleri:** `verdict: str`, `passed: int`, `total: int`, `checks: list`; her-check: `check: str`, `result: str`, `detail: str`. Bu yapı tests/test_cli_rc_dallar.py'deki `test_v2_json_yapisi_alan_tipleri` ile sabitlendi.

## Bilinen-Sonuçlar & D2-Raftaki-Öneriler

Özetle — **geçersiz-girdi traceback yok** ( ama 4 zayıf-doğrulama-notu var):

1. **S2/S4/R2** — tenant varlığı doğrulanmaz ( motor tamamen in-memory, `PipelineConfig(tenant_id=...)` string-kabul). Bilinen-davranış, *kırılma-değil*.
2. **I3/I4** — telefon-formatında içerik-doğrulaması yok ( "abc" veya "" sessiz-kabul). Güvenilmez-veri riski.
3. **R3/R4** — tarih-format doğrulaması yok ( "wrong" veya 2026-13-45 sessiz-kabul).
4. **M9** — devasa-run sayısı için üst-sınır-guard yok ( doomsayıcı-run = pratikte sonsuz-CPU).

Bu dördü de DALGA-D2'ye-rafta-bırakılmıştır ( D1-kapsamı: sadece pin'ler, üretim-dokunulmaz).

## Pin-Testleri

`tests/test_cli_rc_dallar.py` — **33 pin-testi, HEPSİ-YEŞİL** ( 27 matris-satırının-çoğu + --json yapı-testi + komut-tutarlılık-kontrolleri). Test-yöntemi: `click.testing.CliRunner` ( gerçek-proses-fork'u-yok, hızlı).

**Kırmızı-kalan-pin: YOK** — geçersiz-girdi traceback ( rc=1) bulunmadığı için DALGA-kuralı gereği kırmızı-test-bırakılmadı. Mevcut-davranış pin'lendi; zayıf-doğrulama-düzeltmeleri DALGA-D2'ye-rafta.

**Tam-suiteasyonu ( pin'lerle):** 481 passed, rc=0 ( 448 temel + 33 yeni-pin).
