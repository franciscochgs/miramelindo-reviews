"""
analyzer.py — Análisis de reseñas con Gemini
Envía cada reseña al LLM y devuelve un JSON estructurado.
"""
import json
import logging

import google.generativeai as genai

from config import config

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Prompt de análisis — tono y contexto Miramelindo
# ------------------------------------------------------------------
ANALYSIS_PROMPT = """\
Eres el asistente de reputación de Miramelindo, un resort tropical \
en Costa Rica que incluye Hotel Spa, Glamping, Cabañas del Río y Restaurante. \
El tono de la marca es: cálido, profesional, cercano, orgulloso de la \
naturaleza costarricense y del servicio personalizado.

Analiza la siguiente reseña de Google y responde ÚNICAMENTE con un objeto \
JSON válido (sin bloques de código markdown, sin texto adicional).

--- DATOS DE LA RESEÑA ---
Propiedad : {property_name}
Autor      : {author_name}
Estrellas  : {stars} / 5
Reseña     : "{review_text}"
--------------------------

Devuelve EXACTAMENTE este esquema (sin campos extra):
{{
  "sentimiento": "positivo" | "neutro" | "negativo",
  "temas": ["array de temas detectados — posibles valores: limpieza, servicio, \
comida, instalaciones, precio, ubicación, personal, check-in, check-out, \
spa, piscina, habitación, desayuno, naturaleza, ruido, wifi, estacionamiento"],
  "urgencia": "alta" | "media" | "baja",
  "razon_urgencia": "string o null — explica brevemente si urgencia es alta",
  "staff_mencionado": ["nombres del personal mencionados — lista vacía si ninguno"],
  "queja_principal": "descripción de la queja más importante o null",
  "elogio_principal": "descripción del elogio más importante o null",
  "borrador_respuesta": "Respuesta en español, cálida y profesional, \
de 2-3 oraciones. Si es negativa: reconoce el problema sin excusas y ofrece \
solución o invitación a comunicarse directamente. Si es positiva: agradece \
con calidez y menciona algo específico de la reseña. Firma siempre como \
'El equipo de Miramelindo'.",
  "requiere_accion": true | false
}}

Criterios de urgencia ALTA (cualquiera de los siguientes):
- Problemas de salud, seguridad o higiene graves
- Mención de plagas o fauna nociva
- Acusaciones de fraude o cobros incorrectos
- Experiencia completamente negativa con detalles severos y específicos
- Amenaza de denuncia pública o legal\
"""


class ReviewAnalyzer:
    """Analiza reseñas usando Gemini y devuelve JSON estructurado."""

    def __init__(self):
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel(config.gemini_model)

    def analyze(self, review: dict, property_name: str) -> dict:
        """
        Analiza una reseña y devuelve el análisis estructurado.
        Si Gemini falla, devuelve un análisis de fallback basado solo en estrellas.
        """
        review_text = review.get("comment", "").strip()
        author_name = review.get("reviewer", {}).get("displayName", "Anónimo")
        stars       = review.get("starRatingInt", 3)

        # Si la reseña no tiene texto, análisis básico por estrellas
        if not review_text:
            logger.info("  Reseña sin texto — usando análisis por estrellas")
            return self._star_only_analysis(stars)

        prompt = ANALYSIS_PROMPT.format(
            property_name=property_name,
            author_name=author_name,
            stars=stars,
            review_text=review_text[:2000],  # Cap de seguridad de tokens
        )

        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()

            # Limpiar si Gemini añadió bloques ```json ... ```
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        raw = part
                        break

            result = json.loads(raw)
            logger.info(f"  Análisis OK — sentimiento: {result.get('sentimiento')} | urgencia: {result.get('urgencia')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"  Error parseando JSON de Gemini: {e}\n  Respuesta raw: {raw[:300]}")
            return self._star_only_analysis(stars)

        except Exception as e:
            logger.error(f"  Error en Gemini: {e}")
            return self._star_only_analysis(stars)

    @staticmethod
    def _star_only_analysis(stars: int) -> dict:
        """Análisis de fallback cuando no hay texto o Gemini falla."""
        if stars >= 4:
            sentiment, urgency = "positivo", "baja"
        elif stars == 3:
            sentiment, urgency = "neutro", "media"
        else:
            sentiment, urgency = "negativo", "alta" if stars == 1 else "media"

        return {
            "sentimiento":      sentiment,
            "temas":            [],
            "urgencia":         urgency,
            "razon_urgencia":   None,
            "staff_mencionado": [],
            "queja_principal":  None,
            "elogio_principal": None,
            "borrador_respuesta": (
                "Gracias por su visita a Miramelindo. "
                "El equipo de Miramelindo"
                if stars >= 4 else
                "Lamentamos que su experiencia no haya sido la esperada. "
                "Le invitamos a contactarnos directamente para atender su caso. "
                "El equipo de Miramelindo"
            ),
            "requiere_accion":  stars <= 3,
        }
