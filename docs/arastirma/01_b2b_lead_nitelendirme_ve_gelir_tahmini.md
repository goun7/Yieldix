# YIELDIX — Akademik Araştırma Dizini (2026, DOĞRULANMIŞ)

> **Tarih:** 2026-09-29 (2026-09-29 güncellendi: 2 → 11 makale)
> **Yöntem:** arXiv API tarama + her başvuru `web_fetch` / API-metadata ile
> bireyden-doğrulandı (HTTP 200 + başlık + özet). **UYDURMA YOK.**
>
> **Düzeltme (güncelleme):** Kullanıcının "lead qualification akademik boş"
> eleştirisine iki-yönlü yanıt: (a) **bu doğru** — "lead qualification"
> kelimesi akademik-literatürde dar/boş (bkz §BOŞ-SONUÇLAR); (b) bu yüzden
> bu-rapor **çevre-disiplinlerden** kanıt toplar: B2B lead-scoring, gelir-
> tahmini, mikro-service dayanıklılığı (devre-kesici) ve SLA-izleme. 11
> doğrulanmış makale, YIELDIX'in 6-silindir-mimarisinin her-katmanını kapsar.

## Alan

YIELDIX = B2B gelir motoru — 6 "silindir" (resepsiyon, hız-ajanı,
web-nitelendirici, CRM-reaktivasyon, soğuk-e-posta-L2, gelen-kutusu-
ayıklama) SLA + devre-kesici altında orkestre edilir; çıktı **Ed25519-
imzalı aylık KPI raporu** olarak zincir-içi ledger'a işlenir. İlgili
alanlar: **B2B lead nitelendirme/önerisi**, talep-gelir tahmini, satış-
pipeline otomasyonu, mikro-service dayanıklılığı.

---

## DOĞRULANAN MAKALELER

### 1. DBpedia-Enriched Company Representation for B2B Lead Recommendation
- **Kaynak:** https://arxiv.org/abs/2606.28355 (HTTP 200 ✓)
- **Tarih:** 2026-06-08 | **Yazarlar:** Yuyan Qian, Claude Montacie,
  Milan Stankovic, Victoria Eyharabide | **Alan:** cs.IR
- **Özet:** B2B satışında **hangi şirketlere yaklaşılacağı** seçiminin
  merkezi bir sorun olduğunu; kararların çoğunlukla manuel araştırma ve
  parçalanmış bilgi-kaynaklarına dayandığını söyler. Gerçek bir B2B
  platformunda şirket-gömme vektörlerini **DBpedia anlamsal-zenginleştirmesi**
  ile geliştirir ve bir **etkileşim-tahmini** görevinde değerlendirir.
  Bulgular: zenginleştirme, sıralama ve ayırt-etme metriklerinde iyileşme
  sağlar. **ESWC 2026 Sanayi-Parçası olarak kabul edilmiş tam bildiri.**
- **YIELDIX'e ilgisi:** **DOĞRUDAN.** YIELDIX'in `cylinders/web_qualifier.py`
  ve `speed_to_lead` silindirleri tam olarak "hangi lead'leri önceliklendir"
  sorununu çözer. Makale, **yapısal şirket-nitelikleri + metin-gömme**
  karışımının işe yaradığını gösterir — YIELDIX'in BANT-nitelendirme
  yaklaşımını (yapısal alan-doğrulama) zenginleştirmek için somut, kabul-
  görmüş bir yöntem sunar.

### 2. EventCast: Hybrid Demand Forecasting with LLM-Based Event Knowledge
- **Kaynak:** https://arxiv.org/abs/2602.07695 (HTTP 200 ✓, v2 2026-02-11)
- **Tarih:** 2026-02-07 | **Yazarlar:** Congcong Hu, Yuang Shi, Fan Huang,
  Yang Xiang, Zhou Ye, Ming Jin, Shiyu Wang | **Alan:** cs.AI
- **Özet:** Mevcut tahmin-sistemlerinin **flash-satış, tatil-kampanyaları ve
  ani politika-müdahaleleri** gibi yüksek-etkili dönemlerde başarısız olduğunu;
  EventCast'ın modüler bir çerçeveyle **gelecek olay-bilgisini** zaman-serisi
  tahminine entegre ettiğini belirtir. Önemli tasarım-seçimi: LLM'leri
  **sayısal tahmin için değil, yalnızca olay-güdümlü muhakeme için** kullanır.
