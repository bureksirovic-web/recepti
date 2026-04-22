const NUTRIENT_META = {
  iron_mg:     { label: "Iron",      unit: "mg",  color: "#e07b5a" },
  calcium_mg:  { label: "Calcium",   unit: "mg",  color: "#7bb8e0" },
  folate_mcg: { label: "Folate",    unit: "mcg", color: "#c07bd4" },
  b12_mcg:    { label: "Vitamin B12", unit: "mcg", color: "#7bd4a0" },
  protein_g:  { label: "Protein",   unit: "g",   color: "#d4c07b" },
  fiber_g:    { label: "Fiber",     unit: "g",   color: "#7bd4c0" },
  calories:   { label: "Calories",  unit: "kcal", color: "#d47b7b" },
  carbs_g:    { label: "Carbs",     unit: "g",   color: "#7b8ed4" },
  fat_g:      { label: "Fat",       unit: "g",   color: "#d4a07b" },
};

const BASE_API = "";

let activeCharts = [];

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function renderDashboard(data) {
  document.getElementById("loading").style.display = "none";
  document.getElementById("dashboard").style.display = "grid";
  activeCharts.forEach((c) => c.destroy());
  activeCharts = [];

  const groceryEl = document.getElementById("groceryTags");
  groceryEl.innerHTML = data.suggested_groceries.length
    ? data.suggested_groceries.map((s) => `<span class="grocery-tag">${s}</span>`).join("")
    : '<span style="color:rgba(255,255,255,0.4);font-size:0.82rem">All gaps met — no suggestions</span>';

  const grid = document.getElementById("dashboard");
  const existing = [document.getElementById("groceryTags").closest(".member-card")];
  data.members.forEach((member) => {
    const card = document.createElement("div");
    card.className = "member-card";
    card.innerHTML = `<h3>${member.member_name}</h3>`;
    grid.appendChild(card);
    renderMemberChart(card, member);
  });
}

function renderMemberChart(card, member) {
  const gaps = member.gaps || [];
  const gapByNut = {};
  gaps.forEach((g) => (gapByNut[g.nutrient] = g));

  const nutrientOrder = Object.keys(NUTRIENT_META).filter((n) => member.pct_of_rda[n] != null);
  const labels = nutrientOrder.map((n) => NUTRIENT_META[n].label);
  const percentages = nutrientOrder.map((n) => Math.min(100, member.pct_of_rda[n]));

  const canvas = document.createElement("canvas");
  canvas.style.maxHeight = "260px";
  card.appendChild(canvas);

  const chart = new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "% of RDA",
          data: percentages,
          backgroundColor: percentages.map((p) =>
            p >= 80 ? hexToRgba(NUTRIENT_META[nutrientOrder[percentages.indexOf(p)]].color, 0.85)
                   : hexToRgba("#d45a5a", 0.8)
          ),
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const n = nutrientOrder[ctx.dataIndex];
              const rda = member.rda[n];
              const intake = member.intake[n];
              const unit = NUTRIENT_META[n].unit;
              const gap = gapByNut[n];
              let tip = `${ctx.raw}% of RDA (${intake.toFixed(1)}/${rda?.toFixed(0)} ${unit})`;
              if (gap) tip += ` — need ${gap.gap_mg.toFixed(1)} ${unit} more`;
              return tip;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "rgba(255,255,255,0.5)", font: { size: 11 } },
          grid: { display: false },
        },
        y: {
          ticks: {
            color: "rgba(255,255,255,0.5)",
            callback: (v) => v + "%",
            stepSize: 25,
          },
          grid: { color: "rgba(255,255,255,0.06)" },
          max: 120,
        },
      },
    },
  });

  activeCharts.push(chart);

  if (gaps.length) {
    const alertDiv = document.createElement("div");
    alertDiv.style.marginTop = "12px";
    alertDiv.innerHTML = `<div style="font-size:0.78rem;color:#d45a5a;margin-bottom:6px">
      ⚠️ Top shortages:
      ${gaps
        .sort((a, b) => a.pct - b.pct)
        .slice(0, 3)
        .map((g) => {
          const meta = NUTRIENT_META[g.nutrient] || { label: g.nutrient, unit: "" };
          return `<b>${meta.label}</b>: ${g.pct.toFixed(0)}% (need ${g.gap_mg.toFixed(1)} ${meta.unit})`;
        })
        .join(" &nbsp;|&nbsp; ")}
    </div>`;
    card.appendChild(alertDiv);
  }
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