#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de récupération des skins (et leurs déblocages) ainsi que de l'Armurerie Légendaire (et leurs recettes de craft) depuis GW2.app.
Génère une base SQLite, un fichier JSON et un fichier JavaScript (.js) pour compatibilité navigateur directe (file://).
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gw2.app/api/v1"
DEFAULT_DB_PATH = "gw2_skins_unlocks.db"
DEFAULT_JSON_PATH = "gw2_skins_unlocks.json"
DEFAULT_JS_PATH = "gw2_skins_unlocks.js"
DEFAULT_WORKERS = 20

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def init_sqlite_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skins (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            rarity TEXT,
            icon TEXT,
            keywords TEXT,
            acquisition_methods_json TEXT,
            used_in_json TEXT,
            full_data_json TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skins_name ON skins(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skins_type ON skins(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skins_rarity ON skins(rarity)")

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leg_name ON legendaries(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leg_type ON legendaries(type)")

    conn.commit()
    return conn

def fetch_skin_details(skin_id, lang="fr"):
    url = f"{BASE_URL}/skins/{skin_id}?lang={lang}"
    try:
        return fetch_json(url)
    except Exception:
        return None

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

    ingredients = recipe.get("ingredients", [])
    ingredient_items = recipe.get("ingredient_items", [])

    for ing, ing_item in zip(ingredients, ingredient_items):
        sub_id = ing.get("id")
        sub_tree = build_craft_tree(sub_id, mystic_map, depth + 1, max_depth) if sub_id else None
        tree["ingredients"].append({
            "id": sub_id,
            "count": ing.get("count", 1),
            "name": ing_item.get("name"),
            "rarity": ing_item.get("rarity"),
            "icon": ing_item.get("icon"),
            "sub_recipe": sub_tree
        })
    return tree

def main():
    parser = argparse.ArgumentParser(description="Recuperation des skins GW2, debloquages et craft legendaire depuis gw2.app")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de skins (0 pour tous)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Nombre de threads concurrents")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Chemin du fichier SQLite")
    parser.add_argument("--json", type=str, default=DEFAULT_JSON_PATH, help="Chemin du fichier JSON")
    parser.add_argument("--js", type=str, default=DEFAULT_JS_PATH, help="Chemin du fichier JS")
    parser.add_argument("--lang", type=str, default="fr", help="Langue (fr, en, de, es)")
    args = parser.parse_args()

    print(f"=== GW2 Skins Unlocks & Legendary Crafting Scraper ({args.lang}) ===")

    # -------------------------------------------------------------
    # PART 1: SKINS & UNLOCKS
    # -------------------------------------------------------------
    print(f"\n[1/2] Recuperation des skins depuis {BASE_URL}/skins/all...")
    try:
        all_skins_summary = fetch_json(f"{BASE_URL}/skins/all?lang={args.lang}")
    except Exception as e:
        print(f"[ERREUR] Impossible de charger la liste des skins: {e}")
        sys.exit(1)

    total_skins = len(all_skins_summary)
    print(f"Total de skins trouves : {total_skins}")

    if args.limit > 0:
        all_skins_summary = all_skins_summary[:args.limit]
        print(f"Limitation appliquee : {len(all_skins_summary)} skins")

    skin_ids = [s["id"] for s in all_skins_summary if "id" in s]
    print(f"Telechargement des details pour {len(skin_ids)} skins ({args.workers} workers)...")

    skin_results = {}
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_id = {executor.submit(fetch_skin_details, sid, args.lang): sid for sid in skin_ids}
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            data = future.result()
            completed += 1
            if data:
                skin_results[sid] = data
            if completed % 500 == 0 or completed == len(skin_ids):
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"Skins progression: {completed}/{len(skin_ids)} ({completed*100/len(skin_ids):.1f}%) - {rate:.1f} skins/sec")

    print(f"Extraction skins terminee en {time.time() - t0:.2f}s ({len(skin_results)} skins recuperes).")

    # -------------------------------------------------------------
    # PART 2: LEGENDARY ARMORY & CRAFTING
    # -------------------------------------------------------------
    print(f"\n[2/2] Recuperation des objets et recettes legendaires depuis {BASE_URL}/legendary-armory/all...")
    try:
        leg_summary = fetch_json(f"{BASE_URL}/legendary-armory/all?lang={args.lang}")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de charger l'Armurerie Légendaire: {e}")
        leg_summary = []

    print(f"Total d'objets legendaires trouves : {len(leg_summary)}")

    print(f"Chargement des recettes de Forge Mystique depuis {BASE_URL}/mystic-recipes/all...")
    try:
        mystic_recipes = fetch_json(f"{BASE_URL}/mystic-recipes/all?lang={args.lang}")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de charger les recettes mystiques: {e}")
        mystic_recipes = []

    mystic_map = {}
    for r in mystic_recipes:
        out_id = r.get("output_item_id")
        if out_id and (out_id not in mystic_map or r.get("is_primary")):
            mystic_map[out_id] = r

    leg_ids = [leg["id"] for leg in leg_summary if "id" in leg]
    print(f"Extraction des details d'obtention pour {len(leg_ids)} objets legendaires...")

    leg_item_details = {}
    with ThreadPoolExecutor(max_workers=min(args.workers, 15)) as executor:
        future_to_leg = {executor.submit(fetch_item_details, lid, args.lang): lid for lid in leg_ids}
        for future in as_completed(future_to_leg):
            lid = future_to_leg[future]
            data = future.result()
            if data:
                leg_item_details[lid] = data

    leg_results = []
    for leg in leg_summary:
        lid = leg.get("id")
        item_data = leg.get("item", {})
        item_det = leg_item_details.get(lid, {})

        craft_tree = build_craft_tree(lid, mystic_map)
        acq_methods = item_det.get("acquisitionMethods", [])

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

    print(f"Armurerie Legendaire integree ({len(leg_results)} objets traités).")

    # -------------------------------------------------------------
    # SAVE TO SQLITE, JSON & JS
    # -------------------------------------------------------------
    print(f"\n[SAUVEGARDE] Enregistrement dans SQLite ({args.db})...")
    conn = init_sqlite_db(args.db)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM skins")
    cursor.execute("DELETE FROM legendaries")

    skin_db_rows = []
    skin_json_export = []

    for sid in sorted(skin_results.keys()):
        data = skin_results[sid]
        skin_info = data.get("skin", {})
        acq_methods = data.get("acquisitionMethods", [])
        used_in = data.get("usedIn", [])
        keywords = data.get("keywords", "")

        s_name = skin_info.get("name", "")
        s_type = skin_info.get("type", "")
        s_rarity = skin_info.get("rarity", "")
        s_icon = skin_info.get("icon", "")

        keywords_str = " ".join(keywords) if isinstance(keywords, list) else str(keywords)

        acq_json = json.dumps(acq_methods, ensure_ascii=False)
        used_in_json = json.dumps(used_in, ensure_ascii=False)
        full_json = json.dumps(data, ensure_ascii=False)

        skin_db_rows.append((
            sid,
            s_name,
            s_type,
            s_rarity,
            s_icon,
            keywords_str,
            acq_json,
            used_in_json,
            full_json
        ))

        skin_json_export.append({
            "id": sid,
            "name": s_name,
            "type": s_type,
            "rarity": s_rarity,
            "icon": s_icon,
            "keywords": keywords,
            "acquisitionMethods": acq_methods,
            "usedIn": used_in,
            "raw": data
        })

    cursor.executemany("""
        INSERT INTO skins (id, name, type, rarity, icon, keywords, acquisition_methods_json, used_in_json, full_data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, skin_db_rows)

    leg_db_rows = []
    for leg in leg_results:
        leg_db_rows.append((
            leg["id"],
            leg["name"],
            leg["type"],
            leg["rarity"],
            leg["icon"],
            leg["max_count"],
            leg["default_skin_id"],
            json.dumps(leg["craft_tree"], ensure_ascii=False) if leg["craft_tree"] else None,
            json.dumps(leg["acquisitionMethods"], ensure_ascii=False),
            json.dumps(leg["raw"], ensure_ascii=False)
        ))

    cursor.executemany("""
        INSERT INTO legendaries (id, name, type, rarity, icon, max_count, default_skin_id, craft_tree_json, acquisition_methods_json, full_data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, leg_db_rows)

    conn.commit()
    conn.close()
    print(f"Base SQLite mise a jour ({len(skin_db_rows)} skins, {len(leg_db_rows)} legendaires).")

    full_output = {
        "skins": skin_json_export,
        "legendaries": leg_results
    }

    print(f"Exportation du fichier JSON ({args.json})...")
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)
    print(f"JSON sauvegarde ({os.path.getsize(args.json) / (1024*1024):.2f} MB).")

    print(f"Exportation du fichier JS ({args.js})...")
    with open(args.js, "w", encoding="utf-8") as f:
        f.write("window.GW2_SKINS_DB = ")
        json.dump(full_output, f, ensure_ascii=False)
        f.write(";")
    print(f"JS sauvegarde ({os.path.getsize(args.js) / (1024*1024):.2f} MB).")

    print("\nExtraction terminee avec succes!")

if __name__ == "__main__":
    main()
