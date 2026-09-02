const $ = (q) => document.querySelector(q);
const fmt = new Intl.NumberFormat('en-US',{maximumFractionDigits:2});

function price(units, unit){ return (units * unit).toFixed(Math.max(0, String(unit).split('.')[1]?.length || 0)); }

function metricRows(m, mc){
  const rows = [
    ['Total Entry', m.total_entry],
    ['Win Rate', `${fmt.format(m.wr_pct)}%`],
    ['PF Net', Number.isFinite(m.pf_net)?fmt.format(m.pf_net):'∞'],
    ['Net Profit', `$${fmt.format(m.net_profit_usd)}`],
    ['EV / Trade', `$${fmt.format(m.ev_per_trade_usd)}`],
    ['Avg Win', `$${fmt.format(m.avg_win_usd)}`],
    ['Avg Loss', `$${fmt.format(m.avg_loss_usd)}`],
    ['Max DD', `$${fmt.format(m.max_dd_usd)} · ${fmt.format(m.max_dd_pct)}%`],
    ['Recovery Factor', Number.isFinite(m.recovery_factor)?fmt.format(m.recovery_factor):'∞'],
    ['Max Consecutive Loss', m.max_consecutive_loss],
    ['SQN', fmt.format(m.sqn)],
    ['Monte Carlo Pass', `${fmt.format(mc?.pass_rate_pct || 0)}%`],
    ['MC 95% DD', `${fmt.format(mc?.dd95_pct || 0)}%`],
    ['Positive Year', m.positive_year],
    ['Worst Year', `$${fmt.format(m.worst_year_usd)}`],
  ];
  $('#metrics').innerHTML = rows.map(([a,b]) => `<div class="metric"><span>${a}</span><span>${b}</span></div>`).join('');
}

function draw(payload){
  const c=$('#chart'), ctx=c.getContext('2d');
  const rect=c.getBoundingClientRect(); const dpr=window.devicePixelRatio||1;
  c.width=Math.round(rect.width*dpr); c.height=Math.round(rect.height*dpr); ctx.scale(dpr,dpr);
  const W=rect.width,H=rect.height; ctx.clearRect(0,0,W,H); ctx.fillStyle='#071018'; ctx.fillRect(0,0,W,H);
  const bricks=payload.bricks||[]; if(!bricks.length){ctx.fillStyle='#7e9caf';ctx.font='14px system-ui';ctx.fillText('No bricks',24,36);return;}
  const unit=Number(payload.meta?.price_unit||0.01);
  const vals=bricks.flatMap(b=>[b.open_units,b.close_units]); let min=Math.min(...vals),max=Math.max(...vals); if(min===max){min--;max++;}
  const pad=34, top=24,bottom=34; const availH=H-top-bottom; const bw=Math.max(3,Math.min(18,(W-pad*2)/Math.max(bricks.length,1)*0.72));
  const step=(W-pad*2)/Math.max(bricks.length,1); const y=v=>top+(max-v)/(max-min)*availH;
  ctx.strokeStyle='#102b3b';ctx.lineWidth=1;
  for(let i=0;i<=5;i++){const yy=top+i*availH/5;ctx.beginPath();ctx.moveTo(pad,yy);ctx.lineTo(W-pad,yy);ctx.stroke();ctx.fillStyle='#6d8a9d';ctx.font='10px system-ui';ctx.fillText(price(max-(max-min)*i/5,unit),4,yy+3)}
  bricks.forEach((b,i)=>{const x=pad+i*step+(step-bw)/2;const yo=y(b.open_units),yc=y(b.close_units);const yy=Math.min(yo,yc),hh=Math.max(2,Math.abs(yc-yo));ctx.fillStyle=b.direction>0?'#2fc98f':'#ef6c73';ctx.fillRect(x,yy,bw,hh);if(b.is_reversal){ctx.strokeStyle='#f1d17a';ctx.lineWidth=1;ctx.strokeRect(x-.5,yy-.5,bw+1,hh+1)}});
  ctx.fillStyle='#6d8a9d';ctx.font='10px system-ui';ctx.fillText(`brick_id 0`,pad,H-12);ctx.textAlign='right';ctx.fillText(`brick_id ${bricks.at(-1).brick_id}`,W-pad,H-12);ctx.textAlign='left';
}

function trades(payload){
  const unit=Number(payload.meta?.price_unit||0.01);
  $('#tradeRows').innerHTML=(payload.trades||[]).slice(-20).map((t,i)=>`<tr><td>${i+1}</td><td class="${t.side>0?'buy':'sell'}">${t.side>0?'BUY':'SELL'}</td><td>${t.signal_tick_id}</td><td>${t.entry_tick_id}</td><td>${t.exit_tick_id}</td><td>${price(t.entry_units,unit)}</td><td>${price(t.exit_units,unit)}</td><td>${t.exit_reason}</td><td class="${t.pnl_usd>=0?'profit':'loss'}">${fmt.format(t.pnl_usd)}</td></tr>`).join('');
}

