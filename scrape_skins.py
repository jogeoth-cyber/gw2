#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 1: Extraction des skins et de leurs détails depuis GW2.app API.
Peut être exécuté de manière autonome (`python scrape_skins.py`).
"""

import os
import sqlite3
import urllib.request
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gw2.app/api/v1"
DEFAULT_DB_PATH = "gw2_skins_unlocks.db"
DEFAULT_JSON_PATH = "gw2_skins_unlocks.json"
DEFAULT_JS_PATH = "gw2_skins_unlocks.js"

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_skin_details(skin_id, lang="fr"):
    url = f"{BASE_URL}/skins/{skin_id}?lang={lang}"
    try:
        return fetch_json(url)
    except Exception:
        return None

def run_scrape_skins(limit=0, workers=20, lang="fr"):
    print(f"[SKINS] Récupération depuis {BASE_URL}/skins/all ({lang})...")
    all_skins_summary = fetch_json(f"{BASE_URL}/skins/all?lang={lang}")

    if limit > 0:
        all_skins_summary = all_skins_summary[:limit]

    skin_ids = [s["id"] for s in all_skins_summary if isinstance(s, dict) and "id" in s]
    print(f"[SKINS] Téléchargement des détails pour {len(skin_ids)} skins ({workers} workers)...")

    results = {}
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_id = {executor.submit(fetch_skin_details, sid, lang): sid for sid in skin_ids}
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            data = future.result()
            completed += 1
            if data:
                results[sid] = data
            if completed % 500 == 0 or completed == len(skin_ids):
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"[SKINS] Progression: {completed}/{len(skin_ids)} - {rate:.1f} skins/sec")

    print(f"[SKINS] Terminé: {len(results)} skins extraits en {time.time()-t0:.2f}s.")
    return results

def save_standalone(skin_results):
    """Enregistre les résultats de manière autonome."""
    skin_json_export = []
    skin_db_rows = []

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

    existing_data = {"skins": [], "containers": [], "legendaries": [], "unlocks_tree": [], "dyes": []}
    if os.path.exists(DEFAULT_JSON_PATH):
        try:
            with open(DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass

    existing_data["skins"] = skin_json_export

    print(f"[SKINS] Enregistrement autonome dans {DEFAULT_JSON_PATH} et {DEFAULT_JS_PATH}...")
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
            cursor.execute("DELETE FROM skins")
            cursor.executemany("""
                INSERT INTO skins (id, name, type, rarity, icon, keywords, acquisition_methods_json, used_in_json, containers_json, full_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, skin_db_rows)
            conn.commit()
            conn.close()
            print(f"[SKINS] Lignes mises à jour dans SQLite ({len(skin_db_rows)}).")
        except Exception as e:
            print(f"[SKINS] Erreur SQLite: {e}")

if __name__ == "__main__":
    data = run_scrape_skins(limit=0)
    save_standalone(data)
    print("Extraction autonome des skins terminée.")
