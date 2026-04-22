# Recipe Hunter — Autonomous Discovery System
## Recepti Croatian Family Meal-Planning Telegram Bot

**Status**: Design & Implementation Plan
**Author**: Sisyphus-Junior
**Date**: 2026-04-22
**Prerequisite reading**: `recepti/scraper.py`, `recepti/llm_service.py`, `recepti/scheduler.py`, `recepti/rating_store.py`, `recepti/recipe_expander.py`, `recepti/web_app.py`

---

## 0. Assumptions & Constraints

| Assumption | Detail |
|---|---|
| Bot runs as single-process polling | No separate cron/container. Hunter is a daemon `threading.Thread` inside the bot process |
| Rejection → blacklist at CUISINE level | `FamilyMember.dislikes` is cuisine-level. ≥3 thumbs-down on a cuisine → cuisine added to ALL members' dislikes |
| DuckDuckGo available | `duckduckgo_search` Python package already in use by `recipe_expander.py` |
| LLM already in use | `llm_service.extract_recipe_from_url()` already handles non-JSON-LD pages |
| `data/` is writable | All state files live under `data/` |
| Cron interval | 24h default, configurable via `RECEPTI_HUNT_INTERVAL_HOURS` env var |

---

## 1. System Architecture (Text Diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Telegram Bot Process                         │
│  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ Telegram     │  │ Flask REST API    │  │ Hunter Daemon   │ │
│  │ Handler      │  │ /api/coverage     │  │ Thread         │ │
│  │ Thread      │  │ /api/scrape-todo  │  │ (daemon=True)  │ │
│  └──────┬───────┘  └────────┬─────────┘  └───────┬────────┘   │ │
│         │                   │                    │               │   │ │
│  ┌──────┴─────────────────┴────────────────────┴────────────┐ │ │
│  │              Shared Singleton State                      │ │ │
│  │  RecipeStore  │  RecipeRatingStore  │  CookingLogStore  │ │ │
│  └──────────────────────────────────────────────────────────┘ │ │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ coverage    │    │ scrape-todo  │    │ hunt_state   │
    │ (computed   │    │ (targets =   │    │ .json        │
    │ on-request) │    │ holes+rej)  │    │             │
    └─────────────┘    └─────────────┘    └─────────────┘
                              │
                              ▼
          ┌─────────────────────────────────────────────┐
          │         RecipeHunter (background loop)        │
          │                                             │
          │  ┌──────────────┐  ┌────────────────────┐ │
          │  │HuntCycle     │  │CuisineBlacklister  │ │
          │  │• _should_run │  │• get_rejected_cuisin│ │
          │  │• _targets() │  │• _sync_to_members() │ │
          │  │• _extract() │  └────────────────────┘ │
          │  │• _notify()  │                          │
          │  └──────────────┘  ┌────────────────────┐ │
          │                    │HuntNotificationStore│ │
          │                    │• write()           │ │
          │                    │• fetch_pending()  │ │
          │                    └────────────────────┘ │
          └─────────────────────────────────────────────┘
                              │
                              ▼
          ┌─────────────────────────────────────────────┐
          │              External World                 │
          │                                             │
          │  DuckDuckGo ──→ Recipe URLs ( Croatian )   │
          │      ↓                                        │
          │  LLM extract via OpenRouter API             │
          │      ↓                                        │
          │  Validate (vegetarian + Croatia ingredients) │
          │      ↓                                        │
          │  Save to expanded_recipes.json + notify       │
          └─────────────────────────────────────────────┘
