const $ = q => document.querySelector(q);
const fmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const finite = Number.isFinite;
const PRICE_UNIT = 0.01;
const LIVE_SYMBOL = 'XAUUSD';
const LIVE_BRICK_UNITS = 25;
const LIVE_HISTORY_URL = 'https://biquote.io/api/XAUUSD/history?count=1000';
const LIVE_TICK_URL = 'https://biquote.io/api/XAUUSD';
const LIVE_HUB_URL = 'https://biquote.io/hubs/tick';

let resultPayload = null;
let chartMode = 'live';
let liveEngine = null;
let liveConnection = null;
let livePollingTimer = null;
let liveTickSeq = 0;
let liveLastTick = null;
let liveStarted = false;

const money = v => finite(v) ? `$${fmt.format(v)}` : '∞';
const price = (u, p) => (u * p).toFixed(Math.max(0, String(p).split('.')[1]?.length || 0));
const px = v => finite(Number(v)) ? Number(v).toFixed(2) : '—';

function setModeButtons() {
  document.querySelectorAll('[data-chart-mode]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.chartMode === chartMode);
  });
}

function setMobileLabels(a, b, c) {
  $('#mobileStat1Label').textContent = a;
  $('#mobileStat2Label').textContent = b;
  $('#mobileStat3Label').textContent = c;
}

function metricRows(m = {}, mc = {}) {
  $('#metricsTitle').textContent = 'PERFORMANCE';
  $('#metricsSubtitle').textContent = 'RAW BID/ASK REPLAY';
  const rows = [
    ['ENTRY', m.total_entry ?? 0, ''],
    ['WR', `${fmt.format(m.wr_pct || 0)}%`, 'positive'],
    ['PF NET', finite(m.pf_net) ? fmt.format(m.pf_net) : '∞', 'positive'],
    ['NET P/L', money(m.net_profit_usd), (m.net_profit_usd || 0) >= 0 ? 'positive' : 'negative'],
    ['EV / TRD', money(m.ev_per_trade_usd), (m.ev_per_trade_usd || 0) >= 0 ? 'positive' : 'negative'],
    ['AVG WIN', money(m.avg_win_usd), 'positive'],
    ['AVG LOSS', money(m.avg_loss_usd), 'negative'],
    ['MAX DD', `${money(m.max_dd_usd)} · ${fmt.format(m.max_dd_pct || 0)}%`, 'negative'],
    ['RECOVERY', finite(m.recovery_factor) ? fmt.format(m.recovery_factor) : '∞', ''],
    ['MAX CONSEC. LOSS', m.max_consecutive_loss ?? 0, 'negative'],
    ['SQN', fmt.format(m.sqn || 0), 'gold'],
    ['MC PASS', `${fmt.format(mc.pass_rate_pct || 0)}%`, 'positive'],
    ['MC 95% DD', `${fmt.format(mc.dd95_pct || 0)}%`, 'positive'],
    ['POSITIVE YEAR', m.positive_year ?? 0, ''],
    ['WORST YEAR', money(m.worst_year_usd), (m.worst_year_usd || 0) >= 0 ? 'positive' : 'negative']
  ];
  $('#metrics').innerHTML = rows.map(([k, v, c]) => `<div class="metric ${c}"><span>${k}</span><span>${v}</span></div>`).join('');
  setMobileLabels('PF', 'WR', 'DD');
  $('#mobilePF').textContent = finite(m.pf_net) ? fmt.format(m.pf_net) : '∞';
  $('#mobileWR').textContent = `${fmt.format(m.wr_pct || 0)}%`;
  $('#mobileDD').textContent = money(m.max_dd_usd || 0);
}

