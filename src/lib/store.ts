type Listener = (id: string, source: string) => void;

const listeners = new Set<Listener>();
let current = 'somali';

export const store = {
  get region() {
    return current;
  },
  select(id: string, source = 'ui') {
    if (!id) return;
    current = id;
    try {
      history.replaceState(null, '', `#region=${id}`);
    } catch {}
    listeners.forEach((fn) => fn(id, source));
    window.dispatchEvent(new CustomEvent('zinab:region', { detail: { id, source } }));
  },
  subscribe(fn: Listener) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  boot(defaultId: string) {
    const match = location.hash.match(/region=([a-z-]+)/);
    current = match ? match[1] : defaultId;
    return current;
  },
};
