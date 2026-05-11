"""
Test completi per le nuove funzionalita' della v0.3.0:
- WhatsApp export
- Affinita' fratello-famiglia
- Bozza turni (draft workflow)
- Stato esecuzione visite
- Sostituzione fratello
- Solver fairness multi-periodo
- Schema v3 persistenza
"""
from __future__ import annotations

import json
import pytest

from turni_visite.domain import (
    AffinitaFamiglia,
    ValidazioneError,
    EntitaNonTrovata,
    NON_ASSEGNATO,
    STATO_BOZZA_PROPOSTO,
    STATO_BOZZA_ACCETTATO,
    STATO_BOZZA_RIFIUTATO,
    STATO_ESECUZIONE_PIANIFICATO,
    STATO_ESECUZIONE_COMPLETATO,
    STATO_ESECUZIONE_ANNULLATO,
)
from turni_visite.repository import JsonRepository
from turni_visite.whatsapp_export import format_whatsapp_mesi
from turni_visite.stats import tasso_completamento, report_carico_fratelli
from turni_visite.service import trova_sostituto


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    """Repository di test con dati minimali."""
    f = tmp_path / "test_data.json"
    r = JsonRepository(f)
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_brother("Paolo Verdi")
    r.add_family("Famiglia Neri")
    r.add_family("Famiglia Gialli")
    r.associate("Mario Rossi", "Famiglia Neri")
    r.associate("Luigi Bianchi", "Famiglia Neri")
    r.associate("Paolo Verdi", "Famiglia Neri")
    r.associate("Mario Rossi", "Famiglia Gialli")
    r.associate("Luigi Bianchi", "Famiglia Gialli")
    r.associate("Paolo Verdi", "Famiglia Gialli")
    # capacita' 3 per tutti per non avere problemi con il solver
    r.set_brother_capacity("Mario Rossi", 3)
    r.set_brother_capacity("Luigi Bianchi", 3)
    r.set_brother_capacity("Paolo Verdi", 3)
    return r


@pytest.fixture
def solution_single():
    """Soluzione fittizia per un singolo mese."""
    return {
        "by_month": {
            "2026-05": {
                "by_family": {
                    "Famiglia Neri": ["Mario Rossi", "Luigi Bianchi"],
                    "Famiglia Gialli": ["Paolo Verdi", "Mario Rossi"],
                },
                "by_brother": {
                    "Mario Rossi": ["Famiglia Neri", "Famiglia Gialli"],
                    "Luigi Bianchi": ["Famiglia Neri"],
                    "Paolo Verdi": ["Famiglia Gialli"],
                },
            }
        }
    }


@pytest.fixture
def solution_multi():
    """Soluzione fittizia per due mesi."""
    return {
        "by_month": {
            "2026-05": {
                "by_family": {
                    "Famiglia Neri": ["Mario Rossi", "Luigi Bianchi"],
                },
                "by_brother": {
                    "Mario Rossi": ["Famiglia Neri"],
                    "Luigi Bianchi": ["Famiglia Neri"],
                },
            },
            "2026-06": {
                "by_family": {
                    "Famiglia Neri": ["Paolo Verdi", "Mario Rossi"],
                },
                "by_brother": {
                    "Paolo Verdi": ["Famiglia Neri"],
                    "Mario Rossi": ["Famiglia Neri"],
                },
            },
        }
    }


def _make_week_windows(*mesi):
    """Helper: crea week_windows fittizi per test WhatsApp."""
    ww = {}
    for m in mesi:
        ww[m] = {
            2: ["01-07", "15-21"],
            1: ["08-14"],
            4: ["01-07", "08-14", "15-21", "22-28"],
        }
    return ww


# ===================================================================
# 1. TestWhatsAppExport
# ===================================================================

