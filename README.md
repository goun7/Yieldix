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
python3 -m pytest tests/                # 110-passed (+11 Tamga-anchor)
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

## Tamga ledger sabitleme ( mesh-anchor)

Yieldix'in imzalı kanıtı artık **Tamga'nın bağımsız hash-zincirine**
sabitleniyor — [TamgaProtocol](../../05_acik_kaynak/TamgaProtocol)
( mesh'in kalıcı kanıt-anchor katmanı). Kanıt tek-parti tarafından
gizlice değiştirilemesin diye: aynı kanıt iki bağımsız zincirde paralel
yaşar ( Yieldix'in Ed25519 imza-zincirinde + Tamga'nın append-only
hash-zincirinde).

```
MonthlyReportPayload → Ed25519-imza ( AT-077)
         ↓
    tamga_anchor.build_anchor_record
         ↓  h = sha256(prev ‖ jcs(kayıt − {h}))   ← RFC 8785 JCS, bayt-uyumlu
    tamga-sim/1 ledger.jsonl   →  Tamga'nın KENDİ verifier'ında GREEN
```

**Modül:** `yieldix.mesh.tamga_anchor` — bağımlılıksız ( stdlib-only);
Tamga'nın JCS'i RFC 8785'den sıfırdan yazılmıştır ve `tamga_canon.jcs` ile
**bayt-bayt uyumludur** ( parite-testi makine-çeklidir).

```bash
# Üretilen ledger'ı Tamga'nın KENDİ bağımsız verifier'ında doğrula
PYTHONPATH=src python3 -c "
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.mesh.tamga_anchor import sabitle_raporlar
# ... imzalı raporları üret ...
s = sabitle_raporlar(raporlar, signer=signer)
s.tamga.jsonl_yaz('/tmp/yieldix_anchor.jsonl')
"
python3 /path/to/TamgaProtocol/tests/conformance/verify.py /tmp/yieldix_anchor.jsonl
# → {"ok": true, "reason": "ok", ...}   ( GREEN)
```

```python
from yieldix.mesh.tamga_anchor import KanitTamgaSabitleyici, anchor_report

# Tek kanıtı mevcut bir ledger'a sabitle ( kırık zincire asla eklemez)
kayit = anchor_report(rapor, "tamga-ledger.jsonl",
                      public_key_hex=signer.public_key_hex)

# Veya toplu + üç-katmanlı doğrulama
sabitleyici = KanitTamgaSabitleyici(raporlar, signer=signer)
sabitleyici.sabitle()          # idempotent: yalnızca yeni kanıtları işler
assert sabitleyici.dogrula()   # 1) Tamga zincir-bütünlüğü ( D5 kuralı)
                               # 2) Ed25519 imzası kanıt-üzerinde geçerli
                               # 3) tamlık: her kanıt sabitlenmiş
```

**Neden RFC 8785 ( JCS) değil ``json.dumps(sort_keys=True)``?** Bir kanıtın
noktası, yabancının **farklı bir dille** aynı baytları yeniden türetebilmesidir.
RFC 8785: üye-adları UTF-16 kod-birim dizisine göre sıralar ( §3.2.3) ve
sayıları ECMAScript ``Number.prototype.toString`` ile yazar ( §3.2.2.2:
``1.0`` → ``"1"``, ``2.93e-07`` → ``"2.93e-7"``). Yieldix'in mevcut imza
yüzeyi ( AT-077) olduğu gibi kalır; yalnızca Tamga zincir-hash'i JCS
kullanır — iki ayrı canonicalization, iki ayrı amaç için.

## Test

```bash
python3 -m pytest tests/ -q    # 121-passed
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

## Akademik Kaynaklar (2024-2026)

Bu çalışma aşağıdaki araştırmaya dayanır (her referans canlı
doğrulanmıştır: `curl -sIL https://arxiv.org/abs/...` → **200**):

- **[1] Katkı-kanıtı mekanizması** —
  *A proof of contribution in blockchain using game theoretical deep
  learning model* — Wang, arXiv 2024 (cs.CR).
  Blockchain üzerinde oyun-teorik **katkı-kanıtı** ( proof-of-
  contribution) mekanizması: katılımcıları kaynaklarını sunmaya
  motive eden teşvik-modeli. Yieldix'in "üretim-kanıtı üretir"
  tasarımının doğrudan benzeri — kepenk yerine **katılımı**
  ispatlar.
  [arXiv:2409.07460](https://arxiv.org/abs/2409.07460)
- **[2] Katkı-kanunu + itibar** —
  *PoCQ: Proof of Contribution Quality as a Lightweight Blockchain
  Consensus for Secure Federated Learning* — Abed et al., arXiv 2026
  (cs.DC).
  **İtibar-farkında** doğrulama + kriptografik-commitment ile katkı
  kalitesinin kanıtlanması; zincire yalnızca sıkı-denetim-metaverisi
  yazılır. Yieldix'in her-adım-kanıt-hash'i + BANT-nitelendirme
  ikilisinin ( hafif-doğrulama + itibar) akademik karşılığı.
  [arXiv:2606.05642](https://arxiv.org/abs/2606.05642)
- **[3] Katkı-ölçümü + teşvik** —
  *Democratizing Federated Learning with Blockchain and Multi-Task
  Peer Prediction* — Witt et al., arXiv 2026 (cs.CR, cs.CY).
  Katkı-ölçümünün hesaplama-ağırlığının zincir kısıtlarıyla çatışması
  sorununa **peer-prediction** ile çözüm; akıllı-sözleşmelerle
  katılım-teşviki. Yieldix'in "kanıt-hesaplaması-pipeline-içinde-
  kalır" benzeri bir maliyet-farkındalığı.
  [arXiv:2603.28434](https://arxiv.org/abs/2603.28434)
- **[4] Yararlı-iş kanıtı + teşvik-güvenliği** —
  *Proof-of-Learning with Incentive Security* — Zhao et al., arXiv
  2024 (cs.CR, cs.AI, cs.ET).
  PoW/PoS'un yerine **anlamlı-iş** ( proof-of-useful-work) kanıtlayan
  protokol ailesi ve teşvik-uyumlu-güvenlik analizi. Yieldix'in
  "kanıt-üretir, fon yönetmez" tercihinin teorik temeli: ispatın
  kendisi üretilen-değerdir.
  [arXiv:2404.09005](https://arxiv.org/abs/2404.09005)
- **[5] Çok-ajanlı adil-atfedim** —
  *Semantic Cooperative Games for Contribution Attribution in
  LLM-Based Multi-Agent Systems* — Jiang et al., arXiv 2026 (cs.AI).
  Çok-ajanlı iş-akışlarında **karşı-faktörel** ( counterfactual)
  yöntemlerin yüksek-varyans/maliyet sorununa semantik-oyun-teorisi
  çözümü: her ajanın bilgiye katkısını ayrıştırır. Yieldix'in
  pipeline-silindirleri boyunca "kim-üretti" sorusunun akademik
  çerçevesi.
  [arXiv:2607.18255](https://arxiv.org/abs/2607.18255)
- **[6] Shapley-tabanli kredi-ataması** —
  *Who Deserves the Reward? SHARP: Shapley Credit-based Optimization
  for Multi-Agent System* — Li et al., arXiv 2026 (cs.AI).
  Seyrek/genel-yayın ödüllerinin yerine **Shapley-değerine-dayalı
  hiyerarşik-atfedim**: hangi işlevsel-ajanın başarıdan/başarısızlıktan
  sorumlu olduğunu belirler. BANT-nitelendirmenin "yapısal-lead-
  doğrulama" yaklaşımı için dağıtık-adillik referansı.
  [arXiv:2602.08335](https://arxiv.org/abs/2602.08335)
- **[7] Ajans-sistemi kredi-ataması** —
  *CANTANTE: Optimizing Agentic Systems via Contrastive Credit
  Attribution* — Zehle, arXiv 2026 (cs.CL, cs.AI, cs.MA).
  Sistem-düzeyi puanlarını **kontrastif** karşılaştırmayla her-ajan
  için yerel güncelleme-sinyallerine ayrıştırır. Yieldix'in
  tenant-bazlı-rapor-pipeline'ında sistem-düzeyi-çıktıyı
  adil-biçimde-parçalama ihtiyacıyla örtüşür.
  [arXiv:2605.13295](https://arxiv.org/abs/2605.13295)
- **[8] Katilimci-uretim protokolu** —
  *DAO-Agent: Zero Knowledge-Verified Incentives for Decentralized
  Multi-Agent Coordination* — Xia et al., arXiv 2025 (cs.MA).
  Güvensiz-ortamlarda merkezileştirilmiş-koordinasyonun açık-vurgusu:
  "şeffaf katkı-ölçümü ve adil-teşvik-dağıtımı sağlanamaz"; çözüm
  sıfır-bilgi-kanıtlı denetlenebilir-görev-yürütme. Yieldix'in
  **katılım-üretim protokolü** olarak varoluş-gerekçesinin ( neden
  imzalı-kanıt gerekli) en yakın akademik ifadesi.
  [arXiv:2512.20973](https://arxiv.org/abs/2512.20973)
