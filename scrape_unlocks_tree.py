#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 4: Extraction de la hiérarchie Éléments Parents -> Éléments Débloqués.
Indexe pour chaque élément parent (boîte, succès, coffre) la liste complète de ses sous-éléments et skins débloqués.
"""

import json

def run_scrape_unlocks_tree(skin_results, container_list, leg_results):
    print("[HIÉRARCHIE] Génération de l'arbre Élément Parent -> Éléments Débloqués...")
    parent_map = {}  # parent_name -> { id, name, type, icon, isTpItem, children: [] }

    # 1. Map from Containers / Boxes
    for c in container_list:
        pname = c["name"]
        if pname not in parent_map:
            parent_map[pname] = {
                "id": c["id"],
                "name": pname,
                "type": "Caisse / Boîte / Coffre",
                "icon": c["icon"],
                "isTpItem": c["isTpItem"],
                "description": c.get("description", ""),
                "children": []
            }

        for item_obj in (c.get("items") or []):
            if isinstance(item_obj, dict):
                parent_map[pname]["children"].append({
                    "id": item_obj.get("id"),
                    "name": item_obj.get("name"),
                    "icon": item_obj.get("icon"),
                    "type": item_obj.get("type", "Équipement"),
                    "rarity": item_obj.get("rarity", "Exotic")
                })

    # 2. Map from Skins & Achievement Sources
    for sid, sdata in skin_results.items():
        sinfo = sdata.get("skin") or {}
        acq_methods = sdata.get("acquisitionMethods") or []

        for m in acq_methods:
            if not isinstance(m, dict):
                continue

            # Achievement as Parent Element
            ach = m.get("achievement")
            if isinstance(ach, dict) and ach.get("name"):
                aname = ach["name"]
                if aname not in parent_map:
                    parent_map[aname] = {
                        "id": ach.get("id"),
                        "name": aname,
                        "type": "🏆 Succès / Collection",
                        "icon": ach.get("icon", ""),
                        "isTpItem": False,
                        "description": ach.get("requirement") or ach.get("description", ""),
                        "children": []
                    }

                if not any(ch.get("id") == sid for ch in parent_map[aname]["children"]):
                    parent_map[aname]["children"].append({
                        "id": sid,
                        "name": sinfo.get("name", "Skin"),
                        "icon": sinfo.get("icon", ""),
                        "type": sinfo.get("type", "Skin"),
                        "rarity": sinfo.get("rarity", "Exotic")
                    })

    unlocks_tree_list = list(parent_map.values())
    print(f"[HIÉRARCHIE] Terminé: {len(unlocks_tree_list)} éléments parents et leurs arborescences de déblocage indexés.")
    return unlocks_tree_list
