import re
import unicodedata
import difflib


def _is_valid_name_char(c: str) -> bool:
    """
    Verifica se un carattere e' ammesso in un nome:
    - Lettera Unicode (categoria che inizia con "L")
    - Spazio, apostrofo, trattino, punto
    """
    cat = unicodedata.category(c)
    return cat.startswith("L") or c in " '-."


def canonicalizza_nome(raw: str | None) -> str | None:
    """
    Normalizza un nome proprio in forma canonica (title-case, spazi ridotti,
    apostrofo normalizzato, solo caratteri alfabetici/spazi/apostrofi/trattini).

    Ritorna None se l'input e' None, vuoto, o contiene caratteri non ammessi.
    """
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", raw)
    s = s.replace(" ", " ")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("’", "'")   # apostrofo curvo → dritto
    s = s.replace("‘", "'")
    if not s or not all(_is_valid_name_char(c) for c in s):
        return None
    s = " ".join(s.split()).title()
    if not any(c.isalpha() for c in s):
        return None
    return s


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
