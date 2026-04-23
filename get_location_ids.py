"""
get_location_ids.py — Descubrir IDs de cuentas y ubicaciones GBP
==================================================================
Ejecuta DESPUÉS de oauth_setup.py.
Lista todas tus cuentas y ubicaciones de Google Business Profile
para que puedas copiar los IDs correctos al configurar GBP_LOCATIONS.

CÓMO CORRER (con las variables de entorno ya configuradas):
  export GOOGLE_CLIENT_ID="..."
  export GOOGLE_CLIENT_SECRET="..."
  export GOOGLE_REFRESH_TOKEN="..."
  python scripts/get_location_ids.py

O en Windows:
  set GOOGLE_CLIENT_ID=...
  set GOOGLE_CLIENT_SECRET=...
  set GOOGLE_REFRESH_TOKEN=...
  python scripts/get_location_ids.py
"""
import json
import os
import sys

import requests

# Leer credenciales desde entorno (igual que en producción)
CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

GBP_BASE = "https://mybusiness.googleapis.com/v4"


def get_access_token() -> str:
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "refresh_token": REFRESH_TOKEN,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "refresh_token",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main():
    # Validar que las variables existan
    missing = [k for k, v in {
        "GOOGLE_CLIENT_ID":     CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN": REFRESH_TOKEN,
    }.items() if not v]

    if missing:
        print(f"❌ Variables de entorno faltantes: {', '.join(missing)}")
        print("   Configúralas antes de correr este script.")
        sys.exit(1)

    print("\nObteniendo access token...")
    token   = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------
    # Listar cuentas
    # ------------------------------------------------------------------
    print("Consultando cuentas de Google Business Profile...\n")
    resp = requests.get(f"{GBP_BASE}/accounts", headers=headers, timeout=10)

    if resp.status_code != 200:
        print(f"❌ Error consultando cuentas: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    accounts = resp.json().get("accounts", [])
    if not accounts:
        print("❌ No se encontraron cuentas de GBP.")
        print("   Asegúrate de que el correo autorizado sea el admin de las propiedades.")
        sys.exit(1)

    all_locations = []

    for account in accounts:
        account_name  = account["name"]        # "accounts/1234567890"
        account_label = account.get("accountName", account_name)

        print(f"📁 Cuenta: {account_label}")
        print(f"   ID    : {account_name}\n")

        # Listar ubicaciones de esta cuenta
        loc_resp = requests.get(
            f"{GBP_BASE}/{account_name}/locations",
            headers=headers,
            params={"pageSize": 100},
            timeout=10,
        )

        if loc_resp.status_code != 200:
            print(f"   ⚠️  Error listando ubicaciones: {loc_resp.status_code}")
            continue

        locations = loc_resp.json().get("locations", [])
        if not locations:
            print("   (Sin ubicaciones en esta cuenta)\n")
            continue

        for loc in locations:
            loc_id    = loc["name"]          # "accounts/X/locations/Y"
            loc_label = loc.get("locationName", loc_id)
            address   = loc.get("address", {}).get("addressLines", [""])[0]

            print(f"   📍 {loc_label}")
            print(f"      location_id: {loc_id}")
            if address:
                print(f"      Dirección  : {address}")
            print()

            all_locations.append({
                "name":        loc_label,
                "property":    "COMPLETAR",  # hotel | glamping | cabanas | restaurante
                "location_id": loc_id,
            })

    # ------------------------------------------------------------------
    # Generar el JSON listo para GBP_LOCATIONS
    # ------------------------------------------------------------------
    print("=" * 60)
    print("COPIA Y EDITA ESTE JSON PARA TU SECRET GBP_LOCATIONS")
    print("(Cambia el campo 'property' por el valor correcto)")
    print("=" * 60)

    # Asignar propiedades conocidas de Miramelindo si se detectan por nombre
    PROPERTY_MAP = {
        "hotel":       ["hotel", "spa", "miramelindo"],
        "glamping":    ["glamping"],
        "cabanas":     ["cabaña", "cabana", "río", "rio"],
        "restaurante": ["restaurante", "restaurant"],
    }

    for loc in all_locations:
        name_lower = loc["name"].lower()
        for prop_key, keywords in PROPERTY_MAP.items():
            if any(kw in name_lower for kw in keywords):
                loc["property"] = prop_key
                break

    print(json.dumps(all_locations, indent=2, ensure_ascii=False))
    print("\nPega este JSON (en una sola línea) como el valor del secret GBP_LOCATIONS.")
    print("En GitHub Actions, el valor del secret debe ser el JSON completo en UNA línea.")
    print("\nEjemplo de valor compacto para el secret:")
    print(json.dumps(all_locations, ensure_ascii=False))


if __name__ == "__main__":
    main()
