const API = '/api';

let charts = {
    cuisine: null,
    mealType: null,
    difficulty: null
};

function getThemeColors() {
    const style = getComputedStyle(document.documentElement);
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        primary: style.getPropertyValue('--primary').trim() || '#2d6a4f',
        primaryLight: isDark ? '#74c69d' : '#40916c',
        secondary: style.getPropertyValue('--secondary').trim() || '#d4a574',
        accent: style.getPropertyValue('--accent').trim() || '#e76f51',
        text: style.getPropertyValue('--text').trim() || '#1a1a1a',
        textMuted: style.getPropertyValue('--text-muted').trim() || '#6b7280',
        border: style.getPropertyValue('--border').trim() || '#e5e7eb',
        bg: style.getPropertyValue('--bg').trim() || '#faf9f7',
        success: style.getPropertyValue('--success').trim() || '#10b981',
        warning: style.getPropertyValue('--warning').trim() || '#f59e0b',
        danger: style.getPropertyValue('--danger').trim() || '#ef4444',
    };
}

function showSkeletons() {
    ['chart-cuisine', 'chart-meal-type', 'chart-difficulty'].forEach(id => {
        const el = document.getElementById(id);
        el.innerHTML = '<div class="skeleton skeleton-card"></div>';
    });
}

function esc(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function init() {
    showSkeletons();
    loadCoverage();
}

async function loadCoverage() {
    try {
        const res = await fetch(`${API}/coverage`);
        if (!res.ok) throw new Error('Failed to load coverage data');
        const data = await res.json();

        document.getElementById('total-recipes').textContent = data.total_recipes;
        document.getElementById('hole-count').textContent = data.holes.length;
        document.getElementById('sparse-count').textContent = data.holes.filter(h => h.status === 'SPARSE').length;
        document.getElementById('empty-count').textContent = data.holes.filter(h => h.status === 'EMPTY').length;

        renderCharts(data.by_dimension);
        renderHoles(data.holes, data.total_recipes);

        updateCopyAllButton(data.holes);
    } catch (e) {
        console.error('Coverage load failed:', e);
        document.getElementById('holes-list').innerHTML =
            '<div class="loading" style="padding:24px;">Failed to load coverage data. Is the server running?</div>';
    }
}

function renderCharts(byDimension) {
    const colors = getThemeColors();
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: colors.text,
                titleColor: '#fff',
                bodyColor: '#fff',
                padding: 10,
                cornerRadius: 6,
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: colors.border },
                ticks: { color: colors.textMuted, font: { size: 11 } }
            },
            x: {
                grid: { display: false },
                ticks: { color: colors.textMuted, font: { size: 11 } }
            }
        }
    };

    const barColor = colors.primary;

    
    const cuisineData = byDimension.cuisine;
    const cuisineLabels = Object.keys(cuisineData).sort();
    const cuisineCounts = cuisineLabels.map(k => cuisineData[k].count);

    if (charts.cuisine) charts.cuisine.destroy();
    charts.cuisine = new Chart(document.getElementById('chart-cuisine'), {
        type: 'bar',
        data: {
            labels: cuisineLabels,
            datasets: [{
                data: cuisineCounts,
                backgroundColor: barColor,
                borderRadius: 4,
            }]
        },
        options: chartOptions
    });

    
    const mealTypeData = byDimension.meal_type;
    const mealTypeLabels = Object.keys(mealTypeData).sort();
    const mealTypeCounts = mealTypeLabels.map(k => mealTypeData[k].count);

    if (charts.mealType) charts.mealType.destroy();
    charts.mealType = new Chart(document.getElementById('chart-meal-type'), {
        type: 'bar',
        data: {
            labels: mealTypeLabels,
            datasets: [{
                data: mealTypeCounts,
                backgroundColor: barColor,
                borderRadius: 4,
            }]
        },
        options: chartOptions
    });

    
    const difficultyData = byDimension.difficulty;
    const difficultyLabels = ['easy', 'medium', 'hard'].filter(d => difficultyData[d]);
    const difficultyCounts = difficultyLabels.map(k => difficultyData[k].count);

    if (charts.difficulty) charts.difficulty.destroy();
    charts.difficulty = new Chart(document.getElementById('chart-difficulty'), {
        type: 'bar',
        data: {
            labels: difficultyLabels,
            datasets: [{
                data: difficultyCounts,
                backgroundColor: difficultyLabels.map((_, i) => {
                    const base = [colors.success, colors.warning, colors.danger];
                    return base[i] || barColor;
                }),
                borderRadius: 4,
            }]
        },
        options: chartOptions
    });
}