class TestWhatsAppExport:
    """Test per format_whatsapp_mesi."""

    def test_single_month_format(self, solution_single):
        freq = {"Famiglia Neri": 2, "Famiglia Gialli": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], solution_single, freq, ww)
        assert "VISITE DI SOSTEGNO" in txt
        assert "Maggio 2026" in txt

    def test_multi_month_format(self, solution_multi):
        freq = {"Famiglia Neri": 2}
        ww = _make_week_windows("2026-05", "2026-06")
        txt = format_whatsapp_mesi(["2026-05", "2026-06"], solution_multi, freq, ww)
        assert "Maggio 2026" in txt
        assert "Giugno 2026" in txt

    def test_empty_solution(self):
        txt = format_whatsapp_mesi(["2026-05"], {"by_month": {}}, {}, {})
        assert txt == ""

    def test_non_assegnato_excluded(self):
        sol = {
            "by_month": {
                "2026-05": {
                    "by_family": {
                        "Famiglia Neri": [NON_ASSEGNATO, "Mario Rossi"],
                    },
                    "by_brother": {
                        "Mario Rossi": ["Famiglia Neri"],
                    },
                }
            }
        }
        freq = {"Famiglia Neri": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], sol, freq, ww)
        assert NON_ASSEGNATO not in txt

    def test_bold_markers_present(self, solution_single):
        freq = {"Famiglia Neri": 2, "Famiglia Gialli": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], solution_single, freq, ww)
        # WhatsApp bold: *text*
        assert "*VISITE DI SOSTEGNO" in txt
        assert "*Per Fratello:*" in txt
        assert "*Per Famiglia:*" in txt

    def test_week_windows_labels_included(self, solution_single):
        freq = {"Famiglia Neri": 2, "Famiglia Gialli": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], solution_single, freq, ww)
        # slot labels from week windows (01-07 or 15-21) should appear
        assert "01-07" in txt or "15-21" in txt

    def test_per_fratello_section(self, solution_single):
        freq = {"Famiglia Neri": 2, "Famiglia Gialli": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], solution_single, freq, ww)
        # fratelli should appear in the Per Fratello section
        assert "Mario Rossi" in txt
        assert "Luigi Bianchi" in txt
        assert "Paolo Verdi" in txt

    def test_per_famiglia_section(self, solution_single):
        freq = {"Famiglia Neri": 2, "Famiglia Gialli": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], solution_single, freq, ww)
        assert "Famiglia Neri" in txt
        assert "Famiglia Gialli" in txt

    def test_separator_between_months(self, solution_multi):
        freq = {"Famiglia Neri": 2}
        ww = _make_week_windows("2026-05", "2026-06")
        txt = format_whatsapp_mesi(["2026-05", "2026-06"], solution_multi, freq, ww)
        # separator is "—" * 25
        assert "—" * 25 in txt

    def test_bullet_points_present(self, solution_single):
        freq = {"Famiglia Neri": 2, "Famiglia Gialli": 2}
        ww = _make_week_windows("2026-05")
        txt = format_whatsapp_mesi(["2026-05"], solution_single, freq, ww)
        assert "•" in txt  # bullet point


# ===================================================================
# 2. TestAffinita
# ===================================================================

