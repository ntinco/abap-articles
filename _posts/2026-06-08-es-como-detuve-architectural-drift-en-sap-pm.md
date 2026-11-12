---
layout: article
title: "Como detuve architectural drift en SAP PM"
date: 2026-06-08 00:00:00 +0000
lang: es
categories: [arquitectura]
description: "Como una taxonomia de responsabilidades en ABAP me permitio frenar architectural drift en una codebase SAP PM."
back_label: "Volver a ABAP Craft"
discuss_label: "Comenta este articulo"
comments_intro: "Los comentarios usan GitHub Discussions."
redirect_from:
  - /posts/es-como-detuve-architectural-drift-en-sap-pm.html
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

<p class="note">Los ejemplos usan nombres genericos <code>ZXX_*</code> para proteger sistemas productivos.</p>

---

Despues de 13 anos trabajando en sistemas SAP, he visto el mismo patron repetirse una y otra vez.

Un sistema empieza limpio. Un equipo pequeno lo construye con cuidado. Luego crece — mas integraciones, mas personas, mas presion para entregar rapido. Tres anos despues, nadie puede decir que hace exactamente cada clase. Una clase llamada `GESTOR_API` maneja HTTP, gestion de tokens, serializacion JSON, validacion de negocio y logica de transaccion. Una clase llamada `EXT` envia datos a tres sistemas externos diferentes. Una clase llamada `PRINCIPAL` instancia todo y se convierte en el lugar donde va la logica cuando nadie sabe donde mas ponerla.

El sistema sigue funcionando. Pero cada cambio es caro, porque cada cambio requiere entender demasiado contexto antes de tocar cualquier cosa.

Esto es lo que hice en un modulo SAP PM real con mas de 80 clases personalizadas, multiples integraciones externas y un equipo con rotacion regular.

---

## El problema real no es el naming

Es tentador enmarcar esto como un problema de naming. No lo es.

El problema real es que **cuando los nombres de clases no comunican responsabilidad, el equipo comienza a poner logica donde no deberia** — y lo hacen gradualmente, un pequeno compromiso a la vez, hasta que la arquitectura es irreconocible.

Naming es el punto de intervencion porque es la primera senal que un desarrollador lee antes de abrir una clase. Si el nombre establece la expectativa equivocada, sigue la logica equivocada.

El objetivo no es tener nombres bonitos. El objetivo es hacer visible la arquitectura en los nombres, para que las violaciones sean obvias antes de que se confirmen.

---

## La taxonomia

Separe las clases en siete roles. Cada rol responde una pregunta diferente.

```
EXT      A quien extiende esta clase?      Una transaccion SAP o enhancement
API      Que contrato posee esta clase?    El limite de integracion con otro sistema
CLIENTE  Que transporte posee?              HTTP, token, serializacion, logs
SERVICIO Que entidad posee?                 Logica de dominio para una entidad PM
FACHADA  Que agrupa esta clase?             Instancias — nada mas
UTIL     Que calcula esta clase?            Funcion tecnica reutilizable
FORM     Que produce esta clase?            Un documento o salida
```

El patron:

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

## Decisiones que hubo que defender

Esta es la parte que mas importa. La taxonomia de arriba es directa. Lo que no es directo es donde estan las lineas y por que.

### `_TO_` vs `_FOR_` en clases EXT

Al principio del diseno, tenia un patron unico para todas las clases EXT que involucraban sistemas externos:

```
ZXX_C_EXT_TX01_TO_SYSTEM_A   " TX01 envia datos a SYSTEM_A
ZXX_C_EXT_TX02_TO_SYSTEM_B   " TX02 envia datos a SYSTEM_B?
```

Luego me encontre con un caso que no encajaba. Una clase activada desde la transaccion `TX02` no estaba enviando nada a `SYSTEM_B`. Existia porque `SYSTEM_B` habia originado datos y SAP necesitaba reaccionar — crear una orden de seguimiento, actualizar un estado, ejecutar un proceso. La direccion estaba invertida.

Llamarla `TO_SYSTEM_B` habria sido activamente enganoso.

La solucion fue hacer explicitamente direccional la preposicion:

```
_TO_    SAP inicia   — empuja datos hacia un sistema externo
_FOR_   SAP reacciona — procesa datos originados por un sistema externo
```

Esta distincion importa a escala. En un modulo con 15+ integraciones y 30+ clases EXT, un desarrollador que se une al equipo necesita entender direccion antes de abrir una clase. La preposicion lo da en un segundo.

Para extensiones funcionales sin sistema externo involucrado, sin preposicion:

```
ZXX_C_EXT_TX01_VALIDATION      " solo comportamiento interno
ZXX_C_EXT_TX01_CUSTOM_FIELDS   " solo comportamiento interno
```

---

### Por que `API` y `CLIENTE` son capas separadas

El instinto es fusionarlas. "Es solo una llamada HTTP — por que dos clases?"

La respuesta es lo que sucede seis meses despues.

