"""
alerts.py — Sistema de alertas por email (Resend)
Se dispara cuando entra una reseña ≤3 estrellas o urgencia alta.
"""
import logging
import resend

from config import config

logger = logging.getLogger(__name__)

STAR_EMOJI = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}

PROPERTY_LABEL = {
    "hotel":       "Hotel Spa Miramelindo",
    "glamping":    "Glamping Miramelindo",
    "cabanas":     "Cabañas del Río",
    "restaurante": "Restaurante Miramelindo",
}


class AlertSystem:
    """Envía alertas por email usando Resend."""

    def __init__(self):
        if config.resend_api_key:
            resend.api_key = config.resend_api_key
        else:
            logger.warning("RESEND_API_KEY no configurado — alertas desactivadas.")

    def should_alert(self, review: dict, analysis: dict) -> bool:
        """Determina si una reseña amerita una alerta."""
        stars   = review.get("starRatingInt", 5)
        urgency = analysis.get("urgencia", "baja")
        return stars <= config.alert_threshold or urgency == "alta"

    def send_alert(self, review: dict, analysis: dict, property_key: str) -> bool:
        """
        Envía alerta por email.
        Retorna True si se envió, False si no (config faltante o error).
        """
        if not config.resend_api_key or not config.alert_email_to:
            logger.info("  Alertas no configuradas, omitiendo.")
            return False

        stars        = review.get("starRatingInt", 0)
        author       = review.get("reviewer", {}).get("displayName", "Anónimo")
        review_text  = review.get("comment", "(Sin texto)")
        urgency      = analysis.get("urgencia", "baja")
        topics       = ", ".join(analysis.get("temas", [])) or "—"
        staff        = ", ".join(analysis.get("staff_mencionado", [])) or "—"
        complaint    = analysis.get("queja_principal") or "—"
        draft        = analysis.get("borrador_respuesta") or ""
        prop_label   = PROPERTY_LABEL.get(property_key, property_key)

        is_urgent    = urgency == "alta"
        header_color = "#dc2626" if is_urgent else "#f59e0b"
        header_label = "🚨 URGENTE" if is_urgent else "⚠️ Reseña Negativa"
        subject      = f"{header_label} — {prop_label} — {STAR_EMOJI.get(stars, '')} {stars}/5"

        html = f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:20px;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">

    <!-- Header -->
    <div style="background:{header_color};padding:20px 24px;">
      <h1 style="margin:0;color:#fff;font-size:20px;">{header_label} en {prop_label}</h1>
    </div>

    <!-- Body -->
    <div style="padding:24px;">

      <!-- Datos básicos -->
      <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
        <tr>
          <td style="padding:8px 12px;background:#f3f4f6;border-radius:6px;width:40%;font-weight:bold;color:#374151;">Autor</td>
          <td style="padding:8px 12px;">{author}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;background:#f3f4f6;border-radius:6px;font-weight:bold;color:#374151;">Calificación</td>
          <td style="padding:8px 12px;">{STAR_EMOJI.get(stars, '')} {stars}/5</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;background:#f3f4f6;border-radius:6px;font-weight:bold;color:#374151;">Urgencia</td>
          <td style="padding:8px 12px;color:{header_color};font-weight:bold;">{urgency.upper()}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;background:#f3f4f6;border-radius:6px;font-weight:bold;color:#374151;">Temas</td>
          <td style="padding:8px 12px;">{topics}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;background:#f3f4f6;border-radius:6px;font-weight:bold;color:#374151;">Staff mencionado</td>
          <td style="padding:8px 12px;">{staff}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;background:#f3f4f6;border-radius:6px;font-weight:bold;color:#374151;">Queja principal</td>
          <td style="padding:8px 12px;">{complaint}</td>
        </tr>
      </table>

      <!-- Texto de la reseña -->
      <div style="background:#fef9c3;border-left:4px solid #f59e0b;padding:14px 16px;border-radius:0 6px 6px 0;margin-bottom:20px;">
        <p style="margin:0 0 6px;font-weight:bold;color:#92400e;">📝 Reseña completa:</p>
        <p style="margin:0;color:#374151;font-style:italic;">"{review_text}"</p>
      </div>

      <!-- Borrador de respuesta -->
      <div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:14px 16px;border-radius:0 6px 6px 0;margin-bottom:20px;">
        <p style="margin:0 0 6px;font-weight:bold;color:#1e40af;">💬 Borrador de respuesta sugerido:</p>
        <p style="margin:0;color:#374151;">{draft}</p>
      </div>

      <!-- Footer -->
      <p style="color:#9ca3af;font-size:12px;border-top:1px solid #e5e7eb;padding-top:12px;">
        Sistema automático de monitoreo de reseñas — Miramelindo<br>
        Este mensaje se generó automáticamente. El borrador de respuesta debe ser revisado antes de publicarse.
      </p>
    </div>
  </div>
</body>
</html>
"""

        try:
            resend.Emails.send({
                "from":    config.alert_email_from,
                "to":      [config.alert_email_to],
                "subject": subject,
                "html":    html,
            })
            logger.info(f"  📧 Alerta enviada → {config.alert_email_to}")
            return True
        except Exception as e:
            logger.error(f"  ❌ Error enviando alerta por email: {e}")
            return False
