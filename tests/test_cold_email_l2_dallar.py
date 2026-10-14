"""
Dal-kesen (branch-cutting) testler: yieldix.cylinders.cold_email_l2

Kapsanan public API (src/yieldix/cylinders/cold_email_l2.py):
  * ColdEmailL2Manager.__init__
  * ColdEmailL2Manager.verify_domain_deliverability
  * ColdEmailL2Manager.enqueue_outbound_draft
  * ColdEmailL2Manager.review_draft
  * ColdEmailL2Manager.get_pending_tasks

ONEMLI: verify_domain_deliverability canli DNS sorgular (dns.resolver).
Kural-4 geregi gercek ag cagrisi YAPILMAZ — dns paketi sys.modules'e
fake modul olarak yerlestirilir (monkeypatch ile, test sonunda geri alinir).
Tum testler saf in-memory'dir.

DAL LISTESI (her dal icin en az bir test):
  [__init__]
    D1  tenant_id saklanir
    D2  varsayilan daily_quota = 35
    D3  ozel daily_quota saklanir
  [verify_domain_deliverability]
    D4  SPF + DMARC p=reject -> tam saglikli
    D5  DMARC p=quarantine -> saglikli (reject|quarantine dali)
    D6  yalnizca SPF (DMARC yok) -> saglikli degil
    D7  DMARC p=none -> reddedilir (izleme politikasi yetersiz)
    D8  SPF oneksiz ("include:..." ) -> spf_valid False
    D9  DMARC kaydi tamamen yok -> dmarc_reject_policy False
    D10 bilinmeyen politika degeri ("p=sternly-worded-letter") -> False
    D11 buyuk/kucuk duyarsizlik + TXT tirnak-soyumu
    D12 birden fazla TXT arasinda SPF bulunur
    D13 DMARC noktali-virgul-sonrasi politika (bosluklu) -> gecerli
    D14 DNS hatasi (NXDOMAIN/SERVFAIL) -> fail-closed tum bayraklar False
    D15 dkim_valid her zaman False (selector domain seviyesinde bilinemez)
    D16 apex + _dmarc.<domain> sorgulanir
  [enqueue_outbound_draft]
    D17 saglikli domain -> "l2_<ms>_<lead_id>" formatinda task_id doner
    D18 kirli domain -> ValueError firlatir
    D19 eklenen task PENDING statundedir
    D20 task tenant/recipient/subject/body degerlerini tasir
    D21 company_domain verilmezse varsayilan kullanilir
    D22 iki ekleme farkli task_id uretir
    D23 queue boyutu her eklemeye artar
  [review_draft]
    D24 onay: PENDING -> APPROVED, True doner
    D25 onay _sent_today_count sayacini artirir
    D26 onay + modified_body -> govde guncellenir
    D27 onay + modified_body=None -> govde degismez
    D28 red -> REJECTED, True doner, sayac ARTMAZ
    D29 bilinmeyen task_id -> False
    D30 zaten onaylanmis taski tekrar inceleme -> False (idempotens)
    D31 reddedilmis taski tekrar inceleme -> False
    D32 kota dolmusken onay -> False (kota sinir dali)
    D33 reviewed_by / reviewed_at ayarlanir
  [get_pending_tasks]
    D34 yalnizca PENDING tasklari doner
    D35 bos queue -> bos liste
    D36 incelemeden sonra task pending listesinden cikar
"""

from __future__ import annotations

import sys
import types

import pytest

from yieldix.core.types import TaskStatus
from yieldix.cylinders.cold_email_l2 import ColdEmailL2Manager


