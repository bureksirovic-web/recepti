# Recepti

Family recipe bot with meal planning, nutrition tracking, and shopping list generation.

## Setup

```bash
pip install python-telegram-bot>=20.0
pip install ruff  # for linting
```

## Configuration

Environment variables:

- `RECEPTI_BOT_TOKEN` — Telegram bot token from @BotFather
- `BRAIN_BASE_URL` — LLM API endpoint (default: `http://localhost:8002/v1`)

## Bot Commands

- `/start` — Welcome message
- `/search <query>` — Search recipes by keyword, cuisine, or ingredient
- `/plan` — Generate a weekly meal plan
- `/recipes` — List all available recipes
- `/history` — Check meal history per child

## Project Structure

```
recepti/
  bot.py          — Telegram bot (polling-based)
  scraper.py     — Recipe web scraper
  search.py      — Keyword search with relevance scoring
  planner.py     — Weekly meal planner
  models.py      — Pydantic data models
  recipe_store.py — Recipe persistence (JSON)
  nutrition.py   — Nutrition estimation
  shopping.py    — Shopping list generation
  kid_tracker.py — Per-child meal history
  llm_client.py  — LLM API client
  config.py      — Configuration
data/
  recipes.json   — Recipe database (30 Indian vegetarian recipes)
  family.json    — Child profiles (name, age, allergies)
tests/
  test_*.py      — 59 tests (all passing)
```

## Testing

```bash
python -m pytest  # 59 tests
python -m ruff check recepti/  # lint
```