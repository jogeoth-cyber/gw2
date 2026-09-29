#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Principal d'Orchestration:
Exécute de manière modulaire les 4 scripts d'extraction:
- Module 1: scrape_skins.py (Skins & détails)
- Module 2: scrape_containers.py (Caisses, coffres, boîtes d'apparences)
- Module 3: scrape_legendaries.py (Armurerie Légendaire & recettes de craft)
- Module 4: scrape_unlocks_tree.py (Hiérarchie Élément Parent -> Arbre de Déblocage)

Exporte vers SQLite, JSON et JavaScript.
"""

import os
import sys
import json
import sqlite3
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrape_skins import run_scrape_skins
from scrape_containers import run_scrape_containers
from scrape_legendaries import run_scrape_legendaries
from scrape_unlocks_tree import run_scrape_unlocks_tree

DEFAULT_DB_PATH = "gw2_skins_unlocks.db"
DEFAULT_JSON_PATH = "gw2_skins_unlocks.json"
DEFAULT_JS_PATH = "gw2_skins_unlocks.js"
DEFAULT_WORKERS = 20

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

    conn.commit()
    return conn

def main():
    parser = argparse.ArgumentParser(description="Extraction complète GW2 Skins, Caisses, Légendaires et Arbre de Déblocages")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de skins (0 pour tous)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Nombre de threads concurrents")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Chemin du fichier SQLite")
    parser.add_argument("--json", type=str, default=DEFAULT_JSON_PATH, help="Chemin du fichier JSON")
    parser.add_argument("--js", type=str, default=DEFAULT_JS_PATH, help="Chemin du fichier JS")
    parser.add_argument("--lang", type=str, default="fr", help="Langue (fr, en, de, es)")
    args = parser.parse_args()

    print("==============================================================")
    print(f"   GW2 Scraper Modulaire ({args.lang})")
    print("==============================================================")

    # Step 1: Module Skins
    skin_results = run_scrape_skins(limit=args.limit, workers=args.workers, lang=args.lang)

    # Step 2: Module Containers
    container_list = run_scrape_containers(skin_results, lang=args.lang)

    # Step 3: Module Legendaries
    leg_results = run_scrape_legendaries(workers=args.workers, lang=args.lang)

    # Step 4: Module Unlocks Tree Hierarchy
    unlocks_tree_list = run_scrape_unlocks_tree(skin_results, container_list, leg_results)

    # Step 5: Save to SQLite, JSON & JS
    print(f"\n[SAUVEGARDE] Enregistrement dans la base SQLite ({args.db})...")
    conn = init_sqlite_db(args.db)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM skins")
    cursor.execute("DELETE FROM containers")
    cursor.execute("DELETE FROM legendaries")
    cursor.execute("DELETE FROM unlocks_tree")

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

    conn.commit()
    conn.close()

    full_output = {
        "skins": skin_json_export,
        "containers": container_list,
        "legendaries": leg_results,
        "unlocks_tree": unlocks_tree_list
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
    print(f"Skins : {len(skin_db_rows)} | Caisses : {len(container_db_rows)} | Légendaires : {len(leg_db_rows)} | Arbres de déblocages : {len(tree_db_rows)}")
    print(f"==============================================================")

if __name__ == "__main__":
    main()
