r"""99-Yieldix mesh.tamga_anchor JCS + zincir dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory ( DIS-AG/imza-sunucusu/zincir CAGRILMAZ).

ORTAM-ANATOMI:
- _enc_string(s): JSON-string kacis ( raw non-ASCII)
- _encode(o, out): JCS kanoniklestirici ( accumulator)
- _json_saf_yap(deger): JCS-guvenli ilkel-ture indirge
- jcs(obj): bytes / jcs_str(obj): str — RFC 8785
- compute_record_hash(prev, record): Tamga zincir-kurali
- es_number(x): ECMAScript Number.prototype.toString ( RFC 8785 3.2.2.2)
"""
import decimal
import enum
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from yieldix.mesh.tamga_anchor import (  # noqa: E402
    _enc_string, _json_saf_yap, _HASH_DISI_ALANLAR, compute_record_hash,
    es_number, jcs, jcs_str,
)


def _E(o):
    """jcs_str kisa-yolu."""
    return jcs_str(o)


# == _enc_string =====================================================================================

def test_enc_string_temel():
    """ORTAM: tirnaklar eklenir."""
    assert _enc_string("abc") == '"abc"'


def test_enc_string_bos():
    assert _enc_string("") == '""'


@pytest.mark.parametrize("girdi,bek", [
    ("a\"b", '"a\\"b"'), ("a\\b", '"a\\\\b"'),
    ("a\tb", '"a\\tb"'), ("a\nb", '"a\\nb"'),
    ("a\rb", '"a\\rb"'), ("a\fb", '"a\\fb"'), ("a\bb", '"a\\bb"'),
])
def test_enc_string_kacislar(girdi, bek):
    """ORTAM: 7-kacis-haritasi ( " \\ b f n r t)."""
    assert _enc_string(girdi) == bek


@pytest.mark.parametrize("k", ["\\", "\"", "\t", "\n", "\r", "\f", "\b"])
def test_enc_string_kacis_idempotent(k):
    """ORTAM: tek-karakter kacislar duz-geri-donusturulebilir."""
    assert _enc_string(k)[1:-1] == {
        "\\": "\\\\", '"': '\\"', "\t": "\\t", "\n": "\\n",
        "\r": "\\r", "\f": "\\f", "\b": "\\b"}[k]


@pytest.mark.parametrize("k, bek", [
    ("\x00", "\\u0000"), ("\x01", "\\u0001"), ("\x07", "\\u0007"),
    ("\x08", "\\b"), ("\x09", "\\t"), ("\x0a", "\\n"),
    ("\x1f", "\\u001f"), ("\x1e", "\\u001e"),
])
def test_enc_string_dusuk_unocode(k, bek):
    """ORTAM-OGRENDI: ord < 0x20 -> '\\uXXXX' ( 4-hane); HARITADA-OLANLAR
    ( \\b \\t \\n \\r \\f) once-yakalanir ( ' \\b f n r t haritada-once)."""
    assert _enc_string(k) == '"' + bek + '"'


def test_enc_string_bosluk_raw():
    """ORTAM: 0x20 bosluk RAW ( kacis-YOK)."""
    assert _enc_string("a b") == '"a b"'


@pytest.mark.parametrize("k", ["ğ", "ü", "ş", "日", "月", "🎉", "𝄞"])
def test_enc_string_non_ascii_raw(k):
    """ORTAM-OGRENDI: non-ASCII RAW ( UTF-8 kacislanMAZ; BMP-disi 4-byte
    emoji dahil) — RFC 8785 3.2.2.1 'non-ASCII kacislanmaz'."""
    assert _enc_string(k) == '"' + k + '"'


def test_enc_string_turkce_cumle():
    assert _enc_string("Merhaba Dünya") == '"Merhaba Dünya"'


def test_enc_string_karisik():
    """ORTAM: kacis + non-ASCII + kontrol bir-arada."""
    assert _enc_string("a\tğ\x07日") == '"a\\tğ\\u0007日"'


def test_enc_string_donut_str():
    assert isinstance(_enc_string("x"), str)


