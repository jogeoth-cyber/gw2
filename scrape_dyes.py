#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_dyes.py
Extraction complète de toutes les teintures Guild Wars 2 via l'API v2 (/v2/colors).
Enrichit chaque teinture avec le nom français, les composantes RGB / Hexadécimal,
la rareté, l'icône de l'objet flacon, l'éligibilité au comptoir (TP),
les packs de teintures d'anniversaire / cadeaux d'anniversaire (Birthday Dye Kits)
et les coffres/kits associés.

Peut être exécuté de manière totalement autonome (`python scrape_dyes.py`).
"""

import os
import sys
import json
import sqlite3
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_DB_PATH = "gw2_skins_unlocks.db"
DEFAULT_JSON_PATH = "gw2_skins_unlocks.json"
DEFAULT_JS_PATH = "gw2_skins_unlocks.js"

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

# Birthday & Anniversary Dye Kits Mapping
ANNIVERSARY_DYE_KITS = [
    {"name": "Kit de teintures du 3e anniversaire", "en": "3rd Anniversary Dye Kit", "gift": "Cadeau de 3e anniversaire (Year 3 Birthday Gift)"},
    {"name": "Kit de teintures du 4e anniversaire", "en": "4th Anniversary Dye Kit", "gift": "Cadeau de 4e anniversaire (Year 4 Birthday Gift)"},
    {"name": "Kit de teintures du 5e anniversaire", "en": "5th Anniversary Dye Kit", "gift": "Cadeau de 5e anniversaire (Year 5 Birthday Gift)"},
    {"name": "Kit de teintures du 6e anniversaire", "en": "6th Anniversary Dye Kit", "gift": "Cadeau de 6e anniversaire (Year 6 Birthday Gift)"},
    {"name": "Kit de teintures du 7e anniversaire", "en": "7th Anniversary Dye Kit", "gift": "Cadeau de 7e anniversaire (Year 7 Birthday Gift)"},
    {"name": "Kit de teintures du 8e anniversaire", "en": "8th Anniversary Dye Kit", "gift": "Cadeau de 8e anniversaire (Year 8 Birthday Gift)"},
    {"name": "Kit de teintures du 9e anniversaire", "en": "9th Anniversary Dye Kit", "gift": "Cadeau de 9e anniversaire (Year 9 Birthday Gift)"},
    {"name": "Kit de teintures du 10e anniversaire", "en": "10th Anniversary Dye Kit", "gift": "Cadeau de 10e anniversaire (Year 10 Birthday Gift)"},
    {"name": "Kit de teintures du 11e anniversaire", "en": "11th Anniversary Dye Kit", "gift": "Cadeau de 11e anniversaire (Year 11 Birthday Gift)"},
    {"name": "Pack de teintures de célébration", "en": "Celebration Dye Pack", "gift": "Coffre d'anniversaire / Célébration"},
    {"name": "Boîte de choix de teintures exclusives", "en": "Exclusive Dye Selection Box", "gift": "Coffre de choix d'anniversaire du compte"}
]

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
        is_exclusive = "Exclusive" in raw_categories

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

        # Anniversary Dye Packs & Birthday Choice Gifts Mapping
        anniversary_packs = []
        if is_exclusive or rarity in ["Rare", "Masterwork"]:
            # Exclusive & Rare dyes are unlockable in Anniversary Choice Dye Kits (Years 3-11)
            for akit in ANNIVERSARY_DYE_KITS:
                anniversary_packs.append({
                    "name": akit["name"],
                    "gift": akit["gift"],
                    "icon": "https://render.guildwars2.com/file/206587F7D25A82BD9A52A606A6D2C318FDC8A909/1202868.png"
                })

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
            "containers": assoc_containers,
            "anniversary_packs": anniversary_packs
        })

    logging.info(f"[TEINTURES] Extraction réussie : {len(dyes_list)} teintures indexées.")
    return dyes_list

def save_standalone(dyes_list):
    """Met à jour les fichiers JSON, JS et SQLite de manière autonome."""
    json_path = DEFAULT_JSON_PATH
    js_path = DEFAULT_JS_PATH
    db_path = DEFAULT_DB_PATH

    existing_data = {"skins": [], "containers": [], "legendaries": [], "unlocks_tree": [], "dyes": []}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass

    existing_data["dyes"] = dyes_list

    logging.info(f"[TEINTURES] Enregistrement autonome dans {json_path} et {js_path}...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.GW2_SKINS_DB = ")
        json.dump(existing_data, f, ensure_ascii=False)
        f.write(";")

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dyes (
                    id INTEGER PRIMARY KEY,
                    color_id INTEGER,
                    item_id INTEGER,
                    name TEXT,
                    full_name TEXT,
                    hex TEXT,
                    hue TEXT,
                    rarity TEXT,
                    icon TEXT,
                    is_tp_item INTEGER,
                    buy_price INTEGER,
                    sell_price INTEGER,
                    containers_json TEXT,
                    full_data_json TEXT
                )
            """)
            cursor.execute("DELETE FROM dyes")

            dyes_db_rows = []
            for d in dyes_list:
                dyes_db_rows.append((
                    d["id"],
                    d["color_id"],
                    d["item_id"],
                    d["name"],
                    d["full_name"],
                    d["hex"],
                    d["hue"],
                    d["rarity"],
                    d["icon"],
                    1 if d["is_tp_item"] else 0,
                    d["buy_price"],
                    d["sell_price"],
                    json.dumps(d["containers"], ensure_ascii=False),
                    json.dumps(d, ensure_ascii=False)
                ))

            cursor.executemany("""
                INSERT INTO dyes (id, color_id, item_id, name, full_name, hex, hue, rarity, icon, is_tp_item, buy_price, sell_price, containers_json, full_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, dyes_db_rows)
            conn.commit()
            conn.close()
            logging.info(f"[TEINTURES] Enregistrement SQLite réussi ({len(dyes_db_rows)} lignes dans 'dyes').")
        except Exception as e:
            logging.warning(f"[TEINTURES] Impossible d'enregistrer dans SQLite : {e}")

if __name__ == "__main__":
    dyes = run_scrape_dyes()
    save_standalone(dyes)
    print(f"Extraction autonome des teintures terminée : {len(dyes)} teintures enregistrées.")
