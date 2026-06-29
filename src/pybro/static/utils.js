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

// Convert basic Markdown to HTML (zero‑dep, safe)
export function convertMarkdown(text) {
    if (!text) return '';
    let html = text;
    // Escape existing HTML to prevent XSS
    html = escapeHtml(html);
    // Bold / italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Inline code
    html = html.replace(/`(.+?)`/g, '<code>$1</code>');
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    // Unordered lists (very simple, one level only)
    html = html.replace(/^\* (.+)$/gm, '<li>$1</li>');
    // Wrap consecutive <li> in <ul>
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<')) {
        html = '<p>' + html + '</p>';
    }
    return html;
}