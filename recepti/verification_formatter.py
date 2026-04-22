"""Croatian Telegram verification message formatter for parsed meals."""

from recepti.meal_parser import EaterEntry, MealParsingResult, ParsedMeal

MEAL_LABELS = {
    "breakfast": "🍳 DORUČAK",
    "lunch": "🥘 RUČAK",
    "dinner": "🍽️ VEČERA",
}

MAX_MESSAGE_LEN = 4000


def _format_amount(amount: float) -> str:
    if amount == 0.0:
        return "NIJE JELA"
    if amount == 0.5:
        return "½ porcije"
    if amount == 1.0:
        return "1 porcija"
    if amount == 2.0:
        return "2 porcije"
    if amount == 2.5:
        return "2½ porcije"
    whole = int(amount)
    if whole == amount:
        return f"{whole} porcija"
    return f"{amount} porcija"


def _format_eater(eater: EaterEntry, member_matches: dict[str, str]) -> str:
    matched = member_matches.get(eater.member_name)
    if matched:
        name_display = f"✅ {matched}"
    else:
        name_display = f"❓ {eater.member_name}"

    amount_display = _format_amount(eater.amount)
    if eater.amount == 0.0:
        amount_display = f"❌ {amount_display}"

    notes = f" | {eater.notes}" if eater.notes else ""
    return f"  • {name_display}: {amount_display}{notes}"


def _format_recipe_name(recipe_name: str, recipe_matches: dict[str, str]) -> str:
    matched = recipe_matches.get(recipe_name)
    if matched:
        return f"✅ {matched}"
    return f"⚠️ {recipe_name}"


def format_verification_message(
    result: MealParsingResult,
    member_matches: dict[str, str],
    recipe_matches: dict[str, str],
    raw_text: str,
) -> str:
    """
    Format a parsed meal result as a Croatian Telegram verification message.

    Args:
        result: parsed meal data from meal_parser
        member_matches: {unmatched_name: matched_family_member_name}
        recipe_matches: {unrecognized_recipe: best_match_recipe_name}
        raw_text: original user message (shown for reference)

    Returns:
        Formatted Croatian Telegram message string
    """
    if not result.meals:
        return (
            "📋 PROVJERI / VERIFY:\n\n"
            "❌ Nisam uspjela raspoznati obroke u poruci.\n"
            "Molim te napiši slobodno, npr:\n"
            '"ručak: šuklji, tomi je pojeo 2 porcije, ivana 1 porciju"\n'
            '"danas za večeru: salata, svi su jeli"'
        )

    lines: list[str] = ["📋 PROVJERI / VERIFY:", ""]

    for meal in result.meals:
        label = MEAL_LABELS.get(meal.meal_type, f"🍽️ {meal.meal_type.upper()}")
        lines.append("━" * 21)
        lines.append(label)
        lines.append("━" * 21)

        recipe_display = _format_recipe_name(meal.recipe_name, recipe_matches)
        lines.append(f"🍽️ Jelo: {recipe_display}")
        lines.append("🥗 Osobe:")

        for eater in meal.eaters:
            lines.append(_format_eater(eater, member_matches))

        lines.append("")

    lines.append("━" * 21)
    lines.append("")

    unmatched_recipes = [
        r for r in result.unmatched_recipes if r not in recipe_matches
    ]
    if unmatched_recipes:
        lines.append(f"⚠️ Neprepoznatih jela: {', '.join(unmatched_recipes)}")

    unmatched_members_display = [
        m for m in result.unmatched_members if m not in member_matches
    ]
    if unmatched_members_display:
        lines.append(f"❓ Neprepoznatih osoba: {', '.join(unmatched_members_display)}")

    if unmatched_recipes or unmatched_members_display:
        lines.append("")

    lines.append("✅ Potvrdi → pošalji")
    lines.append("❌ Ispravi → napiši ispravno")
    lines.append("")
    lines.append(f"_{raw_text[:200]}{'...' if len(raw_text) > 200 else ''}_")

    message = "\n".join(lines)

    if len(message) > MAX_MESSAGE_LEN:
        message = message[:MAX_MESSAGE_LEN - 3] + "..."

    return message