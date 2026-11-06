import {build} from '../browser-extension/node_modules/esbuild/lib/main.js';
import {writeFileSync, mkdirSync, copyFileSync} from 'node:fs';
import {createMorph, canonicalD} from '../browser-extension/node_modules/morphicons/dist/dom.js';
import * as lucide from '../browser-extension/node_modules/lucide/dist/cjs/lucide.js';
const names = {download: 'Download', play: 'Play', pause: 'Pause', check: 'Check', shield: 'ShieldCheck',
  settings: 'Settings', folder: 'FolderOpen', list: 'List', video: 'Video', file: 'FileText', search: 'Search',
  plus: 'Plus', globe: 'Globe', info: 'Info', scissors: 'Scissors', close: 'X', app: 'AppWindow',
  music: 'Music', image: 'Image', archive: 'Archive', 'arrow-down': 'ArrowDown', 'arrow-up': 'ArrowUp',
  activity: 'ChartNoAxesCombined', sun: 'Sun', moon: 'Moon'};
await build({entryPoints: ['browser-extension/icon-entry.js'], bundle: true, format: 'esm',
  outfile: 'browser-extension/icons.js', minify: true, legalComments: 'eof'});
mkdirSync('src/hngoos_dm/assets/icons', {recursive: true});
mkdirSync('browser-extension/licenses', {recursive: true});
const svg = d => `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="${d}" fill="none" stroke="#e6edf8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
for (const [name, exported] of Object.entries(names)) {
  writeFileSync(`src/hngoos_dm/assets/icons/${name}.svg`, svg(canonicalD(lucide[exported])));
}
// Sample the real Morphicons interpolation, then rasterize these frames once for Tkinter.
for (let frame = 0; frame <= 12; frame++) {
  let d;
  const morph = createMorph({setAttribute(key, value) { if (key === 'd') d = value; }}, lucide.Play,
    {reducedMotion: 'always'});
  morph.seek(lucide.Pause, frame/12);
  writeFileSync(`src/hngoos_dm/assets/icons/play-pause-${frame}.svg`, svg(d));
  morph.destroy();
}
for (const [dependency, license] of [['morphicons', 'LICENSE'], ['lucide', 'LICENSE']]) {
  copyFileSync(`browser-extension/node_modules/${dependency}/${license}`, `browser-extension/licenses/${dependency}.txt`);
}
console.log('Generated local Morphicons runtime, SVG states and animation frames');
