# Decisioni e richieste dell'utente

Questo file registra solo ciò che è stato deciso o richiesto dall'utente.

## Decisioni

| Data | Decisione o richiesta |
|------------|-----------------------|
| 2026-11-08 | Lo scopo iniziale del progetto è tracciare il punto da cui esce il suono negli strumenti musicali. |
| 2026-11-08 | Si parte da un solo strumento: il saxofono. |
| 2026-11-08 | Dal punto tracciato partiranno animazioni basate sul microfono del computer. |
| 2026-11-08 | Tracciare sempre le decisioni dell'utente, separandole da ciò che decide l'AI. |
| 2026-11-08 | Nei commit l'AI non va mai citata. |
| 2026-11-08 | La repository su GitHub è privata. |
| 2026-11-08 | Il primo sax da tracciare è il sax tenore. |
| 2026-11-08 | Il progetto è personale, aperto a eventuali contributi esterni. |
| 2026-11-08 | I documenti di progetto sono scritti in inglese. |
| 2026-11-08 | Si usano solo immagini che non creino problemi legali di copyright: licenze accettate CC0, pubblico dominio e CC BY, salvando sempre la citazione dell'autore. |
| 2026-11-08 | Il modello si addestra su sax tenore e contralto, escludendo i soprani dritti. |
| 2026-11-08 | Oltre alle immagini online si useranno video girati dall'utente con un sax tenore. |
| 2026-11-08 | Su ogni immagine si segnano 4 punti: centro della campana, 2 punti opposti sul bordo e bocchino. |
| 2026-11-08 | Il modello da addestrare è YOLO di Ultralytics. |
| 2026-11-08 | I punti li segna l'utente, con un'interfaccia su misura in localhost con l'elenco delle immagini. |
| 2026-11-08 | La prima parte di lavoro finisce con il dataset annotato e un breve addestramento di prova. |
| 2026-11-08 | Se i punti di uno strumento cambiano, le immagini già annotate tornano da riannotare senza perdere i vecchi punti. |
| 2026-11-08 | Le prove automatiche della pagina di annotazione stanno nel progetto, con Playwright installato solo per lo sviluppo. |
| 2026-11-08 | Il quarto punto è il kiver e non più il bocchino, che raramente è visibile: frontalmente è coperto dal kiver, curvo su alcuni sax. |
| 2026-11-08 | Il punto kiver si segna circa sul punto più alto visibile della sua curva. |
| 2026-11-08 | Immagini e video non vanno mai su GitHub: se ci finiscono vanno rimossi senza lasciare traccia. |
| 2026-11-08 | Nella seconda fase la pagina mostra i punti già messi dal modello: l'utente sposta quelli sbagliati, invece di cliccarli tutti. |
| 2026-11-08 | Le immagini si controllano una alla volta e si salvano solo con Conferma o Invio, non con una griglia di conferma multipla. |
| 2026-11-08 | Le immagini in cui il modello non trova il sax arrivano in fondo e si segnano a mano. |
| 2026-11-08 | Sulla pagina i tasti 1-4 selezionano un punto, le frecce lo spostano, il tasto cancella lo elimina e il tasto S nasconde o mostra tutti i punti. |
| 2026-11-09 | Il dataset esportato e i risultati degli addestramenti stanno fuori da iCloud, per evitare file doppi. |
| 2026-11-09 | L'intero progetto sta fuori da iCloud, in `~/Projects/visualMusic`. |
| 2026-11-09 | Il prossimo lavoro è solo il tracciamento dal vivo: microfono e animazioni arrivano dopo. |
| 2026-11-09 | Il tracciamento si vede in una pagina nel browser, raggiungibile solo da questo computer. |
| 2026-11-09 | La sorgente può essere la webcam o un video registrato. |
| 2026-11-09 | I punti con sicurezza sotto il 50% non si mostrano. |
| 2026-11-09 | Un punto del suono viene evidenziato: il centro della campana o, se è nascosto, il punto medio tra i due bordi. |
| 2026-11-09 | I punti dal vivo sono stabilizzati e restano fermi circa 0,2 secondi quando il modello li perde. |
| 2026-11-09 | Come punto finale del progetto verrà distribuito il modello addestrato; fino ad allora si continua a migliorarlo. |
