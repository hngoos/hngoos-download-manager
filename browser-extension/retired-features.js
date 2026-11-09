// Remove persisted rules/scripts from older versions; download capture stays enabled.
export async function removeWebsiteTools(api) {
  try {
    const scripts = await api.scripting?.getRegisteredContentScripts?.();
    const ids = (scripts || []).filter(item => item.id === 'hdm-site-protection' || item.id.startsWith('hdm-invoice-')).map(item => item.id);
    if (ids.length) await api.scripting.unregisterContentScripts({ids});
  } catch { /* Revoked permissions already prevent these scripts from running. */ }
  try {
    const rules = await api.declarativeNetRequest?.getDynamicRules?.();
    if (rules?.length) await api.declarativeNetRequest.updateDynamicRules({removeRuleIds:rules.map(rule => rule.id), addRules:[]});
  } catch { /* Network filtering permission is no longer requested. */ }
  await api.alarms?.clear?.('filters');
  await api.storage.local.remove?.(['mode', 'allowSites', 'compiledRules', 'sourceStats', 'hiddenElements', 'invoiceHosts']);
}
