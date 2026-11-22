"""Besonderheiten des Landes (0.31 Teil 4, Nutzer 08.11.: „in der übersicht sollte noch alles individuelle eines landes aufgelistet
sein, was sie von anderen unterscheidet: besondere mechaniken, gesetze, einheiten, technologien, staatsformen usw.“).

Was als Besonderheit zählt (Regel des Ratgebers): ein Eintrag der Spieldateien, dessen Sichtbarkeit (potential, bei Einheiten
country_potential, bei Situationen visible, bei Katastrophen can_start) an das Land, seine Kultur, seine Religion oder die Lage seiner
Hauptstadt gebunden ist – und für uns zutrifft. Genauer: die ganze Bedingung ist erfüllt und mindestens eine der Bindungen trifft zu, die
nicht unter NOT steht (has_or_had_tag, tag, original_tag; culture, culture.language, culture.dialect; religion, religion.group; capital,
original_capital mit Region, Gebiet, Provinz oder Subkontinent). Bindungen in Spielbedingungen (scripted_triggers) zählen mit. Was nur an
Regierungsform, Rang, Zeitalter oder den Kontinent der Hauptstadt hängt, haben viele Länder – das zählt nicht (Probelauf Walachei 08.11.:
Kriegsgaleone und Schwarzer Tod hingen nur am Kontinent Europa).

Dazu, was eigene Fortschritte freischalten (unlock_unit, unlock_government_reform, unlock_law …): einzigartige Einheiten und Reformen
stehen oft nur dort.

Ausgewertet mit techbaum.Bedingung (dieselbe Prüfung wie Techbaum und Forschung) und techbaum.fakten aus der Momentaufnahme.
"""
import json

from . import techbaum, wiki
from .sprache import ue

# Bindung -> Grund (Anzeige); Reihenfolge = Rang des Grunds
GRUENDE = (("land", ue("Land")), ("kultur", ue("Kultur")), ("religion", ue("Religion")), ("region", ue("Lage")))
BINDUNG = {"has_or_had_tag": "land", "tag": "land", "original_tag": "land",
           "culture": "kultur", "culture.language": "kultur", "culture.dialect": "kultur",
           "religion": "religion", "religion.group": "religion",
           "capital": "region", "original_capital": "region"}
# Arten (Anzeige-Reihenfolge): Schlüssel, Bezeichnung, [(Ordner, Bedingungsfeld, Bezeichnung je Eintrag)], Freischaltung durch
# Fortschritte (Feld unlock_…), Seitenleiste des Spiels
ARTEN = (
    ("fortschritte", ue("Fortschritte"), (("advances", "potential", ue("Fortschritt")),), (), "advances"),
    ("einheiten", ue("Einheiten"), (("unit_types", "country_potential", ue("Einheit")),), ("unlock_unit",), "military_ledger"),
    ("staat", ue("Staatsform und Reformen"), (("government_reforms", "potential", ue("Reform")),
                                              ("heir_selections", "potential", ue("Erbfolge")),
                                              ("parliament_types", "potential", ue("Parlament"))),
     ("unlock_government_reform", "unlock_heir_selection"), "government_reforms"),
    ("gesetze", ue("Gesetze"), (("laws", "potential", ue("Gesetz")),), ("unlock_law", "unlock_policy"), "laws"),
    ("staende", ue("Stände und Privilegien"), (("estate_privileges", "potential", ue("Privileg")),), ("unlock_estate_privilege",),
     "government"),
    ("mechaniken", ue("Besondere Mechaniken"), (("cabinet_actions", "potential", ue("Kabinettsaktion")),
                                                ("decisions", "potential", ue("Entscheidung")),
                                                ("generic_actions", "potential", ue("Aktion")),
                                                ("country_interactions", "potential", ue("Diplomatische Aktion")),
                                                ("character_interactions", "potential", ue("Personen-Aktion")),
                                                ("bureaucracies", "potential", ue("Bürokratie")),
                                                ("town_rights", "potential", ue("Stadtrecht")),
                                                ("chivalric_orders", "potential", ue("Ritterorden")),
                                                ("parliament_agendas", "potential", ue("Parlamentsvorhaben")),
                                                ("situations", "visible", ue("Situation")),
                                                ("disasters", "can_start", ue("Katastrophe"))),
     ("unlock_cabinet_action",), "government"),
)
MAX_TIEFE = 6
LAGE = ("region", "area", "province", "sub_continent")       # Lage zählt nur feiner als der Kontinent
RANG = {"land": 0, "kultur": 1, "region": 2, "religion": 3, "fortschritt": 4}
ACTOR = "scope:actor"                                       # Aktionen und Diplomatie: der Handelnde (wir)


def _liste(v):
    return v if isinstance(v, list) else [v]


