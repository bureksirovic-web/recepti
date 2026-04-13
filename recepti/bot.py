"""
Telegram Bot for Recepti — Family Recipe Bot.
Polling-based, no webhook required.
"""
import logging
import os
import sys
from datetime import date
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from recepti.models import Child, Recipe
from recepti.recipe_store import RecipeStore
from recepti.kid_tracker import KidMealHistory
from recepti.planner import generate_weekly_plan, format_meal_plan
from recepti.shopping import generate_shopping_list_from_recipes, format_shopping_list
from recepti.nutrition import check_daily_balance

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("RECEPTI_BOT_TOKEN", "")
DATA_DIR = os.getenv("RECEPTI_DATA_DIR", "/workspace/repos/Recepti/data")

RECIPES_FILE = f"{DATA_DIR}/recipes.json"
FAMILY_FILE = f"{DATA_DIR}/family.json"
MEAL_PLAN_FILE = f"{DATA_DIR}/meal_plans.json"

# ── State (simple singleton) ────────────────────────────────────────
_store: Optional[RecipeStore] = None
_kid_history: Optional[KidMealHistory] = None
_family: list[Child] = []

def get_store() -> RecipeStore:
    global _store
    if _store is None:
        _store = RecipeStore(RECIPES_FILE)
    return _store

def get_kid_history() -> KidMealHistory:
    global _kid_history
    if _kid_history is None:
        _kid_history = KidMealHistory()
        _kid_history._set_recipe_store(get_store())
    return _kid_history

def get_family() -> list[Child]:
    global _family
    if not _family:
        _family = _load_family()
    return _family

def _load_family() -> list[Child]:
    import json
    from pathlib import Path
    from recepti.models import Child
    path = Path(FAMILY_FILE)
    if not path.exists():
        return []
    try:
    with open(path) as f:
        data = json.load(f)
    return [Child(
        id=c["id"],
        name=c["name"],
        age_years=c["age_years"],
        dislikes=c.get("dislikes", []),
        favorites=c.get("favorites", []),
    ) for c in data.get("family", [])]
        except Exception:
        return []

# ── Helpers ──────────────────────────────────────────────────────────
async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🍽️ Recepti — Family Recipe Bot\n\n"
        "Commands:\n"
        "/search <ingredients> — find recipes by available ingredients\n"
        "/plan [days] — generate meal plan\n"
        "/shopping [date] — shopping list for a meal plan\n"
        "/history <child_id> [days] — meal history for a child\n"
        "/favorites <child_id> — top recipes for a child\n"
        "/balance [date] — nutrition balance check\n"
        "/addmeal <child_id> <recipe_id> <meal_type> <eaten%> — record a meal\n"
        "/recipes — list all recipes\n"
        "/recipe <id> — full recipe details\n"
        "/help — this message"
    )

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await start_command(update, ctx)

