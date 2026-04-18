import re
import unicodedata
import difflib


def canonicalizza_nome(raw: str | None) -> str | None:
    """
    Normalizza un nome proprio in forma canonica (title-case, spazi ridotti,
    apostrofo normalizzato, solo caratteri alfabetici/spazi/apostrofi/trattini).

    Ritorna None se l'input e' None, vuoto, o contiene caratteri non ammessi.
    """
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", raw)
    s = s.replace("\u00A0", " ")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u2019", "'")   # apostrofo curvo → dritto
    s = s.replace("\u2018", "'")
    if not s or not re.match(r"^[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF\s'\-\.]+$", s):
        return None
    return s.title()


def trova_alias_simili(
    nomi: list[str], soglia: float = 0.88
) -> list[tuple[str, list[str]]]:
    """
    Raggruppa nomi simili (potenziali alias / typo) usando SequenceMatcher.

    Ritorna una lista di (nome_riferimento, [simili]) dove ogni nome_riferimento
    non e' gia' stato classificato come simile di un altro.
    """
    nomi_sorted = sorted(set(nomi))
    gruppi: list[tuple[str, list[str]]] = []
    visti: set[str] = set()
    for n in nomi_sorted:
        if n in visti:
            continue
        simili = [
            m for m in nomi_sorted
            if m != n and difflib.SequenceMatcher(None, n, m).ratio() >= soglia
        ]
        if simili:
            visti.update(simili)
            visti.add(n)
            gruppi.append((n, simili))
    return gruppi