function render(payload){
  const meta=payload.meta||{}; $('#modeBadge').textContent=meta.mode||'RESULT JSON';
  $('#chartMeta').textContent=`${meta.symbol||'XAUUSD'} · brick ${meta.brick_size_price ?? meta.brick_size_units ?? '?'} · ${payload.bricks?.length||0} bricks`;
  $('#warning').textContent=meta.note||'Production results must come from audited raw tick history; this UI never invents live performance.';
  metricRows(payload.metrics||{},payload.monte_carlo||{}); trades(payload); window._payload=payload; draw(payload);
}

async function loadDefault(){ const r=await fetch('data/sample.json',{cache:'no-store'}); if(!r.ok) throw new Error(`sample load ${r.status}`); render(await r.json()); }
$('#fileInput').addEventListener('change',async e=>{const f=e.target.files?.[0];if(!f)return;render(JSON.parse(await f.text()))});
window.addEventListener('resize',()=>window._payload&&draw(window._payload));
loadDefault().catch(err=>{$('#modeBadge').textContent='LOAD ERROR';$('#warning').textContent=String(err)});

async function api(path, method='GET', body=null){
  const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null,cache:'no-store'});
  const j=await r.json(); if(!r.ok||j.ok===false) throw new Error(j.error||`HTTP ${r.status}`); return j;
}
function jobText(j){ if(!j)return 'Not started'; return `${j.status||'?'}${j.returncode!=null?` · rc=${j.returncode}`:''}`; }
function paintState(el, txt){el.textContent=txt;el.classList.remove('ok-text','bad-text','run-text'); if(/pass|ready|online|ok/i.test(txt))el.classList.add('ok-text'); else if(/fail|missing|error/i.test(txt))el.classList.add('bad-text'); else if(/running/i.test(txt))el.classList.add('run-text');}
async function refreshLocalStatus(){
  try{
    const s=await api('/api/status');
    const stackOk=!!(s.python?.ok&&s.node?.ok&&s.npm?.ok&&s.dukascopy_node?.ok);
    paintState($('#stackStatus'), stackOk?'READY':`Python ${s.python?.ok?'OK':'FAIL'} · Node ${s.node?.ok?'OK':'FAIL'} · Dukascopy ${s.dukascopy_node?.ok?'OK':'MISSING'}`);
    paintState($('#smokeStatus'),jobText(s.jobs?.xauusd_smoke));
    paintState($('#historyStatus'),`${jobText(s.jobs?.xauusd_total_history)} · ${s.raw_manifest_days||0} day manifests`);
    paintState($('#backtestStatus'),jobText(s.jobs?.backtest_latest));
    $('#localLog').textContent=`SERVER ${s.server}\nROOT ${s.root}\nPY ${s.python?.path||'-'}\nNODE ${s.node?.path||'-'}\nNPM ${s.npm?.path||'-'}\nDUKASCOPY ${s.dukascopy_node?.path||'-'}\nRAW DAYS ${s.raw_manifest_days||0}\nUPDATED ${s.updated_at}`;
    if(s.latest_result?.ok){ try{const r=await fetch('data/latest.json',{cache:'no-store'});if(r.ok)render(await r.json())}catch(_){} }
  }catch(e){ paintState($('#stackStatus'),'LOCAL SERVER ERROR'); $('#localLog').textContent=String(e); }
}
async function launchAction(btn,path,body={}){const old=btn.textContent;btn.disabled=true;btn.textContent='Starting…';try{await api(path,'POST',body);await refreshLocalStatus()}catch(e){alert(String(e))}finally{btn.disabled=false;btn.textContent=old}}
const localControlMode = ['127.0.0.1','localhost','::1'].includes(location.hostname);
if(localControlMode){
  $('#refreshStatus')?.addEventListener('click',refreshLocalStatus);
  $('#prepareBtn')?.addEventListener('click',e=>launchAction(e.currentTarget,'/api/prepare'));
  $('#smokeBtn')?.addEventListener('click',e=>launchAction(e.currentTarget,'/api/smoke',{date:'2026-09-01'}));
  $('#historyBtn')?.addEventListener('click',e=>launchAction(e.currentTarget,'/api/full-history'));
  $('#backtestBtn')?.addEventListener('click',e=>launchAction(e.currentTarget,'/api/backtest',{brick:Number($('#brickInput').value),sl:Number($('#slInput').value),tp:Number($('#tpInput').value),qty:100}));
  setInterval(refreshLocalStatus,5000); refreshLocalStatus();
}else{
  document.querySelector('.control-panel')?.remove();
  const badge=$('#modeBadge');
  if(badge && badge.textContent==='LOADING') badge.textContent='PUBLIC VIEWER';
}
