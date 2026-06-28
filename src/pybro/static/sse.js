// sse.js
export function startSSE({ onTokensUpdated, onStateUpdate, onCallbackOutput }) {
    const evtSource = new EventSource('/stream');
    const statusDot = document.getElementById('sse-status');

    evtSource.addEventListener('open', () => {
        statusDot.style.background = '#00e676';
    });

    evtSource.addEventListener('tokens_updated', () => {
        console.log("SSE tokens_updated – rebuilding UI");
        onTokensUpdated();
    });

    evtSource.addEventListener('state_update', e => {
        const state = JSON.parse(e.data);
        onStateUpdate(state);
    });

    evtSource.addEventListener('callback_output', e => {
        const data = JSON.parse(e.data);
        onCallbackOutput(data);
    });

    evtSource.onerror = () => {
        statusDot.style.background = '#ff5252';
        evtSource.close();
        setTimeout(() => startSSE({ onTokensUpdated, onStateUpdate, onCallbackOutput }), 3000);
    };
}