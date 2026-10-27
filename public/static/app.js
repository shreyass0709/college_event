const $ = (s, r = document) => r.querySelector(s);
const mins = t => +t.slice(0, 2) * 60 + +t.slice(3, 5);
const hhmm = m => String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
const ymd = d => d.toLocaleDateString('en-CA');
const hm = d => d.toTimeString().slice(0, 5);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nice = day => new Date(day + 'T00:00').toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
const t12 = t => { const h = +t.slice(0, 2); return `${h % 12 || 12}:${t.slice(3, 5)} ${h < 12 ? 'AM' : 'PM'}`; };

const ICONS = { success: '✓', error: '!', info: 'i' };
function autoHide(el, ms) {
  const hide = () => { el.classList.add('out'); setTimeout(() => el.remove(), 400); };
  let t = setTimeout(hide, ms);
  el.onmouseenter = () => clearTimeout(t); el.onmouseleave = () => (t = setTimeout(hide, 2000));
  el.onclick = hide;
}
function toast(msg, type = 'info') {
  let box = $('.flashes');
  if (!box) { box = document.createElement('div'); box.className = 'flashes'; box.setAttribute('role', 'status'); document.body.append(box); }
  const el = document.createElement('div');
  el.className = 'flash ' + type;
  el.innerHTML = `<span class="ico">${ICONS[type] || 'i'}</span><span></span>`;
  el.lastChild.textContent = msg; box.append(el); autoHide(el, 4500);
}
// survive a reload: toastNext('Approved'); location.reload();
function toastNext(msg, type = 'success') { try { sessionStorage.setItem('toast', JSON.stringify([msg, type])); } catch {} }

async function api(url, body) {
  try {
    const r = await fetch(url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
    if (r.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); }
    const data = await r.json().catch(() => ({ error: 'Unexpected server response. Please try again.' }));
    return { ok: r.ok, status: r.status, data };
  } catch {
    return { ok: false, status: 0, data: { error: 'Network problem. Check your connection and try again.' } };
  }
}

/* Branded confirm dialog. Resolves to false (cancelled), true, or the typed text when `input` is set. */
function ask({ title, text = '', ok = 'Confirm', danger = false, input = null, icon = '?' }) {
  let d = $('#ask');
  if (!d) {
    d = document.createElement('dialog'); d.id = 'ask'; d.className = 'modal ask';
    d.innerHTML = `<form method="dialog"><div class="ask-ico"></div><h3></h3><p class="muted"></p>
      <textarea class="hidden" rows="3" maxlength="300"></textarea>
      <div class="ask-actions"><button class="btn btn-ghost" value="no" type="button">Go back</button><button class="btn" value="yes">OK</button></div></form>`;
    document.body.append(d);
    d.addEventListener('click', e => { if (e.target === d) d.close('no'); });
  }
  const [ico, h, p, ta] = ['.ask-ico', 'h3', 'p', 'textarea'].map(s => d.querySelector(s));
  const [no, yes] = d.querySelectorAll('.ask-actions button');
  ico.textContent = icon; ico.className = 'ask-ico' + (danger ? ' danger' : '');
  h.textContent = title; p.textContent = text;
  yes.textContent = ok; yes.className = 'btn ' + (danger ? 'btn-danger' : 'btn-navy');
  ta.classList.toggle('hidden', !input); ta.value = ''; ta.placeholder = input || ''; ta.required = !!input;
  return new Promise(res => {
    no.onclick = () => d.close('no');
    d.onclose = () => res(d.returnValue === 'yes' && (input ? ta.value.trim() : true));
    d.returnValue = ''; d.showModal(); (input ? ta : no).focus();
  });
}

