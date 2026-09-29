#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 2: Extraction et indexation des caisses, boîtes, coffres d'apparences et de leurs éléments contenus.
"""

import urllib.request
import json

BASE_URL = "https://gw2.app/api/v1"

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
                    "output_item": output_obj
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
                            "output_item": output_obj
                        })

    return containers

def run_scrape_containers(skin_results, lang="fr"):
    print("[CAISSES] Indexation des caisses/boîtes/coffres à partir des skins...")
    container_map = {}

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
                    "isTpItem": c["isTpItem"],
                    "description": c.get("description", ""),
                    "items": []
                }

            out_obj = c.get("output_item")
            if out_obj and isinstance(out_obj, dict):
                if not any(it.get("name") == out_obj.get("name") for it in container_map[cid]["items"]):
                    container_map[cid]["items"].append(out_obj)

    # Check known major containers
    container_ids_to_check = [106159]
    for cid in container_ids_to_check:
        if cid not in container_map or len(container_map[cid]["items"]) <= 1:
            cdata = fetch_item_details(cid, lang)
            if cdata and cdata.get("item"):
                item_info = cdata["item"]
                outputs = []
                for u in (cdata.get("usedIn") or []):
                    vitem = u.get("vendoritem")
                    if vitem and vitem.get("output_item"):
                        out = vitem["output_item"]
                        outputs.append({
                            "id": out.get("id"),
                            "name": out.get("name"),
                            "icon": out.get("icon"),
                            "rarity": out.get("rarity", "Exotic"),
                            "type": out.get("type", ""),
                            "default_skin": out.get("default_skin")
                        })

                container_map[cid] = {
                    "id": cid,
                    "name": item_info.get("name", ""),
                    "icon": item_info.get("icon", ""),
                    "isTpItem": item_info.get("isTpItem", False),
                    "description": item_info.get("description", ""),
                    "items": outputs
                }

    container_list = list(container_map.values())
    print(f"[CAISSES] Terminé: {len(container_list)} caisses/coffres indexés.")
    return container_list