class TestAffinita:
    """Test per affinita' fratello-famiglia."""

    def test_add_affinita_creates_entry(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        aff = repo.get_affinita()
        assert len(aff) == 1
        assert aff[0]["famiglia"] == "Famiglia Neri"
        assert aff[0]["fratello"] == "Mario Rossi"
        assert aff[0]["peso"] == 5

    def test_add_affinita_updates_existing(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        repo.add_affinita("Famiglia Neri", "Mario Rossi", -3)
        aff = repo.get_affinita()
        assert len(aff) == 1
        assert aff[0]["peso"] == -3

    def test_remove_affinita_works(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        repo.remove_affinita("Famiglia Neri", "Mario Rossi")
        assert repo.get_affinita() == []

    def test_remove_affinita_not_found_raises(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.remove_affinita("Famiglia Neri", "Mario Rossi")

    def test_affinita_cleaned_on_remove_brother(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        repo.remove_brother("Mario Rossi")
        # affinita' should be cleaned
        aff = repo.get_affinita()
        assert not any(a["fratello"] == "Mario Rossi" for a in aff)

    def test_affinita_cleaned_on_remove_family(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 5)
        repo.remove_family("Famiglia Neri")
        aff = repo.get_affinita()
        assert not any(a["famiglia"] == "Famiglia Neri" for a in aff)

    def test_affinita_in_data_snapshot(self, repo):
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 7)
        snap = repo.data_snapshot()
        assert "affinita" in snap
        assert len(snap["affinita"]) == 1
        assert snap["affinita"][0]["peso"] == 7

    def test_affinita_famiglia_dataclass_validation(self):
        af = AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=5)
        assert af.peso == 5

    def test_peso_out_of_range_raises(self):
        with pytest.raises(ValidazioneError):
            AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=11)
        with pytest.raises(ValidazioneError):
            AffinitaFamiglia(famiglia="Neri", fratello="Mario", peso=-11)

    def test_affinita_persistence(self, repo, tmp_path):
        repo.add_affinita("Famiglia Neri", "Luigi Bianchi", -4)
        # Reload from file
        repo2 = JsonRepository(repo.filename)
        aff = repo2.get_affinita()
        assert len(aff) == 1
        assert aff[0]["fratello"] == "Luigi Bianchi"
        assert aff[0]["peso"] == -4


# ===================================================================
# 3. TestBozzaTurni
# ===================================================================

class TestBozzaTurni:
    """Test per il workflow bozza turni."""

    def _make_solution(self):
        return {
            "by_month": {
                "2026-05": {
                    "by_family": {
                        "Famiglia Neri": ["Mario Rossi", "Luigi Bianchi"],
                    },
                    "by_brother": {
                        "Mario Rossi": ["Famiglia Neri"],
                        "Luigi Bianchi": ["Famiglia Neri"],
                    },
                }
            }
        }

    def test_save_bozza_creates_draft(self, repo):
        sol = self._make_solution()
        repo.save_bozza(["2026-05"], sol)
        bozza = repo.get_bozza()
        assert bozza is not None
        assert bozza["mesi"] == ["2026-05"]
        assert len(bozza["assegnazioni"]) == 2

    def test_update_bozza_stato_changes_status(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "accettato")
        bozza = repo.get_bozza()
        a0 = next(a for a in bozza["assegnazioni"] if a["slot"] == 0)
        assert a0["stato"] == "accettato"

    def test_update_bozza_stato_invalid_raises(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        with pytest.raises(ValidazioneError):
            repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "invalido")

    def test_conferma_bozza_moves_accepted_to_storico(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "accettato")
        repo.update_bozza_stato("2026-05", "Famiglia Neri", 1, "accettato")
        result = repo.conferma_bozza()
        assert "2026-05" in result["salvati"]
        assert repo.storico_has_mese("2026-05")
        assert repo.get_bozza() is None

    def test_conferma_bozza_discards_rejected(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "rifiutato")
        repo.update_bozza_stato("2026-05", "Famiglia Neri", 1, "rifiutato")
        result = repo.conferma_bozza()
        # nessun mese accettato
        assert result == {"salvati": [], "saltati": []}
        assert not repo.storico_has_mese("2026-05")

    def test_conferma_bozza_with_nothing_accepted(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        # tutti in stato "proposto" (default), nessuno accettato
        result = repo.conferma_bozza()
        assert result == {"salvati": [], "saltati": []}

    def test_discard_bozza_clears_draft(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        repo.discard_bozza()
        assert repo.get_bozza() is None

    def test_get_bozza_returns_none_when_no_draft(self, repo):
        assert repo.get_bozza() is None

    def test_draft_persistence(self, repo):
        repo.save_bozza(["2026-05"], self._make_solution())
        repo2 = JsonRepository(repo.filename)
        bozza = repo2.get_bozza()
        assert bozza is not None
        assert bozza["mesi"] == ["2026-05"]

    def test_accept_then_confirm_flow(self, repo):
        """Flusso completo: salva bozza, accetta tutti, conferma."""
        repo.save_bozza(["2026-05"], self._make_solution())
        bozza = repo.get_bozza()
        for a in bozza["assegnazioni"]:
            repo.update_bozza_stato(a["mese"], a["famiglia"], a["slot"], "accettato")
        result = repo.conferma_bozza()
        assert "2026-05" in result["salvati"]
        # storico deve avere le assegnazioni
        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        assert len(rec["assegnazioni"]) == 2

    def test_no_draft_raises_on_update(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.update_bozza_stato("2026-05", "Famiglia Neri", 0, "accettato")

    def test_no_draft_raises_on_conferma(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.conferma_bozza()


# ===================================================================
# 4. TestStatoEsecuzione
# ===================================================================

class TestStatoEsecuzione:
    """Test per stato esecuzione visite nello storico."""

    def _add_storico(self, repo):
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
            {"famiglia": "Famiglia Gialli", "fratello": "Paolo Verdi", "slot": 0},
        ])

    def test_set_stato_completato(self, repo):
        self._add_storico(repo)
        repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 0, "completato")
        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        a = next(a for a in rec["assegnazioni"]
                 if a["famiglia"] == "Famiglia Neri" and a["slot"] == 0)
        assert a["stato_esecuzione"] == "completato"

    def test_set_stato_annullato(self, repo):
        self._add_storico(repo)
        repo.set_stato_esecuzione("2026-05", "Famiglia Gialli", 0, "annullato")
        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        a = next(a for a in rec["assegnazioni"]
                 if a["famiglia"] == "Famiglia Gialli" and a["slot"] == 0)
        assert a["stato_esecuzione"] == "annullato"

    def test_set_stato_invalid_raises(self, repo):
        self._add_storico(repo)
        with pytest.raises(ValidazioneError):
            repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 0, "invalido")

    def test_set_stato_not_found_raises(self, repo):
        self._add_storico(repo)
        with pytest.raises(EntitaNonTrovata):
            repo.set_stato_esecuzione("2026-05", "Famiglia Inesistente", 0, "completato")

    def test_backward_compat_default_pianificato(self, repo):
        self._add_storico(repo)
        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        for a in rec["assegnazioni"]:
            # stato_esecuzione non presente => default pianificato
            assert a.get("stato_esecuzione", "pianificato") == "pianificato"

    def test_tasso_completamento_mixed(self, repo):
        self._add_storico(repo)
        repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 0, "completato")
        repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 1, "annullato")
        # Famiglia Gialli slot 0 rimane pianificato
        result = tasso_completamento(repo.get_storico_turni())
        assert result["totale"] == 3
        assert result["completate"] == 1
        assert result["annullate"] == 1
        assert result["pianificate"] == 1
        assert result["tasso_pct"] == pytest.approx(33.3, abs=0.1)

    def test_tasso_completamento_empty(self):
        result = tasso_completamento([])
        assert result["totale"] == 0
        assert result["tasso_pct"] == 0.0

    def test_report_carico_solo_completati(self, repo):
        self._add_storico(repo)
        repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 0, "completato")
        repo.set_stato_esecuzione("2026-05", "Famiglia Neri", 1, "annullato")
        # solo_completati=True should only count completato assignments
        report = report_carico_fratelli(repo.get_storico_turni(), solo_completati=True)
        assert len(report) == 1
        assert report[0]["fratello"] == "Mario Rossi"
        assert report[0]["visite_totali"] == 1


