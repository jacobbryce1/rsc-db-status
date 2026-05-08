"""Interactive HTML report with filtering and dashboard."""
from datetime import datetime
from ..config import (
    RSC_DOMAIN, STALE_SNAPSHOT_DAYS, MISSED_SNAPSHOT_LOOKBACK_HOURS,
    TIMESTAMP
)


def write_html_report(databases: list, filename: str):
    """Generate interactive HTML report."""
    total = len(databases)

    online = sum(1 for d in databases if d.get("event_status") == "Online")
    warning = sum(1 for d in databases if "Warning" in d.get("event_status", ""))
    offline = sum(1 for d in databases if "Offline" in d.get("event_status", ""))
    relic = sum(1 for d in databases if "Relic" in d.get("event_status", ""))
    unknown = total - online - warning - offline - relic

    platforms = sorted(set(d.get("platform", "") for d in databases))
    clusters = sorted(set(d.get("cluster_name", "") for d in databases))
    slas = sorted(set(d.get("sla_name", "") for d in databases))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RSC DB Status Report — {TIMESTAMP}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
margin:20px;background:#f5f7fa;color:#1a1a2e}}
h1{{color:#1a237e;border-bottom:3px solid #00897b;padding-bottom:10px}}
.note{{background:#e3f2fd;padding:12px 16px;border-radius:6px;
margin-bottom:20px;font-size:13px;border-left:4px solid #1565c0}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:16px;margin-bottom:24px}}
.c{{background:white;border-radius:8px;padding:20px;
box-shadow:0 2px 8px rgba(0,0,0,.08);text-align:center}}
.c h3{{margin:0 0 8px;font-size:13px;color:#666}}
.m{{font-size:32px;font-weight:bold}}
.m-on{{color:#22c55e}}.m-off{{color:#ef4444}}
.m-warn{{color:#f97316}}.m-unk{{color:#6b7280}}.m-rel{{color:#9ca3af}}
.filters{{margin-bottom:16px;display:flex;gap:12px;flex-wrap:wrap;
align-items:center;background:white;padding:16px;
border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.05)}}
.filters input,.filters select{{padding:8px 12px;border:1px solid #ddd;
border-radius:4px;font-size:13px}}
.filters input{{min-width:250px}}
table{{width:100%;border-collapse:collapse;background:white;
border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);
font-size:12px;margin-top:15px}}
th{{background:#1e293b;color:white;padding:12px 8px;text-align:left;
font-size:11px;cursor:pointer;position:sticky;top:0}}
th:hover{{background:#334155}}
td{{padding:10px 8px;border-bottom:1px solid #f1f5f9}}
tr:hover td{{background:#f8fafc}}
.truncate{{max-width:150px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}}
#counter{{font-size:14px;color:#666;font-weight:500}}
.st-on{{color:#16a34a;font-weight:500}}
.st-off{{color:#dc2626;font-weight:500}}
.st-warn{{color:#ea580c;font-weight:500}}
.st-rel{{color:#9ca3af;font-style:italic}}
</style>
</head>
<body>
<h1>🔴🟢 Rubrik RSC — Database Status Report</h1>
<p style="color:#9e9e9e">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {RSC_DOMAIN}</p>

<div class="note">
<strong>Status Detection:</strong> Uses <code>unprotectableReasons</code>,
missed snapshot events, missed recoverable range events,
snapshot recency ({STALE_SNAPSHOT_DAYS}d threshold), SLA pause status,
and cloud native state. MSSQL event lookback: {MISSED_SNAPSHOT_LOOKBACK_HOURS}h.
</div>

<div class="g">
<div class="c"><h3>TOTAL</h3><div class="m" style="color:#1a237e">{total}</div></div>
<div class="c"><h3>🟢 ONLINE</h3><div class="m m-on">{online}</div></div>
<div class="c"><h3>🔴 OFFLINE</h3><div class="m m-off">{offline}</div></div>
<div class="c"><h3>⚠️ WARNING</h3><div class="m m-warn">{warning}</div></div>
<div class="c"><h3>👻 RELIC</h3><div class="m m-rel">{relic}</div></div>
<div class="c"><h3>❓ OTHER</h3><div class="m m-unk">{unknown}</div></div>
</div>

<div class="filters">
<input type="text" id="fi" placeholder="Search by name..." onkeyup="ff()">
<select id="sf" onchange="ff()"><option value="">All Statuses</option>
<option value="Online">Online</option><option value="Warning">Warning</option>
<option value="Offline">Offline</option><option value="Relic">Relic</option></select>
<select id="pf" onchange="ff()"><option value="">All Platforms</option>
{"".join(f'<option value="{p}">{p}</option>' for p in platforms)}</select>
<select id="clf" onchange="ff()"><option value="">All Clusters</option>
{"".join(f'<option value="{c}">{c}</option>' for c in clusters[:50])}</select>
<select id="slaf" onchange="ff()"><option value="">All SLAs</option>
{"".join(f'<option value="{s}">{s}</option>' for s in slas[:50])}</select>
<span id="counter">Showing {total} of {total}</span>
</div>

<table>
<thead><tr>
<th onclick="st(0)">Name</th>
<th onclick="st(1)">Platform</th>
<th onclick="st(2)">Cluster/Region</th>
<th onclick="st(3)">SLA</th>
<th onclick="st(4)">Engine</th>
<th onclick="st(5)">Relic</th>
<th onclick="st(6)">Unprotected Reason</th>
<th onclick="st(7)">Newest Snapshot</th>
<th onclick="st(8)">Missed</th>
<th onclick="st(9)">Status</th>
</tr></thead>
<tbody id="tb">
"""

    for db in databases:
        unp = db.get("unprotected_reason", "") or ""
        unp_short = unp[:25] + "..." if len(unp) > 25 else unp
        status = db.get("event_status", "")
        status_class = ("st-on" if "Online" in status
                        else "st-off" if "Offline" in status
                        else "st-warn" if "Warning" in status
                        else "st-rel" if "Relic" in status
                        else "")
        engine = db.get("db_engine", "") or db.get("recovery_model", "")
        html += f"""<tr data-status="{status}" data-platform="{db.get('platform','')}" \
data-cluster="{db.get('cluster_name','')}" data-sla="{db.get('sla_name','')}">
<td>{db.get('name','')}</td>
<td>{db.get('platform','')}</td>
<td>{db.get('cluster_name','')}</td>
<td>{db.get('sla_name','')}</td>
<td>{engine}</td>
<td>{'Yes' if db.get('is_relic') else 'No'}</td>
<td class="truncate" title="{unp}">{unp_short}</td>
<td>{db.get('newest_snapshot','')[:10]}</td>
<td>{db.get('total_missed_snapshots',0)}</td>
<td class="{status_class}">{status}</td>
</tr>\n"""

    html += f"""</tbody></table>
<script>
function ff(){{
var fi=document.getElementById('fi').value.toLowerCase();
var sf=document.getElementById('sf').value;
var pf=document.getElementById('pf').value;
var clf=document.getElementById('clf').value;
var slaf=document.getElementById('slaf').value;
var rows=document.getElementById('tb').getElementsByTagName('tr');
var shown=0;
for(var i=0;i<rows.length;i++){{
var r=rows[i];var name=r.cells[0].textContent.toLowerCase();
var status=r.getAttribute('data-status');
var platform=r.getAttribute('data-platform');
var cluster=r.getAttribute('data-cluster');
var sla=r.getAttribute('data-sla');
var show=true;
if(fi&&name.indexOf(fi)===-1)show=false;
if(sf&&status.indexOf(sf)===-1)show=false;
if(pf&&platform!==pf)show=false;
if(clf&&cluster!==clf)show=false;
if(slaf&&sla!==slaf)show=false;
r.style.display=show?'':'none';
if(show)shown++;
}}
document.getElementById('counter').textContent='Showing '+shown+' of {total}';
}}
var sortDir={{}};
function st(col){{
var tb=document.getElementById('tb');
var rows=Array.from(tb.rows);
sortDir[col]=!sortDir[col];
rows.sort(function(a,b){{
var x=a.cells[col].textContent.toLowerCase();
var y=b.cells[col].textContent.toLowerCase();
if(!isNaN(x)&&!isNaN(y))return sortDir[col]?x-y:y-x;
return sortDir[col]?x.localeCompare(y):y.localeCompare(x);
}});
rows.forEach(function(r){{tb.appendChild(r);}});
}}
</script>
</body></html>"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[+] HTML report saved: {filename}")
