# Recepti E2E Test Plan

## Overview

This test plan covers all pages, endpoints, and interactive features of the Recepti web application. The goal is to ensure reliable operation across desktop and mobile browsers with proper accessibility support.

**Test Environment:**
- Browser: Chromium (Playwright)
- Test Framework: pytest + pytest-playwright
- Base URL: Configurable via environment variable

---

## Page: Index (/)

The homepage displays recipe statistics fetched from the API.

### TC-INDEX-001: Static file serving
**Description:** Verify index.html is served at GET /
**Expected Outcome:** HTTP 200, Content-Type text/html, HTML with `<title>Recepti — Family Recipe Bot</title>`
**Priority:** P0
**Category:** Static page serving

### TC-INDEX-002: Stats display from API
**Description:** Verify total, croatian-count, and expanded-count elements are populated from `/api/stats`
**Expected Outcome:** All three stat cards display numeric values (not "—" or "?"), matching actual recipe counts
**Priority:** P0
**Category:** Data rendering in HTML

### TC-INDEX-003: Navigation links to Recipe Browser
**Description:** Click link to /recipes navigates to Recipe Browser page
**Expected Outcome:** URL changes to /recipes, recipes.html content renders
**Priority:** P1
**Category:** Static page serving

### TC-INDEX-004: Skip link accessibility
**Description:** Tab to skip-link and activate skips to main content
**Expected Outcome:** Skip link visible on Tab focus, pressing Enter focuses main content area
**Priority:** P1
**Category:** Accessibility

### TC-INDEX-005: Theme toggle presence
**Description:** Verify theme toggle widget renders in header
**Expected Outcome:** Theme toggle button visible in header, clickable without errors
**Priority:** P2
**Category:** JavaScript widget interactions

---

## Page: Recipe Browser (/recipes)

The recipe browser displays paginated recipe cards with filtering and search capabilities.

### TC-REC-001: Static file serving
**Description:** Verify recipes.html is served at GET /recipes
**Expected Outcome:** HTTP 200, Content-Type text/html, contains recipe grid and drawer elements
**Priority:** P0
**Category:** Static page serving

### TC-REC-002: Filter dropdown population
**Description:** Verify cuisine and meal-type dropdowns populate from `/api/filters`
**Expected Outcome:** Dropdowns contain valid cuisine options (e.g., Punjabi, Croatian) and meal types
**Priority:** P0
**Category:** Data rendering in HTML

### TC-REC-003: Search input filtering
**Description:** Type in search-input filters recipe cards by name/description
**Expected Outcome:** Recipe cards update to show only matching recipes, empty state if no matches
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-REC-004: Cuisine filter
**Description:** Select cuisine from dropdown filters results
**Expected Outcome:** Only recipes with matching cuisine tags display, stats update
**Priority:** P0
**Category:** Data rendering in HTML

### TC-REC-005: Meal type filter
**Description:** Select meal type from dropdown filters results
**Expected Outcome:** Only recipes with matching meal_type display
**Priority:** P0
**Category:** Data rendering in HTML

### TC-REC-006: Difficulty filter
**Description:** Select difficulty level from dropdown filters results
**Expected Outcome:** Only recipes with matching difficulty display
**Priority:** P1
**Category:** Data rendering in HTML

### TC-REC-007: Source filter (original/croatian/expanded)
**Description:** Select source filter shows only recipes from that batch
**Expected Outcome:** Original (id ≤30), Croatian (31-50), Expanded (≥51) filtered correctly
**Priority:** P1
**Category:** Data rendering in HTML

### TC-REC-008: Clear filters button
**Description:** Click clear-filters resets all dropdowns and search
**Expected Outcome:** All filters reset to default, all recipes display
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-REC-009: Pagination previous button
**Description:** Click previous button when on page > 1
**Expected Outcome:** Page decrements, showing previous set of recipes
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-REC-010: Pagination next button
**Description:** Click next button when additional pages exist
**Expected Outcome:** Page increments, showing next set of recipes, button disabled on last page
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-REC-011: Recipe card rendering
**Description:** Verify recipe cards display name, description, cuisine tag, difficulty badge, times
**Expected Outcome:** Each card shows: recipe name, description truncated, cuisine tag, difficulty badge, prep/cook/total times
**Priority:** P0
**Category:** Data rendering in HTML

### TC-REC-012: Recipe card click opens drawer
**Description:** Click on recipe card opens detail drawer
**Expected Outcome:** Drawer slides in from right, overlay appears, body scroll locked
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-REC-013: Recipe card keyboard navigation
**Description:** Focus card and press Enter/Space to open drawer
**Expected Outcome:** Drawer opens, focus moves to close button
**Priority:** P1
**Category:** Accessibility