function liveMetricRows() {
  const t = liveLastTick || {};
  const bid = Number(t.bid);
  const ask = Number(t.ask);
  const mid = finite(Number(t.mid)) ? Number(t.mid) : (finite(bid) && finite(ask) ? (bid + ask) / 2 : NaN);
  const spread = finite(bid) && finite(ask) ? ask - bid : NaN;
  const bricks = liveEngine?.bricks?.length || 0;
  const ticks = liveEngine?.tickCount || 0;
  const lastTime = t.time ? new Date(t.time) : null;
  const age = lastTime && !Number.isNaN(lastTime.getTime()) ? Math.max(0, Math.round((Date.now() - lastTime.getTime()) / 1000)) : null;
  const market = String(t.marketState || 'open').toUpperCase();
  $('#metricsTitle').textContent = 'LIVE MARKET';
  $('#metricsSubtitle').textContent = 'REAL-TIME BID / ASK FEED';
  const rows = [
    ['BID', finite(bid) ? bid.toFixed(2) : '—', 'positive'],
    ['ASK', finite(ask) ? ask.toFixed(2) : '—', 'negative'],
    ['MID', finite(mid) ? mid.toFixed(2) : '—', 'gold'],
    ['SPREAD', finite(spread) ? spread.toFixed(2) : '—', ''],
    ['BRICK', `$${(liveEngine?.brickSizeUnits || 100) * PRICE_UNIT}`, 'gold'],
    ['BRICKS', bricks, ''],
    ['TICKS', ticks, ''],
    ['FEED', t.source || 'MT5', ''],
    ['MARKET', market, market === 'OPEN' ? 'positive' : ''],
    ['AGE', age == null ? '—' : `${age}s`, age != null && age <= 5 ? 'positive' : ''],
  ];
  $('#metrics').innerHTML = rows.map(([k, v, c]) => `<div class="metric ${c}"><span>${k}</span><span>${v}</span></div>`).join('');
  setMobileLabels('BID', 'ASK', 'BRICKS');
  $('#mobilePF').textContent = finite(bid) ? bid.toFixed(2) : '—';
  $('#mobileWR').textContent = finite(ask) ? ask.toFixed(2) : '—';
  $('#mobileDD').textContent = String(bricks);
}

