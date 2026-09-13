from __future__ import annotations

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Raeburn Intelligence OS</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      background: #081017;
      color: #f5f7f8;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #081017; }
    main { max-width: 1280px; margin: 0 auto; padding: 32px 20px 72px; }
    header { display: flex; justify-content: space-between; gap: 24px; align-items: end; }
    h1 { margin: 0; font-size: clamp(30px, 5vw, 56px); letter-spacing: -0.04em; }
    .muted { color: #91a0ab; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(4, 1fr); margin-top: 28px; }
    .card { background: #101a22; border: 1px solid #22303a; border-radius: 18px; padding: 18px; }
    .metric { font-size: 34px; font-weight: 700; margin-top: 8px; }
    .panel { margin-top: 20px; }
    .row { display: flex; gap: 10px; flex-wrap: wrap; }
    input, button {
      border-radius: 12px; border: 1px solid #2a3944; padding: 12px 14px; font: inherit;
    }
    input { flex: 1; min-width: 220px; background: #0b141b; color: #fff; }
    button { background: #f5f7f8; color: #081017; font-weight: 700; cursor: pointer; }
    button.secondary { background: #16232d; color: #f5f7f8; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { text-align: left; padding: 12px 8px; border-bottom: 1px solid #22303a; }
    .score { font-size: 22px; font-weight: 800; }
    .pill { padding: 5px 9px; border-radius: 999px; background: #1c2b35; display: inline-block; }
    .ok { color: #9ef0bc; }
    .warn { color: #ffd38a; }
    .empty { padding: 24px 0; color: #91a0ab; }
    @media (max-width: 850px) {
      .grid { grid-template-columns: repeat(2, 1fr); }
      header { align-items: start; flex-direction: column; }
    }
    @media (max-width: 520px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <div class="muted">THE RAEBURN GROUP · PUBLIC INTELLIGENCE ENGINE</div>
      <h1>Raeburn Intelligence OS</h1>
      <p class="muted">Evidence-backed company intelligence, signals and commercial opportunities.</p>
    </div>
    <div id="integration" class="pill">Checking integrations…</div>
  </header>

  <section class="grid">
    <div class="card"><div class="muted">Companies indexed</div><div id="companies" class="metric">—</div></div>
    <div class="card"><div class="muted">Ranked opportunities</div><div id="opportunities" class="metric">—</div></div>
    <div class="card"><div class="muted">Sources registered</div><div id="sources" class="metric">—</div></div>
    <div class="card"><div class="muted">Environment</div><div id="environment" class="metric">—</div></div>
  </section>

  <section class="card panel">
    <h2>Company intelligence</h2>
    <p class="muted">Refresh a UK company by Companies House number.</p>
    <div class="row">
      <input id="companyNumber" placeholder="e.g. 17361231" aria-label="Company number">
      <button onclick="refreshCompany()">Refresh company</button>
    </div>
    <div id="refreshResult" class="muted"></div>
  </section>

  <section class="card panel">
    <div class="row" style="justify-content:space-between;align-items:center">
      <div>
        <h2>Opportunity radar</h2>
        <p class="muted">Highest-scoring evidence-backed opportunities across indexed companies.</p>
      </div>
      <button class="secondary" onclick="loadAll()">Refresh dashboard</button>
    </div>
    <div id="opportunityTable"></div>
  </section>

  <section class="card panel">
    <h2>Indexed companies</h2>
    <div id="companyTable"></div>
  </section>
</main>
<script>
async function json(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

async function loadStatus() {
  const data = await json('/v1/status');
  document.getElementById('companies').textContent = data.companies_indexed;
  document.getElementById('opportunities').textContent = data.opportunities_ranked;
  document.getElementById('sources').textContent = data.sources_registered;
  document.getElementById('environment').textContent = data.environment;
  const ch = data.integrations.companies_house;
  const label = ch.configured ? 'Companies House live' : 'Companies House key required';
  const integration = document.getElementById('integration');
  integration.textContent = label;
  integration.className = `pill ${ch.configured ? 'ok' : 'warn'}`;
}

async function loadOpportunities() {
  const rows = await json('/v1/opportunities?limit=100');
  const target = document.getElementById('opportunityTable');
  if (!rows.length) {
    target.innerHTML = '<div class="empty">No scored opportunities yet. Index a company first.</div>';
    return;
  }
  target.innerHTML = `<table><thead><tr><th>Score</th><th>Company</th><th>Type</th><th>Action</th></tr></thead><tbody>${rows.slice(0, 30).map(row => `<tr><td class="score">${row.opportunity.score}</td><td>${escapeHtml(row.company.name)}</td><td><span class="pill">${escapeHtml(row.opportunity.kind)}</span></td><td>${escapeHtml(row.opportunity.recommended_action)}</td></tr>`).join('')}</tbody></table>`;
}

async function loadCompanies() {
  const rows = await json('/v1/companies?limit=100');
  const target = document.getElementById('companyTable');
  if (!rows.length) {
    target.innerHTML = '<div class="empty">No companies indexed yet.</div>';
    return;
  }
  target.innerHTML = `<table><thead><tr><th>Company</th><th>Number</th><th>Status</th><th>SIC</th></tr></thead><tbody>${rows.map(row => `<tr><td>${escapeHtml(row.name)}</td><td>${escapeHtml(row.company_number)}</td><td>${escapeHtml(row.status || '—')}</td><td>${escapeHtml((row.sic_codes || []).join(', '))}</td></tr>`).join('')}</tbody></table>`;
}

async function refreshCompany() {
  const number = document.getElementById('companyNumber').value.trim();
  const target = document.getElementById('refreshResult');
  if (!number) return;
  target.textContent = 'Refreshing…';
  try {
    const data = await json(`/v1/companies/${encodeURIComponent(number)}/refresh`, {method: 'POST'});
    target.textContent = `Indexed ${data.name} (${data.company_number}).`;
    await loadAll();
  } catch (error) {
    target.textContent = error.message;
  }
}

async function loadAll() {
  await Promise.all([loadStatus(), loadOpportunities(), loadCompanies()]);
}
loadAll().catch(error => console.error(error));
</script>
</body>
</html>
"""