### TC-REC-014: Drawer close button
**Description:** Click X button to close drawer
**Expected Outcome:** Drawer closes, overlay removed, body scroll restored, focus returns to card
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-REC-015: Drawer overlay click closes
**Description:** Click on drawer overlay behind drawer
**Expected Outcome:** Drawer closes, overlay removed
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-REC-016: Drawer Escape key closes
**Description:** Press Escape while drawer is open
**Expected Outcome:** Drawer closes, focus returns to triggering card
**Priority:** P1
**Category:** Accessibility

### TC-REC-017: Drawer keyboard trap
**Description:** Tab through drawer elements cycles within drawer
**Expected Outcome:** Tab cycles between close button and interactive elements, does not exit drawer
**Priority:** P1
**Category:** Accessibility

### TC-REC-018: Typeahead search appears
**Description:** Type in typeahead-search field triggers API search suggestions
**Expected Outcome:** Dropdown appears with matching suggestions (max 8), highlighted search term
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-REC-019: Typeahead keyboard navigation
**Description:** Use ArrowUp/Down to navigate suggestions, Enter to select
**Expected Outcome:** Selection highlights, Enter opens drawer for selected recipe, input clears
**Priority:** P1
**Category:** Accessibility

### TC-REC-020: Typeahead clear button
**Description:** Click clear button when input has text
**Expected Outcome:** Input clears, suggestions hide, clear button hides
**Priority:** P2
**Category:** JavaScript widget interactions

### TC-REC-021: Skeleton loading states
**Description:** Reload page observe skeleton cards during API fetch
**Expected Outcome:** Skeleton cards display immediately, replaced with real cards after load
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-REC-022: Empty state display
**Description:** Apply filter that matches no recipes
**Expected Outcome:** Empty state message displays ("No recipes match your filters")
**Priority:** P2
**Category:** Data rendering in HTML

### TC-REC-023: Stats bar updates
**Description:** Apply filters observe stats bar update
**Expected Outcome:** Total count and showing count reflect filtered results
**Priority:** P1
**Category:** Data rendering in HTML

### TC-REC-024: Mobile responsive layout
**Description:** View page at 375px width
**Expected Outcome:** Filters aside stacks above content, recipe grid single column
**Priority:** P1
**Category:** Mobile responsive

### TC-REC-025: Print styles
**Description:** Print page (Ctrl+P)
**Expected Outcome:** Print-friendly layout, no drawer overlay, essential content only
**Priority:** P2
**Category:** Print styles

---

## Page: Nutrition Dashboard (/nutrients)

The nutrition dashboard displays family member nutrient balance and grocery suggestions.

### TC-NUT-001: Static file serving
**Description:** Verify nutrients.html is served at GET /nutrients
**Expected Outcome:** HTTP 200, Content-Type text/html, contains period select and refresh button
**Priority:** P0
**Category:** Static page serving

### TC-NUT-002: Period selection (7/14/30 days)
**Description:** Change period select triggers data reload
**Expected Outcome:** Data updates to reflect selected time period
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-NUT-003: Refresh button
**Description:** Click refresh button fetches fresh data
**Expected Outcome:** Loading indicator displays, data reloads
**Priority:** P2
**Category:** JavaScript widget interactions

### TC-NUT-004: Member cards rendering
**Expected Outcome:** Each family member displays with nutrient gaps highlighted
**Priority:** P0
**Category:** Data rendering in HTML

### TC-NUT-005: Grocery suggestions display
**Description:** Verify suggested groceries render in dedicated card
**Expected Outcome:** Grocery tags render with clickable items for clipboard copy
**Priority:** P1
**Category:** Data rendering in HTML

### TC-NUT-006: Not configured state
**Description:** When family_members.json missing, show not-configured error
**Expected Outcome:** Error message displays with instructions to add members via Telegram bot
**Priority:** P0
**Category:** Data rendering in HTML

### TC-NUT-007: Loading state display
**Description:** Observe loading state before API responds
**Expected Outcome:** Loading message displays during data fetch
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-NUT-008: Chart.js renders nutrient charts
**Description:** Verify Chart.js library loads and renders visualization
**Expected Outcome:** Charts display percentage of RDA for each nutrient
**Priority:** P1
**Category:** Data rendering in HTML

### TC-NUT-009: Skip link and accessibility
**Description:** Verify skip link and aria labels present
**Expected Outcome:** Skip link present, all interactive elements labeled
**Priority:** P2
**Category:** Accessibility

### TC-NUT-010: Theme toggle
**Description:** Toggle theme and observe visual change
**Expected Outcome:** Colors invert appropriately, preference persisted to localStorage
**Priority:** P2
**Category:** JavaScript widget interactions

---

## Page: Coverage Audit (/coverage)

The coverage audit displays recipe collection gaps by dimension.

### TC-COV-001: Static file serving
**Description:** Verify coverage.html is served at GET /coverage
**Expected Outcome:** HTTP 200, Content-Type text/html, contains charts-grid and holes-list
**Priority:** P0
**Category:** Static page serving

