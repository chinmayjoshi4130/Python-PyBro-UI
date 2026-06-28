// gatekeeper.js
import { getAuthHeaders } from './utils.js';

let pendingCommand = null;

export function openGatekeeper(cmd, desc, targetId) {
    pendingCommand = { cmd, targetId };
    document.getElementById('gate-desc').innerText = desc;
    document.getElementById('gate-cmd').innerText = cmd;
    document.getElementById('gatekeeper-modal').style.display = 'flex';
}

export async function resolveGatekeeper(allowed) {
    document.getElementById('gatekeeper-modal').style.display = 'none';
    if (!allowed || !pendingCommand) return;

    const res = await fetch('/execute_os', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ cmd: pendingCommand.cmd, target_id: pendingCommand.targetId })
    });

    const data = await res.json();
    if (res.status === 403) {
        updateTarget("Access denied by server.", pendingCommand.targetId);
    } else {
        updateTarget(data.output, data.target_id || pendingCommand.targetId);
    }
    pendingCommand = null;
}

export function updateTarget(output, target_id) {
    if (target_id) {
        const el = document.getElementById(target_id);
        if (el) {
            if (el.tagName === 'TEXTAREA') el.value = output;
            else el.innerText = output;
        }
    } else {
        const first = document.querySelector('textarea, .terminal');
        if (first) {
            if (first.tagName === 'TEXTAREA') first.value = output;
            else first.innerText = output;
        }
    }
}