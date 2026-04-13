#!/usr/bin/env python3
"""Generate 40 Indian veg recipes using vLLM, save incrementally."""
import json
import urllib.request
import ssl
import time
import concurrent.futures
import threading
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

RECIPE_FILE = "/workspace/repos/Recepti/data/recipes.json"
OUTPUT_FILE = "/workspace/repos/Recepti/data/recipes.json.new"

def call_vllm(prompt, max_tokens=4096, temperature=0.8):
    payload = {
        "model": "minimax-m2.7",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "n": 1,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://172.17.0.1:8002/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def extract_json(raw):
    try:
        choices = raw.get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return None
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:])
            content = content.replace("```", "").strip()
        arr_start = content.find("[{")
        if arr_start == -1:
            arr_start = content.find("[\n{")
        if arr_start == -1:
            return None
        return json.loads(content[arr_start:])
    except:
        return None

regions = ["Punjabi", "Gujarati", "South Indian", "Bengali", "Maharashtrian", "Rajasthani", "Kashmiri", "Chettinad"]
base_prompt = """Generate 5 different Indian vegetarian recipes (lacto-ovo, no soy, no gluten, no meat/fish). Each as JSON object:
{{"id":int,"name":str,"description":str,"ingredients":[{{"name":str,"amount":str,"unit":str}}],"instructions":[str],"tags":{{"cuisine":str,"meal_type":str,"dietary_tags":[str]}},"servings":int,"prep_time_min":int,"cook_time_min":int,"difficulty":str}}

Output ONLY JSON array. No markdown. Start with [{{"""

recipes = []
errors = []

def gen_batch(batch_num):
    offset = batch_num * 5
    prompts = [
        (f"""{base_prompt}\n\nBatch {batch_num+1}/8, Recipe {i+1}/5, ID={offset+i+1}. {regions[batch_num]} cuisine. Unique recipe.""",
         offset+i+1)
        for i in range(5)
    ]
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(call_vllm, p[0]) for p in prompts]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.time() - start
    
    batch_recipes = []
    for r in results:
        if "error" in r:
            errors.append(r["error"])
        else:
            parsed = extract_json(r)
            if parsed:
                if isinstance(parsed, list):
                    batch_recipes.extend([x for x in parsed if isinstance(x, dict) and "name" in x])
                elif isinstance(parsed, dict) and "name" in parsed:
                    batch_recipes.append(parsed)
    
    print(f"BATCH {batch_num+1} done in {elapsed:.1f}s: {len(batch_recipes)} recipes, {len(errors)} errors", flush=True)
    return batch_recipes

# Load existing if any
existing = []
try:
    with open(RECIPE_FILE) as f:
        existing = json.load(f).get("recipes", [])
    print(f"Loaded {len(existing)} existing recipes", flush=True)
except:
    pass

# Generate all batches sequentially (avoid thread explosion)
for bn in range(8):
    br = gen_batch(bn)
    for r in br:
        if r not in recipes:
            recipes.append(r)
    print(f"TOTAL so far: {len(recipes)}", flush=True)
    
    # Incremental save every 2 batches
    if bn % 2 == 1:
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"recipes": recipes[:40]}, f, indent=2)
        print(f"INCREMENTAL SAVE: {len(recipes)} recipes", flush=True)

# Final save
with open(RECIPE_FILE, "w") as f:
    json.dump({"recipes": recipes[:40]}, f, indent=2)

with open(OUTPUT_FILE, "w") as f:
    json.dump({"recipes": recipes[:40]}, f, indent=2)

names = [r.get("name") for r in recipes[:40]]
print(f"DONE. {len(recipes)} recipes saved.", flush=True)
print(f"NAMES: {names}", flush=True)
print(f"ERRORS: {errors}", flush=True)