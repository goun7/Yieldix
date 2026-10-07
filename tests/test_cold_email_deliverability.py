"""YENI test: ColdEmailL2Manager.verify_domain_deliverability — anti-spam
DMARC/SPF dogrulama mantigi (fail-closed).

Kapsanan test-disi public fonksiyon (58 satir):
  - verify_domain_deliverability (cylinders/cold_email_l2.py:28-85)

Mevcut testler bu fonksiyonu yalnizca GERCEK DNS uzerinden (google.com /
broken.domain) ve enqueue_outbound_draft icinden dolayli exercise etti —
SPF/DMARC ayristirma mantigi (reject/quarantine tespiti, tirnak-soyumu,
case-insensitivity) HIC dogrudan test edilmedi. Burada dns.resolver
sys.modules'e fake modul olarak yerlestirildi (MOCK — dis ag cagrisi YOK);
yalnizca fonksiyonun KENDI mantigi test edildi.
"""
from __future__ import annotations

import sys
import types

import pytest

from yieldix.cylinders.cold_email_l2 import ColdEmailL2Manager


class _FakeTXT:
    """dns.resolver TXT kaydi: str() tirnakli metin dondurur (gercekte oldugu gibi)."""

    def __init__(self, text: str):
        self._text = text

    def __str__(self):
        return self._text


class _FakeResolveError(Exception):
    """NXDOMAIN/SERVFAIL/timeout taklidi."""


class _FakeResolver:
    def __init__(self, mapping: dict[str, list[str]]):
        self._m = {k.lower(): v for k, v in mapping.items()}
        self.calls: list[tuple[str, str]] = []

    def resolve(self, name: str, rdtype: str, lifetime=None):
        self.calls.append((name, rdtype))
        key = name.lower()
        if key not in self._m:
            raise _FakeResolveError(name)
        return [_FakeTXT(t) for t in self._m[key]]


@pytest.fixture
def install_fake_dns(monkeypatch):
    """dns paketini sys.modules'e fake olarak yerlestirir (MOCK)."""

    def _install(mapping, raise_on=None):
        resolver = _FakeResolver(mapping)

        class _RaiseResolver(_FakeResolver):
            def resolve(self, name, rdtype, lifetime=None):
                raise _FakeResolveError(name)

        kullanilacak = _RaiseResolver(mapping) if raise_on else resolver
        pkg = types.ModuleType("dns")
        pkg.resolver = kullanilacak
        pkg.exception = types.ModuleType("dns.exception")
        monkeypatch.setitem(sys.modules, "dns", pkg)
        monkeypatch.setitem(sys.modules, "dns.resolver", kullanilacak)
        monkeypatch.setitem(sys.modules, "dns.exception", pkg.exception)
        return kullanilacak

    return _install


def _manager():
    return ColdEmailL2Manager(tenant_id="test_deliverability")


# ---------------------------------------------------------------------------
# saglikli domain
# ---------------------------------------------------------------------------
def test_saglikli_domain_hepsi_gecerli(install_fake_dns):
    install_fake_dns({
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


def test_dmarc_quarantine_da_saglikli(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"v=spf1 -all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=quarantine"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["dmarc_reject_policy"] is True
    assert sonuc["deliverability_healthy"] is True


# ---------------------------------------------------------------------------
# eksik/zayif kayitlar
# ---------------------------------------------------------------------------
def test_yalnizca_spf_sagliksiz(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"v=spf1 include:_spf.ornek.com ~all"'],
        "_dmarc.ornek.com": [],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["spf_valid"] is True
    assert sonuc["dmarc_reject_policy"] is False
    assert sonuc["deliverability_healthy"] is False


def test_dmarc_none_politikasi_reddedilir(install_fake_dns):
    """p=none izleme politikasi deliverability icin yeterli degil."""
    install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=none; rua=mailto:d@ornek.com"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["dmarc_reject_policy"] is False
    assert sonuc["deliverability_healthy"] is False


def test_spf_prefix_olmadan_gecersiz(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"include:_spf.ornek.com ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["spf_valid"] is False
    assert sonuc["deliverability_healthy"] is False


def test_dmarc_prefix_olmadan_gecersiz(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"p=reject"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["dmarc_reject_policy"] is False


def test_dmarc_bilinmeyen_politika_degeri_gecersiz(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=sternly-worded-letter"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["dmarc_reject_policy"] is False


# ---------------------------------------------------------------------------
# metin ayristirma detaylari
# ---------------------------------------------------------------------------
def test_tirnak_soyumu_ve_case_insensitivity(install_fake_dns):
    """dns TXT'leri tirnakli gelir; basliklar buyuk/kucuk harf duyarsiz."""
    install_fake_dns({
        "ORNEK.COM": ['"V=SPF1 include:x ~all"', '"diger txt"'],
        "_dmarc.ORNEK.COM": ['"V=Dmarc1; P=REJECT"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["spf_valid"] is True
    assert sonuc["dmarc_reject_policy"] is True
    assert sonuc["deliverability_healthy"] is True


def test_birden_fazla_txt_arasinda_spf_bulunur(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"google-site-verification=abc"',
                     '"v=spf1 include:_spf.ornek.com -all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["spf_valid"] is True
    assert sonuc["deliverability_healthy"] is True


def test_dmarc_noktali_virgulsuz_politika_gecerli(install_fake_dns):
    """Tek policy ifadesi 'v=DMARC1; p=reject' formatinda (bosluklu)."""
    install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["dmarc_reject_policy"] is True


# ---------------------------------------------------------------------------
# fail-closed (dis hata durumlari)
# ---------------------------------------------------------------------------
def test_nxdomain_fail_closed(install_fake_dns):
    install_fake_dns({}, raise_on=True)
    sonuc = _manager().verify_domain_deliverability("mevcut-olmayan.domain")
    assert sonuc == {
        "spf_valid": False,
        "dkim_valid": False,
        "dmarc_reject_policy": False,
        "deliverability_healthy": False,
    }


def test_dns_hatasi_fail_closed(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
    }, raise_on=True)
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    # servis-yok/timeout → tum bayraklar False (dogrulanamaz domain
    # ASLA deliverable raporlanmaz)
    assert sonuc["deliverability_healthy"] is False
    assert sonuc["spf_valid"] is False


# ---------------------------------------------------------------------------
# dkim her zaman False (selector domain seviyesinde bilinemez — dokumante)
# ---------------------------------------------------------------------------
def test_dkim_her_zaman_false(install_fake_dns):
    install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
    })
    sonuc = _manager().verify_domain_deliverability("ornek.com")
    assert sonuc["dkim_valid"] is False


# ---------------------------------------------------------------------------
# cagri yonu: _dmarc alt-domeni sorgulanir
# ---------------------------------------------------------------------------
def test_dmarc_alt_domeni_sorgulanir(install_fake_dns):
    resolver = install_fake_dns({
        "ornek.com": ['"v=spf1 ~all"'],
        "_dmarc.ornek.com": ['"v=DMARC1; p=reject"'],
    })
    _manager().verify_domain_deliverability("ornek.com")
    sorgular = {name for name, _rdtype in resolver.calls}
    assert "ornek.com" in sorgular
    assert "_dmarc.ornek.com" in sorgular
