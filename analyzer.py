"""
analyzer.py — Análisis de reseñas con Gemini
Envía cada reseña al LLM y devuelve un JSON estructurado.
"""
import json
import logging

from google import genai
from google.genai import types # Importación añadida para configuración de tipos

from config import config

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Prompt de análisis — tono y contexto Miramelindo
# ------------------------------------------------------------------
ANALYSIS_PROMPT = """\
Eres el asistente de reputación de Miramelindo, un grupo de hospitalidad \
boutique y spa en Baños de Agua Santa, Ecuador, que incluye Hotel Spa, \
Glamping, Cabañas del Río y Restaurante. El tono de la marca es: cálido, \
profesional, directo y enfocado en ofrecer experiencias personalizadas.

Analiza la siguiente reseña de Google y responde ÚNICAMENTE con un objeto \
JSON válido que siga exactamente el esquema provisto.

--- DATOS DE LA RESEÑA ---
Propiedad : {property_name}
Autor      : {author_name}
Estrellas  : {stars} / 5
Reseña     : "{review_text}"
--------------------------

--- ESQUEMA JSON REQUERIDO ---
{{
  "sentimiento": "positivo",
  "temas": ["limpieza", "servicio"],
  "urgencia": "baja",
  "razon_urgencia": null,
  "staff_mencionado": [],
  "queja_principal": null,
  "elogio_principal": null,
  "borrador_respuesta": "Gracias por su visita.",
  "requiere_accion": false
}}

--- INSTRUCCIONES DE CAMPOS ---
- sentimiento: "positivo" | "neutro" | "negativo".
- temas: Array de strings. Posibles valores: limpieza, servicio, comida, instalaciones, precio, ubicación, personal, check-in, check-out, spa, piscina, habitación, desayuno, naturaleza, ruido, wifi, estacionamiento.
- urgencia: "alta" | "media" | "baja".
- razon_urgencia: string explicando si urgencia es alta, sino null.
- staff_mencionado: array con nombres del personal mencionados.
- queja_principal: descripción de la queja más importante o null.
- elogio_principal: descripción del elogio más importante o null.
- borrador_respuesta: Respuesta en español neutro, cálida y profesional, de 2-3 oraciones. Si es negativa: reconoce el problema sin excusas y ofrece solución o invitación a comunicarse directamente. Si es positiva: agradece con calidez y menciona algo específico. Firma siempre como 'El equipo de Miramelindo'.
- requiere_accion: true | false.

--- CRITERIOS DE URGENCIA ALTA ---
Cualquiera de los siguientes:
- Problemas de salud, seguridad o higiene graves.
- Mención de plagas o fauna nociva.
- Acusaciones de fraude o cobros incorrectos.
- Experiencia completamente negativa con detalles severos y específicos.
- Amenaza de denuncia pública o legal.\
"""


class ReviewAnalyzer:
    """Analiza reseñas usando Gemini y devuelve JSON estructurado."""

    def __init__(self):
        self.client = genai.Client(api_key=config.gemini_api_key)

    def analyze(self, review: dict, property_name: str) -> dict:
        """
        Analiza una reseña y devuelve el análisis estructurado.
        Si Gemini falla, devuelve un análisis de fallback basado solo en estrellas.
        """
        review_text = review.get("comment", "").strip()
        author_name = review.get("reviewer", {}).get("displayName", "Anónimo")
        stars       = review.get("starRatingInt", 3)

        if not review_text:
            logger.info("  Reseña sin texto — usando análisis por estrellas")
            return self._star_only_analysis(stars)

        prompt = ANALYSIS_PROMPT.format(
            property_name=property_name,
            author_name=author_name,
            stars=stars,
            review_text=review_text[:2000],
        )

        try:
            # Implementación de GenerateContentConfig para forzar salida JSON limpia
            response = self.client.models.generate_content(
                model=config.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2 # Temperatura baja para análisis más consistentes
                )
            )
            
            raw = response.text.strip()
            result = json.loads(raw) # Ya no necesitamos limpiar el markdown manual
            
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
