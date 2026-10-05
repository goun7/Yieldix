"""
Yieldix kanıt-imzalarını Tamga hash-zincirine sabitleyen mesh-köprü katmanı.

Mesh konumu
-----------
TAMGA-MESH bağlantı matrisinde Yieldix (01_unicorn) **katılım-üretim**
protokolüdür: pipeline-çıkışının Ed25519 ile imzalanmış kanıtını ( kanıt-
imzası, AT-077) üretir. ``05_acik_kaynak/TamgaProtocol`` ise mesh'in
**kalıcı kanıt-anchor** katmanıdır. Bu modul iki katmanını birlestirir:
Yieldix'in imzalı aylık-rapor kanıtını, Tamga'nin hash-zincirlenmiş
``ledger.jsonl`` kanit modelinde **bayt-uyumlu** bir kayda dönüştürür.

Neden değerli?
--------------
Bir aylık-rapor kanıtı yalnızca Yieldix'in kendi deposunda duruyorsa, o
kanıtı üreten taraf (biz) onu gizlice değiştirebilir; imza yeniden
hesaplanıp "her zaman böyleydi" denebilir. Kanıtı Tamga'nın **bağımsız**
hash-zincirine sabitlemek, geriye-dönük yeniden-yazımı tespit-edilebilir
kılar: kanıt artık iki bağımsız zincirde paralel yaşar — Yieldix'in
Ed25519 imza zincirinde ve Tamga'nın append-only hash-zincirinde.

Kanıt-imzası modeli ( gerçek — uydurma değil)
--------------------------------------------
Bu modul Yieldix'in mevcut kripto yüzeyini **yeniden icat etmez**;
üretim modüllerini kullanır:

- ``MonthlyReportGenerator.to_signable_dict`` — imzalanabilir kanıt dict'i
  ( kripto-yüzey AT-077/088/097/114/118'in dışına taşmaz).
- ``sha256_digest_hex`` / ``canonical_json_bytes`` — mevcut SHA-256 yüzeyi.
- ``Ed25519ReportSigner.verify_signature`` — mevcut Ed25519 (RFC 8032) yüzeyi.

Sabitleme kaydı, kanıtın **kendi sha256_digest'ini + Ed25519 imzasını +
genel-anahtarını** yük olarak taşıdığı için, bağımsız bir doğrulayıcı
Yieldix'i kurmadan bile (a) Tamga zincir-bütünlüğünü, (b) imzanın kanıt
içeriğine yeniden doğrulanmasını hesaplayabilir — çapraz-çapa bütünlüğü.

Tamga ledger modeli ( normatif — TamgaProtocol ``docs/ARCHITECTURE.md:42``
ve ``tamga_runner._verify_chain`` ile birebir)::

    seq     : 1-based artan tamsayı
    prev    : önceki kaydın ``h`` değeri; İLK kayıt için 64×'0' (genesis)
    h       = sha256(prev ‖ jcs(kayıt − {h, node_sig}))
    kayıt   : düz JSON nesnesi; ``seq``/``prev``/``h`` + keyfi yük alanları

İki kritik ayrım ( yanlış anlaşılırsa digest uyuşmaz):

1. ``prev`` hem **dize-prefix** olarak hem de jcs'in **içinde** bulunur —
   yani hash girdisi ``prev_str + jcs(kayıt)`` biçimindedir ( bayt-düzeyinde).
2. Canonicalization **RFC 8785 (JCS)** ile yapılır — ``json.dumps(
   sort_keys=True)`` DEĞİL. RFC 8785: üye-adları UTF-16 kod-birim
   dizisine göre sıralanır (§3.2.3) ve sayılar ECMAScript
   ``Number.prototype.toString`` algoritmasıyla yazılır ( §3.2.2.2:
   ``1.0`` → ``"1"``, ``2.93e-07`` → ``"2.93e-7"``). Bu, başka bir dilde
   ( Node/Go/Rust) yazılmış bir Tamga verifier'ının aynı baytları yeniden
   türetmesini sağlar.

JCS uygulaması bu modüle **bağımlılıksız** ( stdlib-only) olarak gömülmüştür
— TamgaProtocol'ün ``tamga_canon.py``'siyle **bayt-bayt uyumlu** olacak
biçimde RFC 8785'den sıfırdan yazılmıştır; parite testi gerçek
``tamga_canon.jcs``'e karşı çalışır ( mevcutsa; değilse skip). Gömme
sebebi: Yieldix'in Tamga kurulumuna runtime bağımlılığı olmadan kendi
başına çalışabilmesi.

KULLANIM
--------

    from yieldix.core.engine import YieldixEngine
    from yieldix.core.types import PipelineConfig
    from yieldix.mesh.tamga_anchor import KanitTamgaSabitleyici, anchor_report

    # 1) Pipeline → imzalı kanıt ( mevcut üretim yolu)
    engine = YieldixEngine(PipelineConfig(tenant_id="tenant-abc"))
    rapor = reporter.generate_signed_report("tenant-abc", "2026-09-01",
                                            "2026-09-30", engine.kpi_collector,
                                            engine.config.enabled_components)

    # 2) Kanıtı Tamga'nın hash-zincirine sabitle
    kayit = anchor_report(rapor, "tamga-ledger.jsonl",
                          public_key_hex=signer.public_key_hex)

    # 3) Üç-katmanlı doğrulama
    sabitleyici = KanitTamgaSabitleyici([rapor])
    sabitleyici.sabitle()
    assert sabitleyici.dogrula()
"""

