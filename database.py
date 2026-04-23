"""
database.py — Capa de acceso a Supabase
Maneja guardado, deduplicación y consultas de reseñas.
"""
import logging
from datetime import datetime, timezone

from supabase import create_client, Client

from config import config

logger = logging.getLogger(__name__)


class Database:
    """Gestiona todas las operaciones con la tabla 'reviews' en Supabase."""

    def __init__(self):
        self.client: Client = create_client(config.supabase_url, config.supabase_key)
        logger.info("Conexión a Supabase establecida.")

    # ------------------------------------------------------------------
    # Deduplicación
    # ------------------------------------------------------------------

    def filter_new_reviews(self, reviews: list[dict], location_id: str) -> list[dict]:
        """
        Recibe la lista completa de reseñas de GBP y devuelve solo
        las que aún no están en la base de datos.
        Usa review_id (el ID único que asigna Google) para deduplicar.
        """
        if not reviews:
            return []

        incoming_ids = [r["reviewId"] for r in reviews]

        # Consulta por lotes de hasta 200 IDs para no exceder límites de URL
        existing_ids: set[str] = set()
        batch_size = 200
        for i in range(0, len(incoming_ids), batch_size):
            batch = incoming_ids[i:i + batch_size]
            response = (
                self.client.table("reviews")
                .select("review_id")
                .in_("review_id", batch)
                .execute()
            )
            existing_ids.update(row["review_id"] for row in response.data)

        new_reviews = [r for r in reviews if r["reviewId"] not in existing_ids]
        logger.info(f"  {len(new_reviews)} nuevas de {len(reviews)} totales en GBP")
        return new_reviews

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def save_review(self, review: dict, analysis: dict, location: dict) -> bool:
        """
        Guarda una reseña con su análisis IA en Supabase.
        Retorna True si se guardó correctamente, False si hubo error.
        """
        data = {
            # Identidad
            "review_id":    review["reviewId"],
            "property":     location["property"],
            "location_id":  location["location_id"],

            # Datos de la reseña
            "author_name":  review.get("reviewer", {}).get("displayName", "Anónimo"),
            "star_rating":  review.get("starRatingInt", 0),
            "review_text":  review.get("comment", ""),
            "review_reply": review.get("reviewReply", {}).get("comment") if review.get("reviewReply") else None,
            "create_time":  review.get("createTime"),
            "update_time":  review.get("updateTime"),

            # Análisis IA
            "sentiment":        analysis.get("sentimiento"),
            "topics":           analysis.get("temas", []),
            "urgency":          analysis.get("urgencia"),
            "urgency_reason":   analysis.get("razon_urgencia"),
            "staff_mentioned":  analysis.get("staff_mencionado", []),
            "main_complaint":   analysis.get("queja_principal"),
            "main_praise":      analysis.get("elogio_principal"),
            "response_draft":   analysis.get("borrador_respuesta"),
            "requires_action":  analysis.get("requiere_accion", False),
            "analyzed_at":      datetime.now(timezone.utc).isoformat(),

            # Control
            "alert_sent": False,
        }

        try:
            self.client.table("reviews").insert(data).execute()
            prop = location["property"].upper()
            stars = "⭐" * review.get("starRatingInt", 0)
            logger.info(f"  ✅ [{prop}] Guardada: {stars} — {data['author_name']}")
            return True
        except Exception as e:
            logger.error(f"  ❌ Error guardando reseña {review['reviewId']}: {e}")
            return False

    def mark_alert_sent(self, review_id: str) -> None:
        """Marca una reseña como alertada para no enviar duplicados."""
        try:
            self.client.table("reviews") \
                .update({"alert_sent": True}) \
                .eq("review_id", review_id) \
                .execute()
        except Exception as e:
            logger.error(f"Error marcando alerta enviada para {review_id}: {e}")

    # ------------------------------------------------------------------
    # Lectura (para scripts auxiliares)
    # ------------------------------------------------------------------

    def get_recent_reviews(self, limit: int = 20, property_filter: str | None = None) -> list[dict]:
        """Obtiene las reseñas más recientes. Útil para testing."""
        query = self.client.table("reviews").select("*").order("create_time", desc=True).limit(limit)
        if property_filter:
            query = query.eq("property", property_filter)
        return query.execute().data
