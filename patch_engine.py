"""
patch_engine.py — Apply the totals/BTTS market_odds fix directly
==================================================================
Run from your World Cup MOdel folder:
    python patch_engine.py
"""

with open("predictions/predictions_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """        # Totals 2.5 (over/under)
        over_25 = None
        under_25 = None
        for line_key, line_data in totals_block.items():
            lk = line_key.lower()
            if "2.5" in lk and "over" in lk:
                over_25 = line_data.get("best_decimal")
            elif "2.5" in lk and "under" in lk:
                under_25 = line_data.get("best_decimal")
        
        if over_25 or under_25:
            market["totals_2_5"] = {
                "over":  round(over_25, 2) if over_25 else None,
                "under": round(under_25, 2) if under_25 else None,
            }"""

new = """        # Totals -- prefer 2.5 if available, otherwise use whichever
        # line the bookmakers have actually posted (e.g. 3.0, 2.25).
        lines_by_value = {}
        for line_key, line_data in totals_block.items():
            if line_key in ("btts_yes", "btts_no"):
                continue
            lk = line_key.lower()
            try:
                if "_over" in lk:
                    val = float(lk.replace("_over", ""))
                    side = "over"
                elif "_under" in lk:
                    val = float(lk.replace("_under", ""))
                    side = "under"
                else:
                    continue
            except ValueError:
                continue
            lines_by_value.setdefault(val, {})[side] = line_data.get("best_decimal")

        if lines_by_value:
            if 2.5 in lines_by_value:
                chosen_val = 2.5
            else:
                chosen_val = min(lines_by_value.keys(), key=lambda v: abs(v - 2.5))
            chosen = lines_by_value[chosen_val]
            over_v  = chosen.get("over")
            under_v = chosen.get("under")
            if over_v or under_v:
                market["totals"] = {
                    "line":  chosen_val,
                    "over":  round(over_v, 2) if over_v else None,
                    "under": round(under_v, 2) if under_v else None,
                }"""

if old not in content:
    print("ERROR: Could not find the old code block to replace.")
    print("The file may have already been patched, or differs from expected.")
else:
    content = content.replace(old, new)
    with open("predictions/predictions_engine.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: predictions_engine.py patched.")
    print("Verify with: findstr lines_by_value predictions\\predictions_engine.py")
