"""
oauth_setup.py — Configuración OAuth ÚNICA VEZ
=================================================
Ejecuta este script UNA SOLA VEZ desde tu computadora local.
Abrirá el navegador para que autorices el acceso a tu cuenta de Google.
Al finalizar, te imprimirá el GOOGLE_REFRESH_TOKEN que debes guardar
como secret en tu repositorio de GitHub.

ANTES DE CORRER:
  1. Ve a https://console.cloud.google.com
  2. Crea un proyecto y habilita "Business Profile API"
  3. En "Credenciales" crea credenciales OAuth 2.0 (tipo: Aplicación web)
  4. Agrega http://localhost:8080/callback como "URI de redireccionamiento autorizado"
  5. Copia el Client ID y Client Secret abajo

CÓMO CORRER:
  pip install requests
  python scripts/oauth_setup.py
"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests

# ⚠️ LLENAR ESTOS VALORES CON TUS CREDENCIALES DE GOOGLE CLOUD
CLIENT_ID     = "TU_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "TU_CLIENT_SECRET"

REDIRECT_URI = "http://localhost:8080/callback"
SCOPE        = "https://www.googleapis.com/auth/business.manage"

# Variable global para capturar el código del callback
_auth_code: str | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Servidor HTTP mínimo para capturar el código de autorización."""

    def do_GET(self):
        global _auth_code
        params     = parse_qs(urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if _auth_code:
            msg = "<h2>✅ Autorizado correctamente. Puedes cerrar esta ventana y volver a la terminal.</h2>"
        else:
            msg = "<h2>❌ No se recibió código. Intenta de nuevo.</h2>"

        self.wfile.write(msg.encode())

    def log_message(self, format, *args):
        pass  # Silenciar logs del servidor HTTP


def main():
    global _auth_code

    # ------------------------------------------------------------------
    # Paso 1: Generar URL de autorización y abrir el navegador
    # ------------------------------------------------------------------
    auth_url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPE}"
        "&response_type=code"
        "&access_type=offline"
        "&prompt=consent"  # IMPORTANTE: sin esto no recibirás el refresh_token
    )

    print("\n" + "=" * 60)
    print("CONFIGURACIÓN OAUTH — MIRAMELINDO")
    print("=" * 60)
    print("\nAbriendo el navegador para autorizar el acceso...")
    print("Si no se abre automáticamente, copia esta URL:\n")
    print(auth_url)
    print()

    webbrowser.open(auth_url)

    # ------------------------------------------------------------------
    # Paso 2: Esperar el callback en localhost:8080
    # ------------------------------------------------------------------
    print("Esperando autorización en http://localhost:8080/callback ...")
    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    server.handle_request()  # Atiende UNA request y sale

    if not _auth_code:
        print("\n❌ No se recibió el código de autorización. Intenta de nuevo.")
        return

    print(f"\n✅ Código recibido: {_auth_code[:20]}...")

    # ------------------------------------------------------------------
    # Paso 3: Intercambiar el code por tokens
    # ------------------------------------------------------------------
    print("\nIntercambiando código por tokens...")
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          _auth_code,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri":  REDIRECT_URI,
            "grant_type":    "authorization_code",
        },
        timeout=10,
    )

    tokens = response.json()

    if "error" in tokens:
        print(f"\n❌ Error al obtener tokens: {tokens}")
        return

    if "refresh_token" not in tokens:
        print("\n❌ No se recibió refresh_token.")
        print("   Causa probable: Ya autorizaste esta app antes sin revocar acceso.")
        print("   Solución: Ve a https://myaccount.google.com/permissions")
        print("   Revoca el acceso a tu app y vuelve a correr este script.")
        print(f"\n   Respuesta de Google: {json.dumps(tokens, indent=2)}")
        return

    # ------------------------------------------------------------------
    # Paso 4: Mostrar los valores que debes guardar como GitHub Secrets
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("✅ ÉXITO — GUARDA ESTOS VALORES COMO GITHUB SECRETS")
    print("=" * 60)
    print(f"\nGOOGLE_CLIENT_ID     = {CLIENT_ID}")
    print(f"GOOGLE_CLIENT_SECRET = {CLIENT_SECRET}")
    print(f"GOOGLE_REFRESH_TOKEN = {tokens['refresh_token']}")
    print("\n" + "=" * 60)
    print("Dónde guardarlos en GitHub:")
    print("  Repositorio → Settings → Secrets and variables → Actions → New secret")
    print("=" * 60 + "\n")

    print("SIGUIENTE PASO: Corre el script get_location_ids.py para")
    print("obtener los IDs de tus 4 ubicaciones de Google Business Profile.\n")


if __name__ == "__main__":
    main()
