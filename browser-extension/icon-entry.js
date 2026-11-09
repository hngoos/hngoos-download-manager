// Build with scripts/build-icons.mjs. Runtime bundle is local: no CDN or remote scripts.
import {createMorph, canonicalD} from 'morphicons/dom';
import {Download, Play, Pause, Check, ShieldCheck, Settings, FolderOpen, List, Video,
  FileText, Search, Plus, Globe, Info, Scissors, X, LoaderCircle} from 'lucide';
export {createMorph, canonicalD};
export const icons = {download: Download, play: Play, pause: Pause, check: Check, shield: ShieldCheck,
  settings: Settings, folder: FolderOpen, list: List, video: Video, file: FileText, search: Search,
  plus: Plus, globe: Globe, info: Info, scissors: Scissors, close: X, loading: LoaderCircle};
export function mountIcon(element, name, size = 18) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', size); svg.setAttribute('height', size);
  svg.setAttribute('fill', 'none'); svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2'); svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round'); svg.setAttribute('aria-hidden', 'true');
  svg.style.cssText = 'vertical-align:middle;flex-shrink:0;margin-right:8px';
  const path = document.createElementNS(svg.namespaceURI, 'path');
  svg.append(path); element.prepend(svg);
  return createMorph(path, icons[name] || icons.download, {reducedMotion: 'user'});
}
