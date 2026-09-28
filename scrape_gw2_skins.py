#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de récupération des skins et de leurs méthodes de déblocage depuis GW2.app.
Génère une base SQLite (ultra-rapide à lire) et un fichier JSON complet.
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
DEFAULT_WORKERS = 20

def fetch_json(url, timeout=10):
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
    conn.commit()
    return conn

def fetch_skin_details(skin_id, lang="fr"):
    url = f"{BASE_URL}/skins/{skin_id}?lang={lang}"
    try:
        return fetch_json(url)
    except Exception as e:
        return None

def main():
    parser = argparse.ArgumentParser(description="Recuperation des skins GW2 et modes de deblocage depuis gw2.app")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de skins (0 pour tous)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Nombre de threads concurrents")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Chemin du fichier SQLite")
    parser.add_argument("--json", type=str, default=DEFAULT_JSON_PATH, help="Chemin du fichier JSON")
    parser.add_argument("--lang", type=str, default="fr", help="Langue (fr, en, de, es)")
    args = parser.parse_args()

    print(f"=== GW2 Skin Unlocks Scraper ({args.lang}) ===")
    print(f"Recuperation de la liste complete des skins depuis {BASE_URL}/skins/all...")

    try:
        all_skins_summary = fetch_json(f"{BASE_URL}/skins/all?lang={args.lang}")
    except Exception as e:
        print(f"[ERREUR] Impossible de charger la liste des skins: {e}")
        sys.exit(1)

    total_skins = len(all_skins_summary)
    print(f"Total de skins trouves dans la base : {total_skins}")

    if args.limit > 0:
        all_skins_summary = all_skins_summary[:args.limit]
        print(f"Limitation appliquee : {len(all_skins_summary)} skins")

    skin_ids = [s["id"] for s in all_skins_summary if "id" in s]

    print(f"Recuperation des details et debloquages pour {len(skin_ids)} skins ({args.workers} workers)...")

    results = {}
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_id = {executor.submit(fetch_skin_details, sid, args.lang): sid for sid in skin_ids}
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            data = future.result()
            completed += 1
            if data:
                results[sid] = data
            if completed % 500 == 0 or completed == len(skin_ids):
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"Progression: {completed}/{len(skin_ids)} ({completed*100/len(skin_ids):.1f}%) - {rate:.1f} skins/sec")

    print(f"Telechargement termine en {time.time() - t0:.2f} seconds. Skins recupere: {len(results)}")

    # Enregistrement dans SQLite
    print(f"Sauvegarde dans la base SQLite : {args.db}...")
    conn = init_sqlite_db(args.db)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM skins")  # Purge old data

    db_rows = []
    json_export = []

    for sid in sorted(results.keys()):
        data = results[sid]
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

        db_rows.append((
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

        json_export.append({
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
    """, db_rows)
    conn.commit()
    conn.close()
    print(f"Base SQLite enregistree avec succes ({len(db_rows)} entrees).")

    # Enregistrement dans JSON
    print(f"Sauvegarde dans le fichier JSON : {args.json}...")
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(json_export, f, ensure_ascii=False, indent=2)
    print(f"Fichier JSON enregistre avec succes ({os.path.getsize(args.json) / (1024*1024):.2f} MB).")
    print("Operation terminee avec succes!")

if __name__ == "__main__":
    main()