```

---

## 2. New Files & Their Responsibilities

### 2.1 `recepti/recipe_hunter.py`
**Responsibility**: Core hunter engine — daemon thread, search pipeline, LLM extraction, notification queue.

| Class | Method | Lines | Description |
|---|---|---|---|
| `HuntTarget` | dataclass | — | NamedTuple: `query`, `reason`, `priority_score`, `target_type` |
| `HuntResult` | dataclass | — | `success`, `recipe`, `source_url`, `error`, `was_duplicate` |
| `RecipeHunter` | `__init__()` | ~20 | Init with store, croatia_ingredients_path, state_path, interval_hours |
| `RecipeHunter` | `_should_run_today()` | ~10 | Read `last_hunt` from state file, compare elapsed hours ≥ interval_hours |
| `RecipeHunter` | `_fetch_targets()` | ~15 | Call existing `/api/scrape-todo` logic (coverage holes + rejections), return top-N HuntTargets |
| `RecipeHunter` | `_search_ddg()` | ~15 | Use `DDGS().text()` to search DuckDuckGo, filter Croatian domains, return URLs |
| `RecipeHunter` | `_fetch_page_content()` | ~10 | requests GET + lxml strip noise + return text[:8000] (copy from RecipeExpander) |
| `RecipeHunter` | `_extract_recipe()` | ~10 | Call `llm_service.extract_recipe_from_url()` with croatia_hint |
| `RecipeHunter` | `_is_strictly_vegetarian()` | ~10 | Reject forbidden ingredient list (copy from RecipeExpander) |
| `RecipeHunter` | `_is_duplicate()` | ~10 | Normalize name + word-overlap dedup against store._recipes |
| `RecipeHunter` | `_validate_and_add()` | ~15 | Vegetarian check → dup check → assign ID → append to expanded_recipes.json |
| `RecipeHunter` | `_run_cycle()` | ~30 | Inner loop: for each target, search → extract → validate_and_add → early exit on N successes |
| `RecipeHunter` | `_save_state()` | ~5 | Write `last_hunt`, `cycle_count`, `recipes_added_this_cycle` to state file |
| `RecipeHunter` | `_notify()` | ~10 | Write notification dict to `data/hunt_notifications.json` |
| `RecipeHunter` | `run_once()` | ~5 | `_should_run_today()` → `_run_cycle()` → `_notify()`; returns bool (ran/skipped) |
| `RecipeHunter` | `run()` | ~15 | Daemon thread loop: `run_once()`, `threading.Event().wait(timeout=interval_hours*3600)` |
| `RecipeHunter` | `force_run()` | ~5 | Force run one cycle ignoring interval check (for `/hunt` command) |

### 2.2 `recepti/cuisine_blacklister.py`
**Responsibility**: Sync cuisine-level thumbs-down rejections → family_member.dislikes.

| Class | Method | Lines | Description |
|---|---|---|---|
| `CuisineBlacklister` | `__init__()` | ~10 | Init with CookingLogStore (members_path), RecipeRatingStore, optional threshold |
| `CuisineBlacklister` | `_get_rejected_cuisines()` | ~10 | Call `rating_store.get_rejected_cuisines(store, threshold)` |
| `CuisineBlacklister` | `_sync_to_members()` | ~20 | Load all members, for each rejected cuisine append to `member.dislikes` if not present, save |
| `CuisineBlacklister` | `sync()` | ~5 | Public entry: `_get_rejected_cuisines()` → `_sync_to_members()`; return list of synced cuisines |

### 2.3 `recepti/hunt_notification.py`
**Responsibility**: Persistent notification queue that survives process restarts.

| Class | Method | Lines | Description |
|---|---|---|---|
| `HuntNotification` | dataclass | — | `timestamp`, `type` ("cycle_summary"\|"error"), `title`, `body`, `read` |
| `HuntNotificationStore` | `__init__()` | ~10 | Init with path |
| `HuntNotificationStore` | `write()` | ~10 | Append notification, atomic JSON write |
| `HuntNotificationStore` | `fetch_pending()` | ~10 | Return unread notifications, mark as read |
| `HuntNotificationStore` | `mark_read()` | ~5 | Mark notification(s) as read by timestamp |

### 2.4 `data/hunt_state.json`
**Responsibility**: Persist last run timestamp and cycle stats.

```json
{
  "last_hunt": "2026-04-21T08:00:00",
  "interval_hours": 24,
  "cycle_count": 3,
  "total_recipes_added": 12,
  "recipes_added_this_cycle": 4,
  "cuisines_blacklisted_this_cycle": [],
  "last_error": ""
}
```

### 2.5 `data/hunt_notifications.json`
**Responsibility**: Notification queue (FIFO).

```json
[
  {
    "timestamp": "2026-04-21T08:05:00",
    "type": "cycle_summary",
    "title": "🆕 Hunter cycle done",
    "body": "Found 4 new recipes: [Recipe1, Recipe2, Recipe3, Recipe4]\nBlacklisted: [italian]",
    "read": false
  }
]
```

### 2.6 `data/known_sites.json`
**Responsibility**: Discovered Croatian recipe sites.

```json
[
  {
    "url": "https://www.coolinarika.com",
    "name": "Coolinarika",
    "has_jsonld": false,
    "recipe_count": 0,
    "last_seen": "2026-04-21"
  }
]
```

---

## 3. Each File — Key Classes & Line Ranges

### 3.1 `recepti/recipe_hunter.py` (NEW — ~320 lines)

```
Lines 1-15    │ Imports: threading, datetime, json, logging, requests, DDGS, lxml, pathlib
             │ Local imports: models, recipe_store, llm_service, CuisineBlacklister