// Approve / reject / cancel, shared by "My bookings", "Approvals" and the calendar.
async function act(id, action, btn) {
  let note = '';
  if (action === 'reject') {
    note = await ask({ title: 'Reject this request?', text: 'Tell the requester why. They will see this note.', ok: 'Reject request', danger: true, icon: '✕', input: 'e.g. Hall reserved for exams that day' });
    if (!note) return;
  } else if (action === 'cancel') {
    if (!await ask({ title: 'Cancel this booking?', text: 'The slot will be freed for others. This cannot be undone.', ok: 'Yes, cancel it', danger: true, icon: '!' })) return;
  } else if (action === 'approve') {
    if (!await ask({ title: 'Approve this request?', text: 'It will appear as confirmed on the common calendar.', ok: 'Approve', icon: '✓' })) return;
  }
  btn?.classList.add('loading');
  const { ok, data } = await api(`/api/bookings/${id}/status`, { action, note });
  btn?.classList.remove('loading');
  if (!ok) return toast(data.error, 'error');
  const msg = { approve: 'Request approved.', reject: 'Request rejected.', cancel: 'Booking cancelled.' }[action];
  const card = btn?.closest('.bitem');
  if (card) card.classList.add('gone');
  toastNext(msg); setTimeout(() => location.reload(), card ? 350 : 0);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach((el, i) => autoHide(el, 6000 + i * 300));
  try { const t = JSON.parse(sessionStorage.getItem('toast')); sessionStorage.removeItem('toast'); if (t) toast(...t); } catch {}

  // confirm before logging out (every logout link/button)
  document.querySelectorAll('a[href$="/logout"]').forEach(a => a.addEventListener('click', async e => {
    e.preventDefault();
    if (await ask({ title: 'Log out?', text: "You'll need your college email and password to sign in again.", ok: 'Log out', danger: true, icon: '↩' })) location.href = a.href;
  }));

  // <form data-confirm="Title|Text"> → ask first (e.g. disabling a venue)
  document.querySelectorAll('form[data-confirm]').forEach(f => f.addEventListener('submit', async e => {
    if (f.dataset.ok) return;
    e.preventDefault();
    const [title, text] = f.dataset.confirm.split('|');
    if (await ask({ title, text, ok: f.dataset.confirmOk || 'Confirm', danger: 'danger' in f.dataset, icon: '!' })) { f.dataset.ok = 1; f.requestSubmit(); }
  }));

  // spinner + no double submit on normal (server) forms
  document.querySelectorAll('form[method=post]').forEach(f => f.addEventListener('submit', e => {
    if (e.defaultPrevented) return;
    if (f.dataset.sending) return e.preventDefault();
    f.dataset.sending = 1; delete f.dataset.dirty;
    (e.submitter || f.querySelector('button:not([type=button])'))?.classList.add('loading');
  }));

  // warn before leaving a half-filled form
  document.querySelectorAll('form[data-guard]').forEach(f => f.addEventListener('input', () => (f.dataset.dirty = 1)));
  addEventListener('beforeunload', e => { if ($('form[data-dirty]')) e.preventDefault(); });

  // show / hide password
  document.querySelectorAll('input[type=password]').forEach(i => {
    const w = document.createElement('div'); w.className = 'pw'; i.before(w); w.append(i);
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'pw-eye'; b.setAttribute('aria-label', 'Show password'); b.textContent = 'Show';
    b.onclick = () => { const s = i.type === 'password'; i.type = s ? 'text' : 'password'; b.textContent = s ? 'Hide' : 'Show'; b.setAttribute('aria-label', (s ? 'Hide' : 'Show') + ' password'); };
    w.append(b);
  });

  // mobile drawer
  const dr = $('#drawer');
  if (dr) {
    const set = open => { document.body.classList.toggle('drawer-open', open); dr.setAttribute('aria-hidden', !open); $('#burger').setAttribute('aria-expanded', open); };
    $('#burger').onclick = () => set(!document.body.classList.contains('drawer-open'));
    dr.querySelector('.drawer-bg').onclick = () => set(false);
    addEventListener('keydown', e => { if (e.key === 'Escape') set(false); });
  }
  $('.tabs .on')?.scrollIntoView({ block: 'nearest', inline: 'center' });
});

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
