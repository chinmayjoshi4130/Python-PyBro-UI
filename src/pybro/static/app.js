// app.js
import { getAuthHeaders } from './utils.js';
import { captureFormState, restoreFormState, evaluateReactiveMath } from './state.js';
import { buildPageStructure, renderPages, attachGlobalListeners, ensureGlobalDelegation, callbackButtons } from './renderer.js';
import { startSSE } from './sse.js';
import { updateTarget, resolveGatekeeper } from './gatekeeper.js';
import { startPolling } from './poller.js';

let currentTokens = [];
let uiGeneration = 0;

// Store session key from URL
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.has('key')) {
    try { sessionStorage.setItem('pybro_session_token', urlParams.get('key')); } catch (e) {}
}

// ---------- Core UI rebuild ----------
async function initRuntime() {
    uiGeneration++;
    const currentGen = uiGeneration;
    const scrollY = window.scrollY;
    captureFormState();

    try {
        const res = await fetch('/tokens' + window.location.search, { headers: getAuthHeaders() });
        if (res.status === 401) {
            document.getElementById('app-canvas').innerHTML = `<h2 style="color:var(--red)">⚠️ Access Denied: Invalid Security Token</h2>`;
            return;
        }
        if (!res.ok) {
            document.getElementById('app-canvas').innerHTML = `<h2 style="color:var(--red)">Could not load interface. Server returned ${res.status}.</h2>`;
            return;
        }
        const tokens = await res.json();
        if (uiGeneration !== currentGen) return;

        currentTokens = tokens;
        const pages = buildPageStructure(tokens);
        renderPages(pages);
        attachGlobalListeners();        // harmless, delegation is already active
        evaluateReactiveMath();
        restoreFormState();
        window.scrollTo(0, scrollY);
    } catch (e) {
        console.error("initRuntime error:", e);
    }
}

// ---------- Callback dispatching ----------
async function firePythonCallback(name) {
    const target_id = callbackButtons[name] || null;
    const startGen = uiGeneration;
    updateTarget("[*] Dispatching callback...", target_id);

    try {
        const { getFormState } = await import('./state.js');
        const res = await fetch('/trigger_callback', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                callback_name: name,
                form_state: getFormState(),
                target_id: target_id
            })
        });
        const data = await res.json();
        console.log("Callback response:", data);

        if (uiGeneration !== startGen) {
            console.log("UI rebuilt during callback – ignoring manual update.");
            return;
        }

        if (!data.ui_patched) {
            updateTarget(data.output, data.target_id || target_id);
        }
    } catch (err) {
        console.error("Callback error:", err);
        updateTarget("Error: " + (err.message || err), target_id);
    }
}

// Custom event from renderer's delegated buttons
window.addEventListener('pybro:callback', e => {
    firePythonCallback(e.detail.name);
});

// Gatekeeper approve/deny buttons are static HTML, attach once
function setupGatekeeperButtons() {
    document.getElementById('gate-approve-btn').addEventListener('click', () => resolveGatekeeper(true));
    document.getElementById('gate-deny-btn').addEventListener('click', () => resolveGatekeeper(false));
}
setupGatekeeperButtons();

// ---------- SSE state update handler ----------
function applyRemoteState(state) {
    Object.entries(state).forEach(([key, value]) => {
        const el = document.getElementById(key);
        if (!el) return;
        if (el.type === 'checkbox') {
            if (el.checked !== value) el.checked = value;
        } else {
            if (el.value !== value) el.value = value;
        }
    });
    evaluateReactiveMath();
}

// ---------- Launch ----------
window.onload = () => {
    // Activate global delegated listeners once before any UI
    ensureGlobalDelegation();

    initRuntime();
    startSSE({
        onTokensUpdated: () => initRuntime(),
        onStateUpdate: applyRemoteState,
        onCallbackOutput: (data) => updateTarget(data.output, data.target_id)
    });
    startPolling(
        (newTokens) => {
            currentTokens = newTokens;
            initRuntime();
        },
        () => currentTokens
    );
};