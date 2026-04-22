"""
Telegram Bot for Recepti — Family Recipe Bot.
Polling-based, no webhook required.
"""

import logging
import os
import sys
from datetime import date
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from recepti.kid_tracker import KidMealHistory
from recepti.models import Child
from recepti.nutrition import check_daily_balance
from recepti.planner import format_meal_plan, generate_weekly_plan
from recepti.recipe_store import RecipeStore
from recepti.shopping import format_shopping_list, generate_shopping_list_from_recipes
from recepti.llm_service import suggest_recipe, scale_ingredients_for_family
from recepti.recipe_expander import RecipeExpander
from recepti.cooking_log import CookingLogStore
from recepti.family_nutrient_balancer import FamilyNutrientBalancer
from recepti.grocery_suggester import GrocerySuggester

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("RECEPTI_BOT_TOKEN", "")
DATA_DIR = os.getenv("RECEPTI_DATA_DIR", "data")

RECIPES_FILE = f"{DATA_DIR}/recipes.json"
FAMILY_FILE = f"{DATA_DIR}/family.json"
MEAL_PLAN_FILE = f"{DATA_DIR}/meal_plans.json"
CROATIAN_RECIPES_JSON = f"{DATA_DIR}/croatian_recipes.json"
EXPANDED_RECIPES_JSON = f"{DATA_DIR}/expanded_recipes.json"
COOKING_LOG_JSON = f"{DATA_DIR}/cooking_log.json"
FAMILY_MEMBERS_JSON = f"{DATA_DIR}/family_members.json"

FLASK_PORT = os.getenv("RECEPTI_FLASK_PORT")
_flask_app = None


def _try_import_flask():
    global _flask_app
    if _flask_app is None:
        try:
            from recepti.web_app import create_app
            _flask_app = create_app
        except ImportError:
            logger.warning(
                "Flask not installed. Set RECEPTI_FLASK_PORT and run: pip install flask flask-cors"
            )
            _flask_app = False
    return _flask_app or None


# ── State (simple singleton) ────────────────────────────────────────
_store: Optional[RecipeStore] = None
_kid_history: Optional[KidMealHistory] = None
_family: list[Child] = []
_cooking_log: Optional[CookingLogStore] = None
_balancer: Optional[FamilyNutrientBalancer] = None
_suggester: Optional[GrocerySuggester] = None


def get_store() -> RecipeStore:
    global _store
    if _store is None:
        _store = RecipeStore(RECIPES_FILE, extra_sources=[CROATIAN_RECIPES_JSON])
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
        return [
            Child(
                id=c["id"],
                name=c["name"],
                age_years=c["age_years"],
                dislikes=c.get("dislikes", []),
                favorites=c.get("favorites", []),
            )
            for c in data.get("family", [])
        ]
    except Exception:
        return []


def get_cooking_log() -> CookingLogStore:
    global _cooking_log
    if _cooking_log is None:
        _cooking_log = CookingLogStore(COOKING_LOG_JSON, FAMILY_MEMBERS_JSON)
    return _cooking_log


def get_balancer() -> FamilyNutrientBalancer:
    global _balancer
    if _balancer is None:
        _balancer = FamilyNutrientBalancer(get_cooking_log(), get_store())
    return _balancer


def get_suggester() -> GrocerySuggester:
    global _suggester
    if _suggester is None:
        ingredient_names = [
            ing.name for recipe in get_store()._recipes for ing in recipe.ingredients
        ]
        _suggester = GrocerySuggester(existing_ingredients=ingredient_names)
    return _suggester


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
        "/suggest <ingredients> [lunch|dinner|breakfast] — AI recipe suggestion\n"
        "        /expand <ingredient> — find & add recipes online\n"
        "/balance-family [days] — family nutrition report + grocery suggestions\n"
        "/kuhano <recipe_id> [porcija] — zapisnik da ste skuhali nešto\n"
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
            1
            for ing in recipe.ingredients
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
            days = min(max(int(ctx.args[0]), 14), 14)
        except ValueError:
            pass

    store = get_store()
    from recepti.models import RecipeCollection

    collection = RecipeCollection(recipes=store._recipes)

    plans = generate_weekly_plan(
        days=days,
        preferences={
            "recipe_collection": collection,
            "excluded_ids": [],
        },
    )

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
    from recepti.models import RecipeCollection
    from recepti.planner import generate_weekly_plan

    collection = RecipeCollection(recipes=all_recipes)
    plans = generate_weekly_plan(
        days=3,
        preferences={
            "recipe_collection": collection,
        },
    )

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
        await update.message.reply_text(
            f"No meals recorded for child #{child_id} in last {days} days."
        )
        return

    lines = [f"📋 Meal history for child #{child_id} ({days} days):\n"]
    for entry in history[-15:]:  # last 15 entries
        lines.append(
            f"  {entry['date']} {entry['meal_type']}: {entry['recipe_name']} ({entry['amount_eaten'] * 100:.0f}%)"
        )
        if entry["notes"]:
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
        f"✅ Recorded: child #{child_id} ate #{recipe_id} ({amount_eaten * 100:.0f}%) at {meal_type}"
    )


