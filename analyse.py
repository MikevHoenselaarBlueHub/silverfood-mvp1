\
import json, re
from recipe_scrapers import scrape_me
from rapidfuzz import process, fuzz

# Laad vervanglijst
with open("substitutions.json", encoding="utf-8") as f:
    SUBS = json.load(f)

# Heel simpele hoeveelheid-parser (alleen g/ml/l)
def parse_qty(line: str):
    pattern = r"([\d/.]+)\s*(g|gram|ml|l)?\s*(.*)"
    m = re.match(pattern, line.lower())
    if not m:
        return None, None, line.lower()
    amount = eval(m.group(1))
    unit   = m.group(2) or "g"
    name   = m.group(3).strip()
    return amount, unit, name

def find_substitution(name: str):
    # fuzzy-match tegen de keys uit substitutions
    key = process.extractOne(name, SUBS.keys(), scorer=fuzz.WRatio, score_cutoff=85)
    return SUBS[key[0]] if key else None

def analyse(url: str):
    scraper = scrape_me(url, wild_mode=True)
    swaps = []
    for line in scraper.ingredients():
        _, _, name = parse_qty(line)
        alt = find_substitution(name)
        if alt:
            swaps.append({"ongezond_ingredient": name, "vervang_door": alt})
    return swaps

if __name__ == "__main__":
    import sys, pprint
    pprint.pp(analyse(sys.argv[1]))
