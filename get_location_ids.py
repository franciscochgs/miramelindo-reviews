"""
get_location_ids.py — Descubrir IDs de cuentas y ubicaciones GBP
==================================================================

Ejecuta DESPUÉS de oauth_setup.py.
Lista todas tus cuentas y ubicaciones de Google Business Profile
para que puedas copiar los IDs correctos al configurar GBP_LOCATIONS.

Usa las APIs modernas (la v4 fue apagada):
  - My Business Account Management API (cuentas)
  - My Business Business Information API (ubicaciones)
"""

import json
import os
import sys

import requests

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

ACCOUNTS_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"

# Campos que pedimos para cada ubicación (la API exige readMask)
LOCATION_READ_MASK = "name,title,storefrontAddress"


def get_access_token() -> str:
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main():
    missing = [k for k, v in {
        "GOOGLE_CLIENT_ID": CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN": REFRESH_TOKEN,
    }.items() if not v]
    if missing:
        print(f"❌ Variables de entorno faltantes: {', '.join(missing)}")
        sys.exit(1)

    print("\nObteniendo access token...")
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------
    # Listar cuentas (API Account Management v1)
    # ------------------------------------------------------------------
    print("Consultando cuentas de Google Business Profile (v1)...\n")
    resp = requests.get(f"{ACCOUNTS_BASE}/accounts", headers=headers, timeout=15)

    if resp.status_code != 200:
        print(f"❌ Error consultando cuentas: {resp.status_code}")
        print(resp.text[:500])
        sys.exit(1)

    accounts = resp.json().get("accounts", [])

    if not accounts:
        print("❌ No se encontraron cuentas de GBP.")
        sys.exit(1)

    all_locations = []

    for account in accounts:
        account_name = account["name"]  # "accounts/1234567890"
        account_label = account.get("accountName", account_name)

        print(f"📁 Cuenta: {account_label}")
        print(f"   ID    : {account_name}\n")

        # ------------------------------------------------------------------
        # Listar ubicaciones (API Business Information v1)
        # ------------------------------------------------------------------
        loc_resp = requests.get(
            f"{INFO_BASE}/{account_name}/locations",
            headers=headers,
            params={
                "readMask": LOCATION_READ_MASK,
                "pageSize": 100,
            },
            timeout=15,
        )

        if loc_resp.status_code != 200:
            print(f"   ⚠️ Error listando ubicaciones: {loc_resp.status_code}")
            print(f"   {loc_resp.text[:300]}")
            continue

        locations = loc_resp.json().get("locations", [])

        if not locations:
            print("   (Sin ubicaciones en esta cuenta)\n")
            continue

        for loc in locations:
            # En la v1 los locations vienen como "locations/<id>" (sin el prefijo accounts/)
            # Hay que componer el resource name completo manualmente
            raw_name = loc["name"]
            if raw_name.startswith("accounts/"):
                full_id = raw_name
            elif raw_name.startswith("locations/"):
                full_id = f"{account_name}/{raw_name}"
            else:
                full_id = f"{account_name}/locations/{raw_name}"

            title = loc.get("title", full_id)
            address = ""
            sa = loc.get("storefrontAddress", {})
            if sa:
                lines = sa.get("addressLines", [])
                if lines:
                    address = lines[0]

            print(f"   📍 {title}")
            print(f"      location_id: {full_id}")
            if address:
                print(f"      Dirección  : {address}")
            print()

            all_locations.append({
                "name": title,
                "property": "COMPLETAR",
                "location_id": full_id,
            })

    # ------------------------------------------------------------------
    # Generar el JSON listo para GBP_LOCATIONS
    # ------------------------------------------------------------------
    print("=" * 60)
    print("COPIA Y EDITA ESTE JSON PARA TU SECRET GBP_LOCATIONS")
    print("(Cambia el campo 'property' por el valor correcto)")
    print("=" * 60)

    PROPERTY_MAP = {
        "hotel_pueblo": ["pueblo"],
        "glamping": ["glamping"],
        "cabanas": ["cabaña", "cabana", "río", "rio"],
        "restaurante": ["restaurante", "restaurant"],
        "hotel": ["hotel", "spa", "miramelindo"],
    }

    for loc in all_locations:
        name_lower = loc["name"].lower()
        for prop_key, keywords in PROPERTY_MAP.items():
            if any(kw in name_lower for kw in keywords):
                loc["property"] = prop_key
                break

    print(json.dumps(all_locations, indent=2, ensure_ascii=False))
    print("\nPega este JSON (en una sola línea) como el valor del secret GBP_LOCATIONS.")
    print("\nEjemplo de valor compacto para el secret:")
    print(json.dumps(all_locations, ensure_ascii=False))


if __name__ == "__main__":
    main()
