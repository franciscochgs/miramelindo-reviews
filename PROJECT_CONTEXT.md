# PROJECT_CONTEXT — miramelindo-reviews

> Sistema automatizado de monitoreo de reseñas de Google Business Profile
> para las propiedades de Miramelindo en Baños de Agua Santa, Ecuador.

---

## ROL

Eres mi asistente técnico y socio estratégico para este proyecto. 
Sé directo, anticipa problemas, dame pasos concretos, y dime si algo no tiene sentido.

---

## QUÉ HACE EL SISTEMA

1. Cada 2 horas (GitHub Actions, CRON DESACTIVADO temporalmente) obtiene reseñas nuevas de GBP API
2. Filtra reseñas no procesadas (deduplicación vía Supabase + UNIQUE constraint en review_id)
3. Analiza cada reseña con Gemini (sentimiento, temas, urgencia, borrador de respuesta)
4. Guarda resultado en Supabase (PostgreSQL)
5. Envía alerta email vía Resend si reseña ≤3 estrellas o urgencia alta

**Propiedades monitoreadas (3, no 4):**

| Nombre | property | account_id | location_id (FID, no de API) |
|---|---|---|---|
| Hotel Spa Miramelindo | hotel | 1040529650473468362 | 4534516120926464453 |
| Hotel De Mi Pueblo | hotel_pueblo | 668681559579858968 | 4606808945732175508 |
| Restaurante Miramelindo | restaurante | 3154054069811734812 | 5079756601528139365 |

**Glamping Miramelindo se DESCARTÓ del scope.**

⚠️ Los `location_id` en la tabla son los FID del panel web (URL `business.google.com/n/{account}/profile?fid={location}`). **NO son los `location_id` reales de la API.** Pendiente: descubrir los reales cuando Google apruebe la cuota.

---

## REPOSITORIO

- **GitHub:** `https://github.com/franciscochgs/miramelindo-reviews`
- **Rama principal:** `main`
- **Estructura REAL (todos los .py en la raíz, NO en subcarpetas):**
miramelindo-reviews/
├── .github/workflows/
│   └── review_sync.yml          # Workflow principal (cron desactivado temporalmente)
├── main.py                       # Orquestador
├── config.py                     # Vars de entorno
├── gbp_client.py                 # Cliente GBP (URL: mybusiness.googleapis.com/v4)
├── analyzer.py                   # Análisis con Gemini (google-genai)
├── database.py                   # Cliente Supabase
├── alerts.py                     # Alertas email vía Resend
├── oauth_setup.py                # Genera GOOGLE_REFRESH_TOKEN (correr 1 vez)
├── get_location_ids.py           # Descubre IDs GBP (bloqueado por cuota actualmente)
├── requirements.txt
├── schema.sql
└── PROJECT_CONTEXT.md            # Este archivo

---

## DEPENDENCIAS (requirements.txt PINEADO)

Versiones pineadas para evitar backtracking infinito de pip:
google-auth==2.29.0
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0
requests==2.31.0
google-genai==0.3.0
supabase==2.9.1
websockets>=13.0,<15.0
resend==2.1.0

⚠️ NO usar `google-generativeai` (deprecated). El paquete correcto es `google-genai`.

---

## VARIABLES DE ENTORNO (GitHub Secrets)

| Secret | Estado | Notas |
|---|---|---|
| GOOGLE_CLIENT_ID | ✅ Configurado | OAuth2 client ID |
| GOOGLE_CLIENT_SECRET | ✅ Configurado | OAuth2 client secret |
| GOOGLE_REFRESH_TOKEN | ✅ Configurado | Token de larga duración |
| GBP_LOCATIONS | ⚠️ Con FIDs (no location_ids reales) | Ver tabla de propiedades arriba |
| GEMINI_API_KEY | ✅ Configurado | API key de Google AI Studio |
| SUPABASE_URL | ✅ Configurado | URL del proyecto Supabase |
| SUPABASE_KEY | ✅ Configurado | service_role key (NO anon) |
| RESEND_API_KEY | ✅ Configurado | API key de Resend |
| ALERT_EMAIL_TO | ✅ Configurado | Destinatario de alertas |

---

## ESTADO ACTUAL — Bloqueador principal

🚫 **El sistema NO está en producción.**

**Bloqueador:** Google Business Profile API tiene **cuota = 0** en "Requests per minute" para estas APIs:
- `mybusinessaccountmanagement.googleapis.com` (cuota 0/min)
- `mybusinessbusinessinformation.googleapis.com` (cuota 0/min en per-minute, daily quotas OK)

Esto impide listar las cuentas y ubicaciones de GBP para obtener los `location_id` REALES de la API (los FIDs del panel NO sirven — son distintos).

**Aprobación previa:** El proyecto SÍ está aprobado para el programa GBP API (correo del 11 de mayo de 2026, caso `0-5108000041368`). Pero la cuota per-minute requiere solicitud adicional separada.

**Acción pendiente:** Solicitud de aumento de cuota enviada el 12 de mayo de 2026 — esperando respuesta de Google.

