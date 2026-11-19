/* Mooer GE100 Pro protocol: framing, CRC and message decoding (port of src/ge100pro, see PROTOCOL.md).
 * The CRC and framing follow src/ge100pro/crc.py and framing.py, which are adapted from
 * fingerskier/Mooer_GE150_Pro_Li-IO (MIT, see NOTICE.md and CREDITS.md).
 * Classic script (no modules) so the page also works when opened straight from disk.
 * In Node: const P = require('./protocol.js'). In the browser: window.GE100.
 */
(function (root) {
  'use strict';

  const VENDOR_ID = 0x34db;
  const PRODUCT_ID = 0x0011;
  const REPORT_SIZE = 64;
  const CHUNK = REPORT_SIZE - 1;

  // CRC-16/GSM: poly 0x1021, init 0, not reflected, xorout 0xffff; over len field + cmd + payload
  function crc16(bytes) {
    let c = 0;
    for (const b of bytes) {
      c ^= b << 8;
      for (let i = 0; i < 8; i++) c = c & 0x8000 ? ((c << 1) ^ 0x1021) & 0xffff : (c << 1) & 0xffff;
    }
    return c ^ 0xffff;
  }

  function buildMessage(cmd, payload = []) {
    const body = [cmd, ...payload];
    const len = [body.length & 0xff, body.length >> 8];
    const crc = crc16([...len, ...body]);
    return Uint8Array.from([0xaa, 0x55, ...len, ...body, crc >> 8, crc & 0xff]);
  }

  /** Split one message into 64-byte reports: [n] + chunk + zero padding. */
  function buildReports(cmd, payload = []) {
    const msg = buildMessage(cmd, payload);
    const out = [];
    for (let i = 0; i < msg.length; i += CHUNK) {
      const chunk = msg.subarray(i, i + CHUNK);
      const r = new Uint8Array(REPORT_SIZE);
      r[0] = chunk.length;
      r.set(chunk, 1);
      out.push(r);
    }
    return out;
  }

  /** Reassembles frames {cmd, payload, crcOk} from 64-byte reports. */
  class Deframer {
    constructor() { this.buf = []; }
    feed(report) {
      const n = Math.min(report[0], CHUNK);
      for (let i = 1; i <= n; i++) this.buf.push(report[i]);
      const frames = [];
      for (;;) {
        let s = -1;
        for (let i = 0; i + 1 < this.buf.length; i++) if (this.buf[i] === 0xaa && this.buf[i + 1] === 0x55) { s = i; break; }
        if (s < 0) { this.buf = this.buf.length && this.buf[this.buf.length - 1] === 0xaa ? [0xaa] : []; return frames; }
        if (s > 0) this.buf = this.buf.slice(s);
        if (this.buf.length < 4) return frames;
        const len = this.buf[2] | (this.buf[3] << 8);
        if (len < 1) { this.buf = this.buf.slice(2); continue; }
        const total = 4 + len + 2;
        if (this.buf.length < total) return frames;
        const sizeAndBody = this.buf.slice(2, 4 + len);
        const crc = (this.buf[4 + len] << 8) | this.buf[5 + len];
        frames.push({ cmd: this.buf[4], payload: Uint8Array.from(this.buf.slice(5, 4 + len)), crcOk: crc16(sizeAndBody) === crc });
        this.buf = this.buf.slice(total);
      }
    }
  }

  // ---- message decoding ------------------------------------------------------------------
  const u16 = (p, o) => p[o] | (p[o + 1] << 8);
  const text = (p) => {
    let s = '';
    for (const b of p) { if (b === 0) break; s += String.fromCharCode(b); }
    return s.replace(/\s+$/, '');
  };

  const SLOT_RECORD = 50;
  const SLOT_PARAMS = 11;
  const PRESET_SLOTS = 10;

  // Effect types: names where values fit the Prime M2's types (hypothesis, see PROTOCOL.md §4)
  const TYPE_NAMES = { 0: 'Pre FX', 1: 'Drive', 2: 'Amp', 3: 'Cab', 4: 'Dynamics', 5: 'EQ', 6: 'Modulation', 7: 'Delay', 8: 'Reverb' };

  function parseSlot(index, r) {
    return {
      index,
      used: u16(r, 0) !== 0,
      type: u16(r, 2),
      enabled: u16(r, 4) !== 0,
      model: u16(r, 6),
      params: Array.from({ length: SLOT_PARAMS }, (_, i) => u16(r, 8 + 2 * i)),
      text: text(r.subarray(30, 50)),
      raw: Uint8Array.from(r.subarray(0, SLOT_RECORD)),
    };
  }

  /** Encode a slot back into the 50-byte record, the way Mooer Studio sends it (parameter 11 = 1). */
  function encodeSlot(slot) {
    const r = Uint8Array.from(slot.raw);
    const put = (o, v) => { r[o] = v & 0xff; r[o + 1] = (v >> 8) & 0xff; };
    put(0, slot.used ? 1 : 0);
    put(2, slot.type);
    put(4, slot.enabled ? 1 : 0);
    put(6, slot.model);
    slot.params.forEach((v, i) => put(8 + 2 * i, v));
    put(8 + 2 * 10, 1);
    return r;
  }

  function parsePreset(p) {
    const body = p.subarray(17);
    return {
      preset: p[0],
      name: text(p.subarray(1, 17)),
      slots: Array.from({ length: PRESET_SLOTS }, (_, i) => parseSlot(i, body.subarray(i * SLOT_RECORD, (i + 1) * SLOT_RECORD))),
    };
  }

  function parseNames(p) {
    const names = [];
    for (let i = 2; i + 16 <= p.length; i += 16) names.push(text(p.subarray(i, i + 16)));
    return { first: p[0], last: p[1], names };
  }

  function parseDeviceInfo(p) {
    return { name: text(p.subarray(0, 32)), firmware: text(p.subarray(32, 39)) };
  }

  /** 16-byte name field, space padded like the pedal's own names. */
  function nameField(name) {
    const out = new Uint8Array(16).fill(0x20);
    for (let i = 0; i < Math.min(16, name.length); i++) {
      const c = name.charCodeAt(i);
      out[i] = c >= 0x20 && c < 0x7f ? c : 0x3f;
    }
    return out;
  }

  const CMD = {
    DEVICE_INFO: 0x01, STATE: 0x11, SET_STATE: 0x13, PRESET: 0x21, SET_SLOT: 0x25, NAMES: 0x29,
    AVAILABILITY: 0x2b, SAVE: 0x2f, CURRENT_PRESET: 0x31, OPEN_PAGE: 0x41, LIST: 0x65,
  };
  const REPLY = {
    DEVICE_INFO: 0x02, STATE: 0x12, SET_STATE: 0x14, STATUS: 0x15, PRESET: 0x22, SET_SLOT: 0x26, SLOT: 0x27,
    NAMES: 0x2a, AVAILABILITY: 0x2c, SAVE: 0x30, PRESET_DUMP: 0x32, OPEN_PAGE: 0x42, NAV: 0x43, LIST: 0x66, X49: 0x49,
  };

  const api = {
    VENDOR_ID, PRODUCT_ID, REPORT_SIZE, CMD, REPLY, TYPE_NAMES, SLOT_RECORD, SLOT_PARAMS, PRESET_SLOTS,
    crc16, buildMessage, buildReports, Deframer, parseSlot, encodeSlot, parsePreset, parseNames, parseDeviceInfo, nameField,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.GE100 = api;
})(typeof self !== 'undefined' ? self : this);
