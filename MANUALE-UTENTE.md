# Turni Visite — Guida all'uso

**Versione 0.3.0**

Questa guida ti accompagna nell'utilizzo del software passo dopo passo, dalla prima apertura fino alla gestione completa dei turni di visite.

---

## Prima di iniziare

### Installazione

Apri il terminale e digita uno di questi comandi in base a come vuoi usare il programma:

```
pip install turni-visite[gui]        # con interfaccia grafica (consigliato)
pip install turni-visite[gui,api]    # interfaccia grafica + accesso remoto via API
pip install turni-visite             # solo riga di comando, senza finestre
```

Requisito: Python 3.10 o superiore. Su Linux potrebbe servire anche `python3-tk`.

### Avvio

| Cosa vuoi fare | Comando da digitare |
|---|---|
| Aprire l'interfaccia grafica | `turni-gui` |
| Usare la riga di comando | `turni` |
| Avviare il server API | `turni-api` |

---

## Come funziona il programma — in breve

Il software gestisce l'assegnazione delle visite alle famiglie da parte dei fratelli. Tu inserisci:

- **Chi** sono i fratelli disponibili e quante visite ciascuno puo' fare al mese (capacita')
- **Chi** sono le famiglie da visitare e quante visite riceve ciascuna al mese (frequenza)
- **Chi puo' visitare chi** (associazioni tra fratelli e famiglie)

Il programma calcola automaticamente il piano turni migliore, bilanciando il carico tra tutti i fratelli e rispettando le regole che hai impostato.

### Concetti da conoscere

**Capacita'** — Quante visite puo' fare un fratello in un mese (da 0 a 50). Se la imposti a 0, il fratello viene escluso dalla pianificazione.

**Frequenza** — Quante visite riceve una famiglia al mese: 1, 2 o 4.

**Associazione** — Il collegamento tra un fratello e una famiglia. Solo i fratelli associati a una famiglia possono essere assegnati a visitarla.

**Cooldown** — Dopo aver visitato una famiglia, un fratello non ci torna per un certo numero di mesi (di solito 3). Questo garantisce varieta' nelle visite.

**Bozza** — Il piano calcolato dal programma e' una bozza modificabile. Diventa definitivo solo quando lo confermi.

**Storico** — L'archivio di tutti i turni confermati. Il programma lo consulta per non riassegnare gli stessi fratelli troppo presto alle stesse famiglie.

---

## La barra inferiore

In basso nella finestra trovi sempre:

- **Barra di stato** (a sinistra): mostra messaggi di feedback dopo ogni operazione
- **Tema**: menu a tendina per scegliere l'aspetto visivo — Light (chiaro), Dark (scuro), System (segue il sistema operativo)
- **Lingua**: menu a tendina per cambiare lingua (italiano/inglese). La modifica richiede il riavvio dell'applicazione

La scorciatoia **Ctrl+P** stampa il piano turni corrente in qualsiasi momento.

---

## Parte 1 — Preparare i dati

La prima cosa da fare e' inserire fratelli, famiglie e associazioni. Usa la scheda **Anagrafica**.

### Aggiungere i fratelli

1. Scrivi il nome nel campo **Fratello** in alto
2. Premi **Aggiungi Fratello** (oppure premi Invio direttamente)

Ripeti per ogni fratello.

### Aggiungere le famiglie

1. Scrivi il nome nel campo **Famiglia**
2. Premi **Aggiungi Famiglia** (oppure premi Invio)

### Collegare fratelli e famiglie

Per ogni fratello, indica quali famiglie puo' visitare:

1. Nella riga **Associa**, seleziona un fratello dal primo menu
2. Seleziona una famiglia dal secondo menu
3. Premi **Associa**

Un fratello non associato a nessuna famiglia non partecipera' mai alla pianificazione.

### Impostare la frequenza delle famiglie

La frequenza indica quante volte al mese una famiglia viene visitata. Il valore predefinito e' 2.

1. Nella riga **Frequenza**, scegli il valore (1, 2 o 4)
2. Seleziona la famiglia
3. Premi **Imposta**

### Impostare la capacita' dei fratelli