# == jcs / jcs_str ===================================================================================

def test_jcs_bytes_vs_str():
    """ORTAM-OGRENDI: jcs BYTES doner, jcs_str STR ( ayni-icerik)."""
    assert jcs({"a": 1}) == b'{"a":1}'
    assert jcs_str({"a": 1}) == '{"a":1}'
    assert jcs({"a": 1}) == jcs_str({"a": 1}).encode("utf-8")


def test_jcs_null_bool():
    """ORTAM: None null; True/False true/false."""
    assert _E(None) == "null"
    assert _E(True) == "true"
    assert _E(False) == "false"


def test_jcs_bool_once_gelir():
    """ORTAM-OGRENDI: 'o is True/False' once — bool int'in ALT-SINIFI;
    'isinstance(o, bool)' dali DEAD CODE ( gercekte ulasilamaz)."""
    assert _E(True) == "true"
    assert isinstance(True, int)  # bool int alt-sinifi


def test_jcs_int():
    assert _E(0) == "0"
    assert _E(42) == "42"
    assert _E(-1) == "-1"
    assert _E(2**53) == "9007199254740992"
    assert _E(-(2**53)) == "-9007199254740992"


def test_jcs_int_sinir_disi():
    """ORTAM-OGRENDI: 2^53+1 -> ValueError 'ijson_number_out_of_range'
    ( RFC 7493; U+2212 Unicode-eksi icerir)."""
    with pytest.raises(ValueError, match="ijson_number_out_of_range"):
        jcs(2**53 + 1)
    with pytest.raises(ValueError, match="ijson_number_out_of_range"):
        jcs(-(2**53) - 1)


def test_jcs_str_deger():
    assert _E("x") == '"x"'


def test_jcs_list():
    assert _E([1, 2, 3]) == "[1,2,3]"


def test_jcs_bos_liste():
    assert _E([]) == "[]"


def test_jcs_tuple_list_gibi():
    """ORTAM: tuple list-gibi serilesir ( list|tuple)."""
    assert _E((1, 2)) == "[1,2]"


def test_jcs_bos_tuple():
    assert _E(()) == "[]"


def test_jcs_ic_ice_liste():
    assert _E([[1], [2]]) == "[[1],[2]]"


def test_jcs_dict_bos():
    assert _E({}) == "{}"


def test_jcs_dict_tek():
    assert _E({"a": 1}) == '{"a":1}'


