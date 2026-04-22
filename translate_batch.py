import json
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from recepti.llm_service import translate_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RECIPE_FILE = Path(__file__).parent / "data" / "recipes.json"

GLOSSARY = [
    "dal", "spanakopita", "moussaka", "tzatziki", "burek", "ćevapi",
    "pašticada", "fišpek", "baklava", "sarajevski burek", "burek sa sirom",
    "gibanica", "zeljanik", "sarma", "grašković", "begavi corba",
    "kibbeh", "falafel", "shakshuka", "tagine", "Fiš-paštić", "čobanac",
    "brudet", "fiš paprikaš", "štrukli", "štrudla", "kremšnite", "buhtle",
    "fižol", "pašteta", "lećenik",
]

BATCH_SIZE = 10
MAX_RECIPES = 30


def build_batch_prompt(recipes_batch):
    lines = []
    for r in recipes_batch:
        lines.append(f"Name: {r['name']}")
        lines.append(f"Description: {r['description']}")
        lines.append("")
    return "\n".join(lines).strip()


def parse_translated_batch(raw_text, count):
    blocks = []
    current = None
    for line in raw_text.strip().splitlines():
        line = line.rstrip()
        if line.lower().startswith("name:"):
            if current is not None:
                blocks.append(current)
            current = {"name": line.split(":", 1)[1].strip(), "description": ""}
        elif line.lower().startswith("description:"):
            if current is not None:
                current["description"] = line.split(":", 1)[1].strip()
        elif current is not None:
            if current["description"]:
                current["description"] += " " + line.strip()
            elif current["name"]:
                current["description"] = line.strip()
    if current is not None:
        blocks.append(current)

    if len(blocks) < count:
        blocks = []
        parts = raw_text.strip().split("\n\n")
        for p in parts:
            p = p.strip()
            if not p:
                continue
            name_val, desc_val = "", ""
            for lp in p.splitlines():
                lp_lower = lp.lower()
                if lp_lower.startswith("name:"):
                    name_val = lp.split(":", 1)[1].strip()
                elif lp_lower.startswith("description:"):
                    desc_val = lp.split(":", 1)[1].strip()
            if name_val or desc_val:
                blocks.append({"name": name_val, "description": desc_val})

    while len(blocks) < count:
        blocks.append({"name": "", "description": ""})

    return blocks[:count]


def translate_batch(recipes_batch, attempt=1):
    prompt_text = build_batch_prompt(recipes_batch)
    logger.info(f"  -- Batch has {len(recipes_batch)} recipes --")

    instruction = (
        'Translate each recipe Name and Description to Croatian. '
        "Preserve capitalization for proper nouns. "
        "Keep dish names exact (dal, spanakopita, moussaka, tzatziki, burek, ćevapi, "
        "pašticada, fišpek, baklava, gibanica, zeljanik, sarma, etc.) unchanged. "
        "Output each block as:\n"
        "Name: <translated name>\n"
        "Description: <translated description>\n\n"
        "BEGIN:\n"
        + prompt_text
    )

    try:
        raw = translate_text(
            instruction,
            target_lang="Croatian",
            source_lang="English",
            glossary=GLOSSARY,
        )
        logger.info(f"  -- Raw response (first 300 chars): {raw[:300]} --")
        blocks = parse_translated_batch(raw, len(recipes_batch))
        return blocks
    except Exception as e:
        logger.error(f"  -- Translation failed (attempt {attempt}): {e} --")
        if attempt < 2:
            time.sleep(3)
            return translate_batch(recipes_batch, attempt=attempt + 1)
        return [{"name": "", "description": ""} for _ in recipes_batch]


def main():
    with open(RECIPE_FILE) as f:
        data = json.load(f)

    recipes = data["recipes"]
    logger.info(f"Loaded {len(recipes)} recipes total")

    to_translate = recipes[:MAX_RECIPES]
    logger.info(f"Translating first {MAX_RECIPES} recipes in batches of {BATCH_SIZE}")

    for i in range(0, MAX_RECIPES, BATCH_SIZE):
        batch = to_translate[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"=== Batch {batch_num} (recipes {i+1}–{i+len(batch)}) ===")
        blocks = translate_batch(batch)
        for j, (r, block) in enumerate(zip(batch, blocks)):
            r["name_croatian"] = block["name"].strip()
            r["description_croatian"] = block["description"].strip()
            logger.info(f"  [{i+j+1}] {r['name']} -> {r['name_croatian']}")
            logger.info(f"       desc -> {r['description_croatian'][:80]}")
        time.sleep(1)

    with open(RECIPE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Written enriched data/recipes.json")

    with open(RECIPE_FILE) as f:
        verify = json.load(f)
    total = len(verify["recipes"])
    missing_name = sum(1 for r in verify["recipes"] if "name_croatian" not in r)
    missing_desc = sum(1 for r in verify["recipes"] if "description_croatian" not in r)
    print(f"\n=== VERIFICATION ===")
    print(f"Recipes: {total}")
    print(f"Missing name_croatian: {missing_name}")
    print(f"Missing description_croatian: {missing_desc}")
    sample = verify["recipes"][0].get("name_croatian", "MISSING")
    print(f"Sample: {sample}")
    if missing_name == 0 and missing_desc == 0:
        print("PASS -- all fields present")
    else:
        print("FAIL -- some fields missing")
        sys.exit(1)


if __name__ == "__main__":
    main()
