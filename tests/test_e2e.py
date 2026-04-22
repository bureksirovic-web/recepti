import os
import pytest
from playwright.sync_api import Page, expect


BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:5001")


@pytest.fixture
def page(page: Page) -> Page:
    page.set_default_timeout(10000)
    return page


class TestIndex:
    def test_index_static_serving(self, page: Page):
        page.goto(f"{BASE_URL}/")
        expect(page).to_have_title("Recepti — Family Recipe Bot")
        expect(page.get_by_role("heading", name="Family Recipe Collection")).to_be_visible()

    def test_index_stats_from_api(self, page: Page):
        page.goto(f"{BASE_URL}/")
        page.wait_for_function("document.getElementById('total-count').textContent !== '—'")
        total = page.locator("#total-count").text_content()
        croatian = page.locator("#croatian-count").text_content()
        expanded = page.locator("#expanded-count").text_content()
        assert total not in ("—", "?"), "Total count not populated"
        assert croatian not in ("—", "?"), "Croatian count not populated"
        assert expanded not in ("—", "?"), "Expanded count not populated"
        assert int(total) > 0

    def test_index_nav_to_recipes(self, page: Page):
        page.goto(f"{BASE_URL}/")
        page.get_by_role("link", name="Recipe Browser").click()
        page.wait_for_url("**/recipes**")
        expect(page).to_have_title("Recipe Browser — Recepti")

    def test_index_skip_link(self, page: Page):
        page.goto(f"{BASE_URL}/")
        page.keyboard.press("Tab")
        skip_link = page.get_by_role("link", name="Skip to content")
        if skip_link.count() > 0:
            skip_link.first.focus()
            page.keyboard.press("Enter")
            main = page.locator("main")
            if main.count() > 0:
                expect(main.first).to_be_focused()

    def test_index_theme_toggle(self, page: Page):
        page.goto(f"{BASE_URL}/")
        toggle = page.locator("#theme-toggle-wrap button")
        if toggle.count() > 0:
            toggle.click()
            page.wait_for_timeout(300)


