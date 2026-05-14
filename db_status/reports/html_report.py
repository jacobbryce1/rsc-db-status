"""Interactive HTML report with virtual scrolling for large datasets.

Rather than emitting one <tr> per database (which produces enormous files at
scale), all records are serialised as a compact JSON array embedded in a
<script> tag. A lightweight JS virtual scroller renders only the rows
currently visible in the viewport (~30–50 at any time), so the browser DOM
stays small regardless of dataset size.

File size is proportional to the data, not to DOM structure:
    64 K records ≈ 10–15 MB  (vs multi-GB with static rows)

SECURITY F-01: values passed through JSON serialisation (html.escape is
               applied to any value inserted directly into HTML attributes).
SECURITY F-10: Content-Security-Policy meta tag retained.
SECURITY AU-9: raw_event_status column included.
"""

import json
import html as html_mod
from datetime import datetime
from ..config import RSC_DOMAIN, STALE_SNAPSHOT_DAYS, MISSED_SNAPSHOT_LOOKBACK_HOURS, TIMESTAMP


def _e(value) -> str:
    """Escape a value for safe HTML attribute / text insertion."""
    return html_mod.escape(str(value) if value is not None else "", quote=True)


def write_html_report(databases: list, filename: str):
    """Generate virtual-scrolling interactive HTML report."""
    total   = len(databases)
    online  = sum(1 for d in databases if d.get("event_status") == "Online")
    warning = sum(1 for d in databases if "Warning" in d.get("event_status", ""))
    offline = sum(1 for d in databases if "Offline" in d.get("event_status", ""))
    relic   = sum(1 for d in databases if "Relic"   in d.get("event_status", ""))
    unknown = total - online - warning - offline - relic

    # Compact record format to minimise embedded JSON size.
    # Keys: n=name, pl=platform, cl=cluster, sl=sla, en=engine,
    #       re=is_relic, un=unprotected_reason, sn=newest_snapshot,
    #       ms=missed_snapshots, st=status, rs=raw_status
    records = []
    for db in databases:
        unp = db.get("unprotected_reason", "") or ""
        engine = db.get("db_engine", "") or db.get("recovery_model", "") or ""
        snap   = (db.get("newest_snapshot", "") or "")[:10]
        status = db.get("event_status", "") or ""
        raw    = db.get("raw_event_status", "") or ""
        records.append({
            "n":  db.get("name", "") or "",
            "pl": db.get("platform", "") or "",
            "cl": db.get("cluster_name", "") or "",
            "sl": db.get("sla_name", "") or "",
            "en": engine,
            "re": bool(db.get("is_relic")),
            "un": unp,
            "sn": snap,
            "ms": int(db.get("total_missed_snapshots", 0) or 0),
            "st": status,
            "rs": raw if raw and raw != status else "",
        })

    data_json = json.dumps(records, ensure_ascii=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
<title>RSC DB Status — {_e(TIMESTAMP)}</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  margin:20px;background:#f5f7fa;color:#1a1a2e}}
h1{{color:#1a237e;border-bottom:3px solid #00897b;padding-bottom:10px}}
.note{{background:#e3f2fd;padding:12px 16px;border-radius:6px;
  margin-bottom:20px;font-size:13px;border-left:4px solid #1565c0}}
.note-warn{{background:#fff8e1;border-left:4px solid #f9a825;
  padding:10px 14px;border-radius:6px;margin-bottom:16px;font-size:12px}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:16px;margin-bottom:24px}}
.c{{background:white;border-radius:8px;padding:20px;
  box-shadow:0 2px 8px rgba(0,0,0,.08);text-align:center}}
.c h3{{margin:0 0 8px;font-size:13px;color:#666}}
.m{{font-size:32px;font-weight:bold}}
.m-on{{color:#22c55e}}.m-off{{color:#ef4444}}
.m-warn{{color:#f97316}}.m-unk{{color:#6b7280}}.m-rel{{color:#9ca3af}}
.filters{{margin-bottom:12px;display:flex;gap:10px;flex-wrap:wrap;
  align-items:center;background:white;padding:14px;
  border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.05)}}
.filters input,.filters select{{padding:7px 11px;border:1px solid #ddd;
  border-radius:4px;font-size:13px}}
.filters input{{min-width:220px}}
#counter{{font-size:13px;color:#666;font-weight:500;margin-left:auto}}
/* Virtual scroll container */
#vs-wrap{{position:relative;background:white;border-radius:8px;
  box-shadow:0 2px 8px rgba(0,0,0,.08);overflow:hidden}}
#vs-scroll{{overflow-y:auto;height:600px}}
table{{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}}
thead th{{background:#1e293b;color:white;padding:10px 8px;text-align:left;
  font-size:11px;cursor:pointer;position:sticky;top:0;z-index:10;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
thead th:hover{{background:#334155}}
#spacer-top,#spacer-bot{{display:block}}
td{{padding:9px 8px;border-bottom:1px solid #f1f5f9;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
tr:hover td{{background:#f8fafc}}
.st-on{{color:#16a34a;font-weight:500}}
.st-off{{color:#dc2626;font-weight:500}}
.st-warn{{color:#ea580c;font-weight:500}}
.st-rel{{color:#9ca3af;font-style:italic}}
.st-raw{{color:#6b7280;font-size:11px;font-style:italic}}
/* Column widths */
th:nth-child(1),td:nth-child(1){{width:18%}}
th:nth-child(2),td:nth-child(2){{width:12%}}
th:nth-child(3),td:nth-child(3){{width:12%}}
th:nth-child(4),td:nth-child(4){{width:10%}}
th:nth-child(5),td:nth-child(5){{width:7%}}
th:nth-child(6),td:nth-child(6){{width:5%}}
th:nth-child(7),td:nth-child(7){{width:11%}}
th:nth-child(8),td:nth-child(8){{width:9%}}
th:nth-child(9),td:nth-child(9){{width:4%}}
th:nth-child(10),td:nth-child(10){{width:7%}}
th:nth-child(11),td:nth-child(11){{width:5%}}
</style>
</head>
<body>
<h1>Rubrik RSC — Database Status Report</h1>
<p style="color:#9e9e9e">Generated: {_e(generated)} | {_e(RSC_DOMAIN)}</p>

<div class="note">
<strong>Status Detection:</strong> Uses <code>unprotectableReasons</code>,
missed snapshot events, missed recoverable range events,
snapshot recency ({_e(STALE_SNAPSHOT_DAYS)}d threshold), SLA pause status,
and cloud native state. MSSQL event lookback: {_e(MISSED_SNAPSHOT_LOOKBACK_HOURS)}h.
Virtual scrolling active — all {total:,} records available; only visible rows are in the DOM.
</div>

<div class="note-warn">
<strong>Pre-inheritance status (Raw Status column):</strong> Where snapshot dates are
inherited from a parent or child object, the original status before inheritance is shown
in the Raw Status column. An empty Raw Status means the final status was not derived
from inheritance.
</div>

<div class="g">
<div class="c"><h3>TOTAL</h3><div class="m" style="color:#1a237e">{total:,}</div></div>
<div class="c"><h3>ONLINE</h3><div class="m m-on">{online:,}</div></div>
<div class="c"><h3>OFFLINE</h3><div class="m m-off">{offline:,}</div></div>
<div class="c"><h3>WARNING</h3><div class="m m-warn">{warning:,}</div></div>
<div class="c"><h3>RELIC</h3><div class="m m-rel">{relic:,}</div></div>
<div class="c"><h3>OTHER</h3><div class="m m-unk">{unknown:,}</div></div>
</div>

<div class="filters">
  <input  type="text" id="fi"   placeholder="Search by name…" oninput="applyFilters()">
  <select id="sf"  onchange="applyFilters()">
    <option value="">All Statuses</option>
    <option value="Online">Online</option>
    <option value="Warning">Warning</option>
    <option value="Offline">Offline</option>
    <option value="Relic">Relic</option>
  </select>
  <select id="pf"  onchange="applyFilters()"><option value="">All Platforms</option></select>
  <select id="clf" onchange="applyFilters()"><option value="">All Clusters</option></select>
  <select id="slaf" onchange="applyFilters()"><option value="">All SLAs</option></select>
  <span id="counter">Loading…</span>
</div>

<div id="vs-wrap">
  <div id="vs-scroll">
    <table>
      <thead><tr>
        <th onclick="sortBy(0)">Name</th>
        <th onclick="sortBy(1)">Platform</th>
        <th onclick="sortBy(2)">Cluster/Region</th>
        <th onclick="sortBy(3)">SLA</th>
        <th onclick="sortBy(4)">Engine</th>
        <th onclick="sortBy(5)">Relic</th>
        <th onclick="sortBy(6)">Unprotected Reason</th>
        <th onclick="sortBy(7)">Newest Snapshot</th>
        <th onclick="sortBy(8)">Missed</th>
        <th onclick="sortBy(9)">Status</th>
        <th onclick="sortBy(10)">Raw Status</th>
      </tr></thead>
      <tbody>
        <tr><td id="spacer-top" colspan="11" style="padding:0;height:0"></td></tr>
        <tr><td id="spacer-bot" colspan="11" style="padding:0;height:0"></td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
// ── Data ─────────────────────────────────────────────────────────────────────
const ALL = {data_json};

// ── State ────────────────────────────────────────────────────────────────────
let filtered = ALL.slice();
let sortCol = -1, sortAsc = true;
const ROW_H = 38;    // px — must match CSS td padding
const BUFFER = 5;    // extra rows above/below viewport

// ── Populate filter dropdowns ─────────────────────────────────────────────────
(function buildDropdowns() {{
  const platforms = [...new Set(ALL.map(r=>r.pl))].sort();
  const clusters  = [...new Set(ALL.map(r=>r.cl))].sort();
  const slas      = [...new Set(ALL.map(r=>r.sl))].sort();
  function fill(id, arr) {{
    const sel = document.getElementById(id);
    arr.forEach(v=>{{ const o=document.createElement('option'); o.value=o.text=v; sel.appendChild(o); }});
  }}
  fill('pf', platforms);
  fill('clf', clusters.slice(0,200));
  fill('slaf', slas.slice(0,200));
}})();

// ── Filtering ────────────────────────────────────────────────────────────────
function applyFilters() {{
  const fi   = document.getElementById('fi').value.toLowerCase();
  const sf   = document.getElementById('sf').value;
  const pf   = document.getElementById('pf').value;
  const clf  = document.getElementById('clf').value;
  const slaf = document.getElementById('slaf').value;
  filtered = ALL.filter(r=>{{
    if (fi   && !r.n.toLowerCase().includes(fi)) return false;
    if (sf   && !r.st.includes(sf))  return false;
    if (pf   && r.pl !== pf)         return false;
    if (clf  && r.cl !== clf)        return false;
    if (slaf && r.sl !== slaf)       return false;
    return true;
  }});
  document.getElementById('counter').textContent =
    'Showing ' + filtered.length.toLocaleString() + ' of ' + ALL.length.toLocaleString();
  document.getElementById('vs-scroll').scrollTop = 0;
  render();
}}

// ── Sorting ──────────────────────────────────────────────────────────────────
const KEYS = ['n','pl','cl','sl','en','re','un','sn','ms','st','rs'];
function sortBy(col) {{
  if (sortCol === col) {{ sortAsc = !sortAsc; }} else {{ sortCol = col; sortAsc = true; }}
  const key = KEYS[col];
  filtered.sort((a,b)=>{{
    const x = a[key], y = b[key];
    if (typeof x === 'number') return sortAsc ? x-y : y-x;
    return sortAsc ? String(x).localeCompare(String(y)) : String(y).localeCompare(String(x));
  }});
  render();
}}

// ── Virtual scroller ──────────────────────────────────────────────────────────
function statusClass(st) {{
  if (st.includes('Online'))  return 'st-on';
  if (st.includes('Offline')) return 'st-off';
  if (st.includes('Warning')) return 'st-warn';
  if (st.includes('Relic'))   return 'st-rel';
  return '';
}}

function makeRow(r) {{
  const tr = document.createElement('tr');
  const cells = [
    r.n, r.pl, r.cl, r.sl, r.en,
    r.re ? 'Yes' : 'No',
    r.un.length>30 ? r.un.slice(0,30)+'…' : r.un,
    r.sn, r.ms, r.st, r.rs
  ];
  cells.forEach((v,i)=>{{
    const td = document.createElement('td');
    td.textContent = v;
    if (i===9)  td.className = statusClass(r.st);
    if (i===10) td.className = 'st-raw';
    if (i===6 && r.un) td.title = r.un;
    tr.appendChild(td);
  }});
  return tr;
}}

let _lastStart = -1, _lastEnd = -1;
const tbody = document.querySelector('tbody');
const topSpacer = document.getElementById('spacer-top');
const botSpacer = document.getElementById('spacer-bot');

function render() {{
  const scroll  = document.getElementById('vs-scroll');
  const scrollTop = scroll.scrollTop;
  const viewH  = scroll.clientHeight;
  const total  = filtered.length;
  const totalH = total * ROW_H;

  const firstVis = Math.floor(scrollTop / ROW_H);
  const lastVis  = Math.min(total-1, Math.ceil((scrollTop + viewH) / ROW_H));
  const start    = Math.max(0, firstVis - BUFFER);
  const end      = Math.min(total-1, lastVis + BUFFER);

  if (start === _lastStart && end === _lastEnd) return;
  _lastStart = start; _lastEnd = end;

  // Spacers
  topSpacer.style.height = (start * ROW_H) + 'px';
  botSpacer.style.height = ((total - 1 - end) * ROW_H) + 'px';

  // Remove old rows (between the two spacer rows)
  while (tbody.children.length > 2) {{
    tbody.removeChild(tbody.children[1]);
  }}

  // Insert new rows
  const frag = document.createDocumentFragment();
  for (let i = start; i <= end; i++) {{
    frag.appendChild(makeRow(filtered[i]));
  }}
  tbody.insertBefore(frag, botSpacer.parentElement);
}}

document.getElementById('vs-scroll').addEventListener('scroll', render);
window.addEventListener('resize', render);

// ── Init ──────────────────────────────────────────────────────────────────────
applyFilters();
</script>
</body></html>"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    import os
    os.chmod(filename, 0o600)

    size_mb = os.path.getsize(filename) / 1_048_576
    print(f"[+] HTML report saved: {filename} ({size_mb:.1f} MB, {total:,} records, "
          f"virtual scrolling, permissions: 600)")
