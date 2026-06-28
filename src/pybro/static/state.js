// state.js
import { getAuthHeaders } from './utils.js';

let savedFormState = {};
let globalMathFormulas = [];
let syncTimeout = null;

export function setMathFormulas(formulas) {
    globalMathFormulas = formulas;
}

export function getMathFormulas() {
    return globalMathFormulas;
}

export function getFormState() {
    const state = {};
    document.querySelectorAll('input, select').forEach(el => {
        if (el.id) state[el.id] = el.type === 'checkbox' ? el.checked : el.value;
    });
    return state;
}

export function captureFormState() {
    savedFormState = getFormState();
}

export function restoreFormState() {
    Object.entries(savedFormState).forEach(([key, value]) => {
        const el = document.getElementById(key);
        if (!el) return;
        if (el.type === 'checkbox') el.checked = value;
        else el.value = value;
    });
}

export function debouncedSyncFormState() {
    clearTimeout(syncTimeout);
    syncTimeout = setTimeout(syncFormStateToServer, 300);
}

function syncFormStateToServer() {
    const state = getFormState();
    fetch('/broadcast_state', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ form_state: state })
    }).catch(() => {});
}

export function evaluateReactiveMath() {
    const state = getFormState();
    globalMathFormulas.forEach(formulaObj => {
        const targetElement = document.getElementById(formulaObj.target_id);
        if (!targetElement) return;
        let expression = formulaObj.formula;
        Object.keys(state).forEach(key => {
            const val = parseFloat(state[key]) || 0;
            expression = expression.replaceAll(`{${key}}`, val);
        });
        try {
            const result = Function("\"use strict\"; return (" + expression + ")")();
            if (targetElement.tagName === 'INPUT' || targetElement.tagName === 'TEXTAREA')
                targetElement.value = result;
            else
                targetElement.innerText = result;
        } catch (e) {
            targetElement.innerText = "[Math Error]";
        }
    });
}