Lines 16-30  │ Dataclasses: HuntTarget (query, reason, priority_score, type),
             │            HuntResult (success, recipe, source_url, error, was_duplicate)
Lines 31-60  │ RecipeHunter.__init__() — store ref, paths, _load_state(), _load_ingredients()
Lines 61-80  │ _should_run_today() — read last_hunt from state, elapsed ≥ interval_hours?
Lines 81-100 │ _fetch_targets() — call web_app._build_holes() + get_rejected_cuisines(),
             │           return top-10 HuntTargets ranked by priority_score
Lines 101-130│ _search_ddg() — DDGS().text() for Croatian queries, filter domain + recipe hints,
             │           deduplicate URLs, return list[str]
Lines 131-150│ _fetch_page_content() — requests GET + lxml.strip_noise + text[:8000]
Lines 151-180│ _extract_recipe() — call extract_recipe_from_url() from llm_service
Lines 181-200│ _is_strictly_vegetarian() — forbidden ingredient list check (copy from RecipeExpander)
Lines 201-220│ _is_duplicate() — normalize + word-overlap dedup against store._recipes
Lines 221-250│ _validate_and_add() — vegetarian check → dup check → save to expanded_recipes.json
             │            → store._recipes.append()
Lines 251-280│ _run_cycle() — for each target: search → extract → validate → track successes;
             │            early exit when max_recipes reached
Lines 281-300│ _notify() — write HuntNotification to HuntNotificationStore
Lines 301-320│ run() — daemon thread: while not stop_event.is_set():
             │            run_once(); stop_event.wait(timeout=interval_hours*3600)
```

### 3.2 `recepti/cuisine_blacklister.py` (NEW — ~90 lines)

```
Lines 1-10    │ Imports: json, logging, threading, pathlib
Lines 11-20   │ CuisineBlacklister.__init__() — store CookingLogStore + RecipeRatingStore refs
Lines 21-40   │ _get_rejected_cuisines() — call rating_store.get_rejected_cuisines(store, threshold=3)
Lines 41-70   │ _sync_to_members() — for each rejected cuisine:
             │   for member in cooking_log.get_members():
             │     if cuisine not in member.dislikes: member.dislikes.append(cuisine)
             │   cooking_log._save_members() — atomic write
Lines 71-90   │ sync() — public entry: _get_rejected_cuisines() → _sync_to_members();
             │   returns list[str] of newly blacklisted cuisines
