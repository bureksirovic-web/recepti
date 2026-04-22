const API = '/api';
let allRecipes = [];
let filtered = [];
let page = 1;
const PER_PAGE = 12;
const SKELETON_COUNT = 12;

function showSkeletons() {
    const grid = document.getElementById('recipe-grid');
    const skeletons = Array.from({ length: SKELETON_COUNT }, () =>
        `<div class="recipe-card card skeleton-card"></div>`
    ).join('');
    grid.innerHTML = skeletons;
}

function hideSkeletons() {
    const grid = document.getElementById('recipe-grid');
    const skeletons = grid.querySelectorAll('.skeleton-card');
    skeletons.forEach(s => s.remove());
}

async function init() {
    showSkeletons();
    await Promise.all([loadFilters(), loadRecipes()]);
    setupListeners();
}

async function loadFilters() {
    try {
        const res = await fetch(`${API}/filters`);
        const data = await res.json();
        populate('cuisine-filter', data.cuisines);
        populate('meal-type-filter', data.meal_types);
    } catch (e) {
        console.error('Failed to load filters', e);
    }
}

function populate(selectId, options) {
    const select = document.getElementById(selectId);
    options.forEach(opt => {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        select.appendChild(o);
    });
}

async function loadRecipes() {
    try {
        const res = await fetch(`${API}/recipes?per_page=200`);
        const data = await res.json();
        allRecipes = data.recipes;
        hideSkeletons();
        applyFilters();
    } catch (e) {
        hideSkeletons();
        document.getElementById('recipe-grid').innerHTML =
            '<div class="loading">Failed to load recipes. Is the server running?</div>';
    }
}

function applyFilters() {
    const s = document.getElementById('search-input').value.toLowerCase();
    const c = document.getElementById('cuisine-filter').value;
    const m = document.getElementById('meal-type-filter').value;
    const d = document.getElementById('difficulty-filter').value;
    const src = document.getElementById('source-filter').value;

    filtered = allRecipes.filter(r => {
        if (s && !r.name.toLowerCase().includes(s) && !r.description.toLowerCase().includes(s)) return false;
        if (c && r.tags.cuisine !== c) return false;
        if (m && r.tags.meal_type !== m) return false;
        if (d && r.difficulty !== d) return false;
        if (src === 'original' && r.id > 30) return false;
        if (src === 'croatian' && (r.id < 31 || r.id > 50)) return false;
        if (src === 'expanded' && r.id < 51) return false;
        return true;
    });

    page = 1;
    hideSkeletons();
    render();
    updateStats();
}

function render() {
    const grid = document.getElementById('recipe-grid');
    const start = (page - 1) * PER_PAGE;
    const slice = filtered.slice(start, start + PER_PAGE);

    if (slice.length === 0) {
        grid.innerHTML = '<div class="loading">No recipes match your filters.</div>';
        return;
    }

    grid.innerHTML = slice.map(r => card(r)).join('');
    updatePagination();
}

function card(r) {
    const badge = r.id <= 30 ? 'original' : r.id <= 50 ? 'croatian' : 'expanded';
    const badgeLabel = r.id <= 30 ? 'Indian' : r.id <= 50 ? 'Croatian' : 'Expanded';
    const diffClass = `difficulty-${r.difficulty}`;

    return `
        <article class="recipe-card" tabindex="0" role="button" aria-label="View recipe: ${esc(r.name)}" data-recipe-id="${r.id}">
            <header>
                <h3>${esc(r.name)}</h3>
                <span class="source-badge ${badge}">${badgeLabel}</span>
            </header>
            <p class="description">${esc(r.description)}</p>
            <div class="meta">
                <span class="tag">${esc(r.tags.cuisine)}</span>
                <span class="tag">${esc(r.tags.meal_type)}</span>
                <span class="tag ${diffClass}">${r.difficulty}</span>
            </div>
            <div class="times">
                <span>Prep: ${r.prep_time_min}m</span>
                <span>Cook: ${r.cook_time_min}m</span>
                <span>Total: ${r.total_time_min}m</span>
            </div>
            <div class="ingredients-preview">
                ${r.ingredients.slice(0, 5).map(i => `<span class="ingredient-tag">${esc(i.name)}</span>`).join('')}
                ${r.ingredients.length > 5 ? `<span class="more">+${r.ingredients.length - 5} more</span>` : ''}
            </div>
        </article>
    `;
}

function setupCardKeyboardHandlers() {
    const grid = document.getElementById('recipe-grid');
    grid.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            const card = e.target.closest('.recipe-card');
            if (card) {
                e.preventDefault();
                openDrawer(card.dataset.recipeId);
            }
        }
    });
    grid.addEventListener('click', (e) => {
        const card = e.target.closest('.recipe-card');
        if (card) {
            openDrawer(card.dataset.recipeId);
        }
    });
}