# ===================================================================
# 5. TestSostituzione
# ===================================================================

class TestSostituzione:
    """Test per trova_sostituto e update_storico_assegnazione."""

    def _add_storico(self, repo):
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
        ])

    def test_trova_sostituto_returns_candidates(self, repo):
        self._add_storico(repo)
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        assert len(candidati) > 0
        nomi = [c["fratello"] for c in candidati]
        assert "Mario Rossi" not in nomi

    def test_trova_sostituto_no_candidates_all_busy(self, repo):
        # Tutti i fratelli gia' assegnati e capacita' = 1
        repo.set_brother_capacity("Mario Rossi", 1)
        repo.set_brother_capacity("Luigi Bianchi", 1)
        repo.set_brother_capacity("Paolo Verdi", 1)
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Luigi Bianchi", "slot": 1},
            {"famiglia": "Famiglia Gialli", "fratello": "Paolo Verdi", "slot": 0},
        ])
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        # Luigi e Paolo gia' a capacita', nessun candidato
        assert len(candidati) == 0

    def test_trova_sostituto_respects_indisponibilita(self, repo):
        self._add_storico(repo)
        repo.set_indisponibilita("Paolo Verdi", ["2026-05"])
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        nomi = [c["fratello"] for c in candidati]
        assert "Paolo Verdi" not in nomi

    def test_update_storico_assegnazione(self, repo):
        self._add_storico(repo)
        repo.update_storico_assegnazione(
            "2026-05", "Famiglia Neri", 0, "Mario Rossi", "Paolo Verdi"
        )
        storico = repo.get_storico_turni()
        rec = next(r for r in storico if r["mese"] == "2026-05")
        a0 = next(a for a in rec["assegnazioni"]
                  if a["famiglia"] == "Famiglia Neri" and a["slot"] == 0)
        assert a0["fratello"] == "Paolo Verdi"

    def test_update_storico_assegnazione_not_found_raises(self, repo):
        self._add_storico(repo)
        with pytest.raises(EntitaNonTrovata):
            repo.update_storico_assegnazione(
                "2026-05", "Famiglia Neri", 0, "Paolo Verdi", "Luigi Bianchi"
            )

    def test_trova_sostituto_empty_storico(self, repo):
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        assert candidati == []

    def test_candidates_sorted_by_load(self, repo):
        # Diamo a Paolo piu' carico storico ma fuori dalla finestra di cooldown
        # (default cooldown=3 mesi) per non escluderlo dai candidati.
        repo.append_storico_turni("2025-08", [
            {"famiglia": "Famiglia Neri", "fratello": "Paolo Verdi", "slot": 0},
            {"famiglia": "Famiglia Neri", "fratello": "Paolo Verdi", "slot": 1},
        ])
        repo.append_storico_turni("2026-05", [
            {"famiglia": "Famiglia Neri", "fratello": "Mario Rossi", "slot": 0},
        ])
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi")
        assert len(candidati) >= 2, f"Attesi almeno 2 candidati, trovati: {candidati}"
        # candidati dovrebbero essere ordinati per score (carico piu' basso primo)
        for i in range(len(candidati) - 1):
            assert candidati[i]["score"] >= candidati[i + 1]["score"]

    def test_trova_sostituto_filter_by_family(self, repo):
        self._add_storico(repo)
        candidati = trova_sostituto(
            repo, "2026-05", "Mario Rossi", famiglia="Famiglia Neri"
        )
        for c in candidati:
            assert c["famiglia"] == "Famiglia Neri"

    def test_trova_sostituto_exclue_incompatibili(self, repo):
        """Candidati incompatibili con i compagni già nello slot non devono comparire."""
        # Storico: Mario slot 0, Luigi slot 1
        self._add_storico(repo)
        # Paolo è incompatibile con Luigi
        repo.add_vincolo("Paolo Verdi", "Luigi Bianchi", "incompatibile", "test")
        candidati = trova_sostituto(repo, "2026-05", "Mario Rossi", famiglia="Famiglia Neri")
        # Paolo non dovrebbe comparire perché Luigi è già nello slot 1 della stessa famiglia
        nomi = [c["fratello"] for c in candidati]
        assert "Paolo Verdi" not in nomi


