"""Test per vincoli personalizzati nel solver (incompatibile + preferenza_coppia)."""
import pytest

try:
    from ortools.sat.python import cp_model as _cp
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False

pytestmark = pytest.mark.skipif(not _ORTOOLS_OK, reason="ortools non installato")

from turni_visite.scheduling import ottimizza_turni_mesi


def _params_con_vincoli():
    fratelli = {"Mario", "Luigi", "Carla", "Anna"}
    famiglie = {"Fam A"}
    associazioni = {"Fam A": ["Mario", "Luigi", "Carla", "Anna"]}
    frequenze = {"Fam A": 2}
    capacita = {fr: 2 for fr in fratelli}
    return fratelli, famiglie, associazioni, frequenze, capacita


class TestVincoloIncompatibile:
    def test_incompatibili_non_nella_stessa_famiglia_mese(self):
        fr, fam, assoc, freq, cap = _params_con_vincoli()
        vincoli = [{"fratello_a": "Mario", "fratello_b": "Luigi", "tipo": "incompatibile"}]
        sol = ottimizza_turni_mesi(
            mesi=["2026-01"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
        )
        assert sol is not None
        slots = sol["by_month"]["2026-01"]["by_family"]["Fam A"]
        assert not ("Mario" in slots and "Luigi" in slots), \
            f"Mario e Luigi incompatibili ma assegnati insieme: {slots}"

    def test_incompatibili_su_piu_mesi(self):
        fr = {"Mario", "Luigi", "Carla", "Anna", "Elena", "Bruno"}
        fam = {"Fam A"}
        assoc = {"Fam A": ["Mario", "Luigi", "Carla", "Anna", "Elena", "Bruno"]}
        freq = {"Fam A": 2}
        cap = {f: 2 for f in fr}
        vincoli = [{"fratello_a": "Mario", "fratello_b": "Luigi", "tipo": "incompatibile"}]
        sol = ottimizza_turni_mesi(
            mesi=["2026-01", "2026-02"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
        )
        assert sol is not None
        for mese in ["2026-01", "2026-02"]:
            slots = sol["by_month"][mese]["by_family"]["Fam A"]
            assert not ("Mario" in slots and "Luigi" in slots)

    def test_incompatibili_su_piu_famiglie(self):
        fr = {"Mario", "Luigi", "Carla", "Anna"}
        fam = {"Fam A", "Fam B"}
        assoc = {
            "Fam A": ["Mario", "Luigi", "Carla"],
            "Fam B": ["Mario", "Luigi", "Anna"],
        }
        freq = {"Fam A": 2, "Fam B": 2}
        cap = {f: 3 for f in fr}
        vincoli = [{"fratello_a": "Mario", "fratello_b": "Luigi", "tipo": "incompatibile"}]
        sol = ottimizza_turni_mesi(
            mesi=["2026-01"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
        )
        assert sol is not None
        for famiglia in fam:
            slots = sol["by_month"]["2026-01"]["by_family"][famiglia]
            assert not ("Mario" in slots and "Luigi" in slots), \
                f"Vincolo incompatibile violato in {famiglia}: {slots}"


class TestVincoloPreferenzaCoppia:
    def test_coppia_preferita_stessa_famiglia(self):
        fr = {"Mario", "Luigi", "Carla", "Anna"}
        fam = {"Fam A"}
        assoc = {"Fam A": ["Mario", "Luigi", "Carla", "Anna"]}
        freq = {"Fam A": 2}
        cap = {f: 2 for f in fr}
        vincoli = [{"fratello_a": "Mario", "fratello_b": "Luigi", "tipo": "preferenza_coppia"}]
        sol = ottimizza_turni_mesi(
            mesi=["2026-01"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
        )
        assert sol is not None
        slots = sol["by_month"]["2026-01"]["by_family"]["Fam A"]
        assert "Mario" in slots and "Luigi" in slots, \
            f"Preferenza coppia non rispettata (soft): {slots}"

    def test_coppia_non_blocca_se_impossibile(self):
        fr = {"Mario", "Luigi"}
        fam = {"Fam A", "Fam B"}
        assoc = {"Fam A": ["Mario"], "Fam B": ["Luigi"]}
        freq = {"Fam A": 1, "Fam B": 1}
        cap = {"Mario": 1, "Luigi": 1}
        vincoli = [{"fratello_a": "Mario", "fratello_b": "Luigi", "tipo": "preferenza_coppia"}]
        sol = ottimizza_turni_mesi(
            mesi=["2026-01"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
        )
        assert sol is not None


class TestVincoloIndisponibilita:
    def test_indisponibile_non_assegnato(self):
        fr = {"Mario", "Luigi", "Carla"}
        fam = {"Fam A"}
        assoc = {"Fam A": ["Mario", "Luigi", "Carla"]}
        freq = {"Fam A": 2}
        cap = {f: 2 for f in fr}
        indisp = {"Mario": ["2026-01"]}
        sol = ottimizza_turni_mesi(
            mesi=["2026-01"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            indisponibilita=indisp,
        )
        assert sol is not None
        slots = sol["by_month"]["2026-01"]["by_family"]["Fam A"]
        assert "Mario" not in slots

    def test_indisponibilita_parziale(self):
        fr = {"Mario", "Luigi", "Carla", "Anna"}
        fam = {"Fam A"}
        assoc = {"Fam A": ["Mario", "Luigi", "Carla", "Anna"]}
        freq = {"Fam A": 2}
        cap = {f: 2 for f in fr}
        indisp = {"Mario": ["2026-01"]}
        sol = ottimizza_turni_mesi(
            mesi=["2026-01", "2026-02"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            indisponibilita=indisp,
        )
        assert sol is not None
        assert "Mario" not in sol["by_month"]["2026-01"]["by_family"]["Fam A"]


class TestVincoliCombinati:
    def test_incompatibile_piu_indisponibilita(self):
        fr = {"Mario", "Luigi", "Carla", "Anna", "Elena"}
        fam = {"Fam A"}
        assoc = {"Fam A": ["Mario", "Luigi", "Carla", "Anna", "Elena"]}
        freq = {"Fam A": 2}
        cap = {f: 2 for f in fr}
        vincoli = [{"fratello_a": "Mario", "fratello_b": "Luigi", "tipo": "incompatibile"}]
        indisp = {"Carla": ["2026-01"]}
        sol = ottimizza_turni_mesi(
            mesi=["2026-01"],
            fratelli=fr, famiglie=fam, associazioni=assoc,
            frequenze=freq, capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
            indisponibilita=indisp,
        )
        assert sol is not None
        slots = sol["by_month"]["2026-01"]["by_family"]["Fam A"]
        assert not ("Mario" in slots and "Luigi" in slots)
        assert "Carla" not in slots
