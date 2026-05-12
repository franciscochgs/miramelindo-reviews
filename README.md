# Sistema de Reseñas Miramelindo

Orquestador en Python para obtener, analizar (con Gemini) y respaldar (en Supabase) las reseñas de Google Business Profile de las propiedades de Miramelindo. Además, envía alertas por email usando Resend para reseñas críticas o negativas.

El sistema está diseñado para correr automáticamente vía GitHub Actions cada 2 horas.

## Configuración Inicial

Para configurar el entorno por primera vez y obtener los secretos necesarios para GitHub Actions:

1. Instala las dependencias locales:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta el script de OAuth para autorizar a la app y obtener tu `GOOGLE_REFRESH_TOKEN`:
   ```bash
   python oauth_setup.py
   ```
3. Una vez tengas el refresh token, obtén los IDs de las ubicaciones ejecutando:
   ```bash
   python get_location_ids.py
   ```
4. Configura todos los secretos resultantes en tu repositorio de GitHub tal como se detalla en la consola durante el proceso.