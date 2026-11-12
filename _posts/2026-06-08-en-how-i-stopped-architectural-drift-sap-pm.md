---
layout: article
title: "How I Stopped Architectural Drift in SAP PM"
date: 2026-06-08 00:00:00 +0000
lang: en
categories: [architecture]
description: "How a responsibility taxonomy helped me stop architectural drift in a large SAP PM ABAP codebase."
back_label: "Back to ABAP Craft"
discuss_label: "Discuss this article"
comments_intro: "Comments are powered by GitHub Discussions."
redirect_from:
  - /posts/en-how-i-stopped-architectural-drift-sap-pm.html
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

<p class="note">Examples use generic names <code>ZXX_*</code> to protect production systems.</p>

---

After 13 years working on SAP systems, I've seen the same pattern repeat.

A system starts clean. A small team builds it with care. Then it grows — more integrations, more people, more pressure to deliver fast. Three years later, nobody can tell what each class actually does. A class called `GESTOR_API` handles HTTP, token management, JSON serialization, business validation, and transaction logic. A class called `EXT` sends data to three different external systems. A class called `PRINCIPAL` instantiates everything and ends up being the place where logic goes when nobody knows where else to put it.

The system still works. But every change is expensive, because every change requires understanding too much context before touching anything.

This is what I did about it in a real SAP PM module with 80+ custom classes, multiple external integrations, and a team with regular rotation.

---

## The real problem is not naming

It's tempting to frame this as a naming problem. It isn't.

The real problem is that **when class names don't communicate responsibility, the team starts putting logic where it doesn't belong** — and they do it gradually, one small compromise at a time, until the architecture is unrecognizable.

Naming is the intervention point because it's the first signal a developer reads before opening a class. If the name sets the wrong expectation, the wrong logic follows.

The goal is not pretty names. The goal is to make the architecture visible in the names, so that violations become obvious before they're committed.

---

## The taxonomy

I separated classes into seven roles. Each role answers a different question.

```
EXT      Who is this class extending?       A SAP transaction or enhancement
API      What contract does this class own? The integration boundary with another system
CLIENTE  What transport does this class own? HTTP, token, serialization, logging
SERVICIO What entity does this class own?   Domain logic for one PM entity
FACHADA  What does this class group?        Instances — nothing else
UTIL     What does this class compute?      Reusable technical function
FORM     What does this class produce?      A document or output
```

The pattern:

```
ZXX_C_EXT__
ZXX_C_EXT__TO_
ZXX_C_EXT__FOR_

ZXX_C_API_SAP_TO_
ZXX_C_API__TO_

ZXX_C_CLIENTE_
ZXX_C_SERVICIO_
ZXX_C_FACHADA_
ZXX_C_UTIL_
ZXX_C_FORM_
```

---

## Decisions I had to defend

This is the part that matters most. The taxonomy above is straightforward. What's not straightforward is where the lines are and why.

### `_TO_` vs `_FOR_` in EXT classes

Early in the design, I had a single pattern for all EXT classes that involved external systems:

```
ZXX_C_EXT_TX01_TO_SYSTEM_A   " TX01 sends data to SYSTEM_A
ZXX_C_EXT_TX02_TO_SYSTEM_B   " TX02 sends data to SYSTEM_B?
```

Then I hit a case that didn't fit. A class triggered from transaction `TX02` wasn't sending anything to `SYSTEM_B`. It existed because `SYSTEM_B` had originated data and SAP needed to react — create a follow-up order, update a status, run a process. The direction was reversed.

Calling it `TO_SYSTEM_B` would have been actively misleading.

The fix was to make direction explicit in the preposition:

```
_TO_    SAP initiates — pushes data toward an external system
_FOR_   SAP reacts   — processes data originated by an external system
```

This distinction matters at scale. In a module with 15+ integrations and 30+ EXT classes, a developer joining the team needs to understand direction before opening a class. The preposition gives that in one second.

For functional extensions with no external system involved, no preposition:

```
ZXX_C_EXT_TX01_VALIDATION      " internal behavior only
ZXX_C_EXT_TX01_CUSTOM_FIELDS   " internal behavior only
```

---

### Why `API` and `CLIENTE` are separate layers

The instinct is to merge them. "It's just one HTTP call — why two classes?"

The answer is what happens six months later.

A class that owns both the integration contract *and* the HTTP transport will inevitably grow in two incompatible directions. The contract side needs to change when the external system changes its payload. The transport side needs to change when authentication or infrastructure changes. When they're in the same class, every change touches things it shouldn't need to touch.