function draw(payload) {
  const c = $('#chart'), ctx = c.getContext('2d'), r = c.getBoundingClientRect(), dpr = devicePixelRatio || 1, W = r.width, H = r.height;
  c.width = Math.max(1, Math.round(W * dpr));
  c.height = Math.max(1, Math.round(H * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = '#0d0d0d';
  ctx.fillRect(0, 0, W, H);
  const all = payload?.bricks || [];
  if (!all.length) {
    ctx.fillStyle = '#77776f';
    ctx.font = '12px system-ui';
    ctx.fillText(chartMode === 'live' ? 'Waiting for live XAUUSD Renko bricks…' : 'No bricks', 18, 28);
    return;
  }
  const L = 18, R = 18, T = 18, B = 26, aw = W - L - R, ah = H - T - B;
  const n = Math.max(1, Math.floor(aw / 8));
  const data = all.slice(Math.max(0, all.length - n));
  let vals = data.flatMap(b => [b.open_units, b.close_units]), min = Math.min(...vals), max = Math.max(...vals);
  if (min === max) { min--; max++; }
  const step = aw / Math.max(data.length, 1), bw = Math.max(6, Math.min(20, step * .72)), y = v => T + (max - v) / (max - min) * ah;
  ctx.strokeStyle = '#1d1d1d'; ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) { const yy = T + i * ah / 5; ctx.beginPath(); ctx.moveTo(L, yy + .5); ctx.lineTo(W - R, yy + .5); ctx.stroke(); }
  for (let i = 0; i <= 8; i++) { const xx = L + i * aw / 8; ctx.beginPath(); ctx.moveTo(xx + .5, T); ctx.lineTo(xx + .5, H - B); ctx.stroke(); }
  data.forEach((b, i) => {
    const x = L + i * step + (step - bw) / 2, yo = y(b.open_units), yc = y(b.close_units), yy = Math.min(yo, yc), hh = Math.max(3, Math.abs(yc - yo));
    ctx.fillStyle = b.direction > 0 ? '#62d77c' : '#ff6762';
    ctx.fillRect(x, yy, bw, hh);
    if (b.is_reversal) { ctx.strokeStyle = '#f0c94b'; ctx.strokeRect(x - .5, yy - .5, bw + 1, hh + 1); }
  });
  ctx.fillStyle = '#707069'; ctx.font = '9px system-ui';
  ctx.fillText(`brick_id ${data[0]?.brick_id ?? 0}`, L, H - 9);
  ctx.textAlign = 'right'; ctx.fillText(`brick_id ${data.at(-1)?.brick_id ?? 0}`, W - R, H - 9); ctx.textAlign = 'left';
}

function renderTrades(payload) {
  const p = Number(payload.meta?.price_unit || .01);
  $('#tradeRows').innerHTML = (payload.trades || []).slice(-20).map((t, i) => `<tr><td>${i + 1}</td><td class="${t.side > 0 ? 'buy' : 'sell'}">${t.side > 0 ? 'BUY' : 'SELL'}</td><td>${t.signal_tick_id}</td><td>${t.entry_tick_id}</td><td>${t.exit_tick_id}</td><td>${price(t.entry_units, p)}</td><td>${price(t.exit_units, p)}</td><td>${t.exit_reason}</td><td class="${t.pnl_usd >= 0 ? 'profit' : 'loss'}">${fmt.format(t.pnl_usd)}</td></tr>`).join('');
}

function badge(text, ok = false) { $('#modeBadge').innerHTML = `<span class="status-dot ${ok ? 'online' : ''}"></span><span>${text}</span>`; }

function renderResult(payload) {
  resultPayload = payload;
  if (chartMode !== 'result') return;
  const m = payload.meta || {};
  badge(m.mode === 'SYNTHETIC_DEMO' ? 'DEMO RESULT' : 'RESULT');
  $('#chartMeta').textContent = `${m.symbol || 'XAUUSD'} · ${m.mode === 'SYNTHETIC_DEMO' ? 'DEMO' : 'TOTAL HISTORY'} · brick ${m.brick_size_price ?? m.brick_size_units ?? '?'} · brick_id axis`;
  $('#liveQuote').textContent = 'RESULT MODE';
  $('#warning').textContent = m.note || 'Production results must come from audited raw tick history.';
  metricRows(payload.metrics, payload.monte_carlo);
  renderTrades(payload);
  window._payload = payload;
  draw(payload);
}

class LiveRenkoEngine {
  constructor(brickSizeUnits = 100) { this.reset(brickSizeUnits); }
  reset(brickSizeUnits = 100) {
    this.brickSizeUnits = Math.max(1, Number(brickSizeUnits) || 100);
    this.anchor = null;
    this.lastClose = null;
    this.direction = 0;
    this.bricks = [];
    this.tickCount = 0;
  }
  emit(openUnits, closeUnits, tick, isReversal) {
    const direction = closeUnits > openUnits ? 1 : -1;
    this.bricks.push({
      brick_id: this.bricks.length,
      open_units: openUnits,
      high_units: Math.max(openUnits, closeUnits),
      low_units: Math.min(openUnits, closeUnits),
      close_units: closeUnits,
      direction,
      is_reversal: !!isReversal,
      source_tick_close: tick.tick_id,
      source_timestamp_close: tick.timestamp_ms
    });
    this.lastClose = closeUnits;
    this.direction = direction;
  }
  process(tick) {
    this.tickCount++;
    const p = Math.floor((tick.bid_units + tick.ask_units) / 2);
    const b = this.brickSizeUnits;
    if (this.anchor == null) {
      this.anchor = Math.floor(p / b) * b;
      this.lastClose = this.anchor;
    }
    if (this.direction === 0) {
      if (p >= this.lastClose + b) while (p >= this.lastClose + b) this.emit(this.lastClose, this.lastClose + b, tick, false);
      else if (p <= this.lastClose - b) while (p <= this.lastClose - b) this.emit(this.lastClose, this.lastClose - b, tick, false);
      return;
    }
    if (this.direction > 0) {
      while (p >= this.lastClose + b) this.emit(this.lastClose, this.lastClose + b, tick, false);
      if (p <= this.lastClose - 2 * b) {
        const old = this.lastClose;
        this.emit(old - b, old - 2 * b, tick, true);
        while (p <= this.lastClose - b) this.emit(this.lastClose, this.lastClose - b, tick, false);
      }
      return;
    }
    while (p <= this.lastClose - b) this.emit(this.lastClose, this.lastClose - b, tick, false);
    if (p >= this.lastClose + 2 * b) {
      const old = this.lastClose;
      this.emit(old + b, old + 2 * b, tick, true);
      while (p >= this.lastClose + b) this.emit(this.lastClose, this.lastClose + b, tick, false);
    }
  }
  payload() { return { meta: { symbol: LIVE_SYMBOL, mode: 'LIVE', price_unit: PRICE_UNIT, brick_size_units: this.brickSizeUnits, brick_size_price: this.brickSizeUnits * PRICE_UNIT }, bricks: this.bricks }; }
}

function decimalToUnits(value) { return Math.round(Number(value) / PRICE_UNIT); }
function tickTimeMs(t) {
  const raw = t.time || t.timestamp || t.datetime || Date.now();
  const n = Number(raw);
  if (finite(n)) return n > 1e12 ? Math.round(n) : Math.round(n * 1000);
  const parsed = Date.parse(raw);
  return Number.isNaN(parsed) ? Date.now() : parsed;
}
function normalizeTick(t) {
  const bid = Number(t.bid ?? t.bidPrice);
  const ask = Number(t.ask ?? t.askPrice);
  if (!finite(bid) || !finite(ask) || ask < bid) return null;
  const timestamp_ms = tickTimeMs(t);
  return { tick_id: liveTickSeq++, timestamp_ms, bid_units: decimalToUnits(bid), ask_units: decimalToUnits(ask), raw: t };
}

function renderLive() {
  if (chartMode !== 'live') return;
  const t = liveLastTick || {};
  const bid = Number(t.bid), ask = Number(t.ask);
  const market = String(t.marketState || 'open').toLowerCase();
  const isOpen = market !== 'closed';
  badge(isOpen ? 'LIVE XAUUSD' : 'MARKET CLOSED', isOpen);
  $('#liveQuote').textContent = finite(bid) && finite(ask) ? `BID ${bid.toFixed(2)} · ASK ${ask.toFixed(2)}` : 'CONNECTING…';
  $('#chartMeta').textContent = `REAL-TIME · ${t.source || 'MT5'} · brick $${((liveEngine?.brickSizeUnits || 100) * PRICE_UNIT).toFixed(2)} · brick_id axis`;
  $('#warning').textContent = 'Live chart uses current XAUUSD BID/ASK market data. Research/backtest results remain separate and continue to use the repository research pipeline.';
  liveMetricRows();
  window._payload = liveEngine?.payload() || { bricks: [] };
  draw(window._payload);
}

function ingestLiveTick(raw) {
  const tick = normalizeTick(raw);
  if (!tick) return;
  liveLastTick = raw;
  liveEngine.process(tick);
  renderLive();
}

async function seedLiveHistory() {
  const r = await fetch(LIVE_HISTORY_URL, { cache: 'no-store' });
  if (!r.ok) throw new Error(`history ${r.status}`);
  const j = await r.json();
  let ticks = Array.isArray(j) ? j : (j.ticks || j.data || j.items || []);
  ticks = ticks.slice().sort((a, b) => tickTimeMs(a) - tickTimeMs(b));
  ticks.forEach(ingestLiveTick);
}

function startPollingFallback() {
  if (livePollingTimer) return;
  const poll = async () => {
    try {
      const r = await fetch(LIVE_TICK_URL, { cache: 'no-store' });
      if (r.ok) ingestLiveTick(await r.json());
    } catch (_) {}
  };
  poll();
  livePollingTimer = setInterval(poll, 2000);
}

async function connectLiveSignalR() {
  if (!window.signalR) throw new Error('SignalR unavailable');
  liveConnection = new signalR.HubConnectionBuilder().withUrl(LIVE_HUB_URL).withAutomaticReconnect([0, 2000, 5000, 10000]).build();
  liveConnection.on('ReceiveTick', t => { if (String(t.symbol || '').toUpperCase() === LIVE_SYMBOL) ingestLiveTick(t); });
  liveConnection.onreconnected(async () => { try { await liveConnection.invoke('Subscribe', [LIVE_SYMBOL]); } catch (_) {} });
  await liveConnection.start();
  await liveConnection.invoke('Subscribe', [LIVE_SYMBOL]);
}

async function startLiveRenko() {
  if (liveStarted) return;
  liveStarted = true;
  liveEngine = new LiveRenkoEngine(LIVE_BRICK_UNITS);
  try { await seedLiveHistory(); } catch (_) {}
  try { await connectLiveSignalR(); }
  catch (_) { startPollingFallback(); }
  renderLive();
}

function setChartMode(mode) {
  chartMode = mode === 'result' ? 'result' : 'live';
  setModeButtons();
  if (chartMode === 'live') renderLive();
  else if (resultPayload) renderResult(resultPayload);
}

document.querySelectorAll('[data-chart-mode]').forEach(btn => btn.addEventListener('click', () => setChartMode(btn.dataset.chartMode)));

async function loadDefault() {
  const r = await fetch('data/sample.json', { cache: 'no-store' });
  if (!r.ok) throw new Error(`sample load ${r.status}`);
  resultPayload = await r.json();
  renderTrades(resultPayload);
}

$('#fileInput').addEventListener('change', async e => {
  const f = e.target.files?.[0];
  if (!f) return;
  resultPayload = JSON.parse(await f.text());
  setChartMode('result');
});
addEventListener('resize', () => window._payload && draw(window._payload));

async function api(path, method = 'GET', body) {
  const r = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : null, cache: 'no-store' });
  const j = await r.json();
  if (!r.ok || j.ok === false) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}
