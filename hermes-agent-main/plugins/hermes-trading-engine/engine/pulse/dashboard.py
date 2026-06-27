"""Read-only BTC pulse dashboard HTML (embedded SPA)."""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>BTC Pulse · Hermes (paper)</title>
<style>
:root{
  --bg:#14161c;--bg2:#1a1d26;--card:#1e222c;--card2:#252a36;
  --text:#d4dae3;--text2:#9aa3b2;--text3:#6e7687;
  --line:#2d3340;--line2:#383f4d;
  --good:#7dcea0;--bad:#d4a5a5;--warn:#d4c4a5;--accent:#8eb8e8;
  --radius:14px;--gap:18px;
}
*{box-sizing:border-box}
body{
  margin:0;background:var(--bg);color:var(--text);
  font:21px/1.65 "Segoe UI",system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased;
}
header{
  padding:20px 24px 16px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;
  border-bottom:1px solid var(--line);background:var(--bg2);
}
h1{font-size:28px;font-weight:600;margin:0;letter-spacing:-.02em;color:var(--text)}
.tag{font-size:17px;color:var(--text3);padding:4px 10px;border-radius:20px;background:var(--card)}
.tag.live{color:var(--good);background:rgba(125,206,160,.12)}
.tag.off{color:var(--bad);background:rgba(212,165,165,.12)}
main{max-width:1180px;margin:0 auto;padding:24px 20px 40px}
.hero{
  display:grid;grid-template-columns:1.2fr 1fr;gap:var(--gap);margin-bottom:var(--gap);
}
@media(max-width:820px){.hero{grid-template-columns:1fr}}
.panel{
  background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px 22px;
}
.panel.soft{background:var(--bg2);border-color:transparent}
.panel h2{
  margin:0 0 14px;font-size:18px;font-weight:600;color:var(--text2);
  letter-spacing:.01em;text-transform:none;
}
.panel.trades-panel{
  border-color:rgba(142,184,232,.35);
  background:linear-gradient(180deg,var(--card) 0%,var(--card2) 100%);
}
.panel.trades-panel h2{color:var(--accent);font-size:20px}
.panel h3.sub{
  margin:20px 0 10px;font-size:17px;font-weight:600;color:var(--text2);
}
.money{font-size:48px;font-weight:600;letter-spacing:-.03em;line-height:1.2}
.money-sub{margin-top:8px;color:var(--text2);font-size:20px}
.money-sub b{font-weight:600;color:var(--text)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--gap)}
.prose p{margin:0 0 10px;color:var(--text2);font-size:20px}
.prose p:last-child{margin-bottom:0}
.prose b{color:var(--text);font-weight:600}
.kv{display:grid;gap:8px}
.kv-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--line)}
.kv-row:last-child{border-bottom:0}
.kv-k{color:var(--text2);font-size:18px}
.kv-v{font-variant-numeric:tabular-nums;color:var(--text);font-size:18px;text-align:right}
.pos{color:var(--good)}.neg{color:var(--bad)}.neu{color:var(--text3)}
.market-table{width:100%;border-collapse:collapse;font-size:18px}
.market-table th,.market-table td{padding:10px 8px;text-align:right;border-bottom:1px solid var(--line)}
.market-table th:first-child,.market-table td:first-child{text-align:left}
.market-table th{color:var(--text3);font-weight:500;font-size:17px}
details.tech{margin-top:28px}
details.tech>summary{
  cursor:pointer;list-style:none;color:var(--text2);font-size:18px;
  padding:12px 0;border-top:1px solid var(--line);user-select:none;
}
details.tech>summary::-webkit-details-marker{display:none}
details.tech[open]>summary{margin-bottom:var(--gap);color:var(--text)}
table.data{width:100%;border-collapse:collapse;font-size:18px}
table.data th,table.data td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line)}
table.data th:first-child,table.data td:first-child{text-align:left}
table.data th{color:var(--text3);font-weight:500}
table.data tr:hover td{background:rgba(255,255,255,.02)}
.coupling-banner{
  display:none;margin:0 20px 0;max-width:1180px;margin-left:auto;margin-right:auto;
  padding:14px 18px;border-radius:var(--radius);border:1px solid rgba(212,196,165,.35);
  background:rgba(212,196,165,.1);color:var(--warn);font-size:18px;
}
.coupling-banner.show{display:block}
.coupling-banner b{color:var(--text)}
.flow{
  display:flex;flex-wrap:wrap;gap:6px 4px;align-items:center;
  font-size:17px;color:var(--text2);margin:0 0 14px;
}
.flow span.step{
  padding:4px 10px;border-radius:8px;background:var(--bg2);border:1px solid var(--line);
  color:var(--text);white-space:nowrap;
}
.flow span.arr{color:var(--text3);font-size:15px}
.pill{
  display:inline-block;padding:2px 8px;border-radius:10px;font-size:15px;
  background:var(--bg2);color:var(--text2);
}
.pill.ok{color:var(--good);background:rgba(125,206,160,.12)}
.pill.warn{color:var(--warn);background:rgba(212,196,165,.12)}
.pill.off{color:var(--text3)}
.lesson-item{
  font-size:17px;color:var(--text2);padding:6px 0;border-bottom:1px solid var(--line);
}
.lesson-item:last-child{border-bottom:0}
.lesson-item b{color:var(--text);font-weight:600}
.foot{margin-top:32px;padding-top:16px;border-top:1px solid var(--line);color:var(--text3);font-size:17px}
</style>
</head>
<body>
<header>
  <h1>BTC Pulse</h1>
  <span class="tag">Paper only</span>
  <span class="tag" id="health">Loading...</span>
  <span class="tag neu" id="meta"></span>
