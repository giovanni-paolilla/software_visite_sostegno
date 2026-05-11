"""
API REST opzionale basata su Flask.

Espone il service layer come endpoint REST per accesso da web/mobile.
Avviare con: python -m turni_visite.api

Richiede: pip install flask

Sicurezza:
- Bind su 127.0.0.1 (solo localhost).
- Autenticazione opzionale: imposta la variabile d'ambiente TURNI_API_KEY
  per abilitare il controllo dell'header X-API-Key su tutte le richieste.
"""
from __future__ import annotations

import hmac
import logging
import os
import sys
import threading
import time
from collections import defaultdict

try:
    from flask import Flask, jsonify, request
except ImportError:
    Flask = None  # type: ignore

from .config import DATA_FILE, API_SOLVER_TIMEOUT
from .repository import JsonRepository
from .scheduling import validate_month_yyyy_mm
from .service import esegui_ottimizzazione, diagnosi_infeasible, quick_check, trova_sostituto
from .stats import report_carico_fratelli, calcola_indice_equita, trend_mensile, tasso_completamento
from .whatsapp_export import format_whatsapp_mesi
from .domain import TurniVisiteError, EntitaNonTrovata, DuplicatoError

_API_KEY = os.environ.get("TURNI_API_KEY", "").strip()
_NO_AUTH = os.environ.get("TURNI_API_NO_AUTH", "") == "1"

logger = logging.getLogger(__name__)

MAX_INPUT_LEN = 200
MAX_STRING_LEN = 200
MAX_NAME_LEN = 100

_DEFAULT_CORS = ["http://localhost:5000", "http://localhost:3000", "http://localhost:8080",
                 "http://127.0.0.1:5000", "http://127.0.0.1:3000", "http://127.0.0.1:8080"]
_CORS_ORIGINS = [o.strip() for o in os.environ.get("TURNI_CORS_ORIGINS", "").split(",") if o.strip()] or _DEFAULT_CORS
_ALLOWED_ORIGINS = set(_CORS_ORIGINS)


class _RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self._max = max_calls
        self._period = period
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            calls = self._calls[key]
            calls[:] = [t for t in calls if now - t < self._period]
            if len(calls) >= self._max:
                return False
            calls.append(now)
            return True


_limiter_ottimizza = _RateLimiter(max_calls=5, period=60.0)
_limiter_general = _RateLimiter(max_calls=60, period=60.0)


def _validate_json_body(*required_fields: str) -> tuple[dict | None, tuple | None]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"errore": "Body JSON non valido."}), 400)
    missing = [
        f for f in required_fields
        if f not in data or data.get(f) is None or data.get(f) == ""
    ]
    if missing:
        return None, (jsonify({"errore": f"Campi obbligatori mancanti: {', '.join(missing)}"}), 400)
    _NON_STRING_FIELDS = {"mesi", "peso", "slot", "capacita", "frequenza", "cooldown", "solution"}
    for f in required_fields:
        val = data.get(f)
        if val is not None and not isinstance(val, str) and f not in _NON_STRING_FIELDS:
            return None, (jsonify({"errore": f"Il campo '{f}' deve essere una stringa."}), 400)
        if isinstance(val, str):
            limit = MAX_NAME_LEN if f == "nome" else MAX_STRING_LEN
            if len(val) > limit:
                return None, (jsonify({"errore": f"Campo '{f}' troppo lungo (max {limit} caratteri)"}), 400)
    return data, None


def _validate_mesi(mesi_raw: list) -> tuple[list[str] | None, tuple | None]:
    if not isinstance(mesi_raw, list) or not mesi_raw:
        return None, (jsonify({"errore": "Il campo 'mesi' deve essere una lista non vuota di stringhe YYYY-MM."}), 400)
    if len(mesi_raw) > 24:
        return None, (jsonify({"errore": "La lista mesi non può contenere più di 24 elementi."}), 400)
    validated: list[str] = []
    for m in mesi_raw:
        try:
            validated.append(validate_month_yyyy_mm(m))
        except (ValueError, TypeError):
            return None, (jsonify({"errore": f"Formato mese non valido: {m!r}. Usa YYYY-MM."}), 400)
    return validated, None


def _check_url_param_len(param: str, name: str = "parametro") -> tuple | None:
    """Ritorna una risposta di errore 400 se il parametro URL supera MAX_INPUT_LEN, altrimenti None."""
    if len(param) > MAX_INPUT_LEN:
        return jsonify({"errore": f"{name} troppo lungo"}), 400
    return None


