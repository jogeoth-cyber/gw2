#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 2: Extraction, classification et indexation automatique des caisses, boîtes,
coffres d'apparences avec filtres de catégories (Choice chests, Stat-selectable, Map currency, Gizmos, Black Lion)
et types de récompenses (Armes, Armures, Bijoux, Élevé, Légendaire).
"""

import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gw2.app/api/v1"
GW2_API_URL = "https://api.guildwars2.com/v2"

# Known major container IDs
KNOWN_CONTAINER_IDS = [
    106732,  # Boîte de résine chromatique
    106159,  # Boîte d'outils récupérés
    105104,  # Boîte de choix d'apparence d'arme en résine chromatique
    97889,   # Boîte de choix légendaire
    108987,  # Résine scintillante
    109782   # Cache d'armes en résine scintillante
]

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_item_details(item_id, lang="fr"):
    url = f"{BASE_URL}/items/{item_id}?lang={lang}"
    try:
        return fetch_json(url)
    except Exception:
        return None

def categorize_container(name, ctype, items):
    n_low = (name or "").lower()

    # 1. Container Category
    category = "Choice chests"
    if ctype == "Gizmo" or any(k in n_low for k in ["gizmo", "outils", "boîte de résine", "résine"]):
        category = "Container gizmos"
    elif any(k in n_low for k in ["lion noir", "black lion", "billet", "statuette"]):
        category = "Black Lion Chest rewards"
    elif any(k in n_low for k in ["monnaie", "currency", "maguuma", "contrée", "carte"]):
        category = "Map currency containers"
    elif any(k in n_low for k in ["statistique", "stats", "choix de stats", "préfixe", "berserker"]):
        category = "Stat-selectable equipment"

    # 2. Reward Type
    reward_type = "Stat-selectable weapons"
    if any(k in n_low for k in ["légendaire", "legendary"]):
        reward_type = "Legendary chests"
    elif any(k in n_low for k in ["élevé", "elevé", "ascended"]):
        reward_type = "Ascended chests"
    elif any(k in n_low for k in ["armure", "manteau", "bottes", "gants", "casque", "pantalon"]):
        reward_type = "Stat-selectable armor"
    elif any(k in n_low for k in ["bijou", "anneau", "amulette", "accessoire", "trinket"]):
        reward_type = "Stat-selectable trinkets"

    # 3. Semantic Properties
    has_stat_selection = True if (reward_type in ["Stat-selectable armor", "Stat-selectable weapons", "Stat-selectable trinkets", "Ascended chests"] or "stat" in n_low) else False

    return {
        "category": category,
        "reward_type": reward_type,
        "has_context_choice": True,
        "is_selectable_type": True,
        "has_stat_selection": has_stat_selection
    }

def scan_gw2_container_gizmo_ids(lang="fr"):
    print("[CAISSES] Détection automatique des conteneurs & gizmos (Category:Container_gizmos & items)...")
    discovered_ids = set(KNOWN_CONTAINER_IDS)

    try:
        all_ids = fetch_json(f"{GW2_API_URL}/items")
        if isinstance(all_ids, list):
            recent_ids = [i for i in all_ids if i > 75000]

            for i in range(0, len(recent_ids), 200):
                batch = recent_ids[i:i+200]
                ids_str = ",".join(map(str, batch))
                url = f"{GW2_API_URL}/items?ids={ids_str}&lang={lang}"
                try:
                    items = fetch_json(url, timeout=10)
                    for item in (items or []):
                        if not isinstance(item, dict):
                            continue
                        itype = item.get("type")
                        name = (item.get("name") or "").lower()
                        if itype in ["Gizmo", "Container"] and any(k in name for k in ["boîte", "boite", "caisse", "coffre", "pack", "choix", "cache", "conteneur"]):
                            discovered_ids.add(item.get("id"))
                except Exception:
                    pass
    except Exception as e:
        print(f"[CAISSES] Scan API GW2 secondaire : {e}")

    return list(discovered_ids)

def extract_containers_and_outputs(acq_methods, skin_info, sid):
    containers = []
    seen_ids = set()

    for m in (acq_methods or []):
        if not isinstance(m, dict):
            continue

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
                    "output_item": output_obj,
                    "type": citem.get("type", "Container")
                })

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
                            "output_item": output_obj,
                            "type": itype
                        })

    return containers

def run_scrape_containers(skin_results, lang="fr"):
    print("[CAISSES] Indexation des caisses/boîtes/coffres d'apparences...")
    container_map = {}

    # 1. Extract containers linked from skins
    for sid, sdata in skin_results.items():
        sinfo = sdata.get("skin") or {}
        acq_methods = sdata.get("acquisitionMethods") or []

        skin_containers = extract_containers_and_outputs(acq_methods, sinfo, sid)
        sdata["containers"] = skin_containers

        for c in skin_containers:
            cid = c["id"]
            if cid not in container_map:
                container_map[cid] = {
                    "id": cid,
                    "name": c["name"],
                    "icon": c["icon"],
                    "type": c.get("type", "Container"),
                    "isTpItem": c["isTpItem"],
                    "description": c.get("description", ""),
                    "items": []
                }

            out_obj = c.get("output_item")
            if out_obj and isinstance(out_obj, dict):
                if not any(it.get("name") == out_obj.get("name") for it in container_map[cid]["items"]):
                    container_map[cid]["items"].append(out_obj)

    # 2. Discover and fetch Container/Gizmo choice items
    discovered_ids = scan_gw2_container_gizmo_ids(lang=lang)
    missing_ids = [cid for cid in discovered_ids if cid not in container_map or len(container_map[cid]["items"]) == 0]

    print(f"[CAISSES] Extraction des éléments contenus pour {len(missing_ids)} conteneur(s)/gizmo(s)...")

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_cid = {executor.submit(fetch_item_details, cid, lang): cid for cid in missing_ids}
        for future in as_completed(future_to_cid):
            cid = future_to_cid[future]
            cdata = future.result()
            if cdata and cdata.get("item"):
                item_info = cdata["item"]
                cname = item_info.get("name", "")
                cicon = item_info.get("icon", "")
                ctype = item_info.get("type", "Container")
                is_tp = item_info.get("isTpItem", False)

                if cid not in container_map:
                    container_map[cid] = {
                        "id": cid,
                        "name": cname,
                        "icon": cicon,
                        "type": ctype,
                        "isTpItem": is_tp,
                        "description": item_info.get("description", ""),
                        "items": []
                    }

                for u in (cdata.get("usedIn") or []):
                    if not isinstance(u, dict):
                        continue
                    vitem = u.get("vendoritem")
                    if isinstance(vitem, dict) and vitem.get("output_item"):
                        out = vitem["output_item"]
                        out_obj = {
                            "id": out.get("id"),
                            "name": out.get("name"),
                            "icon": out.get("icon"),
                            "rarity": out.get("rarity", "Exotic"),
                            "type": out.get("type", ""),
                            "default_skin": out.get("default_skin")
                        }
                        if not any(it.get("name") == out_obj["name"] for it in container_map[cid]["items"]):
                            container_map[cid]["items"].append(out_obj)

    # 3. Add classification tags
    container_list = []
    for cid, c in container_map.items():
        if len(c.get("items", [])) > 0 or cid in KNOWN_CONTAINER_IDS:
            tags = categorize_container(c["name"], c.get("type"), c.get("items"))
            c.update(tags)
            container_list.append(c)

    print(f"[CAISSES] Terminé: {len(container_list)} caisses/coffres d'apparences valides indexés.")
    return container_list
