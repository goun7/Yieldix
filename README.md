# Yieldix — Yield Pipeline + Kanıt-İmzası

Yieldix, TAMGA-MESH'in **katılım-üretim** protokolüdür: BANT-nitelendirme
+ aylık-rapor-pipeline'ı + her-çıktının imzalı-kanıtı.

## Rolü (mesh-içinde)

```
inbound-lead → BANT-nitelendir → pipeline-silindirleri
        ↓ ( her-adımda kanıt-hash'i)
   MonthlyReportPayload → Ed25519-imza → §6-foreign_chain_proof
        ↓
   tamga D5-ledger (RFC-010 §6: yieldix-zinciri-kendi-adında)
```

Yieldix **fon yönetmez** — **üretim-kanıtı** üretir: bir pipeline-çıkışının
gerçekten-çalıştığını ve kim-ürettiğini kaydeder.

## Kurulum

```bash
cd yieldix
pip install -e .                        # pydantic + cryptography
python3 -m pytest tests/                # 53-passed
```

## ⏱️ In 30 seconds ( hızlı-bakış)

```bash
# 1) Bağımsız-doğrulama — lead→pipeline→KPI→imzalı-rapor zincirini sıfırdan-oynar
#    ve Ed25519-imzasını yeniden-teyit-eder ( kanıt-entegrasyonu)
PYTHONPATH=src python3 -m yieldix.cli.main verify            # → SONUÇ: PASS — 5/5

# 2) Makine-okunabilir-çıktı ( CI/entegrasyon-için)
PYTHONPATH=src python3 -m yieldix.cli.main verify --json     # → {"verdict":"PASS",...}

# 3) İmzalı-performans-raporu ( Ed25519 + SHA-256)
PYTHONPATH=src python3 -m yieldix.cli.main report --tenant demo-tenant

# 4) Sağlık
PYTHONPATH=src python3 -m yieldix.cli.main status
```

> `verify` çıkış-kodu: **0** = tüm-geçitler-sağlam, **1** = en-az-bir-bozuk.
> Kontroller: `pipeline_runs_lead_to_cycle`, `signed_report_produced`,
> `signature_verifies_and_tamper_resistant`, `tenant_isolation_enforced`,
> `circuit_breaker_sheds_on_breach`.

## Temel-API

```python
from yieldix.core.engine import YieldixEngine
from yieldix.core.types import PipelineConfig

# AT-179: tenant-ZORUNLU ( default_tenant-artık-YOK)
engine = YieldixEngine(PipelineConfig(tenant_id="tenant-abc"))
report = engine.run_daily_cycle()
```

## Güvenlik-modeli ( AT-165..184)

| Özellik | Uygulama |
|---|---|
| Tenant-izolasyon | `YieldixEngine()`-config-YOKSE → `tenant-required` (AT-179) |
| Ed25519-imza | gerçek-kütüphane, ham-digest (AT-077-üretim-yolu) |
| Circuit-breaker | CLOSED/OPEN/HALF_OPEN; 25-başarısız → OPEN (AT-182) |
| Transactional-backoff | exponential-retry + max_retries |
| Kanıt-hash'leri | her-silindir-çıktısı-hash'lenir → Merkle-bağı |
| BANT-nitelendir | yapısal-lead-doğrulama ( anahtar-kelime-tespiti-DEĞİL) |

## Test

```bash
python3 -m pytest tests/ -q    # 53-passed
```

## Sınırlar ( dürüst)

- Yieldix'in **beş-yüzü** vardır ( AT-077/088/097/114/118) — bunlar
  tamamlanmış-kripto-yüzeydir; **onun-dışında** imza/digest/doğrulama-YOK
  ( AT-183-incelemesi: 11-kalan-modül-İNDETERMİNE-test-double'sız)
- Pipeline **sync**-çalışır; async-zamanlama-kontrolleri-yok ( AT-181-
  kapsamında-temiz)

## Akademik & teknik temel

- **Append-only evidence chain** — her pipeline adımı bir kanıt-hash'i
  taşır: inbound-lead → BANT-nitelendir → pipeline-sırası →
  MonthlyReportPayload → Ed25519-imza. Bu, **append-only ledger**
  desenidir: geçmiş değiştirilemez, sadece yeni kayıt eklenebilir.
- **Ed25519 imza** — rapor imzası için (RFC 8032): hızlı, deterministik,
  küçük imza. Ajan-pazarlama raporlarında **değiştirilemez kanıt**
  için seçildi.
- **EU AI Act §6 (şeffaflık + kanıt)** — Yieldix'in imzalı raporu,
  AI tarafından üretilen pazarlama kararlarının **denetlenebilir**
  olmasını sağlar. Benzer tartışma:
  [x402 #2332](https://github.com/x402-foundation/x402/issues/2332)
  (post-settlement accountability — "loglar yeniden yazılabilir;
  hash-chain anchor olamaz").
- **Mesh içindeki rolü** — Yieldix kanıt üretir; **ödeme-makbuz
  katmanı** [63-Sester](../63-Sester), **kalıcı kanıt-anchor**
  [TamgaProtocol](../../05_acik_kaynak/TamgaProtocol). Her katman
  tek bir işi yapar.
