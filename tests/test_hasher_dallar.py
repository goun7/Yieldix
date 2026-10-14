"""
Dal-kesen (branch-cutting) testler: yieldix.crypto.hasher

Kapsanan public fonksiyonlar (src/yieldix/crypto/hasher.py):
  * canonical_json_bytes(payload) -> bytes
  * sha256_digest_hex(payload) -> str

DAL LISTESI (her dal icin en az bir test):
  [canonical_json_bytes]
    D1  anahtar siralama (sort_keys=True) — farkli ekleme sirasi ayni bytes
    D2  kompakt ayraclar (",", ":") — bosluk YOK
    D3  ensure_ascii=False — Turkce/UTF-8 kacis YOK, ham UTF-8 bytes
    D4  Decimal -> str ( _default cekirdegi)
    D5  desteklenmeyen tur -> TypeError (object/set/ozel sinif)
    D6  TypeError mesaji tur bilgisini tasir
    D7  bos dict -> b"{}"
    D8  ic-ice kaplar (dict/list icinde dict) — ic seviyeler de sirali
    D9  liste sirasi KORUNUR (JSON listeleri siralanmaz)
    D10 ilkel turler (None/bool/int/float/str) dogru serilesir
    D11 donus tipi bytes'dir (str degil)
  [sha256_digest_hex]
    D12 64-karakter hex dizgi
    D13 hex alfabesi yalnizca [0-9a-f]
    D14 anahtar-sira permutasyonu ayni digest (determinizm)
    D15 farkli payload farkli digest (carpisma-gercekligi)
    D16 known-answer test (KAT) — sabit payload sabit digest
    D17 bos dict KAT digest
    D18 Decimal payload canonical'den gecer (TypeError YOK)
    D19 UTF-8 payload KAT digest
    D20 hashlib ile bagimsiz yeniden-hesaplama ayni sonuc
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from yieldix.crypto.hasher import canonical_json_bytes, sha256_digest_hex


# ---------------------------------------------------------------------------
# yardimci sabitler (KAT degerleri olcülerek alindi, hafiza degil)
# ---------------------------------------------------------------------------
_KAT_KARISIK_DIGEST = (
    "61c6a506ab16b97c26581aa8fec1ab90dd2b118b39dfd41ae7d7424d52bf3e64"
)
_KAT_BOS_DIGEST = (
    "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)
_KAT_TR_DIGEST = (
    "bb3162727a20b21ae4b4e679c3a844f5104f6103a45f45ab9987e42b1c82ee38"
)


class TestCanonicalJsonBytes:
    """canonical_json_bytes — kuralli UTF-8 JSON serilestirme dallari."""

    def test_anahtar_siralamasi_deterministik(self):
        """D1: sort_keys=True — farkli ekleme sirasi ayni bytes verir."""
        duz = canonical_json_bytes({"a": 1, "b": 2, "z": [3, 2, 1]})
        ters = canonical_json_bytes({"z": [3, 2, 1], "b": 2, "a": 1})
        karisik = canonical_json_bytes({"b": 2, "a": 1, "z": [3, 2, 1]})
        assert duz == ters == karisik

    def test_kompakt_ayraclar_bosluk_yok(self):
        """D2: separators=(',', ':') — cikista bosluk YOK."""
        cikti = canonical_json_bytes({"a": 1, "b": 2})
        assert cikti == b'{"a":1,"b":2}'
        assert b", " not in cikti
        assert b": " not in cikti

    def test_ensure_ascii_false_utf8_kacis_yok(self):
        """D3: ensure_ascii=False — Turkce karakterler \\uXXXX degil ham UTF-8."""
        cikti = canonical_json_bytes({"sehir": "İstanbul"})
        # kompakt ayraç: ':' sonrasi bosluk YOK
        assert cikti == '{"sehir":"İstanbul"}'.encode("utf-8")
        assert b", " not in cikti
        assert b": " not in cikti
        # bayt-duzeyinde UTF-8 kodlama (İ = c4 b0)
        assert b"\xc4\xb0" in cikti

    def test_decimal_str_olarak_serilesir(self):
        """D4: Decimal -> str ( _default cekirdegi)."""
        assert canonical_json_bytes({"cpl": Decimal("110.50")}) == b'{"cpl":"110.50"}'
        assert canonical_json_bytes({"d": Decimal("-0.5")}) == b'{"d":"-0.5"}'

    @pytest.mark.parametrize("desteklenmeyen", [
        object(),
        {1, 2, 3},
        (lambda: None),
    ])
    def test_desteklenmeyen_tur_type_error(self, desteklenmeyen):
        """D5: JSON serilestirilemeyen deger -> TypeError firlatir."""
        with pytest.raises(TypeError):
            canonical_json_bytes({"kotu": desteklenmeyen})

    def test_type_error_mesaji_tur_icerir(self):
        """D6: TypeError mesaji 'Object of type ... is not JSON serializable'."""
        with pytest.raises(TypeError) as exc_info:
            canonical_json_bytes({"kotu": object()})
        mesaj = str(exc_info.value)
        assert "Object of type" in mesaj
        assert "is not JSON serializable" in mesaj
        assert "object" in mesaj

    def test_bos_dict(self):
        """D7: bos payload -> b'{}'."""
        assert canonical_json_bytes({}) == b"{}"

    def test_ic_ice_kaplar_ic_seviyelerde_sirali(self):
        """D8: ic-ice dict/list icindeki dict'ler de sort_keys'e tabidir."""
        cikti = canonical_json_bytes({"x": {"d": 4, "c": 3}, "l": [{"b": 2, "a": 1}]})
        assert cikti == b'{"l":[{"a":1,"b":2}],"x":{"c":3,"d":4}}'

    def test_liste_sirasi_korunur(self):
        """D9: listeler sort_keys'ten etkilenmez — JSON listeleri siralidir."""
        assert canonical_json_bytes({"z": [3, 2, 1]}) == b'{"z":[3,2,1]}'
        assert canonical_json_bytes({"z": [1, 2, 3]}) == b'{"z":[1,2,3]}'

    @pytest.mark.parametrize("deger,beklenen", [
        (None, b'{"a":null}'),
        (True, b'{"a":true}'),
        (False, b'{"a":false}'),
        (42, b'{"a":42}'),
        (3.5, b'{"a":3.5}'),
        ("metin", b'{"a":"metin"}'),
    ])
    def test_ilkel_turler_dogru_serilesir(self, deger, beklenen):
        """D10: None/bool/int/float/str ilkel turleri JSON standartinda."""
        assert canonical_json_bytes({"a": deger}) == beklenen

    def test_donus_tipi_bytesdir(self):
        """D11: donus degeri bytes'dir (str degil)."""
        sonuc = canonical_json_bytes({"a": 1})
        assert isinstance(sonuc, bytes)
        assert not isinstance(sonuc, str)


