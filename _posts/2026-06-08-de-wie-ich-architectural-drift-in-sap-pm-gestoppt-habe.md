---
layout: article
title: "Wie ich Architectural Drift in SAP PM gestoppt habe"
date: 2026-06-08 00:00:00 +0000
lang: de
categories: [architektur]
description: "Wie eine klare Verantwortungstaxonomie in ABAP Architectural Drift in einer grossen SAP-PM-Codebasis reduziert hat."
back_label: "Zuruck zu ABAP Craft"
discuss_label: "Diesen Artikel diskutieren"
comments_intro: "Kommentare laufen uber GitHub Discussions."
redirect_from:
  - /posts/de-wie-ich-architectural-drift-in-sap-pm-gestoppt-habe.html
translations:
  - lang: en
    label: English
    url: /architecture/2026/06/08/en-how-i-stopped-architectural-drift-sap-pm/
  - lang: de
    label: Deutsch
    url: /architektur/2026/06/08/de-wie-ich-architectural-drift-in-sap-pm-gestoppt-habe/
  - lang: es
    label: Español
    url: /arquitectura/2026/06/08/es-como-detuve-architectural-drift-en-sap-pm/
---

<p class="note">Die Beispiele verwenden generische Namen wie <code>ZXX_*</code>, um produktive Systeme zu schutzen.</p>

---

Nach 13 Jahren mit SAP-Systemen habe ich das gleiche Muster immer wieder beobachtet.

Ein System startet sauber. Ein kleines Team baut es gewissenhaft auf. Dann waechst es — mehr Integrationen, mehr Menschen, mehr Druck, schnell zu liefern. Drei Jahre spaeter kann niemand sagen, was jede Klasse eigentlich tut. Eine Klasse mit dem Namen `GESTOR_API` handhabt HTTP, Token-Management, JSON-Serialisierung, Business-Validierung und Transaktionslogik. Eine Klasse namens `EXT` sendet Daten an drei verschiedene externe Systeme. Eine Klasse namens `PRINCIPAL` instanziiert alles und wird zum Ort, an den Logik wandert, wenn niemand sonst weiss, wo sie hingehoert.

Das System funktioniert noch. Aber jede Aenderung ist teuer, weil jede Aenderung erfordert, zu viel Kontext zu verstehen, bevor man etwas beruehrt.

Das ist, was ich in einem echten SAP-PM-Modul mit 80+ benutzerdefinierten Klassen, mehreren externen Integrationen und einem Team mit regelmaessiger Rotation getan habe.

---

## Das echte Problem ist nicht das Naming

Es ist verloeckend, dies als Naming-Problem zu rahmen. Es ist es nicht.

Das eigentliche Problem ist, dass **wenn Klassennamen keine Verantwortung vermitteln, das Team beginnt, Logik dort zu platzieren, wo sie nicht hingehoert** — und sie tun es graduell, einen kleinen Kompromiss nach dem anderen, bis die Architektur unkenntlich ist.

Naming ist der Interventionspunkt, weil es das erste Signal ist, das ein Entwickler liest, bevor er eine Klasse oeffnet. Wenn der Name die falsche Erwartung setzt, folgt die falsche Logik.

Das Ziel ist nicht, schoene Namen zu haben. Das Ziel ist, die Architektur in den Namen sichtbar zu machen, sodass Verstoesse offensichtlich werden, bevor sie gepflegt werden.

---

## Die Taxonomie

Ich habe Klassen in sieben Rollen unterteilt. Jede Rolle beantwortet eine andere Frage.

```
EXT      Wen erweitert diese Klasse?     Eine SAP-Transaktion oder Enhancement
API      Welchen Contract behoert?        Die Integrationsgrenze mit einem anderen System
CLIENTE  Welcher Transport gehoert?       HTTP, Token, Serialisierung, Protokoll
SERVIZIO Welche Entitaet gehoert?        Domain-Logik fuer eine PM-Entitaet
FACHADA  Was fasst diese Klasse zusammen? Instanzen — nichts anderes
UTIL     Was berechnet diese Klasse?     Wiederverwendbare technische Funktion
FORM     Was produziert diese Klasse?    Ein Dokument oder Output
```

Das Muster:

```
ZXX_C_EXT__
ZXX_C_EXT__TO_
ZXX_C_EXT__FOR_

ZXX_C_API_SAP_TO_
ZXX_C_API__TO_

ZXX_C_CLIENTE_
ZXX_C_SERVIZIO_
ZXX_C_FACHADA_
ZXX_C_UTIL_
ZXX_C_FORM_
```

---

## Entscheidungen, die ich verteidigen musste

Dies ist der wichtigste Teil. Die oben beschriebene Taxonomie ist einfach. Das, was nicht einfach ist, ist, wo die Grenzen liegen und warum.

### `_TO_` vs `_FOR_` in EXT-Klassen

Am Anfang des Designs hatte ich ein einzelnes Muster fuer alle EXT-Klassen, die externe Systeme einbezogen:

```
ZXX_C_EXT_TX01_TO_SYSTEM_A   " TX01 sendet Daten an SYSTEM_A
ZXX_C_EXT_TX02_TO_SYSTEM_B   " TX02 sendet Daten an SYSTEM_B?
```

Dann bin ich auf einen Fall gestossen, der nicht passte. Eine Klasse, die von Transaktion `TX02` ausgeloest wurde, sendete nichts an `SYSTEM_B`. Sie existierte, weil `SYSTEM_B` Daten stammt haette und SAP reagieren musste — eine Follow-up-Bestellung erstellen, einen Status aktualisieren, einen Prozess ausfuehren. Die Richtung war umgekehrt.

Sie `TO_SYSTEM_B` zu nennen, waere aktiv irrefuehrend gewesen.

Die Loesung war, die Richtung durch die Praposition explizit zu machen:

```
_TO_    SAP initiiert — sendet Daten gegen ein externes System
_FOR_   SAP reagiert  — verarbeitet Daten, die von einem externen System stammen
```

Diese Unterscheidung ist bei Skalierung wichtig. In einem Modul mit 15+ Integrationen und 30+ EXT-Klassen muss ein Entwickler, der dem Team beitritt, die Richtung verstehen, bevor er eine Klasse oeffnet. Die Praposition gibt das in einer Sekunde.

Fuer funktionale Erweiterungen ohne beteiligtes externes System keine Praposition:

```
ZXX_C_EXT_TX01_VALIDATION      " nur internes Verhalten
ZXX_C_EXT_TX01_CUSTOM_FIELDS   " nur internes Verhalten
```

---

### Warum `API` und `CLIENTE` separate Layer sind

Der Instinkt ist, sie zu fusionieren. "Es ist nur ein HTTP-Aufruf — warum zwei Klassen?"

Die Antwort ist, was sechs Monate spaeter passiert.

Eine Klasse, die sowohl den Integrations-Contract *als auch* den HTTP-Transport behoert, wird inaevitabel in zwei inkompatible Richtungen waechsen. Die Contract-Seite muss sich aendern, wenn das externe System seine Payload aendert. Die Transport-Seite muss sich aendern, wenn sich Authentifizierung oder Infrastruktur aendert. Wenn sie in der gleichen Klasse sind, beruehrt jede Aenderung Dinge, die sie nicht beruehren sollte.

Die Trennung, die ich nutze:

```
API      kennt den funktionalen Contract — Strukturen, Feldmappings, Dispatch
CLIENTE  kennt den Transport — HTTP-Client, Token, JSON-Serialisierung, Fehlercodes, Logs
```

Eine `API`-Klasse ruft eine `CLIENTE`-Klasse auf. Sie dupliziert keine Transport-Logik. Eine `CLIENTE`-Klasse hat keine Kenntnis darueber, welche Entitaet sie traegt — Bestellung, Benachrichtigung, Messung, alles. Sie sendet einfach.

In der Praxis:

```
" API-Klasse — kennt den Contract, nicht den Transport
METHOD send.
  NEW zxx_c_cliente_http( )->call_service(
    destination  = 'SYSTEM_A'
    service_name = 'CREATE_ORDER'
    input        = input
    ...
  ).
ENDMETHOD.

" CLIENTE-Klasse — kennt den Transport, nicht den Contract
METHOD call_service.
  " Token abrufen
  " HTTP-Anfrage konstruieren
  " JSON serialisieren
  " Senden, Empfangen, Protokollieren
  " Statuscode interpretieren
ENDMETHOD.
```

Die Grenze ist streng. Sobald du einer `API`-Klasse erlaubst, einen Token zu handhaben, hast du die Trennung verloren und bist wieder bei `GESTOR_API`.

---

### Warum `FACHADA` niemals Business-Logik enthalten darf

Eine `FACHADA`-Klasse gruppiert Instanzen von Services und APIs. Das ist ihre gesamte Aufgabe.

```
CLASS zxx_c_fachada_pm DEFINITION.
  PUBLIC SECTION.
    DATA servizio_orden TYPE REF TO zxx_c_servizio_orden.
    DATA servizio_aviso TYPE REF TO zxx_c_servizio_aviso.
    DATA api_to_system_a TYPE REF TO zxx_c_api_sap_to_system_a.
    ...
  METHODS constructor.
ENDCLASS.
```

Die Regel, die ich erzwinge: **wenn sie ein `IF` hat, das vom Ergebnis eines Service abhaengt, um zu entscheiden, was als naechstes aufgerufen wird, ist es keine `FACHADA` mehr — es ist ein Koordinator.**

Der Grund, warum diese Regel explizit sein muss, ist, dass `FACHADA` der bequemste Ort ist, um Logik hinzuzufuegen. Sie hat bereits alle Instanzen. Es ist einfach, `IF gestor->orden->is_valid( ) THEN gestor->api->send( )` direkt dort zu schreiben. Und das erste Mal, wenn du es tust, sieht es harmlos aus.