function esc(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

function initDrawer() {
    const drawer = document.getElementById('recipe-drawer');
    const overlay = document.getElementById('drawer-overlay');
    const closeBtn = document.getElementById('drawer-close');

    closeBtn.addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !drawer.hidden) {
            closeDrawer();
        }
    });

    drawer.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
            const focusable = drawer.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });
}

function openDrawer(recipeId) {
    const drawer = document.getElementById('recipe-drawer');
    const overlay = document.getElementById('drawer-overlay');
    const body = document.getElementById('drawer-body');
    const title = document.getElementById('drawer-title');

    body.innerHTML = '<div class="loading">Loading recipe...</div>';
    drawer.removeAttribute('hidden');
    drawer.classList.add('drawer-open');
    overlay.classList.add('drawer-overlay-open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';

    setTimeout(() => document.getElementById('drawer-close').focus(), 50);

    fetch(`${API}/recipe/${recipeId}`)
        .then(r => r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`)))
        .then(recipe => {
            title.textContent = recipe.name;
            const badge = recipe.id <= 30 ? 'original' : recipe.id <= 50 ? 'croatian' : 'expanded';
            const badgeLabel = recipe.id <= 30 ? 'Indian' : recipe.id <= 50 ? 'Croatian' : 'Expanded';

            const ingredientsHtml = recipe.ingredients.map((ing, i) => `
                <li class="ingredient-item">
                    <input type="checkbox" id="ing-${i}" class="ingredient-check">
                    <label for="ing-${i}">
                        <svg aria-hidden="true" width="16" height="16"><use href="/static/svg/icons.svg#icon-check"/></svg>
                        ${esc(ing.name)}${ing.amount ? ` - ${esc(ing.amount)}` : ''}
                    </label>
                </li>
            `).join('');

            const instructionsHtml = recipe.instructions.map((step, i) => `
                <li class="instruction-step">
                    <span class="step-number">${i + 1}</span>
                    <span class="step-text">${esc(step)}</span>
                </li>
            `).join('');

            body.innerHTML = `
                <div class="drawer-meta">
                    <span class="source-badge ${badge}">${badgeLabel}</span>
                    <span class="tag">${esc(recipe.cuisine)}</span>
                    <span class="tag difficulty-${recipe.difficulty}">${recipe.difficulty}</span>
                </div>
                <div class="drawer-times">
                    <span><svg aria-label="Prep time" width="16" height="16"><use href="/static/svg/icons.svg#icon-clock"/></svg> Prep: ${recipe.prep_time_min}m</span>
                    <span><svg aria-label="Cook time" width="16" height="16"><use href="/static/svg/icons.svg#icon-clock"/></svg> Cook: ${recipe.cook_time_min}m</span>
                    <span><svg aria-label="Servings" width="16" height="16"><use href="/static/svg/icons.svg#icon-users"/></svg> Servings: ${recipe.servings}</span>
                </div>
                <section class="drawer-section">
                    <h3 class="drawer-section-title">Sastojci</h3>
                    <ul class="ingredient-list">${ingredientsHtml}</ul>
                </section>
                <section class="drawer-section">
                    <h3 class="drawer-section-title">Priprema</h3>
                    <ol class="instruction-list">${instructionsHtml}</ol>
                </section>
            `;
        })
        .catch(() => {
            body.innerHTML = '<div class="loading">Failed to load recipe.</div>';
        });
}

function closeDrawer() {
    const drawer = document.getElementById('recipe-drawer');
    const overlay = document.getElementById('drawer-overlay');

    drawer.setAttribute('hidden', '');
    drawer.classList.remove('drawer-open');
    overlay.classList.remove('drawer-overlay-open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
}

function highlightMatch(text, query) {
    if (!query) return esc(text);
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return esc(text).replace(regex, '<mark>$1</mark>');
}

function clearSuggestions() {
    const suggestions = document.getElementById('search-suggestions');
    const searchInput = document.getElementById('typeahead-search');
    const clearBtn = document.getElementById('search-clear');

    suggestions.innerHTML = '';
    suggestions.setAttribute('hidden', '');
    suggestions.classList.remove('search-suggestions-open');
    searchInput.setAttribute('aria-expanded', 'false');
    clearBtn.setAttribute('hidden', '');
    clearBtn.classList.remove('search-clear-visible');
}

function initTypeahead() {
    const searchInput = document.getElementById('typeahead-search');
    const suggestions = document.getElementById('search-suggestions');
    const clearBtn = document.getElementById('search-clear');
    let selectedIndex = -1;

    function showSuggestions(results, query) {
        suggestions.innerHTML = '';
        selectedIndex = -1;

        if (results.length === 0) {
            suggestions.innerHTML = '<div class="search-suggestion-item" style="color: var(--text-muted); cursor: default;">No results found</div>';
            suggestions.removeAttribute('hidden');
            suggestions.classList.add('search-suggestions-open');
            searchInput.setAttribute('aria-expanded', 'true');
            return;
        }

        results.slice(0, 8).forEach((recipe, i) => {
            const div = document.createElement('div');
            div.className = 'search-suggestion-item';
            div.setAttribute('role', 'option');
            div.setAttribute('data-recipe-id', recipe.id);
            div.setAttribute('aria-selected', 'false');
            div.innerHTML = `
                <span style="flex: 1;">
                    <strong>${highlightMatch(recipe.name, query)}</strong>
                </span>
                <span style="font-size: 12px; color: var(--text-muted);">${esc(recipe.cuisine || '')}</span>
            `;
            suggestions.appendChild(div);
        });

        suggestions.removeAttribute('hidden');
        suggestions.classList.add('search-suggestions-open');
        searchInput.setAttribute('aria-expanded', 'true');
    }

    const fetchSuggestions = debounce(async (query) => {
        if (!query.trim()) {
            clearSuggestions();
            return;
        }

        try {
            const res = await fetch(`${API}/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            showSuggestions(data.results || [], query);
        } catch (e) {
            console.error('Search failed', e);
        }
    }, 300);

    searchInput.addEventListener('input', (e) => {
        const value = e.target.value;
        if (value) {
            clearBtn.removeAttribute('hidden');
            clearBtn.classList.add('search-clear-visible');
        } else {
            clearBtn.setAttribute('hidden', '');
            clearBtn.classList.remove('search-clear-visible');
        }
        fetchSuggestions(value);
    });

    searchInput.addEventListener('keydown', (e) => {
        const items = suggestions.querySelectorAll('.search-suggestion-item[data-recipe-id]');
        const total = items.length;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (items.length > 0) {
                if (selectedIndex < total - 1) {
                    selectedIndex++;
                } else {
                    selectedIndex = 0;
                }
                items.forEach((item, i) => {
                    item.setAttribute('aria-selected', i === selectedIndex ? 'true' : 'false');
                });
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (items.length > 0) {
                if (selectedIndex > 0) {
                    selectedIndex--;
                } else {
                    selectedIndex = total - 1;
                }
                items.forEach((item, i) => {
                    item.setAttribute('aria-selected', i === selectedIndex ? 'true' : 'false');
                });
            }
        } else if (e.key === 'Enter') {
            if (selectedIndex >= 0 && items[selectedIndex]) {
                e.preventDefault();
                const recipeId = items[selectedIndex].dataset.recipeId;
                openDrawer(recipeId);
                searchInput.value = '';
                clearSuggestions();
            }
        } else if (e.key === 'Escape') {
            clearSuggestions();
            searchInput.blur();
        }
    });

    suggestions.addEventListener('click', (e) => {
        const item = e.target.closest('.search-suggestion-item[data-recipe-id]');
        if (item) {
            const recipeId = item.dataset.recipeId;
            openDrawer(recipeId);
            searchInput.value = '';
            clearSuggestions();
        }
    });

    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearSuggestions();
        searchInput.focus();
    });

    document.addEventListener('click', (e) => {
        const wrapper = e.target.closest('.search-wrapper');
        if (!wrapper) {
            clearSuggestions();
        }
    });
}

