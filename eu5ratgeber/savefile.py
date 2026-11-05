"""Gezielter Zugriff auf einen EU5-Text-Spielstand.

Ein Durchlauf über die Datei merkt sich Anfang und Ende aller Blöcke bis INDEX_DEPTH
(z. B. countries/database/382). Zeichenketten werden dabei als Ganzes übersprungen, damit
Klammern darin nicht zählen. Danach wird nur zerlegt, was gebraucht wird.

    s = SaveFile(pfad)
    s.meta                          # metadata-Block
    s.block("countries/tags")       # beliebiger Block bis Tiefe 3, zerlegt
    s.entry("countries/database", 382)
    s.entry_ids("building_manager/database")
    s.raw_entry(...)                # Rohbytes, z. B. für schnelle Vorfilter
"""
import re
import time

from . import pdx
from .sprache import ue

INDEX_DEPTH = 3
SCAN = re.compile(rb'"(?:[^"\\]|\\.)*"|[{}]')
KEY_BEFORE = re.compile(rb'([^\s{}=]+)\s*=\s*$')


class SaveFile:
    def __init__(self, path):
        t0 = time.time()
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        nl = self.data.find(b"\n")
        self.header = self.data[:nl].decode("ascii", "replace")
        # Kopf: SAV02 + 10 Zeichen + Format (0004 = Text, 0006 = binär gepackt) + ...
        if self.header[15:19] != "0004":
            raise ValueError(ue(t"Kein Text-Spielstand (Kopf {self.header}) - Startoption -force_text_save setzen"))
        self.blocks = {}     # "a/b/c" -> (start, end) ; start = Position von '{', end = nach '}'
        self.children = {}   # "a/b"   -> [(key, start, end), ...]
        self._index(nl + 1)
        self.index_seconds = time.time() - t0
        self.meta = self.block("metadata")

    def _index(self, pos):
        data = self.data
        stack = []           # je offener Block: (key|None, start)
        depth = 0
        for m in SCAN.finditer(data, pos):
            c = data[m.start()]
            if c == 123:                              # {
                if depth < INDEX_DEPTH:
                    s = m.start()
                    ls = data.rfind(b"\n", 0, s) + 1
                    k = KEY_BEFORE.search(data, ls, s)
                    stack.append((k.group(1).decode("utf-8", "replace") if k else None, s))
                depth += 1
            elif c == 125:                            # }
                depth -= 1
                if depth < INDEX_DEPTH:
                    key, s = stack.pop()
                    if key is None:
                        continue
                    parent = "/".join(k for k, _ in stack if k is not None)
                    path = f"{parent}/{key}" if parent else key
                    end = m.end()
                    self.children.setdefault(parent, []).append((key, s, end))
                    if path not in self.blocks:
                        self.blocks[path] = (s, end)
            # Zeichenketten: nichts zu tun, sie sind als Ganzes übersprungen
        if depth != 0:
            raise ValueError(ue(t"Klammern gehen nicht auf (Tiefe {depth} am Dateiende)"))

    # --- Zugriff -------------------------------------------------------------------------

    def raw(self, path):
        s, e = self.blocks[path]
        return self.data[s:e]

    def block(self, path):
        return pdx.parse_block(self.raw(path))

    def entry_ids(self, parent):
        return [int(k) for k, _, _ in self.children.get(parent, []) if k.lstrip("-").isdigit()]

    def raw_entry(self, parent, eid):
        return self._entry_map(parent).get(int(eid))

    def entry(self, parent, eid):
        raw = self.raw_entry(parent, eid)
        return pdx.parse_block(raw) if raw is not None else None

    def raw_entries(self, parent):
        """(id, rohbytes) für alle Einträge eines database-Blocks."""
        d = self.data
        for k, s, e in self.children.get(parent, []):
            if k.lstrip("-").isdigit():
                yield int(k), d[s:e]

    def _entry_map(self, parent):
        cache = self.__dict__.setdefault("_emaps", {})
        if parent not in cache:
            cache[parent] = {int(k): self.data[s:e] for k, s, e in self.children.get(parent, [])
                             if k.lstrip("-").isdigit()}
        return cache[parent]

    def top_scalar(self, key):
        """Einfacher Wert auf oberster Ebene, z. B. 'current_age'."""
        m = re.search(rb"\n" + re.escape(key.encode()) + rb"=([^\s{]+)", self.data)
        return pdx._atom(m.group(1)) if m else None