# ---------------------------------------------------------------------------
# fake DNS (sys.modules stub — gercek ag YOK, Kural-4)
# ---------------------------------------------------------------------------
class _FakeTXT:
    """dns.resolver TXT kaydi: str() tirnakli metin dondurur (gercekte oldugu gibi)."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text


class _FakeResolveError(Exception):
    """NXDOMAIN / SERVFAIL / timeout taklidi."""


class _FakeResolver:
    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._m = {k.lower(): v for k, v in mapping.items()}
        self.calls: list[tuple[str, str]] = []

    def resolve(self, name: str, rdtype: str, lifetime=None):
        self.calls.append((name, rdtype))
        key = name.lower()
        if key not in self._m:
            raise _FakeResolveError(name)
        return [_FakeTXT(t) for t in self._m[key]]


class _RaiseResolver(_FakeResolver):
    """Her sorguda hata firlatarak fail-closed dalini zorlar."""

    def resolve(self, name, rdtype, lifetime=None):
        raise _FakeResolveError(name)


@pytest.fixture
def fake_dns(monkeypatch):
    """dns paketini sys.modules'e fake olarak yerlestirir (MOCK, ag YOK)."""

    def _install(mapping, raise_on=False):
        resolver = _RaiseResolver(mapping) if raise_on else _FakeResolver(mapping)
        pkg = types.ModuleType("dns")
        pkg.resolver = resolver
        pkg.exception = types.ModuleType("dns.exception")
        monkeypatch.setitem(sys.modules, "dns", pkg)
        monkeypatch.setitem(sys.modules, "dns.resolver", resolver)
        monkeypatch.setitem(sys.modules, "dns.exception", pkg.exception)
        return resolver

    return _install


@pytest.fixture
def saglikli_dns(fake_dns):
    """Saglikli domain icin hazir fake DNS (SPF + DMARC reject)."""
    return fake_dns({
        "saglikli.com": ['"v=spf1 include:_spf.saglikli.com ~all"'],
        "_dmarc.saglikli.com": ['"v=DMARC1; p=reject; rua=mailto:d@saglikli.com"'],
    })


def _manager(quota: int = 35) -> ColdEmailL2Manager:
    return ColdEmailL2Manager(tenant_id="test_dal", daily_quota=quota)


def _enqueue(manager: ColdEmailL2Manager, lead_id: str = "lead-1",
             domain: str = "saglikli.com") -> str:
    return manager.enqueue_outbound_draft(
        lead_id=lead_id,
        recipient_email=f"{lead_id}@saglikli.com",
        subject="Konu",
        body_text="Gövde",
        company_domain=domain,
    )


class TestInit:
    """__init__ — yapilandirma dallari."""

    def test_tenant_id_saklanir(self):
        """D1: tenant_id atanir."""
        m = ColdEmailL2Manager(tenant_id="musteri-99")
        assert m.tenant_id == "musteri-99"

    def test_varsayilan_kota_35(self):
        """D2: daily_quota varsayilani 35'tir."""
        assert ColdEmailL2Manager(tenant_id="t").daily_quota == 35

    def test_ozel_kota_saklanir(self):
        """D3: ozel daily_quota saklanir."""
        assert ColdEmailL2Manager(tenant_id="t", daily_quota=5).daily_quota == 5


