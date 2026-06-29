// renderer.js
import { escapeHtml, applyComponentCSS } from './utils.js';
import { debouncedSyncFormState, evaluateReactiveMath, setMathFormulas } from './state.js';
import { openGatekeeper } from './gatekeeper.js';

// Global maps rebuilt once per full UI render
export let callbackButtons = {};
export let globalMathFormulas = [];

// ---------- Page structure parsing ----------
export function buildPageStructure(tokens) {
    const pages = [];
    let currentPage = null;
    let inTabGroup = false;
    let currentTab = null;
    let tabTokens = [];

    const flushTab = () => {
        if (currentTab) {
            currentTab.tokens = tabTokens;
            if (!currentPage.tabs) currentPage.tabs = [];
            currentPage.tabs.push(currentTab);
            currentTab = null;
            tabTokens = [];
        }
    };

    tokens.forEach(tok => {
        if (tok.type === 'PAGE_START') {
            if (currentPage) pages.push(currentPage);
            currentPage = { name: tok.name, tokens: [], tabs: null };
            inTabGroup = false;
            flushTab();
        } else if (tok.type === 'PAGE_END') {
            if (currentPage) { flushTab(); pages.push(currentPage); currentPage = null; }
        } else if (tok.type === 'TAB_GROUP_START') {
            if (currentPage) { inTabGroup = true; if (!currentPage.tabs) currentPage.tabs = []; }
        } else if (tok.type === 'TAB_GROUP_END') {
            flushTab(); inTabGroup = false;
        } else if (tok.type === 'TAB_START') {
            flushTab(); currentTab = { name: tok.name, tokens: [] };
        } else if (tok.type === 'TAB_END') {
            flushTab();
        } else {
            if (currentPage) {
                if (inTabGroup && currentTab) tabTokens.push(tok);
                else if (!inTabGroup) currentPage.tokens.push(tok);
            }
        }
    });
    if (currentPage) pages.push(currentPage);
    return pages;
}

// ---------- Rendering ----------
export function renderPages(pages) {
    const canvas = document.getElementById('app-canvas');
    const nav = document.getElementById('page-nav');
    canvas.innerHTML = '';
    nav.innerHTML = '';

    if (pages.length === 0) return;

    // Reset global maps once per full UI rebuild
    callbackButtons = {};
    globalMathFormulas = [];
    setMathFormulas(globalMathFormulas);

    pages.forEach(page => {
        const btn = document.createElement('button');
        btn.className = 'page-nav-btn';
        btn.innerText = page.name;
        btn.onclick = () => showPage(page.name);
        nav.appendChild(btn);

        const pageDiv = document.createElement('div');
        pageDiv.className = 'page-content';
        pageDiv.id = 'page-' + page.name.replace(/\s/g, '_');

        if (page.tokens.length > 0) {
            const pageTokensDiv = document.createElement('div');
            renderTokens(pageTokensDiv, page.tokens);
            pageDiv.appendChild(pageTokensDiv);
        }

        if (page.tabs && page.tabs.length > 0) {
            const tabBar = document.createElement('div');
            tabBar.className = 'tab-bar';
            const tabsContainer = document.createElement('div');
            tabsContainer.className = 'tabs-container';

            page.tabs.forEach(tab => {
                const tabBtn = document.createElement('button');
                tabBtn.className = 'tab-btn';
                tabBtn.innerText = tab.name;
                tabBtn.onclick = () => showTab(page.name, tab.name);
                tabBar.appendChild(tabBtn);

                const tabContent = document.createElement('div');
                tabContent.className = 'tab-content';
                tabContent.id = `tab-${page.name.replace(/\s/g, '_')}-${tab.name.replace(/\s/g, '_')}`;
                renderTokens(tabContent, tab.tokens);
                tabsContainer.appendChild(tabContent);
            });

            pageDiv.appendChild(tabBar);
            pageDiv.appendChild(tabsContainer);
        }

        canvas.appendChild(pageDiv);
    });

    const hash = window.location.hash.substring(1);
    let initialPage = hash || pages[0].name;
    if (!pages.find(p => p.name === initialPage)) initialPage = pages[0].name;
    showPage(initialPage);
}

let activePageName = null;
let activeTabName = {};