def bindungen(b, vg, neg=False, tiefe=0):
    """Bindungen (Schlüssel, Wert) eines Bedingungsblocks, die nicht unter NOT/NOR/NAND stehen – auch in Spielbedingungen
    (scripted_triggers = yes) und Wenn-Zweigen; capital.region und original_capital.region zählen als Lage. scope:actor = { … } (Aktionen
    und Diplomatie: der Handelnde sind wir) zählt wie AND, scope:actor.religion wie religion (Prüfer 08.11.: sonst lieferten Aktionen,
    Diplomatische und Personen-Aktionen nie einen Eintrag)."""
    out = []
    if not isinstance(b, dict) or tiefe > MAX_TIEFE:
        return out
    st = vg("scripted_triggers") or {}
    for k, v in b.items():
        k0 = str(k)[:-2] if str(k).endswith("?=") else str(k)
        k0 = k0[len(ACTOR) + 1:] if k0.startswith(ACTOR + ".") else k0
        for x in _liste(v):
            if k0 == ACTOR and isinstance(x, dict):
                out += bindungen(x, vg, neg, tiefe + 1)
            elif k0 in ("NOT", "not", "NOR", "nor", "NAND", "nand"):
                out += bindungen(x, vg, not neg, tiefe + 1)
            elif k0 in ("AND", "and", "OR", "or", "custom_tooltip", "trigger_if", "trigger_else_if", "trigger_else"):
                out += bindungen({a: c for a, c in x.items() if a not in ("limit", "text")} if isinstance(x, dict) else {}, vg, neg,
                                 tiefe + 1)
            elif k0 in st and x in ("yes", "no") and isinstance((st[k0] or {}).get("def"), dict):
                out += bindungen(st[k0]["def"], vg, neg if x == "yes" else not neg, tiefe + 1)
            elif not neg:
                art = BINDUNG.get(k0) or BINDUNG.get(k0.split(".")[0] if k0.split(".")[0] in ("capital", "original_capital") else "")
                if art == "region" and not _fein(k0, x, vg):
                    continue
                if art:
                    out.append((art, k0, x))
    return out


def _fein(k0, x, vg):
    """Lage-Bindung nennt Region, Gebiet, Provinz oder Subkontinent (nicht nur den Kontinent) – auch über eine Spielbedingung im
    Hauptstadt-Block (Prüfer 08.11.: unlock_camel_*_advance mit unit_camelry_region_trigger)."""
    if "." in k0:
        return k0.split(".", 1)[1] in LAGE
    return any(str(a).rstrip("?=") in LAGE for a in _schluessel(x, vg))


def _schluessel(x, vg, tiefe=0):
    """Schlüssel eines Blocks, verschachtelt; Spielbedingungen (scripted_triggers = yes) durch ihre Schlüssel ersetzt."""
    out = []
    st = vg("scripted_triggers") or {}
    if isinstance(x, dict) and tiefe <= MAX_TIEFE:
        for k, v in x.items():
            k0 = str(k).rstrip("?=")
            for y in _liste(v):
                if k0 in st and y in ("yes", "no") and isinstance((st[k0] or {}).get("def"), dict):
                    out += _schluessel(st[k0]["def"], vg, tiefe + 1)
                    continue
                out.append(k)
                out += _schluessel(y, vg, tiefe + 1)
    return out


class Bedingung(techbaum.Bedingung):
    """techbaum.Bedingung mit
    - religion = { group = … } (Gesetze der Spieldateien schreiben die Religionsgruppe so) und Merkmalen der Religion
      (has_autocephalous_patriarchates = yes: Feld der Religion in den Spieldateien),
    - scope:actor = { … } und scope:actor.<x> (Aktionen und Diplomatie: der Handelnde sind wir),
    - has_advance (erforscht laut Spielstand)."""

    def knoten(self, k, x, scope):
        k0 = k[:-2] if k.endswith("?=") else k
        if k0.startswith(ACTOR + "."):
            return self.knoten(k0[len(ACTOR) + 1:], x, scope)
        if k0 == ACTOR and isinstance(x, dict):
            kinder, ok = self.block(x, scope)
            return [ue("Wir (Handelnde):"), ok, kinder]
        if k0 == "religion" and isinstance(x, dict):
            rd = ((self.vg("religions") or {}).get(self.F.get("religion")) or {}).get("def") or {}
            kinder = []
            for a, ws in x.items():
                a0 = a[:-2] if a.endswith("?=") else a
                feld = {"group": "religion.group", "this": "religion"}.get(a0)
                for w in techbaum._liste(ws):                   # Prüfer 08.11.: Liste (Schlüssel mehrfach) stürzte ab
                    if feld:
                        kinder.append(self.knoten(feld, w, scope))
                    elif w in ("yes", "no") and self.F.get("religion") and rd:
                        # Merkmal unserer Religion laut Spieldateien – Anzeige: die Religion (der Schlüssel sagt dem Spieler nichts)
                        kinder.append([self.name("religions", self.F["religion"]), str(rd.get(a0) or "no").lower() == w, []])
                    else:
                        kinder.append([ue(t"religion.{a} = {w} (nicht auswertbar)"), None, []])
            return [ue("Religion:"), techbaum._und([n[1] for n in kinder]), kinder]
        if k0 == "has_advance" and isinstance(x, str):
            e = self.F.get("erforscht")
            a = techbaum._ohne(x)
            return [ue(t"Fortschritt {self.name('advances', a)} erforscht"), None if e is None else a in e, []]
        return super().knoten(k, x, scope)


