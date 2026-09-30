#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_dyes.py
Extraction complète de toutes les teintures Guild Wars 2 via l'API v2 (/v2/colors).
Enrichit chaque teinture avec le nom français, les composantes RGB / Hexadecimal,
la rareté, l'icône de l'objet flacon, l'éligibilité au comptoir (TP) et les coffres/kits associés.
"""

import json
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HUE_TRANSLATIONS = {
    "Gray": "Gris / Noir / Blanc",
    "Red": "Rouge",
    "Orange": "Orange",
    "Yellow": "Jaune / Doré",
    "Green": "Vert",
    "Blue": "Bleu",
    "Purple": "Violet / Rose",
    "Brown": "Marron / Brun",
    "Exclusive": "Exclusif (Kit du Lion Noir)"
}

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logging.warning(f"Erreur d'accès à {url}: {e}")
        return None

def run_scrape_dyes(container_results=None):
    logging.info("[TEINTURES] Extraction de la liste complète des teintures (/v2/colors?ids=all)...")
    colors_data = fetch_json("https://api.guildwars2.com/v2/colors?ids=all&lang=fr")

    if not colors_data or not isinstance(colors_data, list):
        logging.error("[TEINTURES] Impossible de récupérer les couleurs API v2.")
        return []

    # Map item_ids to color objects
    item_ids = [c["item"] for c in colors_data if "item" in c and isinstance(c["item"], int)]

    items_map = {}
    if item_ids:
        # Fetch items in chunks of 200
        for i in range(0, len(item_ids), 200):
            chunk = item_ids[i:i+200]
            ids_str = ",".join(map(str, chunk))
            items_chunk = fetch_json(f"https://api.guildwars2.com/v2/items?ids={ids_str}&lang=fr")
            if items_chunk and isinstance(items_chunk, list):
                for item_obj in items_chunk:
                    items_map[item_obj["id"]] = item_obj

    # Fetch TP prices for items
    tp_map = {}
    if item_ids:
        for i in range(0, len(item_ids), 200):
            chunk = item_ids[i:i+200]
            ids_str = ",".join(map(str, chunk))
            prices_chunk = fetch_json(f"https://api.guildwars2.com/v2/commerce/prices?ids={ids_str}")
            if prices_chunk and isinstance(prices_chunk, list):
                for price_obj in prices_chunk:
                    tp_map[price_obj["id"]] = price_obj

    # Build container mapping for dyes
    dye_containers_map = {}
    if container_results and isinstance(container_results, list):
        for c in container_results:
            c_items = c.get("items", []) or c.get("skins", [])
            for item in c_items:
                iname = item.get("name") if isinstance(item, dict) else item
                if iname:
                    dye_containers_map.setdefault(iname.lower(), []).append({
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "icon": c.get("icon"),
                        "isTpItem": c.get("isTpItem", False)
                    })

    dyes_list = []
    for c in colors_data:
        cid = c.get("id")
        cname = c.get("name", f"Teinture #{cid}")
        cloth = c.get("cloth", {}) or c.get("leather", {}) or {}
        rgb = cloth.get("rgb", [128, 128, 128])

        if len(rgb) == 3:
            hex_code = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".upper()
        else:
            hex_code = "#808080"

        raw_categories = c.get("categories", [])
        hue_category = "Autre"
        for cat in raw_categories:
            if cat in HUE_TRANSLATIONS:
                hue_category = HUE_TRANSLATIONS[cat]
                break

        item_id = c.get("item")
        item_obj = items_map.get(item_id, {}) if item_id else {}
        tp_obj = tp_map.get(item_id, {}) if item_id else {}

        full_item_name = item_obj.get("name", cname)
        rarity = item_obj.get("rarity", "Basic")
        icon = item_obj.get("icon") or "https://render.guildwars2.com/file/6E262204244D033C2C38DF3F026654B49BFE4EA4/66650.png"

        flags = item_obj.get("flags", [])
        is_tp = ("NoTrade" not in flags and "AccountBound" not in flags and item_id in tp_map)

        buys_price = tp_obj.get("buys", {}).get("unit_price", 0) if is_tp else 0
        sells_price = tp_obj.get("sells", {}).get("unit_price", 0) if is_tp else 0

        # Find matching containers
        assoc_containers = dye_containers_map.get(full_item_name.lower(), []) or dye_containers_map.get(cname.lower(), [])

        dyes_list.append({
            "id": cid,
            "color_id": cid,
            "item_id": item_id,
            "name": cname,
            "full_name": full_item_name,
            "rgb": rgb,
            "hex": hex_code,
            "categories": raw_categories,
            "hue": hue_category,
            "rarity": rarity,
            "icon": icon,
            "is_tp_item": is_tp,
            "buy_price": buys_price,
            "sell_price": sells_price,
            "containers": assoc_containers
        })

    logging.info(f"[TEINTURES] Extraction réussie : {len(dyes_list)} teintures indexées.")
    return dyes_list

if __name__ == "__main__":
    dyes = run_scrape_dyes()
    print(f"Sample dye: {json.dumps(dyes[1] if len(dyes) > 1 else dyes[0], indent=2, ensure_ascii=False)}")