export function showPage(pageName) {
    document.querySelectorAll('.page-content').forEach(div => div.classList.remove('active'));
    document.querySelectorAll('.page-nav-btn').forEach(btn => btn.classList.remove('active'));

    const pageDiv = document.getElementById('page-' + pageName.replace(/\s/g, '_'));
    if (pageDiv) pageDiv.classList.add('active');
    document.querySelectorAll('.page-nav-btn').forEach(btn => {
        if (btn.innerText === pageName) btn.classList.add('active');
    });

    activePageName = pageName;
    window.location.hash = '#' + pageName;

    const tabBtns = pageDiv ? pageDiv.querySelectorAll('.tab-btn') : [];
    if (tabBtns.length > 0) {
        const firstTabName = tabBtns[0].innerText;
        if (!activeTabName[pageName]) showTab(pageName, firstTabName);
        else showTab(pageName, activeTabName[pageName]);
    }
}

export function showTab(pageName, tabName) {
    const pageDiv = document.getElementById('page-' + pageName.replace(/\s/g, '_'));
    if (!pageDiv) return;
    pageDiv.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
    pageDiv.querySelectorAll('.tab-btn').forEach(tb => tb.classList.remove('active'));

    const tabContent = document.getElementById(`tab-${pageName.replace(/\s/g, '_')}-${tabName.replace(/\s/g, '_')}`);
    if (tabContent) tabContent.classList.add('active');
    pageDiv.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.innerText === tabName) btn.classList.add('active');
    });

    activeTabName[pageName] = tabName;
}