```

### 3.3 `recepti/hunt_notification.py` (NEW — ~80 lines)

```
Lines 1-15    │ Imports: json, datetime, pathlib, tempfile, threading
Lines 16-25   │ Dataclass: HuntNotification (timestamp, type, title, body, read)
Lines 26-50    │ HuntNotificationStore.__init__() + _load() + _atomic_save()
Lines 51-65    │ write() — append notification to list, atomic save
Lines 66-80    │ fetch_pending() — filter read=False, return list; mark_read() — update flags, save
```

---

## 4. Modified Existing Files

### 4.1 `recepti/bot.py`

**Add to imports (line ~28):**
```python
from recepti.recipe_hunter import RecipeHunter
from recepti.hunt_notification import HuntNotificationStore
```

**Add to global state (after line ~78 `_rating_store`):**
```python
_hunter: Optional[RecipeHunter] = None
_notification_store: Optional[HuntNotificationStore] = None
```

**Add getters (after line ~157 `get_rating_store()`):**
```python
def get_hunter() -> RecipeHunter:
    global _hunter
    if _hunter is None:
        _hunter = RecipeHunter(
            store=get_store(),
            croatia_ingredients_path=os.path.join(DATA_DIR, "croatia_ingredients.json"),
            state_path=os.path.join(DATA_DIR, "hunt_state.json"),
            interval_hours=float(os.getenv("RECEPTI_HUNT_INTERVAL_HOURS", "24")),
            notifications_path=os.path.join(DATA_DIR, "hunt_notifications.json"),
        )
    return _hunter


def get_notification_store() -> HuntNotificationStore:
    global _notification_store
    if _notification_store is None:
        _notification_store = HuntNotificationStore(
            os.path.join(DATA_DIR, "hunt_notifications.json")
        )
    return _notification_store
