#!/usr/bin/env python3
"""Generate 40 Indian veg recipes using vLLM with JSON mode."""
import json, urllib.request, ssl, time, concurrent.futures, sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

RECIPE_FILE = "/workspace/repos/Recepti/data/recipes.json"

def call_vllm(prompt):
    payload = {
        "model": "minimax-m2.7",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
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

def extract_json(text):
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        text = text.replace("```", "").strip()
    # Strip surrounding braces if it's wrapped
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict) and "recipes" in obj:
            return obj["recipes"]
        return obj
    except:
        pass
    # Try finding array
    import re
    m = re.search(r'\[.+?\]', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            pass
    return None

cuisines = ["Punjabi", "Gujarati", "South Indian", "Bengali", "Maharashtrian", "Rajasthani", "Kashmiri", "Chettinad"]
base_prompt = """Generate 5 different Indian vegetarian recipes (lacto-ovo, no soy, no gluten, no meat/fish). Output a JSON object with a "recipes" key containing the array. Each recipe has:
- id (1-40)
- name
- description
- ingredients: [{"name":str,"amount":str,"unit":str}]
- instructions: [str]
- tags: {"cuisine":str,"meal_type":str,"dietary_tags":[str]}
- servings
- prep_time_min
- cook_time_min
- difficulty ("Easy"|"Medium"|"Hard")

Cover these cuisines: {cuisines}. Make each authentic. Output JSON object with "recipes" array."""

recipes = []
errors = []

# Generate in batches of 5
for batch_num in range(8):
    cuisine_batch = cuisines[batch_num]
    prompt = f"""Generate 5 different Indian vegetarian recipes. {cuisine_batch} cuisine. Output JSON: {{"recipes": [{{"id":N,"name":"...","description":"...","ingredients":[{{"name":"...","amount":"...","unit":"..."}}],"instructions":["..."],"tags":{{"cuisine":"{cuisine_batch}","meal_type":"...","dietary_tags":["vegetarian"]}},"servings":4,"prep_time_min":15,"cook_time_min":30,"difficulty":"Easy"}}]}}"""

    print(f"Generating batch {batch_num+1}/8 ({cuisine_batch})...", flush=True)
    start = time.time()
    raw = call_vllm(prompt)
    elapsed = time.time() - start
    
    if "error" in raw:
        print(f"  ERROR: {raw['error']}", flush=True)
        errors.append(raw["error"])
        continue
    
    msg = raw["choices"][0]["message"]
    content = msg.get("content", "")
    print(f"  Content: {len(content)} chars in {elapsed:.1f}s", flush=True)
    
    parsed = extract_json(content)
    if parsed:
        if isinstance(parsed, list):
            for r in parsed:
                if isinstance(r, dict) and "name" in r and r not in recipes:
                    recipes.append(r)
        elif isinstance(parsed, dict) and "recipes" in parsed:
            for r in parsed["recipes"]:
                if isinstance(r, dict) and "name" in r and r not in recipes:
                    recipes.append(r)
        print(f"  Total unique recipes: {len(recipes)}", flush=True)
    else:
        print(f"  PARSE FAILED: {content[:200]}", flush=True)
        errors.append(f"batch {batch_num+1} parse failed")

# Dedupe by id
seen_ids = set()
deduped = []
for r in recipes:
    rid = r.get("id")
    if rid not in seen_ids:
        seen_ids.add(rid)
        deduped.append(r)

# Sort by id
deduped.sort(key=lambda x: x.get("id", 99))

# Re-assign sequential IDs if needed
for i, r in enumerate(deduped):
    r["id"] = i + 1

# Save
with open(RECIPE_FILE, "w") as f:
    json.dump({"recipes": deduped[:40]}, f, indent=2)

names = [r.get("name") for r in deduped[:40]]
print(f"\nDONE. {len(deduped)} recipes saved.", flush=True)
print(f"NAMES: {names}", flush=True)
print(f"ERRORS: {errors}", flush=True)