def test_jcs_dict_siralama():
    """ORTAM: anahtarlar UTF-16-BE siralanir ( b once a degil)."""
    assert _E({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_jcs_dict_siralama_zor():
    assert _E({"z": 1, "a": 2, "m": 3}) == '{"a":2,"m":3,"z":1}'


def test_jcs_dict_utf16_be():
    """ORTAM-OGRENDI: §3.2.3 UTF-16-BE siralama — '日' < '月' (
    U+65E5 < U+6708); Python code-point sirasi ile ayni ( BMP)."""
    assert _E({"月": 1, "日": 2}) == '{"日":2,"月":1}'


def test_jcs_dict_bmp_disi():
    """ORTAM-OGRENDI: BMP-disi surrogate-pair UTF-16-BE siralamasini
    ETKILER — json.dumps(sort_keys=True) YETERLI DEGIL. 'a' ( UTF-16-BE
    00 61) '𝄞' ( D8 34 DD 1E)'den ONCE gelir ( 0x00 < 0xD8); '日' (
    65 E5) de '𝄞'den once."""
    assert _E({"𝄞": 1, "a": 2}) == '{"a":2,"𝄞":1}'
    assert _E({"𝄞": 1, "日": 2}) == '{"日":2,"𝄞":1}'


def test_jcs_int_anahtar_str():
    """ORTAM: int-anahtar str() ile serilesir."""
    assert _E({2: "a"}) == '{"2":"a"}'


def test_jcs_dict_ic_ice():
    assert _E({"a": {"b": 1}}) == '{"a":{"b":1}}'


def test_jcs_dict_liste_deger():
    assert _E({"a": [1, 2]}) == '{"a":[1,2]}'


def test_jcs_liste_dict_deger():
    assert _E([{"a": 1}]) == '[{"a":1}]'


def test_jcs_desteklenmeyen_tip():
    """ORTAM-OGRENDI: object -> TypeError 'jcs-desteklenmeyen-tip'."""
    with pytest.raises(TypeError, match="jcs-desteklenmeyen-tip"):
        jcs(object())
    with pytest.raises(TypeError, match="jcs-desteklenmeyen-tip"):
        jcs(complex(1, 2))


def test_jcs_ic_ice_karisik():
    assert _E({"a": [1, {"b": null_k()}]}) == '{"a":[1,{"b":null}]}'


def null_k():
    return None


def test_jcs_stabil():
    """ORTAM: ayni-girdi ayni-cikti."""
    obj = {"b": [1, {"c": None}], "a": "x"}
    assert _E(obj) == _E(obj)


def test_jcs_hassas_siralama_karmasik():
    """ORTAM: derin-yapi siralama ( her-seviyede)."""
    assert _E({"z": {"d": 1, "c": 2}, "y": [3]}) == \
        '{"y":[3],"z":{"c":2,"d":1}}'


# == es_number =======================================================================================

@pytest.mark.parametrize("g, bek", [
    (0.0, "0"), (-0.0, "0"), (1.0, "1"), (-1.0, "-1"),
    (1.5, "1.5"), (42.0, "42"), (1e16, "10000000000000000"),
    (2.93e-07, "2.93e-7"), (1e21, "1e+21"), (1e-6, "0.000001"),
    (1e-7, "1e-7"), (123456789012345680.0, "123456789012345680"),
    (-42.5, "-42.5"), (100.0, "100"), (0.1, "0.1"),
])
def test_es_number_tablo(g, bek):
    """ORTAM: ECMAScript Number.prototype.toString ( RFC 8785 3.2.2.2)."""
    assert es_number(g) == bek


@pytest.mark.parametrize("g", [float("nan"), float("inf"), float("-inf")])
def test_es_number_sonlu_degil(g):
    """ORTAM-OGRENDI: NaN/Inf -> ValueError 'ijson_number_not_finite'
    ( I-JSON RFC 7493)."""
    with pytest.raises(ValueError, match="ijson_number_not_finite"):
        es_number(g)


def test_es_number_isaret_sifir():
    """ORTAM-OGRENDI: -0.0 == 0 -> '0' ( ECMAScript '-0' BASMAZ;
    x == 0 kontrolu -0.0'i da yakalar)."""
    assert es_number(-0.0) == "0"


def test_es_number_trailing_zero():
    """ORTAM: 1.50 -> '1.5' ( trailing-zero normalizasyonu)."""
    assert es_number(1.50) == "1.5"


def test_es_number_buyuk_tamsayi():
    """ORTAM: 1e16 tamsayi-gorunumlu ( e-notasyonu yok)."""
    assert es_number(1e16) == "10000000000000000"
    assert "e" not in es_number(1e16)


def test_es_number_ust_sinir():
    """ORTAM: 1e21 -> e-notasyonu ( n > 21 esigi)."""
    assert es_number(1e21) == "1e+21"


def test_es_number_alt_sinir():
    """ORTAM: 1e-6 -> '0.000001' ( -6 < n <= 0 sabit-gorunum)."""
    assert es_number(1e-6) == "0.000001"


def test_es_number_alt_e_notasyonu():
    """ORTAM: 1e-7 -> '1e-7' ( n <= -7 esigi)."""
    assert es_number(1e-7) == "1e-7"


# == _json_saf_yap ====================================================================================

def test_json_saf_yap_int():
    """ORTAM: ilkiller OLDUGU-GIBI doner."""
    assert _json_saf_yap(42) == 42
    assert _json_saf_yap(1.5) == 1.5
    assert _json_saf_yap("x") == "x"
    assert _json_saf_yap(None) is None


def test_json_saf_yap_bool():
    """ORTAM-OGRENDI: bool ÖNCE kontrol ( int'den once; True -> True)."""
    assert _json_saf_yap(True) is True
    assert _json_saf_yap(False) is False


def test_json_saf_yap_dict():
    """ORTAM: dict recursive; anahtarlar str()."""
    assert _json_saf_yap({"b": 2, "a": 1}) == {"b": 2, "a": 1}


def test_json_saf_yap_dict_int_anahtar():
    """ORTAM-OGRENDI: int-anahtar str() olur ( {str(k)})."""
    out = _json_saf_yap({1: "a"})
    assert list(out.keys()) == ["1"]


def test_json_saf_yap_liste():
    assert _json_saf_yap([1, 2]) == [1, 2]


def test_json_saf_yap_tuple_listeye():
    """ORTAM: tuple -> list ( sirali-saklanir)."""
    out = _json_saf_yap((1, 2))
    assert out == [1, 2]
    assert isinstance(out, list)


def test_json_saf_yap_ic_ice():
    """ORTAM: ic-ice dict/liste recursive."""
    assert _json_saf_yap({"a": [1, {"b": 2}]}) == {"a": [1, {"b": 2}]}


def test_json_saf_yap_decimal():
    """ORTAM-OGRENDI: Decimal -> str ( JCS-guvenli; float-hassasiyet
    kaybi YOK)."""
    out = _json_saf_yap(decimal.Decimal("1.5"))
    assert out == "1.5"
    assert isinstance(out, str)


def test_json_saf_yap_enum():
    """ORTAM-OGRENDI: Enum -> str ( enum-adi DEGIL; str(enum) ->
    'R.A' formatinda)."""

    class Rengi(enum.Enum):
        A = "x"

    out = _json_saf_yap(Rengi.A)
    assert isinstance(out, str)


def test_json_saf_yap_diger_tip_str():
    """ORTAM-OGRENDI: bilinmeyen-tip -> str() ( complex, set, object)."""
    assert _json_saf_yap(complex(1, 2)) == "(1+2j)"
    assert isinstance(_json_saf_yap(object()), str)


def test_json_saf_yap_idempotent():
    """ORTAM: iki-kere uygulama ayni-sonuc."""
    v = {"a": decimal.Decimal("1.5")}
    once = _json_saf_yap(v)
    assert _json_saf_yap(once) == once


def test_json_saf_yap_bos_konteynerler():
    assert _json_saf_yap({}) == {}
    assert _json_saf_yap([]) == []
    assert _json_saf_yap(()) == []


# == compute_record_hash =============================================================================

def test_record_hash_sabit():
    """ORTAM: sabit-girdi sabit-cikti ( SHA-256)."""
    h = compute_record_hash("0" * 64, {"a": 1})
    assert h == "fc6cee09194dd2578bd7664604fcb72a539066fd34544cea0009c43eb6cdc289"


def test_record_hash_uzunluk():
    """ORTAM: 64-hex ( 32-bayt)."""
    h = compute_record_hash("0" * 64, {"a": 1})
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_record_hash_prev_etkili():
    """ORTAM: prev DEGISSE hash DEGISIR ( zincir-bagimi)."""
    h1 = compute_record_hash("0" * 64, {"a": 1})
    h2 = compute_record_hash("1" * 64, {"a": 1})
    assert h1 != h2


def test_record_hash_kayit_etkili():
    """ORTAM: kayit DEGISSE hash DEGISIR."""
    h1 = compute_record_hash("0" * 64, {"a": 1})
    h2 = compute_record_hash("0" * 64, {"a": 2})
    assert h1 != h2


def test_record_hash_dis_alanlar_haric():
    """ORTAM-OGRENDI: 'h' ve 'node_sig' hash-GIRDISINE DAHIL DEGIL
    ( _HASH_DISI_ALANLAR; SELF-REFERENCE kirar)."""
    base = {"a": 1}
    h1 = compute_record_hash("p", base)
    h2 = compute_record_hash("p", {**base, "h": "farkli"})
    h3 = compute_record_hash("p", {**base, "node_sig": "farkli"})
    assert h1 == h2 == h3


def test_record_hash_dis_alanlar_kumesi():
    """ORTAM: tam-kume { 'h', 'node_sig'}."""
    assert set(_HASH_DISI_ALANLAR) == {"h", "node_sig"}


def test_record_hash_frozenset():
    """ORTAM: _HASH_DISI_ALANLAR frozenset ( degismez)."""
    assert isinstance(_HASH_DISI_ALANLAR, frozenset)


def test_record_hash_siralama_bagimsiz():
    """ORTAM: jcs anahtar-siraladigi icin dict-ekleme-sirasi ONEMSIZ."""
    h1 = compute_record_hash("p", {"a": 1, "b": 2})
    h2 = compute_record_hash("p", {"b": 2, "a": 1})
    assert h1 == h2


def test_record_hash_ic_ice():
    """ORTAM: ic-ice-kayitlar da jcs ile kanonik."""
    h = compute_record_hash("p", {"a": {"b": [1, 2]}})
    assert len(h) == 64


def test_record_hash_bos_kayit():
    """ORTAM: bos-kayit gecerli ( prev + '{}')."""
    h = compute_record_hash("p", {})
    assert len(h) == 64


def test_record_hash_bos_prev():
    """ORTAM: bos-prev gecerli."""
    h = compute_record_hash("", {"a": 1})
    assert len(h) == 64


def test_record_hash_stabil():
    h1 = compute_record_hash("p", {"a": 1})
    h2 = compute_record_hash("p", {"a": 1})
    assert h1 == h2


# == parite (GNoME/LexBinder/Dumen ailesi) ============================================================

_ES_TABLO = {
    0.0: "0", -0.0: "0", 1.0: "1", -1.0: "-1", 42.5: "-42.5",
    1e16: "10000000000000000", 2.93e-07: "2.93e-7", 1e21: "1e+21",
    1e-6: "0.000001", 1e-7: "1e-7", 42.5: "42.5",
}


@pytest.mark.parametrize("g,bek", list(_ES_TABLO.items()))
def test_mesh_parite_es_number(g, bek):
    """ORTAM-OGRENDI (MESH-PARITE): es_number 19-GNoME-Forge _es_number,
    02-LexBinder es_number, 77-Dumen _ecmascript_number ile AYNI RFC 8785
    algoritmasi — anchor'lar-arasi digest-uyusmasi ZORUNLU."""
    assert es_number(g) == bek


def test_mesh_parite_jcs():
    """ORTAM: JCS ciktilari TamgaProtocol tamga_canon.jcs ile bayt-uyumlu."""
    obj = {"b": [1, 2], "a": {"c": None}}
    assert jcs(obj) == b'{"a":{"c":null},"b":[1,2]}'


# == karakterizasyon ==================================================================================

def test_amaci():
    r"""ORTAM-OGRENDI (DOCSTACK): RFC 8785 JCS — _enc_string 7-kacis
    haritasi ( " \\ b f n r t) + ord<0x20 -> \uXXXX; non-ASCII RAW ( BMP-
    disi-emoji-dahil); _encode None/True/False once ( bool int'in alt-
    sinifi -> isinstance-bool dali DEAD CODE); int [−2^53,2^53] ( RFC 7493,
    U+2212); float es_number; dict UTF-16-BE siralama ( 3.2.3; BMP-disi
    surrogate-pair json.dumps(sort_keys=True)'den farkli); tuple list-gibi;
    bilinmeyen-tip -> TypeError; jcs BYTES / jcs_str STR; _json_saf_yap
    Decimal/Enum -> str, tuple -> list, bool once; compute_record_hash
    'h'+'node_sig' DISARIDA ( self-reference kirar), prev ile zincirleme."""
    assert _E({"b": 1, "a": None}) == '{"a":null,"b":1}'
    assert _enc_string("a\tğ\x07") == '"a\\tğ\\u0007"'
    assert _json_saf_yap(decimal.Decimal("1.5")) == "1.5"
    h1 = compute_record_hash("p", {"a": 1, "h": "x"})
    h2 = compute_record_hash("p", {"a": 1})
    assert h1 == h2