// ---------- Token → DOM ----------
export function renderTokens(container, tokens) {
    let containers = [container];

    tokens.forEach(tok => {
        if (tok.type === 'SECTION_START') {
            const sectionDiv = document.createElement('div');
            sectionDiv.className = 'section';
            sectionDiv.id = 'section-' + tok.id;
            if (!tok.visible) sectionDiv.style.display = 'none';
            applyComponentCSS(sectionDiv, tok);
            containers[containers.length - 1].appendChild(sectionDiv);
            containers.push(sectionDiv);
        } else if (tok.type === 'SECTION_END') {
            if (containers.length > 1) containers.pop();
        } else if (tok.type === 'LAYOUT_ROW_START') {
            const row = document.createElement('div');
            row.className = "ui-row";
            applyComponentCSS(row, tok);
            containers[containers.length - 1].appendChild(row);
            containers.push(row);
        } else if (tok.type === 'LAYOUT_ROW_END') {
            if (containers.length > 1) containers.pop();
        } else if (tok.type === 'UI_ROOT_CSS') {
            import('./utils.js').then(m => m.applyRootCSS(tok.css_vars));
            return;
        } else {
            const wrapper = document.createElement('div');
            wrapper.className = "component";
            applyComponentCSS(wrapper, tok);

            switch (tok.type) {
                case "UI_TITLE":
                    const h = document.createElement('h1');
                    h.innerText = tok.text;
                    if (tok.css) { for (const [p, v] of Object.entries(tok.css)) h.style.setProperty(p, v); }
                    if (tok.class) h.classList.add(tok.class);
                    containers[containers.length - 1].appendChild(h);
                    return;
                case "UI_INPUT":
                    wrapper.innerHTML = `<label>${tok.label}</label><input id="${tok.id}" type="text">`;
                    break;
                case "UI_CHECKBOX":
                    wrapper.innerHTML = `<label style="display:flex; align-items:center; gap:8px;"><input id="${tok.id}" type="checkbox"> ${tok.label}</label>`;
                    break;
                case "UI_DROPDOWN":
                    const optionsHTML = tok.options.map(o => `<option value="${o}">${o}</option>`).join('');
                    wrapper.innerHTML = `<label>${tok.label}</label><select id="${tok.id}">${optionsHTML}</select>`;
                    break;
                case "UI_TEXT_AREA":
                    const textAreaValue = tok.value || "System Idle...";
                    wrapper.innerHTML = `<label>${tok.label}</label><textarea id="${tok.id}" readonly>${escapeHtml(textAreaValue)}</textarea>`;
                    break;
                case "UI_CALLBACK_BUTTON":
                    callbackButtons[tok.callback_name] = tok.target_id || null;
                    wrapper.innerHTML = `<button type="button" data-callback="${tok.callback_name}">${tok.text}</button>`;
                    break;
                case "UI_MATH_COMPUTE":
                    globalMathFormulas.push(tok);
                    return;
                case "OS_GATEKEEPER":
                    wrapper.innerHTML = `
                        <button type="button" data-os-cmd="${encodeURIComponent(tok.cmd)}" data-os-desc="${encodeURIComponent(tok.desc)}" data-os-target="${tok.target_id}">Execute Script Hook</button>
                        <label style="margin-top:10px;">System Buffer Output:</label>
                        <div id="${tok.target_id}" class="terminal">Console idle.</div>`;
                    break;
                case "UI_TABLE":
                    let tableHtml = '';
                    const headers = tok.headers || [];
                    const rows = tok.rows || [];
                    if (headers.length === 0 && rows.length === 0) {
                        tableHtml = '<p style="padding:1rem;">No data available.</p>';
                    } else {
                        const ths = headers.map(h => `<th>${h}</th>`).join('');
                        const trs = rows.map(r => {
                            const cells = [];
                            for (let i = 0; i < headers.length; i++) {
                                cells.push(`<td>${r[i] !== undefined ? r[i] : ''}</td>`);
                            }
                            return `<tr>${cells.join('')}</tr>`;
                        }).join('');
                        tableHtml = `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
                    }
                    wrapper.innerHTML += tableHtml;
                    break;
                case "UI_MARKDOWN":
                    import('./utils.js').then(m => {
                        wrapper.innerHTML = `<div class="markdown-content">${m.convertMarkdown(tok.text)}</div>`;
                    });
                    break;
                case "UI_SLIDER":
                    const min = tok.min !== undefined ? tok.min : 0;
                    const max = tok.max !== undefined ? tok.max : 100;
                    const step = tok.step !== undefined ? tok.step : 1;
                    wrapper.innerHTML = `
                        <label>${tok.label} (<span id="${tok.id}-value">${min}</span>)</label>
                        <input type="range" id="${tok.id}" min="${min}" max="${max}" step="${step}" value="${min}"
                               oninput="document.getElementById('${tok.id}-value').innerText = this.value">
                    `;
                    break;
                case "UI_PASSWORD":
                    wrapper.innerHTML = `<label>${tok.label}</label><input id="${tok.id}" type="password">`;
                    break;
                case "UI_TOGGLE":
                    const checked = tok.checked ? 'checked' : '';
                    wrapper.innerHTML = `
                        <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                            <input id="${tok.id}" type="checkbox" ${checked}
                                   style="appearance:none; width:44px; height:24px; background:${tok.checked ? 'var(--accent)' : '#444'}; border-radius:12px; position:relative; transition:background 0.2s; cursor:pointer; outline:none;"
                                   onchange="this.style.background = this.checked ? 'var(--accent)' : '#444'">
                            ${tok.label}
                        </label>`;
                    break;
                case "UI_PROGRESS":
                    const progValue = tok.value || 0;
                    const progMax = tok.max || 100;
                    wrapper.innerHTML = `
                        <label>${tok.label}</label>
                        <div style="background:#1a2236; border-radius:6px; overflow:hidden; height:20px;">
                            <div id="${tok.id}" style="background:var(--accent); height:100%; width:${(progValue / progMax) * 100}%; transition:width 0.3s;"></div>
                        </div>`;
                    break;
                case "UI_DATE":
                    wrapper.innerHTML = `<label>${tok.label}</label><input id="${tok.id}" type="date">`;
                    break;
                case "UI_INPUT_GENERIC":
                    const itype = tok.input_type || 'text';
                    wrapper.innerHTML = `<label>${tok.label}</label><input id="${tok.id}" type="${itype}">`;
                    break;
            }
            containers[containers.length - 1].appendChild(wrapper);
        }
    });
}

// ---------- Delegated event setup (one‑time, no duplication) ----------
let delegationReady = false;

export function ensureGlobalDelegation() {
    if (delegationReady) return;
    delegationReady = true;

    // Reactive math + form state sync for all inputs/selects
    document.addEventListener('input', (e) => {
        if (!e.target.matches('input, select')) return;
        evaluateReactiveMath();
        debouncedSyncFormState();
    });
    document.addEventListener('change', (e) => {
        if (!e.target.matches('input, select')) return;
        evaluateReactiveMath();
        debouncedSyncFormState();
    });

    // OS Gatekeeper buttons
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-os-cmd]');
        if (!btn) return;
        const cmd = decodeURIComponent(btn.dataset.osCmd);
        const desc = decodeURIComponent(btn.dataset.osDesc);
        const target = btn.dataset.osTarget;
        openGatekeeper(cmd, desc, target);
    });

    // Callback buttons → emit custom event for app.js
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-callback]');
        if (!btn) return;
        window.dispatchEvent(new CustomEvent('pybro:callback', {
            detail: { name: btn.dataset.callback }
        }));
    });
}

// attachGlobalListeners is now a no‑op – delegation handles everything
export function attachGlobalListeners() {}