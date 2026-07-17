export function formatResetDate(limitReset: string | null | undefined): string {
  if (!limitReset) return '';
  const d = new Date();
  d.setUTCHours(0, 0, 0, 0);

  if (limitReset === 'daily') {
    d.setUTCDate(d.getUTCDate() + 1);
  } else if (limitReset === 'weekly') {
    const day = d.getUTCDay();
    const daysUntilMon = (1 - day + 7) % 7 || 7;
    d.setUTCDate(d.getUTCDate() + daysUntilMon);
  } else if (limitReset === 'monthly') {
    d.setUTCMonth(d.getUTCMonth() + 1, 1);
  } else {
    return limitReset;
  }

  return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', timeZone: 'UTC' }) +
    ' ' + d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC';
}
