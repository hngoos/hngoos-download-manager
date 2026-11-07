export const MODES = {off: 'Tắt', safe: 'An toàn tối thiểu', ads: 'Chặn quảng cáo', strong: 'Mạnh'};

// Translate only DNR-equivalent network rules. Unsupported options never become broader blocks.
export function compileFilters(text, source = '') {
  const domains = new Set();
  const exceptions = new Set();
  const scoped = [];
  const resourceTypes = ['script', 'image', 'sub_frame', 'xmlhttprequest', 'ping', 'other', 'stylesheet', 'font'];
  const types = {script:'script',image:'image',subdocument:'sub_frame',xmlhttprequest:'xmlhttprequest',
    ping:'ping',other:'other',stylesheet:'stylesheet',font:'font'};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const exception = line.match(/^@@\|\|([a-z0-9.-]+)\^$/i);
    if (exception) exceptions.add(exception[1].toLowerCase());
    const match = line.match(/^\|\|([a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)\^(?:\$third-party)?$/i);
    if (match && match[1].includes('.')) domains.add(match[1].toLowerCase());
    if (match || exception || !line || line.startsWith('!') || line.startsWith('[') || line.includes('#')) continue;
    const allow = line.startsWith('@@');
    const rule = allow ? line.slice(2) : line;
    const split = rule.lastIndexOf('$');
    const pattern = split < 0 ? rule : rule.slice(0, split);
    if (pattern.startsWith('/') || !pattern || pattern.length > 1500 || /[\x00-\x20]/.test(pattern)) continue;
    if (!/^\|\|[a-z0-9.-]+\./i.test(pattern)) continue;
    const condition = {urlFilter:pattern,resourceTypes:[...resourceTypes]};
    let supported = true;
    const positive = [], negative = [];
    for (const option of (split < 0 ? [] : rule.slice(split+1).split(','))) {
      if (types[option]) positive.push(types[option]);
      else if (option.startsWith('~') && types[option.slice(1)]) negative.push(types[option.slice(1)]);
      else if (option === 'third-party') condition.domainType = 'thirdParty';
      else if (option === '~third-party') condition.domainType = 'firstParty';
      else if (option === 'match-case') condition.isUrlFilterCaseSensitive = true;
      else if (option.startsWith('domain=')) {
        const included = [], excluded = [];
        for (const domain of option.slice(7).split('|')) {
          if (!/^~?[a-z0-9.-]+\.[a-z0-9.-]+$/i.test(domain)) { supported=false; break; }
          (domain.startsWith('~') ? excluded : included).push(domain.replace(/^~/,'').toLowerCase());
        }
        if (included.length) condition.initiatorDomains=included;
        if (excluded.length) condition.excludedInitiatorDomains=excluded;
      } else supported=false;
    }
    if (!supported) continue;
    condition.resourceTypes=(positive.length ? positive : resourceTypes).filter(type => !negative.includes(type));
    if (!condition.resourceTypes.length) continue;
    scoped.push({priority:allow ? 2 : 1,action:{type:allow ? 'allow' : 'block'},condition,source});
  }
  return [...[...domains].filter(domain => ![...exceptions].some(exception =>
    domain === exception || domain.endsWith(`.${exception}`) || exception.endsWith(`.${domain}`))).map(domain => ({
    priority: 1, action: {type: 'block'},
    condition: {urlFilter: `||${domain}^`, domainType: 'thirdParty',
      resourceTypes: ['script', 'image', 'sub_frame', 'xmlhttprequest', 'ping', 'other']},
    source,
  })),...scoped];
}

export function protectionRules(compiled, mode, allowSites = []) {
  const selected = compiled.filter(rule => mode === 'strong' ||
    (mode === 'safe' ? rule.source.includes('badware') : !rule.source.includes('Privacy')));
  const protectedSites = ['gov.vn', 'chinhphu.vn', 'dichvucong.gov.vn', 'vietcombank.com.vn',
    'bidv.com.vn', 'techcombank.com', 'mbbank.com.vn', 'acb.com.vn', 'vietinbank.vn', 'paypal.com',
    'stripe.com', 'accounts.google.com', 'login.microsoftonline.com', 'login.live.com'];
  const blocks = selected.map(({source, ...rule}, index) => ({...rule, id: index + 100,
    condition: {...rule.condition, excludedInitiatorDomains: [...new Set([...(rule.condition.excludedInitiatorDomains || []),
      ...protectedSites, ...(mode === 'safe' ? [] : allowSites)])]}}));
  // User allowlist keeps malware rules active; higher priority domain allow rules are unnecessary.
  for (let index = 0; index < blocks.length; index++) {
    if (selected[index].source.includes('badware')) {
      blocks[index].condition.excludedInitiatorDomains = [...new Set([
        ...(selected[index].condition.excludedInitiatorDomains || []),...protectedSites])];
      blocks[index].priority += 10;
    }
  }
  return blocks;
}