The separation I use:

```
API      knows the functional contract — structures, field mappings, dispatch
CLIENTE  knows the transport — HTTP client, token, JSON serialization, error codes, logs
```

An `API` class calls a `CLIENTE`. It does not duplicate transport logic. A `CLIENTE` class has no knowledge of what entity it's carrying — order, notification, measurement, anything. It just sends.

In practice:

```
" API class — knows the contract, not the transport
METHOD send.
  NEW zxx_c_cliente_http( )->call_service(
    destination  = 'SYSTEM_A'
    service_name = 'CREATE_ORDER'
    input        = input
    ...
  ).
ENDMETHOD.

" CLIENTE class — knows the transport, not the contract
METHOD call_service.
  " get token
  " build HTTP request
  " serialize JSON
  " send, receive, log
  " interpret status code
ENDMETHOD.
```

The boundary is strict. Once you allow an `API` class to handle a token, you've lost the separation and you're back to `GESTOR_API`.

---

### Why `FACHADA` must never contain business logic

A `FACHADA` class groups instances of services and APIs. That's its entire job.

```
CLASS zxx_c_fachada_pm DEFINITION.
  PUBLIC SECTION.
    DATA servicio_orden TYPE REF TO zxx_c_servicio_orden.
    DATA servicio_aviso TYPE REF TO zxx_c_servicio_aviso.
    DATA api_to_system_a TYPE REF TO zxx_c_api_sap_to_system_a.
    ...
  METHODS constructor.
ENDCLASS.
```

The rule I enforce: **if it has an `IF` that depends on the result of a service to decide what to call next, it's not a `FACHADA` anymore — it's a coordinator.**

The reason this rule needs to be explicit is that `FACHADA` is the most convenient place to add logic. It already has all the instances. It's easy to write `IF gestor->orden->is_valid( ) THEN gestor->api->send( )` right there. And the first time you do it, it seems harmless.

Three years later, `FACHADA_PM` has 40 methods, 600 lines, and is the new `GESTOR_PRINCIPAL`.

The rule also has a corollary: **EXT classes must not depend on `FACHADA_PM`**. They must declare direct dependencies on the specific `SERVICIO` or `API` they need. `FACHADA` is for high-level consumers — reports, programs, coordinators — not for transaction extensions.

---

### Inheritance hierarchies in EXT

When a group of EXT classes shares behavior — same base logic, same data access, same method signatures — the parent class takes the base name without a differentiator:

```
ZXX_C_EXT_FORMS           " abstract parent
ZXX_C_EXT_FORMS_TYPE_A    " concrete implementation
ZXX_C_EXT_FORMS_TYPE_B    " concrete implementation
ZXX_C_EXT_FORMS_TYPE_C    " concrete implementation
```

The parent is the prefix. The children add the differentiator. Any developer who sees `ZXX_C_EXT_FORMS_TYPE_A` knows where to find the parent without searching.

---

## What this looks like at scale

Before, the inventory looked like this — 80 classes, no visible structure:

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

After, the same inventory sorted by type reveals the architecture immediately:

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

── SERVICIO (4) ──────────────────────────────
ZXX_C_SERVICIO_NOTIFICATION
ZXX_C_SERVICIO_ORDER
ZXX_C_SERVICIO_EQUIPMENT
ZXX_C_SERVICIO_FLOC

── FACHADA (1) ───────────────────────────────
ZXX_C_FACHADA_PM
```

The architecture is readable without opening a single class.

---

## The test I use for new classes

Before naming a new class, I answer three questions:

1. **What does it react to?** A SAP transaction event, an HTTP call, an IDoc, a direct method call from another class?

2. **What does it know about?** The functional domain, the transport layer, the integration contract, or just technical utilities?

3. **What does it produce?** A side effect on a SAP entity, an outbound call, a document, a reusable computation?

The answers map directly to the taxonomy. If the answers span multiple types — functional domain *and* HTTP transport — that's a signal the class is doing too much, not a signal to create a new type.

---

## Final note

This convention didn't come from a whiteboard session. It came from looking at a real system, finding the inconsistencies, and asking why each one existed.

The taxonomy has seven types. That's enough to cover every class in a large SAP PM module without ambiguity. If a new class doesn't fit, the right question is whether the class is well-scoped — not whether the taxonomy needs a new type.

The architecture is only as visible as the names you give it.
