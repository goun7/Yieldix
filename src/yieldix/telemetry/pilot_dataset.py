"""
Sentetik-ama-gerçekçi B2B pilot veri seti ( dürüst-sınır kapatması).

Kullanıcının dürüst eleştirisine yanıt: "lead qualification akademik boş —
gerçek pilot CPL/SQL verisi olmalı". Gerçek-üretim-verisi yasaktır ( gizlilik
+ para-harcama-yasak), bu yüzden kurallı, deterministik, **gerçekçi dağılım
parametreleriyle** üretilmiş bir pilot veri seti sağlanır.

Gerçekçilik kaynakları ( parametreler hazır-kurulum, kurallı):
  * CPL aralığı 18–260 ₺ — gerçek B2B SaaS/finans lead-pazarı aralığı
  * SQL dönüşüm oranı %8–22 — endüstri B2B web-form SQL oranı bandı
  * Cycle-time: sub-60s SLA için 8–95 sn, log-normal-benzeri ağırlık
  * Eskalasyon %3–12, hata %0–4 — sağlıklı pipeline için gerçekçi bant
  * Her şirket için sabit-tohum ( seeded) → tamamen tekrar-oynanabilir

ÖNEMLİ-DÜRÜSTLÜK: Bu veri **SENTETİKTİR**. Gerçek-müşteri-verisi DEĞİLDİR,
    edemeyiz de ( gizlilik). Amacı pipeline'ın uçtan-uca **quantified**
    çalıştığını göstermek ve CPL/SQL hesaplamasının **kanıtlanabilir**
    olduğunu imzalı-raporla sunmaktır — gerçek-pilot-metriklerinin yerini
    almaz, onun için yer-tutar ( placeholder).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from yieldix.core.types import InboundLeadPayload, LeadSource
from yieldix.telemetry.kpi_collector import KPICollector
from yieldix.telemetry.reporter import MonthlyReportGenerator


@dataclass(frozen=True)
class PilotCompany:
    """Kurgusal pilot şirket — B2B hedef-profili ( ICP) parametreleri."""
    company_id: str
    company_name: str
    sector: str
    employee_band: str
    intent_weight: float      # 0.0–1.0: yüksek = daha nitelikli-lead eğilimi
    cpl_try: float            # bu şirket için beklenen lead-başı-maliyet (₺)
    sql_rate: float           # bu şirket için beklenen SQL dönüşüm oranı


@dataclass(frozen=True)
class PilotLeadRecord:
    """Pipeline'a işlenmiş bir pilot lead'in kanıt-kaydı."""
    lead_id: str
    company_id: str
    cycle_time_sec: float
    is_sql: bool
    cost_try: float
    has_error: bool
    escalated: bool


# --------------------------------------------------------------------------
# 12 kurgusal şirket — gerçekçi B2B segmenti ( Türkiye-odaklı ICP)
# Sabit-liste: deterministic, tekrar-oynanabilir, uydurma-kurumsal-veri-yok.
# --------------------------------------------------------------------------
PILOT_COMPANIES: tuple[PilotCompany, ...] = (
    PilotCompany("pilot-01", "Anadolu Lojistik A.Ş.", "Lojistik/Filo", "200-500", 0.78, 42.0, 0.19),
    PilotCompany("pilot-02", "Marmara Finans Danışmanlık", "Finans/Fintech", "50-200", 0.65, 88.0, 0.14),
    PilotCompany("pilot-03", "Ege Tekstil Sanayi", "Üretim/Textile", "500-1000", 0.44, 24.0, 0.08),
    PilotCompany("pilot-04", "Boğaziçi Sağlık Grubu", "Sağlık/Medtech", "200-500", 0.71, 115.0, 0.17),
    PilotCompany("pilot-05", " Kapadokya Turizm Holding", "Turizm/Otelcilik", "100-300", 0.38, 31.0, 0.09),
    PilotCompany("pilot-06", "Trakya Tarım Teknolojileri", "AgriTech", "50-200", 0.52, 27.0, 0.11),
    PilotCompany("pilot-07", "İstanbul Yapı ve İnşaat", "İnşaat/PropTech", "500-1000", 0.59, 96.0, 0.13),
    PilotCompany("pilot-08", "Erciyes Enerji Çözümleri", "Enerji/Cleantech", "200-500", 0.82, 134.0, 0.22),
    PilotCompany("pilot-09", "Akdeniz Perakende Zinciri", "Perakende/Retail", "1000+", 0.33, 19.0, 0.07),
    PilotCompany("pilot-10", "Ankara Hukuk & Danışmanlık", "Hukuk/LegalTech", "10-50", 0.67, 205.0, 0.15),
    PilotCompany("pilot-11", "Karadeniz Gıda Üretim", "Gıda/FoodTech", "300-600", 0.49, 36.0, 0.10),
    PilotCompany("pilot-12", "Teknopark Yapay-Zeka Stüdyosu", "AI/SaaS", "10-50", 0.88, 258.0, 0.21),
)


class SyntheticPilotDataset:
    """
    Deterministik B2B pilot veri seti üreticisi.

    Kullanım:
        ds = SyntheticPilotDataset(leads_per_company=25, seed=1337)
        records = ds.generate()
        report = ds.build_signed_report(records, tenant_id="pilot-demo")
    """

    def __init__(self, leads_per_company: int = 25, seed: int = 1337) -> None:
        if leads_per_company <= 0:
            raise ValueError(f"leads_per_company > 0 gerekir (got {leads_per_company})")
        self.leads_per_company = leads_per_company
        self.seed = seed

    # ---------------- üretim ----------------
    def generate(self) -> list[PilotLeadRecord]:
        """Kurallı pilot lead kayıtları üretir ( tamamen tekrar-oynanabilir)."""
        rng = random.Random(self.seed)
        records: list[PilotLeadRecord] = []
        seq = 0

        for company in PILOT_COMPANIES:
            for _ in range(self.leads_per_company):
                seq += 1
                # Cycle-time: sub-60s SLA hedefi; çoğunluk hızlı, kuyruk log-normal
                # benzeri uzun-kuyruk. 8–95 sn aralığı gerçek B2B aralığı.
                base = rng.lognormvariate(2.8, 0.55)  # ~16sn medyan, uzun kuyruk
                cycle = float(min(95.0, max(6.0, base)))

                # SQL olasılığı = şirket sql_rate * küçük gürültü
                p_sql = min(0.95, max(0.02, company.sql_rate * rng.uniform(0.85, 1.15)))
                is_sql = rng.random() < p_sql

                # Maliyet: SQL'ler daha pahalı ( insan-dokunuşu); CPL şirkete göre
                cost = company.cpl_try * (1.0 if is_sql else rng.uniform(0.25, 0.55))

                escalated = rng.random() < rng.uniform(0.03, 0.12)
                has_error = rng.random() < rng.uniform(0.005, 0.04)

                records.append(PilotLeadRecord(
                    lead_id=f"pilot_lead_{seq:05d}",
                    company_id=company.company_id,
                    cycle_time_sec=round(cycle, 2),
                    is_sql=is_sql,
                    cost_try=round(cost, 2),
                    has_error=has_error,
                    escalated=escalated,
                ))
        return records

    def to_inbound_payloads(
        self, records: list[PilotLeadRecord], tenant_id: str
    ) -> list[InboundLeadPayload]:
        """Kayıtları pipeline'ın gerçek girişine ( InboundLeadPayload) çevirir."""
        by_id = {c.company_id: c for c in PILOT_COMPANIES}
        out: list[InboundLeadPayload] = []
        for i, r in enumerate(records):
            comp = by_id[r.company_id]
            out.append(InboundLeadPayload(
                tenant_id=tenant_id,
                lead_id=r.lead_id,
                contact_name=f"{comp.company_name} Yetkilisi {i + 1}",
                contact_phone="+90850" + f"{2200000 + i:07d}",
                contact_email=None,
                source=LeadSource.MANUAL_IMPORT,
                intent_summary=f"{comp.sector} segmentinde kurumsal teklif talebi",
                timestamp_utc=float(i),
            ))
        return out

    # ---------------- KPI + imzalı-rapor ----------------
    def build_kpi_collector(
        self, records: list[PilotLeadRecord], tenant_id: str
    ) -> KPICollector:
        """Kayıtları KPI toplayıcısına işler ( CPL/SQL/p95 gerçek-hesaplaması)."""
        kpi = KPICollector(tenant_id=tenant_id)
        for r in records:
            kpi.record_lead_processed(
                lead_id=r.lead_id,
                cycle_time_sec=r.cycle_time_sec,
                is_sql=r.is_sql,
                cost_try=Decimal(str(r.cost_try)),
                has_error=r.has_error,
                escalated=r.escalated,
            )
        return kpi

    def build_signed_report(
        self,
        records: list[PilotLeadRecord],
        tenant_id: str,
        period_start: str = "2026-10-01",
        period_end: str = "2026-10-31",
        active_components: list[str] | None = None,
    ) -> tuple[Any, str, str]:
        """
        Pilot veri setinden Ed25519-imzalı aylık rapor üretir.

        Returns: ( MonthlyReportPayload, dataset_fingerprint_sha256,
                   public_key_hex)
        Public key döndürülür ki imza **bağımsız olarak** yeniden-doğrulansın
        ( her-rapor-yeni-anahtar-üretirse doğrulama imkânsız olurdu).
        """
        kpi = self.build_kpi_collector(records, tenant_id)
        gen = MonthlyReportGenerator()
        report = gen.generate_signed_report(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            kpi_collector=kpi,
            active_components=active_components or [
                "c1_receptionist", "c2_speed_to_lead", "c3_web_qualifier",
                "c4_crm_reactivation", "c5_cold_email_l2", "c6_inbox_triage",
            ],
        )
        fingerprint = self.dataset_fingerprint(records)
        return report, fingerprint, gen.signer.public_key_hex

    # ---------------- kanıt-parmakizi ----------------
    @staticmethod
    def dataset_fingerprint(records: list[PilotLeadRecord]) -> str:
        """
        SHA-256 parmakizi — deterministik kayıt-listesinin kanıtı.
        İmzalı-raporla birlikte doğrulanır: rapordaki CPL/SQL değerlerinin
        KAYNAĞI bu veri setidir.
        """
        import hashlib
        canonical = json.dumps(
            [asdict(r) for r in records],
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ---------------- diske-yaz / oku ----------------
    @staticmethod
    def write_json(records: list[PilotLeadRecord], path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {"companies": [asdict(c) for c in PILOT_COMPANIES],
                 "records": [asdict(r) for r in records],
                 "synthetic": True,
                 "note": "SENTETIK pilot veri — gercek musteri verisi DEGIL"},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        return p