def _name(e, key, nm):
    n = (e or {}).get("name") if isinstance(e, dict) else None
    if not n or n == key:
        n = nm(key)
    if not n or n == key:                                # Entscheidungen: Titel unter <key>.title (decisions/*_l_<sprache>.yml)
        n = nm(f"{key}.title")
        n = None if n == f"{key}.title" else n
    return n if n else key


def _blaetter(n):
    """Texte der zutreffenden Einzelbedingungen unter einem Knoten (Gruppen wie „eine davon:“ fallen weg)."""
    if not n[2]:
        return [n[0]]
    return [x for k in n[2] if k[1] is True for x in _blaetter(k)]


def _text(n):
    """Text eines zutreffenden Knotens: bei Blöcken (Kultur:, Hauptstadt:) die zutreffenden Einzelbedingungen dahinter."""
    teile = _blaetter(n) if n[2] else []
    return f"{n[0]} {', '.join(teile)}" if teile and n[0].endswith(":") else n[0]


def _gruende(B, bind):
    """Gründe einer zutreffenden Bindung (Reihenfolge wie GRUENDE) mit dem Text der Prüfung."""
    out = {}
    for art, k, x in bind:
        n = B.knoten(k, x, "land")
        if n[1] is True and art not in out:
            out[art] = _text(n)
    return [{"art": a, "name": l, "text": out[a]} for a, l in GRUENDE if a in out]


# Stand eines Eintrags: Kennung -> Anzeige (researched: erforscht, active: gilt jetzt, unlocked: freischaltender Fortschritt erforscht)
STATUS = {"researched": ue("erforscht"), "active": ue("aktiv"), "unlocked": ue("freigeschaltet")}


def _status(art, ordner, key, F, last):
    """researched/active, wo der Spielstand es zeigt (STATUS); sonst None."""
    if ordner == "advances":
        return "researched" if key in set(F.get("erforscht") or []) else None
    if ordner == "government_reforms":
        return "active" if key in set(F.get("reformen") or []) else None
    if ordner == "estate_privileges":
        return "active" if key in set(last.get("privilegien") or []) else None
    if ordner == "laws":
        g = last.get("gesetze")
        return "active" if isinstance(g, dict) and key in g else None
    return None


