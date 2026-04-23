"""
config.py — Configuración centralizada
Lee todas las variables de entorno del sistema.
En GitHub Actions estas vienen de los Secrets del repositorio.
"""
import os
import json


class Config:
    def __init__(self):
        # Google OAuth
        self.google_client_id     = self._require("GOOGLE_CLIENT_ID")
        self.google_client_secret = self._require("GOOGLE_CLIENT_SECRET")
        self.google_refresh_token = self._require("GOOGLE_REFRESH_TOKEN")

        # Google Business Profile
        self.gbp_account_id = self._require("GBP_ACCOUNT_ID")
        # Formato JSON: [{"name":"Hotel Spa","property":"hotel","location_id":"accounts/X/locations/Y"}, ...]
        self.locations = json.loads(self._require("GBP_LOCATIONS"))

        # IA
        self.gemini_api_key = self._require("GEMINI_API_KEY")
        self.gemini_model   = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

        # Base de datos
        self.supabase_url = self._require("SUPABASE_URL")
        self.supabase_key = self._require("SUPABASE_KEY")  # service_role key

        # Alertas (opcionales — el sistema funciona sin ellas)
        self.resend_api_key  = os.environ.get("RESEND_API_KEY", "")
        self.alert_email_to  = os.environ.get("ALERT_EMAIL_TO", "")
        self.alert_email_from = os.environ.get("ALERT_EMAIL_FROM", "alertas@miramelindo.com")

        # Comportamiento
        # Reseñas con esta cantidad de estrellas o menos disparan alerta
        self.alert_threshold = int(os.environ.get("ALERT_STAR_THRESHOLD", "3"))

    @staticmethod
    def _require(key: str) -> str:
        value = os.environ.get(key)
        if not value:
            raise EnvironmentError(
                f"Variable de entorno requerida no encontrada: {key}\n"
                f"Asegúrate de configurarla en GitHub Secrets o en tu .env local."
            )
        return value


# Instancia global — importar desde otros módulos con: from config import config
config = Config()
