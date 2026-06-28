// poller.js
import { getAuthHeaders } from './utils.js';

export function startPolling(onNewTokens, getCurrentTokens) {
    const pollMs = parseInt(window.pybroPollInterval) || 2000;
    setInterval(async () => {
        try {
            const res = await fetch('/tokens' + window.location.search, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const newTokens = await res.json();
            const newSnapshot = JSON.stringify(newTokens);
            const currentSnapshot = JSON.stringify(getCurrentTokens());
            if (newSnapshot !== currentSnapshot) {
                onNewTokens(newTokens);
            }
        } catch (e) {}
    }, pollMs);
}