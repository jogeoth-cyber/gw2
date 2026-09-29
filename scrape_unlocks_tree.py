#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 4: Extraction et construction de l'arborescence multi-niveaux indéfinie
(Enfant -> Parent -> Grand-Parent -> Racine).
Trace tous les niveaux de parents jusqu'au sommet (succès, collections, coffres, marchand).
"""

import json

def get_ancestor_chain(child_name, child_to_parents, visited=None):
    if visited is None:
        visited = set()
    if child_name in visited:
        return []
    visited.add(child_name)

    parents = child_to_parents.get(child_name, [])
    if not parents:
        return []

    chain = []
    for p in parents:
        parent_obj = {
            "id": p.get("id"),
            "name": p.get("name"),
            "type": p.get("type", "Parent"),
            "icon": p.get("icon", ""),
            "description": p.get("description", "")
        }
        # Trace higher levels recursively
        grandparents = get_ancestor_chain(p.get("name"), child_to_parents, visited.copy())
        if grandparents:
            parent_obj["higher_parents"] = grandparents
        chain.append(parent_obj)

    return chain

def run_scrape_unlocks_tree(skin_results, container_list, leg_results):
    print("[HIÉRARCHIE] Construction de la carte multi-niveaux d'ascendance indéfinie...")

    child_to_parents = {}  # child_name -> list of parent dicts
    element_catalog = {}   # element_name -> dict

    # 1. Register Containers / Boxes as Parents
    for c in container_list:
        pname = c["name"]
        p_obj = {
            "id": c["id"],
            "name": pname,
            "type": "📦 Caisse / Boîte / Coffre",
            "icon": c["icon"],
            "isTpItem": c["isTpItem"],
            "description": c.get("description", "")
        }
        element_catalog[pname] = p_obj

        for item_obj in (c.get("items") or []):
            if isinstance(item_obj, dict):
                cname = item_obj.get("name")
                if cname:
                    if cname not in child_to_parents:
                        child_to_parents[cname] = []
                    if not any(p["name"] == pname for p in child_to_parents[cname]):
                        child_to_parents[cname].append(p_obj)

                    element_catalog[cname] = {
                        "id": item_obj.get("id"),
                        "name": cname,
                        "type": item_obj.get("type", "Équipement"),
                        "icon": item_obj.get("icon", ""),
                        "rarity": item_obj.get("rarity", "Exotic")
                    }

    # 2. Register Achievements & Collections as Higher Parents
    for sid, sdata in skin_results.items():
        sinfo = sdata.get("skin") or {}
        sname = sinfo.get("name")
        if not sname:
            continue

        element_catalog[sname] = {
            "id": sid,
            "name": sname,
            "type": sinfo.get("type", "Skin"),
            "icon": sinfo.get("icon", ""),
            "rarity": sinfo.get("rarity", "Exotic")
        }

        acq_methods = sdata.get("acquisitionMethods") or []
        for m in acq_methods:
            if not isinstance(m, dict):
                continue

            # Achievement / Collection parent
            ach = m.get("achievement")
            if isinstance(ach, dict) and ach.get("name"):
                aname = ach["name"]
                ach_parent_obj = {
                    "id": ach.get("id"),
                    "name": aname,
                    "type": "🏆 Succès / Collection",
                    "icon": ach.get("icon", ""),
                    "description": ach.get("requirement") or ach.get("description", "")
                }
                element_catalog[aname] = ach_parent_obj

                if sname not in child_to_parents:
                    child_to_parents[sname] = []
                if not any(p["name"] == aname for p in child_to_parents[sname]):
                    child_to_parents[sname].append(ach_parent_obj)

            # Item source -> check vendoritem/collection
            vitem = m.get("vendoritem")
            if isinstance(vitem, dict):
                col = vitem.get("collection")
                if col:
                    col_parent_obj = {
                        "id": vitem.get("collection_achievement_id"),
                        "name": col,
                        "type": "📜 Collection",
                        "icon": "https://render.guildwars2.com/file/20177B180A6D55C4587C95E2BEE86A6A94F40966/866107.png",
                        "description": f"Collection liée à : {col}"
                    }
                    element_catalog[col] = col_parent_obj

                    # Link container or item to collection
                    for ing in (vitem.get("ingredient_items") or []):
                        if isinstance(ing, dict) and ing.get("name"):
                            ing_name = ing["name"]
                            if ing_name not in child_to_parents:
                                child_to_parents[ing_name] = []
                            if not any(p["name"] == col for p in child_to_parents[ing_name]):
                                child_to_parents[ing_name].append(col_parent_obj)

    # 3. Compute full multi-level parent chains for all catalog elements
    multi_level_tree = []
    for ename, elem in element_catalog.items():
        ancestors = get_ancestor_chain(ename, child_to_parents)
        children = [
            {"name": cname, "details": element_catalog.get(cname, {})}
            for cname, plist in child_to_parents.items()
            if any(p["name"] == ename for p in plist)
        ]

        multi_level_tree.append({
            "id": elem.get("id"),
            "name": ename,
            "type": elem.get("type", "Élément"),
            "icon": elem.get("icon", ""),
            "rarity": elem.get("rarity", "Exotic"),
            "description": elem.get("description", ""),
            "isTpItem": elem.get("isTpItem", False),
            "ancestors_chain": ancestors,  # Full multi-level parents upward
            "children": children            # Direct child elements downward
        })

    print(f"[HIÉRARCHIE] Terminé: {len(multi_level_tree)} éléments avec leurs chaînes de parents multiniveaux indexés.")
    return multi_level_tree
