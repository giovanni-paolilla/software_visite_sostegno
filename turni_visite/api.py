"""
API REST opzionale basata su Flask.

Espone il service layer come endpoint REST per accesso da web/mobile.
Avviare con: python -m turni_visite.api

Richiede: pip install flask
"""
from __future__ import annotations

import logging

try:
    from flask import Flask, jsonify, request
except ImportError:
    Flask = None  # type: ignore

from .config import DATA_FILE
from .repository import JsonRepository
from .service import esegui_ottimizzazione, diagnosi_infeasible, quick_check
from .stats import report_carico_fratelli, calcola_indice_equita, trend_mensile
from .domain import TurniVisiteError


def create_app(data_file=None) -> "Flask":
    if Flask is None:
        raise RuntimeError(
            "Flask non installato. Installa con: pip install flask"
        )

    app = Flask(__name__)
    repo = JsonRepository(data_file or DATA_FILE)

    # ------------------------------------------------------------------
    # Dashboard / KPI
    # ------------------------------------------------------------------

    @app.route("/api/dashboard", methods=["GET"])
    def dashboard():
        return jsonify(repo.get_dashboard_kpi())

    # ------------------------------------------------------------------
    # Fratelli
    # ------------------------------------------------------------------

    @app.route("/api/fratelli", methods=["GET"])
    def list_fratelli():
        return jsonify([
            {"nome": fr, "capacita": repo.capacita.get(fr, 1),
             "indisponibilita": repo.indisponibilita.get(fr, [])}
            for fr in sorted(repo.fratelli)
        ])

    @app.route("/api/fratelli", methods=["POST"])
    def add_fratello():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        try:
            nome = repo.add_brother(data.get("nome", ""))
            if "capacita" in data:
                repo.set_brother_capacity(nome, int(data["capacita"]))
            return jsonify({"nome": nome}), 201
        except (TurniVisiteError, ValueError, TypeError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/fratelli/<nome>", methods=["DELETE"])
    def delete_fratello(nome):
        try:
            repo.remove_brother(nome)
            return jsonify({"ok": True})
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 404

    # ------------------------------------------------------------------
    # Famiglie
    # ------------------------------------------------------------------

    @app.route("/api/famiglie", methods=["GET"])
    def list_famiglie():
        return jsonify([
            {"nome": fam, "frequenza": repo.frequenze.get(fam, 2),
             "fratelli_associati": repo.associazioni.get(fam, [])}
            for fam in sorted(repo.famiglie)
        ])

    @app.route("/api/famiglie", methods=["POST"])
    def add_famiglia():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        try:
            nome = repo.add_family(data.get("nome", ""))
            if "frequenza" in data:
                repo.set_frequency(nome, int(data["frequenza"]))
            return jsonify({"nome": nome}), 201
        except (TurniVisiteError, ValueError, TypeError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/famiglie/<nome>", methods=["DELETE"])
    def delete_famiglia(nome):
        try:
            repo.remove_family(nome)
            return jsonify({"ok": True})
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 404

    # ------------------------------------------------------------------
    # Associazioni
    # ------------------------------------------------------------------

    @app.route("/api/associazioni", methods=["POST"])
    def associate():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        try:
            repo.associate(data.get("fratello", ""), data.get("famiglia", ""))
            return jsonify({"ok": True}), 201
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/associazioni", methods=["DELETE"])
    def disassociate():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        try:
            repo.disassociate(data.get("fratello", ""), data.get("famiglia", ""))
            return jsonify({"ok": True})
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Ottimizzazione
    # ------------------------------------------------------------------

    @app.route("/api/ottimizza", methods=["POST"])
    def ottimizza():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        mesi = data.get("mesi", [])
        try:
            cooldown = int(data.get("cooldown", repo.get_setting("cooldown_mesi", 3)))
        except (ValueError, TypeError):
            return jsonify({"errore": "Cooldown deve essere un numero intero."}), 400
        snap = repo.data_snapshot()
        try:
            result = esegui_ottimizzazione(
                snap=snap, mesi=mesi,
                storico_turni=repo.get_storico_turni(), cooldown=cooldown,
            )
            if result.feasible:
                return jsonify({"feasible": True, "solution": result.solution})
            else:
                diag = diagnosi_infeasible(
                    snap=snap, mesi=mesi,
                    storico_turni=repo.get_storico_turni(), cooldown=cooldown,
                )
                return jsonify({"feasible": False, "diagnosi": diag})
        except (RuntimeError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/pre-check", methods=["POST"])
    def pre_check():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        mesi = data.get("mesi", [])
        try:
            cooldown = int(data.get("cooldown", repo.get_setting("cooldown_mesi", 3)))
        except (ValueError, TypeError):
            return jsonify({"errore": "Cooldown deve essere un numero intero."}), 400
        snap = repo.data_snapshot()
        return jsonify(quick_check(snap, mesi, repo.get_storico_turni(), cooldown))

    # ------------------------------------------------------------------
    # Storico
    # ------------------------------------------------------------------

    @app.route("/api/storico", methods=["GET"])
    def get_storico():
        return jsonify(repo.get_storico_turni())

    @app.route("/api/storico/<mese>", methods=["DELETE"])
    def delete_storico(mese):
        try:
            repo.delete_storico_mese(mese)
            return jsonify({"ok": True})
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 404

    # ------------------------------------------------------------------
    # Statistiche
    # ------------------------------------------------------------------

    @app.route("/api/stats/carico", methods=["GET"])
    def stats_carico():
        return jsonify(report_carico_fratelli(repo.get_storico_turni()))

    @app.route("/api/stats/equita", methods=["GET"])
    def stats_equita():
        return jsonify(calcola_indice_equita(repo.get_storico_turni()))

    @app.route("/api/stats/trend", methods=["GET"])
    def stats_trend():
        return jsonify(trend_mensile(repo.get_storico_turni()))

    # ------------------------------------------------------------------
    # Indisponibilita'
    # ------------------------------------------------------------------

    @app.route("/api/indisponibilita/<fratello>", methods=["GET"])
    def get_indisp(fratello):
        try:
            return jsonify(repo.get_indisponibilita(fratello))
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 404

    @app.route("/api/indisponibilita", methods=["POST"])
    def add_indisp():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        try:
            repo.add_indisponibilita(data.get("fratello", ""), data.get("mese", ""))
            return jsonify({"ok": True}), 201
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Vincoli
    # ------------------------------------------------------------------

    @app.route("/api/vincoli", methods=["GET"])
    def get_vincoli():
        return jsonify(repo.get_vincoli())

    @app.route("/api/vincoli", methods=["POST"])
    def add_vincolo():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"errore": "Body JSON non valido."}), 400
        try:
            repo.add_vincolo(
                data.get("fratello_a", ""), data.get("fratello_b", ""),
                data.get("tipo", ""), data.get("descrizione", ""),
            )
            return jsonify({"ok": True}), 201
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    return app


def main() -> None:
    from .logging_cfg import setup_logging
    setup_logging()
    app = create_app()
    logging.info("API REST avviata su http://127.0.0.1:5000")
    print("API REST disponibile su http://127.0.0.1:5000")
    app.run(debug=False, port=5000)


if __name__ == "__main__":
    main()