class TestSha256DigestHex:
    """sha256_digest_hex — SHA-256 ozet dallari."""

    def test_64_karakter_hex(self):
        """D12: SHA-256 hex digest her zaman 64 karakterdir."""
        assert len(sha256_digest_hex({"a": 1})) == 64

    @pytest.mark.parametrize("payload", [
        {"a": 1},
        {},
        {"ad": "Ahmet Yılmaz"},
        {"cpl": Decimal("110.50")},
        {"z": [3, 2, 1], "a": 1},
    ])
    def test_hex_alfabesi_sinirli(self, payload):
        """D13: hex digest yalnizca [0-9a-f] karakterleri icerir."""
        ozet = sha256_digest_hex(payload)
        assert set(ozet) <= set("0123456789abcdef")

    @pytest.mark.parametrize("sira1,sira2", [
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
        ({"z": [3, 2, 1], "a": 1}, {"a": 1, "z": [3, 2, 1]}),
    ])
    def test_anahtar_permutasyonu_ayni_digest(self, sira1, sira2):
        """D14: ayni icerik farkli anahtar sirasi ayni ozeti verir."""
        assert sha256_digest_hex(sira1) == sha256_digest_hex(sira2)

    def test_farkli_payload_farkli_digest(self):
        """D15: farkli payload farkli ozet (yayilan carpisma-gercekligi)."""
        assert sha256_digest_hex({"a": 1}) != sha256_digest_hex({"a": 2})
        assert sha256_digest_hex({"a": 1}) != sha256_digest_hex({"a": 1, "b": 2})

    def test_known_answer_test_karisik_payload(self):
        """D16: KAT — sabit payload icin olculen digest."""
        assert sha256_digest_hex({"b": 2, "a": 1, "z": [3, 2, 1]}) == _KAT_KARISIK_DIGEST

    def test_known_answer_test_bos_payload(self):
        """D17: KAT — bos dict icin olculen digest."""
        assert sha256_digest_hex({}) == _KAT_BOS_DIGEST

    def test_decimal_payload_type_error_yok(self):
        """D18: Decimal deger canonical yoldan digest'a gider."""
        ozet = sha256_digest_hex({"cpl": Decimal("110.50")})
        assert len(ozet) == 64
        assert ozet == sha256_digest_hex({"cpl": Decimal("110.50")})

    def test_utf8_payload_known_answer(self):
        """D19: KAT — Turkce karakter iceren payload icin olculen digest."""
        assert sha256_digest_hex({"ad": "Ahmet Yılmaz", "şehir": "İstanbul"}) == _KAT_TR_DIGEST

    def test_hashlib_bagimsiz_yeniden_hesaplama(self):
        """D20: hashlib ile bagimsiz hesap ayni sonucu verir (guvenilirlik)."""
        payload = {"b": 2, "a": 1, "z": [3, 2, 1]}
        beklenen = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        assert sha256_digest_hex(payload) == beklenen