from __future__ import annotations

import datetime
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from yieldix.crypto.hasher import sha256_digest_hex
from yieldix.crypto.signer import Ed25519ReportSigner
from yieldix.telemetry.reporter import MonthlyReportGenerator

__all__ = [
    "TAMGA_GENESIS_H",
    "ANCHOR_OP",
    "KAYNAK_PROJE",
    "TAMGA_LEDGER_FORMAT",
    "BozukTamgaZinciriError",
    "jcs",
    "jcs_str",
    "es_number",
    "compute_record_hash",
    "build_anchor_record",
    "verify_chain",
    "TamgaLedger",
    "KanitTamgaSabitleyici",
    "anchor_report",
    "sabitle_raporlar",
]

# Tamga genesis: ilk kaydın prev değeri ( TamgaProtocol ile aynı sabit).
TAMGA_GENESIS_H = "0" * 64

# Bu üreticinin kanıt türü. Tamga'nın unknown_ops yardımcısı bilinmeyen
# op'ları 'garanti dışı' olarak işaretler ( üretici-garantisi yalnızca kendi
# emitter'larını kapsar) — bu davranış biçimi kasıtlıdır: alıcı karar verir.
ANCHOR_OP = "yieldix.kanit-imzasi-sabitle"

# Kaynak proje kimliği — hangi mesh üyesinden sabitlendiği zincirde okunur.
KAYNAK_PROJE = "99-Yieldix/kanit-imzasi"

# Tamga ledger depolama-biçimi ( conformance spec: "tamga-sim/1" JSONL).
TAMGA_LEDGER_FORMAT = "tamga-sim/1"

# Hash girdisinden çıkarılan alanlar ( node_sig imza katmanı hash'in
# dışındadır; biz node_sig kullanmayız ama kuralı birebrit uygulamak için
# dışarıda bırakırız).
_HASH_DISI_ALANLAR = frozenset({"h", "node_sig"})


class BozukTamgaZinciriError(RuntimeError):
    """Tamga zincir-bütünlüğü ihlali ( seq/prev/hash uyuşmazlığı)."""
    pass