La capacita' indica il massimo di visite mensili per fratello. Il valore predefinito e' 1.

1. Nel riquadro **Capacita' visite mensili**, seleziona il fratello
2. Modifica il numero nel campo **Cap (0-50)**
3. Premi **Imposta**

### Importare da file CSV

Se hai gia' un elenco in formato CSV, premi **Importa CSV** e seleziona il file. Il formato atteso e':

```
tipo;nome;valore
fratello;Mario Rossi;2
famiglia;Famiglia Bianchi;1
```

### Eliminare un fratello o una famiglia

Usa i menu **Elimina Fratello** o **Elimina Famiglia** in basso, poi premi il pulsante rosso **Elimina**. Il programma ti chiedera' conferma.

### Liste di riepilogo

In basso nella scheda vedi due liste:
- **Fratelli**: ogni nome con la capacita' (`cap=N`) e le eventuali indisponibilita'
- **Famiglie**: ogni nome con la frequenza (`freq=N`) e il numero di fratelli associati (`assoc=N`)

---

## Parte 2 — Controllare la situazione

Prima di pianificare, apri la scheda **Dashboard** per verificare che tutto sia in ordine.

### I sei indicatori

| Indicatore | Significato |
|---|---|
| **Fratelli attivi** | Quanti fratelli hanno almeno un'associazione |
| **Famiglie** | Quante famiglie sono registrate |
| **Capacita' totale** | La somma delle capacita' di tutti i fratelli |
| **Domanda mensile** | Quante visite servono in totale ogni mese |
| **Bilancio** | Capacita' meno domanda. **Deve essere positivo** (verde). Se e' negativo (rosso), i fratelli non bastano |
| **Mesi storico** | Quanti mesi di turni sono gia' stati confermati |

In basso viene mostrato l'**ultimo mese pianificato** e il pulsante **Aggiorna** per ricaricare i dati.

### Avvisi

Il riquadro **Avvisi e suggerimenti** ti segnala eventuali problemi:
- Famiglie senza fratelli associati
- Fratelli non associati a nessuna famiglia
- Capacita' insufficiente rispetto alla domanda
- Indisponibilita' registrate
- Vincoli personalizzati attivi

Se vedi "Tutto in ordine", puoi procedere con la pianificazione.

---

## Parte 3 — Pianificare i turni

Apri la scheda **Pianificazione**. Segui questi passi:

### Passo 1 — Inserire i mesi

Nel campo **Mesi**, scrivi i mesi da pianificare separati da virgola. Formato: `AAAA-MM`.

Esempio per un trimestre: `2026-06, 2026-07, 2026-08`

### Passo 2 — Controllare i parametri

- **Cooldown**: quanti mesi devono passare prima che lo stesso fratello torni nella stessa famiglia (consigliato: 3)
- **Timeout**: quanti secondi il programma puo' impiegare per cercare la soluzione (consigliato: 20-60)
- **Thread**: quanti processori usare in parallelo (lascia il valore predefinito se non sei sicuro)

### Passo 3 — Verifica rapida (facoltativo)

Premi **Pre-check fattibilita'** per un controllo veloce. Il programma ti dice subito se ci sono problemi evidenti (fratelli insufficienti, famiglie senza associazioni, ecc.) senza ancora calcolare il piano.

### Passo 4 — Calcolare il piano

Premi **Ottimizza & Genera PDF**.

Si apre una finestra dove puoi impostare le **settimane del mese** in cui cadono le visite (es. "01-07, 15-21" per due visite nella prima e terza settimana). Se hai gia' salvato un template, i valori sono precompilati: premi **Conferma** per accettarli.

Una barra animata indica che il calcolo e' in corso. Al termine:

- **Se la soluzione viene trovata**: il piano compare nell'area di testo, organizzato per fratello
- **Se non viene trovata**: il programma mostra una diagnosi con i motivi (troppo pochi fratelli, cooldown troppo stretto, ecc.)

### Passo 5 — Modificare singole assegnazioni (facoltativo)

Se qualche assegnazione non ti convince, usa il pannello **Modifica assegnazione**:

1. Seleziona il **mese**
2. Seleziona la **famiglia**
3. Seleziona lo **slot** (il numero della visita in quel mese)
4. Scegli il **nuovo fratello** da assegnare
5. Premi **Applica**

### Passo 6 — Salvare e confermare

Hai tre opzioni:

| Pulsante | Cosa fa |
|---|---|
| **Salva come bozza** | Salva il piano in modo provvisorio. Ti chiede se vuoi anche generare un PDF da stampare o inviare per approvazione |
| **Accetta tutti** | Marca tutte le assegnazioni della bozza come accettate |
| **Conferma selezionati** | Salva definitivamente nello storico le assegnazioni accettate. Crea automaticamente un backup prima di salvare. Se le email sono configurate, ti chiede se vuoi inviare le notifiche ai fratelli |
| **Scarta bozza** | Cancella tutto senza salvare |

### Esportare il piano

Dopo l'ottimizzazione, puoi:

- Premere **Esporta CSV** per salvare un foglio di calcolo
- Premere **Copia WhatsApp** per copiare il testo formattato negli appunti, pronto da incollare in una chat
- Premere **Ctrl+P** per stampare direttamente

### Salvare i template settimanali

Se le settimane delle visite sono sempre le stesse, premi **Salva template settimane**: la prossima volta saranno precompilate automaticamente.

---

## Parte 4 — Gestire lo storico

Dopo aver confermato i turni, apri la scheda **Storico** per gestire l'esecuzione delle visite.

### Consultare i turni passati

La lista mostra tutti i mesi confermati con il numero di assegnazioni, quante visite sono state completate e la data di conferma. Fai clic su un mese per vedere il dettaglio: per ogni famiglia vedrai il fratello assegnato, il numero di slot e lo stato:

