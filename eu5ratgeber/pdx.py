"""Parser für das Paradox-Textformat (Spielstände und Spieldateien).

parse(bytes) liefert verschachtelte dicts/lists:
  key=value            -> dict[key] = value
  key mehrfach         -> dict[key] = [wert1, wert2, ...]  (erst ab dem zweiten Vorkommen)
  { a b c }            -> list
  { { ... } { ... } }  -> list von dicts
  color=rgb { 1 2 3 }  -> ("rgb", [1, 2, 3])
  key<5 / key>=5 ...   -> dict["key<"] = 5 (Vergleiche aus Spieldateien)
Zahlen werden zu int/float, alles andere bleibt str (Anführungszeichen entfernt).
Kommentare (#...) werden übersprungen. Datumswerte wie 1337.4.1 bleiben str.
"""
import re

TOKEN = re.compile(
    rb'"(?:[^"\\]|\\.)*"'          # Zeichenkette, auch mehrzeilig
    rb'|#[^\n]*'                   # Kommentar
    rb'|[<>!?]=|[{}=<>]'           # Klammern und Operatoren
    rb'|[^\s{}=<>!?"#]+'           # Wort / Zahl / Datum
    rb'|[!?]'                      # einzelnes ! oder ? (selten)
)
INT = re.compile(rb"-?\d+\Z")
FLOAT = re.compile(rb"-?\d*\.\d+\Z")
OPS = {b"<", b">", b"<=", b">=", b"!=", b"?="}
COLOR_WORDS = {b"rgb", b"hsv", b"hsv360", b"hex"}


def _atom(tok):
    if tok[:1] == b'"':
        return tok[1:-1].replace(b'\\"', b'"').decode("utf-8", "replace")
    if INT.match(tok):
        return int(tok)
    if FLOAT.match(tok):
        return float(tok)
    return tok.decode("utf-8", "replace")


def _tokens(data):
    for m in TOKEN.finditer(data):
        t = m.group()
        if t[:1] != b"#":
            yield t


class _Stream:
    __slots__ = ("it", "buf")

    def __init__(self, data):
        self.it = _tokens(data)
        self.buf = []

    def next(self):
        return self.buf.pop() if self.buf else next(self.it, None)

    def push(self, t):
        self.buf.append(t)


def _put(obj, key, val):
    if key in obj:
        old = obj[key]
        if isinstance(old, _Multi):
            old.append(val)
        else:
            obj[key] = _Multi([old, val])
    else:
        obj[key] = val


class _Multi(list):
    """Liste aus wiederholten Schlüsseln (unterscheidbar von einer {a b c}-Liste)."""


def _value(s, tok):
    if tok is None:          # Datei endet nach "key="
        return None
    if tok == b"{":
        return _block(s)
    val = _atom(tok)
    if tok in COLOR_WORDS:
        nxt = s.next()
        if nxt == b"{":
            return (val, _block(s))
        if nxt is not None:
            s.push(nxt)
    return val


def _block(s):
    """Liest bis zur schließenden Klammer. Ergebnis: dict, list oder gemischt als dict."""
    obj = {}
    items = []
    while True:
        tok = s.next()
        if tok is None or tok == b"}":
            break
        if tok == b"{":
            items.append(_block(s))
            continue
        nxt = s.next()
        if nxt == b"=" or nxt in OPS:
            key = _atom(tok)
            if nxt != b"=":
                key = f"{key}{nxt.decode()}"
            _put(obj, key, _value(s, s.next()))
        else:
            items.append(_value(s, tok))
            if nxt is not None:
                s.push(nxt)
    if obj and items:
        obj["_items"] = items
        return obj
    return obj if obj else items


def parse(data):
    """Parst einen ganzen Text (Datei oder Ausschnitt ohne äußere Klammern)."""
    return _block(_Stream(data))


def parse_block(data):
    """Parst einen Ausschnitt der Form 'key={ ... }' bzw. '{ ... }' und gibt den Inhalt zurück."""
    i = data.find(b"{")
    return _block(_Stream(data[i + 1:]))


def as_list(v):
    """Wert als Liste - für Schlüssel, die mal einfach, mal mehrfach vorkommen."""
    if v is None:
        return []
    return list(v) if isinstance(v, _Multi) else [v]