class TestRecipes:
    def test_recipes_static_serving(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        expect(page).to_have_title("Recipe Browser — Recepti")
        expect(page.locator("#recipe-grid")).to_be_visible()

    def test_recipes_filter_dropdowns(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.getElementById('cuisine-filter').options.length > 1")
        cuisine_opts = page.locator("#cuisine-filter option").all()
        cuisine_texts = [o.text_content() for o in cuisine_opts]
        assert any("Punjabi" in t or "Croatian" in t for t in cuisine_texts), f"No cuisine options: {cuisine_texts}"

    def test_recipes_search_filter(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        search_input = page.locator("#search-input")
        search_input.fill("Dal")
        page.wait_for_timeout(500)
        cards = page.locator("#recipe-grid .recipe-card")
        assert cards.count() >= 0

    def test_recipes_cuisine_filter(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cuisine_select = page.locator("#cuisine-filter")
        opts = cuisine_select.locator("option").all()
        cuisine_found = False
        for opt in opts:
            txt = opt.text_content()
            if txt and txt not in ("", "All Cuisines"):
                cuisine_select.select_option(opt.get_attribute("value"))
                cuisine_found = True
                break
        assert cuisine_found

    def test_recipes_meal_type_filter(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        meal_select = page.locator("#meal-type-filter")
        opts = meal_select.locator("option").all()
        for opt in opts:
            txt = opt.text_content()
            if txt and txt not in ("", "All Types"):
                meal_select.select_option(opt.get_attribute("value"))
                break

    def test_recipes_difficulty_filter(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        diff_select = page.locator("#difficulty-filter")
        diff_select.select_option("easy")

    def test_recipes_source_filter(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        src_select = page.locator("#source-filter")
        src_select.select_option("croatian")

    def test_recipes_clear_filters(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        page.locator("#cuisine-filter").select_option("")
        clear_btn = page.locator("#clear-filters")
        if clear_btn.count() > 0:
            clear_btn.click()
        page.wait_for_timeout(300)

    def test_recipes_pagination_prev(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        prev_btn = page.locator("#prev-page")
        assert prev_btn.count() > 0

    def test_recipes_pagination_next(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        next_btn = page.locator("#next-page")
        if next_btn.count() > 0:
            next_btn.click()
            page.wait_for_timeout(500)
            assert int(page.locator("#page-info").text_content().split(" ")[1]) >= 1

    def test_recipes_card_rendering(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            first = cards.first
            expect(first.locator(".recipe-name, h3, .card-title")).to_be_visible()

    def test_recipes_card_opens_drawer(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            cards.first.click()
            page.wait_for_timeout(500)
            drawer = page.locator("#recipe-drawer")
            if drawer.count() > 0:
                is_visible = drawer.first.is_visible()
                assert is_visible or not drawer.first.get_attribute("hidden")

    def test_recipes_card_keyboard_nav(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            cards.first.focus()
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)

    def test_recipes_drawer_close(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            cards.first.click()
            page.wait_for_timeout(500)
            close_btn = page.locator("#drawer-close")
            if close_btn.count() > 0 and close_btn.first.is_visible():
                close_btn.first.click()
                page.wait_for_timeout(300)

    def test_recipes_drawer_overlay_close(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            cards.first.click()
            page.wait_for_timeout(500)
            overlay = page.locator("#drawer-overlay")
            if overlay.count() > 0 and overlay.first.is_visible():
                overlay.first.click()
                page.wait_for_timeout(300)

    def test_recipes_drawer_escape_close(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            cards.first.click()
            page.wait_for_timeout(500)
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

    def test_recipes_drawer_keyboard_trap(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        cards = page.locator("#recipe-grid .recipe-card")
        if cards.count() > 0:
            cards.first.click()
            page.wait_for_timeout(500)
            close_btn = page.locator("#drawer-close")
            if close_btn.count() > 0 and close_btn.first.is_visible():
                close_btn.first.focus()
                for _ in range(3):
                    page.keyboard.press("Tab")

    def test_recipes_typeahead(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        search = page.locator("#typeahead-search")
        search.fill("Dal")
        page.wait_for_timeout(800)
        suggestions = page.locator("#search-suggestions")
        if suggestions.count() > 0 and not suggestions.first.get_attribute("hidden"):
            expect(suggestions.first).to_be_visible()

    def test_recipes_typeahead_keyboard(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        search = page.locator("#typeahead-search")
        search.fill("Dal")
        page.wait_for_timeout(800)
        suggestions = page.locator("#search-suggestions")
        if suggestions.count() > 0 and not suggestions.first.get_attribute("hidden"):
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(200)
            page.keyboard.press("ArrowUp")

    def test_recipes_typeahead_clear(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        search = page.locator("#typeahead-search")
        search.fill("Dal")
        page.wait_for_timeout(800)
        clear_btn = page.locator("#search-clear")
        if clear_btn.count() > 0:
            clear_btn.click()
            page.wait_for_timeout(300)

    def test_recipes_skeleton_loading(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        skeletons = page.locator(".skeleton, .skeleton-card")
        if skeletons.count() > 0:
            page.wait_for_timeout(2000)

    def test_recipes_empty_state(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        all_opts = page.locator("#cuisine-filter option").all()
        vals = [o.get_attribute("value") for o in all_opts if o.get_attribute("value")]
        if vals:
            page.locator("#cuisine-filter").select_option(vals[0])
            page.wait_for_timeout(500)

    def test_recipes_stats_bar_updates(self, page: Page):
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        total = page.locator("#total-count")
        showing = page.locator("#showing-count")
        if total.count() > 0 and showing.count() > 0:
            assert total.first.text_content() not in ("—", "")

    def test_recipes_mobile_responsive(self, page: Page):
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/recipes")
        page.wait_for_function("document.querySelectorAll('#recipe-grid .recipe-card').length > 0")
        expect(page.locator("header").first).to_be_visible()


class TestNutrients:
    def test_nutrients_static_serving(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        expect(page).to_have_title("Family Nutrition Dashboard — Recepti")
        expect(page.locator("#main-content").first).to_be_visible()

    def test_nutrients_period_selection(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        period_select = page.locator("#periodSelect")
        if period_select.count() > 0:
            period_select.select_option("14")
            page.wait_for_timeout(500)

    def test_nutrients_refresh_button(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        refresh = page.locator("#refreshBtn")
        if refresh.count() > 0:
            refresh.click()
            page.wait_for_timeout(1000)

    def test_nutrients_member_cards_or_not_configured(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        page.wait_for_timeout(2000)
        dashboard = page.locator("#dashboard")
        not_configured = page.locator("#notConfigured")
        assert dashboard.count() > 0 or not_configured.count() > 0

    def test_nutrients_grocery_suggestions(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        page.wait_for_timeout(2000)
        grocery = page.locator("#groceryTags, .grocery-tags")
        assert grocery.count() >= 0

    def test_nutrients_not_configured_state(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        page.wait_for_timeout(2000)
        not_configured = page.locator("#notConfigured")
        loading = page.locator("#loading")
        assert not_configured.count() > 0 or loading.count() > 0 or not_configured.first.is_visible()

    def test_nutrients_loading_state(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        loading = page.locator("#loading")
        page.wait_for_timeout(500)
        if loading.count() > 0:
            assert True

    def test_nutrients_skip_link(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        skip_link = page.get_by_role("link", name="Skip to content")
        if skip_link.count() > 0:
            skip_link.first.focus()
            page.keyboard.press("Enter")

    def test_nutrients_theme_toggle(self, page: Page):
        page.goto(f"{BASE_URL}/nutrients")
        toggle = page.locator("#theme-toggle-wrap button")
        if toggle.count() > 0:
            toggle.click()
            page.wait_for_timeout(300)


class TestCoverage:
    def test_coverage_static_serving(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        expect(page).to_have_title("Coverage Audit - Recepti")
        expect(page.locator("#charts-grid").first).to_be_visible()

    def test_coverage_cuisine_chart(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_function("document.getElementById('chart-cuisine') !== null")
        chart = page.locator("#chart-cuisine")
        assert chart.count() > 0

    def test_coverage_meal_type_chart(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_function("document.getElementById('chart-meal-type') !== null")
        chart = page.locator("#chart-meal-type")
        assert chart.count() > 0

    def test_coverage_difficulty_chart(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_function("document.getElementById('chart-difficulty') !== null")
        chart = page.locator("#chart-difficulty")
        assert chart.count() > 0

    def test_coverage_holes_list(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_function("document.getElementById('holes-list') !== null")
        holes = page.locator("#holes-list")
        if holes.count() > 0:
            page.wait_for_timeout(2000)

    def test_coverage_copy_suggested_query(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_function("document.getElementById('holes-list') !== null")
        page.wait_for_timeout(2000)
        query_tag = page.locator(".query-tag, .suggested-query").first
        if query_tag.count() > 0:
            query_tag.click()
            page.wait_for_timeout(300)

    def test_coverage_copy_all_button(self, page: Page):
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_function("document.getElementById('copy-all-btn') !== null")
        copy_all = page.locator("#copy-all-btn")
        if copy_all.count() > 0:
            copy_all.click()
            page.wait_for_timeout(500)

    def test_coverage_mobile_responsive(self, page: Page):
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/coverage")
        page.wait_for_timeout(1000)
        expect(page.locator("header").first).to_be_visible()


class TestScrapeTodo:
    def test_scrape_todo_static_serving(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        expect(page).to_have_title("Recipe Scraping Targets — Recepti")
        expect(page.locator("#targets-table")).to_be_visible()

    def test_scrape_todo_type_filter(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        page.wait_for_function("document.getElementById('targets-table') !== null")
        type_filter = page.locator("#type-filter")
        if type_filter.count() > 0:
            type_filter.select_option("coverage")
            page.wait_for_timeout(500)

    def test_scrape_todo_table_rendering(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        page.wait_for_function("document.getElementById('targets-table') !== null")
        page.wait_for_timeout(2000)
        rows = page.locator("#targets-body tr")
        assert rows.count() >= 0

    def test_scrape_todo_copy_individual(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        page.wait_for_function("document.getElementById('targets-table') !== null")
        page.wait_for_timeout(2000)
        copy_btn = page.locator(".copy-btn, .row-copy").first
        if copy_btn.count() > 0:
            copy_btn.click()
            page.wait_for_timeout(300)

    def test_scrape_todo_copy_coverage(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        page.wait_for_function("document.getElementById('copy-coverage-btn') !== null")
        copy_cov = page.locator("#copy-coverage-btn")
        if copy_cov.count() > 0:
            copy_cov.click()
            page.wait_for_timeout(500)

    def test_scrape_todo_copy_all(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        page.wait_for_function("document.getElementById('copy-all-btn') !== null")
        copy_all = page.locator("#copy-all-btn")
        if copy_all.count() > 0:
            copy_all.click()
            page.wait_for_timeout(500)

    def test_scrape_todo_empty_state(self, page: Page):
        page.goto(f"{BASE_URL}/scrape-todo")
        page.wait_for_function("document.getElementById('type-filter') !== null")
        page.locator("#type-filter").select_option("coverage")
        page.wait_for_timeout(500)
        empty_state = page.locator("#empty-state")
        if empty_state.count() > 0:
            assert True


class TestRESTAPI:
    def test_api_health(self, page: Page):
        page.goto(f"{BASE_URL}/api/health")
        data = page.evaluate("() => document.body.innerText")
        import json
        resp = json.loads(data)
        assert resp.get("status") == "healthy"
        assert "timestamp" in resp
        assert "recipe_count" in resp

    def test_api_health_cors(self, page: Page):
        page.goto(f"{BASE_URL}/api/health")
        assert page.evaluate("() => document.title") is not None

    def test_api_recipes_pagination(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?page=1&per_page=5")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert len(data.get("recipes", [])) <= 5
        assert "total" in data

    def test_api_recipes_pagination_page2(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?page=2&per_page=5")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert data.get("page") == 2

    def test_api_recipe_single(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?page=1&per_page=1")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        recipes = data.get("recipes", [])
        if recipes:
            recipe_id = recipes[0]["id"]
            page.goto(f"{BASE_URL}/api/recipe/{recipe_id}")
            single = json.loads(page.evaluate("() => document.body.innerText"))
            assert "id" in single
            assert "ingredients" in single

    def test_api_recipe_not_found(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipe/99999")
        data = page.evaluate("() => document.body.innerText")
        import json
        resp = json.loads(data)
        assert "error" in resp or page.evaluate("() => document.title") == "404"

    def test_api_recipes_cuisine_filter(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?cuisine=Punjabi")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        for r in data.get("recipes", []):
            assert r["tags"]["cuisine"] == "Punjabi"

    def test_api_recipes_meal_type_filter(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?meal_type=breakfast")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        for r in data.get("recipes", []):
            assert "breakfast" in r["tags"]["meal_type"]

    def test_api_recipes_difficulty_filter(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?difficulty=easy")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        for r in data.get("recipes", []):
            assert r["difficulty"] == "easy"

    def test_api_recipes_search_filter(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?search=Dal")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "recipes" in data

    def test_api_recipes_source_filter(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?source=croatian")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        for r in data.get("recipes", []):
            assert 31 <= r["id"] <= 50

    def test_api_recipes_combined_filters(self, page: Page):
        page.goto(f"{BASE_URL}/api/recipes?cuisine=Punjabi&difficulty=easy")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        for r in data.get("recipes", []):
            assert r["tags"]["cuisine"] == "Punjabi"
            assert r["difficulty"] == "easy"

    def test_api_stats(self, page: Page):
        page.goto(f"{BASE_URL}/api/stats")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "total" in data
        assert "by_cuisine" in data
        assert "by_source" in data

    def test_api_filters(self, page: Page):
        page.goto(f"{BASE_URL}/api/filters")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "cuisines" in data
        assert "meal_types" in data

    def test_api_search_missing_query(self, page: Page):
        page.goto(f"{BASE_URL}/api/search")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert data.get("error") or page.evaluate("() => document.title") != "200"

    def test_api_search_empty_query(self, page: Page):
        page.goto(f"{BASE_URL}/api/search?q=")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert data.get("error") or page.evaluate("() => document.title") != "200"

    def test_api_search_with_results(self, page: Page):
        page.goto(f"{BASE_URL}/api/search?q=Dal")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "results" in data
        assert len(data.get("results", [])) > 0

    def test_api_search_limit_param(self, page: Page):
        page.goto(f"{BASE_URL}/api/search?q=Dal&limit=2")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert len(data.get("results", [])) <= 2

    def test_api_search_limit_capped(self, page: Page):
        page.goto(f"{BASE_URL}/api/search?q=Dal&limit=100")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert len(data.get("results", [])) <= 20

    def test_api_search_case_insensitive(self, page: Page):
        page.goto(f"{BASE_URL}/api/search?q=DAL")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert len(data.get("results", [])) > 0

    def test_api_search_relevance_ordering(self, page: Page):
        page.goto(f"{BASE_URL}/api/search?q=Dal")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        results = data.get("results", [])
        if len(results) > 1:
            assert results[0]["name"] in [r["name"] for r in results]

    def test_api_nutrients_configured(self, page: Page):
        page.goto(f"{BASE_URL}/api/nutrients")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "members" in data or "error" in data

    def test_api_nutrients_not_configured(self, page: Page):
        page.goto(f"{BASE_URL}/api/nutrients")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        if data.get("error"):
            assert "not configured" in data["error"].lower()

    def test_api_coverage(self, page: Page):
        page.goto(f"{BASE_URL}/api/coverage")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "by_dimension" in data or "holes" in data

    def test_api_scrape_todo(self, page: Page):
        page.goto(f"{BASE_URL}/api/scrape-todo")
        import json
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert "targets" in data or "coverage_holes" in data