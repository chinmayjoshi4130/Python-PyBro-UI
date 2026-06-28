// utils.js
export function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

export function getAuthHeaders() {
    let token = null;
    try { token = sessionStorage.getItem('pybro_session_token'); } catch (e) {}
    return token ? { 'X-Pybro-Key': token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

export function applyRootCSS(cssVars) {
    const root = document.documentElement;
    for (const [prop, value] of Object.entries(cssVars)) root.style.setProperty(prop, value);
}

export function applyComponentCSS(wrapper, token) {
    if (token.css) for (const [p, v] of Object.entries(token.css)) wrapper.style.setProperty(p, v);
    if (token.class) wrapper.classList.add(token.class);
}
