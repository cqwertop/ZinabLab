export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

let observer: IntersectionObserver | null = null;

export function reveal(root: ParentNode = document) {
  if (!observer) {
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in');
            observer?.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    );
  }
  root.querySelectorAll('[data-reveal]:not(.is-in)').forEach((el) => observer!.observe(el));
}

export function countUp(el: HTMLElement, to: number, { decimals = 0, suffix = '', prefix = '', duration = 1400 } = {}) {
  if (reducedMotion() || !Number.isFinite(to)) {
    el.textContent = `${prefix}${Number.isFinite(to) ? to.toFixed(decimals) : '—'}${suffix}`;
    return;
  }
  const start = performance.now();
  const from = 0;
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 4);
    el.textContent = `${prefix}${(from + (to - from) * eased).toFixed(decimals)}${suffix}`;
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

let tip: HTMLDivElement | null = null;

export function initTooltips() {
  if (tip) return;
  tip = document.createElement('div');
  tip.className = 'zl-tip';
  tip.setAttribute('role', 'tooltip');
  document.body.appendChild(tip);
  const place = (x: number, y: number) => {
    if (!tip) return;
    const r = tip.getBoundingClientRect();
    let left = x + 16;
    let top = y + 16;
    if (left + r.width > window.innerWidth - 12) left = x - r.width - 16;
    if (top + r.height > window.innerHeight - 12) top = y - r.height - 16;
    tip.style.transform = `translate(${Math.max(8, left)}px, ${Math.max(8, top)}px)`;
  };
  document.addEventListener('pointermove', (e) => {
    const target = (e.target as Element)?.closest?.('[data-tip]') as HTMLElement | null;
    if (!target || !tip) {
      tip?.classList.remove('show');
      return;
    }
    tip.innerHTML = target.dataset.tip ?? '';
    tip.classList.add('show');
    place(e.clientX, e.clientY);
  });
  document.addEventListener('pointerleave', () => tip?.classList.remove('show'));
  document.addEventListener('scroll', () => tip?.classList.remove('show'), { passive: true });
}

export function showTip(html: string, x: number, y: number) {
  if (!tip) initTooltips();
  tip!.innerHTML = html;
  tip!.classList.add('show');
  const r = tip!.getBoundingClientRect();
  let left = x + 16;
  if (left + r.width > window.innerWidth - 12) left = x - r.width - 16;
  tip!.style.transform = `translate(${Math.max(8, left)}px, ${Math.max(8, y - r.height - 14)}px)`;
}

export function hideTip() {
  tip?.classList.remove('show');
}