function updateStats() {
    document.getElementById('total-count').textContent = filtered.length;
    const start = (page - 1) * PER_PAGE;
    const end = Math.min(page * PER_PAGE, filtered.length);
    document.getElementById('showing-count').textContent =
        filtered.length === 0 ? '0' : `${start + 1}-${end} of ${filtered.length}`;
}

function updatePagination() {
    const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
    document.getElementById('prev-page').disabled = page <= 1;
    document.getElementById('next-page').disabled = page >= totalPages;
    document.getElementById('page-info').textContent = `Page ${page} of ${totalPages}`;
}

function setupListeners() {
    initDrawer();
    initTypeahead();
    document.getElementById('search-input').addEventListener('input', applyFilters);
    document.getElementById('cuisine-filter').addEventListener('change', applyFilters);
    document.getElementById('meal-type-filter').addEventListener('change', applyFilters);
    document.getElementById('difficulty-filter').addEventListener('change', applyFilters);
    document.getElementById('source-filter').addEventListener('change', applyFilters);

    document.getElementById('clear-filters').addEventListener('click', () => {
        ['search-input', 'cuisine-filter', 'meal-type-filter', 'difficulty-filter', 'source-filter']
            .forEach(id => { const el = document.getElementById(id); if (el.tagName === 'SELECT') el.selectedIndex = 0; else el.value = ''; });
        applyFilters();
    });

    document.getElementById('prev-page').addEventListener('click', () => { if (page > 1) { page--; render(); updateStats(); } });
    document.getElementById('next-page').addEventListener('click', () => {
        const totalPages = Math.ceil(filtered.length / PER_PAGE);
        if (page < totalPages) { page++; updateStats(); }
    });

    setupCardKeyboardHandlers();
}

document.addEventListener('DOMContentLoaded', init);

document.addEventListener('DOMContentLoaded', initAnimations);