"""
Test di integrazione end-to-end: Service → Repository → Scheduling.

Coprono il ciclo completo dalla creazione degli anagrafici fino alla
persistenza e verifica dello storico, senza mock dei componenti interni.
"""
from __future__ import annotations

import pytest

try:
    from ortools.sat.python import cp_model as _cp  # noqa: F401
    _ORTOOLS_OK = True
except Exception:
    _ORTOOLS_OK = False

pytestmark = pytest.mark.skipif(
    not _ORTOOLS_OK, reason="ortools non disponibile"
)

from turni_visite.repository import JsonRepository
from turni_visite.domain import NON_ASSEGNATO, SolverResult
from turni_visite.service import (
    esegui_ottimizzazione,
    conferma_e_salva_turni,
    modifica_assegnazione,
)
from turni_visite.stats import report_carico_fratelli


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_repo(tmp_path, filename="dati.json"):
    """Crea un repository vuoto su filesystem temporaneo."""
    return JsonRepository(str(tmp_path / filename))


def _setup_anagrafica(repo: JsonRepository) -> tuple[list[str], list[str]]:
    """
    Aggiunge 3 fratelli e 2 famiglie con associazioni incrociate.

    Fratelli: Alpha, Beta, Gamma  (capacita 2 ciascuno)
    Famiglie: Famiglia Uno (freq 2), Famiglia Due (freq 2)
    Associazioni:
        Famiglia Uno <- Alpha, Beta, Gamma
        Famiglia Due <- Alpha, Beta, Gamma

    Restituisce (lista_fratelli, lista_famiglie) come nomi canonici.
    """
    fr_a = repo.add_brother("Alpha")
    fr_b = repo.add_brother("Beta")
    fr_c = repo.add_brother("Gamma")

    repo.set_brother_capacity("Alpha", 2)
    repo.set_brother_capacity("Beta", 2)
    repo.set_brother_capacity("Gamma", 2)

    fam_1 = repo.add_family("Famiglia Uno")
    fam_2 = repo.add_family("Famiglia Due")

    repo.set_frequency("Famiglia Uno", 2)
    repo.set_frequency("Famiglia Due", 2)

    for fr in ("Alpha", "Beta", "Gamma"):
        repo.associate(fr, "Famiglia Uno")
        repo.associate(fr, "Famiglia Due")

    return ([fr_a, fr_b, fr_c], [fam_1, fam_2])


# ---------------------------------------------------------------------------
# 1. Ciclo completo: ottimizzazione, salvataggio, persistenza
# ---------------------------------------------------------------------------

class TestCicloCompletoOttimizzazioneESalvataggio:
    """Verifica il flusso completo dal solver fino alla rilettura da file."""

    def test_risultato_feasible(self, tmp_path):
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2026-01", "2026-02"]
        result: SolverResult = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )

        assert result.feasible, "Il solver deve trovare una soluzione feasible"
        assert result.solution is not None
        assert "by_month" in result.solution
        for mese in mesi:
            assert mese in result.solution["by_month"]

    def test_conferma_salva_storico(self, tmp_path):
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2026-01", "2026-02"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        salvati = conferma_e_salva_turni(repo, mesi, result.solution)

        assert set(salvati) == set(mesi)
        for mese in mesi:
            assert repo.storico_has_mese(mese), f"Mese {mese} deve essere nello storico"

    def test_storico_contiene_assegnazioni_reali(self, tmp_path):
        """Ogni record storico deve avere almeno un'assegnazione con fratello reale."""
        repo = _build_repo(tmp_path)
        fratelli, _ = _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2026-01", "2026-02"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        conferma_e_salva_turni(repo, mesi, result.solution)
        storico = repo.get_storico_turni()

        assert len(storico) == 2
        for rec in storico:
            assegnazioni = rec["assegnazioni"]
            fratelli_assegnati = [a["fratello"] for a in assegnazioni]
            assert all(fr != NON_ASSEGNATO for fr in fratelli_assegnati), (
                "Nessuna assegnazione deve contenere NON_ASSEGNATO nello storico confermato"
            )
            assert any(fr in fratelli for fr in fratelli_assegnati), (
                "Almeno un fratello reale deve essere presente nel record"
            )

    def test_persistenza_su_file_reload(self, tmp_path):
        """Dopo reload dal file, lo storico deve essere identico a quello in memoria."""
        repo = _build_repo(tmp_path, "persists.json")
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2026-03", "2026-04"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible
        conferma_e_salva_turni(repo, mesi, result.solution)

        storico_prima = repo.get_storico_turni()

        # Crea una seconda istanza che rilegge da disco
        repo2 = JsonRepository(str(tmp_path / "persists.json"))
        storico_dopo = repo2.get_storico_turni()

        assert len(storico_prima) == len(storico_dopo)
        mesi_nel_file = {r["mese"] for r in storico_dopo}
        assert set(mesi) == mesi_nel_file

        for rec_prima, rec_dopo in zip(
            sorted(storico_prima, key=lambda r: r["mese"]),
            sorted(storico_dopo, key=lambda r: r["mese"]),
        ):
            assert rec_prima["mese"] == rec_dopo["mese"]
            assert len(rec_prima["assegnazioni"]) == len(rec_dopo["assegnazioni"])