Drei Jahre spaeter hat `FACHADA_PM` 40 Methoden, 600 Zeilen und ist der neue `GESTOR_PRINCIPAL`.

Die Regel hat auch ein Korollar: **EXT-Klassen duerfen nicht von `FACHADA_PM` abhaengen**. Sie muessen direkte Abhaengigkeiten von dem spezifischen `SERVIZIO` oder `API` deklarieren, das sie benoetigen. `FACHADA` ist fuer High-Level-Consumer — Reports, Programme, Koordinatoren — nicht fuer Transaktions-Erweiterungen.

---

### Vererbungshierarchien in EXT

Wenn eine Gruppe von EXT-Klassen Verhalten teilt — gleiche Basislogik, gleicher Datenzugriff, gleiche Method-Signaturen — nimmt die Parent-Klasse den Basennamen ohne Differenziator:

```
ZXX_C_EXT_FORMS           " abstrakte Parent
ZXX_C_EXT_FORMS_TYPE_A    " konkrete Implementierung
ZXX_C_EXT_FORMS_TYPE_B    " konkrete Implementierung
ZXX_C_EXT_FORMS_TYPE_C    " konkrete Implementierung
```

Die Parent ist das Praefix. Die Children fuegen den Differenziator hinzu. Jeder Entwickler, der `ZXX_C_EXT_FORMS_TYPE_A` sieht, weiss, wo die Parent zu finden ist, ohne zu suchen.

---

## Wie das im grossen Massstab aussieht

Vorher sah das Inventar so aus — 80 Klassen, keine sichtbare Struktur:

```
ZXX_C_GESTOR_AVISO
ZXX_C_GESTOR_API_EXTERNA
ZXX_C_GESTOR_PRINCIPAL
ZXX_C_API_TX01_SYSTEM_A
ZXX_C_AMP_TX02_API_SYSTEM_B
ZXX_C_AMP_TX02_API_SYSTEM_C
ZXX_C_AMP_TX02_FORMS_1
ZXX_C_AMP_TX02_FORMS_2
...
```

Nachher offenbart das gleiche Inventar, nach Typ sortiert, die Architektur sofort:

```
── EXT (31) ──────────────────────────────────
ZXX_C_EXT_TX01_VALIDATION
ZXX_C_EXT_TX01_TO_SYSTEM_A
ZXX_C_EXT_TX01_FOR_SYSTEM_B
ZXX_C_EXT_TX02_TO_SYSTEM_C
ZXX_C_EXT_FORMS               ← parent
ZXX_C_EXT_FORMS_TYPE_A
ZXX_C_EXT_FORMS_TYPE_B
...

── API (13) ──────────────────────────────────
ZXX_C_API_SAP_TO_SYSTEM_A
ZXX_C_API_SAP_TO_SYSTEM_B
ZXX_C_API_SYSTEM_C_TO_TX01
...

── CLIENTE (2) ───────────────────────────────
ZXX_C_CLIENTE_HTTP
ZXX_C_CLIENTE_MIDDLEWARE

── SERVIZIO (4) ──────────────────────────────
ZXX_C_SERVIZIO_NOTIFICATION
ZXX_C_SERVIZIO_ORDER
ZXX_C_SERVIZIO_EQUIPMENT
ZXX_C_SERVIZIO_FLOC

── FACHADA (1) ───────────────────────────────
ZXX_C_FACHADA_PM
```

Die Architektur ist lesbar, ohne eine einzige Klasse zu oeffnen.

---

## Der Test, den ich fuer neue Klassen benutze

Bevor ich eine neue Klasse benenne, beantworte ich drei Fragen:

1. **Worauf reagiert sie?** Ein SAP-Transaktions-Event, ein HTTP-Aufruf, ein IDoc, ein direkter Method-Aufruf von einer anderen Klasse?

2. **Was weiss sie?** Die funktionale Domaene, die Transport-Layer, den Integrations-Contract, oder nur technische Utilities?

3. **Was produziert sie?** Eine Nebenwirkung auf einer SAP-Entitaet, ein ausgehender Aufruf, ein Dokument, eine wiederverwendbare Berechnung?

Die Antworten bilden sich direkt in die Taxonomie ab. Wenn die Antworten mehrere Typen umfassen — funktionale Domaene *und* HTTP-Transport — ist das ein Signal, dass die Klasse zu viel tut, nicht ein Signal, einen neuen Typ zu schaffen.

---

## Abschluss

Diese Konvention kam nicht von einer Whiteboard-Sitzung. Sie kam aus dem Anschauen eines echten Systems, dem Finden der Inkonsistenzen und dem Fragen, warum jede existierte.

Die Taxonomie hat sieben Typen. Das reicht aus, um jede Klasse in einem grossen SAP-PM-Modul ohne Mehrdeutigkeit abzudecken. Wenn eine neue Klasse nicht passt, ist die richtige Frage, ob die Klasse gut scoped ist — nicht, ob die Taxonomie einen neuen Typ braucht.

Die Architektur ist nur so sichtbar wie die Namen, die du ihr gibst.