function renderHoles(holes, total) {
    const container = document.getElementById('holes-list');

    if (holes.length === 0) {
        container.innerHTML = '<div class="loading" style="padding:24px;">No coverage holes detected. Great job!</div>';
        return;
    }

    container.innerHTML = holes.map((hole, index) => {
        const percent = total > 0 ? (hole.count / total) * 100 : 0;
        const barColor = hole.count === 0 ? 'var(--danger)' : 'var(--warning)';

        return `
            <div class="hole-row" data-index="${index}" tabindex="0" role="button" aria-label="Copy suggested queries for ${esc(hole.value)}">
                <div style="display:flex;flex-direction:column;gap:8px;flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                        <span class="badge badge-${hole.dimension.split('_')[0]}" style="text-transform:capitalize;">${esc(hole.dimension.replace('_', ' '))}</span>
                        <span class="hole-label">${esc(hole.value)}</span>
                        <span class="badge badge-${hole.status.toLowerCase()}">${esc(hole.status)}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span class="hole-count">${hole.count} recipe${hole.count !== 1 ? 's' : ''}</span>
                        <div class="hole-bar-wrapper">
                            <div class="hole-bar">
                                <div class="hole-bar-fill" style="width:${Math.min(percent * 10, 100)}%;background:${barColor};"></div>
                            </div>
                        </div>
                    </div>
                    <div style="display:flex;flex-wrap:wrap;gap:4px;" class="query-tags">
                        ${hole.suggested_queries.map(q => `
                            <span class="grocery-tag" style="cursor:pointer;" data-query="${esc(q)}" title="Click to copy: ${esc(q)}">${esc(q)}</span>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    
    container.querySelectorAll('.query-tags .grocery-tag').forEach(tag => {
        tag.addEventListener('click', (e) => {
            e.stopPropagation();
            const query = tag.dataset.query;
            copyToClipboard(query);
            showCopiedFeedback(tag);
        });
    });

    
    container.querySelectorAll('.hole-row').forEach(row => {
        row.addEventListener('click', () => {
            const index = parseInt(row.dataset.index);
            const hole = holes[index];
            const queriesText = hole.suggested_queries.join('\n');
            copyToClipboard(queriesText);
            showCopiedFeedback(row);
        });

        row.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                row.click();
            }
        });
    });
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (e) {
        
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            document.body.removeChild(textarea);
            return true;
        } catch (err) {
            document.body.removeChild(textarea);
            return false;
        }
    }
}

function showCopiedFeedback(element) {
    const original = element.getAttribute('title') || '';
    element.setAttribute('title', 'Copied!');
    element.style.opacity = '0.7';

    setTimeout(() => {
        element.setAttribute('title', original);
        element.style.opacity = '1';
    }, 800);
}

function updateCopyAllButton(holes) {
    const btn = document.getElementById('copy-all-btn');
    const topHoles = holes.slice(0, 5);

    if (topHoles.length === 0) {
        btn.disabled = true;
        return;
    }

    btn.disabled = false;
    btn.addEventListener('click', () => {
        const allQueries = topHoles
            .filter(h => h.priority > 0.1)
            .flatMap(h => h.suggested_queries)
            .join('\n');

        if (allQueries) {
            copyToClipboard(allQueries);
            btn.innerHTML = `
                <svg class="icon" aria-hidden="true" style="width:14px;height:14px;"><use href="/static/svg/icons.svg#icon-check"/></svg>
                Copied!
            `;
            setTimeout(() => {
                btn.innerHTML = `
                    <svg class="icon" aria-hidden="true" style="width:14px;height:14px;"><use href="/static/svg/icons.svg#icon-clipboard-list"/></svg>
                    Copy All
                `;
            }, 1500);
        }
    });
}



document.addEventListener('DOMContentLoaded', init);