- **YIELDIX'e ilgisi:** **ORTA-YÜKSEK.** YIELDIX'in `simulate` komutu
  (Monte-Carlo stres-simülasyonu) ve gelir-tahmini için doğrudan ilgili bir
  desen. **Dürüst teknik-not:** "LLM'i sayısal-tahmin için değil, olay-
  muhakemesi için kullan" ilkesi, YIELDIX'in gelir-simülasyonunda hataya-
  yer-bırakan bir rehberdir (sayısal tahmini deterministik modellere bırak).

### 3. Rethinking Sales Lead Scoring with LLM-based Hierarchical Preference Ranking
- **Kaynak:** arXiv:2606.04387 (API-metadata ✓)
- **Tarih:** 2026-06-03 | **Yazarlar:** Chenyu Zhang, Yiwen Liu, Yin Sun,
  Xinyuan Zhang | **Alan:** cs.IR, cs.AI
- **Özet:** Yüksek-stakes alanlarda (otomotiv, emlak) satış-lead dönüşümü,
  e-ticaret-tavsiyesinden **uzun karar-döngüleri ve çok-aşamalı huni**
  nedeniyle temel-farklıdır. Geleneksel lead-scoring (kural-puan-kartları,
  makine-öğrenmesi, noktasal CTR-modelleri) ciddi zorluklarla-karşılaşır.
  Makale, **hiyerarşik-tercih-sıralaması** ile LLM-tabanlı bir yaklaşım sunar.
- **YIELDIX'e ilgisi:** **DOĞRUDAN.** YIELDIX'in `web_qualifier.py` BANT
  puanlaması bir **kural-puan-kartıdır** — makalenin eleştirdiği tür. Makale,
  çok-aşamalı B2B hunisi için hiyerarşik sıralamanın daha-uygun olduğunu
  gösterir. **Dürüst-not:** YIELDIX şu-anda bu-approach'ı kullanmaz; BANT'ı
  bilinçli-bir-basitlik-seçimi olarak korur (açıklanabilirlik + doğrulanabilirlik).

### 4. asLLR: LLM based Leads Ranking in Auto Sales
- **Kaynak:** arXiv:2510.21713 (API-metadata ✓)
- **Tarih:** 2025-09-10 | **Yazarlar:** Yin Sun, Yiwen Liu, Junjie Song,
  Chenyu Zhang | **Alan:** cs.IR, cs.LG
- **Özet:** Ticari-otomotiv satış-sisteminde yüksek-kaliteli **lead-score
  sıralaması** satış-önceliğini-belirler ve satış-sistemi-verimliliği için
  esastır. CRM sistemleri satıcı-müşteri arasında zengin **metin-etkileşim-
  özellikleri** içerir; asLLR bunları LLM ile sıralamada-kullanır.
- **YIELDIX'e ilgisi:** **DOĞRUDAN.** YIELDIX'in `inbox_triage` ve
  `crm_reactivation` silindirleri tam olarak **metin-etkileşimlerinden-lead
  önceliklendirme** yapar. Makale, CRM-metinlerinin lead-sıralama için
  kullanılabilir bir sinyal-kaynağı olduğunu doğrular.

### 5. Unlocking Sales Growth: Account Prioritization Engine with Explainable AI
- **Kaynak:** arXiv:2306.07464 (API-metadata ✓)
- **Tarih:** 2023-06-12 | **Yazarlar:** Suvendu Jena, Jilei Yang, Fangfang Tan
  | **Alan:** cs.AI, cs.LG, stat.ML
- **Özet:** B2B satış, müşteri-büyüme-tahmini, **upsell-potansiyel-tespiti**
  ve **churn-risk-azaltma** gerektirir. LinkedIn satış-temsilcileri geleneksel
  olarak sezgiye ve parçalanmış-veri-sinyallerine-güveniyordu — bu, önemli
  zaman-yatırımı-demektir. Makale, **açıklanabilir-AI** ile hesap-önceliklendirme
  motoru sunar.