- `-` pianificato (la visita deve ancora avvenire)
- `V` completato (la visita e' stata fatta)
- `X` annullato (la visita non e' stata fatta)

### Segnare una visita come completata o annullata

1. Seleziona il mese nella lista
2. Nel pannello **Stato esecuzione**, scegli la **famiglia** e lo **slot**
3. Premi **Segna completata** (verde) oppure **Segna annullata** (rosso)

### Trovare un sostituto

Se un fratello si ammala o non puo' fare la visita:

1. Seleziona il mese nella lista
2. Nel pannello **Sostituzione d'emergenza**, seleziona il fratello da sostituire
3. Premi **Cerca sostituto**: il programma propone i candidati migliori ordinati per carico (chi ha meno visite viene prima)
4. Scegli il candidato dal menu e premi **Applica sostituzione**

### Esportare lo storico

Premi **Esporta storico CSV** per salvare tutto lo storico in un file apribile con Excel.

### Eliminare un mese dallo storico

Seleziona il mese e premi **Elimina selezionato** (rosso). Il programma chiede conferma. Questa azione e' irreversibile, a meno che tu non abbia un backup da ripristinare.

---

## Parte 5 — Vista calendario

La scheda **Calendario** mostra una griglia con le famiglie sulle righe e i mesi sulle colonne. Ogni cella mostra il fratello assegnato, colorato con un colore univoco. In basso c'e' la legenda dei colori.

E' utile per avere una visione d'insieme rapida: vedi subito se un fratello appare troppo spesso nella stessa famiglia o se ci sono mesi scoperti.

Premi **Aggiorna** per ricaricare i dati.

---

## Parte 6 — Funzioni avanzate

La scheda **Avanzate** contiene sette sotto-schede per le impostazioni piu' specifiche.

### Indisponibilita'

Per segnalare che un fratello non e' disponibile in un mese specifico (ferie, malattia, ecc.):

1. Seleziona il fratello
2. Scrivi il mese nel formato `AAAA-MM`
3. Premi **Aggiungi**

Il programma escludera' automaticamente quel fratello dalla pianificazione di quel mese. Per togliere l'indisponibilita', seleziona lo stesso fratello e mese e premi **Rimuovi**.

### Vincoli tra fratelli

Puoi definire regole tra coppie di fratelli:

- **incompatibile**: i due fratelli non verranno mai assegnati insieme alla stessa famiglia nello stesso mese
- **preferenza_coppia**: il programma cerchera' di assegnarli insieme quando possibile

1. Seleziona i due fratelli e il tipo di vincolo
2. Premi **Aggiungi**

Per eliminare un vincolo, selezionalo nella lista e premi **Rimuovi selezionato**.

### Affinita'

Puoi indicare quanto un fratello e' adatto a visitare una famiglia specifica:

1. Seleziona famiglia e fratello
2. Inserisci un **peso** da -10 a +10: positivo = preferito, negativo = sconsigliato
3. Premi **Imposta affinita'**

L'ottimizzatore terra' conto di queste preferenze quando possibile.

### Notifiche email

Per inviare email ai fratelli dopo la conferma dei turni:

**Configurazione del server email:**

1. Compila i campi **Host SMTP** (es. `smtp.gmail.com`), **Porta** (es. `587`), **Utente** e **Mittente**
2. Premi **Salva configurazione**

**Importante**: la password del server email NON va inserita qui. Per motivi di sicurezza, devi impostarla come variabile d'ambiente nel sistema:

```
export TURNI_SMTP_PASSWORD="la_tua_password"
```

Su Windows: Impostazioni di sistema > Variabili d'ambiente.

**Email dei fratelli:**

1. Seleziona un fratello
2. Scrivi il suo indirizzo email
3. Premi **Imposta**

Dopo aver confermato i turni nella scheda Pianificazione, il programma ti chiedera' se vuoi inviare le notifiche via email.

### Backup e ripristino

- **Crea backup ora**: salva una copia del file dati con la data e l'ora
- **Ripristina selezionato**: riporta i dati allo stato del backup scelto (chiede conferma)
- **Aggiorna lista**: ricarica l'elenco dei backup disponibili
- Il programma crea automaticamente un backup ogni volta che confermi i turni
- Vengono conservati gli ultimi 10 backup; i piu' vecchi vengono eliminati automaticamente

### Statistiche

Quattro rapporti per valutare l'equita' e la copertura:

| Pulsante | Cosa mostra |
|---|---|
| **Carico fratelli** | Per ogni fratello: visite totali, mesi attivi, famiglie visitate |
| **Copertura famiglie** | Per ogni famiglia: visite ricevute, mesi coperti, fratelli coinvolti |
| **Indice equita'** | Media, deviazione standard, minimo, massimo delle visite per fratello e indice di Gini (0 = equo, 1 = disuguale) |
| **Trend mensile** | Andamento mese per mese con un grafico a barre testuale |

### Audit Trail

Mostra il registro degli ultimi 50 eventi del sistema (aggiunte, eliminazioni, conferme, ripristini). Premi **Aggiorna** per ricaricare.

---

## Parte 7 — Uso da riga di comando (CLI)

Se preferisci lavorare dal terminale, avvia il programma con il comando `turni`. Compare un menu numerato:

```
 1. Aggiungi un fratello          10. Storico turni
 2. Aggiungi una famiglia         11. Indisponibilita' temporanee
 3. Associa fratello-famiglia     12. Vincoli personalizzati
 4. Frequenza (1/2/4)             13. Backup e ripristino
 5. Capacita' (0-50)              14. Statistiche e report
 6. Ottimizza turni               15. Import da CSV
 7. Sanifica dati                 16. Dashboard KPI
 8. Elimina un fratello           17. Sostituzione d'emergenza
 9. Elimina una famiglia          18. Affinita'
                                  19. Esci
```

Digita il numero e premi Invio. Il programma ti guida con domande in sequenza.

### Comando 6 — Ottimizza turni (il piu' importante)

1. Inserisci i mesi uno per riga (Invio vuoto per terminare)
2. Configura le settimane per ogni frequenza (premi Invio per accettare i valori preimpostati)
3. Il programma esegue un controllo preliminare e ti avvisa di eventuali problemi
4. Se la soluzione viene trovata, genera automaticamente un PDF e ti chiede:
   - Vuoi esportare per WhatsApp? `[s/N]`
   - Vuoi esportare in CSV? `[s/N]`
   - Vuoi salvare nello storico? `[s/N]`

### Comando 7 — Sanifica dati

Questo comando normalizza tutti i nomi nel sistema (uniforma maiuscole, spazi, accenti) e permette di unificare nomi duplicati o simili tramite alias manuali. Utile quando i nomi sono stati inseriti in modi diversi (es. "Mario Rossi" e "mario rossi").

Il programma ti chiede di inserire le mappature nel formato `nome_errato -> nome_corretto`. Invio vuoto per terminare. Dopo la sanifica, segnala eventuali nomi ancora simili che potresti voler unificare.

### Ricerca fuzzy dei nomi

Quando scrivi un nome nella CLI, non serve che sia esatto. Se il programma non lo trova, ti suggerisce i nomi piu' simili e ti chiede di scegliere.

---

## Parte 8 — Configurazione avanzata

### Variabili d'ambiente

Puoi personalizzare il comportamento del programma impostando queste variabili prima di avviarlo:

| Variabile | Cosa controlla | Valore predefinito |
|---|---|---|
| `TURNI_DATA_FILE` | Percorso del file dati | `dati_turni.json` |
| `TURNI_BACKUP_DIR` | Cartella dei backup | `backups/` |
| `TURNI_SOLVER_TIMEOUT` | Tempo massimo per il calcolo (secondi) | 30 (max 300) |
| `TURNI_SMTP_PASSWORD` | Password del server email | *(obbligatoria per le email)* |
| `TURNI_SMTP_HOST` | Server email | *(sovrascrive il valore salvato)* |
| `TURNI_SMTP_PORT` | Porta email (587 o 465) | *(sovrascrive il valore salvato)* |
| `TURNI_SMTP_USER` | Utente email | *(sovrascrive il valore salvato)* |
| `TURNI_API_KEY` | Chiave di autenticazione API | *(obbligatoria per l'API)* |
| `TURNI_API_NO_AUTH` | Disabilita autenticazione API (impostare a `1`) | *(solo per sviluppo/test)* |
| `TURNI_CORS_ORIGINS` | Origini CORS consentite (URL separati da virgola) | localhost varie porte |
| `TURNI_LOG_LEVEL` | Livello di logging (DEBUG, INFO, WARNING, ERROR) | INFO |

### File dati

Tutti i dati sono in un unico file `dati_turni.json`. Se vuoi spostarlo (es. su una cartella condivisa), imposta `TURNI_DATA_FILE` con il nuovo percorso.

---

## Riepilogo: il percorso tipico

```
1. PREPARAZIONE
   Anagrafica > Aggiungi fratelli e famiglie
   Anagrafica > Associa fratelli a famiglie
   Anagrafica > Imposta capacita' e frequenze
   Avanzate > Indisponibilita' (se necessario)

2. CONTROLLO
   Dashboard > Verifica che il bilancio sia verde e non ci siano avvisi

3. PIANIFICAZIONE
   Pianificazione > Inserisci i mesi
   Pianificazione > Pre-check (facoltativo)
   Pianificazione > Ottimizza & Genera PDF
   Pianificazione > Modifica eventuali assegnazioni
   Pianificazione > Salva come bozza > stampa il PDF per approvazione

4. CONFERMA
   Pianificazione > Accetta tutti > Conferma selezionati
   (il programma crea backup e offre l'invio email)

5. ESECUZIONE
   Storico > Segna completata / Segna annullata per ogni visita
   Storico > Cerca sostituto se un fratello non puo' fare la visita

6. VERIFICA
   Calendario > Vista d'insieme dei turni
   Avanzate > Statistiche > Controlla equita' e copertura
```

---

## Nota sull'API REST

Se hai installato il software con `pip install turni-visite[api]`, puoi avviare un server che espone tutte le funzionalita' del programma come servizio web. Questo permette di integrare Turni Visite con altre applicazioni (web, mobile, script automatici).

Per avviare: `turni-api` (richiede la variabile `TURNI_API_KEY` o `TURNI_API_NO_AUTH=1`).

L'API espone endpoint per gestire fratelli, famiglie, associazioni, ottimizzazione, bozze, storico, statistiche e sostituzioni. Per la documentazione tecnica completa degli endpoint, consultare il file sorgente `turni_visite/api.py`.

---

*Turni Visite v0.3.0 — Guida all'uso*
