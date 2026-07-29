// withMediaToken — appends auth token to /api/media/ URLs for per-user media access.
// <img>/<video> tags can't send Authorization headers, so token goes in query param.
// Legacy /public/ URLs and external URLs pass through unchanged.
export function withMediaToken(url: string | undefined): string {
  if (!url) return '';
  if (!url.includes('/api/media/')) return url;
  const token = localStorage.getItem('auth_token');
  if (!token) return url; // no token → endpoint will 401, ImageResultCard onError handles fallback
  const sep = url.includes('?') ? '&' : '?';
  return url + sep + 'token=' + encodeURIComponent(token);
}
