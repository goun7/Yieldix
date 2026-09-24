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
python3 -m pytest tests/                # 49-passed
```

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
python3 -m pytest tests/ -q    # 49-passed
```

## Sınırlar ( dürüst)

- Yieldix'in **beş-yüzü** vardır ( AT-077/088/097/114/118) — bunlar
  tamamlanmış-kripto-yüzeydir; **onun-dışında** imza/digest/doğrulama-YOK
  ( AT-183-incelemesi: 11-kalan-modül-İNDETERMİNE-test-double'sız)
- Pipeline **sync**-çalışır; async-zamanlama-kontrolleri-yok ( AT-181-
  kapsamında-temiz)
