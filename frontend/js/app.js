'use strict';

// ─── Utilities ────────────────────────────────────────────────────────────────

function timeAgo(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function severityCls(s) {
  return { High: 'bg-red-500/15 text-red-400 border-red-500/30', Medium: 'bg-orange-500/15 text-orange-400 border-orange-500/30', Low: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30', Informational: 'bg-blue-500/15 text-blue-400 border-blue-500/30' }[s] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30';
}

function statusCls(s) {
  return { New: 'bg-blue-500/15 text-blue-400 border-blue-500/30', Active: 'bg-green-500/15 text-green-400 border-green-500/30', Closed: 'bg-slate-500/15 text-slate-400 border-slate-500/30' }[s] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30';
}

function badge(text, cls) {
  return `<span class="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${cls}">${esc(text)}</span>`;
}

// ─── API ──────────────────────────────────────────────────────────────────────

const api = {
  async getIncidents({ status = '', severity = '', limit = 50 } = {}) {
    const p = new URLSearchParams({ limit });
    if (status) p.set('status', status);
    if (severity) p.set('severity', severity);
    const r = await fetch(`/api/incidents?${p}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async enrichAlert(entities) {
    const r = await fetch('/api/enrich-alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entities }),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async respondToIncident(incidentId, actions) {
    const r = await fetch('/api/respond-incident', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incidentId, actions }),
    });
    if (!r.ok && r.status !== 207) throw new Error(await r.text());
    return r.json();
  },

  async healthCheck() {
    try {
      const r = await fetch('/api/incidents?limit=1', { signal: AbortSignal.timeout(4000) });
      return r.ok;
    } catch { return false; }
  },
};

// ─── State ────────────────────────────────────────────────────────────────────

const S = {
  tab: 'incidents',
  apiOnline: null,
  // incidents
  incidents: [],
  incidentsLoading: false,
  incidentsError: null,
  selectedIncident: null,
  filters: { status: '', severity: '', limit: 50 },
  // enrich
  enrichEntities: [{ type: 'ip', value: '' }],
  enrichResults: null,
  enrichLoading: false,
  enrichError: null,
  // respond
  respondId: '',
  respondActions: [{ type: 'disable_user', target: '' }],
  respondResults: null,
  respondLoading: false,
  respondError: null,
};

// ─── Render ───────────────────────────────────────────────────────────────────

function render() {
  document.getElementById('app').innerHTML = shell();
  wire();
}

function shell() {
  const tabs = [
    { id: 'incidents', icon: '⚠', label: 'Incidents' },
    { id: 'enrich',    icon: '🔍', label: 'Enrich' },
    { id: 'respond',   icon: '⚡', label: 'Respond' },
  ];

  const dot = S.apiOnline === null
    ? `<span class="w-2 h-2 rounded-full bg-slate-600"></span><span class="text-xs text-slate-500">Connecting…</span>`
    : S.apiOnline
      ? `<span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]"></span><span class="text-xs text-emerald-400">API Online</span>`
      : `<span class="w-2 h-2 rounded-full bg-red-400"></span><span class="text-xs text-red-400">API Offline</span>`;

  const tabBtns = tabs.map(t => `
    <button data-tab="${t.id}" class="tab-btn flex items-center gap-1.5 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${S.tab === t.id ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}">
      <span>${t.icon}</span>${t.label}
    </button>`).join('');

  const content = S.tab === 'incidents' ? renderIncidents()
    : S.tab === 'enrich' ? renderEnrich()
    : renderRespond();

  return `
    <div class="min-h-screen bg-slate-950 flex flex-col">
      <header class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-sm text-white shadow-lg">S</div>
          <span class="font-semibold text-slate-100 tracking-wide">PySOC</span>
          <span class="hidden sm:block text-slate-600 text-xs border-l border-slate-700 pl-3">Security Operations Center</span>
        </div>
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2">${dot}</div>
          <button id="btn-refresh" class="text-xs px-3 py-1.5 rounded border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors">↻ Refresh</button>
        </div>
      </header>

      <nav class="bg-slate-900 border-b border-slate-800 px-6 flex gap-1 overflow-x-auto">
        ${tabBtns}
      </nav>

      <main class="flex-1 p-6 fade-in">
        ${content}
      </main>
    </div>`;
}

// ─── Incidents Tab ────────────────────────────────────────────────────────────

function renderIncidents() {
  const { incidents, incidentsLoading, incidentsError, filters, selectedIncident } = S;

  const cnt = (fn) => incidents.filter(fn).length;
  const stats = [
    { label: 'Total',  val: incidents.length,              color: 'text-slate-200' },
    { label: 'New',    val: cnt(i => i.status === 'New'),   color: 'text-blue-400' },
    { label: 'Active', val: cnt(i => i.status === 'Active'),color: 'text-emerald-400' },
    { label: 'Closed', val: cnt(i => i.status === 'Closed'),color: 'text-slate-500' },
    { label: 'High',   val: cnt(i => i.severity === 'High'),color: 'text-red-400' },
  ].map(s => `
    <div class="bg-slate-900 rounded-lg border border-slate-800 px-4 py-3 text-center">
      <div class="text-2xl font-bold ${s.color}">${s.val}</div>
      <div class="text-xs text-slate-500 mt-0.5 uppercase tracking-wide">${s.label}</div>
    </div>`).join('');

  const selOpts = (vals, cur, fmt = v => v) =>
    vals.map(v => `<option value="${v}" ${cur === v ? 'selected' : ''}>${esc(fmt(v))}</option>`).join('');

  let tbody;
  if (incidentsLoading) {
    tbody = `<tr><td colspan="7" class="text-center py-16 text-slate-600">
      <div class="inline-block w-5 h-5 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin mb-2"></div>
      <div class="text-sm">Loading incidents…</div></td></tr>`;
  } else if (incidentsError) {
    tbody = `<tr><td colspan="7" class="text-center py-12 text-red-400 text-sm">${esc(incidentsError)}</td></tr>`;
  } else if (!incidents.length) {
    tbody = `<tr><td colspan="7" class="text-center py-16 text-slate-600 text-sm">No incidents found</td></tr>`;
  } else {
    tbody = incidents.map(i => {
      const sel = selectedIncident?.id === i.id;
      return `
        <tr data-iid="${esc(i.id)}" class="incident-row border-b border-slate-800/60 hover:bg-slate-800/40 cursor-pointer transition-colors ${sel ? 'bg-blue-500/8 border-l-2 border-l-blue-500' : ''}">
          <td class="px-4 py-3 text-slate-600 text-xs font-mono">#${String(i.incidentNumber ?? 0).padStart(4, '0')}</td>
          <td class="px-4 py-3 max-w-xs">
            <span class="font-medium text-slate-200 truncate block">${esc(i.title)}</span>
            ${i.labels?.length ? `<span class="text-xs text-slate-600">${i.labels.map(esc).join(', ')}</span>` : ''}
          </td>
          <td class="px-4 py-3">${badge(i.severity, severityCls(i.severity))}</td>
          <td class="px-4 py-3">${badge(i.status, statusCls(i.status))}</td>
          <td class="px-4 py-3 text-slate-500 text-xs truncate max-w-[120px]">${esc(i.assignedTo || '—')}</td>
          <td class="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">${timeAgo(i.createdAt)}</td>
          <td class="px-4 py-3">
            <div class="flex gap-1.5">
              <button data-enrich-id="${esc(i.id)}" class="btn-enrich-incident text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 transition-colors">Enrich</button>
              <button data-respond-id="${esc(i.id)}" class="btn-respond-incident text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 border border-orange-500/20 transition-colors">Respond</button>
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  const detail = selectedIncident ? `
    <div class="w-72 xl:w-80 flex-shrink-0 bg-slate-900 rounded-lg border border-slate-800 p-4 space-y-4 self-start sticky top-24 fade-in">
      <div class="flex items-start justify-between gap-2">
        <div>
          <div class="text-xs font-mono text-slate-600 mb-1">${esc(selectedIncident.id)}</div>
          <h3 class="text-sm font-semibold text-slate-100 leading-snug">${esc(selectedIncident.title)}</h3>
        </div>
        <button id="btn-close-detail" class="text-slate-700 hover:text-slate-300 text-xl leading-none flex-shrink-0">×</button>
      </div>
      <div class="flex flex-wrap gap-2">
        ${badge(selectedIncident.severity, severityCls(selectedIncident.severity))}
        ${badge(selectedIncident.status, statusCls(selectedIncident.status))}
      </div>
      <div class="text-xs space-y-1.5 text-slate-400">
        <div class="flex justify-between"><span class="text-slate-600">Incident #</span><span>${selectedIncident.incidentNumber ?? '—'}</span></div>
        <div class="flex justify-between"><span class="text-slate-600">Alerts</span><span>${selectedIncident.alertCount ?? 0}</span></div>
        <div class="flex justify-between"><span class="text-slate-600">Assigned</span><span class="truncate ml-2 text-right">${esc(selectedIncident.assignedTo || '—')}</span></div>
        <div class="flex justify-between"><span class="text-slate-600">Created</span><span>${timeAgo(selectedIncident.createdAt)}</span></div>
        <div class="flex justify-between"><span class="text-slate-600">Updated</span><span>${timeAgo(selectedIncident.updatedAt)}</span></div>
      </div>
      ${selectedIncident.labels?.length ? `<div class="flex flex-wrap gap-1">${selectedIncident.labels.map(l => `<span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-500 border border-slate-700">${esc(l)}</span>`).join('')}</div>` : ''}
      <div class="pt-3 border-t border-slate-800 space-y-2">
        <button data-goto-enrich="${esc(selectedIncident.id)}" class="w-full text-left text-sm px-3 py-2 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 transition-colors">🔍 Enrich Entities</button>
        <button data-goto-respond="${esc(selectedIncident.id)}" class="w-full text-left text-sm px-3 py-2 rounded bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 border border-orange-500/20 transition-colors">⚡ Take Response Action</button>
      </div>
    </div>` : '';

  return `
    <div class="space-y-4">
      <div class="grid grid-cols-5 gap-3">${stats}</div>
      <div class="flex gap-4 items-start">
        <div class="flex-1 min-w-0 bg-slate-900 rounded-lg border border-slate-800 overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-800 flex flex-wrap items-center gap-2">
            <select id="f-status" class="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded px-3 py-1.5 focus:outline-none focus:border-blue-500">
              ${selOpts(['', 'new', 'active', 'closed'], filters.status, v => v || 'All Statuses')}
            </select>
            <select id="f-severity" class="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded px-3 py-1.5 focus:outline-none focus:border-blue-500">
              ${selOpts(['', 'high', 'medium', 'low', 'informational'], filters.severity, v => v || 'All Severities')}
            </select>
            <select id="f-limit" class="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded px-3 py-1.5 focus:outline-none focus:border-blue-500">
              ${[10, 25, 50, 100].map(v => `<option value="${v}" ${filters.limit == v ? 'selected' : ''}>${v} per page</option>`).join('')}
            </select>
            <button id="btn-apply" class="ml-auto px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors">Apply</button>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-slate-800 text-slate-600 text-xs uppercase tracking-wider">
                  ${['No.','Title','Severity','Status','Assigned','Created','Actions'].map(h => `<th class="px-4 py-2.5 text-left font-medium">${h}</th>`).join('')}
                </tr>
              </thead>
              <tbody>${tbody}</tbody>
            </table>
          </div>
        </div>
        ${detail}
      </div>
    </div>`;
}

// ─── Enrich Tab ───────────────────────────────────────────────────────────────

function renderEnrich() {
  const { enrichEntities, enrichResults, enrichLoading, enrichError } = S;

  const entityRows = enrichEntities.map((e, i) => `
    <div class="flex gap-2 items-center">
      <select data-etype="${i}" class="entity-type bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded px-3 py-2 w-28 focus:outline-none focus:border-blue-500">
        <option value="ip" ${e.type === 'ip' ? 'selected' : ''}>IP</option>
        <option value="domain" ${e.type === 'domain' ? 'selected' : ''}>Domain</option>
      </select>
      <input data-eval="${i}" type="text" value="${esc(e.value)}"
        placeholder="${e.type === 'ip' ? '1.2.3.4' : 'example.com'}"
        class="entity-val flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-blue-500" />
      ${enrichEntities.length > 1
        ? `<button data-eremove="${i}" class="text-slate-700 hover:text-red-400 text-xl leading-none transition-colors">×</button>`
        : '<div class="w-5"></div>'}
    </div>`).join('');

  let resultsHtml = '';
  if (enrichLoading) {
    resultsHtml = `<div class="text-center py-10 text-slate-600">
      <div class="inline-block w-5 h-5 border-2 border-slate-700 border-t-blue-500 rounded-full animate-spin mb-2"></div>
      <div class="text-sm">Querying threat intel APIs…</div></div>`;
  } else if (enrichError) {
    resultsHtml = `<div class="text-red-400 text-sm p-4 rounded-lg bg-red-500/10 border border-red-500/20">${esc(enrichError)}</div>`;
  } else if (enrichResults) {
    const rows = enrichResults.map(r => {
      const vtColor = r.vt_malicious > 0 ? 'text-red-400 font-semibold' : r.vt_suspicious > 0 ? 'text-orange-400' : 'text-emerald-400';
      const abColor = r.abuseipdb_score > 75 ? 'text-red-400 font-semibold' : r.abuseipdb_score > 25 ? 'text-orange-400' : 'text-emerald-400';
      const vtTxt = r.vt_total_engines > 0 ? `${r.vt_malicious}/${r.vt_total_engines}` : '—';
      const abTxt = r.entity_type === 'ip' && r.abuseipdb_score !== undefined ? `${r.abuseipdb_score}%` : '—';
      return `
        <tr class="border-b border-slate-800/60 hover:bg-slate-800/30">
          <td class="px-4 py-3 font-mono text-xs text-slate-300">${esc(r.entity)}</td>
          <td class="px-4 py-3">${badge(r.entity_type.toUpperCase(), 'bg-slate-700/60 text-slate-400 border-slate-600')}</td>
          <td class="px-4 py-3 text-sm ${vtColor}">${vtTxt}</td>
          <td class="px-4 py-3 text-sm ${abColor}">${abTxt}</td>
          <td class="px-4 py-3 text-xs text-slate-500">${esc(r.abuseipdb_country || '—')}</td>
          <td class="px-4 py-3 text-xs">${r.enriched ? '<span class="text-emerald-500">✓ Enriched</span>' : '<span class="text-slate-600">Partial</span>'}</td>
        </tr>`;
    }).join('');
    resultsHtml = `
      <div class="bg-slate-900 rounded-lg border border-slate-800 overflow-hidden fade-in">
        <div class="px-4 py-2.5 border-b border-slate-800 text-xs text-slate-600 uppercase tracking-wider">
          Results — ${enrichResults.length} entit${enrichResults.length === 1 ? 'y' : 'ies'}
        </div>
        <table class="w-full text-sm">
          <thead><tr class="border-b border-slate-800 text-xs text-slate-600 uppercase tracking-wider">
            ${['Entity','Type','VT Detections','AbuseIPDB','Country','Status'].map(h => `<th class="px-4 py-2.5 text-left font-medium">${h}</th>`).join('')}
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  return `
    <div class="max-w-3xl space-y-6">
      <div>
        <h2 class="text-lg font-semibold text-slate-100">Entity Enrichment</h2>
        <p class="text-sm text-slate-500 mt-1">Query VirusTotal and AbuseIPDB for IP addresses and domains.</p>
      </div>
      <div class="bg-slate-900 rounded-lg border border-slate-800 p-5 space-y-3">
        <div class="text-xs font-medium text-slate-600 uppercase tracking-wider">Entities</div>
        <div id="entity-list" class="space-y-2">${entityRows}</div>
        <button id="btn-add-entity" class="text-xs text-blue-400 hover:text-blue-300 transition-colors">+ Add entity</button>
      </div>
      <button id="btn-run-enrich" ${enrichLoading ? 'disabled' : ''}
        class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-lg font-medium transition-colors">
        ${enrichLoading ? 'Enriching…' : 'Enrich Entities'}
      </button>
      ${resultsHtml}
    </div>`;
}

// ─── Respond Tab ──────────────────────────────────────────────────────────────

function renderRespond() {
  const { respondId, respondActions, respondResults, respondLoading, respondError } = S;

  const ACTION_LABELS = { disable_user: 'Disable User', revoke_sessions: 'Revoke Sessions', isolate_machine: 'Isolate Machine' };
  const ACTION_PH = { disable_user: 'user@corp.com', revoke_sessions: 'user@corp.com', isolate_machine: 'machine-id-abc123' };

  const actionRows = respondActions.map((a, i) => `
    <div class="flex gap-2 items-center">
      <select data-atype="${i}" class="action-type bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500">
        ${Object.entries(ACTION_LABELS).map(([v, l]) => `<option value="${v}" ${a.type === v ? 'selected' : ''}>${l}</option>`).join('')}
      </select>
      <input data-atarget="${i}" type="text" value="${esc(a.target)}"
        placeholder="${ACTION_PH[a.type] ?? 'target'}"
        class="action-target flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 placeholder-slate-600 focus:outline-none focus:border-blue-500" />
      ${respondActions.length > 1
        ? `<button data-aremove="${i}" class="text-slate-700 hover:text-red-400 text-xl leading-none transition-colors">×</button>`
        : '<div class="w-5"></div>'}
    </div>`).join('');

  let resultsHtml = '';
  if (respondLoading) {
    resultsHtml = `<div class="text-center py-10 text-slate-600">
      <div class="inline-block w-5 h-5 border-2 border-slate-700 border-t-orange-500 rounded-full animate-spin mb-2"></div>
      <div class="text-sm">Executing response actions…</div></div>`;
  } else if (respondError) {
    resultsHtml = `<div class="text-red-400 text-sm p-4 rounded-lg bg-red-500/10 border border-red-500/20">${esc(respondError)}</div>`;
  } else if (respondResults) {
    const allOk = respondResults.errors?.length === 0;
    const rows = [
      ...(respondResults.results ?? []).map(r => `
        <div class="flex items-center gap-3 py-2.5 border-b border-slate-800 last:border-0">
          <span class="text-emerald-400 text-base">✓</span>
          <span class="text-sm text-slate-300 font-medium">${esc(ACTION_LABELS[r.action] ?? r.action)}</span>
          <span class="text-xs text-slate-600">→ ${esc(r.target)}</span>
          <span class="ml-auto text-xs text-emerald-400">success</span>
        </div>`),
      ...(respondResults.errors ?? []).map(e => `
        <div class="flex items-center gap-3 py-2.5 border-b border-slate-800 last:border-0">
          <span class="text-red-400 text-base">✗</span>
          <span class="text-sm text-slate-300 font-medium">${esc(ACTION_LABELS[e.action] ?? e.action)}</span>
          <span class="text-xs text-slate-600">→ ${esc(e.target ?? '')}</span>
          <span class="ml-auto text-xs text-red-400 truncate ml-2">${esc(e.error)}</span>
        </div>`),
    ].join('');
    resultsHtml = `
      <div class="bg-slate-900 rounded-lg border ${allOk ? 'border-emerald-500/30' : 'border-orange-500/30'} overflow-hidden fade-in">
        <div class="px-4 py-2.5 border-b ${allOk ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400' : 'border-orange-500/20 bg-orange-500/5 text-orange-400'} text-xs font-medium uppercase tracking-wider">
          ${allOk ? `✓ All ${respondResults.results.length} action${respondResults.results.length === 1 ? '' : 's'} succeeded` : `⚠ ${respondResults.results?.length ?? 0} succeeded · ${respondResults.errors.length} failed`}
        </div>
        <div class="px-4">${rows}</div>
      </div>`;
  }

  return `
    <div class="max-w-3xl space-y-6">
      <div>
        <h2 class="text-lg font-semibold text-slate-100">Incident Response</h2>
        <p class="text-sm text-slate-500 mt-1">Disable users, revoke sessions, and isolate machines for a Sentinel incident.</p>
      </div>
      <div class="bg-slate-900 rounded-lg border border-slate-800 p-5 space-y-5">
        <div>
          <label class="text-xs font-medium text-slate-600 uppercase tracking-wider block mb-2">Incident ID</label>
          <input id="inp-incident-id" type="text" value="${esc(respondId)}" placeholder="inc-0001"
            class="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2.5 placeholder-slate-600 focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <div class="text-xs font-medium text-slate-600 uppercase tracking-wider mb-2">Actions</div>
          <div id="action-list" class="space-y-2">${actionRows}</div>
          <button id="btn-add-action" class="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors">+ Add action</button>
        </div>
      </div>
      <button id="btn-run-respond" ${respondLoading ? 'disabled' : ''}
        class="px-6 py-2.5 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-lg font-medium transition-colors">
        ${respondLoading ? 'Executing…' : 'Execute Response'}
      </button>
      ${resultsHtml}
    </div>`;
}

// ─── Event Wiring ─────────────────────────────────────────────────────────────

function wire() {
  // Tabs + refresh
  document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.tab; render(); }));
  document.getElementById('btn-refresh')?.addEventListener('click', loadIncidents);

  // Incidents table rows
  document.querySelectorAll('.incident-row').forEach(row => {
    row.addEventListener('click', e => {
      if (e.target.closest('button')) return;
      const found = S.incidents.find(i => i.id === row.dataset.iid);
      S.selectedIncident = S.selectedIncident?.id === row.dataset.iid ? null : found;
      render();
    });
  });

  // Incident action buttons (Enrich / Respond in table row)
  document.querySelectorAll('.btn-enrich-incident').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); S.tab = 'enrich'; render(); }));
  document.querySelectorAll('.btn-respond-incident').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); S.respondId = b.dataset.respondId; S.tab = 'respond'; render(); }));

  // Detail panel shortcuts
  document.getElementById('btn-close-detail')?.addEventListener('click', () => { S.selectedIncident = null; render(); });
  document.querySelectorAll('[data-goto-enrich]').forEach(b => b.addEventListener('click', () => { S.tab = 'enrich'; render(); }));
  document.querySelectorAll('[data-goto-respond]').forEach(b => b.addEventListener('click', () => { S.respondId = b.dataset.gotoRespond; S.tab = 'respond'; render(); }));

  // Filters
  document.getElementById('btn-apply')?.addEventListener('click', () => {
    S.filters.status   = document.getElementById('f-status')?.value ?? '';
    S.filters.severity = document.getElementById('f-severity')?.value ?? '';
    S.filters.limit    = parseInt(document.getElementById('f-limit')?.value ?? '50');
    loadIncidents();
  });

  // Enrich entity form
  document.querySelectorAll('[data-etype]').forEach(s => s.addEventListener('change', () => { S.enrichEntities[+s.dataset.etype].type = s.value; render(); }));
  document.querySelectorAll('[data-eval]').forEach(i => i.addEventListener('input', () => { S.enrichEntities[+i.dataset.eval].value = i.value; }));
  document.querySelectorAll('[data-eremove]').forEach(b => b.addEventListener('click', () => { S.enrichEntities.splice(+b.dataset.eremove, 1); render(); }));
  document.getElementById('btn-add-entity')?.addEventListener('click', () => { S.enrichEntities.push({ type: 'ip', value: '' }); render(); });
  document.getElementById('btn-run-enrich')?.addEventListener('click', runEnrich);

  // Respond action form
  document.getElementById('inp-incident-id')?.addEventListener('input', e => { S.respondId = e.target.value; });
  document.querySelectorAll('[data-atype]').forEach(s => s.addEventListener('change', () => { S.respondActions[+s.dataset.atype].type = s.value; render(); }));
  document.querySelectorAll('[data-atarget]').forEach(i => i.addEventListener('input', () => { S.respondActions[+i.dataset.atarget].target = i.value; }));
  document.querySelectorAll('[data-aremove]').forEach(b => b.addEventListener('click', () => { S.respondActions.splice(+b.dataset.aremove, 1); render(); }));
  document.getElementById('btn-add-action')?.addEventListener('click', () => { S.respondActions.push({ type: 'disable_user', target: '' }); render(); });
  document.getElementById('btn-run-respond')?.addEventListener('click', runRespond);
}