### TC-COV-002: Cuisine chart rendering
**Description:** Verify cuisine bar chart renders with data
**Expected Outcome:** Bar chart displays recipe counts per cuisine
**Priority:** P0
**Category:** Data rendering in HTML

### TC-COV-003: Meal type chart rendering
**Description:** Verify meal type bar chart renders with data
**Expected Outcome:** Bar chart displays recipe counts per meal type
**Priority:** P0
**Category:** Data rendering in HTML

### TC-COV-004: Difficulty chart rendering
**Description:** Verify difficulty bar chart renders with color-coded bars
**Expected Outcome:** Bar chart displays counts per difficulty, colors indicate level
**Priority:** P0
**Category:** Data rendering in HTML

### TC-COV-005: Coverage holes list
**Description:** Verify holes list displays dimensions with < 3 recipes
**Expected Outcome:** Each hole shows dimension, value, count, status (SPARSE/EMPTY), suggested queries
**Priority:** P0
**Category:** Data rendering in HTML

### TC-COV-006: Copy individual suggested query
**Description:** Click on query tag within hole row
**Expected Outcome:** Query copied to clipboard, visual feedback shown
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-COV-007: Copy all top holes button
**Description:** Click copy-all-btn button
**Expected Outcome:** All suggested queries from top priority holes copied, button shows feedback
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-COV-008: Hole row keyboard activation
**Description:** Focus hole row and press Enter
**Expected Outcome:** Same behavior as click, queries copied
**Priority:** P2
**Category:** Accessibility

### TC-COV-009: Mobile responsive
**Description:** View at 375px width
**Expected Outcome:** Charts stack vertically, holes sidebar below main content
**Priority:** P2
**Category:** Mobile responsive

---

## Page: Scrape Targets (/scrape-todo)

The scrape targets page displays prioritized queries for recipe collection expansion.

### TC-SCR-001: Static file serving
**Description:** Verify scrape-todo.html is served at GET /scrape-todo
**Expected Outcome:** HTTP 200, Content-Type text/html, contains targets-table
**Priority:** P0
**Category:** Static page serving

### TC-SCR-002: Type filter dropdown
**Description:** Select different type filter values
**Expected Outcome:** Table filters to show only matching type (coverage/rejection/both)
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-SCR-003: Table row rendering
**Description:** Verify table displays type badge, query, priority bar, reason, copy button
**Expected Outcome:** Each row has colored type badge, monospace query, progress bar, reason text, copy icon
**Priority:** P0
**Category:** Data rendering in HTML

### TC-SCR-004: Copy individual query
**Description:** Click on query text or copy button
**Expected Outcome:** Query copied, toast shows "Query copied!"
**Priority:** P0
**Category:** JavaScript widget interactions

### TC-SCR-005: Copy coverage button
**Description:** Click copy-coverage-btn button
**Expected Outcome:** Only coverage-type queries copied, toast confirms count
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-SCR-006: Copy all button
**Description:** Click copy-all-btn button
**Expected Outcome:** All visible queries copied, toast confirms count
**Priority:** P1
**Category:** JavaScript widget interactions

### TC-SCR-007: Empty state display
**Description:** Apply filter matching no targets
**Expected Outcome:** Empty state displays with helpful message
**Priority:** P1
**Category:** Data rendering in HTML

---

## REST API Endpoints

### TC-API-001: Health check endpoint
**Description:** GET /api/health
**Expected Outcome:** 200, JSON with status="healthy", timestamp, recipe_count
**Priority:** P0
**Category:** REST API endpoints

### TC-API-002: Health check CORS headers
**Description:** Verify CORS headers on health endpoint
**Expected Outcome:** Access-Control-Allow-Origin header present
**Priority:** P1
**Category:** REST API endpoints

### TC-API-003: Recipes list pagination
**Description:** GET /api/recipes?page=1&per_page=5
**Expected Outcome:** Returns exactly 5 recipes, total count, pagination metadata
**Priority:** P0
**Category:** REST API endpoints

### TC-API-004: Recipes list pagination page 2
**Description:** GET /api/recipes?page=2&per_page=5
**Expected Outcome:** Returns recipes 6-10, prev/next links functional
**Priority:** P0
**Category:** REST API endpoints

### TC-API-005: Recipe single retrieval
**Description:** GET /api/recipes/1
**Expected Outcome:** Returns full recipe object with id=1, includes ingredients array, instructions array, tags object
**Priority:** P0
**Category:** REST API endpoints

### TC-API-006: Recipe not found
**Description:** GET /api/recipes/9999
**Expected Outcome:** 404, JSON error message
**Priority:** P0
**Category:** REST API endpoints

