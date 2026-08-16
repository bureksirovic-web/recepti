#!/usr/bin/env python3
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent / ".env"))

from recepti.llm_service import call_openrouter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INPUT_FILE  = Path(__file__).parent / "data" / "croatia_ingredients.json"
OUTPUT_FILE = Path(__file__).parent / "data" / "croatia_ingredients_v2.json"

CATEGORY_ORDER = ["vegetables", "legumes", "grains", "dairy", "eggs", "nuts_seeds", "pantry", "fruits"]

def load_input():
    with open(INPUT_FILE) as f:
        return json.load(f)

def save_partial(data):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def translate_batch_prompt(items, start_idx, batch_num):
    items_json = json.dumps(items, ensure_ascii=False)
    prompt = f"""Translate each ingredient name from English to Croatian.
Use accurate food terminology for Croatian/Mediterranean cuisine.
Return ONLY valid JSON (no markdown, no explanation) with this structure:
{{"translations": [{{"index": 0, "english": "...", "croatian": "..."}}, ...]}}

List of {len(items)} ingredients to translate (global index from {start_idx}):
{items_json}

RESPOND WITH ONLY JSON."""
    max_tokens = min(200 + len(items) * 80, 4000)
    try:
        raw = call_openrouter(prompt, model="google/gemma-4-26b-a4b-it:free", temperature=0.0, max_tokens=max_tokens)
        raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"^```\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.IGNORECASE)
        logger.info(f"Batch {batch_num} raw (first 200): {raw[:200]}")
        parsed = json.loads(raw)
        return {item["index"]: item["croatian"] for item in parsed["translations"]}
    except Exception as e:
        logger.error(f"Batch {batch_num} failed: {e}")
        raise

def main():
    data = load_input()
    output = {"version": 2, "categories": {}}

    all_items = []
    for cat in CATEGORY_ORDER:
        for name in data["categories"][cat]:
            all_items.append(name)
    logger.info(f"Total ingredients: {len(all_items)}")

    BATCH_SIZE = 20
    start_idx = 0
    batch_num = 0
    translations = {}

    while start_idx < len(all_items):
        batch_num += 1
        end_idx = min(start_idx + BATCH_SIZE, len(all_items))
        batch = all_items[start_idx:end_idx]
        logger.info(f"=== Batch {batch_num}: items {start_idx}–{end_idx-1} ({len(batch)} items) ===")

        attempts = 0
        while attempts < 5:
            try:
                result = translate_batch_prompt(batch, start_idx, batch_num)
                for i, cro in result.items():
                    idx = start_idx + int(i)
                    if idx < len(all_items):
                        translations[idx] = cro
                break
            except Exception as e:
                attempts += 1
                if "429" in str(e):
                    logger.warning(f"Batch {batch_num} 429 — wait 60s retry {attempts}/5")
                    time.sleep(60)
                else:
                    logger.warning(f"Batch {batch_num} error — wait 30s retry {attempts}/5")
                    time.sleep(30)
        if attempts == 5:
            logger.error(f"Batch {batch_num} exhausted — fill with originals")
            for i, item in enumerate(batch):
                translations[start_idx + i] = item

        start_idx = end_idx
        if start_idx < len(all_items):
            time.sleep(20)

    idx = 0
    for cat in CATEGORY_ORDER:
        cat_items = data["categories"][cat]
        output["categories"][cat] = [
            {"name": name, "croatian_name": translations[idx + i].strip()}
            for i, name in enumerate(cat_items)
        ]
        idx += len(cat_items)

    save_partial(output)
    logger.info(f"Done — {len(all_items)} ingredients written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
