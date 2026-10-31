#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 1: Extraction des skins et de leurs détails depuis GW2.app API.
Version hardenisée avec gestion d'erreurs, retry, validation, et protection des données.
"""

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gw2.app/api/v1"


def fetch_json(url, timeout=12, retries=3, backoff=1.0):
    """Télécharge et parse un JSON avec gestion robuste des erreurs."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if getattr(exc, "code", None) in (429, 500, 502, 503, 504):
                if attempt < retries:
                    time.sleep(backoff * (2 ** attempt))
                    continue
            if attempt >= retries:
                break
            time.sleep(backoff)
    raise RuntimeError(f"fetch_json() failed for {url}: {last_error}")


def fetch_skin_details(skin_id, lang="fr"):
    url = f"{BASE_URL}/skins/{skin_id}?lang={lang}"
    try:
        return fetch_json(url)
    except Exception:
        return None


def run_scrape_skins(limit=0, workers=20, lang="fr"):
    print(f"[SKINS] Récupération depuis {BASE_URL}/skins/all ({lang})...")
    try:
        all_skins_summary = fetch_json(f"{BASE_URL}/skins/all?lang={lang}")
    except Exception as exc:
        print(f"[SKINS] Erreur critique lors de la récupération du catalogue: {exc}")
        return {}

    if not isinstance(all_skins_summary, list):
        print("[SKINS] Le catalogue ne contient pas une liste valide.")
        return {}

    if limit > 0:
        all_skins_summary = all_skins_summary[:limit]

    skin_ids = [s["id"] for s in all_skins_summary if isinstance(s, dict) and "id" in s]
    print(f"[SKINS] Téléchargement des détails pour {len(skin_ids)} skins ({workers} workers)...")

    results = {}
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_id = {executor.submit(fetch_skin_details, sid, lang): sid for sid in skin_ids}
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            try:
                data = future.result()
            except Exception:
                data = None
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
