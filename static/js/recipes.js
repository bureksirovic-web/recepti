const API = '/api';
let allRecipes = [];
let filtered = [];
let page = 1;
const PER_PAGE = 12;

async function init() {
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
        applyFilters();
    } catch (e) {
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
        <article class="recipe-card">
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

function esc(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
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
        if (page < totalPages) { page++; render(); updateStats(); }
    });
}

document.addEventListener('DOMContentLoaded', init);