</header>
<div class="coupling-banner" id="coupling-banner"></div>
<main>
  <div class="hero" id="hero"></div>
  <div class="grid" id="summary"></div>
  <details class="tech" id="tech-wrap">
    <summary>Show technical details</summary>
    <div class="grid" id="tech"></div>
  </details>
  <div class="foot">Refreshes every 5s · read-only · Chainlink oracle via Polymarket RTDS</div>
</main>
<script>
const $=(h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild};
const f=(x,d=2)=>x==null?'—':(typeof x==='number'?x.toFixed(d):x);
const money=(x)=>x==null?'—':(x>=0?'+$':'-$')+Math.abs(x).toFixed(2);
const pnlCls=(x)=>x==null?'neu':(x>=0?'pos':'neg');
function is15m(obj){
  const lbl=String((obj&&obj.series_label)||'').toLowerCase();
  const slug=String((obj&&obj.series_slug)||(obj&&obj.market_series)||'').toLowerCase();
  return lbl==='15m'||slug.includes('15m');
}
function is15mPosition(p){
  const r=(p&&p.research)||{};
  if(is15m(r)) return true;
  const ttc=r.entry_ttc_s;
  if(ttc!=null&&Number(ttc)>=400) return true;
  const ws=r.window_seconds;
  if(ws!=null&&Number(ws)>=900) return true;
  return false;
}
function fmtTs(ts){
  if(ts==null) return '—';
  try{return new Date(Number(ts)*1000).toLocaleString();}catch(e){return '—';}
}
function tradeResult(x){
  if((x.status||'').toLowerCase()==='open') return ['open','neu'];
  if(x.won===true) return ['win','pos'];
  if(x.won===false) return ['loss','neg'];
  return [x.status||'—','neu'];
}
function recentTradesTable(pos){
  const tb=$('<table class="market-table"><thead><tr><th>Time</th><th>Window</th><th>Side</th><th>Entry</th><th>TTC</th><th>Fair</th><th>Result</th><th>PnL</th><th>Mode</th></tr></thead><tbody></tbody></table>');
  pos.forEach(x=>{
    const r=x.research||{};
    const [res,cls]=tradeResult(x);
    const side=(x.side||'—').toUpperCase();
    const sideCls=side==='DOWN'?'neg':(side==='UP'?'pos':'neu');
    tb.querySelector('tbody').appendChild($(`<tr>
      <td class="neu">${fmtTs(x.entry_ts)}</td>
      <td>${x.window_key||'—'}</td>
      <td class="${sideCls}">${side}</td>
      <td>${f(x.entry_price,3)}</td>
      <td class="neu">${r.entry_ttc_s==null?'—':f(r.entry_ttc_s,0)+'s'}</td>
      <td>${f(x.fair_at_entry,3)}</td>
      <td class="${cls}">${res}</td>
      <td class="${pnlCls(x.pnl_usd)}">${x.pnl_usd==null?'—':money(x.pnl_usd)}</td>
      <td class="neu">${r.entry_mode||r.gate_decision||'—'}</td>
    </tr>`));
  });
  return tb;
}
function loopLivePill(info){
  if(info.stalled) return '<span class="pill warn">stalled</span>';
  if(info.last_beat_age_s!=null){
    const age=info.last_beat_age_s;
    return '<span class="pill '+(age<30?'ok':'warn')+'">'+f(age,0)+'s ago</span>';
  }
  const st=info.status||{};
  if(st.tripped) return '<span class="pill warn">tripped</span>';
  if(st.enabled===false) return '<span class="pill off">off</span>';
  if(st.mode) return '<span class="pill ok">'+st.mode+'</span>';
  return '<span class="pill off">—</span>';
}
function loopStatusNote(info){
  const st=info.status||{};
  const bits=[];
  if(st.decided!=null) bits.push('decided '+st.decided);
  if(st.requested!=null) bits.push('req '+st.requested);
  if(st.errors) bits.push('err '+st.errors);
  if(st.calls!=null) bits.push('calls '+st.calls);
  if(st.tripped!=null) bits.push(st.tripped?'breaker':'ok');
  if(info.stop_condition) bits.push(info.stop_condition);
  return bits.length?bits.join(' · '):'—';
}
function loopsTable(loopsRoot){
  const loops=(loopsRoot&&loopsRoot.loops)||{};
  const names=Object.keys(loops).sort();
  const tb=$('<table class="data"><thead><tr><th>Loop</th><th>Role</th><th>Trigger</th><th>Cadence</th><th>Live</th><th>Status</th></tr></thead><tbody></tbody></table>');
  names.forEach(name=>{
    const info=loops[name]||{};
    const cad=info.interval_s==null?'—':f(info.interval_s,0)+'s';
    tb.querySelector('tbody').appendChild($(`<tr>
      <td>${name}</td><td class="neu">${info.role||'—'}</td>
      <td class="neu">${info.trigger||'—'}</td><td class="neu">${cad}</td>
      <td>${loopLivePill(info)}</td>
      <td class="neu">${loopStatusNote(info)}</td>
    </tr>`));
  });
  return tb;
}
function gateFunnelLines(lc){
  const terms=lc.terminals||{};
  const rbs=lc.rejected_by_stage||{};
  const top=Object.entries(rbs).sort((a,b)=>b[1]-a[1]).slice(0,4);
  const lines=[
    'Windows scanned <b>'+(lc.created||0)+'</b> · scored <b>'+(lc.feature_scored||0)+'</b> · '
    +'fills <b>'+(terms.accepted||0)+'</b> · rejected <b>'+(terms.rejected||0)+'</b> · skipped <b>'+(terms.skipped||0)+'</b>',
  ];
  if(top.length) lines.push('Top blocks: <b>'+top.map(([k,v])=>k+' ('+v+')').join(', ')+'</b>');
  return lines;
}
function appendKvRows(kv,rows){
  rows.forEach(([k,v,cls])=>{
    const r=$('<div class="kv-row"><span class="kv-k"></span><span class="kv-v"></span></div>');
    r.querySelector('.kv-k').textContent=k;
    const vEl=r.querySelector('.kv-v');
    vEl.textContent=v;
    if(cls) vEl.classList.add(cls);
    kv.appendChild(r);
  });
}
function loopEngineSection(s){
  const wrap=document.createDocumentFragment();
  const lc=s.decision_lifecycle||{};
  const lr=s.learning||{};
  const sg=s.learned_selectivity_gate||{};
  const cohort=s.baseline_cohort_gate||{};
  const les=s.lessons||{};
  const rl=s.research_loop||{};
  const gd=s.grok_decider||{};
  const loops=s.loops||{};
  const mb=(lr.market_benchmark||{});

  const h3op=$('<h3 class="sub">Loop engine · operation</h3>');
  wrap.appendChild(h3op);
  const flow=$('<div class="flow"></div>');
  ['Tick','Ingest','Fair P(up)','Gate stack','Exec gate','Paper fill','Settle','Learn']
    .forEach((step,i,arr)=>{
      flow.appendChild($('<span class="step">'+step+'</span>'));
      if(i<arr.length-1) flow.appendChild($('<span class="arr">→</span>'));
    });
  wrap.appendChild(flow);
  const opProse=proseCard('',gateFunnelLines(lc));
  opProse.querySelector('h2').remove();
  wrap.appendChild(opProse);
  if(loops.count) wrap.appendChild(loopsTable(loops));

  const strat=$('<div class="panel soft" style="margin-top:12px"><h2>Quant path (15m DOWN)</h2><div class="kv"></div></div>');
  const mtfG3=(s.tradingview||{}).mtf_gate||{};
  appendKvRows(strat.querySelector('.kv'),[
    ['Green path',cohort.green_path_enabled?'on':'off',cohort.green_path_enabled?'pos':'neu'],
    ['TV trade authority',mtfG3.enabled?'MTF on':'observe-only',mtfG3.enabled?'neg':'pos'],
    ['Cohort TTC (15m)',cohort['15m_ttc_band_s']?cohort['15m_ttc_band_s'].join('–')+'s':'—'],
    ['DOWN TV gate',cohort.down_tv_gate_enabled?'on':'off',cohort.down_tv_gate_enabled?'neg':'pos'],
    ['Cohort blocks',cohort.blocked!=null?cohort.blocked:'—'],
  ]);
  wrap.appendChild(strat);

  const h3learn=$('<h3 class="sub">Learning & self-improvement</h3>');
  wrap.appendChild(h3learn);
  const learnNote=$('<div class="money-sub" style="margin-bottom:12px"></div>');
  learnNote.innerHTML='Closed loop: every settled trade grades the model, updates bucket evidence, '
    +'compounds lessons, and tightens or loosens gates. Execution gate always has final veto.';
  wrap.appendChild(learnNote);

  const grid=$('<div class="grid" style="margin-top:8px"></div>');
  const blend=$('<div class="panel soft"><h2>Model blend</h2><div class="kv"></div></div>');
  appendKvRows(blend.querySelector('.kv'),[
    ['Enabled',lr.enabled?'yes':'no'],
    ['Active',lr.active?'yes ('+f((lr.weight||0)*100,0)+'% weight)':'no',lr.active?'pos':'neu'],
    ['Reason',lr.reason||'—'],
    ['Labels',lr.model_n_labeled!=null?lr.model_n_labeled:'—'],
    ['Calib error',lr.model_calibration_error==null?'—':f(lr.model_calibration_error,3)],
    ['Beats market',mb.model_beats_market==null?'—':(mb.model_beats_market?'yes':'no'),
      mb.model_beats_market?'pos':(mb.model_beats_market===false?'neg':'neu')],
  ]);
  grid.appendChild(blend);

  const sel=$('<div class="panel soft"><h2>Selectivity gate</h2><div class="kv"></div></div>');
  const cf=sg.counterfactual||{};
  appendKvRows(sel.querySelector('.kv'),[
    ['Rule',sg.decision_rule||'—'],
    ['Accepted',sg.accepted!=null?sg.accepted:'—','pos'],
    ['Rejected',sg.rejected!=null?sg.rejected:'—',(sg.rejected>0?'neg':'neu')],
    ['Explored',sg.explored!=null?sg.explored:'—'],
    ['Losses avoided',cf.losses_avoided!=null?cf.losses_avoided:'—',(cf.losses_avoided>0?'pos':'neu')],
  ]);
  grid.appendChild(sel);

  const mem=$('<div class="panel soft"><h2>Memory & research</h2><div class="kv"></div></div>');
  appendKvRows(mem.querySelector('.kv'),[
    ['Lessons',(les.active||0)+' active / '+(les.count||0)+' total'],
    ['Research loop',rl.enabled?'on':'off',rl.enabled?'pos':'neu'],
    ['Grok mode',gd.mode||'—'],
    ['View accuracy',gd.view_accuracy==null?'—':f(gd.view_accuracy*100,0)+'%'],
    ['Verifier',((s.verifier||{}).approvals||0)+' ok / '+((s.verifier||{}).vetoes||0)+' veto'],
  ]);
  grid.appendChild(mem);
  wrap.appendChild(grid);

  const recent=les.recent||[];
  if(recent.length){
    const sub=$('<h3 class="sub" style="margin-top:16px">Active lessons</h3>');
    wrap.appendChild(sub);
    const box=$('<div></div>');
    recent.slice(0,5).forEach(ln=>{
      const el=$('<div class="lesson-item"></div>');
      el.innerHTML='<b>'+(ln.kind||'rule')+'</b> · '+(ln.rule||'—');
      box.appendChild(el);
    });
    wrap.appendChild(box);
  }
  const rlNote=(rl.last_note||{}).summary;
  if(rlNote){
    const sub=$('<h3 class="sub" style="margin-top:16px">Research meta-loop</h3>');
    wrap.appendChild(sub);
    const p=$('<p class="prose" style="margin:0;color:var(--text2);font-size:18px"></p>');
    p.textContent=rlNote;
    wrap.appendChild(p);
  }
  return wrap;
}
function kvCard(title,rows){
  const c=$('<div class="panel"><h2></h2><div class="kv"></div></div>');
  c.querySelector('h2').textContent=title;
  const kv=c.querySelector('.kv');
  rows.forEach(([k,v,cls])=>{
    const r=$('<div class="kv-row"><span class="kv-k"></span><span class="kv-v"></span></div>');
    r.querySelector('.kv-k').textContent=k;
    const vEl=r.querySelector('.kv-v');
    vEl.textContent=v;
    if(cls) vEl.classList.add(cls);
    kv.appendChild(r);
  });
  return c;
}
function proseCard(title,lines){
  const c=$('<div class="panel soft"><h2></h2><div class="prose"></div></div>');
  c.querySelector('h2').textContent=title;
  const p=c.querySelector('.prose');
  lines.forEach(html=>{const el=$('<p></p>');el.innerHTML=html;p.appendChild(el)});
  return c;
}
async function fetchJson(url,timeoutMs=20000){
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(),timeoutMs);
  try{
    const r=await fetch(url,{cache:'no-store',signal:ctrl.signal});
    if(!r.ok) throw new Error('HTTP '+r.status);
    return await r.json();
  }finally{clearTimeout(timer);}
}
function setHealth(text,cls){
  const h=document.getElementById('health');
  h.textContent=text;
  h.className='tag'+(cls?' '+cls:'');
}
async function tick(){
  setHealth('Loading...','');
  let s,l;
  try{
    [s,l]=await Promise.all([
      fetchJson('/api/polymarket/training/btc_pulse'),
      fetchJson('/api/polymarket/training/btc_pulse/ledger?summary=1'),
    ]);
  }catch(e){
    setHealth(e&&e.name==='AbortError'?'Timed out':'Unreachable','off');
    return;
  }
  try{
  if(!s.available){setHealth('No data','off');return}
  setHealth('Live','live');
  const cfg=s.config||{};
  document.getElementById('meta').textContent='Ticks '+s.ticks+' · tick '+f(cfg.tick_seconds,0)+'s · max '+f(cfg.max_price,2)+' · '+new Date().toLocaleTimeString();

  const coupling=s.config_coupling||{};
  const cBanner=document.getElementById('coupling-banner');
  if(coupling.active&&!coupling.configured_ok){
    cBanner.className='coupling-banner show';
    cBanner.innerHTML='Gate coupling: <b>PULSE_TV_CONTEXT_MAX_TTC_S='+coupling.configured_s
      +'</b> is too low (need &gt;='+coupling.required_min_s+'s). Runtime clamped to '
      +coupling.effective_s+'s — fix .env.';
  }else if(coupling.active&&coupling.auto_clamped){
    cBanner.className='coupling-banner show';
    cBanner.innerHTML='Gate coupling: env context max was raised at runtime to <b>'
      +coupling.effective_s+'s</b> (configured '+coupling.configured_s+'). Update .env.';
  }else{cBanner.className='coupling-banner';cBanner.innerHTML='';}

  const L=s.ledger||{},cap=s.capital||{},gd=s.grok_decider||{},ver=s.verifier||{};
  const hero=document.getElementById('hero');hero.innerHTML='';
  const onhand=cap.on_hand_capital_usd, start0=cap.starting_capital_usd||500;
  const diff=(onhand!=null&&start0!=null)?(onhand-start0):null;
  const up=diff!=null&&diff>=0;
  hero.appendChild($(`<div class="panel">
    <h2>Capital (paper)</h2>
    <div class="money ${up?'pos':'neg'}">$${f(onhand,2)}</div>
    <div class="money-sub">
      Started $${f(start0,2)} · PnL <b class="${pnlCls(diff)}">${money(diff)}</b>
      (${f(cap.return_pct,1)}%)<br>
      Arb ${money(cap.arb_realized_pnl_usd)} · Total ${money(cap.total_realized_pnl_usd)}
      (${f(cap.total_return_pct,1)}%)
    </div></div>`));

  const lc=s.decision_lifecycle||{}, rbs=lc.rejected_by_stage||{};
  const topGate=Object.entries(rbs).sort((a,b)=>b[1]-a[1])[0];
  const wr=(L.win_rate||0)*100;
  const dr=s.directional_risk||{};
  const cohort=s.baseline_cohort_gate||{};
  const mtfG=(s.tradingview||{}).mtf_gate||{};
  hero.appendChild(proseCard('At a glance',[
    'Status: <b>Running</b> · '+(L.open_positions>0?'has open position':'scanning markets'),
    'Trades <b>'+(L.trades||0)+'</b> ('+(L.settled||0)+' settled) · Win rate <b>'+f(wr,1)+'%</b>',
    '15m DOWN-only · green path <b class="'+(cohort.green_path_enabled?'pos':'neu')+'">'+(cohort.green_path_enabled?'on':'off')+'</b> · TV gate <b class="pos">observe-only</b>',
    topGate?('Most blocks: <b>'+topGate[0]+'</b> ('+topGate[1]+')'):'No gate blocks recorded yet',
    'Grok <b>'+(gd.mode||'—')+'</b> · Verifier '+((ver.approvals||0)+' ok / '+(ver.vetoes||0)+' veto')+' · MTF trade gate <b>'+(mtfG.enabled?'on':'off')+'</b>'
  ]));

  const summary=document.getElementById('summary');summary.innerHTML='';
  const allPos=((l&&l.positions)||[]).slice().sort((a,b)=>(Number(b.entry_ts)||0)-(Number(a.entry_ts)||0));
  const pos15=allPos.filter(is15mPosition).slice(0,10);
  const tradesPanel=$('<div class="panel trades-panel" style="grid-column:1/-1"><h2>Recent 15m trades</h2></div>');
  if(pos15.length){
    const settled=pos15.filter(x=>(x.status||'').toLowerCase()==='settled');
    const wins=settled.filter(x=>x.won===true).length;
    const pnl15=settled.reduce((s,x)=>s+(Number(x.pnl_usd)||0),0);
    const foot=$('<div class="money-sub" style="margin-bottom:14px"></div>');
    foot.innerHTML='Showing <b>'+pos15.length+'</b> latest 15m fills · '
      +'settled <b>'+settled.length+'</b> · wins <b>'+wins+'</b> · net <b class="'+pnlCls(pnl15)+'">'+money(pnl15)+'</b>';
    tradesPanel.appendChild(foot);
    tradesPanel.appendChild(recentTradesTable(pos15));
  }else{
    tradesPanel.appendChild($('<p class="prose" style="margin:0;color:var(--text2)">No 15m trades in the recent ledger window yet.</p>'));
  }
  summary.appendChild(tradesPanel);

  const bySeries=s.by_market_series||{};
  const seriesKeys=Object.keys(bySeries).filter(k=>is15m(bySeries[k]));
  const mPanel=$('<div class="panel" style="grid-column:1/-1"><h2>15m performance summary</h2></div>');
  if(seriesKeys.length){
    const tb=$('<table class="market-table"><thead><tr><th>Market</th><th>Settled</th><th>Win rate</th><th>PF</th><th>PnL</th><th>UP</th><th>DOWN</th></tr></thead><tbody></tbody></table>');
    seriesKeys.sort((a,b)=>(bySeries[a].series_label||'').localeCompare(bySeries[b].series_label||''))
      .forEach(k=>{const r=bySeries[k];
        tb.querySelector('tbody').appendChild($(`<tr>
          <td>${r.series_label||k}</td><td>${r.settled||0}</td>
          <td>${r.win_rate==null?'—':f(r.win_rate*100,1)+'%'}</td>
          <td>${f(r.profit_factor,2)}</td>
          <td class="${pnlCls(r.pnl_usd)}">${money(r.pnl_usd)}</td>
          <td>${r.win_rate_up==null?'—':f(r.win_rate_up*100,0)+'%'}</td>
          <td>${r.win_rate_down==null?'—':f(r.win_rate_down*100,0)+'%'}</td>
        </tr>`));
      });
    mPanel.appendChild(tb);
  }else{
    mPanel.appendChild($('<p class="prose" style="margin:0;color:var(--text2)">No 15m aggregate stats yet.</p>'));
  }
  mPanel.appendChild(loopEngineSection(s));
  summary.appendChild(mPanel);

  const va=gd.view_accuracy, edges=(gd.view_edge_candidates||[]);
  summary.appendChild(proseCard('Edge & learning',[
    "Grok direction accuracy <b>"+(va==null?'—':f(va*100,0)+'%')+"</b> <span class='neu'>(50% = coin flip)</span>",
    'Winning setups: <b>'+(edges.length?edges.slice(0,3).map(e=>e.dimension+'='+e.bucket).join(', '):'still collecting data')+'</b>',
    'Lessons stored: <b>'+((s.lessons||{}).count||0)+'</b>'
  ]));

  const cb=gd.circuit_breaker||{};
  const balanced=((s.reconciliation||{}).global_reconciled!==false);
  summary.appendChild(proseCard('Safety',[
    'Circuit breaker: <b class="'+(cb.tripped?'neg':'pos')+'">'+(cb.tripped?(cb.reason||'tripped'):'OK')+'</b>',
    'Daily loss cap $'+f(cb.daily_loss_cap_usd,0)+' · used $'+f(cb.daily_follow_loss_usd,2),
    'Books reconciled: <b class="'+(balanced?'pos':'neg')+'">'+(balanced?'Yes':'No')+'</b>'
  ]));

  const tv=s.tradingview||{};
  const tvActive=tv.enabled||(tv.tradingview_alerts_valid>0);
  if(tvActive){
    const mtf=tv.tradingview_mtf_confirmation||{};
    const byTf=tv.tradingview_latest_by_timeframe||{};
    const featSym=tv.tradingview_feature_symbol||'BTCUSD';
    const tfs=(tv.tradingview_mtf_timeframes||mtf.mtf_timeframes||['2','3','4']);
    const mtfN=mtf.mtf_count||tfs.length;
    const mtfVerdict=mtf['confirm_'+mtfN+'tf']||mtf.confirm_mtf||mtf.confirm_3tf||mtf.confirm||'none';
    const mtfCls=(mtfVerdict.includes('confirmed')?'pos':(mtfVerdict.includes('conflict')?'neg':'neu'));
    const tvPanel=$('<div class="panel" style="grid-column:1/-1"><h2>BTC trend · TradingView alerts</h2></div>');
    const tb=$('<table class="market-table"><thead><tr><th>Chart</th><th>Direction</th><th>Strength</th><th>Age</th></tr></thead><tbody></tbody></table>');
    tfs.forEach((tf)=>{
      const label=tf+'m';
      const snap=byTf[featSym+'@'+tf]||{};
      const freshDir=mtf['tf_'+tf+'m_dir'];
      const storedDir=snap.direction||null;
      const dir=freshDir||storedDir;
      const stale=freshDir==null&&storedDir!=null;
      const dirCls=dir==='UP'?'pos':(dir==='DOWN'?'neg':'neu');
      const age=mtf['tf_'+tf+'m_age_s'];
      tb.querySelector('tbody').appendChild($(`<tr>
        <td>${label}</td>
        <td class="${dirCls}">${dir||'—'}${stale?' <span class="neu">(stale)</span>':''}</td>
        <td>${snap.strength==null?'—':f(snap.strength,2)}</td>
        <td class="neu">${age==null?'—':f(age,0)+'s'}</td>
      </tr>`));
    });
    tvPanel.appendChild(tb);
    const foot=$('<div class="money-sub" style="margin-top:12px"></div>');
    const mtfGate=tv.mtf_gate||{};
    foot.innerHTML=mtfN+'-TF trend: <b class="'+mtfCls+'">'+mtfVerdict+'</b> · '
      +(mtf.trend_fresh_count==null?'—':mtf.trend_fresh_count)+'/'+mtfN+' fresh · '
      +(tv.tradingview_alerts_valid||0)+' alerts · trade gate <b class="pos">'
      +(mtfGate.enabled?'on':'off (observe-only)')+'</b>';
    tvPanel.appendChild(foot);
    summary.appendChild(tvPanel);
  }

  const tech=document.getElementById('tech');tech.innerHTML='';
  const o=s.oracle||{},c=s.calibration||{},p=s.price||{},eg=s.execution_gate||{};
  const lf=(o.lead_features||{}).feeds||{},rt=o.rtds||{},rec=L.proxy_official_reconciliation||{};
  tech.appendChild(kvCard('Ledger',[
    ['Trades',L.trades],['Settled',L.settled],['Wins',L.wins],
    ['Win rate',f((L.win_rate||0)*100,1)+'%'],['Avg PnL',money(L.avg_pnl_per_trade)],
    ['Open',L.open_positions]
  ]));
  tech.appendChild(kvCard('Oracle & price',[
    ['Feed',o.oracle_feed_type||'—'],['Source',p.source||'—'],
    ['Chainlink',f(rt.latest&&rt.latest['crypto_prices_chainlink:btc/usd'])],
    ['σ/sec',f(p.sigma_per_sec,6)],['RTDS',rt.connected?'connected':'off',rt.connected?'pos':'neg']
  ]));
  tech.appendChild(kvCard('Execution gate',[
    ['Candidates',eg.candidates],['Fills',eg.accepted,'pos'],['Rejected',eg.rejected_total,'neg'],
    ['Reconciled',eg.reconciled?'yes':'no',eg.reconciled?'pos':'neg']
  ]));
  const sg=s.learned_selectivity_gate||{};
  const mtfG2=(s.tradingview||{}).mtf_gate||{};
  tech.appendChild(kvCard('Gates',[
    ['Green path',cohort.green_path_enabled?'on':'off',cohort.green_path_enabled?'pos':'neu'],
    ['TV MTF gate',mtfG2.enabled?'on':'off (observe)',mtfG2.enabled?'neg':'pos'],
    ['Cohort blocks',cohort.blocked||0,(cohort.blocked>0?'neg':'neu')],
    ['Selectivity rejects',sg.rejected||0,(sg.rejected>0?'neg':'neu')],
    ['15m TTC band',cohort['15m_ttc_band_s']?cohort['15m_ttc_band_s'][0]+'-'+cohort['15m_ttc_band_s'][1]+'s':'—'],
    ['Coupling OK',coupling.configured_ok==null?'—':(coupling.configured_ok?'yes':'no'),
      coupling.configured_ok?'pos':'neg'],
    ['Brier',f(c.brier,3)],['Calib samples',c.samples||0]
  ]));
  if(gd.enabled){
    const cb2=gd.circuit_breaker||{};
    tech.appendChild(kvCard('Grok decider',[
      ['Mode',gd.mode||'off'],['Decided',gd.decided],['Direction acc',gd.direction_accuracy==null?'—':f(gd.direction_accuracy*100,1)+'%'],
      ['Abstains',gd.abstains],['Breaker',cb2.tripped?'tripped':'ok',cb2.tripped?'neg':'pos']
    ]));
  }
  const ar=s.arbitrage||{};
  if(ar&&ar.risk_free){
    tech.appendChild(kvCard('Arbitrage',[
      ['Executed',ar.executed||0],['Settled',ar.settled||0],
      ['Profit',money(ar.realized_profit_usd),pnlCls(ar.realized_profit_usd)]
    ]));
  }

  }catch(e){
    setHealth('Render error','off');
  }
}
tick();setInterval(tick,5000);
</script>
</body>
</html>"""