"""
Dal-kesen (branch-cutting) testler: yieldix.cylinders.web_qualifier

Kapsanan public API (src/yieldix/cylinders/web_qualifier.py):
  * WebQualifier(tenant_id).evaluate_initial_bant(...)

DAL LISTESI (her dal icin en az bir test):
  [evaluate_initial_bant — budget]
    D1  budget_answer truthy ANCAK hicbir anahtar-kelime icermiyor -> 15.0
        (elif "butce yok" -in False-dali: 41->45)
    D2  budget_answer None -> baz 15.0
    D3  budget_answer bos-dizi "" (falsy) -> 15.0
    D4  "100k"/"kurumsal" anahtar-kelimeleri -> 25.0 (buyuk/kucuk-harf duyarsiz)
    D5  "25k" anahtar-kelimesi -> 18.0
    D6  "butce yok" anahtar-kelimesi -> 5.0 (en-dusuk sinir)
  [evaluate_initial_bant — authority]
    D7  authority_answer truthy ANCAK anahtar-kelime YOK -> 15.0 (49->53)
    D8  "sahip/kurucu/ceo/direktor/mudur" -> 25.0
    D9  "ekip" -> 15.0 (elif-dali, ust-deger degil)
  [evaluate_initial_bant — need]
    D10 intent_summary BOŞ (varsayilan "") -> 18.0
    D11 intent_summary tam 20-karakter (sinir-Disi: > 20 False) -> 18.0
    D12 intent_summary 21-karakter (sinir-ici) -> 22.0
    D13 uzun-intent + ehemmiyetsiz kelimeler -> 22.0 ( uzunluk yeterli)
  [evaluate_initial_bant — timeline]
    D14 timeline_answer truthy ANCAK anahtar-kelime YOK -> 15.0 (62->65)
    D15 "hemen"/"bu ay" -> 25.0
    D16 "gelecek yil" -> 8.0
  [fail-closed / yanlis-tip]
    D17 budget_answer int (yanlis-tip) -> TypeError ( sessiz-puanlama YOK)
    D18 authority_answer int -> TypeError
    D19 timeline_answer None -> 15.0 ( guvenli-varsayilan)
  [butunlesik-matematik]
    D20 tum-yanitlar-en-iyi -> total_score 100.0 ve is_sql True
    D21 tum-yanitlar-en-kotu -> total_score 15+15+5+8=43.0 ve is_sql False
    D22 BANTScore sinitlari: her-alan [0.0, 25.0] arasinda kalir
    D23 doneus-tipi BANTScore'dur ( yanlis-tip degil)
    D24 ayni-giris Deterministik ( iki-cagri ayni skor)
"""

from __future__ import annotations

import pytest

from yieldix.core.types import BANTScore, InboundLeadPayload, LeadSource
from yieldix.cylinders.web_qualifier import WebQualifier


def _lead(intent: str = "") -> InboundLeadPayload:
    """Saf-bellek lead-fixture'i ( network/DNS YOK)."""
    return InboundLeadPayload(
        tenant_id="tenant_dallar",
        lead_id="lead_dallar_001",
        contact_name="Test Kullanici",
        contact_phone="+905551112233",
        source=LeadSource.WEB_FORM,
        intent_summary=intent,
    )


class TestBudgetDallari:
    """budget_answer — 15.0 baz + 3 anahtar-kelime dali (D1-D6)."""

    def test_d1_anahtarsiz_truthy_yanit_baz_skor(self):
        q = WebQualifier(tenant_id="t")
        skor = q.evaluate_initial_bant(_lead(), budget_answer="yaklasik 50 bin TL")
        assert skor.budget == 15.0  # elif "butce yok" False-dali (41->45)

    def test_d2_yanit_none_baz_skor(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(_lead()).budget == 15.0

    def test_d3_bos_dizi_yanit_baz_skor(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(_lead(), budget_answer="").budget == 15.0

    def test_d4_buyuk_kurumsal_anahtar(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), budget_answer="KURUMSAL 100k paket").budget == 25.0

    def test_d5_yirmibesk_anahtar(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), budget_answer="25k alt sinir").budget == 18.0

    def test_d6_butce_yok_en_dusuk(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), budget_answer="suan bütçe yok").budget == 5.0


class TestAuthorityDallari:
    """authority_answer — 15.0 baz + karar-verici/ekip dallari (D7-D9)."""

    def test_d7_anahtarsiz_truthy_yanit_baz_skor(self):
        q = WebQualifier(tenant_id="t")
        skor = q.evaluate_initial_bant(
            _lead(), authority_answer="saha uzmaniyim, teknik ekibimle bakacagiz")
        assert skor.authority == 15.0  # "ekip" YOK, karar-verici YOK -> 49->53

    def test_d8_karar_verici_anahtar_en_yuksek(self):
        q = WebQualifier(tenant_id="t")
        for kelime in ("sahip", "kurucu", "ceo", "direktör", "müdür"):
            skor = q.evaluate_initial_bant(
                _lead(), authority_answer=f"ben {kelime}yim")
            assert skor.authority == 25.0, f"{kelime} 25.0 vermeli"

    def test_d9_ekip_anahtari_baz_skoru_korur(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), authority_answer="ekip elemaniyim").authority == 15.0