# ---------------------------------------------------------------------------
# RFC 8785 ( JCS) — bağımlılıksız, TamgaProtocol ``tamga_canon.jcs`` ile
# bayt-bayt uyumlu ( parite-testi: tests/test_tamga_anchor.py)
# ---------------------------------------------------------------------------
_ESCAPE = {
    '"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
    "\n": "\\n", "\r": "\\r", "\t": "\\t",
}


def es_number(x: float) -> str:
    """ECMAScript ``Number.prototype.toString`` ( RFC 8785 §3.2.2.2).

    ``tamga_canon.es_number`` ile bire-bit: NaN/Inf reddedilir ( I-JSON,
    RFC 7493), ``1.0`` → ``"1"``, ``2.93e-07`` → ``"2.93e-7"``,
    ``1e16`` → ``"10000000000000000"``.
    """
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError(
            "ijson_number_not_finite: NaN/Infinity I-JSON ( RFC 7493) "
            "kümesinde değil"
        )
    if x == 0:  # -0.0 dahil ECMAScript "0" basar
        return "0"
    neg = x < 0
    digits, exp = Decimal(repr(abs(x))).as_tuple()[-2:]
    while len(digits) > 1 and digits[-1] == 0:
        digits = digits[:-1]
        exp = exp + 1
    k = len(digits)
    n = exp + k
    s = "".join(map(str, digits))
    if k <= n <= 21:
        body = s + "0" * (n - k)
    elif 0 < n <= 21:
        body = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + s
    else:
        e = n - 1
        mant = s if k == 1 else s[0] + "." + s[1:]
        body = mant + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return ("-" if neg else "") + body