### TC-API-007: Recipes cuisine filter
**Description:** GET /api/recipes?cuisine=Punjabi
**Expected Outcome:** Returns only Punjabi cuisine recipes
**Priority:** P0
**Category:** REST API endpoints

### TC-API-008: Recipes meal_type filter
**Description:** GET /api/recipes?meal_type=breakfast
**Expected Outcome:** Returns only breakfast meal_type recipes
**Priority:** P0
**Category:** REST API endpoints

### TC-API-009: Recipes difficulty filter
**Description:** GET /api/recipes?difficulty=easy
**Expected Outcome:** Returns only easy difficulty recipes
**Priority:** P1
**Category:** REST API endpoints

### TC-API-010: Recipes search filter
**Description:** GET /api/recipes?search=Dal
**Expected Outcome:** Returns recipes matching "Dal" in name or description
**Priority:** P0
**Category:** REST API endpoints

### TC-API-011: Recipes source filter
**Description:** GET /api/recipes?source=croatian
**Expected Outcome:** Returns only recipes with id 31-50
**Priority:** P1
**Category:** REST API endpoints

### TC-API-012: Recipes combined filters
**Description:** GET /api/recipes?cuisine=Punjabi&difficulty=easy
**Expected Outcome:** Returns recipes matching both criteria
**Priority:** P1
**Category:** REST API endpoints

### TC-API-013: Stats endpoint
**Description:** GET /api/stats
**Expected Outcome:** JSON with total, by_cuisine, by_meal_type, by_difficulty, by_source, recently_added
**Priority:** P0
**Category:** REST API endpoints

### TC-API-014: Filters endpoint
**Description:** GET /api/filters
**Expected Outcome:** JSON with cuisines, meal_types, dietary_tags, difficulties, sources arrays
**Priority:** P0
**Category:** REST API endpoints

### TC-API-015: Search missing query
**Description:** GET /api/search
**Expected Outcome:** 400 error, "Query parameter 'q' is required"
**Priority:** P0
**Category:** REST API endpoints

### TC-API-016: Search empty query
**Description:** GET /api/search?q=
**Expected Outcome:** 400 error
**Priority:** P0
**Category:** REST API endpoints

### TC-API-017: Search with results
**Description:** GET /api/search?q=Dal
**Expected Outcome:** 200, results array with matching recipes, max 8 results
**Priority:** P0
**Category:** REST API endpoints

### TC-API-018: Search limit parameter
**Description:** GET /api/search?q=Dal&limit=2
**Expected Outcome:** Max 2 results returned
**Priority:** P0
**Category:** REST API endpoints

### TC-API-019: Search limit capped at 20
**Description:** GET /api/search?q=Dal&limit=100
**Expected Outcome:** Max 20 results returned (capped)
**Priority:** P1
**Category:** REST API endpoints

### TC-API-020: Search case insensitivity
**Description:** GET /api/search?q=PALAK
**Expected Outcome:** Matches "Palak Paneer" regardless of case
**Priority:** P0
**Category:** REST API endpoints

### TC-API-021: Search relevance ordering
**Description:** GET /api/search?q=Dal
**Expected Outcome:** Exact match first, starts-with before contains, description matches last
**Priority:** P0
**Category:** REST API endpoints

### TC-API-022: Nutrients endpoint configured
**Description:** GET /api/nutrients with data files present
**Expected Outcome:** 200, family member nutrient data with gaps
**Priority:** P1
**Category:** REST API endpoints

### TC-API-023: Nutrients endpoint not configured
**Description:** GET /api/nutrients without data files
**Expected Outcome:** 503, "Nutrient tracking not configured yet"
**Priority:** P1
**Category:** REST API endpoints

### TC-API-024: Coverage endpoint
**Description:** GET /api/coverage
**Expected Outcome:** 200, by_dimension (cuisine/meal_type/difficulty), holes array
**Priority:** P0
**Category:** REST API endpoints

### TC-API-025: Scrape-todo endpoint
**Description:** GET /api/scrape-todo
**Expected Outcome:** 200, targets array (max 20), coverage_holes count, rejected_cuisines
**Priority:** P0
**Category:** REST API endpoints

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Index Page | 5 |
| Recipe Browser | 25 |
| Nutrition Dashboard | 10 |
| Coverage Audit | 9 |
| Scrape Targets | 7 |
| REST API | 25 |
| **TOTAL** | **81** |

---

## Priority Definitions

- **P0 (Critical):** Core functionality, page loads, essential features
- **P1 (Important):** Secondary features, user experience enhancements
- **P2 (Nice-to-have):** Polish, edge cases, accessibility improvements

---

## Test Execution Notes

1. Run with Playwright browser configured for mobile viewport testing
2. Use fixture with sample_recipes for deterministic results
3. Mock API responses for offline testing scenarios
4. Verify localStorage persistence for theme preference
5. Test keyboard navigation separately from mouse interactions