# MESH Entegrasyon Değerlendirmesi — Kredent DID + Sester Receipt Zinciri

> **Tarih:** 2026-09-29
> **Soru:** (1) YIELDIX çıktıları **Kredent DID** ile imzalanabilir mi?
> (2) **Sester receipt zincirine** bağlanabilir mi?
> **Cevap:** **Evet — her ikisi de.** Aşağıda somut gerekçe ve
> uygulanabilirlik-analizi. **Dürüst-not:** bu bir *değerlendirmedir*,
> uygulanmış-bağlantı değil; kardeş-bağımlılık-kısıtı ( aşağıda) nedeniyle
> gerçek-entegrasyon kendi-kararıdır.
>
> **Kardeş-belge:** FLEKSA için aynı-değerlendirme
> [`76-Fleksa/docs/MESH-ENTTEGRASYON.md`](../76-Fleksa/docs/MESH-ENTTEGRASYON.md).

---

## 1. Kriptografik-uyum ( neden "evet")

| Bileşen | İmza-algoritması | Özet-algoritması | Kimlik-formatı |
|---|---|---|---|
| **YIELDIX** | Ed25519 ( RFC 8032) | SHA-256 ( canonical JSON) | imzalı-KPI-rapor |
| **Kredent** | Ed25519 ( W3C did:key) | SHA-256 ( canonical attestation) | `did:key:z6Mk...` |
| **Sester** | — ( ödeme-metresi) | SHA-256 ( hash-chained ledger) | seq+prev_hash |

**Anahtar-gözlem:** YIELDIX **Ed25519 + SHA-256** kullanıyor ( `crypto/signer.py`,
`crypto/hasher.py`). Kredent'in `did:key` formatı Ed25519 public-key'inden
türetilir — yani YIELDIX'in imzaladığı **aynı private-key** ile bir `did:key`
kimliği-üretilebilir. **Yeni bir anahtar-altyapısı gerekmez.**

## 2. Kredent DID ile imzalama ( uygulanabilirlik: YÜKSEK)

YIELDIX'in `MonthlyReportGenerator.generate_signed_report` çıktısı:
```
sha256_digest + ed25519_signature  →  MonthlyReportPayload
```

Kredent'in `create_attestation(seed, claim)` API'si tam olarak bu-formdadır:
`claim` = KPI-payload ( total_leads, qualified_sql, CPL, p95, …), imza =
Ed25519. **Dönüşüm-maliyeti: düşük** — mevcut `Ed25519ReportSigner` zaten
`sign_dict` ile aynı kanonikleştirme-yolunu ( sorted-JSON) kullanır.

**Önerilen-uyumluluk-katmanı ( kavramsal):**
```python
from kredent.attest import create_attestation
att = create_attestation(
    seed=yieldix_seed_32bytes,           # AYNI Ed25519 seed
    claim={"report_id":..., "qualified_sql":..., "cpl_try":...},
)
# att.issuer == "did:key:z6Mk..." ( YIELDIX anahtarından türetilmiş)
```

**Sınırlar ( dürüst):**
- YIELDIX imzaları her-rapor-üretiminde **yeni-anahtar** üretir
  ( `Ed25519ReportSigner.__init__` → `Ed25519PrivateKey.generate()`).
  Kredent `did:key` **kalıcı-kimlik**-ister. Çözüm: tenant-başına-bir-seed
  ( `YIELDIX_TENANT_SEED` env-değişkeni) — imzalı-rapor-yolu-korunur,
  opsiyonel-Kredent-yolu-eklenir.
- **PRIVATE_KEY-ÜRETİM-YASAK** kısıtı-geçerli: seed yalnızca yerel-demoda
  sabit-demo-değer ( pilot-veri-seti'nin `01*32`-modeliyle-aynı).

## 3. Sester receipt zincirine bağlanma ( uygulanabilirlik: ORTA-YÜKSEK)

Sester ledger'ı ( `sester/ledger.py`):
```
canonical_line(ts, event_type, agent_id, host, amount, payload, prev_hash)
  → SHA-256 → hash → sonraki-satırın prev_hash'i
```
Her-olay bir-öncekinin-hash'ine-bağlı; zincir-kırılması `prev_hash != prev`
ile tespit-edilir.

**YIELDIX bağlantı-noktası:** imzalı-KPI-raporun SHA-256-özü Sester'e
`payload` olarak-yazılır; receipt, raporun **zaman-damgalı varlık-kanıtı**
olur ( non-repudiation + sıralama). KPI-rapor-tutamaçları:
```python
sester.append(event_type="YIELDIX_KPI_PROOF",
              payload=report.sha256_digest,   # kanıt
              amount=0.0)                    # ödeme-YOK ( kanıt-için)
```

**Neden-doğal:** Sester'in "herkes sha256 ile doğrular, Sester'e-ihtiyaç-yok"
ilkesi YIELDIX'in `verify` CLI'sının **bağımsız-doğrulama-felsefesiyle-aynı**.
İki-bağımsız-doğrulama-katmanı birbirini-güçlendirir.

**Sınırlar ( dürüst):**
- **Ödeme-metresi-çakışması:** Sester ödeme-için-tasarlanmıştır; YIELDIX
  **fon-yönetmez** ( "üretim-kanıtı-üretir, fon-yönetmez" — README).
  `amount=0.0` ile bağlanmak Sester'in ödeme-semantiğini **kanıt-defterine**
  dönüştürür — Sester'in-birincil-amacı-DEĞİLDİR; kardeş-kararı-gerektirir.
- **RFC-010 mesh-mutabakat:** mesh-düzeyinde-mutabakat RFC-010'da-tanımlı;
  bu-değerlendirme **protokol-uyumluluğunu** kanıtlar, **mutabakat-kararını** değil.
- **Egemenlik:** YIELDIX'in "üretim-kanıtı" kimliği-zorunlu-kardeş-bağımlılık-
  istemez; entegrasyon **opsiyonel-köprü**-olmalıdır ( mevcut-yol-korunur).

## 4. Önerilen ilk-adım ( minimum-uygulanabilir-kanıt)

`yieldix verify`'a opsiyonel bir kapı eklenebilir:
```
kredent_did_signable:  pilot-veri-seti raporu did:key ile imzalanabilir
                       ( aynı-Ed25519-anahtarı, yeni-altyapı-YOK)
```
Bu, **private-key-üretmeden** ve **para-harcamadan** ( kısıtlara-uygun)
entegrasyonun kriptografik-olarak-mümkün olduğunu kanıtlar.

## 5. Sonuç

| Soru | Cevap | Maliyet | Kısıt |
|---|---|---|---|
| Kredent DID ile imzalanabilir mi? | **EVET** — aynı-Ed25519+SHA-256 | düşük | kalıcı-tenant-seed-gerekli; demo-anahtarı-yeterli |
| Sester receipt zincirine bağlanabilir mi? | **EVET** — SHA-256 hash-zinciri-uyumlu | orta | opsiyonel-köprü-olmalı ( egemenlik) |

**Neden-şimdi-değil:** Kullanıcı-kısıtlarında "Push öncesi BANA SOR" ve
"para-harcama-YASAK" var. Gerçek-entegrasyon kardeş-kararları-içerir;
bu-değerlendirme **uyumluluk-kanıtı** sağlar ve uygulanabilir-yol-haritası
çizer. **Uydurma-YOK:** tüm-format-iddiaları kardeş-dosyalardan-okundu
( `68-Kredent/kredent/attest.py`, `63-Sester/sester/ledger.py`, README'ler).