def _enc_string(s: str) -> str:
    out = ['"']
    for ch in s:
        if ch in _ESCAPE:
            out.append(_ESCAPE[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)  # raw UTF-8; non-ASCII kaçışlanmaz
    out.append('"')
    return "".join(out)


def _encode(o: Any, out: List[str]) -> None:
    if o is None:
        out.append("null")
    elif o is True:
        out.append("true")
    elif o is False:
        out.append("false")
    elif isinstance(o, bool):  # savunma: bool, int'in alt-sınıfıdır
        out.append("true" if o else "false")
    elif isinstance(o, int):
        if not (-(2 ** 53) <= o <= 2 ** 53):
            raise ValueError(
                "ijson_number_out_of_range: [−2^53, 2^53] dışı tamsayı I-JSON "
                "( RFC 7493) kümesinde değil; değeri string olarak serileştirin"
            )
        out.append(str(o))
    elif isinstance(o, float):
        out.append(es_number(o))
    elif isinstance(o, str):
        out.append(_enc_string(o))
    elif isinstance(o, dict):
        out.append("{")
        first = True
        # §3.2.3: üye-adları UTF-16 kod-birim dizisine göre artan sıralanır.
        # Python code-point sırasından BMP-dışı karakterler ile ayrılır;
        # json.dumps(sort_keys=True) YETERLİ DEĞİLDİR.
        for key in sorted(o, key=lambda k: str(k).encode("utf-16-be")):
            if not first:
                out.append(",")
            first = False
            out.append(_enc_string(str(key)))
            out.append(":")
            _encode(o[key], out)
        out.append("}")
    elif isinstance(o, (list, tuple)):
        out.append("[")
        first = True
        for item in o:
            if not first:
                out.append(",")
            first = False
            _encode(item, out)
        out.append("]")
    else:
        raise TypeError(f"jcs-desteklenmeyen-tip: {type(o).__name__}")


def jcs(obj: Any) -> bytes:
    """RFC 8785 canonical serialization ( JCS) — UTF-8 baytları olarak.

    TamgaProtocol ``tamga_canon.jcs`` ile bayt-bayt uyumlu ( parite-testi).
    """
    out: List[str] = []
    _encode(obj, out)
    return "".join(out).encode("utf-8")


def jcs_str(obj: Any) -> str:
    """Aynı canonicalization, ``str`` olarak ( Tamga hash kuralının birebir
    taklidi: digest'lar metin olarak birleştirilir)."""
    return jcs(obj).decode("utf-8")


def _json_saf_yap(deger: Any) -> Any:
    """Değeri JCS-güvenli ilkel türe indirger ( Decimal → str, Enum → str).

    Kanıt dict'i ``to_signable_dict`` tarafından zaten JSON-ilseldir ( Decimal
    zaten str'dir); bu yine de emin olmak için bir normalization adımıdır.
    """
    if isinstance(deger, dict):
        return {str(k): _json_saf_yap(v) for k, v in deger.items()}
    if isinstance(deger, (list, tuple)):
        return [_json_saf_yap(v) for v in deger]
    if isinstance(deger, bool):
        return deger
    if isinstance(deger, (int, float, str)) or deger is None:
        return deger
    return str(deger)


# ---------------------------------------------------------------------------
# Tamga zincir çekirdeği ( tamga_runner._verify_chain ile bayt-uyumlu)
# ---------------------------------------------------------------------------
def compute_record_hash(prev: str, record: Dict[str, Any]) -> str:
    """Tamga zincir kuralı: ``h = sha256(prev ‖ jcs(kayıt − {h, node_sig}))``.

    ``prev`` hem hash girdisinde hem de kayıt alanında bulunur ( Tamga ile
    aynı). Üretim ``tamga_runner._verify_chain`` ve bağımsız
    ``tests/conformance/verify.py`` ile aynı baytları üretir.
    """
    govde = {k: v for k, v in record.items() if k not in _HASH_DISI_ALANLAR}
    return hashlib.sha256((prev + jcs_str(govde)).encode("utf-8")).hexdigest()


def build_anchor_record(
    report: Any,
    prev_hash: str = TAMGA_GENESIS_H,
    seq: Optional[int] = None,
    ts: Optional[str] = None,
    issuer: Optional[str] = None,
    public_key_hex: Optional[str] = None,
) -> Dict[str, Any]:
    """Bir ``MonthlyReportPayload`` kanıtını Tamga-uyumlu kalıcı kanıt
    kaydına dönüştürür.

    Kayıt, Tamga ``ledger.jsonl`` zincirine doğrudan eklenebilir formattadır;
    ``h`` alanı ``verify_chain`` ( veya Tamga'nın kendi verifier'ı) tarafından
    bağımsız olarak yeniden hesaplanabilir.

    ``public_key_hex`` verilmezse kayıt ``public_key_hex: null`` taşır —
    çapraz-çapa imza-doğrulaması o zaman yapılamaz ( zincir-bütünlüğü hâlâ
    tamdır); alıcı karar verir.
    """
    if report.sha256_digest is None or report.ed25519_signature is None:
        raise ValueError(
            "imzasiz-kanit: report.sha256_digest/ed25519_signature eksik — "
            "sabitlemek için önce MonthlyReportGenerator ile imzalayın ( AT-077)"
        )
    if prev_hash is None:
        prev_hash = TAMGA_GENESIS_H
    if seq is None:
        seq = 1
    if ts is None:
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Gerçek kanıt-imzası modeli ( uydurma değil): reporter'ın imzalanabilir
    # dict'i birebir alınır — imza/digest bu içeriğin üzerinde hesaplanmıştır.
    kanit = _json_saf_yap(MonthlyReportGenerator.to_signable_dict(report))

    record: Dict[str, Any] = {
        "op": ANCHOR_OP,
        "seq": seq,
        "prev": prev_hash,
        "ts": ts,
        "kaynak": KAYNAK_PROJE,
        # kanıt kimliği
        "report_id": report.report_id,
        "tenant_id": report.tenant_id,
        "period_start": report.period_start,
        "period_end": report.period_end,
        # üretim-kanıtı: imzalanmış KPI içeriği ( commitment)
        "kanit": kanit,
        # kanıt-imzası ( AT-077 üretim yolu) — çapraz-çapa anahtarları
        "sha256_digest": report.sha256_digest,
        "ed25519_signature": report.ed25519_signature,
        "public_key_hex": public_key_hex,
    }
    if issuer is not None:
        record["issuer"] = issuer

    record["h"] = compute_record_hash(prev_hash, record)
    return record


def verify_chain(records: Iterable[Dict[str, Any]]) -> Tuple[Optional[str], str]:
    """Tamga zincir doğrulama kuralının bağımsız stdlib yeniden uygulaması.

    Karşı taraf ( Yieldix VEYA Tamga kurmadan) kayıtları doğrular —
    ``tamga_verify_mini`` felsefesinde bir tek-gerçek paritesi.

    Dönüş: ``(tip_hash, "ok")`` veya ``(None, "broken@<n>")``.
    """
    prev_h: str = TAMGA_GENESIS_H
    n = 0
    try:
        for rec in records:
            n += 1
            expected = compute_record_hash(rec.get("prev", ""), rec)
            if (
                rec.get("prev") != prev_h
                or rec.get("h") != expected
                or rec.get("seq") != n
            ):
                return None, f"broken@{n}"
            prev_h = rec["h"]
    except Exception:
        return None, f"broken@{n}"
    return prev_h, "ok"


# ---------------------------------------------------------------------------
# TamgaLedger — Tamga ``tamga-sim/1`` gramerli hash-zinciri
# ---------------------------------------------------------------------------
class TamgaLedger:
    """TamgaProtocol ledger modeli: ``h = sha256(prev ‖ jcs(kayıt − {h}))``.

    Kayıt şeması: ``{"seq" ( 1-based), "prev", "h"}`` + keyfi yük alanları.
    Append-only; ``verify()`` zinciri yeniden-türetir; ``yukle()`` bozuk
    zinciri belleğe hiç almaz ( fail-closed).
    """

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self.entries)

    @staticmethod
    def _hashla(seq: int, prev: str, kayit: Dict[str, Any]) -> str:
        """D5 kuralı: ``sha256(prev ‖ jcs(kayıt-h-dışı))``.

        ``prev`` hem dize-prefix hem jcs içindedir — Tamga'nın birebir kuralı.
        """
        govde = {k: v for k, v in kayit.items() if k not in _HASH_DISI_ALANLAR}
        return hashlib.sha256((prev + jcs_str(govde)).encode("utf-8")).hexdigest()

    def append(self, kayit: Dict[str, Any]) -> Dict[str, Any]:
        """Yeni Tamga kaydı ekle; ``seq``/``prev``/``h`` otomatik atanır.

        Çağrıcı yalnızca yük alanlarını verir; ``seq``/``prev``/``h`` zaten
        içeride varsa üzerine yazılır ( append-only sözü: mevcut kayıtlar
        değiştirilemez).
        """
        tam_kayit = {k: v for k, v in kayit.items() if k not in _HASH_DISI_ALANLAR}
        seq = len(self.entries) + 1
        prev = self.entries[-1]["h"] if self.entries else TAMGA_GENESIS_H
        tam_kayit["seq"] = seq
        tam_kayit["prev"] = prev
        tam_kayit["h"] = self._hashla(seq, prev, tam_kayit)
        self.entries.append(tam_kayit)
        return tam_kayit

    def verify(self) -> bool:
        """Zincir bütünlüğü: 1-based seq-sırası + prev-bağlantısı +
        hash-tekrar-hesabı.

        ``tamga_runner._verify_chain`` ile aynı kararlar:
        ``rec["prev"] != prev_h`` veya ``rec["h"] != beklenen`` veya
        ``rec["seq"] != n`` → ``False``.
        """
        prev_h = TAMGA_GENESIS_H
        for n, rec in enumerate(self.entries, start=1):
            if rec.get("seq") != n:
                return False
            if rec.get("prev") != prev_h:
                return False
            if self._hashla(n, rec["prev"], rec) != rec.get("h"):
                return False
            prev_h = rec["h"]
        return True

    def yukle(self, kayitlar: Sequence[Dict[str, Any]]) -> None:
        """Kayıtlı Tamga zincirini yeniden-kur; her kayıt için seq/prev/hash
        yeniden-doğrulanır — bozuk zincir belleğe HİÇ girmez ( fail-closed)."""
        for gelen in kayitlar:
            seq = gelen.get("seq")
            prev = gelen.get("prev")
            h = gelen.get("h")
            if not isinstance(seq, int) or not isinstance(prev, str) or not isinstance(h, str):
                raise BozukTamgaZinciriError(
                    f"eksik/bozuk Tamga kayıt-alanları: seq/prev/h ( seq={seq})"
                )
            beklenen_prev = self.entries[-1]["h"] if self.entries else TAMGA_GENESIS_H
            if seq != len(self.entries) + 1:
                raise BozukTamgaZinciriError(
                    f"seq-sırası bozuk: beklenen {len(self.entries) + 1}, gelen {seq}"
                )
            if prev != beklenen_prev:
                raise BozukTamgaZinciriError(
                    f"prev-bağlantısı bozuk ( seq {seq}): beklenen {beklenen_prev[:12]}…"
                )
            govde = {k: v for k, v in gelen.items() if k not in _HASH_DISI_ALANLAR}
            if self._hashla(seq, prev, govde) != h:
                raise BozukTamgaZinciriError(
                    f"h-doğrulaması başarısız ( seq {seq}) — Tamga zinciri kurcalanmış"
                )
            tam = dict(govde)
            tam["seq"] = seq
            tam["prev"] = prev
            tam["h"] = h
            self.entries.append(tam)

    def disa_aktar(self) -> List[Dict[str, Any]]:
        """Tamga JSONL'ye yazılabilir kayıt listesi ( kopya)."""
        return [dict(g) for g in self.entries]

    def tip(self) -> Optional[str]:
        """Zincir baş-hash'i ( son kaydın ``h``); boşsa ``None``."""
        return self.entries[-1]["h"] if self.entries else None

    def jsonl_yaz(self, yol: str | Path) -> str:
        """Zinciri ``tamga-sim/1`` JSONL olarak yaz ( Tamga verifier'lar için).

        TamgaProtocol'ün ``tests/conformance/verify.py::verify_ledger`` ve
        ``tamga_runner._verify_chain`` bu çıktıyı doğrudan doğrulayabilir.
        """
        yol = Path(yol)
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            for rec in self.entries:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return str(yol)

    def jsonl_oku(self, yol: str | Path) -> None:
        """JSONL'den fail-closed yeniden-yükleme."""
        yol = Path(yol)
        kayitlar = []
        with open(yol, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    kayitlar.append(json.loads(line))
        self.yukle(kayitlar)


# ---------------------------------------------------------------------------
# KanitTamgaSabitleyici — imzalı kanıtları Tamga zincirine bağlar
# ---------------------------------------------------------------------------
class KanitTamgaSabitleyici:
    """Yieldix imzalı kanıtlarını ( ``MonthlyReportPayload``) Tamga
    hash-zincirine sabitler.

    Her imzalı rapor için Tamga zincirine bir kayıt yazılır; kayıt kanıtın
    **kendi sha256_digest'ini + Ed25519 imzasını + genel-anahtarını** yük
    olarak taşıdığı için:

    - Tamga zinciri üzerinde yapılan herhangi bir kurcalama ``dogrula()``
      ile yakalanır ( zincir-bütünlüğü),
    - kayıttaki KPI içeriğinde yapılan her değişiklik imza-dojrulamasında
      yakalanır ( çapraz-çapa imza-bütünlüğü),
    - Yieldix tarafında rapora geriye-dönük bir değişiklik yapılırsa Tamga
      kaydındaki imza artık o içeriği **doğrulamaz**.

    ``sabitle()`` ödurumludur ( idempotent): yalnızca henüz sabitlenmemiş
    raporları işler; büyüyen bir kanıt akışı için tekrar-tekrar çağrılabilir.
    """

    def __init__(
        self,
        raporlar: Iterable[Any],
        tamga: Optional[TamgaLedger] = None,
        public_key_hex: Optional[str] = None,
        signer: Optional[Ed25519ReportSigner] = None,
    ) -> None:
        self.raporlar: List[Any] = list(raporlar)
        self.tamga = tamga if tamga is not None else TamgaLedger()
        if public_key_hex is not None:
            self.public_key_hex = public_key_hex
        elif signer is not None:
            self.public_key_hex = signer.public_key_hex
        else:
            self.public_key_hex = None
        # hangi report_id'ler zaten sabitlendi ( idempotency)
        self._sabitlenen: set = set()
        for rec in self.tamga.entries:
            if rec.get("op") == ANCHOR_OP and rec.get("kaynak") == KAYNAK_PROJE:
                self._sabitlenen.add(rec.get("report_id"))

    # --- sabitleme ---------------------------------------------------------
    def _sabitle_rapor(self, report: Any, ts: Optional[str] = None) -> Dict[str, Any]:
        """Bir imzalı raporu Tamga kaydına dönüştür ( sabitleme-birimi).

        ``build_anchor_record`` ile aynı yük şeması — tek fark, seq/prev/h'nin
        ``TamgaLedger.append`` tarafından atanmasıdır.
        """
        if report.sha256_digest is None or report.ed25519_signature is None:
            raise ValueError(
                "imzasiz-kanit: report.sha256_digest/ed25519_signature eksik — "
                "sabitlemek için önce imzalayın ( AT-077)"
            )
        kanit = _json_saf_yap(MonthlyReportGenerator.to_signable_dict(report))
        kayit: Dict[str, Any] = {
            "op": ANCHOR_OP,
            "ts": ts or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "kaynak": KAYNAK_PROJE,
            "report_id": report.report_id,
            "tenant_id": report.tenant_id,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "kanit": kanit,
            "sha256_digest": report.sha256_digest,
            "ed25519_signature": report.ed25519_signature,
            "public_key_hex": self.public_key_hex,
        }
        return self.tamga.append(kayit)

    def sabitle(self, sadece_yeni: bool = True) -> Dict[str, Any]:
        """İmzalı kanıtları Tamga zincirine sabitle.

        ``sadece_yeni=True`` ( varsayılan): yalnızca yeni raporları işler
        ( idempotent). ``False``: tüm raporları yeniden sabitler ( mevcut
        Tamga zincirinin devamına ekler — dikkat: tekrarlı kayıtlar oluşur).

        Dönen özet: ``{"sabitlelenen": n, "tamga_seq_ilk": …,
        "tamga_seq_son": …, "tamga_tip": …}``.
        """
        sabitleme_sirasi = [
            r for r in self.raporlar
            if not (sadece_yeni and r.report_id in self._sabitlenen)
        ]
        ilk = len(self.tamga) + 1
        for rapor in sabitleme_sirasi:
            self._sabitle_rapor(rapor)
            self._sabitlenen.add(rapor.report_id)
        return {
            "sabitlelenen": len(sabitleme_sirasi),
            "tamga_seq_ilk": ilk if sabitleme_sirasi else None,
            "tamga_seq_son": len(self.tamga) if sabitleme_sirasi else None,
            "tamga_tip": self.tamga.tip(),
        }

    # --- doğrulama ---------------------------------------------------------
    def dogrula(self) -> bool:
        """Üç katmanlı doğrulama ( hepsi sağlanmalı):

        1. **Tamga zincir bütünlüğü** — ``TamgaLedger.verify()`` ( D5 kuralı):
           1-based seq + prev-bağlantısı + hash-tekrar-hesabı.
        2. **Çapraz-çapa imza-bütünlüğü** — her sabitlenmiş kaydın
           ``sha256_digest``'i kayıttaki ``kanit`` içeriğinden yeniden
           hesaplandığında aynı olmalı VE Ed25519 imzası genel-anahtar
           altında o içerik için geçerli olmalı ( AT-077 üretim yolu).
        3. **Tamlık ( completeness)** — her rapor Tamga zincirine
           sabitlenmiş olmalı ( kaçırılmış kanıt yok).
        """
        # 1. Tamga zinciri
        if not self.tamga.verify():
            return False

        sabitli_rapor = set()
        for rec in self.tamga.entries:
            if rec.get("op") != ANCHOR_OP or rec.get("kaynak") != KAYNAK_PROJE:
                continue
            # 2. çapraz-çapa: kanıt-imzası yeniden doğrulanır
            kanit = rec.get("kanit")
            if not isinstance(kanit, dict):
                return False
            if sha256_digest_hex(kanit) != rec.get("sha256_digest"):
                return False  # kanıt içeriği kurcalanmış
            sig = rec.get("ed25519_signature")
            pk = rec.get("public_key_hex")
            if not isinstance(sig, str) or not isinstance(pk, str):
                return False  # imza/anahtar eksik — doğrulanamaz kanıt
            if not Ed25519ReportSigner.verify_signature(kanit, sig, pk):
                return False  # Ed25519 imzası o içerikte geçersiz
            sabitli_rapor.add(rec.get("report_id"))

        # 3. tamlık: her rapor sabitlenmiş olmalı
        beklenen = {r.report_id for r in self.raporlar}
        if sabitli_rapor != beklenen:
            return False

        return True

    def ozet(self) -> Dict[str, Any]:
        """Sabitleme durum özeti ( denetim-raporu amaçlı)."""
        return {
            "kaynak_rapor": len(self.raporlar),
            "tamga_kayit": len(self.tamga),
            "sabitlenen": len(self._sabitlenen),
            "tamga_tip": self.tamga.tip(),
            "tamga_format": TAMGA_LEDGER_FORMAT,
            "dogru": self.dogrula(),
        }


# ---------------------------------------------------------------------------
# Tek-ışık API'ler
# ---------------------------------------------------------------------------
def anchor_report(
    report: Any,
    ledger_path: str | Path,
    public_key_hex: Optional[str] = None,
    signer: Optional[Ed25519ReportSigner] = None,
    ts: Optional[str] = None,
    issuer: Optional[str] = None,
) -> Dict[str, Any]:
    """``report`` kanıtını ``ledger_path``'deki Tamga zincirine uygun ekler.

    Mevcut zinciri önce doğrular; kırık ise fail-closed ( kayıt eklemez).
    Dönüş: eklenen kayıt ( ``h`` dahil).
    """
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        # fail-closed: kırık zincire asla ekleme
        _, reason = verify_chain(records)
        if reason != "ok":
            raise BozukTamgaZinciriError(
                f"kirik-ledgere-eklenmiyor: {reason} — Tamga zinciri kurcalanmış"
            )

    seq = len(records) + 1
    prev_hash = records[-1]["h"] if records else TAMGA_GENESIS_H

    if public_key_hex is None and signer is not None:
        public_key_hex = signer.public_key_hex

    record = build_anchor_record(
        report,
        prev_hash=prev_hash,
        seq=seq,
        ts=ts,
        issuer=issuer,
        public_key_hex=public_key_hex,
    )

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def sabitle_raporlar(
    raporlar: Iterable[Any],
    public_key_hex: Optional[str] = None,
    signer: Optional[Ed25519ReportSigner] = None,
) -> KanitTamgaSabitleyici:
    """Tek-ışık: imzalı raporları yeni bir Tamga zincirine sabitleyip döner."""
    sabitleyici = KanitTamgaSabitleyici(
        raporlar, public_key_hex=public_key_hex, signer=signer
    )
    sabitleyici.sabitle()
    return sabitleyici