async def search_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /search tomatoes, paneer, onion"""
    if not ctx.args:
        await update.message.reply_text("Usage: /search <ingredient1>, <ingredient2>, ...")
        return
    
    query = " ".join(ctx.args).replace(",", " ")
    ingredients = [i.strip() for i in query.split() if i.strip()]
    
    store = get_store()
    results = store.search_by_ingredients(ingredients)
    
    if not results:
        await update.message.reply_text(f"No recipes found matching: {', '.join(ingredients)}")
        return
    
    lines = [f"🔍 Found {len(results)} recipes matching: {', '.join(ingredients)}\n"]
    for recipe in results[:10]:
        match_count = sum(
            1 for ing in recipe.ingredients
            if any(s in ing.name.lower() for s in [i.lower() for i in ingredients])
        )
        lines.append(f"#{recipe.id} {recipe.name} ({match_count} matches)")
        lines.append(f"   {recipe.tags.cuisine} · {recipe.tags.meal_type} · {recipe.difficulty}")
        lines.append(f"   {recipe.prep_time_min}+{recipe.cook_time_min} min")
        lines.append("")
    
    await update.message.reply_text("\n".join(lines).strip())

async def recipes_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """List all recipes."""
    store = get_store()
    all_recipes = store._recipes
    
    if not all_recipes:
        await update.message.reply_text("No recipes loaded. Run recipe generation first.")
        return
    
    lines = [f"📖 {len(all_recipes)} recipes:\n"]
    for r in all_recipes:
        lines.append(f"#{r.id} {r.name} — {r.tags.cuisine}, {r.tags.meal_type}")
    
    await update.message.reply_text("\n".join(lines).strip())

async def recipe_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /recipe <id>"""
    if not ctx.args:
        await update.message.reply_text("Usage: /recipe <id>")
        return
    
    try:
        recipe_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid recipe ID. Use a number.")
        return
    
    store = get_store()
    recipe = store.get_recipe_by_id(recipe_id)
    
    if not recipe:
        await update.message.reply_text(f"Recipe #{recipe_id} not found.")
        return
    
    lines = [
        f"🍲 {recipe.name}",
        f"#{recipe.id} · {recipe.tags.cuisine} · {recipe.difficulty}",
        f"{recipe.prep_time_min} min prep + {recipe.cook_time_min} min cook · {recipe.servings} servings",
        "",
        f"_{recipe.description}_",
        "",
        "📋 Ingredients:",
    ]
    for ing in recipe.ingredients:
        lines.append(f"  • {ing.amount} {ing.unit} {ing.name}")
    
    if isinstance(recipe.instructions, list):
        lines.append("")
        lines.append("👩‍🍳 Instructions:")
        for i, step in enumerate(recipe.instructions, 1):
            lines.append(f"  {i}. {step}")
    else:
        lines.append("")
        lines.append(f"👩‍🍳 Instructions: {recipe.instructions}")
    
    tags_text = ", ".join(recipe.tags.dietary_tags) if recipe.tags.dietary_tags else "none"
    lines.append(f"\n🏷️ Tags: {tags_text}")
    
    await update.message.reply_text("\n".join(lines).strip())

async def plan_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a meal plan. Usage: /plan [days=7]"""
    days = 7
    if ctx.args:
        try:
            days = min(max(int(ctx.args[0]), 14)
        except ValueError:
            pass
    
    store = get_store()
    from recepti.models import RecipeCollection
    collection = RecipeCollection(recipes=store._recipes)
    
    plans = generate_weekly_plan(days=days, preferences={
        "recipe_collection": collection,
        "excluded_ids": [],
    })
    
    lines = [f"📅 Meal Plan ({days} days)\n"]
    for date_str, meal_plan in plans.items():
        lines.append(format_meal_plan(date_str, meal_plan))
        lines.append("")
    
    await update.message.reply_text("\n".join(lines).strip())

async def shopping_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate shopping list. Usage: /shopping [date]"""
    # For now, generate from most recent meal plan
    # Full implementation would load from MEAL_PLAN_FILE
    store = get_store()
    all_recipes = store._recipes
    
    if not all_recipes:
        await update.message.reply_text("No recipes loaded.")
        return
    
    # Build recipes DB
    recipes_db = {r.id: r for r in all_recipes}
    
    # Simple demo: create a 3-day plan with random recipes
    from recepti.planner import generate_weekly_plan
    from recepti.models import RecipeCollection
    from datetime import date, timedelta
    
    collection = RecipeCollection(recipes=all_recipes)
    plans = generate_weekly_plan(days=3, preferences={
        "recipe_collection": collection,
    })
    
    shopping = generate_shopping_list_from_recipes(plans, recipes_db)
    formatted = format_shopping_list(shopping)
    
    await update.message.reply_text(formatted)

