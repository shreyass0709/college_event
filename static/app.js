const $ = (s, r = document) => r.querySelector(s);
const mins = t => +t.slice(0, 2) * 60 + +t.slice(3, 5);
const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
const ymd = d => d.toLocaleDateString('en-CA');
const hm = d => d.toTimeString().slice(0, 5);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nice = day => new Date(day + 'T00:00').toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
const t12 = t => { const h = +t.slice(0, 2); return `${h % 12 || 12}:${t.slice(3, 5)} ${h < 12 ? 'AM' : 'PM'}`; };

function toast(msg, type = 'info') {
  let box = $('.flashes');
  if (!box) { box = document.createElement('div'); box.className = 'flashes'; document.body.append(box); }
  const el = document.createElement('div');
  el.className = 'flash ' + type; el.textContent = msg; box.append(el);
  setTimeout(() => el.classList.add('out'), 4500); setTimeout(() => el.remove(), 5000);
}
document.querySelectorAll('.flash').forEach((el, i) => {
  setTimeout(() => el.classList.add('out'), 6000 + i * 300); setTimeout(() => el.remove(), 6500 + i * 300);
});

async function api(url, body) {
  const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (r.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); }
  const data = await r.json().catch(() => ({ error: 'Unexpected server response.' }));
  return { ok: r.ok, status: r.status, data };
}

// Approve / reject / cancel, shared by "My bookings" and "Admin".
async function act(id, action) {
  let note = '';
  if (action === 'reject') { note = prompt('Reason for rejection (shown to the requester):'); if (note === null) return; }
  if (action === 'cancel' && !confirm('Cancel this booking? The slot will be freed for others.')) return;
  const { ok, data } = await api(`/api/bookings/${id}/status`, { action, note });
  if (ok) location.reload(); else toast(data.error, 'error');
}

// Day timeline 07:00–21:00: busy blocks + clickable free windows.
const OPEN = 420, CLOSE = 1260, pct = m => (m - OPEN) / (CLOSE - OPEN) * 100;
function timeline(v, onPick) {
  const w = document.createElement('div');
  w.className = 'tlw';
  let hours = '';
  for (let h = 7; h <= 21; h += 2) hours += `<span style="left:${pct(h * 60)}%">${h % 12 || 12}${h < 12 ? 'am' : 'pm'}</span>`;
  w.innerHTML = `<div class="tl-hours">${hours}</div><div class="tl"></div>`;
  const tl = w.lastChild;
  const place = (el, s, e) => { el.style.left = pct(mins(s)) + '%'; el.style.width = (pct(mins(e)) - pct(mins(s))) + '%'; };
  v.free.forEach(f => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tl-free'; b.title = `Free ${t12(f.start)} – ${t12(f.end)} · click to use`;
    b.setAttribute('aria-label', b.title);
    place(b, f.start, f.end); b.onclick = () => onPick(f); tl.append(b);
  });
  v.busy.forEach(x => {
    const d = document.createElement('div');
    d.className = 'tl-busy ' + x.status; d.style.background = v.color; d.textContent = x.title;
    d.title = `${x.title} · ${t12(x.start)} – ${t12(x.end)} (${x.status})`;
    place(d, x.start, x.end); tl.append(d);
  });
  return w;
}