# ===================================================================
# 6. TestSolverFairness
# ===================================================================

try:
    from ortools.sat.python import cp_model  # type: ignore
    _HAS_ORTOOLS = True
except ImportError:
    _HAS_ORTOOLS = False

skip_no_ortools = pytest.mark.skipif(
    not _HAS_ORTOOLS, reason="ortools non installato"
)


class TestSolverFairness:
    """Test per la fairness multi-periodo e affinita' nel solver."""

    @skip_no_ortools
    def test_multi_month_distributes_load(self):
        from turni_visite.scheduling import ottimizza_turni_mesi

        fratelli = {"F1", "F2", "F3", "F4"}
        famiglie = {"Fam-A", "Fam-B"}
        assoc = {"Fam-A": ["F1", "F2", "F3", "F4"],
                 "Fam-B": ["F1", "F2", "F3", "F4"]}
        freq = {"Fam-A": 2, "Fam-B": 2}
        cap = {f: 3 for f in fratelli}

        sol = ottimizza_turni_mesi(
            mesi=["2026-05", "2026-06", "2026-07"],
            fratelli=fratelli,
            famiglie=famiglie,
            associazioni=assoc,
            frequenze=freq,
            capacita=cap,
            cooldown_mesi=1,
            solver_timeout=10.0,
        )
        assert sol is not None
        # Check load per fratello across all months
        loads = {f: 0 for f in fratelli}
        for mese_data in sol["by_month"].values():
            for fam, slots in mese_data["by_family"].items():
                for fr in slots:
                    if fr != NON_ASSEGNATO:
                        loads[fr] += 1
        # Total assignments = 3 months * 2 families * 2 slots = 12
        assert sum(loads.values()) == 12
        # With 4 brothers, ideal is 3 each; max-min spread should be <= 2
        assert max(loads.values()) - min(loads.values()) <= 2

    @skip_no_ortools
    def test_affinita_positive_preferred(self):
        from turni_visite.scheduling import ottimizza_turni_mesi

        fratelli = {"F1", "F2"}
        famiglie = {"Fam-A"}
        assoc = {"Fam-A": ["F1", "F2"]}
        freq = {"Fam-A": 1}
        cap = {"F1": 2, "F2": 2}
        # Forte affinita' positiva per F1 con Fam-A
        affinita = [{"famiglia": "Fam-A", "fratello": "F1", "peso": 10}]

        sol = ottimizza_turni_mesi(
            mesi=["2026-05"],
            fratelli=fratelli,
            famiglie=famiglie,
            associazioni=assoc,
            frequenze=freq,
            capacita=cap,
            cooldown_mesi=1,
            affinita=affinita,
            solver_timeout=10.0,
        )
        assert sol is not None
        assigned = sol["by_month"]["2026-05"]["by_family"]["Fam-A"][0]
        assert assigned == "F1"

    @skip_no_ortools
    def test_affinita_negative_avoided(self):
        from turni_visite.scheduling import ottimizza_turni_mesi

        fratelli = {"F1", "F2"}
        famiglie = {"Fam-A"}
        assoc = {"Fam-A": ["F1", "F2"]}
        freq = {"Fam-A": 1}
        cap = {"F1": 2, "F2": 2}
        # Forte affinita' negativa per F1 con Fam-A
        affinita = [{"famiglia": "Fam-A", "fratello": "F1", "peso": -10}]

        sol = ottimizza_turni_mesi(
            mesi=["2026-05"],
            fratelli=fratelli,
            famiglie=famiglie,
            associazioni=assoc,
            frequenze=freq,
            capacita=cap,
            cooldown_mesi=1,
            affinita=affinita,
            solver_timeout=10.0,
        )
        assert sol is not None
        assigned = sol["by_month"]["2026-05"]["by_family"]["Fam-A"][0]
        # F1 dovrebbe essere evitato, F2 scelto
        assert assigned == "F2"

    @skip_no_ortools
    def test_preferenza_coppia_pairs_brothers(self):
        from turni_visite.scheduling import ottimizza_turni_mesi

        fratelli = {"F1", "F2", "F3", "F4"}
        famiglie = {"Fam-A"}
        assoc = {"Fam-A": ["F1", "F2", "F3", "F4"]}
        freq = {"Fam-A": 2}
        cap = {f: 2 for f in fratelli}
        vincoli = [{"fratello_a": "F1", "fratello_b": "F2",
                     "tipo": "preferenza_coppia"}]

        sol = ottimizza_turni_mesi(
            mesi=["2026-05"],
            fratelli=fratelli,
            famiglie=famiglie,
            associazioni=assoc,
            frequenze=freq,
            capacita=cap,
            cooldown_mesi=1,
            vincoli_personalizzati=vincoli,
            solver_timeout=10.0,
        )
        assert sol is not None
        assigned = sol["by_month"]["2026-05"]["by_family"]["Fam-A"]
        # The solver should pair F1 and F2 together (bonus -10)
        assert set(assigned) == {"F1", "F2"}

    @skip_no_ortools
    def test_solver_returns_valid_solution(self):
        from turni_visite.scheduling import ottimizza_turni_mesi

        fratelli = {"F1", "F2", "F3"}
        famiglie = {"Fam-A", "Fam-B"}
        assoc = {"Fam-A": ["F1", "F2", "F3"], "Fam-B": ["F1", "F2", "F3"]}
        freq = {"Fam-A": 2, "Fam-B": 1}
        cap = {f: 3 for f in fratelli}

        sol = ottimizza_turni_mesi(
            mesi=["2026-05"],
            fratelli=fratelli,
            famiglie=famiglie,
            associazioni=assoc,
            frequenze=freq,
            capacita=cap,
            cooldown_mesi=1,
            solver_timeout=10.0,
        )
        assert sol is not None
        # Check correct number of slots
        for fam, slots in sol["by_month"]["2026-05"]["by_family"].items():
            assert len(slots) == freq[fam]
            # No duplicates in same family
            real = [s for s in slots if s != NON_ASSEGNATO]
            assert len(real) == len(set(real))