const job = j => !j ? 'Not started' : `${j.status || '?'}${j.returncode != null ? ` · rc=${j.returncode}` : ''}`;
function state(el, txt) {
  if (!el) return;
  el.textContent = txt;
  el.classList.remove('ok-text', 'bad-text', 'run-text');
  if (/pass|ready|online|ok/i.test(txt)) el.classList.add('ok-text');
  else if (/fail|missing|error/i.test(txt)) el.classList.add('bad-text');
  else if (/running/i.test(txt)) el.classList.add('run-text');
}
async function refresh() {
  try {
    const s = await api('/api/status'), ok = !!(s.python?.ok && s.node?.ok && s.npm?.ok && s.dukascopy_node?.ok);
    state($('#stackStatus'), ok ? 'READY' : 'STACK NEEDS PREPARE');
    state($('#smokeStatus'), job(s.jobs?.xauusd_smoke));
    state($('#historyStatus'), `${job(s.jobs?.xauusd_total_history)} · ${s.raw_manifest_days || 0} days`);
    state($('#backtestStatus'), job(s.jobs?.backtest_latest));
    $('#localLog').textContent = `SERVER ${s.server}  •  RAW DAYS ${s.raw_manifest_days || 0}  •  LATEST RESULT ${s.latest_result?.ok ? 'READY' : '—'}  •  UPDATED ${s.updated_at}`;
    if (chartMode !== 'live') badge(ok ? 'STACK READY' : 'LOCAL ENGINE', ok);
    if (s.latest_result?.ok) { const r = await fetch('data/latest.json', { cache: 'no-store' }); if (r.ok) { resultPayload = await r.json(); if (chartMode === 'result') renderResult(resultPayload); } }
  } catch (e) {
    state($('#stackStatus'), 'LOCAL SERVER ERROR');
    $('#localLog').textContent = String(e);
  }
}
async function launch(btn, path, body = {}) {
  const old = btn.textContent; btn.disabled = true; btn.textContent = 'STARTING…';
  try { await api(path, 'POST', body); await refresh(); }
  catch (e) { alert(String(e)); }
  finally { btn.disabled = false; btn.textContent = old; }
}

