"""Test per le nuove funzionalita' del repository v2 (indisponibilita', vincoli, audit, etc.)."""
import logging
import pytest
from turni_visite.repository import JsonRepository
from turni_visite.domain import (
    DuplicatoError, EntitaNonTrovata, ValidazioneError,
    STATO_BOZZA_ACCETTATO,
)


@pytest.fixture
def repo(tmp_path):
    r = JsonRepository(str(tmp_path / "test_v2.json"))
    r.add_brother("Mario Rossi")
    r.add_brother("Luigi Bianchi")
    r.add_family("Famiglia Verdi")
    r.associate("Mario Rossi", "Famiglia Verdi")
    r.associate("Luigi Bianchi", "Famiglia Verdi")
    return r


# ---------------------------------------------------------------------------
# Indisponibilita'
# ---------------------------------------------------------------------------

class TestIndisponibilita:
    def test_add_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        assert "2026-03" in repo.get_indisponibilita("Mario Rossi")

    def test_remove_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.remove_indisponibilita("Mario Rossi", "2026-03")
        assert "2026-03" not in repo.get_indisponibilita("Mario Rossi")

    def test_set_indisponibilita(self, repo):
        repo.set_indisponibilita("Mario Rossi", ["2026-01", "2026-02"])
        assert repo.get_indisponibilita("Mario Rossi") == ["2026-01", "2026-02"]

    def test_indisponibilita_fratello_inesistente(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.add_indisponibilita("Inesistente", "2026-03")

    def test_rimuovi_fratello_pulisce_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.remove_brother("Mario Rossi")
        assert "Mario Rossi" not in repo.indisponibilita

    def test_persistenza(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        r2 = JsonRepository(repo.filename)
        assert "2026-03" in r2.indisponibilita.get("Mario Rossi", [])


# ---------------------------------------------------------------------------
# Vincoli personalizzati
# ---------------------------------------------------------------------------

class TestVincoliPersonalizzati:
    def test_add_vincolo_incompatibile(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        vincoli = repo.get_vincoli("incompatibile")
        assert len(vincoli) == 1
        assert vincoli[0]["fratello_a"] == "Mario Rossi"

    def test_add_vincolo_coppia(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "preferenza_coppia")
        assert len(repo.get_vincoli("preferenza_coppia")) == 1

    def test_tipo_non_valido(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "tipo_invalido")

    def test_vincolo_con_se_stesso(self, repo):
        with pytest.raises(ValidazioneError):
            repo.add_vincolo("Mario Rossi", "Mario Rossi", "incompatibile")

    def test_vincolo_duplicato(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        with pytest.raises(DuplicatoError):
            repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")

    def test_remove_vincolo(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        repo.remove_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        assert len(repo.get_vincoli()) == 0

    def test_remove_vincolo_inesistente(self, repo):
        with pytest.raises(EntitaNonTrovata):
            repo.remove_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")

    def test_rimuovi_fratello_pulisce_vincoli(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        repo.remove_brother("Mario Rossi")
        assert len(repo.vincoli_personalizzati) == 0

    def test_persistenza(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile", "test")
        r2 = JsonRepository(repo.filename)
        assert len(r2.vincoli_personalizzati) == 1


# ---------------------------------------------------------------------------
# Week templates
# ---------------------------------------------------------------------------

class TestWeekTemplates:
    def test_set_e_get(self, repo):
        repo.set_week_template(2, ["01-07", "15-21"])
        assert repo.get_week_template(2) == ["01-07", "15-21"]

    def test_freq_non_valida(self, repo):
        with pytest.raises(ValidazioneError):
            repo.set_week_template(3, ["01-07"])

    def test_persistenza(self, repo):
        repo.set_week_template(1, ["08-14"])
        r2 = JsonRepository(repo.filename)
        assert r2.get_week_template(1) == ["08-14"]


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_audit_su_add_brother(self, repo):
        repo.add_brother("Nuovo Fratello")
        log = repo.get_audit_log(1)
        assert len(log) >= 1
        assert "aggiungi_fratello" in log[0]["azione"]

    def test_audit_limit(self, repo):
        for i in range(10):
            repo.add_brother(f"FratelloTest{chr(65 + i)}")
        log = repo.get_audit_log(5)
        assert len(log) == 5


# ---------------------------------------------------------------------------
# Disassociate
# ---------------------------------------------------------------------------

class TestDisassociate:
    def test_disassocia(self, repo):
        repo.disassociate("Mario Rossi", "Famiglia Verdi")
        assert "Mario Rossi" not in repo.associazioni.get("Famiglia Verdi", [])

    def test_disassocia_non_associato(self, repo):
        repo.add_brother("Carla Neri")
        with pytest.raises(EntitaNonTrovata):
            repo.disassociate("Carla Neri", "Famiglia Verdi")


# ---------------------------------------------------------------------------
# Dashboard KPI
# ---------------------------------------------------------------------------

class TestDashboardKPI:
    def test_kpi_base(self, repo):
        kpi = repo.get_dashboard_kpi()
        assert kpi["n_fratelli"] == 2
        assert kpi["n_famiglie"] == 1
        assert kpi["n_fratelli_attivi"] == 2
        assert kpi["capacita_totale"] == 2
        assert kpi["domanda_totale"] == 2

    def test_kpi_bilancio(self, repo):
        kpi = repo.get_dashboard_kpi()
        assert kpi["bilancio"] == 0  # cap=2, dom=2

    def test_kpi_fratelli_senza_assoc(self, repo):
        repo.add_brother("Isolato")
        kpi = repo.get_dashboard_kpi()
        assert "Isolato" in kpi["fratelli_senza_associazione"]


# ---------------------------------------------------------------------------
# Data snapshot include nuovi campi
# ---------------------------------------------------------------------------

class TestDataSnapshot:
    def test_include_indisponibilita(self, repo):
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        snap = repo.data_snapshot()
        assert "2026-03" in snap["indisponibilita"]["Mario Rossi"]

    def test_include_vincoli(self, repo):
        repo.add_vincolo("Mario Rossi", "Luigi Bianchi", "incompatibile")
        snap = repo.data_snapshot()
        assert len(snap["vincoli_personalizzati"]) == 1


# ---------------------------------------------------------------------------
# Conferma bozza con fratello rimosso (Fix 29)
# ---------------------------------------------------------------------------

class TestConfermaBozzaFratelloRimosso:
    def _bozza_solution(self, mese: str) -> dict:
        return {
            "by_month": {
                mese: {
                    "by_family": {
                        "Famiglia Verdi": ["Mario Rossi", "Luigi Bianchi"],
                    },
                    "by_brother": {
                        "Mario Rossi": ["Famiglia Verdi"],
                        "Luigi Bianchi": ["Famiglia Verdi"],
                    },
                }
            }
        }

    def test_conferma_bozza_fratello_rimosso_logga_warning(self, repo, caplog):
        """Se un fratello viene rimosso dopo la creazione della bozza,
        la conferma deve loggare un warning e ignorare l'assegnazione."""
        mese = "2026-05"
        # Salva la bozza con entrambi i fratelli
        repo.save_bozza([mese], self._bozza_solution(mese))
        # Accetta entrambe le assegnazioni
        for a in repo.bozza_turni["assegnazioni"]:
            a["stato"] = STATO_BOZZA_ACCETTATO

        # Rimuove Mario Rossi prima della conferma
        repo.remove_brother("Mario Rossi")

        with caplog.at_level(logging.WARNING):
            result = repo.conferma_bozza()

        # La bozza deve essere stata consumata
        assert repo.bozza_turni is None
        # Deve essere presente almeno un warning per Mario Rossi
        assert any("Mario Rossi" in msg for msg in caplog.messages)

    def test_conferma_bozza_fratello_rimosso_salva_altri(self, repo):
        """Le assegnazioni valide (fratello ancora presente) devono essere salvate."""
        mese = "2026-06"
        repo.save_bozza([mese], self._bozza_solution(mese))
        # Accetta entrambe le assegnazioni
        for a in repo.bozza_turni["assegnazioni"]:
            a["stato"] = STATO_BOZZA_ACCETTATO

        # Rimuove Mario Rossi
        repo.remove_brother("Mario Rossi")
        result = repo.conferma_bozza()

        # Il mese deve essere nei salvati (ha ancora Luigi Bianchi)
        assert mese in result["salvati"]
        storico = repo.get_storico_turni()
        ass_mese = next(r for r in storico if r["mese"] == mese)
        fratelli_salvati = [a["fratello"] for a in ass_mese["assegnazioni"]]
        assert "Luigi Bianchi" in fratelli_salvati
        assert "Mario Rossi" not in fratelli_salvati

    def test_conferma_bozza_normale_senza_rimozioni(self, repo):
        """Senza rimozioni la bozza deve salvare tutte le assegnazioni accettate."""
        mese = "2026-07"
        repo.save_bozza([mese], self._bozza_solution(mese))
        for a in repo.bozza_turni["assegnazioni"]:
            a["stato"] = STATO_BOZZA_ACCETTATO

        result = repo.conferma_bozza()
        assert mese in result["salvati"]
        storico = repo.get_storico_turni()
        ass_mese = next(r for r in storico if r["mese"] == mese)
        assert len(ass_mese["assegnazioni"]) == 2


# ---------------------------------------------------------------------------
# extend_storico_turni (Fix 30)
# ---------------------------------------------------------------------------

class TestExtendStoricoTurni:
    """Usa il fixture repo che ha gia' Mario Rossi, Luigi Bianchi e Famiglia Verdi."""

    def _ass(self, famiglia: str = "Famiglia Verdi", fratello: str = "Mario Rossi") -> list[dict]:
        return [{"famiglia": famiglia, "fratello": fratello, "slot": 0}]

    def test_batch_vuoto_ritorna_lista_vuota(self, repo):
        result = repo.extend_storico_turni([])
        assert result == []

    def test_batch_record_validi(self, repo):
        records = [
            ("2026-01", self._ass()),
            ("2026-02", self._ass()),
        ]
        result = repo.extend_storico_turni(records)
        assert result == ["2026-01", "2026-02"]
        assert repo.storico_has_mese("2026-01")
        assert repo.storico_has_mese("2026-02")

    def test_batch_salva_con_unico_save(self, repo, monkeypatch):
        """Tutti i record vengono salvati con un singolo save()."""
        save_count = 0

        original_save = repo.save
        def counting_save():
            nonlocal save_count
            save_count += 1
            original_save()
        monkeypatch.setattr(repo, "save", counting_save)

        repo.extend_storico_turni([
            ("2026-03", self._ass()),
            ("2026-04", self._ass()),
        ])
        assert save_count == 1

    def test_batch_con_mese_duplicato_atomicita(self, repo):
        """Se un mese del batch e' gia' in storico, nessun record viene inserito."""
        from turni_visite.domain import StoricoConflittoError
        repo.append_storico_turni("2026-01", self._ass())

        with pytest.raises(StoricoConflittoError):
            repo.extend_storico_turni([
                ("2026-02", self._ass()),
                ("2026-01", self._ass()),  # gia' presente
            ])

        # 2026-02 non deve essere stato inserito (atomicita')
        assert not repo.storico_has_mese("2026-02")

    def test_batch_con_mese_duplicato_interno(self, repo):
        """Se lo stesso mese compare due volte nel batch, viene bloccato."""
        from turni_visite.domain import StoricoConflittoError

        with pytest.raises(StoricoConflittoError):
            repo.extend_storico_turni([
                ("2026-05", self._ass()),
                ("2026-05", self._ass()),
            ])

        assert not repo.storico_has_mese("2026-05")


# ---------------------------------------------------------------------------
# add_indisponibilita idempotenza (Fix 31)
# ---------------------------------------------------------------------------

class TestAddIndisponibilitaIdempotenza:
    def test_doppia_chiamata_non_duplica_mese(self, repo):
        """Chiamare add_indisponibilita due volte con lo stesso mese
        non deve creare duplicati nella lista."""
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        indisp = repo.get_indisponibilita("Mario Rossi")
        assert indisp.count("2026-03") == 1

    def test_mesi_diversi_non_interferiscono(self, repo):
        """Aggiungere mesi diversi funziona correttamente."""
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.add_indisponibilita("Mario Rossi", "2026-04")
        repo.add_indisponibilita("Mario Rossi", "2026-03")  # duplicato
        indisp = repo.get_indisponibilita("Mario Rossi")
        assert sorted(indisp) == ["2026-03", "2026-04"]

    def test_idempotenza_persistita(self, repo):
        """L'idempotenza deve valere anche dopo il reload dal disco."""
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        repo.add_indisponibilita("Mario Rossi", "2026-03")
        r2 = JsonRepository(repo.filename)
        indisp = r2.indisponibilita.get("Mario Rossi", [])
        assert indisp.count("2026-03") == 1
