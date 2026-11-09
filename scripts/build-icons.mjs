import {build} from '../browser-extension/node_modules/esbuild/lib/main.js';
import {writeFileSync, mkdirSync, copyFileSync} from 'node:fs';
import {createMorph, canonicalD} from '../browser-extension/node_modules/morphicons/dist/dom.js';
import * as lucide from '../browser-extension/node_modules/lucide/dist/cjs/lucide.js';
const names = {download: 'Download', play: 'Play', pause: 'Pause', check: 'Check', shield: 'ShieldCheck',
  settings: 'Settings', folder: 'FolderOpen', list: 'List', video: 'Video', file: 'FileText', search: 'Search',
  plus: 'Plus', globe: 'Globe', info: 'Info', scissors: 'Scissors', close: 'X', app: 'AppWindow',
  music: 'Music', image: 'Image', archive: 'Archive', 'arrow-down': 'ArrowDown', 'arrow-up': 'ArrowUp',
  activity: 'ChartNoAxesCombined', sun: 'Sun', moon: 'Moon', more: 'Ellipsis', trash: 'Trash2', refresh: 'RefreshCw',
  transfer: 'ArrowUpDown', grid: 'LayoutGrid'};
// Iconoir's unstriped trash outline, matching the selected Morphicons preview.
// https://github.com/iconoir-icons/iconoir/blob/main/icons/regular/trash.svg (MIT)
const removeIcon = [
  ['path', {d: 'M20 9L18.005 20.3463C17.8369 21.3026 17.0062 22 16.0353 22H7.96474C6.99379 22 6.1631 21.3026 5.99496 20.3463L4 9'}],
  ['path', {d: 'M21 6L15.375 6M3 6L8.625 6M8.625 6V4C8.625 2.89543 9.52043 2 10.625 2H13.375C14.4796 2 15.375 2.89543 15.375 4V6M8.625 6L15.375 6'}],
];
await build({entryPoints: ['browser-extension/icon-entry.js'], bundle: true, format: 'esm',
  outfile: 'browser-extension/icons.js', minify: true, legalComments: 'eof'});
mkdirSync('src/hngoos_dm/assets/icons', {recursive: true});
mkdirSync('browser-extension/licenses', {recursive: true});
const svg = d => `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="${d}" fill="none" stroke="#eeeeee" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
for (const [name, exported] of Object.entries(names)) {
  writeFileSync(`src/hngoos_dm/assets/icons/${name}.svg`, svg(canonicalD(lucide[exported])));
}
writeFileSync('src/hngoos_dm/assets/icons/remove.svg', svg(canonicalD(removeIcon)));
// Exact filled outlines selected in Morphicons: Material Symbols error and Phosphor sort-ascending.
// Upstream notices are preserved in docs/licenses/material-symbols.txt and phosphor.txt.
const filled = (viewBox, d) => `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="${viewBox}"><path d="${d}" fill="#eeeeee"/></svg>`;
writeFileSync('src/hngoos_dm/assets/icons/alert.svg', filled('0 -960 960 960',
  'M480-280q17 0 28.5-11.5T520-320q0-17-11.5-28.5T480-360q-17 0-28.5 11.5T440-320q0 17 11.5 28.5T480-280Zm-40-160h80v-240h-80v240Zm40 360q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-320Z'));
writeFileSync('src/hngoos_dm/assets/icons/progress.svg', filled('0 0 256 256',
  'M128,128a8,8,0,0,1-8,8H48a8,8,0,0,1,0-16h72A8,8,0,0,1,128,128ZM48,72H184a8,8,0,0,0,0-16H48a8,8,0,0,0,0,16Zm56,112H48a8,8,0,0,0,0,16h56a8,8,0,0,0,0-16Zm125.66-21.66a8,8,0,0,0-11.32,0L192,188.69V112a8,8,0,0,0-16,0v76.69l-26.34-26.35a8,8,0,0,0-11.32,11.32l40,40a8,8,0,0,0,11.32,0l40-40A8,8,0,0,0,229.66,162.34Z'));
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