# ---------------------------------------------------------------------------
# 2. Ottimizzazione con indisponibilita'
# ---------------------------------------------------------------------------

class TestOttimizzazioneConIndisponibilita:
    """Il solver rispetta le indisponibilita' dei fratelli."""

    def test_fratello_non_assegnato_nel_mese_indisponibile(self, tmp_path):
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        mese_indisp = "2026-05"
        repo.set_indisponibilita("Alpha", [mese_indisp])

        snap = repo.data_snapshot()
        mesi = [mese_indisp, "2026-06"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible, "Con 3 fratelli e capacita 2 deve essere feasible anche con 1 indisponibile"

        blocco_indisp = result.solution["by_month"][mese_indisp]
        for fam, slots in blocco_indisp["by_family"].items():
            for fratello_assegnato in slots:
                assert fratello_assegnato != "Alpha", (
                    f"Alpha non deve essere assegnato in {mese_indisp} (indisponibile)"
                )

    def test_fratello_disponibile_nel_mese_libero(self, tmp_path):
        """Nel mese senza indisponibilita' il fratello puo' comparire."""
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        repo.set_indisponibilita("Alpha", ["2026-07"])

        snap = repo.data_snapshot()
        mesi = ["2026-07", "2026-08"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,  # cooldown 0 per non limitare il mese libero
        )
        assert result.feasible

        # Nel mese libero (2026-08), Alpha puo' apparire (non e' garantito
        # dal solver, ma NON deve essere escluso per vincolo di indisponibilita')
        # Il test verifica almeno che la soluzione e' strutturalmente corretta.
        blocco_libero = result.solution["by_month"]["2026-08"]
        assert "by_family" in blocco_libero

    def test_indisponibilita_su_storico_dopo_conferma(self, tmp_path):
        """
        Dopo aver salvato lo storico, il mese con indisponibilita'
        deve avere assegnazioni prive di quel fratello.
        """
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        mese_indisp = "2026-09"
        repo.set_indisponibilita("Gamma", [mese_indisp])

        snap = repo.data_snapshot()
        mesi = [mese_indisp]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        conferma_e_salva_turni(repo, mesi, result.solution)
        storico = repo.get_storico_turni()

        rec = next(r for r in storico if r["mese"] == mese_indisp)
        fratelli_nel_mese = [a["fratello"] for a in rec["assegnazioni"]]
        assert "Gamma" not in fratelli_nel_mese, (
            "Gamma non deve comparire nello storico del mese in cui era indisponibile"
        )


# ---------------------------------------------------------------------------
# 3. Modifica manuale post-ottimizzazione
# ---------------------------------------------------------------------------

class TestModificaManualePostOttimizzazione:
    """Verifica che modifica_assegnazione applichi la modifica e il salvataggio la persista."""

    def test_modifica_applicata_alla_soluzione(self, tmp_path):
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mese = "2026-10"
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=[mese],
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        solution = result.solution
        blocco = solution["by_month"][mese]["by_family"]

        # Trova una famiglia e uno slot con un fratello assegnato
        famiglia_target = next(iter(blocco))
        slot_target = 0
        fratello_originale = blocco[famiglia_target][slot_target]

        # Trova un fratello diverso associato alla stessa famiglia
        associati = repo.associazioni.get(famiglia_target, [])
        nuovo_fratello = next(
            (fr for fr in associati if fr != fratello_originale),
            None,
        )
        if nuovo_fratello is None:
            pytest.skip("Non ci sono fratelli alternativi per la modifica manuale")

        solution_modificata = modifica_assegnazione(
            solution=solution,
            mese=mese,
            famiglia=famiglia_target,
            slot=slot_target,
            nuovo_fratello=nuovo_fratello,
        )

        slot_dopo = solution_modificata["by_month"][mese]["by_family"][famiglia_target][slot_target]
        assert slot_dopo == nuovo_fratello, "La modifica deve aggiornare lo slot nella soluzione"

    def test_modifica_persiste_nello_storico(self, tmp_path):
        """La modifica manuale viene salvata correttamente nello storico."""
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mese = "2026-11"
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=[mese],
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        solution = result.solution
        blocco = solution["by_month"][mese]["by_family"]
        famiglia_target = next(iter(blocco))
        slot_target = 0
        fratello_originale = blocco[famiglia_target][slot_target]
        associati = repo.associazioni.get(famiglia_target, [])
        nuovo_fratello = next(
            (fr for fr in associati if fr != fratello_originale),
            None,
        )
        if nuovo_fratello is None:
            pytest.skip("Non ci sono fratelli alternativi per la modifica manuale")

        solution_modificata = modifica_assegnazione(
            solution=solution,
            mese=mese,
            famiglia=famiglia_target,
            slot=slot_target,
            nuovo_fratello=nuovo_fratello,
        )

        conferma_e_salva_turni(repo, [mese], solution_modificata)

        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == mese)
        slot_nello_storico = next(
            (a["fratello"] for a in rec["assegnazioni"]
             if a["famiglia"] == famiglia_target and a["slot"] == slot_target),
            None,
        )
        assert slot_nello_storico == nuovo_fratello, (
            "Il fratello modificato manualmente deve comparire nello storico"
        )

    def test_soluzione_originale_non_alterata(self, tmp_path):
        """modifica_assegnazione non deve mutare la soluzione originale (deep copy)."""
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mese = "2026-12"
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=[mese],
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        solution = result.solution
        blocco = solution["by_month"][mese]["by_family"]
        famiglia_target = next(iter(blocco))
        slot_target = 0
        fratello_originale = blocco[famiglia_target][slot_target]
        associati = repo.associazioni.get(famiglia_target, [])
        nuovo_fratello = next(
            (fr for fr in associati if fr != fratello_originale),
            None,
        )
        if nuovo_fratello is None:
            pytest.skip("Non ci sono fratelli alternativi")

        modifica_assegnazione(
            solution=solution,
            mese=mese,
            famiglia=famiglia_target,
            slot=slot_target,
            nuovo_fratello=nuovo_fratello,
        )

        # La soluzione originale non deve essere cambiata
        assert solution["by_month"][mese]["by_family"][famiglia_target][slot_target] == fratello_originale