async def suggest_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /suggest <ingredient1>, <ingredient2>, ... [lunch|dinner|breakfast]"""
    meal_type = "lunch"
    if ctx.args:
        last_arg = ctx.args[-1].lower()
        if last_arg in ("breakfast", "lunch", "dinner"):
            meal_type = last_arg
            ingredients = " ".join(ctx.args[:-1]).replace(",", " ")
        else:
            ingredients = " ".join(ctx.args).replace(",", " ")
    else:
        await update.message.reply_text(
            "Usage: /suggest <ingredient1>, <ingredient2>, ... [lunch|dinner|breakfast]\n"
            "Example: /suggest chicken, potatoes, garlic dinner"
        )
        return

    if not ingredients.strip():
        await update.message.reply_text("Please list some ingredients you have.")
        return

    family = get_family()
    family_size = sum(1 for c in family if c.age_years > 0) if family else 9

    ingredient_list = [i.strip() for i in ingredients.split() if i.strip()]
    if not ingredient_list:
        await update.message.reply_text("No valid ingredients provided.")
        return

    store = get_store()
    available = [r.name.lower() for r in store._recipes]
    matched = [i for i in ingredient_list if any(i.lower() in r for r in available)]

    await update.message.reply_text(f"🍽️ Thinking... using {len(ingredient_list)} ingredient(s)...")

    result = suggest_recipe(
        available_ingredients=ingredient_list,
        family_size=family_size,
        meal_type=meal_type,
    )

    if result.get("recipe_id") == "error":
        await update.message.reply_text(
            f"❌ Suggestion unavailable: {result.get('why_this_recipe', 'Unknown error')}"
        )
        return

    lines = [
        f"✨ *Suggested: {result['recipe_name']}*",
        f"Why: {result.get('why_this_recipe', 'N/A')}",
        "",
        f"Scaling for {family_size} people:",
        f"_Notes: {result.get('scaling_notes', 'N/A')}_",
        "",
    ]

    if matched:
        lines.append(f"📦 Matching known recipes: {', '.join(matched)}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def expand_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /expand <ingredient> — auto-search and add recipes."""
    if not ctx.args or len(ctx.args) < 1:
        await update.message.reply_text(
            "❌ Usage: /expand <ingredient>\n\n"
            "Example: /expand red-lentils\n"
            "        /expand mushrooms\n"
            "        /expand spinach"
        )
        return

    ingredient = " ".join(ctx.args).strip()

    await update.message.reply_text(
        f"🔍 Searching for vegetarian recipes with *{ingredient}*..."
    )

    try:
        expander = RecipeExpander(_store)
        results = expander.expand_ingredient(ingredient, max_recipes=3)

        successful = [r for r in results if r.success]
        duplicates = [r for r in results if r.was_duplicate]

        if not successful:
            count_tried = len(results)
            msg = (
                f"❌ No new recipes found for *{ingredient}* "
                f"({count_tried} URLs checked)."
            )
            if duplicates:
                msg += f"\n⊘ {len(duplicates)} were duplicates — already in DB."
            await update.message.reply_text(msg, parse_mode="MarkdownV2")
            return

        recipe_lines = [f"• {r.recipe.name} ({r.recipe.tags.cuisine}, {r.recipe.difficulty})"
                       for r in successful]
        count = len(successful)

        msg = (
            f"✅ Added *{count}* new recipe{'s' if count > 1 else ''}:\n\n"
            + "\n".join(recipe_lines)
        )
        await update.message.reply_text(msg, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Error in /expand command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


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
            lines.append(
                f"  {symbol} {nutrient}: {'met' if meets else 'SHORTAGE: ' + str(assessment['shortages'].get(nutrient, '?'))}"
            )
        lines.append("")

    await update.message.reply_text("\n".join(lines).strip())


async def addmember_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    if not args or len(args) < 3:
        await update.message.reply_text(
            "Usage: /addmember Ime muško/žensko Godine\n"
            "npr. /addmember Marko muško 8"
        )
        return

    text = update.message.text or ""
    tokens = text.strip().split()
    if len(tokens) < 4:
        await update.message.reply_text(
            "Usage: /addmember Ime muško/žensko Godine\n"
            "npr. /addmember Marko muško 8"
        )
        return

    name = tokens[1]
    gender_raw = tokens[2].lower()
    age_raw = tokens[3]

    if name.lower() in ("male", "female"):
        await update.message.reply_text(
            "Usage: /addmember Ime muško/žensko Godine\n"
            "npr. /addmember Marko muško 8"
        )
        return

    if gender_raw not in ("male", "female"):
        await update.message.reply_text(
            "Usage: /addmember Ime muško/žensko Godine\n"
            "npr. /addmember Marko muško 8"
        )
        return

    try:
        age = int(age_raw)
        if age < 1 or age > 120:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "Usage: /addmember Ime muško/žensko Godine\n"
            "npr. /addmember Marko muško 8"
        )
        return

    from recepti.models import FamilyMember

    existing = get_cooking_log().get_members()
    max_id = max(m.id for m in existing) if existing else 0
    new_id = max_id + 1

    member = FamilyMember(
        id=new_id,
        name=name,
        sex=gender_raw,
        age_years=float(age),
    )
    get_cooking_log().add_member(member)

    await update.message.reply_text(
        f"✅ Dodan član: {name} (ID: {new_id}, {gender_raw}, {age} godina)"
    )


