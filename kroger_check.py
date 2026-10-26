import os
import base64
import requests
import json
from datetime import datetime

# Pull secure credentials from GitHub Secrets
CLIENT_ID = os.environ.get("KROGER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("KROGER_CLIENT_SECRET")
ZIP_CODE = "30549"  # Jefferson, GA

# Target items from your November list to check at Kroger
TARGET_ITEMS = [
    "turkey pepperoni",
    "smoked turkey dogs",
    "american cheese deli",
    "buttermilk",
    "cheddar cheese shredded",
    "heavy cream",
    "cottage cheese low fat",
    "mozzarella cheese shredded",
    "pepper jack cheese",
    "sweetened condensed milk",
    "sriracha",
    "flax seed",
    "nutmeg",
    "self rising flour",
    "white lily cornbread mix",
    "hot dog buns",
    "keto hamburger buns",
    "tortillas",
    "apple juice",
    "decaf coffee",
    "prune juice",
    "steak",
    "butter",
    "potatoes russet",
    "sweet potatoes"
]

def get_access_token():
    """Generates an OAuth2 bearer token using your Client ID and Secret."""
    url = "https://api.kroger.com/v1/connect/oauth2/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64_auth}"
    }
    data = {"grant_type": "client_credentials", "scope": "product.compact"}

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def get_nearest_location_id(token):
    """Finds the nearest Kroger store location ID for zip code 30549."""
    url = "https://api.kroger.com/v1/locations"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"filter.zipCode.near": ZIP_CODE, "filter.limit": 1}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    if data.get("data"):
        loc = data["data"][0]
        print(f"Locked onto Store: {loc.get('name')} - {loc.get('address', {}).get('addressLine1')}, {loc.get('address', {}).get('city')}")
        return loc["locationId"]
    return None

def search_product(token, location_id, search_term):
    """Searches for products and extracts regular vs promo pricing."""
    url = "https://api.kroger.com/v1/products"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {
        "filter.term": search_term,
        "filter.locationId": location_id,
        "filter.limit": 3
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return []

    results = []
    items = response.json().get("data", [])
    for item in items:
        desc = item.get("description", "Unknown")
        brand = item.get("brand", "")
        aisle = "N/A"
        for loc in item.get("aisleLocations", []):
            aisle = f"Aisle {loc.get('number', '')} {loc.get('side', '')}".strip()
            break

        regular_price = None
        promo_price = None

        for price_info in item.get("items", []):
            p = price_info.get("price", {})
            regular_price = p.get("regular")
            promo_price = p.get("promo")
            size = price_info.get("size", "")
            break

        is_sale = promo_price is not None and promo_price > 0 and promo_price < regular_price

        results.append({
            "brand": brand,
            "description": desc,
            "size": size,
            "regular_price": regular_price,
            "promo_price": promo_price,
            "on_sale": is_sale,
            "aisle": aisle
        })
    return results

def main():
    print("Authenticating with Kroger API...")
    token = get_access_token()

    print(f"Finding closest Kroger to {ZIP_CODE}...")
    location_id = get_nearest_location_id(token)
    if not location_id:
        print("Could not find a nearby store.")
        return

    report_lines = [
        f"# Kroger Weekly Deal & Price Report - {datetime.now().strftime('%Y-%m-%d')}",
        f"**Target Store Location ID:** {location_id} (Jefferson / Athens area)\n"
    ]

    sale_items = []
    regular_items = []

    print("Checking November grocery list items...")
    for term in TARGET_ITEMS:
        found = search_product(token, location_id, term)
        for prod in found:
            entry = f"- **{prod['description']}** ({prod['brand']} - {prod['size']}): "
            if prod['on_sale']:
                savings = round(prod['regular_price'] - prod['promo_price'], 2)
                entry += f"🔥 **SALE: ${prod['promo_price']:.2f}** (Reg: ${prod['regular_price']:.2f} | Save ${savings:.2f}) - {prod['aisle']}"
                sale_items.append(entry)
            elif prod['regular_price']:
                entry += f"Reg: ${prod['regular_price']:.2f} - {prod['aisle']}"
                regular_items.append(entry)

    report_lines.append("## 🛒 Items Currently on Sale This Week")
    if sale_items:
        report_lines.extend(sale_items)
    else:
        report_lines.append("No active promo pricing flagged on checked items.")

    report_lines.append("\n## 📋 Regular Price Reference for November Items")
    report_lines.extend(regular_items)

    report_text = "\n".join(report_lines)

    # Save to clean Markdown file in the repository
    with open("kroger_weekly_report.md", "w") as f:
        f.write(report_text)

    print("Scan complete. Report saved to kroger_weekly_report.md")

if __name__ == "__main__":
    main()
