#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 3: Extraction de l'Armurerie Légendaire et des recettes de fabrication.
Peut être exécuté de manière totalement autonome (`python scrape_legendaries.py`).
"""

import os
import sqlite3
import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gw2.app/api/v1"
DEFAULT_DB_PATH = "gw2_skins_unlocks.db"
DEFAULT_JSON_PATH = "gw2_skins_unlocks.json"
DEFAULT_JS_PATH = "gw2_skins_unlocks.js"

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_item_details(item_id, lang="fr"):
    url = f"{BASE_URL}/items/{item_id}?lang={lang}"
    try:
        return fetch_json(url)
    except Exception:
        return None

def build_craft_tree(item_id, mystic_map, depth=0, max_depth=3):
    if depth >= max_depth or not item_id:
        return None
    recipe = mystic_map.get(item_id)
    if not recipe:
        return None

    tree = {
        "output_id": item_id,
        "output_name": recipe.get("output_item", {}).get("name"),
        "ingredients": []
    }

    ingredients = recipe.get("ingredients") or []
    ingredient_items = recipe.get("ingredient_items") or []

    for ing, ing_item in zip(ingredients, ingredient_items):
        sub_id = ing.get("id") if isinstance(ing, dict) else None
        sub_tree = build_craft_tree(sub_id, mystic_map, depth + 1, max_depth) if sub_id else None
        ing_item_dict = ing_item if isinstance(ing_item, dict) else {}
        tree["ingredients"].append({
            "id": sub_id,
            "count": ing.get("count", 1) if isinstance(ing, dict) else 1,
            "name": ing_item_dict.get("name"),
            "rarity": ing_item_dict.get("rarity"),
            "icon": ing_item_dict.get("icon"),
            "sub_recipe": sub_tree
        })
    return tree

def run_scrape_legendaries(workers=15, lang="fr"):
    print(f"[LÉGENDAIRES] Récupération depuis {BASE_URL}/legendary-armory/all ({lang})...")
    try:
        leg_summary = fetch_json(f"{BASE_URL}/legendary-armory/all?lang={lang}")
    except Exception as e:
        print(f"[LÉGENDAIRES] Erreur: {e}")
        leg_summary = []

    try:
        mystic_recipes = fetch_json(f"{BASE_URL}/mystic-recipes/all?lang={lang}")
    except Exception:
        mystic_recipes = []

    mystic_map = {}
    for r in (mystic_recipes or []):
        if not isinstance(r, dict):
            continue
        out_id = r.get("output_item_id")
        if out_id and (out_id not in mystic_map or r.get("is_primary")):
            mystic_map[out_id] = r

    leg_ids = [leg["id"] for leg in leg_summary if isinstance(leg, dict) and "id" in leg]

    leg_item_details = {}
    with ThreadPoolExecutor(max_workers=min(workers, 15)) as executor:
        future_to_leg = {executor.submit(fetch_item_details, lid, lang): lid for lid in leg_ids}
        for future in as_completed(future_to_leg):
            lid = future_to_leg[future]
            data = future.result()
            if data:
                leg_item_details[lid] = data

    leg_results = []
    for leg in leg_summary:
        if not isinstance(leg, dict):
            continue
        lid = leg.get("id")
        item_data = leg.get("item") if isinstance(leg.get("item"), dict) else {}
        item_det = leg_item_details.get(lid) if isinstance(leg_item_details.get(lid), dict) else {}

        craft_tree = build_craft_tree(lid, mystic_map)
        acq_methods = item_det.get("acquisitionMethods") or []

        leg_obj = {
            "id": lid,
            "name": item_data.get("name", ""),
            "type": item_data.get("type", ""),
            "rarity": item_data.get("rarity", "Legendary"),
            "icon": item_data.get("icon", ""),
            "max_count": leg.get("max_count", 1),
            "default_skin_id": item_data.get("default_skin"),
            "craft_tree": craft_tree,
            "acquisitionMethods": acq_methods,
            "raw": leg
        }
        leg_results.append(leg_obj)

    print(f"[LÉGENDAIRES] Terminé: {len(leg_results)} objets légendaires traités.")
    return leg_results

def save_standalone(leg_results):
    """Enregistre les objets légendaires de manière autonome."""
    existing_data = {"skins": [], "containers": [], "legendaries": [], "unlocks_tree": [], "dyes": []}
    if os.path.exists(DEFAULT_JSON_PATH):
        try:
            with open(DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass

    existing_data["legendaries"] = leg_results

    print(f"[LÉGENDAIRES] Enregistrement autonome dans {DEFAULT_JSON_PATH} et {DEFAULT_JS_PATH}...")
    with open(DEFAULT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    with open(DEFAULT_JS_PATH, "w", encoding="utf-8") as f:
        f.write("window.GW2_SKINS_DB = ")
        json.dump(existing_data, f, ensure_ascii=False)
        f.write(";")

    if os.path.exists(DEFAULT_DB_PATH):
        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS legendaries (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    rarity TEXT,
                    icon TEXT,
                    max_count INTEGER,
                    default_skin_id INTEGER,
                    craft_tree_json TEXT,
                    acquisition_methods_json TEXT,
                    full_data_json TEXT
                )
            """)
            cursor.execute("DELETE FROM legendaries")
            leg_db_rows = [(
                leg["id"], leg["name"], leg["type"], leg["rarity"], leg["icon"],
                leg["max_count"], leg["default_skin_id"],
                json.dumps(leg["craft_tree"], ensure_ascii=False) if leg["craft_tree"] else None,
                json.dumps(leg["acquisitionMethods"], ensure_ascii=False),
                json.dumps(leg["raw"], ensure_ascii=False)
            ) for leg in leg_results]
            cursor.executemany("""
                INSERT INTO legendaries (id, name, type, rarity, icon, max_count, default_skin_id, craft_tree_json, acquisition_methods_json, full_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, leg_db_rows)
            conn.commit()
            conn.close()
            print(f"[LÉGENDAIRES] Lignes mises à jour dans SQLite ({len(leg_db_rows)}).")
        except Exception as e:
            print(f"[LÉGENDAIRES] Erreur SQLite: {e}")

if __name__ == "__main__":
    legs = run_scrape_legendaries()
    save_standalone(legs)
    print("Extraction autonome des objets légendaires terminée.")
