const $=q=>document.querySelector(q), fmt=new Intl.NumberFormat('en-US',{maximumFractionDigits:2});
const finite=Number.isFinite;
const money=v=>finite(v)?`$${fmt.format(v)}`:'∞';
const price=(u,p)=> (u*p).toFixed(Math.max(0,String(p).split('.')[1]?.length||0));

function metricRows(m={},mc={}){
  const rows=[
    ['ENTRY',m.total_entry??0,''],['WR',`${fmt.format(m.wr_pct||0)}%`,'positive'],['PF NET',finite(m.pf_net)?fmt.format(m.pf_net):'∞','positive'],
    ['NET P/L',money(m.net_profit_usd),(m.net_profit_usd||0)>=0?'positive':'negative'],['EV / TRD',money(m.ev_per_trade_usd),(m.ev_per_trade_usd||0)>=0?'positive':'negative'],
    ['AVG WIN',money(m.avg_win_usd),'positive'],['AVG LOSS',money(m.avg_loss_usd),'negative'],['MAX DD',`${money(m.max_dd_usd)} · ${fmt.format(m.max_dd_pct||0)}%`,'negative'],
    ['RECOVERY',finite(m.recovery_factor)?fmt.format(m.recovery_factor):'∞',''],['MAX CONSEC. LOSS',m.max_consecutive_loss??0,'negative'],['SQN',fmt.format(m.sqn||0),'gold'],
    ['MC PASS',`${fmt.format(mc.pass_rate_pct||0)}%`,'positive'],['MC 95% DD',`${fmt.format(mc.dd95_pct||0)}%`,'positive'],['POSITIVE YEAR',m.positive_year??0,''],
    ['WORST YEAR',money(m.worst_year_usd),(m.worst_year_usd||0)>=0?'positive':'negative']
  ];
  $('#metrics').innerHTML=rows.map(([k,v,c])=>`<div class="metric ${c}"><span>${k}</span><span>${v}</span></div>`).join('');
  $('#mobilePF').textContent=finite(m.pf_net)?fmt.format(m.pf_net):'∞'; $('#mobileWR').textContent=`${fmt.format(m.wr_pct||0)}%`; $('#mobileDD').textContent=money(m.max_dd_usd||0);
}

function draw(payload){
  const c=$('#chart'),ctx=c.getContext('2d'),r=c.getBoundingClientRect(),dpr=devicePixelRatio||1,W=r.width,H=r.height;
  c.width=Math.max(1,Math.round(W*dpr)); c.height=Math.max(1,Math.round(H*dpr)); ctx.setTransform(dpr,0,0,dpr,0,0); ctx.fillStyle='#0d0d0d'; ctx.fillRect(0,0,W,H);
  const all=payload.bricks||[]; if(!all.length){ctx.fillStyle='#77776f';ctx.font='12px system-ui';ctx.fillText('No bricks',18,28);return}
  const L=18,R=18,T=18,B=26,aw=W-L-R,ah=H-T-B,n=Math.max(1,Math.floor(aw/8)),data=all.slice(Math.max(0,all.length-n));
  let vals=data.flatMap(b=>[b.open_units,b.close_units]),min=Math.min(...vals),max=Math.max(...vals); if(min===max){min--;max++}
  const step=aw/Math.max(data.length,1),bw=Math.max(6,Math.min(20,step*.72)),y=v=>T+(max-v)/(max-min)*ah;
  ctx.strokeStyle='#1d1d1d';ctx.lineWidth=1;
  for(let i=0;i<=5;i++){let yy=T+i*ah/5;ctx.beginPath();ctx.moveTo(L,yy+.5);ctx.lineTo(W-R,yy+.5);ctx.stroke()}
  for(let i=0;i<=8;i++){let xx=L+i*aw/8;ctx.beginPath();ctx.moveTo(xx+.5,T);ctx.lineTo(xx+.5,H-B);ctx.stroke()}
  data.forEach((b,i)=>{let x=L+i*step+(step-bw)/2,yo=y(b.open_units),yc=y(b.close_units),yy=Math.min(yo,yc),hh=Math.max(3,Math.abs(yc-yo));ctx.fillStyle=b.direction>0?'#62d77c':'#ff6762';ctx.fillRect(x,yy,bw,hh);if(b.is_reversal){ctx.strokeStyle='#f0c94b';ctx.strokeRect(x-.5,yy-.5,bw+1,hh+1)}});
  ctx.fillStyle='#707069';ctx.font='9px system-ui';ctx.fillText(`brick_id ${data[0]?.brick_id??0}`,L,H-9);ctx.textAlign='right';ctx.fillText(`brick_id ${data.at(-1)?.brick_id??0}`,W-R,H-9);ctx.textAlign='left';
}