def build(last, vg, names=None, wis=None, dlcs=None):
    """Besonderheiten unseres Lands: {grundlagen, arten: [{key, name, ansicht, eintraege, anzahl, aktiv}], offen}. vg(ordner) liefert einen
    Ordner des Spielwissens (history._voll). Ohne Momentaufnahme oder Spielwissen {}."""
    if not last or not vg or not (vg("advances") or {}):
        return {}
    nm = names or (lambda k: k)
    F = techbaum.fakten(last, vg, wis, techbaum.installierte_dlcs() if dlcs is None else dlcs)
    B = Bedingung(F, vg, nm)
    unlock = {}                                          # Feld unlock_… -> {Schlüssel: [eigene Fortschritte]}
    arten, offen = [], 0
    for akey, aname, quellen, frei_felder, ansicht in ARTEN:
        eintraege, gesehen = [], set()
        for ordner, feld, typ in quellen:
            for key, e in sorted((vg(ordner) or {}).items()):
                d = e.get("def") if isinstance(e, dict) else None
                pot = d.get(feld) if isinstance(d, dict) else None
                if not isinstance(pot, dict):
                    continue
                bind = bindungen(pot, vg)
                if not bind:
                    continue
                ok = B.pruefe(pot)
                gr = _gruende(B, bind) if ok is not False else []
                if not gr:
                    continue
                st = _status(akey, ordner, key, F, last)
                if ok is None and not st:                # Bindung trifft zu, eine andere Bedingung bleibt offen; was wir schon
                    offen += 1                           # haben (Gesetz gilt, erforscht …), war sichtbar (Walachei: Patriarchat)
                    continue
                eintraege.append({"key": key, "name": _name(e, key, nm), "typ": typ, "ordner": ordner, "gruende": gr,
                                  "status": st,
                                  "zeitalter": d.get("age") if ordner in ("advances", "unit_types") else None,
                                  **_verweis(ordner, key)})
                gesehen.add(key)
                if ordner == "advances":
                    for ff in ("unlock_unit", "unlock_government_reform", "unlock_heir_selection", "unlock_law", "unlock_policy",
                               "unlock_estate_privilege", "unlock_cabinet_action"):
                        for u in _alle(d, ff):
                            unlock.setdefault(ff, {}).setdefault(u, []).append(key)
        # über eigene Fortschritte freigeschaltet (nur, was nicht schon selbst gebunden ist)
        for ff in frei_felder:
            for u, advs in sorted((unlock.get(ff) or {}).items()):
                if u in gesehen:
                    continue
                ordner = {"unlock_unit": "unit_types", "unlock_government_reform": "government_reforms",
                          "unlock_heir_selection": "heir_selections", "unlock_law": "laws", "unlock_policy": "policies",
                          "unlock_estate_privilege": "estate_privileges", "unlock_cabinet_action": "cabinet_actions"}[ff]
                e = (vg(ordner) or {}).get(u)
                adv_namen = [_name((vg("advances") or {}).get(a), a, nm) for a in advs]
                eintraege.append({"key": u, "name": _name(e, u, nm), "typ": next(t for o, _, t in quellen if o == ordner)
                                  if any(o == ordner for o, _, _ in quellen) else ue("Politlinie"), "ordner": ordner,
                                  "gruende": [{"art": "fortschritt", "name": ue("Fortschritt"),
                                               "text": ue(t"freigeschaltet durch {', '.join(adv_namen)}")}],
                                  "status": _status(akey, ordner, u, F, last)
                                  or ("unlocked" if any(a in set(F.get("erforscht") or []) for a in advs) else None),
                                  "zeitalter": None, "durch": advs, **_verweis(ordner, u)})
                gesehen.add(u)
        # Reihenfolge: Land, Kultur, Lage, Religion, über Fortschritte; darin Erforschtes/Aktives zuerst, dann nach Name
        eintraege.sort(key=lambda x: (RANG.get(x["gruende"][0]["art"], 9), not x["status"], x["name"].lower()))
        if eintraege:
            arten.append({"key": akey, "name": aname, "ansicht": ansicht, "eintraege": eintraege, "anzahl": len(eintraege),
                          "aktiv": sum(1 for x in eintraege if x["status"])})
    return {"grundlagen": grundlagen(last, F, vg, nm), "arten": arten, "offen": offen}


def fuer_series(last, vg, names=None, wis=None):
    """Wie build; ein Fehler hier darf die übrige Rechnung nicht verhindern -> {"fehler": …} (wie startstrategie, Prüfer 08.11.)."""
    try:
        return build(last, vg, names, wis)
    except Exception as e:                       # noqa: BLE001
        return {"fehler": f"{type(e).__name__}: {e}"}


def _verweis(ordner, key):
    """Seite im Browser: Fortschritte in den Techbaum, sonst ins Wiki – nur Ordner, die das Wiki führt (wiki.im_wiki)."""
    if ordner == "advances":
        return {"techbaum": f"techbaum/{key}"}
    return {"wiki": f"wiki/{ordner}/{key}"} if wiki.im_wiki(ordner) else {}


def _alle(d, feld):
    """Alle Werte eines Felds in einem Block, auch verschachtelt (unlock_unit steht teils in Unterblöcken)."""
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            if k == feld:
                out += [x for x in _liste(v) if isinstance(x, str)]
            else:
                out += _alle(v, feld)
    elif isinstance(d, list):
        for v in d:
            out += _alle(v, feld)
    return out


def grundlagen(last, F, vg, nm):
    """Land, Kultur (mit Gruppen), Religion (mit Gruppe), Regierungsform – woran die Besonderheiten hängen."""
    def n(ordner, k):
        return _name((vg(ordner) or {}).get(k), k, nm) if k else None
    meta = last.get("meta") or {}
    return {"land": meta.get("land") or F.get("tag"), "tag": F.get("tag"),
            "kultur": n("cultures", F.get("kultur")), "kulturgruppen": [n("culture_groups", g) for g in F.get("kulturgruppen") or []],
            "religion": n("religions", F.get("religion")), "religionsgruppe": n("religion_groups", F.get("religionsgruppe")),
            "regierungsform": n("government_types", F.get("regierung")),
            "hauptstadt": next((o.get("name") for o in last.get("orte") or [] if o.get("hauptstadt")), None)}


def kurz(b):
    """Kurzfassung für Tests und Fehlersuche."""
    return json.dumps({a["key"]: [x["key"] for x in a["eintraege"]] for a in (b or {}).get("arten") or []}, ensure_ascii=False)
