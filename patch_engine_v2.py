"""
patch_engine_v2.py — Apply the totals/BTTS market_odds fix (line-based)
=========================================================================
Run from your World Cup MOdel folder:
    python patch_engine_v2.py
"""

with open("predictions/predictions_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the block: starts with "# Totals 2.5" comment, ends after the
# closing "}" of market["totals_2_5"] = {...}
start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if "Totals 2.5" in line or "# Totals" in line:
        start_idx = i
        break

if start_idx is None:
    print("ERROR: Could not find start of totals block (looked for '# Totals' comment)")
    print("Showing lines 210-230 for inspection:")
    for i in range(209, min(230, len(lines))):
        print(f"{i+1}: {lines[i]}", end="")
    raise SystemExit(1)

# Find the end: the line containing 'market["totals_2_5"] = {' then find its closing brace
totals_25_idx = None
for i in range(start_idx, min(start_idx + 20, len(lines))):
    if 'market["totals_2_5"]' in lines[i]:
        totals_25_idx = i
        break

if totals_25_idx is None:
    print("ERROR: Could not find 'market[\"totals_2_5\"]' line after start")
    raise SystemExit(1)

# Find the closing brace for this dict (next line with just "}" at similar indent)
end_idx = None
for i in range(totals_25_idx + 1, min(totals_25_idx + 10, len(lines))):
    stripped = lines[i].strip()
    if stripped == "}":
        end_idx = i
        break

if end_idx is None:
    print("ERROR: Could not find closing brace for totals_2_5 dict")
    raise SystemExit(1)

print(f"Found block: lines {start_idx+1} to {end_idx+1}")
print("--- OLD BLOCK ---")
for i in range(start_idx, end_idx+1):
    print(f"{i+1}: {lines[i]}", end="")

# Build replacement block (matching indentation of original)
indent = "        "  # 8 spaces, standard for this method's body

new_block = f'''{indent}# Totals -- prefer 2.5 if available, otherwise use whichever
{indent}# line the bookmakers have actually posted (e.g. 3.0, 2.25).
{indent}lines_by_value = {{}}
{indent}for line_key, line_data in totals_block.items():
{indent}    if line_key in ("btts_yes", "btts_no"):
{indent}        continue
{indent}    lk = line_key.lower()
{indent}    try:
{indent}        if "_over" in lk:
{indent}            val = float(lk.replace("_over", ""))
{indent}            side = "over"
{indent}        elif "_under" in lk:
{indent}            val = float(lk.replace("_under", ""))
{indent}            side = "under"
{indent}        else:
{indent}            continue
{indent}    except ValueError:
{indent}        continue
{indent}    lines_by_value.setdefault(val, {{}})[side] = line_data.get("best_decimal")

{indent}if lines_by_value:
{indent}    if 2.5 in lines_by_value:
{indent}        chosen_val = 2.5
{indent}    else:
{indent}        chosen_val = min(lines_by_value.keys(), key=lambda v: abs(v - 2.5))
{indent}    chosen = lines_by_value[chosen_val]
{indent}    over_v  = chosen.get("over")
{indent}    under_v = chosen.get("under")
{indent}    if over_v or under_v:
{indent}        market["totals"] = {{
{indent}            "line":  chosen_val,
{indent}            "over":  round(over_v, 2) if over_v else None,
{indent}            "under": round(under_v, 2) if under_v else None,
{indent}        }}
'''

# Replace lines[start_idx:end_idx+1] with new_block
new_lines = lines[:start_idx] + [new_block] + lines[end_idx+1:]

with open("predictions/predictions_engine.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("\nSUCCESS: predictions_engine.py patched.")
print('Verify with: findstr lines_by_value predictions\\predictions_engine.py')