function renderTrades(payload){
  const p=Number(payload.meta?.price_unit||.01);
  $('#tradeRows').innerHTML=(payload.trades||[]).slice(-20).map((t,i)=>`<tr><td>${i+1}</td><td class="${t.side>0?'buy':'sell'}">${t.side>0?'BUY':'SELL'}</td><td>${t.signal_tick_id}</td><td>${t.entry_tick_id}</td><td>${t.exit_tick_id}</td><td>${price(t.entry_units,p)}</td><td>${price(t.exit_units,p)}</td><td>${t.exit_reason}</td><td class="${t.pnl_usd>=0?'profit':'loss'}">${fmt.format(t.pnl_usd)}</td></tr>`).join('');
}
function badge(text,ok=false){$('#modeBadge').innerHTML=`<span class="status-dot ${ok?'online':''}"></span><span>${text}</span>`}
function render(payload){
  const m=payload.meta||{}; if(!document.body.classList.contains('local-mode')) badge(m.mode==='SYNTHETIC_DEMO'?'DEMO VIEWER':'PUBLIC VIEWER');
  $('#chartMeta').textContent=`${m.symbol||'XAUUSD'} · ${m.mode==='SYNTHETIC_DEMO'?'DEMO':'TOTAL HISTORY'} · brick ${m.brick_size_price??m.brick_size_units??'?'} · brick_id axis`;
  $('#warning').textContent=m.note||'Production results must come from audited raw tick history.'; metricRows(payload.metrics,payload.monte_carlo); renderTrades(payload); window._payload=payload; draw(payload);
}
async function loadDefault(){let r=await fetch('data/sample.json',{cache:'no-store'});if(!r.ok)throw Error(`sample load ${r.status}`);render(await r.json())}
$('#fileInput').addEventListener('change',async e=>{let f=e.target.files?.[0];if(f)render(JSON.parse(await f.text()))}); addEventListener('resize',()=>window._payload&&draw(window._payload));

async function api(path,method='GET',body){let r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null,cache:'no-store'}),j=await r.json();if(!r.ok||j.ok===false)throw Error(j.error||`HTTP ${r.status}`);return j}
const job=j=>!j?'Not started':`${j.status||'?'}${j.returncode!=null?` · rc=${j.returncode}`:''}`;
function state(el,txt){if(!el)return;el.textContent=txt;el.classList.remove('ok-text','bad-text','run-text');if(/pass|ready|online|ok/i.test(txt))el.classList.add('ok-text');else if(/fail|missing|error/i.test(txt))el.classList.add('bad-text');else if(/running/i.test(txt))el.classList.add('run-text')}
async function refresh(){
  try{let s=await api('/api/status'),ok=!!(s.python?.ok&&s.node?.ok&&s.npm?.ok&&s.dukascopy_node?.ok);state($('#stackStatus'),ok?'READY':'STACK NEEDS PREPARE');state($('#smokeStatus'),job(s.jobs?.xauusd_smoke));state($('#historyStatus'),`${job(s.jobs?.xauusd_total_history)} · ${s.raw_manifest_days||0} days`);state($('#backtestStatus'),job(s.jobs?.backtest_latest));$('#localLog').textContent=`SERVER ${s.server}  •  RAW DAYS ${s.raw_manifest_days||0}  •  LATEST RESULT ${s.latest_result?.ok?'READY':'—'}  •  UPDATED ${s.updated_at}`;badge(ok?'STACK READY':'LOCAL ENGINE',ok);if(s.latest_result?.ok){let r=await fetch('data/latest.json',{cache:'no-store'});if(r.ok)render(await r.json())}}
  catch(e){state($('#stackStatus'),'LOCAL SERVER ERROR');$('#localLog').textContent=String(e);badge('LOCAL ERROR')}
}
async function launch(btn,path,body={}){let old=btn.textContent;btn.disabled=true;btn.textContent='STARTING…';try{await api(path,'POST',body);await refresh()}catch(e){alert(String(e))}finally{btn.disabled=false;btn.textContent=old}}

const local=['127.0.0.1','localhost','::1'].includes(location.hostname);
if(local){
  document.body.classList.add('local-mode'); $('#refreshStatus').onclick=refresh; $('#prepareBtn').onclick=e=>launch(e.currentTarget,'/api/prepare'); $('#smokeBtn').onclick=e=>launch(e.currentTarget,'/api/smoke',{date:'2026-09-01'}); $('#historyBtn').onclick=e=>launch(e.currentTarget,'/api/full-history'); $('#backtestBtn').onclick=e=>launch(e.currentTarget,'/api/backtest',{brick:+$('#brickInput').value,sl:+$('#slInput').value,tp:+$('#tpInput').value,qty:100}); setInterval(refresh,5000); refresh();
}else{
  document.body.classList.add('public-mode'); ['prepareBtn','smokeBtn','historyBtn','backtestBtn','brickInput','slInput','tpInput'].forEach(id=>$('#'+id).disabled=true); ['stackStatus','smokeStatus','historyStatus','backtestStatus'].forEach(id=>state($('#'+id),'LOCAL ONLY')); $('#localLog').textContent='GITHUB PUBLIC VIEWER  •  LOCAL ENGINE COMMANDS REMAIN AVAILABLE IN THIS REPOSITORY ON 127.0.0.1:5173'; badge('PUBLIC VIEWER');
}
loadDefault().catch(e=>{badge('LOAD ERROR');$('#warning').textContent=String(e)});