def create_app(data_file=None) -> "Flask":
    if Flask is None:
        raise RuntimeError(
            "Flask non installato. Installa con: pip install flask"
        )

    if not _API_KEY and not _NO_AUTH:
        logger.error(
            "TURNI_API_KEY non impostata. "
            "Imposta la variabile d'ambiente o usa TURNI_API_NO_AUTH=1 "
            "per disabilitare l'autenticazione."
        )
        sys.exit(1)
    if _NO_AUTH and not _API_KEY:
        logger.warning("Autenticazione disabilitata (TURNI_API_NO_AUTH=1)")

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB
    repo = JsonRepository(data_file or DATA_FILE)

    @app.before_request
    def _auth():
        if request.method == "OPTIONS":
            return
        if not _NO_AUTH and not hmac.compare_digest(request.headers.get("X-API-Key", ""), _API_KEY):
            return jsonify({"errore": "Autenticazione richiesta (header X-API-Key mancante o errato)."}), 401
        # Fix CSRF/Content-Type: le richieste mutanti con body devono dichiarare application/json
        if request.method in ("POST", "PUT", "PATCH") and request.content_length:
            ct = request.content_type or ""
            if "application/json" not in ct:
                return jsonify({"errore": "Content-Type deve essere application/json"}), 415
        # Fix proxy IP: usa X-Forwarded-For se disponibile per identificare il client reale
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        if request.path == "/api/ottimizza" and not _limiter_ottimizza.allow(client_ip):
            return jsonify({"errore": "Troppe richieste, riprova tra poco"}), 429
        if not _limiter_general.allow(client_ip):
            return jsonify({"errore": "Troppe richieste"}), 429

    @app.after_request
    def _cors(response):
        origin = request.headers.get("Origin", "")
        if origin in _ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        response.headers["Permissions-Policy"] = "()"
        return response

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
        data, err = _validate_json_body("nome")
        if err:
            return err
        nome = data.get("nome", "")
        if len(nome) > MAX_INPUT_LEN:
            return jsonify({"errore": f"Nome troppo lungo (max {MAX_INPUT_LEN} caratteri)"}), 400
        cap = None
        if "capacita" in data:
            if isinstance(data["capacita"], bool):
                return jsonify({"errore": "Il campo 'capacita' deve essere un intero, non un booleano."}), 400
            try:
                cap = int(data["capacita"])
            except (ValueError, TypeError):
                return jsonify({"errore": "Il campo 'capacita' deve essere un intero."}), 400
            if not (0 <= cap <= 50):
                return jsonify({"errore": "Capacita' deve essere un intero 0..50."}), 400
        try:
            nome = repo.add_brother(data["nome"])
            if cap is not None:
                repo.set_brother_capacity(nome, cap)
            return jsonify({"nome": nome}), 201
        except DuplicatoError as e:
            return jsonify({"errore": str(e)}), 409
        except (TurniVisiteError, ValueError, TypeError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/fratelli/<nome>", methods=["DELETE"])
    def delete_fratello(nome):
        err = _check_url_param_len(nome, "nome")
        if err:
            return err
        try:
            repo.remove_brother(nome)
            return jsonify({"ok": True})
        except EntitaNonTrovata as e:
            return jsonify({"errore": str(e)}), 404
        except TurniVisiteError as e:
            app.logger.error("Errore operazione: %s", e)
            return jsonify({"errore": str(e)}), 400

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
        data, err = _validate_json_body("nome")
        if err:
            return err
        nome = data.get("nome", "")
        if len(nome) > MAX_INPUT_LEN:
            return jsonify({"errore": f"Nome troppo lungo (max {MAX_INPUT_LEN} caratteri)"}), 400
        freq = None
        if "frequenza" in data:
            if isinstance(data["frequenza"], bool):
                return jsonify({"errore": "Il campo 'frequenza' deve essere un intero, non un booleano."}), 400
            try:
                freq = int(data["frequenza"])
            except (ValueError, TypeError):
                return jsonify({"errore": "Il campo 'frequenza' deve essere un intero."}), 400
            if freq not in (1, 2, 4):
                return jsonify({"errore": "Frequenza deve essere 1, 2 o 4."}), 400
        try:
            nome = repo.add_family(data["nome"])
            if freq is not None:
                repo.set_frequency(nome, freq)
            return jsonify({"nome": nome}), 201
        except DuplicatoError as e:
            return jsonify({"errore": str(e)}), 409
        except (TurniVisiteError, ValueError, TypeError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/famiglie/<nome>", methods=["DELETE"])
    def delete_famiglia(nome):
        err = _check_url_param_len(nome, "nome")
        if err:
            return err
        try:
            repo.remove_family(nome)
            return jsonify({"ok": True})
        except EntitaNonTrovata as e:
            return jsonify({"errore": str(e)}), 404
        except TurniVisiteError as e:
            app.logger.error("Errore operazione: %s", e)
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Associazioni
    # ------------------------------------------------------------------

    @app.route("/api/associazioni", methods=["POST"])
    def associate():
        data, err = _validate_json_body("fratello", "famiglia")
        if err:
            return err
        try:
            repo.associate(data["fratello"], data["famiglia"])
            return jsonify({"ok": True}), 201
        except DuplicatoError as e:
            return jsonify({"errore": str(e)}), 409
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/associazioni", methods=["DELETE"])
    def disassociate():
        data, err = _validate_json_body("fratello", "famiglia")
        if err:
            return err
        try:
            repo.disassociate(data["fratello"], data["famiglia"])
            return jsonify({"ok": True})
        except EntitaNonTrovata as e:
            return jsonify({"errore": str(e)}), 404
        except TurniVisiteError as e:
            app.logger.error("Errore operazione: %s", e)
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Ottimizzazione
    # ------------------------------------------------------------------

    @app.route("/api/ottimizza", methods=["POST"])
    def ottimizza():
        data, err = _validate_json_body("mesi")
        if err:
            return err
        mesi, err = _validate_mesi(data["mesi"])
        if err:
            return err
        try:
            cooldown = int(data.get("cooldown", repo.get_setting("cooldown_mesi", 3)))
            if cooldown < 1:
                return jsonify({"errore": "Cooldown deve essere >= 1."}), 400
            if cooldown > 24:
                return jsonify({"errore": "Il cooldown non può superare 24 mesi."}), 400
        except (ValueError, TypeError):
            return jsonify({"errore": "Cooldown deve essere un numero intero."}), 400
        snap = repo.data_snapshot()
        try:
            result = esegui_ottimizzazione(
                snap=snap, mesi=mesi,
                storico_turni=repo.get_storico_turni(), cooldown=cooldown,
                solver_timeout=API_SOLVER_TIMEOUT,
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
        data, err = _validate_json_body("mesi")
        if err:
            return err
        mesi, err = _validate_mesi(data["mesi"])
        if err:
            return err
        try:
            cooldown = int(data.get("cooldown", repo.get_setting("cooldown_mesi", 3)))
            if cooldown < 1:
                return jsonify({"errore": "Cooldown deve essere >= 1."}), 400
            if cooldown > 24:
                return jsonify({"errore": "Il cooldown non può superare 24 mesi."}), 400
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
        err = _check_url_param_len(mese, "mese")
        if err:
            return err
        try:
            validate_month_yyyy_mm(mese)
        except ValueError as e:
            return jsonify({"errore": str(e)}), 400
        try:
            repo.delete_storico_mese(mese)
            return jsonify({"ok": True})
        except EntitaNonTrovata as e:
            return jsonify({"errore": str(e)}), 404
        except TurniVisiteError as e:
            app.logger.error("Errore operazione: %s", e)
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Statistiche
    # ------------------------------------------------------------------

    @app.route("/api/stats/carico", methods=["GET"])
    def stats_carico():
        try:
            result = report_carico_fratelli(repo.get_storico_turni())
            return jsonify(result)
        except (KeyError, TypeError, AttributeError) as e:
            app.logger.error("Errore stats: %s", e)
            return jsonify({"errore": "Errore nel calcolo delle statistiche."}), 500

    @app.route("/api/stats/equita", methods=["GET"])
    def stats_equita():
        try:
            result = calcola_indice_equita(repo.get_storico_turni())
            return jsonify(result)
        except (KeyError, TypeError, AttributeError) as e:
            app.logger.error("Errore stats: %s", e)
            return jsonify({"errore": "Errore nel calcolo delle statistiche."}), 500

    @app.route("/api/stats/trend", methods=["GET"])
    def stats_trend():
        try:
            result = trend_mensile(repo.get_storico_turni())
            return jsonify(result)
        except (KeyError, TypeError, AttributeError) as e:
            app.logger.error("Errore stats: %s", e)
            return jsonify({"errore": "Errore nel calcolo delle statistiche."}), 500

    # ------------------------------------------------------------------
    # Indisponibilita'
    # ------------------------------------------------------------------

    @app.route("/api/indisponibilita/<fratello>", methods=["GET"])
    def get_indisp(fratello):
        err = _check_url_param_len(fratello, "fratello")
        if err:
            return err
        try:
            return jsonify(repo.get_indisponibilita(fratello))
        except EntitaNonTrovata as e:
            return jsonify({"errore": str(e)}), 404
        except TurniVisiteError as e:
            app.logger.error("Errore operazione: %s", e)
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/indisponibilita", methods=["POST"])
    def add_indisp():
        data, err = _validate_json_body("fratello", "mese")
        if err:
            return err
        try:
            mese = validate_month_yyyy_mm(data["mese"])
            repo.add_indisponibilita(data["fratello"], mese)
            return jsonify({"ok": True}), 201
        except (ValueError, TurniVisiteError) as e:
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Vincoli
    # ------------------------------------------------------------------

    @app.route("/api/vincoli", methods=["GET"])
    def get_vincoli():
        return jsonify(repo.get_vincoli())

    @app.route("/api/vincoli", methods=["POST"])
    def add_vincolo():
        data, err = _validate_json_body("fratello_a", "fratello_b", "tipo")
        if err:
            return err
        tipo = data["tipo"]
        if tipo not in ("incompatibile", "preferenza_coppia"):
            return jsonify({"errore": "Tipo deve essere 'incompatibile' o 'preferenza_coppia'."}), 400
        try:
            repo.add_vincolo(
                data["fratello_a"], data["fratello_b"],
                tipo, data.get("descrizione", ""),
            )
            return jsonify({"ok": True}), 201
        except DuplicatoError as e:
            return jsonify({"errore": str(e)}), 409
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Affinita'
    # ------------------------------------------------------------------

    @app.route("/api/affinita", methods=["GET"])
    def get_affinita():
        return jsonify(repo.get_affinita())

    @app.route("/api/affinita", methods=["POST"])
    def add_affinita():
        data, err = _validate_json_body("famiglia", "fratello", "peso")
        if err:
            return err
        try:
            if isinstance(data["peso"], bool):
                return jsonify({"errore": "Il campo 'peso' deve essere un intero, non un booleano."}), 400
            peso = int(data["peso"])
            repo.add_affinita(data["famiglia"], data["fratello"], peso)
            return jsonify({"ok": True}), 201
        except DuplicatoError as e:
            return jsonify({"errore": str(e)}), 409
        except (TurniVisiteError, ValueError, TypeError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/affinita", methods=["DELETE"])
    def remove_affinita():
        data, err = _validate_json_body("famiglia", "fratello")
        if err:
            return err
        try:
            repo.remove_affinita(data["famiglia"], data["fratello"])
            return jsonify({"ok": True})
        except EntitaNonTrovata as e:
            return jsonify({"errore": str(e)}), 404
        except TurniVisiteError as e:
            app.logger.error("Errore operazione: %s", e)
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Bozza turni
    # ------------------------------------------------------------------

    @app.route("/api/bozza", methods=["GET"])
    def get_bozza():
        bozza = repo.get_bozza()
        if bozza is None:
            return jsonify({"errore": "Nessuna bozza attiva."}), 404
        return jsonify(bozza)

    @app.route("/api/bozza", methods=["DELETE"])
    def discard_bozza():
        repo.discard_bozza()
        return jsonify({"ok": True})

    @app.route("/api/bozza/stato", methods=["PATCH"])
    def update_bozza_stato():
        data, err = _validate_json_body("mese", "famiglia", "slot", "stato")
        if err:
            return err
        if isinstance(data.get("slot"), bool):
            return jsonify({"errore": "Il campo 'slot' deve essere un intero, non un booleano."}), 400
        try:
            repo.update_bozza_stato(data["mese"], data["famiglia"], int(data["slot"]), data["stato"])
            return jsonify({"ok": True})
        except (TurniVisiteError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/bozza/conferma", methods=["POST"])
    def conferma_bozza():
        try:
            result = repo.conferma_bozza()
            return jsonify(result)
        except TurniVisiteError as e:
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Sostituzione d'emergenza
    # ------------------------------------------------------------------

    @app.route("/api/sostituzione", methods=["POST"])
    def sostituzione():
        data, err = _validate_json_body("mese", "fratello_malato")
        if err:
            return err
        try:
            mese = validate_month_yyyy_mm(data["mese"])
        except (ValueError, TypeError):
            return jsonify({"errore": "Formato mese non valido. Usa YYYY-MM."}), 400
        if data["fratello_malato"] not in repo.fratelli:
            return jsonify({"errore": f"Fratello '{data['fratello_malato']}' non trovato."}), 404
        if "famiglia" in data and not isinstance(data["famiglia"], str):
            return jsonify({"errore": "Il campo 'famiglia' deve essere una stringa."}), 400
        candidati = trova_sostituto(repo, mese, data["fratello_malato"],
                                     data.get("famiglia"))
        return jsonify(candidati)

    @app.route("/api/sostituzione/applica", methods=["POST"])
    def applica_sostituzione():
        data, err = _validate_json_body("mese", "famiglia", "slot", "vecchio_fratello", "nuovo_fratello")
        if err:
            return err
        if isinstance(data.get("slot"), bool):
            return jsonify({"errore": "Il campo 'slot' deve essere un intero, non un booleano."}), 400
        try:
            repo.update_storico_assegnazione(
                data["mese"], data["famiglia"], int(data["slot"]),
                data["vecchio_fratello"], data["nuovo_fratello"])
            return jsonify({"ok": True})
        except (TurniVisiteError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400

    # ------------------------------------------------------------------
    # Stato esecuzione
    # ------------------------------------------------------------------

    @app.route("/api/storico/<mese>/esecuzione", methods=["PATCH"])
    def update_esecuzione(mese):
        err = _check_url_param_len(mese, "mese")
        if err:
            return err
        try:
            validate_month_yyyy_mm(mese)
        except ValueError as e:
            return jsonify({"errore": str(e)}), 400
        data, err = _validate_json_body("famiglia", "slot", "stato")
        if err:
            return err
        if isinstance(data.get("slot"), bool):
            return jsonify({"errore": "Il campo 'slot' deve essere un intero, non un booleano."}), 400
        try:
            repo.set_stato_esecuzione(mese, data["famiglia"], int(data["slot"]), data["stato"])
            return jsonify({"ok": True})
        except (TurniVisiteError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/stats/completamento", methods=["GET"])
    def stats_completamento():
        try:
            result = tasso_completamento(repo.get_storico_turni())
            return jsonify(result)
        except (KeyError, TypeError, AttributeError) as e:
            app.logger.error("Errore stats: %s", e)
            return jsonify({"errore": "Errore nel calcolo delle statistiche."}), 500

    # ------------------------------------------------------------------
    # Export WhatsApp
    # ------------------------------------------------------------------

    @app.route("/api/export/whatsapp", methods=["POST"])
    def export_whatsapp():
        data, err = _validate_json_body("mesi", "solution")
        if err:
            return err
        mesi, err = _validate_mesi(data["mesi"])
        if err:
            return err
        if not isinstance(data.get("solution"), dict) or "by_month" not in data["solution"]:
            return jsonify({"errore": "Campo 'solution' mancante o malformato."}), 400
        try:
            text = format_whatsapp_mesi(
                mesi, data["solution"],
                data.get("frequenze", {}), data.get("week_windows", {}))
            return jsonify({"text": text})
        except (KeyError, TypeError, AttributeError) as e:
            app.logger.error("Errore export WhatsApp: %s", e)
            return jsonify({"errore": "Errore nella generazione del testo WhatsApp."}), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        app.logger.exception("Errore interno non gestito: %s", type(e).__name__)
        return jsonify({"errore": "Errore interno del server."}), 500

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"errore": "Risorsa non trovata."}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"errore": "Metodo non permesso."}), 405

    @app.errorhandler(413)
    def handle_too_large(e):
        return jsonify({"errore": "Payload troppo grande (max 1 MB)."}), 413

    return app


def main() -> None:
    from .logging_cfg import setup_logging
    setup_logging()
    app = create_app()
    host = "127.0.0.1"
    logging.info("API REST avviata su http://%s:5000", host)
    print(f"API REST disponibile su http://{host}:5000")
    app.run(debug=False, host=host, port=5000)


if __name__ == "__main__":
    main()
