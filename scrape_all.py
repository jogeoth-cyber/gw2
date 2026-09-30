#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Principal d'Orchestration:
Effectue d'abord une pré-détection rapide du nombre total d'éléments disponibles (skins, caisses, légendaires, teintures),
affiche un résumé clair, puis lance l'extraction modulaire:
- Module 1: scrape_skins.py (Skins & détails)
- Module 2: scrape_containers.py (Caisses, coffres, boîtes d'apparences)
- Module 3: scrape_legendaries.py (Armurerie Légendaire & recettes de craft)
- Module 4: scrape_unlocks_tree.py (Hiérarchie Élément Parent -> Arbre de Déblocage)
- Module 5: scrape_dyes.py (Extraction complète des 600+ teintures GW2 & flacons)

Exporte vers SQLite, JSON et JavaScript.
"""

import os
import sys
import json
import sqlite3
import argparse
import urllib.request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrape_skins import run_scrape_skins
from scrape_containers import run_scrape_containers, KNOWN_CONTAINER_IDS
from scrape_legendaries import run_scrape_legendaries
from scrape_unlocks_tree import run_scrape_unlocks_tree
from scrape_dyes import run_scrape_dyes

DEFAULT_DB_PATH = "gw2_skins_unlocks.db"
DEFAULT_JSON_PATH = "gw2_skins_unlocks.json"
DEFAULT_JS_PATH = "gw2_skins_unlocks.js"
DEFAULT_WORKERS = 20
BASE_URL = "https://gw2.app/api/v1"

def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def pre_detection_scan(lang="fr"):
    print("\n🔍 ==============================================================")
    print("   PHASE DE PRÉ-DÉTECTION DES ÉLÉMENTS (GW2 API & GW2.app API)")
    print("==============================================================")
    print("Analyse rapide des bases de données distantes en cours...\n")

    counts = {
        "skins": 0,
        "containers_estimate": 0,
        "legendaries": 0,
        "mystic_recipes": 0,
        "dyes": 0
    }

    try:
        skins_summary = fetch_json(f"{BASE_URL}/skins/all?lang={lang}")
        if isinstance(skins_summary, list):
            counts["skins"] = len(skins_summary)
            # Estimate known containers + skin container references
            counts["containers_estimate"] = len(KNOWN_CONTAINER_IDS) + (len(skins_summary) // 15)
    except Exception as e:
        print(f"[Avertissement] Pré-détection skins : {e}")

    try:
        leg_summary = fetch_json(f"{BASE_URL}/legendary-armory/all?lang={lang}")
        counts["legendaries"] = len(leg_summary) if isinstance(leg_summary, list) else 0
    except Exception as e:
        print(f"[Avertissement] Pré-détection armurerie légendaire : {e}")

    try:
        mystic_summary = fetch_json(f"{BASE_URL}/mystic-recipes/all?lang={lang}")
        counts["mystic_recipes"] = len(mystic_summary) if isinstance(mystic_summary, list) else 0
    except Exception as e:
        print(f"[Avertissement] Pré-détection recettes mystiques : {e}")

    try:
        colors_summary = fetch_json("https://api.guildwars2.com/v2/colors")
        counts["dyes"] = len(colors_summary) if isinstance(colors_summary, list) else 0
    except Exception as e:
        print(f"[Avertissement] Pré-détection teintures : {e}")

    print("📊 --------------------------------------------------------------")
    print(f"   • Skins détectés dans la garde-robe    : {counts['skins']} skins")
    print(f"   • Caisses, boîtes et coffres détectés  : ~{counts['containers_estimate']} caisses & coffres")
    print(f"   • Armurerie Légendaire détectée         : {counts['legendaries']} objets légendaires")
    print(f"   • Recettes de la Forge Mystique          : {counts['mystic_recipes']} recettes")
    print(f"   • Teintures & Couleurs de la palette    : {counts['dyes']} teintures")
    print("--------------------------------------------------------------")
    print("✅ Pré-détection terminée. Lancement de l'extraction modulaire...\n")
    return counts

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
            containers_json TEXT,
            full_data_json TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS containers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            icon TEXT,
            is_tp_item INTEGER,
            contained_skins_json TEXT,
            full_data_json TEXT
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unlocks_tree (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_name TEXT,
            parent_type TEXT,
            children_json TEXT
        )
    """)

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

    conn.commit()
    return conn

