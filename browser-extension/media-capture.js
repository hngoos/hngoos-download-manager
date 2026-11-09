// Keep only bounded manifest candidates. Never copy credentials or request bodies.
export function mediaCandidate(details) {
  if (details.tabId < 0 || !/^https?:\/\//i.test(details.url)) return null;
  const headers = details.responseHeaders || [];
  const type = headers.find(h => h.name.toLowerCase() === 'content-type')?.value || '';
  let kind = '';
  if (/\.m3u8(?:[?#]|$)/i.test(details.url) || /mpegurl/i.test(type)) kind = 'HLS';
  if (/\.mpd(?:[?#]|$)/i.test(details.url) || /dash\+xml/i.test(type)) kind = 'DASH';
  if (!kind) return null;
  const host = new URL(details.url).hostname;
  if (/(^|\.)(doubleclick\.net|googlesyndication\.com|googleadservices\.com)$/.test(host)
      || /\/(?:ads?|preroll|vast|vpaid)(?:[/.?_-]|$)/i.test(new URL(details.url).pathname)) return null;
  return {url: details.url, kind, host, seen: Date.now()};
}

export function mergeCandidates(current, candidate) {
  return [candidate, ...current.filter(item => item.url !== candidate.url)]
    .filter(item => Date.now()-item.seen < 30*60*1000).slice(0, 30);
}