class TestVerifyDomainDeliverability:
    """verify_domain_deliverability — SPF/DMARC ayristirma + fail-closed."""

    def test_spf_dmarc_reject_tam_saglikli(self, fake_dns):
        """D4: SPF + DMARC p=reject -> tum bayraklar dogru."""
        fake_dns({
            "ornek.com": ['"v=spf1 include:_spf.ornek.com ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=reject; rua=mailto:d@ornek.com"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc == {
            "spf_valid": True,
            "dkim_valid": False,
            "dmarc_reject_policy": True,
            "deliverability_healthy": True,
        }

    def test_dmarc_quarantine_da_saglikli(self, fake_dns):
        """D5: p=quarantine de reject|quarantine dalindan saglikli sayilir."""
        fake_dns({
            "ornek.com": ['"v=spf1 -all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=quarantine"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["dmarc_reject_policy"] is True
        assert sonuc["deliverability_healthy"] is True

    def test_yalnizca_spf_sagliksiz(self, fake_dns):
        """D6: DMARC kaydi yok -> saglikli degil."""
        fake_dns({
            "ornek.com": ['"v=spf1 include:_spf.ornek.com ~all"'],
            "_dmarc.ornek.com": [],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["spf_valid"] is True
        assert sonuc["dmarc_reject_policy"] is False
        assert sonuc["deliverability_healthy"] is False

    def test_dmarc_none_politikasi_reddedilir(self, fake_dns):
        """D7: p=none izleme politikasi yetersiz -> saglikli degil."""
        fake_dns({
            "ornek.com": ['"v=spf1 ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=none; rua=mailto:d@ornek.com"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["dmarc_reject_policy"] is False
        assert sonuc["deliverability_healthy"] is False

    def test_spf_prefix_olmadan_gecersiz(self, fake_dns):
        """D8: 'include:...' v=spf1 oneksiz -> spf_valid False."""
        fake_dns({
            "ornek.com": ['"include:_spf.ornek.com ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["spf_valid"] is False
        assert sonuc["deliverability_healthy"] is False

    def test_dmarc_prefix_olmadan_gecersiz(self, fake_dns):
        """D9: DMARC 'v=DMARC1' prefixi yok -> dmarc_reject_policy False."""
        fake_dns({
            "ornek.com": ['"v=spf1 ~all"'],
            "_dmarc.ornek.com": ['"p=reject"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["dmarc_reject_policy"] is False

    def test_dmarc_bilinmeyen_politika_gecersiz(self, fake_dns):
        """D10: 'p=sternly-worded-letter' gibi bilinmeyen deger -> False."""
        fake_dns({
            "ornek.com": ['"v=spf1 ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=sternly-worded-letter"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["dmarc_reject_policy"] is False

    def test_case_insensitive_ve_tirnak_soyumu(self, fake_dns):
        """D11: buyuk/kucuk duyarsiz; TXT tirnaklari soyulur."""
        fake_dns({
            "ORNEK.COM": ['"V=SPF1 include:x ~all"', '"diger txt"'],
            "_dmarc.ORNEK.COM": ['"V=Dmarc1; P=REJECT"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["spf_valid"] is True
        assert sonuc["dmarc_reject_policy"] is True
        assert sonuc["deliverability_healthy"] is True

    def test_birden_fazla_txt_arasinda_spf_bulunur(self, fake_dns):
        """D12: TXT kumesinde diger kayitlarin arasinda SPF bulunur."""
        fake_dns({
            "ornek.com": ['"google-site-verification=abc"',
                         '"v=spf1 include:_spf.ornek.com -all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["spf_valid"] is True
        assert sonuc["deliverability_healthy"] is True

    def test_dmarc_bosluklu_politika_gecerli(self, fake_dns):
        """D13: 'v=DMARC1; p=reject' noktali-virgul-sonrasi parse edilir."""
        fake_dns({
            "ornek.com": ['"v=spf1 ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
        })
        sonuc = _manager().verify_domain_deliverability("ornek.com")
        assert sonuc["dmarc_reject_policy"] is True

    def test_dns_hatasi_fail_closed(self, fake_dns):
        """D14: NXDOMAIN/SERVFAIL -> fail-closed, tum bayraklar False."""
        fake_dns({}, raise_on=True)
        sonuc = _manager().verify_domain_deliverability("mevcut-olmayan.domain")
        assert sonuc == {
            "spf_valid": False,
            "dkim_valid": False,
            "dmarc_reject_policy": False,
            "deliverability_healthy": False,
        }

    def test_dkim_her_zaman_false(self, fake_dns):
        """D15: dkim_valid her zaman False (selector domain seviyesinde bilinemez)."""
        fake_dns({
            "ornek.com": ['"v=spf1 ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
        })
        assert _manager().verify_domain_deliverability("ornek.com")["dkim_valid"] is False

    def test_apex_ve_dmarc_alt_domeni_sorgulanir(self, fake_dns):
        """D16: hem apex hem _dmarc.<domain> sorgulanir."""
        resolver = fake_dns({
            "ornek.com": ['"v=spf1 ~all"'],
            "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
        })
        _manager().verify_domain_deliverability("ornek.com")
        sorgular = {name for name, _rdtype in resolver.calls}
        assert "ornek.com" in sorgular
        assert "_dmarc.ornek.com" in sorgular


class TestEnqueueOutboundDraft:
    """enqueue_outbound_draft — L2 insan-onay kuyrugu."""

    def test_saglikli_domain_task_id_donar(self, saglikli_dns):
        """D17: saglikli domain -> 'l2_<ms>_<lead_id>' formatinda task_id."""
        task_id = _enqueue(_manager(), lead_id="lead-42")
        assert task_id.startswith("l2_")
        assert task_id.endswith("_lead-42")

    def test_kirli_domain_value_error(self, fake_dns):
        """D18: sagliksiz domain -> ValueError (queue'ya hicbir sey eklenmez)."""
        fake_dns({
            "kirli.com": ['"v=spf1 ~all"'],
            "_dmarc.kirli.com": [],  # DMARC yok -> sagliksiz
        })
        m = _manager()
        with pytest.raises(ValueError):
            _enqueue(m, domain="kirli.com")
        assert m.get_pending_tasks() == []

    def test_eklenen_task_pending(self, saglikli_dns):
        """D19: eklenen task PENDING statundedir."""
        m = _manager()
        task_id = _enqueue(m)
        assert m._queue[task_id]["status"] == TaskStatus.PENDING

    def test_task_alanlari_tasir(self, saglikli_dns):
        """D20: task tenant/recipient/subject/body degerlerini tasir."""
        m = _manager()
        task_id = _enqueue(m, lead_id="lead-1")
        task = m._queue[task_id]
        assert task["tenant_id"] == "test_dal"
        assert task["lead_id"] == "lead-1"
        assert task["recipient_email"] == "lead-1@saglikli.com"
        assert task["subject"] == "Konu"
        assert task["body_text"] == "Gövde"
        assert task["reviewed_at"] is None
        assert task["reviewed_by"] is None

    def test_varsayilan_company_domain_kullanilir(self, saglikli_dns):
        """D21: company_domain verilmezse varsayilan 'outbound.yieldix.internal'."""
        fake = saglikli_dns  # fixture zaten kurulu; varsayilan domain icin ayri kayit
        fake._m["outbound.yieldix.internal"] = ['"v=spf1 ~all"']
        fake._m["_dmarc.outbound.yieldix.internal"] = ['"v=DMARC1; p=reject"']
        m = _manager()
        task_id = m.enqueue_outbound_draft(
            lead_id="lead-x", recipient_email="x@y.com",
            subject="s", body_text="b",
        )
        assert task_id in m._queue

    def test_iki_ekleme_farkli_task_id(self, saglikli_dns):
        """D22: iki ekleme farkli task_id uretir (lead_id ayri)."""
        m = _manager()
        a = _enqueue(m, lead_id="a")
        b = _enqueue(m, lead_id="b")
        assert a != b

    def test_queue_buyur(self, saglikli_dns):
        """D23: her eklemede queue boyutu artar."""
        m = _manager()
        assert len(m.get_pending_tasks()) == 0
        _enqueue(m, lead_id="a")
        assert len(m.get_pending_tasks()) == 1
        _enqueue(m, lead_id="b")
        assert len(m.get_pending_tasks()) == 2


class TestReviewDraft:
    """review_draft — insan-onay / red isleme."""

    def test_onay_pending_approved(self, saglikli_dns):
        """D24: PENDING task onaylanirsa APPROVED olur ve True doner."""
        m = _manager()
        task_id = _enqueue(m)
        assert m.review_draft(task_id, approve=True, reviewer="ahmet") is True
        assert m._queue[task_id]["status"] == TaskStatus.APPROVED

    def test_onay_sayaci_artirir(self, saglikli_dns):
        """D25: her onay _sent_today_count sayacini 1 artirir."""
        m = _manager()
        t1 = _enqueue(m, lead_id="a")
        t2 = _enqueue(m, lead_id="b")
        assert m._sent_today_count == 0
        m.review_draft(t1, approve=True, reviewer="ahmet")
        assert m._sent_today_count == 1
        m.review_draft(t2, approve=True, reviewer="ahmet")
        assert m._sent_today_count == 2

    def test_onay_modified_body_govde_gunceller(self, saglikli_dns):
        """D26: onay + modified_body -> govde degistirilir."""
        m = _manager()
        task_id = _enqueue(m)
        m.review_draft(task_id, approve=True, reviewer="ahmet",
                       modified_body="Düzeltilmiş gövde")
        assert m._queue[task_id]["body_text"] == "Düzeltilmiş gövde"

    def test_onay_modified_body_none_govde_degismez(self, saglikli_dns):
        """D27: onay + modified_body=None -> orijinal govde korunur."""
        m = _manager()
        task_id = _enqueue(m)
        m.review_draft(task_id, approve=True, reviewer="ahmet")
        assert m._queue[task_id]["body_text"] == "Gövde"

    def test_red_rejected_sayac_artmaz(self, saglikli_dns):
        """D28: red -> REJECTED, True doner, gonderim sayaci ARTMAZ."""
        m = _manager()
        task_id = _enqueue(m)
        assert m.review_draft(task_id, approve=False, reviewer="ahmet") is True
        assert m._queue[task_id]["status"] == TaskStatus.REJECTED
        assert m._sent_today_count == 0

    def test_bilinmeyen_task_false(self, saglikli_dns):
        """D29: queue'da olmayan task_id -> False."""
        m = _manager()
        assert m.review_draft("l2_yok_olsun", approve=True, reviewer="ahmet") is False

    def test_zaten_onaylanmis_task_false(self, saglikli_dns):
        """D30: ikinci kez onay incelemesi -> False (idempotens)."""
        m = _manager()
        task_id = _enqueue(m)
        assert m.review_draft(task_id, approve=True, reviewer="ahmet") is True
        assert m.review_draft(task_id, approve=True, reviewer="ahmet") is False

    def test_reddedilmis_task_tekrar_false(self, saglikli_dns):
        """D31: reddedilmis taski tekrar inceleme -> False."""
        m = _manager()
        task_id = _enqueue(m)
        m.review_draft(task_id, approve=False, reviewer="ahmet")
        assert m.review_draft(task_id, approve=True, reviewer="ahmet") is False
        assert m._queue[task_id]["status"] == TaskStatus.REJECTED

    def test_kota_dolmusken_onay_false(self, saglikli_dns):
        """D32: daily_quota=1 iken 2. onay -> False (kota sinir dali)."""
        m = _manager(quota=1)
        t1 = _enqueue(m, lead_id="a")
        t2 = _enqueue(m, lead_id="b")
        assert m.review_draft(t1, approve=True, reviewer="ahmet") is True
        assert m.review_draft(t2, approve=True, reviewer="ahmet") is False
        # kota dolu: ikinci task PENDING'de mahsur kaldi
        assert m._queue[t2]["status"] == TaskStatus.PENDING

    def test_reviewed_by_ve_at_ayarlanir(self, saglikli_dns):
        """D33: inceleme sonrasi reviewed_by ve reviewed_at dolar."""
        m = _manager()
        task_id = _enqueue(m)
        m.review_draft(task_id, approve=True, reviewer="zeynep")
        assert m._queue[task_id]["reviewed_by"] == "zeynep"
        assert m._queue[task_id]["reviewed_at"] is not None


class TestGetPendingTasks:
    """get_pending_tasks — PENDING kuyruk gorunumu."""

    def test_yalnizca_pending_donar(self, saglikli_dns):
        """D34: yalnizca PENDING statundeki tasklar listelenir."""
        m = _manager()
        t1 = _enqueue(m, lead_id="a")
        t2 = _enqueue(m, lead_id="b")
        t3 = _enqueue(m, lead_id="c")
        m.review_draft(t1, approve=True, reviewer="ahmet")
        m.review_draft(t2, approve=False, reviewer="ahmet")
        pending = m.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0]["task_id"] == t3

    def test_bos_queue_bos_liste(self, saglikli_dns):
        """D35: bos queue -> bos liste."""
        assert _manager().get_pending_tasks() == []

    def test_incelemeden_sonra_pending_cikar(self, saglikli_dns):
        """D36: onaydan sonra task pending listesinden cikarilir."""
        m = _manager()
        task_id = _enqueue(m)
        assert len(m.get_pending_tasks()) == 1
        m.review_draft(task_id, approve=True, reviewer="ahmet")
        assert m.get_pending_tasks() == []