// ─── Async Actions ────────────────────────────────────────────────────────────

async function loadIncidents() {
  S.incidentsLoading = true; S.incidentsError = null;
  render();
  try {
    const data = await api.getIncidents(S.filters);
    S.incidents = data.incidents ?? [];
  } catch (e) { S.incidentsError = e.message; }
  finally { S.incidentsLoading = false; render(); }
}

async function runEnrich() {
  // Flush live input values before reading
  document.querySelectorAll('[data-eval]').forEach(i => { S.enrichEntities[+i.dataset.eval].value = i.value; });
  document.querySelectorAll('[data-etype]').forEach(s => { S.enrichEntities[+s.dataset.etype].type = s.value; });
  const entities = S.enrichEntities.filter(e => e.value.trim());
  if (!entities.length) return;
  S.enrichLoading = true; S.enrichResults = null; S.enrichError = null;
  render();
  try {
    const data = await api.enrichAlert(entities);
    S.enrichResults = data.enrichments ?? [];
  } catch (e) { S.enrichError = e.message; }
  finally { S.enrichLoading = false; render(); }
}

async function runRespond() {
  // Flush live input values
  const idEl = document.getElementById('inp-incident-id');
  if (idEl) S.respondId = idEl.value;
  document.querySelectorAll('[data-atype]').forEach(s => { S.respondActions[+s.dataset.atype].type = s.value; });
  document.querySelectorAll('[data-atarget]').forEach(i => { S.respondActions[+i.dataset.atarget].target = i.value; });
  const actions = S.respondActions.filter(a => a.target.trim());
  if (!S.respondId.trim() || !actions.length) return;
  S.respondLoading = true; S.respondResults = null; S.respondError = null;
  render();
  try {
    S.respondResults = await api.respondToIncident(S.respondId, actions);
  } catch (e) { S.respondError = e.message; }
  finally { S.respondLoading = false; render(); }
}

// ─── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  render();
  api.healthCheck().then(ok => { S.apiOnline = ok; render(); });
  await loadIncidents();
  setInterval(() => { if (S.tab === 'incidents' && !S.incidentsLoading) loadIncidents(); }, 30000);
}

document.addEventListener('DOMContentLoaded', init);
