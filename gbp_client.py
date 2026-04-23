"""
gbp_client.py — Cliente para Google Business Profile API
Maneja OAuth 2.0, renovación automática de tokens y paginación.
"""
import time
import logging
import requests

from config import config

logger = logging.getLogger(__name__)

# Google representa las estrellas como strings, no números
STAR_RATING_MAP = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5
}

TOKEN_URL = "https://oauth2.googleapis.com/token"
GBP_BASE  = "https://mybusiness.googleapis.com/v4"


class GBPClient:
    """
    Cliente para Google Business Profile API v4.
    Obtiene un access_token al instanciarse y lo renueva automáticamente
    cuando recibe un 401.
    """

    def __init__(self):
        self._access_token: str = ""
        self._token_expires_at: float = 0
        self._refresh_access_token()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _refresh_access_token(self) -> None:
        """Intercambia el refresh_token por un nuevo access_token."""
        logger.info("Renovando access token de Google...")
        response = requests.post(TOKEN_URL, data={
            "client_id":     config.google_client_id,
            "client_secret": config.google_client_secret,
            "refresh_token": config.google_refresh_token,
            "grant_type":    "refresh_token",
        }, timeout=10)

        if response.status_code != 200:
            raise RuntimeError(
                f"Error renovando token: {response.status_code} — {response.text}"
            )

        data = response.json()
        self._access_token    = data["access_token"]
        # El token dura 3600 seg; renovamos 5 min antes de expirar
        self._token_expires_at = time.time() + data.get("expires_in", 3600) - 300
        logger.info("Access token renovado correctamente.")

    def _headers(self) -> dict:
        if time.time() >= self._token_expires_at:
            self._refresh_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def get_reviews(self, location_id: str) -> list[dict]:
        """
        Obtiene TODAS las reseñas de una ubicación con paginación automática.

        Args:
            location_id: Ruta completa, ej. "accounts/1234567890/locations/9876543210"

        Returns:
            Lista de reseñas normalizadas con starRatingInt como número entero.
        """
        url        = f"{GBP_BASE}/{location_id}/reviews"
        all_reviews: list[dict] = []
        page_token: str | None  = None
        page_num   = 0

        while True:
            page_num += 1
            params: dict = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token

            response = self._get_with_retry(url, params)
            data     = response.json()

            reviews = data.get("reviews", [])
            for review in reviews:
                # Normalizar rating a entero
                raw = review.get("starRating", "ONE")
                review["starRatingInt"] = STAR_RATING_MAP.get(raw, 1)

            all_reviews.extend(reviews)
            logger.info(f"  Página {page_num}: {len(reviews)} reseñas obtenidas")

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Total obtenidas: {len(all_reviews)} reseñas")
        return all_reviews

    def _get_with_retry(self, url: str, params: dict, max_retries: int = 3) -> requests.Response:
        """GET con reintentos automáticos ante 401 (token expirado) y 429 (cuota)."""
        for attempt in range(1, max_retries + 1):
            response = requests.get(url, headers=self._headers(), params=params, timeout=15)

            if response.status_code == 200:
                return response

            if response.status_code == 401:
                logger.warning(f"Token expirado (intento {attempt}), renovando...")
                self._refresh_access_token()
                continue

            if response.status_code == 429:
                wait = 2 ** attempt  # Backoff exponencial: 2s, 4s, 8s
                logger.warning(f"Cuota excedida. Esperando {wait}s antes de reintentar...")
                time.sleep(wait)
                continue

            # Error no recuperable
            response.raise_for_status()

        raise RuntimeError(f"Fallo tras {max_retries} intentos en {url}")