```

**Add command handlers (after `okusi_command`, before `unknown`):**
```python
async def hunt_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Force-run the recipe hunter cycle. Usage: /hunt"""
    await update.message.reply_text("🕵️ Hunter starting — searching for new recipes...")
    try:
        hunter = get_hunter()
        result = hunter.force_run()
        if result:
            await update.message.reply_text(
                f"✅ Hunter cycle complete — found {result['recipes_added']} new recipes"
            )
        else:
            await update.message.reply_text("⚠️ Hunter cycle skipped or no new recipes found")
    except Exception as e:
        logger.error(f"Error in /hunt command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def hunt_status_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Check hunter status and pending notifications. Usage: /hunt-status"""
    try:
        notifications = get_notification_store().fetch_pending()
        hunter = get_hunter()
        state = hunter.get_last_state()

        lines = ["🕵️ Hunter Status\n"]
        if state:
            lines.append(f"Last hunt: {state.get('last_hunt', 'never')}")
            lines.append(f"Cycles run: {state.get('cycle_count', 0)}")
            lines.append(f"Total recipes added: {state.get('total_recipes_added', 0)}")
            lines.append(f"Recipes this cycle: {state.get('recipes_added_this_cycle', 0)}")
        else:
            lines.append("No hunt state yet.")

        if notifications:
            lines.append(f"\n📬 {len(notifications)} pending notification(s):")
            for n in notifications[:3]:
                lines.append(f"  {n['title']}")
                lines.append(f"  {n['body'][:100]}")
        else:
            lines.append("\n📬 No pending notifications.")

        await update.message.reply_text("\n".join(lines).strip())
    except Exception as e:
        logger.error(f"Error in /hunt-status command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
```

**Register handlers in `main()` (after `okusi_command` registration, line ~907):**
```python
    application.add_handler(CommandHandler("hunt", hunt_command))
    application.add_handler(CommandHandler("hunt-status", hunt_status_command))
```

**Start hunter daemon in `main()` (after Flask thread start, before `run_polling`):**
```python
    # Start recipe hunter daemon
    try:
        hunter = get_hunter()
        hunter_thread = threading.Thread(target=hunter.run, daemon=True, name="RecipeHunter")
        hunter_thread.start()
        logger.info("RecipeHunter daemon started")
    except Exception as e:
        logger.warning(f"RecipeHunter daemon failed to start: {e}")
```

### 4.2 `recepti/web_app.py`

**Add to `/api/scrape-todo` endpoint (line ~373):**
After building `targets` list, inject Croatian-specific search queries for coverage holes:
```python
# Inject Croatian-specific queries for coverage holes
if coverage_holes:
    for hole in coverage_holes:
        if hole["dimension"] == "cuisine" and hole["value"] not in ("", "international"):
            croatian_queries = [
                f"{hole['value']} recepti",
                f"{hole['value']} recept bez mesa",
            ]
            for q in croatian_queries:
                if q.lower() not in seen_queries:
                    targets.append({
                        "query": q,
                        "reason": f"SPARSE coverage: cuisine={hole['value']}",
                        "priority_score": hole["priority"],
                        "type": "coverage",
                    })
                    seen_queries.add(q.lower())
```

---

## 5. Telegram Command Specs

### 5.1 `/hunt` — Force Hunter Cycle
**Usage**: `/hunt`

| Field | Value |
|---|---|
| Aliases | `/lovljenje`, `/traži` |
| Permission | Any authenticated user |
| Response | `✅ Hunter cycle complete — found N new recipes` or `⚠️ Hunter cycle skipped` |
| Error | `❌ Error: <error message>` |
| Timeout | Up to 120s (many LLM calls) |

**User flow**:
1. User sends `/hunt`
2. Bot replies `🕵️ Hunter starting — searching for new recipes...`
3. Hunter runs one full cycle (ignores 24h interval check)
4. Bot replies with summary

### 5.2 `/hunt-status` — Check Status
**Usage**: `/hunt-status`

| Field | Value |
|---|---|
| Aliases | `/lovljenje-status`, `/lovljenje-stat` |
| Permission | Any authenticated user |
| Response | Last hunt time, cycle count, total added, pending notifications |
| Error | `❌ Error: <error message>` |

**Response template**:
```
🕵️ Hunter Status

Last hunt: 2026-04-21T08:00:00
Cycles run: 3
Total recipes added: 12
Recipes this cycle: 4

📬 2 pending notification(s):
  🆕 Hunter cycle done
  Found 4 new recipes: [Recipe1, Recipe2, ...]
  Blacklisted: [italian]
```

### 5.3 Automatic Notification (Background)
**Trigger**: After each hunter cycle completes
**Channel**: Sends Telegram message to the chat where the bot is active

Format:
```
🆕 Hunter cycle complete

Found 4 new recipes:
  • RecipeName1 (Cuisine, difficulty)
  • RecipeName2 (Cuisine, difficulty)
  • ...

🛒 Blacklisted cuisines (≥3 rejections):
  • italian

Total in DB now: 89 recipes across 12 cuisines
```

---

## 6. Blacklist Sync Algorithm

```
Algorithm: CuisineBlacklister.sync()

INPUT:
  - CookingLogStore: members_path → data/family_members.json
  - RecipeRatingStore: ratings_path → data/recipe_ratings.json
  - threshold = 3 (configurable via RECEPTI_BLACKLIST_THRESHOLD env var)

PROCESS:
  1. Load all ratings: rating_store._ratings
  2. For each RatingEvent where thumbs == False:
       a. Get recipe from RecipeStore by recipe_id
       b. Extract cuisine = recipe.tags.cuisine
       c. Increment cuisine_rejections[cuisine]
  3. Filter cuisines where cuisine_rejections[cuisine] >= threshold
  4. For each such cuisine:
       a. Load all FamilyMembers from CookingLogStore._members
       b. For each member:
            i. If cuisine NOT in member.dislikes:
               ii. Append cuisine to member.dislikes
       c. Save all members via CookingLogStore._save_members()
  5. Return list of newly blacklisted cuisines

OUTPUT:
  - data/family_members.json: cuisine added to ALL members' dislikes
  - List[str] of new blacklist entries

EDGE CASES:
  - Empty ratings: no cuisines blacklisted → no-op
  - Cuisine already in dislikes: skip (no duplicate)
  - File write failure: log error, raise exception
  - Member not loaded: skip silently
```

---

## 7. Hunter Cycle Algorithm (Step by Step)

```
Algorithm: RecipeHunter.run_once() → bool

PRECONDITIONS:
  - RECEPTI_HUNT_INTERVAL_HOURS env var (default 24)
  - At least one HuntTarget available from _fetch_targets()

PROCESS:

Step 1: Interval Check
  1a. Read data/hunt_state.json["last_hunt"]
  1b. Compute hours_elapsed = (now - last_hunt).total_seconds() / 3600
  1c. If hours_elapsed < interval_hours:
        RETURN False  # Skip, not time yet
  1d. ELSE: CONTINUE

Step 2: Fetch Targets
  2a. Call _fetch_targets() → list[HuntTarget] (top 10 by priority_score)
  2b. If empty: log warning, RETURN False

Step 3: Determine Batch Size
  3a. max_recipes = int(os.getenv("RECEPTI_HUNT_MAX_RECIPES", "5"))
  3b. targets_to_process = targets[:max_recipes * 2]  # Search more than needed (dupes/filtering)

Step 4: Run Extraction Loop
  FOR target IN targets_to_process:
    4a. IF success_count >= max_recipes: BREAK
    4b. _search_ddg(target.query) → list[str] URLs
        - Search: f"{target.query} site:coolinarika.com OR Croatia vegetarian recipe"
        - Filter: prefer Croatian domains, reject non-recipe URLs
    4c. FOR url IN urls (limit 5 per target):
        4c-i.  _fetch_page_content(url) → page_content
        4c-ii. IF page_content is None: CONTINUE
        4c-iii. _extract_recipe(url, page_content, croatia_hint) → Recipe or None
        4c-iv.  IF Recipe is None: CONTINUE
        4c-v.   _is_strictly_vegetarian() → IF False: CONTINUE ("contains non-vegetarian")
        4c-vi.  _is_duplicate() → IF True: CONTINUE
        4c-vii. _validate_and_add(Recipe) → IF success:
                  increment success_count
                  log: "✓ Added: {recipe.name} from {url}"

Step 5: Update Blacklist
  5a. CuisineBlacklister.sync() → list[str] new_blacklisted_cuisines
  5b. Log each new blacklist entry

Step 6: Save State
  6a. Read current state
  6b. Update: last_hunt=NOW, cycle_count+=1,
              recipes_added_this_cycle=success_count,
              cuisines_blacklisted_this_cycle=new_blacklisted_cuisines,
              total_recipes_added+=success_count
  6c. Atomic write to data/hunt_state.json

Step 7: Notify
  7a. Build notification:
        type = "cycle_summary"
        title = f"🆕 Hunter cycle done — found {success_count} new recipes"
        body = f"Found {success_count} new recipes: [{names}]. Blacklisted: [{cuisines}]"
  7b. HuntNotificationStore.write(notification)
  7c. If Telegram bot is active in a group: send message directly

Step 8: Return
  RETURN True  # Cycle ran
```

---

## 8. Notification Mechanism

### 8.1 Architecture
The hunter runs in a background daemon thread **outside** the Telegram async context. Direct Telegram sends from the hunter thread would require async-safe queuing. Two options:

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| **A: JSON queue file** (`data/hunt_notifications.json`) | Survives restarts, simple, no thread-safety issues with bot | Not real-time; read on next user command | ✅ Default |
| **B: Thread-safe Telegram sender** (queue messages from hunter, bot sends async) | Real-time | Complex thread-safe code | Fallback |

**Chosen**: Option A — JSON queue file.

### 8.2 Flow
```
Hunter daemon
    │
    ▼
HuntNotificationStore.write()
    │
    ▼
data/hunt_notifications.json
    │
    ├─→ /hunt-status command reads pending → sends Telegram message
    │
    └─→ Optional: bot startup reads pending → sends Telegram message
```

### 8.3 Notification Types
```python
NOTIFICATION_TYPES = {
    "cycle_summary": "🆕 Hunter cycle done — N new recipes",
    "blacklist_update": "🛒 Cuisines blacklisted: [list]",
    "error": "❌ Hunter error: <message>",
    "low_coverage_warning": "⚠️ Coverage warning: <dimension>=<value> still sparse",
}
```

### 8.4 Cleanup Policy
- Keep last 10 notifications
- Mark as read after `/hunt-status` is shown
- Auto-delete notifications older than 7 days on next write

---

## 9. Test Requirements

### 9.1 Unit Tests (`tests/test_recipe_hunter.py`)

| Test | What it verifies |
|---|---|
| `test_should_run_skips_within_interval` | `_should_run_today()` returns False when elapsed < interval |
| `test_should_run_runs_after_interval` | `_should_run_today()` returns True when elapsed ≥ interval |
| `test_should_run_runs_when_no_state` | `_should_run_today()` returns True when state file missing |
| `test_fetch_targets_returns_list` | `_fetch_targets()` returns non-empty list |
| `test_is_strictly_vegetarian_passes` | Tofu+rice+spinach passes |
| `test_is_strictly_vegetarian_fails` | Chicken or tofu recipe fails |
| `test_is_duplicate_detects` | Same-named recipe detected as duplicate |
| `test_is_duplicate_allows_new` | Distinct recipe passes |
| `test_validate_and_add_success` | Valid recipe appended to store + saved |
| `test_validate_and_add_skips_meat` | Meat recipe rejected |
| `test_validate_and_add_skips_duplicate` | Duplicate skipped |
| `test_save_state_atomic` | State file written atomically |
| `test_notify_writes_json` | Notification written to file |
| `test_cuisine_blacklister_syncs` | Blacklisted cuisine added to all members' dislikes |
| `test_cuisine_blacklister_skips_existing` | Already-blacklisted cuisine not duplicated |

### 9.2 Integration Tests (`tests/test_hunter_integration.py`)

| Test | What it verifies |
|---|---|
| `test_full_cycle_with_mock_ddg` | Full cycle runs with mocked DDGS, at least 1 recipe added |
| `test_cycle_skips_when_already_run_today` | Only one cycle per interval |
| `test_blacklist_syncs_after_thumbs_down` | Cuisine in dislikes after 3+ thumbs-down ratings |

### 9.3 Mock Strategy
- Mock `DDGS` via `unittest.mock.patch("duckduckgo_search.DDGS")`
- Mock `requests.get` for page fetching
- Mock `call_openrouter` for LLM extraction (return fixed JSON)

---

## 10. Estimated Effort

| Component | Effort | Notes |
|---|---|---|
| `cuisine_blacklister.py` | **Small** (~90 lines) | Standalone, well-defined inputs/outputs |
| `hunt_notification.py` | **Small** (~80 lines) | JSON CRUD, simple |
| `recipe_hunter.py` core | **Medium** (~320 lines) | Most complex; DDG search + LLM + dedup |
| `bot.py` modifications | **Small** (~40 lines) | 2 commands + 2 getters + daemon start |
| `web_app.py` modifications | **Small** (~20 lines) | Croatian query injection |
| Tests (unit) | **Medium** (~200 lines) | ~13 tests |
| Tests (integration) | **Medium** (~100 lines) | ~3 tests with mocks |
| **Total** | **~850 lines code + ~300 lines tests** | **Medium project** |

---

## 11. Answered Design Questions

### Q1: How to discover recipe URLs?

**Answer: Option C — DuckDuckGo + coolinarika.com fallback**

1. Primary: `DDGS().text()` with Croatian-specific queries (leverages existing `recipe_expander.py` pattern)
2. Query strategy:
   - Coverage-hole queries: `{cuisine} recepti bez mesa`, `{meal_type} vegetarijanski recepti`
   - Ingredient queries: `{ingredient} recept vegetarian`
   - Include `site:coolinarika.com` in query to target Croatian site directly
3. Filter: reject URLs from blacklisted domains, reject non-recipe pages
4. URL dedup: normalize + deduplicate across all targets per cycle

### Q2: How to handle sites without JSON-LD?

**Answer: `llm_service.extract_recipe_from_url()` (already implemented)**

- Uses OpenRouter LLM to extract structured Recipe from ANY HTML
- Already handles non-JSON-LD pages with Croatian ingredient constraints
- No new code needed; reuse existing function in `_extract_recipe()`
- Cost: ~$0.001-0.01 per recipe (OpenRouter Gemini Flash)

### Q3: What is the blacklist mechanism?

**Answer: Cuisine-level sync from RecipeRatingStore → FamilyMember.dislikes**

1. Load `RecipeRatingStore._ratings`
2. Count `thumbs=False` per cuisine (via `get_rejected_cuisines()`)
3. Threshold: `RECEPTI_BLACKLIST_THRESHOLD` env var (default: 3)
4. For cuisines above threshold: add to `FamilyMember.dislikes` for ALL members
5. Save via `CookingLogStore._save_members()` → writes `data/family_members.json`

Note: `FamilyMember.dislikes` is currently unused at the cuisine level by the planner,
but adding `cuisine` entries here prepares for future cuisine-level exclusion.

### Q4: What data files are needed?

| File | Exists? | Notes |
|---|---|---|
| `data/recipe_ratings.json` | ✅ Yes | Already exists |
| `data/hunt_state.json` | ❌ New | last_hunt, cycle_count, totals |
| `data/hunt_notifications.json` | ❌ New | Notification queue |
| `data/known_sites.json` | ❌ New | Discovered recipe sites (optional, v2) |
| `data/family_members.json` | ✅ Yes | Already exists |

### Q5: How should the bot notify on new recipes?

**Answer: JSON queue + on-demand read via `/hunt-status`**

1. Hunter writes to `data/hunt_notifications.json` (persistent, survives restart)
2. `/hunt-status` command reads + displays + marks as read
3. On bot startup: optionally scan for unread → send Telegram message
4. Telegram send is triggered by user command, not by hunter directly (avoids async complexity)

### Q6: DuckDuckGo integration — `ddg-search` tool vs `requests` to DuckDuckGo HTML?

**Answer: Use `duckduckgo_search` Python package (already in codebase)**

- Already imported in `recipe_expander.py` as `from duckduckgo_search import DDGS`
- More reliable than scraping DuckDuckGo HTML (which blocks bots)
- `ddg-search` MCP tool is not available in bot process context (runs in CLI)
- Tradeoff: package must be installed in bot environment (already is)

### Q7: LLM validation — full quality check or basic validation?

**Answer: Basic validation + LLM extraction (already the pattern)**

- `extract_recipe_from_url()` already applies:
  1. Vegetarian constraint in prompt
  2. Croatia ingredients in hint
  3. Structured output validation (name, ingredients, instructions)
- No second-pass LLM needed (cost + latency)
- Basic checks remain: vegetarian rejection list + Croatia whitelist

### Q8: Interval — 24h default, env var configurable?

**Answer: Yes**

```python
interval_hours = float(os.getenv("RECEPTI_HUNT_INTERVAL_HOURS", "24"))
```

- `RecipePreloader` uses same pattern in `scheduler.py` (line 55-64)
- Prevents runaway cycles if bot restarts frequently
- `/hunt` command bypasses interval check for manual trigger

---

## 12. Implementation Order (Topological)

```
Step 1  → Write tests/ (TDD: test before code)
Step 2  → Implement hunt_notification.py
Step 3  → Implement cuisine_blacklister.py
Step 4  → Implement recipe_hunter.py (core)
Step 5  → Modify bot.py (commands + daemon start)
Step 6  → Modify web_app.py (Croatian query injection)
Step 7  → Run full test suite
Step 8  → Manual smoke test: /hunt, /hunt-status
```