async def kuhano_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Upotreba: /kuhano <recipe_id> [porcija]\n"
            "npr. /kuhano 42\n"
            "npr. /kuhano 42 6"
        )
        return

    try:
        recipe_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Nepoznat ID recepta. Koristi /recipes za popis.")
        return

    store = get_store()
    recipe = store.get_recipe_by_id(recipe_id)
    if recipe is None:
        await update.message.reply_text(f"Recept #{recipe_id} ne postoji. Koristi /recipes.")
        return

    portions: float
    if len(args) >= 2:
        try:
            portions = float(args[1])
            if portions <= 0:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("Broj porcija mora biti pozitivan broj.")
            return
    else:
        portions = float(recipe.servings)

    get_cooking_log().log_session(
        recipe_id=recipe_id,
        servings_made=portions,
        servings_served=None,
        notes="",
        log_date=None,
    )

    await update.message.reply_text(
        f"✅ Zapisano: recept #{recipe_id} — {recipe.name}, {portions:.0f} porcija"
    )


async def balance_family_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    days = 7
    if args and args[0].isdigit():
        days = max(1, min(30, int(args[0])))

    members = get_cooking_log().get_members()
    if not members:
        await update.message.reply_text(
            "No family members found. Run:\n"
            "/addmember Name male/female AGE\n"
            "e.g. /addmember Stipe male 35"
        )
        return

    balancer = get_balancer()
    suggester = get_suggester()
    summaries = balancer.family_balance(days=days)
    grocery_lines: list[str] = []

    lines = [f"👨‍👩‍👧‍👦 Family Nutrition ({days}d)\n"]
    for summary in summaries:
        deficient = balancer.deficient_nutrients(summary)
        status = "✅" if not deficient else "⚠️"
        lines.append(f"{status} {summary.member_name}:")
        if not deficient:
            lines.append("  ✅ all targets met")
        else:
            for nut, pct, gap in deficient[:3]:
                lines.append(f"  ❌ {nut}: {pct:.0f}% (need {gap:.1f} more)")
        lines.append("")
        if deficient:
            member_groceries = suggester.suggest_for_summary(summary, top_n=3)
            for item in member_groceries:
                name = item.split(" (~")[0]
                grocery_lines.append(name)

    grocery_unique = list(dict.fromkeys(grocery_lines))
    if grocery_unique:
        lines.append("🛒 Suggested groceries:")
        for item in grocery_unique[:6]:
            lines.append(f"  • {item}")

    await update.message.reply_text("\n".join(lines).strip())


async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Unknown command. Send /help for available commands.")


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
    application.add_handler(CommandHandler("suggest", suggest_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("expand", expand_command))
    application.add_handler(CommandHandler("balance-family", balance_family_command))
    application.add_handler(CommandHandler("addmember", addmember_command))
    application.add_handler(CommandHandler("kuhano", kuhano_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    if FLASK_PORT:
        create_app_fn = _try_import_flask()
        if create_app_fn:
            import threading
            store = get_store()
            flask_app = create_app_fn(store)
            thread = threading.Thread(
                target=lambda: flask_app.run(
                    host="0.0.0.0",
                    port=int(FLASK_PORT),
                    debug=False,
                    use_reloader=False,
                ),
                daemon=True,
            )
            thread.start()
            logger.info(f"Flask REST API running on :{FLASK_PORT}")
        else:
            logger.warning("Flask REST API disabled — flask-cors not available")

    logger.info("Recepti bot starting — polling mode")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