# ---------------------------------------------------------------------------
# 4. Statistiche dopo il salvataggio
# ---------------------------------------------------------------------------

class TestStatisticheDopSalvataggio:
    """report_carico_fratelli deve escludere NON_ASSEGNATO e essere coerente."""

    def test_non_assegnato_non_contato(self, tmp_path):
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2027-01", "2027-02"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        conferma_e_salva_turni(repo, mesi, result.solution)

        storico = repo.get_storico_turni()
        carico = report_carico_fratelli(storico)

        fratelli_nel_report = [r["fratello"] for r in carico]
        assert NON_ASSEGNATO not in fratelli_nel_report, (
            "NON_ASSEGNATO non deve comparire nel report di carico"
        )

    def test_visite_totali_coerenti_con_storico(self, tmp_path):
        """
        La somma delle visite_totali nel report deve coincidere col numero
        totale di assegnazioni reali nello storico.
        """
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2027-03", "2027-04"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        conferma_e_salva_turni(repo, mesi, result.solution)
        storico = repo.get_storico_turni()

        # Conta assegnazioni reali nello storico (escludendo NON_ASSEGNATO)
        assegnazioni_reali = sum(
            1
            for rec in storico
            for a in rec.get("assegnazioni", [])
            if isinstance(a, dict) and a.get("fratello") != NON_ASSEGNATO
        )

        carico = report_carico_fratelli(storico)
        totale_nel_report = sum(r["visite_totali"] for r in carico)

        assert totale_nel_report == assegnazioni_reali, (
            f"Il report deve contare esattamente le assegnazioni reali: "
            f"storico={assegnazioni_reali}, report={totale_nel_report}"
        )

    def test_ogni_fratello_attivo_ha_almeno_una_visita(self, tmp_path):
        """
        Con 2 mesi, frequenza 2 per 2 famiglie e 3 fratelli cap 2,
        il solver distribuisce il carico: tutti e 3 i fratelli devono
        comparire almeno una volta (4 slot/mese * 2 mesi = 8 assegnazioni, 3 fratelli).
        """
        repo = _build_repo(tmp_path)
        fratelli, _ = _setup_anagrafica(repo)

        snap = repo.data_snapshot()
        mesi = ["2027-05", "2027-06"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        conferma_e_salva_turni(repo, mesi, result.solution)
        storico = repo.get_storico_turni()
        carico = report_carico_fratelli(storico)

        fratelli_con_visite = {r["fratello"] for r in carico if r["visite_totali"] > 0}
        # Tutti i fratelli devono avere almeno 1 visita nell'arco dei 2 mesi
        for fr in fratelli:
            assert fr in fratelli_con_visite, (
                f"Il fratello '{fr}' non ha visite nel report: "
                "la distribuzione non e' equa"
            )

    def test_nessun_fratello_supera_capacita_mensile(self, tmp_path):
        """Le visite per mese di ogni fratello non devono superare la sua capacita'."""
        repo = _build_repo(tmp_path)
        _setup_anagrafica(repo)  # capacita 2 per tutti

        snap = repo.data_snapshot()
        mesi = ["2027-07", "2027-08"]
        result = esegui_ottimizzazione(
            snap=snap,
            mesi=mesi,
            storico_turni=repo.get_storico_turni(),
            cooldown=0,
        )
        assert result.feasible

        conferma_e_salva_turni(repo, mesi, result.solution)
        storico = repo.get_storico_turni()
        carico = report_carico_fratelli(storico)

        for record in carico:
            fr = record["fratello"]
            capacita = repo.capacita.get(fr, 1)
            for mese, n_visite in record["dettaglio_mensile"].items():
                assert n_visite <= capacita, (
                    f"Il fratello '{fr}' ha {n_visite} visite nel mese {mese}, "
                    f"ma la capacita' e' {capacita}"
                )