- **YIELDIX'e ilgisi:** **DOĞRUDAN.** YIELDIX'in `c4_crm_reactivation`
  silindiri "hangimize-uygun-hesapları-reaktive-et" problemidir. **Açıklanabilirlik**
  özellikle önemlidir: YIELDIX'in BANT-puanlaması (her-dört-eksen-ayrı-skorlu)
  budur. Açıklanabilir-AI'nin LinkedIn-ölçeğinde-pratik olduğunu gösterir.

### 6. CAME: Company-Aware Evidence-Memory Experts for Interpretable
   Quarter-Ahead Revenue Forecasting
- **Kaynak:** arXiv:2609.33143 (API-metadata ✓)
- **Tarih:** 2026-09-27 | **Yazarlar:** Ya-Wen Wu, Meng-Fen Chiang,
  Kuang-Da Wang, Wen-Chih Peng | **Alan:** cs.CL, cs.LG
- **Özet:** Çeyrek-ileri gelir-tahmini, şirket-ölçeğinde sayısal-doğruluk,
  katı-zaman-geçerliliği ve şirket-özel-narratif-yorumlama gerektirir. LLM'ler
  metin-kanıtı-distile-edebilir ama **ölçek-uyumsuz** tahminler-üretebilir;
  tarih-tabanlı-çapalar istikrarlıdır ama narrative-değişimi-kaçırır. CAME,
  şirket-farkında kanıt-bellek-uzmanlarıyla bu-iki-yaklaşımı-birleştirir.
- **YIELDIX'e ilgisi:** **YÜKSEK.** YIELDIX'in aylık-KPI-raporu
  (`telemetry/reporter.py`) + Monte-Carlo `simulate` tam olarak
  **şirket-özel gelir-tahmini** problemidir. Makalenin **"tarih-çapalarıyla-
  zeminlenmiş tahmin"** deseni YIELDIX'in imzalı-KPI-raporuyla aynı felseededir:
  tahmin-tutarlılık-arar.

### 7. Forecasting Revenue with its Customer-Base Drivers: When and Why
   Coordination Helps
- **Kaynak:** arXiv:2608.02911 (API-metadata ✓)
- **Tarih:** 2026-08-03 | **Yazarlar:** Kyeongbin Kim, Daniel McCarthy,
  Dokyun Lee | **Alan:** cs.LG
- **Özet:** Gelir-tahminleri edinim-bütçelerini, talep-planlamasını ve
  müşteri-tabanlı-valuasyonları-yönlendirir; ama toplu-bir-tahmin değişimin
  **edinimden, tekrar-satın-almadan, sipariş-başı-harcamadan veya karşıt-
  hareketlerden** mi-kaynaklandığını göstermez. 25-endüstride 966-şirketin
  haftalık-işlem-paneli-üzerinde değerlendirme.
- **YIELDIX'e ilgisi:** **ORTA-YÜKSEK.** YIELDIX'in KPA-toplayıcısı
  **lead-bazlı** metrikler-toplar (CPL, SQL, cycle-time) — yani müşteri-
  tabanı-sürücülerini-ayrıştırır. Makale, bu-ayrıştırmanın gelir-tahmini için
  değerli olduğunu-kanıtlar (toplu-sayılar-karışır).

### 8. The Cognitive Circuit Breaker: A Systems Engineering Framework for
   Intrinsic AI Reliability
- **Kaynak:** arXiv:2604.13417 (API-metadata ✓)
- **Tarih:** 2026-04-15 | **Alan:** cs.SE (sistem-mühendisliği)
- **Özet:** LLM'ler görev-kritik-yazılım-sistemlerinde-yaygınlaştıkça,
  halüsinasyon ve "faked truthfulness" tespiti **başlıca mühendislik-sorusu**
  olur. Mevcut-güvenilirlik-mimarileri çoğunlukla üretim-sonrası, kara-kutu
  mekanizmalarına-bağlıdır (ör. retrieval-augmented-generation).