**Cuota actual de Google My Business API (mybusiness.googleapis.com v4):** ✅ Activa
- Requests per minute: 600
- Requests per day: 250,000
- V4 General Requests per minute: 3,000

Esta API SÍ funciona, pero necesitamos los `location_id` reales primero.

---

## SCHEMA DE SUPABASE (tabla `reviews`)

**Columnas reales (no las del schema.sql original):**

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| id | uuid | NO | gen_random_uuid() |
| review_id | text | NO | — |
| property | text | NO | — |
| location_id | text | NO | — |
| author_name | text | YES | — |
| star_rating | integer | YES | — |
| review_text | text | YES | — |
| review_reply | text | YES | — |
| create_time | timestamptz | YES | — |
| update_time | timestamptz | YES | — |
| sentiment | text | YES | — |
| topics | text[] | YES | '{}' |
| urgency | text | YES | — |
| urgency_reason | text | YES | — |
| staff_mentioned | text[] | YES | '{}' |
| main_complaint | text | YES | — |
| main_praise | text | YES | — |
| response_draft | text | YES | — |
| requires_action | boolean | YES | false |
| analyzed_at | timestamptz | YES | now() |
| alert_sent | boolean | YES | false |
| synced_at | timestamptz | YES | now() |

**Constraints:**
- `reviews_pkey` (PRIMARY KEY)
- `reviews_review_id_key` (UNIQUE en review_id — protege contra duplicados)
- `reviews_sentiment_check` (CHECK valores válidos en sentiment)
- `reviews_star_rating_check` (CHECK valores válidos en star_rating)
- `reviews_urgency_check` (CHECK valores válidos en urgency)

**Vistas disponibles:**
- `v_dashboard_summary` — resumen para dashboard
- `v_pending_response` — reseñas pendientes de respuesta
- `v_recent_reviews` — reseñas recientes

---

## URLS DE GOOGLE — qué funciona y qué no

### ✅ Funciona (a usar)

| URL | Estado | Cuota |
|---|---|---|
| `https://mybusiness.googleapis.com/v4/{location_id}/reviews` | ✅ Activa | 600 req/min |
| `https://oauth2.googleapis.com/token` | ✅ Activa | N/A |

### ❌ No funciona

| URL | Estado | Razón |
|---|---|---|
| `https://mybusinessreviews.googleapis.com/v1/*` | ❌ No existe | API inexistente (estaba en el código original — error) |
| `https://mybusiness.googleapis.com/v4/accounts` (sin más) | ❌ 404 | Endpoint migrado a la API nueva |
| `https://mybusinessaccountmanagement.googleapis.com/v1/accounts` | 🚫 429 (cuota 0) | Esperando aprobación |
| `https://mybusinessbusinessinformation.googleapis.com/v1/{X}/locations` | 🚫 429 (cuota 0) | Esperando aprobación |

---

## BUGS Y FIXES HISTÓRICOS

### Fix 1: URL incorrecta en gbp_client.py
- ❌ Era: `https://mybusinessreviews.googleapis.com/v1` (API que no existe)
- ✅ Ahora: `https://mybusiness.googleapis.com/v4` (oficial según docs de Google)

### Fix 2: Conflicto de websockets
- supabase==2.4.6 trae realtime que requiere websockets<13
- google-genai>=0.3.0 requiere websockets>=13
- Solución: subir supabase a 2.9.1 (usa realtime 2.x compatible)

### Fix 3: Paquete Gemini deprecated
- ❌ Era: `google-generativeai` (deprecated)
- ✅ Ahora: `google-genai` (oficial)

### Fix 4: Supabase keys
- La `anon` key no tiene permisos para INSERT por RLS
- Siempre usar `service_role` key

### Fix 5: PROJECT_CONTEXT.md desactualizado
- El original decía que la estructura era `src/` y `scripts/` (FALSO — todo es plano)
- Decía 4 propiedades incluyendo Cabañas del Río + Glamping (REAL: 3 propiedades, sin Cabañas, Glamping descartado)
- Schema de Supabase con nombres distintos a los reales (`author` vs `author_name`, etc)

---

## LO QUE VIENE DESPUÉS

### Cuando Google apruebe la cuota (próximo paso inmediato):

1. Restaurar el workflow `discover_locations.yml` para correr `get_location_ids.py`
2. Obtener los `location_id` reales de la API
3. Actualizar secret `GBP_LOCATIONS` con los IDs correctos
4. Re-habilitar el cron en `review_sync.yml`
5. Verificar primera ejecución exitosa
6. Validar inserciones en Supabase

### Backlog futuro:

- Dashboard en Looker Studio o Metabase conectado a Supabase
- Webhooks para reseñas en tiempo real (no cada 2h)
- Auto-publicación de respuestas (requiere aprobación manual primero)

---

## CÓMO AYUDARME

- Sé directo y crítico — si algo no tiene sentido, dilo
- Anticipa errores antes de gastar runs/cuotas
- Si das código, que esté listo para copiar/pegar
- Cuando reportes bugs, dime archivo y línea exacta
- Prioriza desbloquear producción sobre todo lo demás