class TestNeedDallari:
    """need_answer yerine intent_summary uzunlugu — sinir 20 (D10-D13)."""

    def test_d10_bos_intent_baz(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(_lead("")).need == 18.0

    def test_d11_tam_yirmi_karakter_sinir_disi(self):
        q = WebQualifier(tenant_id="t")
        # tam 20-karakter: > 20 False -> 18.0
        assert q.evaluate_initial_bant(_lead("a" * 20)).need == 18.0

    def test_d12_yirmibir_karakter_sinir_ici(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(_lead("a" * 21)).need == 22.0

    def test_d13_uzun_intent_ihmal_edilebilir_kelimelerle(self):
        q = WebQualifier(tenant_id="t")
        skor = q.evaluate_initial_bant(
            _lead("selam nasilsiniz bugun hava cok guzel degil mi acep"))
        assert skor.need == 22.0  # uzunluk dongu-kriteri, anahtar-kelime DEGIL


class TestTimelineDallari:
    """timeline_answer — 15.0 baz + acil/gelecek-yil dallari (D14-D16)."""

    def test_d14_anahtarsiz_truthy_yanit_baz_skor(self):
        q = WebQualifier(tenant_id="t")
        skor = q.evaluate_initial_bant(
            _lead(), timeline_answer="once ic toplantimizi yapalim, sonra karar")
        assert skor.timeline == 15.0  # "hemeN"/"bu ay"/"gelecek yil" YOK (62->65)

    def test_d15_hemen_anahtar_en_yuksek(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), timeline_answer="hemen baslamak istiyoruz").timeline == 25.0

    def test_d15b_bu_ay_anahtar(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), timeline_answer="bu ay icinde alabilir miyiz").timeline == 25.0

    def test_d16_gelecek_yil_en_dusuk(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), timeline_answer="gelecek yıl baharinda").timeline == 8.0


class TestFailClosed:
    """Yanlis-tip girisleri sessiz-puanlamaya izin VERMEZ (D17-D19)."""

    def test_d17_budget_int_tip_hatasi(self):
        q = WebQualifier(tenant_id="t")
        with pytest.raises(TypeError):
            q.evaluate_initial_bant(_lead(), budget_answer=50000)

    def test_d18_authority_int_tip_hatasi(self):
        # dikkat: budget int->TypeError ama authority int->AttributeError
        # (.lower-int'ta YOK) — sessiz-puanlama YINE engellenir (fail-closed)
        q = WebQualifier(tenant_id="t")
        with pytest.raises(AttributeError):
            q.evaluate_initial_bant(_lead(), authority_answer=7)

    def test_d19_timeline_none_guvenli_baz(self):
        q = WebQualifier(tenant_id="t")
        assert q.evaluate_initial_bant(
            _lead(), timeline_answer=None).timeline == 15.0


class TestButunlesikMatematik:
    """BANTScore butunlesik-matematik + sinirlar + determinizm (D20-D24)."""

    def test_d20_tum_en_iyi_sql_true(self):
        q = WebQualifier(tenant_id="t")
        uzun = "Kurumsal B2B yazilim teklifi: 200 kullanicili plan"
        skor = q.evaluate_initial_bant(
            _lead(uzun),
            budget_answer="kurumsal 100k",
            authority_answer="bana müdür diyebilirsiniz",
            timeline_answer="hemen",
        )
        assert skor.budget == 25.0
        assert skor.authority == 25.0
        assert skor.need == 22.0
        assert skor.timeline == 25.0
        assert skor.total_score == pytest.approx(97.0)
        assert skor.is_sql is True

    def test_d21_tum_en_kotu_sql_false(self):
        q = WebQualifier(tenant_id="t")
        skor = q.evaluate_initial_bant(
            _lead("kisa"),
            budget_answer="hiç bütçe yok suan",
            authority_answer="ekip uyesiyim",
            timeline_answer="gelecek yıl belki",
        )
        assert skor.budget == 5.0
        assert skor.authority == 15.0
        assert skor.need == 18.0
        assert skor.timeline == 8.0
        assert skor.total_score == pytest.approx(46.0)
        assert skor.is_sql is False

    def test_d22_alan_sinirlari_sifir_yirmibes(self):
        q = WebQualifier(tenant_id="t")
        for uzun in ("", "a" * 5, "a" * 200):
            for b in (None, "", "25k", "100k", "bütçe yok"):
                skor = q.evaluate_initial_bant(_lead(uzun), budget_answer=b)
                assert 0.0 <= skor.budget <= 25.0
                assert 0.0 <= skor.authority <= 25.0
                assert 0.0 <= skor.need <= 25.0
                assert 0.0 <= skor.timeline <= 25.0
                # total_score hep 4-alanin-toplami ( toplamada bozulma YOK)
                assert skor.total_score == pytest.approx(
                    skor.budget + skor.authority + skor.need + skor.timeline)

    def test_d23_donus_tipi_bantscore(self):
        q = WebQualifier(tenant_id="t")
        skor = q.evaluate_initial_bant(_lead("test intent summary"))
        assert isinstance(skor, BANTScore)

    def test_d24_determinizm_ayni_giris_ayni_skor(self):
        q = WebQualifier(tenant_id="t")
        lead = _lead("Kurumsal filo kiralama hakkinda acil bilgi")
        a = q.evaluate_initial_bant(lead, budget_answer="100k",
                                    authority_answer="müdürüm",
                                    timeline_answer="bu ay")
        b = q.evaluate_initial_bant(lead, budget_answer="100k",
                                    authority_answer="müdürüm",
                                    timeline_answer="bu ay")
        # frozen-model: esitlik karsilastirmasi guvenli
        assert a.budget == b.budget
        assert a.total_score == b.total_score
        assert a.is_sql == b.is_sql