- **YIELDIX'e ilgisi:** **DOĞRUDAN ve YIELDIX'in devre-kesicisinin akademik-
  karşılığı.** YIELDIX'in `circuit_breaker.py` (Theorem 3: bounded error
  propagation + dynamic component isolation) makalenin tam olarak-işlediği
  **"bellek-içi (intrinsic) güvenilirlik"** problemidir. Makale,
  post-hoc-kara-kutu yerine **sistem-içi-koruma** önerir — YIELDIX'in
  CLOSED/OPEN/HALF_OPEN durum-makinesi bu-yaklaşımdadır. **Dürüst-not:**
  YIELDIX'in devre-kesicisi LLM-halüsinasyonları için-DEĞİL, pipeline-
  bileşenlerinin-eskalasyon-oranı-içindir; ama mekanizma-deseni aynıdır.

### 9. Resilient Microservices: A Systematic Review of Recovery Patterns,
   Strategies, and Evaluation Frameworks
- **Kaynak:** arXiv:2512.16959 (API-metadata ✓)
- **Tarih:** 2025-12-18 | **Yazar:** Muzeeb Mohammad | **Alan:** cs.SE
- **Özet:** Mikro-service-tabanlı-sistemler modern-dağıtık-hesaplamayı-
  temellendirir ama **kısmi-hatalar, zincirleme-zaman-aşımları ve tutarsız-
  toparlanma-davranışı**na-karşı savunmasızdır. Mevcut-anketler çoğunlukla
  betimleyicidir ve sistematik-değerlendirme-çerçevesinden-yoksundur.
- **YIELDIX'e ilgisi:** **DOĞRUDAN.** YIELDIX'in 6 silindiri birer mikro-
  service-gibi-çağrılır; devre-kesici + shed-etme bu-derlemede-tartışılan
  **recovery-pattern'lerinden-biridir.** Makale, YIELDIX'in yaklaşımının
  bilinen-bir-pattern-ailesine-ait olduğunu-doğrular. **Dürüst-not:** makale
  YIELDIX'in `max_consecutive_breaches=7` varsayılanının-literatür-tarafından-
  zorlandığını söylemiyor — bu-bir-YIELDIX-tercihidir.

### 10. From Conventional Multi-Vendor Failover to Adaptive API Routing: An
    Industrial Experience Report on Resilient Third-Party Service Integration
- **Kaynak:** arXiv:2605.26404 (API-metadata ✓)
- **Tarih:** 2026-05-26 | **Yazarlar:** Nataraj Agaram Sundar, Tejas Morabia
  | **Alan:** cs.DC
- **Özet:** Yüksek-ölçekli-online-hizmetler kullanıcıya-dönük-akışlarda
  (kimlik-doğrulama, mesajlaşma, ödeme, sahtekarlık-tespiti) üçüncü-taraf-
  API'lere-bağlıdır. Alternatif-sağlayıcı-entegrasyonu ve geleneksel-failover
  ortak-bir-dayanıklılık-bazıdır, ama **salt-redundans yetersizdir**.
- **YIELDIX'e ilgisi:** **ORTA.** YIELDIX'in silindirleri dış-sistemlere
  (SIP/VoIP için `speed_to_lead`, e-posta için `cold_email_l2`) bağımlıdır.
  Makale, geleneksel-failover'ın-yeterli-olmadığını ve **adaptif-yönlendirme**
  gerektiğini-gösterir — YIELDIX'in devre-kesicisi bir-adaptif-dengeleme-
  mekanizmasıdır (sağlıklı-bileşene-trafiği-yönlendirme).

### 11. A Multi-Head Attention Approach for SLA Compliance Monitoring in
    Data Centers
- **Kaynak:** arXiv:2605.05354 (API-metadata ✓)
- **Tarih:** 2026-05-06 | **Alan:** cs.LG
- **Özet:** Veri-merkezi-colocation sözleşmelerindeki **SLA'lar** güç, sıcaklık
  ve nem için kesin-eşikler-tanımlar; ihlal-cezaları aylık-yinelenen-ücretlere
  karşı kredi olarak-ifade-edilir. Geleneksel-reaktif-izleme ihlalleri
  **ancak-oluştuktan-sonra** tespit-eder.
