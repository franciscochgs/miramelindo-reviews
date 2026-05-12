"""
get_location_ids.py — Descubrir IDs de cuentas y ubicaciones GBP
==================================================================

Prueba MÚLTIPLES endpoints porque Google migró APIs:
  1. mybusinessaccountmanagement.googleapis.com/v1 (nueva)
  2. mybusiness.googleapis.com/v4 (vieja, deprecated pero a veces activa)

Imprime diagnóstico claro de cada intento.
"""

import json
import os
import sys

import requests

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

# Endpoints candidatos
ENDPOINTS = {
    "v1_account_management": "https://mybusinessaccountmanagement.googleapis.com/v1",
    "v4_my_business": "https://mybusiness.googleapis.com/v4",
}
INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
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


def try_list_accounts(headers: dict) -> list | None:
    """Prueba ambos endpoints. Devuelve la lista de cuentas o None si fallaron todos."""

    for label, base in ENDPOINTS.items():
        url = f"{base}/accounts"
        print(f"\n🔍 Probando {label}: {url}")

        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except Exception as e:
            print(f"   ❌ Error de red: {e}")
            continue

        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            accounts = data.get("accounts", [])
            print(f"   ✅ Éxito: {len(accounts)} cuenta(s) encontrada(s)")
            return accounts

        # Diagnóstico de errores comunes
        try:
            err_body = resp.json()
            err_msg = err_body.get("error", {}).get("message", "")[:200]
            print(f"   ❌ Error: {err_msg}")
        except Exception:
            print(f"   ❌ Body: {resp.text[:200]}")

    return None


def list_locations_v1(account_name: str, headers: dict) -> list:
    """Lista ubicaciones usando la API Business Information v1."""
    resp = requests.get(
        f"{INFO_BASE}/{account_name}/locations",
        headers=headers,
        params={"readMask": LOCATION_READ_MASK, "pageSize": 100},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("locations", [])

    print(f"   ⚠️ v1 Business Information falló: {resp.status_code}")
    print(f"   {resp.text[:300]}")
    return []


def list_locations_v4(account_name: str, headers: dict) -> list:
    """Lista ubicaciones usando la API My Business v4 (legacy)."""
    resp = requests.get(
        f"{ENDPOINTS['v4_my_business']}/{account_name}/locations",
        headers=headers,
        params={"pageSize": 100},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("locations", [])

    print(f"   ⚠️ v4 My Business falló: {resp.status_code}")
    print(f"   {resp.text[:300]}")
    return []


def main():
    missing = [k for k, v in {
        "GOOGLE_CLIENT_ID": CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN": REFRESH_TOKEN,
    }.items() if not v]
    if missing:
        print(f"❌ Variables de entorno faltantes: {', '.join(missing)}")
        sys.exit(1)

    print("Obteniendo access token...")
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    print("\n" + "=" * 60)
    print("FASE 1: LISTAR CUENTAS")
    print("=" * 60)

    accounts = try_list_accounts(headers)

    if not accounts:
        print("\n❌ Ningún endpoint funcionó para listar cuentas.")
        print("   Hay que solicitar aumento de cuota o usar fallback manual.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("FASE 2: LISTAR UBICACIONES DE CADA CUENTA")
    print("=" * 60)

    all_locations = []

    for account in accounts:
        account_name = account["name"]
        account_label = account.get("accountName", account_name)

        print(f"\n📁 Cuenta: {account_label}")
        print(f"   ID    : {account_name}")

        # Intentar v1 primero, luego v4
        print(f"\n   Intentando listar locations con v1 Business Information...")
        locations = list_locations_v1(account_name, headers)

        if not locations:
            print(f"   Intentando listar locations con v4 My Business...")
            locations = list_locations_v4(account_name, headers)

        if not locations:
            print(f"   ❌ No se pudieron listar locations en esta cuenta.")
            continue

        print(f"   ✅ {len(locations)} ubicacion(es) encontrada(s)\n")

        for loc in locations:
            raw_name = loc["name"]
            if raw_name.startswith("accounts/"):
                full_id = raw_name
            elif raw_name.startswith("locations/"):
                full_id = f"{account_name}/{raw_name}"
            else:
                full_id = f"{account_name}/locations/{raw_name}"

            title = loc.get("title") or loc.get("locationName") or full_id

            sa = loc.get("storefrontAddress", {}) or loc.get("address", {})
            address = ""
            if sa:
                lines = sa.get("addressLines", [])
                if lines:
                    address = lines[0]

            print(f"   📍 {title}")
            print(f"      location_id: {full_id}")
            if address:
                print(f"      Dirección  : {address}")

            all_locations.append({
                "name": title,
                "property": "COMPLETAR",
                "location_id": full_id,
            })

    if not all_locations:
        print("\n❌ No se encontraron ubicaciones en ninguna cuenta.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Generar el JSON listo para GBP_LOCATIONS
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("JSON LISTO PARA EL SECRET GBP_LOCATIONS")
    print("(Verifica el campo 'property' antes de pegarlo)")
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

    print("\nFormato legible:")
    print(json.dumps(all_locations, indent=2, ensure_ascii=False))

    print("\nFormato compacto para pegar en el secret (UNA LÍNEA):")
    print(json.dumps(all_locations, ensure_ascii=False))


if __name__ == "__main__":
    main()