# ===================================================================
# 7. TestSchemaV3
# ===================================================================

class TestSchemaV3:
    """Test per schema versione 3 persistenza."""

    def test_save_writes_schema_version_3(self, tmp_path):
        f = tmp_path / "data.json"
        repo = JsonRepository(f)
        repo.save()
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["schema_version"] == 3

    def test_load_old_v2_defaults(self, tmp_path):
        """Un file v2 senza affinita/bozza_turni carica valori di default."""
        f = tmp_path / "data.json"
        data = {
            "schema_version": 2,
            "fratelli": ["Mario Rossi"],
            "famiglie": ["Famiglia Neri"],
            "associazioni": {"Famiglia Neri": ["Mario Rossi"]},
            "frequenze": {"Famiglia Neri": 2},
            "capacita": {"Mario Rossi": 1},
            "settings": {"cooldown_mesi": 3},
            "storico_turni": [],
            "indisponibilita": {},
            "vincoli_personalizzati": [],
            "week_templates": {},
            "audit_log": [],
        }
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        repo = JsonRepository(f)
        assert repo.get_affinita() == []
        assert repo.get_bozza() is None

    def test_new_fields_survive_save_load(self, tmp_path):
        f = tmp_path / "data.json"
        repo = JsonRepository(f)
        repo.add_brother("Mario Rossi")
        repo.add_family("Famiglia Neri")
        repo.associate("Mario Rossi", "Famiglia Neri")
        repo.add_affinita("Famiglia Neri", "Mario Rossi", 3)
        sol = {
            "by_month": {
                "2026-05": {
                    "by_family": {"Famiglia Neri": ["Mario Rossi", "Mario Rossi"]},
                    "by_brother": {"Mario Rossi": ["Famiglia Neri"]},
                }
            }
        }
        repo.save_bozza(["2026-05"], sol)
        # Reload
        repo2 = JsonRepository(f)
        assert len(repo2.get_affinita()) == 1
        assert repo2.get_affinita()[0]["peso"] == 3
        assert repo2.get_bozza() is not None
        assert repo2.get_bozza()["mesi"] == ["2026-05"]

    def test_schema_v3_has_affinita_and_bozza_keys(self, tmp_path):
        f = tmp_path / "data.json"
        repo = JsonRepository(f)
        repo.save()
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert "affinita" in data
        assert "bozza_turni" in data
        assert data["affinita"] == []
        assert data["bozza_turni"] is None