Una clase que posee tanto el contrato de integracion *como* el transporte HTTP inevitablemente creceera en dos direcciones incompatibles. El lado del contrato necesita cambiar cuando el sistema externo cambia su payload. El lado del transporte necesita cambiar cuando cambia la autenticacion o infraestructura. Cuando estan en la misma clase, cada cambio toca cosas que no deberia tocar.

La separacion que uso:

```
API      conoce el contrato funcional — estructuras, mappings de campos, dispatch
CLIENTE  conoce el transporte — cliente HTTP, token, serializacion JSON, codigos de error, logs
```

Una clase `API` llama a una clase `CLIENTE`. No duplica logica de transporte. Una clase `CLIENTE` no tiene conocimiento de que entidad esta llevando — orden, notificacion, medicion, lo que sea. Solo envia.

En la practica:

```
" Clase API — conoce el contrato, no el transporte
METHOD send.
  NEW zxx_c_cliente_http( )->call_service(
    destination  = 'SYSTEM_A'
    service_name = 'CREATE_ORDER'
    input        = input
    ...
  ).
ENDMETHOD.

" Clase CLIENTE — conoce el transporte, no el contrato
METHOD call_service.
  " obtener token
  " construir solicitud HTTP
  " serializar JSON
  " enviar, recibir, registrar
  " interpretar codigo de estado
ENDMETHOD.
```

El limite es estricto. Una vez que permites que una clase `API` maneje un token, has perdido la separacion y vuelves a `GESTOR_API`.

---

### Por que `FACHADA` nunca debe contener logica de negocio

Una clase `FACHADA` agrupa instancias de servicios y APIs. Ese es su trabajo completo.

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

La regla que impongo: **si tiene un `IF` que depende del resultado de un servicio para decidir que llamar despues, ya no es una `FACHADA` — es un coordinador.**

La razon por la que esta regla necesita ser explicita es que `FACHADA` es el lugar mas conveniente para agregar logica. Ya tiene todas las instancias. Es facil escribir `IF gestor->orden->is_valid( ) THEN gestor->api->send( )` directamente ahi. Y la primera vez que lo haces, parece inofensivo.

Tres anos despues, `FACHADA_PM` tiene 40 metodos, 600 lineas y es el nuevo `GESTOR_PRINCIPAL`.

La regla tambien tiene un corolario: **las clases EXT no deben depender de `FACHADA_PM`**. Deben declarar dependencias directas del `SERVICIO` o `API` especifico que necesitan. `FACHADA` es para consumidores de alto nivel — reportes, programas, coordinadores — no para extensiones de transaccion.

---

### Jerarquias de herencia en EXT

Cuando un grupo de clases EXT comparte comportamiento — misma logica base, mismo acceso a datos, mismas signaturas de metodo — la clase padre toma el nombre base sin diferenciador:

```
ZXX_C_EXT_FORMS           " padre abstracto
ZXX_C_EXT_FORMS_TYPE_A    " implementacion concreta
ZXX_C_EXT_FORMS_TYPE_B    " implementacion concreta
ZXX_C_EXT_FORMS_TYPE_C    " implementacion concreta
```

La padre es el prefijo. Las hijas agregan el diferenciador. Cualquier desarrollador que ve `ZXX_C_EXT_FORMS_TYPE_A` sabe donde encontrar la padre sin buscar.

---

## Como se ve a escala

Antes, el inventario se veia asi — 80 clases, sin estructura visible:

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

Despues, el mismo inventario ordenado por tipo revela la arquitectura inmediatamente:

```
── EXT (31) ──────────────────────────────────
ZXX_C_EXT_TX01_VALIDATION
ZXX_C_EXT_TX01_TO_SYSTEM_A
ZXX_C_EXT_TX01_FOR_SYSTEM_B
ZXX_C_EXT_TX02_TO_SYSTEM_C
ZXX_C_EXT_FORMS               ← padre
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

La arquitectura es legible sin abrir una sola clase.

---

## El test que uso para nuevas clases

Antes de nombrar una nueva clase, respondo tres preguntas:

1. **A que reacciona?** A un evento de transaccion SAP, una llamada HTTP, un IDoc, una llamada de metodo directo desde otra clase?

2. **Que sabe?** El dominio funcional, la capa de transporte, el contrato de integracion, o solo utilidades tecnicas?

3. **Que produce?** Un efecto secundario en una entidad SAP, una llamada saliente, un documento, un calculo reutilizable?

Las respuestas mapean directamente a la taxonomia. Si las respuestas abarcan multiples tipos — dominio funcional *y* transporte HTTP — esa es una senal de que la clase hace demasiado, no una senal de que crear un tipo nuevo.

---

## Nota final

Esta convencion no vino de una sesion de pizarra. Vino de mirar un sistema real, encontrar inconsistencias y preguntar por que cada una existia.

La taxonomia tiene siete tipos. Eso es suficiente para cubrir cada clase en un modulo SAP PM grande sin ambiguedad. Si una nueva clase no encaja, la pregunta correcta es si la clase esta bien scoped — no si la taxonomia necesita un tipo nuevo.

La arquitectura es solo tan visible como los nombres que le das.