const local = ['127.0.0.1', 'localhost', '::1'].includes(location.hostname);
if (local) {
  document.body.classList.add('local-mode');
  $('#refreshStatus').onclick = refresh;
  $('#prepareBtn').onclick = e => launch(e.currentTarget, '/api/prepare');
  $('#smokeBtn').onclick = e => launch(e.currentTarget, '/api/smoke', { date: '2026-09-01' });
  $('#historyBtn').onclick = e => launch(e.currentTarget, '/api/full-history');
  $('#backtestBtn').onclick = e => launch(e.currentTarget, '/api/backtest', { brick: +$('#brickInput').value, sl: +$('#slInput').value, tp: +$('#tpInput').value, qty: 100 });
  setInterval(refresh, 5000); refresh();
} else {
  document.body.classList.add('public-mode');
  ['prepareBtn', 'smokeBtn', 'historyBtn', 'backtestBtn', 'brickInput', 'slInput', 'tpInput'].forEach(id => $('#'+id).disabled = true);
  ['stackStatus', 'smokeStatus', 'historyStatus', 'backtestStatus'].forEach(id => state($('#'+id), 'LOCAL ONLY'));
  $('#localLog').textContent = 'GITHUB PUBLIC VIEWER  •  LIVE XAUUSD RENKO ACTIVE  •  LOCAL ENGINE COMMANDS REMAIN AVAILABLE ON 127.0.0.1:5173';
}

Promise.allSettled([loadDefault(), startLiveRenko()]).then(() => setChartMode('live'));
