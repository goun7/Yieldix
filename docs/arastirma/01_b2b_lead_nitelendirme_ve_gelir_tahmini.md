# YIELDIX — Akademik Araştırma Dizini (2026, DOĞRULANMIŞ)

> **Tarih:** 2026-09-29
> **Yöntem:** arXiv API tarama + her başvuru `web_fetch` ile bireyden-doğrulandı
> (HTTP 200 + başlık + özet). **UYDURMA YOK.**

## Alan

YIELDIX = B2B gelir motoru — 6 "silindir" (resepsiyon, hız-ajanı,
web-nitelendirici, CRM-reaktivasyon, soğuk-e-posta-L2, gelen-kutusu-
ayıklama) SLA + devre-kesici altında orkestre edilir; çıktı **Ed25519-
imzalı aylık KPI raporu** olarak zincir-içi ledger'a işlenir. İlgili
alanlar: **B2B lead nitelendirme/önerisi**, talep-gelir tahmini, satış-
pipeline otomasyonu.

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

---

## DOĞRULANAMAYAN / BOŞ SONUÇLAR (dürüst kayıt)

- arXiv `abs:"lead" AND abs:"qualification" AND abs:"sales"` → yalnızca **2
  sonuç** ve ikisi de konu-dışı (kuantum-bilgisayar performans-sonuçları ve
  in-context-grounding). Yani "lead qualification" akademik literatürde
  **dar/boş** — bu, alanın akademik-literatürden çok **endüstri-pratiği**
  (HubSpot/Salesforce ekosistemi, BANT çerçevesi) ile ilerlediğini gösterir;
  bir zayıflık değil, farklı bir kanıt-türü gerektirir (vaka-çalışması ve
  gerçek-pilot verisi).
- `mcp__weblocal__web_search` (DuckDuckGo) bu oturumda **tüm sorgularda boş
  `[]`** döndü; yerleşik `web_search` aracı **HTTP 401** ile başarısız oldu.

## SONUÇ (araştırmaya dayalı dürüst okuma)

YIELDIX'in çekirdek problemi (B2B lead önceliklendirme + gelir-kanıtı)
**gerçek ve akademik olarak çalışılan** bir alandır; kabul-görmüş bir
sanayi-bildirisi (DBpedia/ESWC 2026) YIELDIX'in silindir-mimarisine
doğrudan uygulanabilir bir yöntem sunar. "Lead qualification" akademik
olarak boş olduğundan, doğrulama için bir sonraki adım **gerçek bir pilotun
 ölçülen CPL/SQL verisi** olmalıdır — YIELDIX'in mevcut `report` çıktısı
bunun için tam doğru iskeleti (imzalı KPI) zaten üretmektedir.
