-- ============================================================
-- SCHEMA: Sistema de Reseñas Miramelindo
-- Base de datos: Supabase (PostgreSQL)
-- Ejecutar en: Supabase Dashboard → SQL Editor
-- ============================================================

-- Tabla principal de reseñas
CREATE TABLE IF NOT EXISTS reviews (
  -- Identidad
  id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  review_id       TEXT        UNIQUE NOT NULL,           -- ID único de Google
  property        TEXT        NOT NULL,                  -- 'hotel' | 'glamping' | 'cabanas' | 'restaurante'
  location_id     TEXT        NOT NULL,                  -- accounts/X/locations/Y

  -- Datos de la reseña
  author_name     TEXT,
  star_rating     INTEGER     CHECK (star_rating BETWEEN 1 AND 5),
  review_text     TEXT,
  review_reply    TEXT,                                  -- Respuesta publicada (si existe)
  create_time     TIMESTAMPTZ,
  update_time     TIMESTAMPTZ,

  -- Análisis IA (Gemini)
  sentiment       TEXT        CHECK (sentiment IN ('positivo', 'neutro', 'negativo')),
  topics          TEXT[]      DEFAULT '{}',              -- ['limpieza', 'servicio', ...]
  urgency         TEXT        CHECK (urgency IN ('alta', 'media', 'baja')),
  urgency_reason  TEXT,
  staff_mentioned TEXT[]      DEFAULT '{}',
  main_complaint  TEXT,
  main_praise     TEXT,
  response_draft  TEXT,                                  -- Borrador de respuesta generado por IA
  requires_action BOOLEAN     DEFAULT FALSE,
  analyzed_at     TIMESTAMPTZ DEFAULT NOW(),

  -- Control del sistema
  alert_sent      BOOLEAN     DEFAULT FALSE,
  synced_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES para filtros del dashboard
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_reviews_property     ON reviews(property);
CREATE INDEX IF NOT EXISTS idx_reviews_star_rating  ON reviews(star_rating);
CREATE INDEX IF NOT EXISTS idx_reviews_create_time  ON reviews(create_time DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_sentiment    ON reviews(sentiment);
CREATE INDEX IF NOT EXISTS idx_reviews_urgency      ON reviews(urgency);
CREATE INDEX IF NOT EXISTS idx_reviews_alert_sent   ON reviews(alert_sent) WHERE alert_sent = FALSE;
CREATE INDEX IF NOT EXISTS idx_reviews_requires_action ON reviews(requires_action) WHERE requires_action = TRUE;

-- ============================================================
-- VISTA: Dashboard resumen por propiedad
-- Útil para conectar con Looker Studio o hacer queries rápidas
-- ============================================================
CREATE OR REPLACE VIEW v_dashboard_summary AS
SELECT
  property,
  COUNT(*)                                              AS total_reviews,
  ROUND(AVG(star_rating), 2)                           AS avg_rating,
  COUNT(*) FILTER (WHERE sentiment = 'positivo')       AS positivas,
  COUNT(*) FILTER (WHERE sentiment = 'neutro')         AS neutras,
  COUNT(*) FILTER (WHERE sentiment = 'negativo')       AS negativas,
  COUNT(*) FILTER (WHERE star_rating <= 3)             AS criticas,
  COUNT(*) FILTER (WHERE urgency = 'alta')             AS urgentes,
  COUNT(*) FILTER (WHERE requires_action = TRUE
                   AND review_reply IS NULL)            AS sin_respuesta,
  MAX(create_time)                                     AS ultima_resena
FROM reviews
GROUP BY property
ORDER BY property;

-- ============================================================
-- VISTA: Reseñas pendientes de respuesta
-- ============================================================
CREATE OR REPLACE VIEW v_pending_response AS
SELECT
  id,
  property,
  author_name,
  star_rating,
  review_text,
  sentiment,
  urgency,
  topics,
  staff_mentioned,
  response_draft,
  create_time
FROM reviews
WHERE review_reply IS NULL
  AND star_rating <= 4
ORDER BY urgency DESC, star_rating ASC, create_time DESC;

-- ============================================================
-- VISTA: Últimas 30 reseñas (para feed del dashboard)
-- ============================================================
CREATE OR REPLACE VIEW v_recent_reviews AS
SELECT
  id,
  property,
  author_name,
  star_rating,
  LEFT(review_text, 200) AS review_preview,
  sentiment,
  urgency,
  topics,
  staff_mentioned,
  response_draft,
  create_time,
  alert_sent
FROM reviews
ORDER BY create_time DESC;

-- ============================================================
-- ROW LEVEL SECURITY (opcional pero recomendado)
-- Descomentar si usas Supabase Auth en el dashboard
-- ============================================================
-- ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Solo lectura autenticada" ON reviews
--   FOR SELECT USING (auth.role() = 'authenticated');
