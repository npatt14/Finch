"""Render a single self-contained HTML dashboard for browsing BriefBench + Finch results."""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def build_payload() -> dict:
    dataset = {d["id"]: d for d in _load_jsonl(DATA_DIR / "briefbench.jsonl")}
    results = {r["id"]: r for r in _load_jsonl(DATA_DIR / "results.jsonl")}
    rows = []
    for rid, d in dataset.items():
        r = results.get(rid, {})
        rows.append(
            {
                "id": rid,
                "klass": d.get("klass"),
                "citation": d.get("citation"),
                "case_name": d.get("case_name"),
                "brief_text": d.get("brief_text"),
                "quote": d.get("quote"),
                "claim": d.get("claim"),
                "notes": d.get("notes"),
                "reference_holding": d.get("reference_holding"),
                "expected_verdict": d.get("expected_verdict"),
                "expected_flag": d.get("expected_flag"),
                "actual_verdict": r.get("actual_verdict", "(not run)"),
                "actual_flag": r.get("actual_flag"),
                "correct": r.get("correct"),
                "existence": r.get("existence"),
                "quote_status": r.get("quote_status"),
                "holding_status": r.get("holding_status"),
                "confidence": r.get("confidence"),
                "explanation": r.get("explanation"),
                "retrieved_contexts": r.get("retrieved_contexts") or [],
                "latency_s": r.get("latency_s"),
                "error": r.get("error"),
            }
        )
    rows.sort(key=lambda x: (x["klass"] or "", x["id"]))
    return {
        "rows": rows,
        "metrics": _load_json(DATA_DIR / "metrics.json"),
        "ragas": _load_json(DATA_DIR / "ragas_summary.json"),
    }


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>BriefBench — Finch Evaluation</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#262b36;--fg:#e6e9ef;--mut:#9aa4b2;--good:#2ecc71;--bad:#e74c3c;--warn:#f1c40f;--accent:#5b9dff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:22px 28px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:20px}
.sub{color:var(--mut);margin-top:4px}
.wrap{padding:20px 28px;max-width:1200px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card .v{font-size:24px;font-weight:600}
.card .l{color:var(--mut);font-size:12px;margin-top:2px}
h2{font-size:15px;margin:26px 0 10px;color:var(--fg)}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);font-size:13px}
th{color:var(--mut);font-weight:600;background:#12151b}
tbody tr:hover{background:#1c2029;cursor:pointer}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600}
.ok{background:rgba(46,204,113,.15);color:var(--good)}
.no{background:rgba(231,76,60,.15);color:var(--bad)}
.mut{color:var(--mut)}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;align-items:center}
input,select{background:var(--panel);border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px 10px;font-size:13px}
input[type=search]{min-width:240px;flex:1}
.detail{background:#12151b}
.detail td{padding:0}
.detailbox{padding:14px 18px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
.detailbox h4{margin:0 0 4px;font-size:12px;color:var(--accent);text-transform:uppercase;letter-spacing:.04em}
.detailbox .field{margin-bottom:12px}
.detailbox .full{grid-column:1/3}
.ctx{background:#0c0e12;border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:6px 0;font-size:12px;color:#cbd3e0;white-space:pre-wrap}
code{background:#0c0e12;padding:1px 5px;border-radius:5px}
.count{color:var(--mut);margin-left:auto}
.v-verified{color:var(--good)}.v-fabricated,.v-not_supported{color:var(--bad)}.v-altered,.v-unverifiable,.v-error{color:var(--warn)}
</style></head><body>
<header><h1>BriefBench — Finch Evaluation</h1>
<div class="sub">Synthetic legal-brief citation dataset · classification + retrieval quality</div></header>
<div class="wrap">
<div id="cards" class="cards"></div>
<div id="ragas"></div>
<h2>Per-class accuracy</h2>
<table id="perclass"><thead><tr><th>Fault class</th><th>n</th><th>Verdict acc.</th><th>Flag acc.</th></tr></thead><tbody></tbody></table>
<h2>Items</h2>
<div class="controls">
<input id="q" type="search" placeholder="search citation, case, claim, brief…"/>
<select id="fclass"><option value="">all classes</option></select>
<select id="fres"><option value="">all outcomes</option><option value="correct">correct only</option><option value="wrong">incorrect only</option></select>
<span id="count" class="count"></span>
</div>
<table id="items"><thead><tr><th>id</th><th>class</th><th>citation</th><th>expected</th><th>actual</th><th>result</th></tr></thead><tbody></tbody></table>
</div>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const rows = DATA.rows, M = DATA.metrics||{}, R = DATA.ragas||{};
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const pct = v => v==null?'—':(v*100).toFixed(1)+'%';
const vclass = v => 'v-'+(v||'').replace(/[^a-z_]/g,'');

function cards(){
  const h = M.headline||{};
  const defs = [
    ['Items', M.n_items ?? rows.length],
    ['Exact verdict acc.', pct(h.exact_verdict_accuracy)],
    ['Clean verified', pct(h.clean_verified_rate)],
    ['False-positive (clean)', pct(h.false_positive_rate_on_clean)],
    ['Fabrication recall', pct(h.fabrication_recall)],
    ['Detection recall', pct(h.detection_recall_overall)],
    ['Injection resistance', pct(h.injection_resistance)],
    ['Recent≠fabricated', pct(h.recent_not_miscalled_fabricated)],
    ['Errors', M.errors ?? 0],
  ];
  document.getElementById('cards').innerHTML = defs.map(([l,v])=>
    `<div class="card"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join('');
}
function ragas(){
  if(!R || !Object.keys(R).length) return;
  const order = ['faithfulness','llm_context_precision_with_reference','context_recall','answer_relevancy','semantic_similarity'];
  const keys = Object.keys(R).filter(k=>k!=='n_samples');
  keys.sort((a,b)=>order.indexOf(a)-order.indexOf(b));
  const cardsHtml = keys.map(k=>`<div class="card"><div class="v">${typeof R[k]==='number'?R[k].toFixed(3):esc(R[k])}</div><div class="l">${esc(k)}</div></div>`).join('');
  document.getElementById('ragas').innerHTML =
    `<h2>RAGAS — retrieval &amp; answer quality (n=${esc(R.n_samples||'?')})</h2><div class="cards">${cardsHtml}</div>`;
}
function perclass(){
  const pc = M.per_class||{};
  document.querySelector('#perclass tbody').innerHTML = Object.keys(pc).sort().map(k=>{
    const c = pc[k];
    return `<tr><td>${esc(k)}</td><td>${c.n}</td><td>${pct(c.verdict_accuracy)}</td><td>${pct(c.flag_accuracy)}</td></tr>`;
  }).join('') || '<tr><td colspan="4" class="mut">no metrics yet</td></tr>';
}
function detailHtml(r){
  const ctx = (r.retrieved_contexts||[]).map(c=>`<div class="ctx">${esc(c)}</div>`).join('') || '<span class="mut">none</span>';
  const f = (label,val)=>`<div class="field"><h4>${label}</h4><div>${val}</div></div>`;
  return `<div class="detailbox">
    ${f('Brief text', esc(r.brief_text))}
    ${f('Notes', esc(r.notes)||'<span class=mut>—</span>')}
    ${f('Quote', r.quote?esc(r.quote):'<span class=mut>—</span>')}
    ${f('Claim', r.claim?esc(r.claim):'<span class=mut>—</span>')}
    ${f('Reference holding', r.reference_holding?esc(r.reference_holding):'<span class=mut>—</span>')}
    ${f('Pipeline', `existence=<code>${esc(r.existence)}</code> quote=<code>${esc(r.quote_status)}</code> holding=<code>${esc(r.holding_status)}</code> conf=<code>${esc(r.confidence)}</code> ${r.latency_s?'· '+r.latency_s+'s':''}`)}
    ${f('Adjudicator explanation', r.explanation?esc(r.explanation):'<span class=mut>—</span>')}
    ${r.error?f('Error','<span class="no">'+esc(r.error)+'</span>'):''}
    <div class="field full"><h4>Retrieved contexts</h4>${ctx}</div>
  </div>`;
}
function render(){
  const q = document.getElementById('q').value.toLowerCase();
  const fc = document.getElementById('fclass').value;
  const fr = document.getElementById('fres').value;
  const tb = document.querySelector('#items tbody');
  tb.innerHTML='';
  let n=0;
  rows.forEach(r=>{
    if(fc && r.klass!==fc) return;
    if(fr==='correct' && r.correct!==true) return;
    if(fr==='wrong' && r.correct===true) return;
    if(q){
      const hay = [r.id,r.citation,r.case_name,r.claim,r.brief_text,r.klass].join(' ').toLowerCase();
      if(!hay.includes(q)) return;
    }
    n++;
    const res = r.correct===true?'<span class="pill ok">pass</span>':(r.actual_verdict==='(not run)'?'<span class="mut">—</span>':'<span class="pill no">fail</span>');
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="mut">${esc(r.id)}</td><td>${esc(r.klass)}</td><td>${esc(r.citation)}</td>`+
      `<td class="${vclass(r.expected_verdict)}">${esc(r.expected_verdict)}</td>`+
      `<td class="${vclass(r.actual_verdict)}">${esc(r.actual_verdict)}</td><td>${res}</td>`;
    const det = document.createElement('tr');
    det.className='detail'; det.style.display='none';
    det.innerHTML = `<td colspan="6">${detailHtml(r)}</td>`;
    tr.addEventListener('click',()=>{det.style.display = det.style.display==='none'?'':'none';});
    tb.appendChild(tr); tb.appendChild(det);
  });
  document.getElementById('count').textContent = n+' / '+rows.length+' shown';
}
(function init(){
  cards(); ragas(); perclass();
  const cls = [...new Set(rows.map(r=>r.klass))].sort();
  document.getElementById('fclass').insertAdjacentHTML('beforeend', cls.map(c=>`<option>${esc(c)}</option>`).join(''));
  ['q','fclass','fres'].forEach(id=>document.getElementById(id).addEventListener('input',render));
  render();
})();
</script></body></html>"""


def main():
    payload = build_payload()
    html = HTML.replace("__PAYLOAD__", json.dumps(payload).replace("</", "<\\/"))
    out = DATA_DIR / "report.html"
    out.write_text(html)
    print(f"Wrote {out} ({len(payload['rows'])} rows, {len(html)//1024} KB)")


if __name__ == "__main__":
    main()
