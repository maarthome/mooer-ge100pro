/* When the editor runs inside the desktop app (GE100Pro_Editor.exe / python -m ge100pro.app), the page is served
 * from http://127.0.0.1 and the app talks to the pedal over USB. This file then stands in for navigator.hid
 * (WebHID), so index.html works unchanged. Opened as a file in the browser, it does nothing. */
(function () {
  'use strict';
  if (location.protocol !== 'http:' || location.hostname !== '127.0.0.1') return;
  window.GE100PRO_APP = true;

  const listeners = { connect: [], disconnect: [] };
  let source = null;

  const dev = {
    vendorId: 0x34db, productId: 0x0011, productName: 'GE100 Pro', opened: false,
    _input: new Set(),
    async open() {
      // listen first, so no answer from the pedal is missed; one stream only
      if (!source) {
        source = new EventSource('/bridge/events');
        await new Promise((res, rej) => {
          source.onopen = () => res();
          setTimeout(() => rej(new Error('the editor app did not answer')), 5000);
        });
        wire(source);
      }
      const r = await (await fetch('/bridge/open', { method: 'POST' })).json();
      if (!r.ok) throw new Error(r.error || 'could not open the pedal');
      dev.opened = true;
    },
    async close() { dev.opened = false; if (source) { source.close(); source = null; } },
    async sendReport(id, data) {
      const body = data instanceof Uint8Array ? data : new Uint8Array(data.buffer || data);
      const r = await (await fetch('/bridge/send', { method: 'POST', body })).json();
      if (!r.ok) throw new Error(r.error || 'sending to the pedal failed');
    },
    addEventListener(type, fn) { if (type === 'inputreport') dev._input.add(fn); },
    removeEventListener(type, fn) { if (type === 'inputreport') dev._input.delete(fn); },
  };

  function wire(src) {
      src.addEventListener('report', (e) => {
        const bytes = new Uint8Array(e.data.match(/../g).map((h) => parseInt(h, 16)));
        const ev = { data: new DataView(bytes.buffer), reportId: 0, device: dev };
        dev._input.forEach((fn) => fn(ev));
      });
      src.addEventListener('disconnect', () => {
        dev.opened = false;
        if (source) { source.close(); source = null; }
        listeners.disconnect.forEach((fn) => fn({ device: dev }));
        watchForPedal();
      });
  }

  async function count() {
    try { return (await (await fetch('/bridge/devices')).json()).count; } catch (e) { return 0; }
  }
  // after unplugging: tell the page when a pedal is back, so it connects by itself
  let watching = false;
  function watchForPedal() {
    if (watching) return;
    watching = true;
    const t = setInterval(async () => {
      if ((await count()) > 0) { clearInterval(t); watching = false; listeners.connect.forEach((fn) => fn({ device: dev })); }
    }, 1500);
  }

  const hid = {
    async getDevices() { return (await count()) === 1 ? [dev] : []; },
    async requestDevice() {
      const n = await count();
      if (n === 0) throw new Error('No GE100 Pro found: is it switched on and connected by USB?');
      return [dev];   // with several pedals the app opens the first one
    },
    addEventListener(type, fn) { if (listeners[type]) listeners[type].push(fn); },
    removeEventListener() {},
  };
  Object.defineProperty(Navigator.prototype, 'hid', { configurable: true, get: () => hid });
})();