async def history_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Meal history. Usage: /history <child_id> [days]"""
    if not ctx.args:
        # List all children
        family = get_family()
        if not family:
            await update.message.reply_text("No family data. Add children first.")
            return
        lines = ["👶 Children:"]
        for c in family:
            lines.append(f"  #{c.id} {c.name} ({c.age_years} yrs)")
        await update.message.reply_text("\n".join(lines))
        return
    
    try:
        child_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid child ID.")
        return
    
    days = 30
    if len(ctx.args) > 1:
        try:
            days = int(ctx.args[1])
        except ValueError:
            pass
    
    kid_hist = get_kid_history()
    history = kid_hist.get_child_history(child_id, days=days)
    
    if not history:
        await update.message.reply_text(f"No meals recorded for child #{child_id} in last {days} days.")
        return
    
    lines = [f"📋 Meal history for child #{child_id} ({days} days):\n"]
    for entry in history[-15:]:  # last 15 entries
        lines.append(f"  {entry['date']} {entry['meal_type']}: {entry['recipe_name']} ({entry['amount_eaten']*100:.0f}%)")
        if entry['notes']:
            lines.append(f"    Note: {entry['notes']}")
    
    await update.message.reply_text("\n".join(lines).strip())

async def favorites_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Top recipes for a child. Usage: /favorites <child_id>"""
    if not ctx.args:
        await update.message.reply_text("Usage: /favorites <child_id>")
        return
    
    try:
        child_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid child ID.")
        return
    
    kid_hist = get_kid_history()
    fav_ids = kid_hist.get_child_favorites(child_id)
    
    if not fav_ids:
        await update.message.reply_text(f"No favorites found for child #{child_id}.")
        return
    
    store = get_store()
    lines = [f"⭐ Top recipes for child #{child_id}:\n"]
    for rid in fav_ids:
        recipe = store.get_recipe_by_id(rid)
        if recipe:
            lines.append(f"  #{recipe.id} {recipe.name}")
    
    await update.message.reply_text("\n".join(lines).strip())

async def addmeal_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Record a meal. Usage: /addmeal <child_id> <recipe_id> <meal_type> <eaten_0_1>"""
    if len(ctx.args) < 4:
        await update.message.reply_text(
            "Usage: /addmeal <child_id> <recipe_id> <meal_type> <eaten%>\n"
            "Example: /addmeal 1 5 lunch 0.8"
        )
        return
    
    try:
        child_id = int(ctx.args[0])
        recipe_id = int(ctx.args[1])
        meal_type = ctx.args[2]
        amount_eaten = float(ctx.args[3])
    except ValueError:
        await update.message.reply_text("Invalid parameters.")
        return
    
    today = date.today().isoformat()
    kid_hist = get_kid_history()
    kid_hist.record_meal(child_id, recipe_id, meal_type, today, amount_eaten)
    
    await update.message.reply_text(
        f"✅ Recorded: child #{child_id} ate #{recipe_id} ({amount_eaten*100:.0f}%) at {meal_type}"
    )

async def balance_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Nutrition balance check. Usage: /balance [date]"""
    family = get_family()
    if not family:
        await update.message.reply_text("No family data. Add children first.")
        return
    
    store = get_store()
    recipes_db = {r.id: r for r in store._recipes}
    
    if not recipes_db:
        await update.message.reply_text("No recipes loaded.")
        return
    
    # Build today's meal plan (demo: use first 3 recipes)
    from recepti.models import MealPlan
    keys = list(recipes_db.keys())
    if len(keys) < 3:
        await update.message.reply_text("Need at least 3 recipes for balance check.")
        return
    
    meal_plan = MealPlan(
        date=date.today(),
        breakfast_id=keys[0],
        lunch_id=keys[1],
        dinner_id=keys[2],
    )
    
    assessments = check_daily_balance(meal_plan, family, recipes_db)
    
    lines = ["⚖️ Nutrition Balance Check\n"]
    for child_id, assessment in assessments.items():
        status = "✅" if all(assessment["meets"].values()) else "⚠️"
        lines.append(f"{status} {assessment['child_name']} ({assessment['age_group']}):")
        for nutrient, meets in assessment["meets"].items():
            symbol = "✅" if meets else "❌"
            lines.append(f"  {symbol} {nutrient}: {'met' if meets else 'SHORTAGE: ' + str(assessment['shortages'].get(nutrient, '?'))}")
        lines.append("")
    
    await update.message.reply_text("\n".join(lines).strip())

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Unknown command. Send /help for available commands."
    )

# ── Main ────────────────────────────────────────────────────────────
def main() -> None:
    if not BOT_TOKEN:
        logger.error("RECEPTI_BOT_TOKEN not set")
        sys.exit(1)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("recipes", recipes_command))
    application.add_handler(CommandHandler("recipe", recipe_command))
    application.add_handler(CommandHandler("plan", plan_command))
    application.add_handler(CommandHandler("shopping", shopping_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("favorites", favorites_command))
    application.add_handler(CommandHandler("addmeal", addmeal_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    logger.info("Recepti bot starting — polling mode")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()