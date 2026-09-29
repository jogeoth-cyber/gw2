#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de récupération des skins (et leurs déblocages), caisses/boîtes d'apparences,
et de l'Armurerie Légendaire (recettes de craft) depuis GW2.app.
Génère une base SQLite, un fichier JSON et un fichier JavaScript (.js).
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
            containers_json TEXT,
            full_data_json TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skins_name ON skins(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skins_type ON skins(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_skins_rarity ON skins(rarity)")

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_name ON containers(name)")

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

def extract_containers_and_outputs(acq_methods, skin_info, sid, item_cache=None, lang="fr"):
    containers = []
    seen_ids = set()

    for m in (acq_methods or []):
        if not isinstance(m, dict):
            continue

        # 1. Direct containeritem in skin acquisition
        ci = m.get("containeritem")
        if isinstance(ci, dict) and ci.get("container"):
            c = ci["container"]
            cid = c.get("item_id") or c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                citem = c.get("item") if isinstance(c.get("item"), dict) else {}
                output_obj = {
                    "id": ci.get("output_item_id") or skin_info.get("id"),
                    "name": skin_info.get("name", ""),
                    "icon": skin_info.get("icon", ""),
                    "rarity": skin_info.get("rarity", "Exotic"),
                    "type": skin_info.get("type", ""),
                    "skin_id": sid
                }
                if ci.get("output_item") and isinstance(ci["output_item"], dict):
                    out = ci["output_item"]
                    output_obj["name"] = out.get("name", output_obj["name"])
                    output_obj["icon"] = out.get("icon", output_obj["icon"])
                    output_obj["rarity"] = out.get("rarity", output_obj["rarity"])
                    output_obj["default_skin"] = out.get("default_skin")

                containers.append({
                    "id": cid,
                    "name": citem.get("name") or c.get("name", "Caisse / Boîte"),
                    "icon": citem.get("icon") or c.get("icon", ""),
                    "isTpItem": citem.get("isTpItem", False),
                    "description": citem.get("description", ""),
                    "output_item": output_obj
                })

        # 2. Vendoritem with container/chest ingredients
        vitem = m.get("vendoritem")
        if isinstance(vitem, dict):
            output_obj = {
                "id": vitem.get("output_item_id") or skin_info.get("id"),
                "name": skin_info.get("name", ""),
                "icon": skin_info.get("icon", ""),
                "rarity": skin_info.get("rarity", "Exotic"),
                "type": skin_info.get("type", ""),
                "skin_id": sid
            }
            if vitem.get("output_item") and isinstance(vitem["output_item"], dict):
                out = vitem["output_item"]
                output_obj["name"] = out.get("name", output_obj["name"])
                output_obj["icon"] = out.get("icon", output_obj["icon"])
                output_obj["rarity"] = out.get("rarity", output_obj["rarity"])
                output_obj["default_skin"] = out.get("default_skin")

            for ing_item in (vitem.get("ingredient_items") or []):
                if not isinstance(ing_item, dict):
                    continue
                itype = ing_item.get("type", "")
                iname = ing_item.get("name", "")
                if itype in ["Container", "Gizmo"] or any(k in iname.lower() for k in ["boîte", "boite", "caisse", "coffre", "pack"]):
                    cid = ing_item.get("id")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        containers.append({
                            "id": cid,
                            "name": iname,
                            "icon": ing_item.get("icon", ""),
                            "isTpItem": ing_item.get("isTpItem", False),
                            "description": ing_item.get("description", ""),
                            "output_item": output_obj
                        })

        # 3. Item that itself comes from a container/box (Trace Item -> Container)
        item_obj = m.get("item")
        if isinstance(item_obj, dict):
            iid = item_obj.get("id")
            if iid and item_cache is not None:
                if iid not in item_cache:
                    item_cache[iid] = fetch_item_details(iid, lang)
                idata = item_cache.get(iid)
                if idata and isinstance(idata, dict):
                    for im in (idata.get("acquisitionMethods") or []):
                        if not isinstance(im, dict):
                            continue
                        if im.get("containeritem") and isinstance(im["containeritem"].get("container"), dict):
                            c = im["containeritem"]["container"]
                            cid = c.get("item_id") or c.get("id")
                            if cid and cid not in seen_ids:
                                seen_ids.add(cid)
                                citem = c.get("item") if isinstance(c.get("item"), dict) else {}
                                containers.append({
                                    "id": cid,
                                    "name": citem.get("name") or c.get("name", "Caisse / Boîte"),
                                    "icon": citem.get("icon") or c.get("icon", ""),
                                    "isTpItem": citem.get("isTpItem", False),
                                    "description": citem.get("description", ""),
                                    "output_item": {
                                        "id": iid,
                                        "name": item_obj.get("name", skin_info.get("name", "")),
                                        "icon": item_obj.get("icon", skin_info.get("icon", "")),
                                        "rarity": item_obj.get("rarity", "Exotic"),
                                        "type": item_obj.get("type", ""),
                                        "skin_id": sid,
                                        "default_skin": item_obj.get("default_skin")
                                    }
                                })
                        if im.get("vendoritem") and isinstance(im["vendoritem"], dict):
                            vitem_sub = im["vendoritem"]
                            for ing_sub in (vitem_sub.get("ingredient_items") or []):
                                if not isinstance(ing_sub, dict):
                                    continue
                                itype_sub = ing_sub.get("type", "")
                                iname_sub = ing_sub.get("name", "")
                                if itype_sub in ["Container", "Gizmo"] or any(k in iname_sub.lower() for k in ["boîte", "boite", "caisse", "coffre", "pack"]):
                                    cid = ing_sub.get("id")
                                    if cid and cid not in seen_ids:
                                        seen_ids.add(cid)
                                        containers.append({
                                            "id": cid,
                                            "name": iname_sub,
                                            "icon": ing_sub.get("icon", ""),
                                            "isTpItem": ing_sub.get("isTpItem", False),
                                            "description": ing_sub.get("description", ""),
                                            "output_item": {
                                                "id": iid,
                                                "name": item_obj.get("name", skin_info.get("name", "")),
                                                "icon": item_obj.get("icon", skin_info.get("icon", "")),
                                                "rarity": item_obj.get("rarity", "Exotic"),
                                                "type": item_obj.get("type", ""),
                                                "skin_id": sid,
                                                "default_skin": item_obj.get("default_skin")
                                            }
                                        })

    return containers

def main():
    parser = argparse.ArgumentParser(description="Recuperation des skins, caisses/boites et craft legendaire depuis gw2.app")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de skins (0 pour tous)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Nombre de threads concurrents")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Chemin du fichier SQLite")
    parser.add_argument("--json", type=str, default=DEFAULT_JSON_PATH, help="Chemin du fichier JSON")
    parser.add_argument("--js", type=str, default=DEFAULT_JS_PATH, help="Chemin du fichier JS")
    parser.add_argument("--lang", type=str, default="fr", help="Langue (fr, en, de, es)")
    args = parser.parse_args()

    print(f"=== GW2 Skins, Caisses & Legendary Craft Scraper ({args.lang}) ===")

    # -------------------------------------------------------------
    # PART 1: SKINS & UNLOCKS
    # -------------------------------------------------------------
    print(f"\n[1/3] Recuperation des skins depuis {BASE_URL}/skins/all...")
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

    skin_ids = [s["id"] for s in all_skins_summary if isinstance(s, dict) and "id" in s]
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
    # PART 2: CONTAINERS / CHESTS / CAISSES EXTRACTION
    # -------------------------------------------------------------
    print("\n[2/3] Indexation des caisses, boites et coffres d'apparences...")
    container_map = {}  # cid -> { id, name, icon, isTpItem, items: [] }
    item_cache = {}

    for sid, sdata in skin_results.items():
        sinfo = sdata.get("skin") or {}
        acq_methods = sdata.get("acquisitionMethods") or []

        skin_containers = extract_containers_and_outputs(acq_methods, sinfo, sid, item_cache, args.lang)
        sdata["containers"] = skin_containers

        # Map container -> list of output item objects
        for c in skin_containers:
            cid = c["id"]
            if cid not in container_map:
                container_map[cid] = {
                    "id": cid,
                    "name": c["name"],
                    "icon": c["icon"],
                    "isTpItem": c["isTpItem"],
                    "description": c.get("description", ""),
                    "items": []
                }

            out_obj = c.get("output_item")
            if out_obj and isinstance(out_obj, dict):
                if not any(it.get("name") == out_obj.get("name") for it in container_map[cid]["items"]):
                    container_map[cid]["items"].append(out_obj)

    container_list = list(container_map.values())
    print(f"Total de caisses/boites/coffres d'apparences indexes : {len(container_list)}")

    # -------------------------------------------------------------
    # PART 3: LEGENDARY ARMORY & CRAFTING
    # -------------------------------------------------------------
    print(f"\n[3/3] Recuperation des objets et recettes legendaires depuis {BASE_URL}/legendary-armory/all...")
    try:
        leg_summary = fetch_json(f"{BASE_URL}/legendary-armory/all?lang={args.lang}")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de charger l'Armurerie Légendaire: {e}")
        leg_summary = []

    print(f"Total d'objets legendaires trouves : {len(leg_summary)}")

    try:
        mystic_recipes = fetch_json(f"{BASE_URL}/mystic-recipes/all?lang={args.lang}")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de charger les recettes mystiques: {e}")
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
    with ThreadPoolExecutor(max_workers=min(args.workers, 15)) as executor:
        future_to_leg = {executor.submit(fetch_item_details, lid, args.lang): lid for lid in leg_ids}
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

    print(f"Armurerie Legendaire integree ({len(leg_results)} objets traités).")

    # -------------------------------------------------------------
    # SAVE TO SQLITE, JSON & JS
    # -------------------------------------------------------------
    print(f"\n[SAUVEGARDE] Enregistrement dans SQLite ({args.db})...")
    conn = init_sqlite_db(args.db)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM skins")
    cursor.execute("DELETE FROM containers")
    cursor.execute("DELETE FROM legendaries")

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

        acq_json = json.dumps(acq_methods, ensure_ascii=False)
        used_in_json = json.dumps(used_in, ensure_ascii=False)
        containers_json = json.dumps(skin_containers, ensure_ascii=False)
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
            containers_json,
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

    conn.commit()
    conn.close()
    print(f"Base SQLite mise a jour ({len(skin_db_rows)} skins, {len(container_db_rows)} caisses, {len(leg_db_rows)} legendaires).")

    full_output = {
        "skins": skin_json_export,
        "containers": container_list,
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
