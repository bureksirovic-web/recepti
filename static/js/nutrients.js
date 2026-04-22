const NUTRIENT_META = {
  iron_mg:     { label: "Iron",        unit: "mg"  },
  calcium_mg:  { label: "Calcium",     unit: "mg"  },
  folate_mcg:   { label: "Folate",      unit: "mcg" },
  b12_mcg:     { label: "Vitamin B12", unit: "mcg" },
  protein_g:   { label: "Protein",     unit: "g"   },
  fiber_g:     { label: "Fiber",       unit: "g"   },
  calories:    { label: "Calories",    unit: "kcal"},
  carbs_g:     { label: "Carbs",       unit: "g"   },
  fat_g:       { label: "Fat",         unit: "g"   },
};

const BASE_API = "";

function getProgressClass(pct) {
  if (pct == null) return "progress-fill-low";
  if (pct >= 80)  return "progress-fill-good";
  if (pct >= 50)  return "progress-fill-mid";
  return "progress-fill-low";
}

function buildNutrientRow(nutrientKey, pct) {
  const meta = NUTRIENT_META[nutrientKey] || { label: nutrientKey, unit: "" };
  const fillClass = getProgressClass(pct);
  const displayPct = pct != null ? Math.min(100, Math.round(pct)) : 0;

  return `
    <div class="nutrient-row">
      <div class="nutrient-label">
        <span class="nutrient-name">${meta.label}</span>
        <span class="nutrient-pct">${displayPct}%</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill ${fillClass}" style="width:${displayPct}%"></div>
      </div>
    </div>`;
}

function renderMember(member) {
  const gaps = member.gaps || [];

  const nutrientOrder = Object.keys(NUTRIENT_META).filter(
    (n) => member.pct_of_rda[n] != null
  );

  const nutrientRows = nutrientOrder
    .map((n) => buildNutrientRow(n, member.pct_of_rda[n]))
    .join("");

  const gapRows = gaps
    .sort((a, b) => a.pct - b.pct)
    .map((g) => {
      const meta = NUTRIENT_META[g.nutrient] || { label: g.nutrient, unit: "" };
      return `
      <div class="gap-row">
        <div class="gap-label">
          <span>${meta.label}</span>
          <span class="gap-pct">${Math.round(g.pct)}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill progress-fill-low" style="width:${Math.min(100, Math.round(g.pct))}%"></div>
        </div>
        <span class="badge badge-danger">need ${g.gap_mg.toFixed(1)} ${meta.unit}</span>
      </div>`;
    })
    .join("");

  const groceryTags = (member.suggested_groceries || [])
    .map((g) => `<span class="grocery-tag">${g}</span>`)
    .join("");

  return `
    <div class="member-card card animate-on-scroll">
      <div class="page-title">${member.member_name}</div>

      <div class="member-nutrients">${nutrientRows}</div>

      ${gaps.length ? `
      <div class="member-gaps">
        <div class="section-label">Gaps</div>
        ${gapRows}
      </div>` : ""}

      ${groceryTags ? `
      <div class="member-groceries">
        <div class="section-label">Suggested Groceries</div>
        <div class="grocery-tags">${groceryTags}</div>
      </div>` : ""}
    </div>`;
}

function renderDashboard(data) {
  document.getElementById("loading").style.display = "none";
  document.getElementById("dashboard").style.display = "grid";

  const groceryEl = document.getElementById("groceryTags");
  groceryEl.innerHTML = data.suggested_groceries.length
    ? data.suggested_groceries.map((s) => `<span class="grocery-tag">${s}</span>`).join("")
    : '<span class="empty-hint">All gaps met — no suggestions</span>';

  const grid = document.getElementById("dashboard");
  data.members.forEach((member) => {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = renderMember(member);
    grid.appendChild(wrapper.firstElementChild);
  });

  setTimeout(() => {
    document.querySelectorAll(".animate-on-scroll").forEach((el) => {
      el.classList.add("animated");
    });
  }, 50);
}

async function loadData(days) {
  document.getElementById("loading").style.display = "block";
  document.getElementById("dashboard").style.display = "none";
  document.getElementById("notConfigured").style.display = "none";
  document.getElementById("statusMsg").textContent = "";
  document.getElementById("loading").textContent = "Loading nutrition data…";

  const dashboard = document.getElementById("dashboard");
  while (dashboard.children.length > 1) dashboard.removeChild(dashboard.lastChild);

  try {
    const res = await fetch(`${BASE_API}/api/nutrients?days=${days}`);
    if (res.status === 503) {
      document.getElementById("loading").style.display = "none";
      document.getElementById("notConfigured").style.display = "block";
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    document.getElementById("statusMsg").textContent = `Showing last ${days} days`;
    renderDashboard(data);
  } catch (err) {
    document.getElementById("loading").textContent = `Failed to load: ${err.message}`;
  }
}

document.getElementById("refreshBtn").addEventListener("click", () => {
  loadData(parseInt(document.getElementById("periodSelect").value));
});

loadData(7);