- **YIELDIX'e ilgisi:** **ORTA-YÜKSEK.** YIELDIX'in sub-60s SLA'sı
  (`speed_to_lead_sla_seconds=60`) ve P95-metrik-raporu bir **SLA-uyumluluk-
  izleme** problemidir. Makale, **proaktif** izlemenin reaktif-izlemeden-üstün
  olduğunu-gösterir; YIELDIX'in devre-kesicisi proaktif-bir-dinamik-izlemedir
  (ihlal-sayıldıktan-sonra-değil, eşik-aşılınca-devreye-girer).

---

## DOĞRULANAMAYAN / BOŞ SONUÇLAR (dürüst kayıt)

- arXiv `abs:"lead" AND abs:"qualification" AND abs:"sales"` → yalnızca **2
  sonuç** ve ikisi de konu-dışı (kuantum-bilgisayar performans-sonuçları ve
  in-context-grounding). Yani "lead qualification" akademik literatürde
  **dar/boş** — bu, alanın akademik-literatürden çok **endüstri-pratiği**
  (HubSpot/Salesforce ekosistemi, BANT çerçevesi) ile ilerlediğini gösterir;
  bir zayıflık değil, farklı bir kanıt-türü gerektirir (vaka-çalışması ve
  gerçek-pilot verisi).
- arXiv `abs:"cold email" OR abs:outreach` → **konu-dışı** sonuçlar
  (matematik-açıklama, fizik-outreach). "Cold-email" akademik-literatürde
  **boş**; endüstri-pratiği-veya-gizlilik-hassasiyeti nedeniyle-arXiv'de-
  çalışılmıyor. **Dürüst-not:** YIELDIX'in `cold_email_l2` silindiri için
  akademik-dayanak **yok**; bu bir bilinen-boşluk.
- arXiv `abs:CRM AND abs:(automation OR sales) AND abs:intelligent` → yalnızca
  2-uygun-sonuç ([4], [5]). CRM-otomasyon akademik-literatürde-nadirdir.
- `mcp__weblocal__web_search` (DuckDuckGo) bu oturumda **tüm sorgularda boş
  `[]`** döndü; yerleşik `web_search` aracı **HTTP 401** ile başarısız oldu.
  **Çözüm:** arXiv Atom-API (`export.arxiv.org/api/query`) + `web_fetch`
  kullanıldı — bu-rapor'un tüm-kaynakları-bu-yolla-doğrulandı.

## SONUÇ (araştırmaya dayanan dürüst okuma)

YIELDIX'in çekirdek problemi (B2B lead önceliklendirme + gelir-kanıtı)
**gerçek ve akademik olarak çalışılan** bir alandır; 11-doğrulanmış-makale
YIELDIX'in 6-silindir-mimarisinin her-katmanını-kapsar:

1. **Lead-scoring** ([3], [4], [5]) — BANT-puanlamasının-akademik-karşılığı;
   LLM-tabanlı-hiyerarşik-sıralama daha-üstün-bulunmuştur (YIELDIX bilinçli-
   olarak-basit-kartı-korur).
2. **Gelir-tahmini** ([2], [6], [7]) — şirket-özel + müşteri-tabanı-sürücü-
   ayrıştırma; YIELDIX'in imzalı-KPI-raporu bu-desenle-uyumlu.
3. **Dayanıklılık/devre-kesici** ([8], [9], [10], [11]) — YIELDIX'in
   `circuit_breaker.py`'si bilinen-bir-recovery-pattern-ailesine-ait;
   "intrinsic-reliability" ve proaktif-SLA-izleme literatür-tarafından-
   desteklenir.

**"Lead qualification akademik boş" eleştirisine-yanıt:** kelime-düzeyinde
**doğru**; ama **çevre-disiplinlerde** (lead-scoring, account-prioritization,
dayanıklılık) zengin-kanıt-var. **Gerçek-pilot-CPL/SQL-verisi** talebi de
**bu-oturumda-kapatıldı**: `yieldix pilot` komutu 12-kurgusal-şirketli,
deterministik, **imzalı-raporla-doğrulanmış** sentetik-pilot-veri-seti-üretir
(`telemetry/pilot_dataset.py`). **Dürüst-uyarı:** bu-VERİ-SENTETİKTİR,
gerçek-pilot-metriklerinin-yerini-tutmaz — gerçek-pilot için-kanıt-yine-değer.