def main():
    parser = argparse.ArgumentParser(description="Extraction complète GW2 Skins, Caisses, Légendaires, Teintures et Arbre de Déblocages")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de skins (0 pour tous)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Nombre de threads concurrents")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Chemin du fichier SQLite")
    parser.add_argument("--json", type=str, default=DEFAULT_JSON_PATH, help="Chemin du fichier JSON")
    parser.add_argument("--js", type=str, default=DEFAULT_JS_PATH, help="Chemin du fichier JS")
    parser.add_argument("--lang", type=str, default="fr", help="Langue (fr, en, de, es)")
    args = parser.parse_args()

    # Step 0: Pre-Detection Scan
    pre_detection_scan(lang=args.lang)

    print("==============================================================")
    print(f"   GW2 Scraper Modulaire - Lancement ({args.lang})")
    print("==============================================================")

    # Step 1: Module Skins
    skin_results = run_scrape_skins(limit=args.limit, workers=args.workers, lang=args.lang)

    # Step 2: Module Containers
    container_list = run_scrape_containers(skin_results, lang=args.lang)

    # Step 3: Module Legendaries
    leg_results = run_scrape_legendaries(workers=args.workers, lang=args.lang)

    # Step 4: Module Unlocks Tree Hierarchy
    unlocks_tree_list = run_scrape_unlocks_tree(skin_results, container_list, leg_results)

    # Step 5: Module Dyes
    dyes_list = run_scrape_dyes(container_results=container_list)

    # Step 6: Save to SQLite, JSON & JS
    print(f"\n[SAUVEGARDE] Enregistrement dans la base SQLite ({args.db})...")
    conn = init_sqlite_db(args.db)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM skins")
    cursor.execute("DELETE FROM containers")
    cursor.execute("DELETE FROM legendaries")
    cursor.execute("DELETE FROM unlocks_tree")
    cursor.execute("DELETE FROM dyes")

    skin_db_rows = []
    skin_json_export = []

    for sid in sorted(skin_results.keys()):
        data = skin_results[sid]
        skin_info = data.get("skin") or {}
        acq_methods = data.get("acquisitionMethods") or []
        used_in = data.get("usedIn") or []
        keywords = data.get("keywords") or ""
        skin_containers = data.get("containers") or []

        s_name = skin_info.get("name", "")
        s_type = skin_info.get("type", "")
        s_rarity = skin_info.get("rarity", "")
        s_icon = skin_info.get("icon", "")

        keywords_str = " ".join(keywords) if isinstance(keywords, list) else str(keywords)

        skin_db_rows.append((
            sid,
            s_name,
            s_type,
            s_rarity,
            s_icon,
            keywords_str,
            json.dumps(acq_methods, ensure_ascii=False),
            json.dumps(used_in, ensure_ascii=False),
            json.dumps(skin_containers, ensure_ascii=False),
            json.dumps(data, ensure_ascii=False)
        ))

        skin_json_export.append({
            "id": sid,
            "name": s_name,
            "type": s_type,
            "rarity": s_rarity,
            "icon": s_icon,
            "keywords": keywords,
            "acquisitionMethods": acq_methods,
            "containers": skin_containers,
            "usedIn": used_in,
            "raw": data
        })

    cursor.executemany("""
        INSERT INTO skins (id, name, type, rarity, icon, keywords, acquisition_methods_json, used_in_json, containers_json, full_data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, skin_db_rows)

    container_db_rows = []
    for c in container_list:
        container_db_rows.append((
            c["id"],
            c["name"],
            c["icon"],
            1 if c["isTpItem"] else 0,
            json.dumps(c.get("items") or [], ensure_ascii=False),
            json.dumps(c, ensure_ascii=False)
        ))

    cursor.executemany("""
        INSERT INTO containers (id, name, icon, is_tp_item, contained_skins_json, full_data_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, container_db_rows)

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

    tree_db_rows = []
    for t in unlocks_tree_list:
        tree_db_rows.append((
            t["name"],
            t["type"],
            json.dumps(t["children"], ensure_ascii=False)
        ))

    cursor.executemany("""
        INSERT INTO unlocks_tree (parent_name, parent_type, children_json)
        VALUES (?, ?, ?)
    """, tree_db_rows)

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

    full_output = {
        "skins": skin_json_export,
        "containers": container_list,
        "legendaries": leg_results,
        "unlocks_tree": unlocks_tree_list,
        "dyes": dyes_list
    }

    print(f"Sauvegarde du fichier JSON ({args.json})...")
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)

    print(f"Sauvegarde du fichier JS ({args.js})...")
    with open(args.js, "w", encoding="utf-8") as f:
        f.write("window.GW2_SKINS_DB = ")
        json.dump(full_output, f, ensure_ascii=False)
        f.write(";")

    print(f"\n==============================================================")
    print(f"Extraction et génération complètes terminées avec succès !")
    print(f"Skins : {len(skin_db_rows)} | Caisses : {len(container_db_rows)} | Légendaires : {len(leg_db_rows)} | Arbres : {len(tree_db_rows)} | Teintures : {len(dyes_db_rows)}")
    print(f"==============================================================")

if __name__ == "__main__":
    main()
