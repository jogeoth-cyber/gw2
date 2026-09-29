#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 1: Extraction des skins et de leurs détails depuis GW2.app API.
"""

import urllib.request
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gw2.app/api/v1"

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

if __name__ == "__main__":
    data = run_scrape_skins(limit=10)
    print(f"Sample output: {len(data)} skins loaded.")
