// Run via tests/test_web_protocol.py, which exports the fixtures' HID reports to JSON first.
const path = require('path');
const P = require(path.join(__dirname, '..', '..', 'web', 'protocol.js'));
const data = require(process.argv[2]);
const assert = require('assert');
const hex = s => Uint8Array.from(s.match(/../g).map(h => parseInt(h, 16)));
function frames(name) {
  const d = { host: new P.Deframer(), pedal: new P.Deframer() }, out = [];
  for (const [dir, r] of data[name]) for (const f of d[dir].feed(hex(r))) out.push([dir, f]);
  return out;
}
// CRC + framing match the pedal's own frame
assert.deepStrictEqual(Array.from(P.buildMessage(0x43, [0x22, 0x00])), Array.from(hex('aa5503004322003554')));
// connect capture: all CRCs ok, names, device info, preset 82
const c = frames('01_connect_ge100pro');
assert(c.every(([, f]) => f.crcOk));
const names = {};
for (const [d, f] of c) if (d === 'pedal' && f.cmd === 0x2a) { const n = P.parseNames(f.payload); n.names.forEach((s, i) => names[n.first + i] = s); }
assert.strictEqual(Object.keys(names).length, 150); assert.strictEqual(names[82], 'JP Lead');
const info = P.parseDeviceInfo(c.find(([d, f]) => f.cmd === 0x02)[1].payload);
assert.deepStrictEqual(info, { name: 'GE100PRO', firmware: 'V1.3.3' });
const dump = P.parsePreset(c.find(([d, f]) => f.cmd === 0x32)[1].payload);
assert.strictEqual(dump.name, 'JP Lead');
assert.deepStrictEqual(dump.slots.filter(s => s.used).map(s => [s.index, s.type, s.model]), [[0,4,1],[1,1,21],[2,2,27],[3,5,2],[4,7,8],[5,8,1],[9,3,42]]);
// encodeSlot reproduces Mooer Studio's own SET_SLOT records byte for byte
let checked = 0;
for (const name of ['03_knob', '05_change_model'])
  for (const [d, f] of frames(name)) if (d === 'host' && f.cmd === 0x25) {
    const s = P.parseSlot(f.payload[0], f.payload.subarray(1, 51));
    const re = P.buildMessage(0x25, [f.payload[0], ...P.encodeSlot(s)]);
    assert.deepStrictEqual(Array.from(re.subarray(5, re.length - 2)), Array.from(f.payload)); checked++;
  }
// reports round trip for a long message
const long = Array.from({ length: 529 }, (_, i) => i & 0xff);
const df = new P.Deframer(); const got = P.buildReports(0x32, long).flatMap(r => df.feed(r));
assert(got.length === 1 && got[0].crcOk && got[0].payload.length === 529);
assert.deepStrictEqual(Array.from(P.nameField('JP Lead')), Array.from(hex('4a50204c656164202020202020202020')));
console.log('js protocol ok, SET_SLOT records reproduced:', checked);
