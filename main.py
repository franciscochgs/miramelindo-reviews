"""
main.py — Orquestador principal del sistema de reseñas Miramelindo
Ejecutado por GitHub Actions cada 2 horas.

Flujo:
  1. Para cada propiedad, obtiene reseñas de GBP API
  2. Filtra solo las nuevas (no guardadas aún)
  3. Analiza cada nueva reseña con Gemini
  4. Guarda en Supabase
  5. Envía alerta si es negativa o urgente
"""
import logging
import sys
from datetime import datetime, timezone

from config import config
from gbp_client import GBPClient
from analyzer import ReviewAnalyzer
from database import Database
from alerts import AlertSystem

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run():
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("INICIO — Sistema de Reseñas Miramelindo")
    logger.info(f"Timestamp: {start_time.isoformat()}")
    logger.info(f"Propiedades a procesar: {len(config.locations)}")
    logger.info("=" * 60)

    # Inicializar componentes
    try:
        gbp = GBPClient()
        logger.info("GBPClient OK")
    except Exception as e:
        logger.error(f"Error en GBPClient: {e}", exc_info=True)
        sys.exit(1)

    try:
        db = Database()
        logger.info("Database OK")
    except Exception as e:
        logger.error(f"Error en Database: {e}", exc_info=True)
        sys.exit(1)

    try:
        alerts = AlertSystem()
        logger.info("AlertSystem OK")
    except Exception as e:
        logger.error(f"Error en AlertSystem: {e}", exc_info=True)
        sys.exit(1)

    try:
        analyzer = ReviewAnalyzer()
    except Exception as e:
        logger.warning(f"Gemini no disponible ({e}). Usando análisis básico por estrellas.")
        analyzer = None

    total_new      = 0
    total_alerts   = 0
    errors_by_prop = {}

    # ------------------------------------------------------------------
    # Procesar cada propiedad
    # ------------------------------------------------------------------
    for location in config.locations:
        prop_name    = location["name"]
        prop_key     = location["property"]
        location_id  = location["location_id"]

        logger.info(f"\n{'─' * 40}")
        logger.info(f"Propiedad: {prop_name} ({prop_key})")

        try:
            # 1. Obtener todas las reseñas de GBP
            all_reviews = gbp.get_reviews(location_id=location_id)

            # 2. Filtrar solo las nuevas
            new_reviews = db.filter_new_reviews(all_reviews, location_id)

            if not new_reviews:
                logger.info("  Sin reseñas nuevas — nada que procesar.")
                continue

            # 3. Procesar cada reseña nueva
            for review in new_reviews:
                review_id = review["reviewId"]
                stars     = review.get("starRatingInt", 0)
                author    = review.get("reviewer", {}).get("displayName", "Anónimo")

                logger.info(f"\n  Procesando: {author} — {'⭐' * stars}")

                # Analizar con Gemini
                analysis = analyzer.analyze(review, prop_name) if analyzer else {}

                # Guardar en Supabase
                saved = db.save_review(review, analysis, location)

                if saved:
                    total_new += 1

                    # Alertar si corresponde
                    if alerts.should_alert(review, analysis):
                        sent = alerts.send_alert(review, analysis, prop_key)
                        if sent:
                            db.mark_alert_sent(review_id)
                            total_alerts += 1

        except Exception as e:
            logger.error(f"  ❌ Error procesando {prop_name}: {e}", exc_info=True)
            errors_by_prop[prop_name] = str(e)
            continue

    # ------------------------------------------------------------------
    # Resumen final
    # ------------------------------------------------------------------
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info(f"\n{'=' * 60}")
    logger.info("RESUMEN DE EJECUCIÓN")
    logger.info(f"  ✅ Reseñas nuevas procesadas : {total_new}")
    logger.info(f"  📧 Alertas enviadas          : {total_alerts}")
    logger.info(f"  ❌ Propiedades con error     : {len(errors_by_prop)}")
    logger.info(f"  ⏱️  Tiempo total              : {elapsed:.1f}s")
    if errors_by_prop:
        for prop, err in errors_by_prop.items():
            logger.error(f"  Error en '{prop}': {err}")
    logger.info("=" * 60)

    # Salir con código de error si hubo fallos (útil para monitoreo de CI)
    if errors_by_prop:
        sys.exit(1)


if __name__ == "__main__":
    run()
