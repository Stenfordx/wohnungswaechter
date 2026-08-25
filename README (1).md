# Wohnungswaechter für inberlinwohnen

Prüft alle 10 Minuten den Wohnungsfinder der sieben landeseigenen Gesellschaften und schickt dir eine Push-Nachricht, sobald ein Angebot auftaucht, das zu deinen Filtern passt. Läuft kostenlos auf GitHub Actions, du brauchst keinen eigenen Server und keinen laufenden Rechner.

## Einrichtung, etwa 15 Minuten

### 1. Repository anlegen
Neues **öffentliches** Repository auf GitHub erstellen und diese drei Dateien hochladen:
```
finder.py
README.md
.github/workflows/check.yml
```

**Warum öffentlich:** Private Repositories haben nur 2.000 kostenlose Action-Minuten pro Monat. Ein Lauf alle 10 Minuten sind rund 4.300 Minuten, das reicht nicht. Öffentliche Repositories haben unbegrenzte Minuten. Nichts in diesem Repository ist vertraulich, dein Benachrichtigungskanal liegt in den GitHub-Secrets und nicht im Code.

Wenn du unbedingt privat bleiben willst, stell den Cron im Workflow auf `*/30 * * * *`. Dann kommst du auf etwa 1.440 Minuten im Monat und bleibst im Gratiskontingent.

### 2. Benachrichtigung wählen

**Variante A, ntfy (schneller, keine Anmeldung)**
1. App "ntfy" installieren, gibt es für iOS und Android.
2. In der App ein Topic abonnieren, zum Beispiel `wohnung-berlin-8h3kd9`. Denk dir etwas Zufälliges aus, denn wer den Namen kennt, sieht deine Meldungen mit.
3. In GitHub unter *Settings, Secrets and variables, Actions, New repository secret* anlegen:
   - Name `NTFY_TOPIC`, Wert dein Topic-Name.

**Variante B, Telegram (schöner formatiert)**
1. In Telegram `@BotFather` anschreiben, `/newbot`, Namen vergeben, Token kopieren.
2. Deinen neuen Bot anschreiben, irgendetwas senden.
3. `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` im Browser öffnen und die `chat.id` heraussuchen.
4. Zwei Secrets anlegen: `TELEGRAM_TOKEN` und `TELEGRAM_CHAT_ID`.

Beide Varianten gleichzeitig gehen auch.

### 3. Filter anpassen
Oben in `finder.py` stehen deine Kriterien. Aktuell eingestellt:

| Kriterium | Wert |
|---|---|
| Ganze Bezirke | Friedrichshain-Kreuzberg, Lichtenberg, Marzahn-Hellersdorf, Neukölln |
| Ortsteile über PLZ | Alt-Treptow, Plänterwald, Baumschulenweg, Niederschöneweide, Oberschöneweide, Johannisthal, Adlershof, Prenzlauer Berg, Weißensee |
| Zimmer | 1,5 bis 2,0 |
| Kaltmiete | max. 500 € |
| Gesamtmiete | egal |
| Wohnfläche | 35 bis 50 m² |

**Warum PLZ statt Ortsteilnamen:** Die Angebote nennen nur den Bezirk, also "12435, Treptow-Köpenick" statt "Plänterwald". Ein Filter auf den Ortsteilnamen würde nie greifen. Über die PLZ funktioniert es zuverlässig, und der Ortsteil taucht zusätzlich in der Push-Meldung auf.

Die PLZ-Bereiche sind bewusst grosszügig gesetzt. Einzelne Berliner PLZ liegen über zwei Ortsteile, deshalb rutscht gelegentlich ein Nachbarhaus mit durch. Das ist besser als eine verpasste Wohnung.

Zum Ausschalten eines Filters die Bezirksliste leeren (`BEZIRKE = []`) oder die Obergrenze auf `0` setzen.

### 4. Ersten Lauf starten
Unter *Actions, Wohnungswaechter, Run workflow*. Der erste Lauf meldet absichtlich nichts, er speichert nur den aktuellen Bestand als Ausgangspunkt. Ab dem zweiten Lauf kommen nur noch echte Neuzugänge.

## Wenn nichts ankommt

Im Actions-Log steht immer, wie viele Angebote gefunden und wie viele davon gefiltert wurden.

- **"0 Angebote auf der Seite gefunden"** heißt, die Seitenstruktur hat sich geändert. Schick mir das Log, dann passe ich den Parser an.
- **Viele gefunden, aber 0 passend** heißt, deine Filter sind zu eng. Setz die Kaltmiete testweise auf 2000 und schau, ob Meldungen kommen.

## Hinweise

Der Wohnungsfinder ist ohne Anmeldung öffentlich zugänglich, und ein Abruf alle 10 Minuten entspricht ungefähr dem, was ein Mensch beim manuellen Nachschauen erzeugt. Dreh das Intervall nicht herunter. Häufigeres Abrufen bringt dir nichts, belastet aber fremde Server, und du riskierst, blockiert zu werden.

Das Skript liest ausschließlich die öffentliche Übersichtsseite. Es meldet sich nirgends an und verschickt keine Bewerbungen. Das Bewerben bleibt bei dir, und das ist auch gut so, weil eine persönliche Nachricht bei den Gesellschaften mehr bringt als eine automatisierte.

GitHub führt geplante Aktionen bei hoher Last manchmal mit einigen Minuten Verzögerung aus. Rechne im Schnitt mit 10 bis 20 Minuten zwischen Veröffentlichung und Push.
