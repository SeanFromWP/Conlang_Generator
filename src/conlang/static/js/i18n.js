// ===============================
// i18n.js  (Flask + CSV version)
// ===============================

let i18nData = {};     // 原始分類結構
let i18nFlat = {};     // 扁平快取 (key -> {zh,en})
let currentLang = 'zh';
let isTranslating = false;


// ===============================
// 1️⃣  載入 CSV
// ===============================
async function loadTranslations() {
    try {
        const response = await fetch(
            window.TRANSLATION_URL + "?t=" + new Date().getTime()
        );
        if (!response.ok) throw new Error("Fetch failed");

        const text = await response.text();
        parseCSV(text);

        applyTranslations();
        observeDOM();

        console.log("✅ i18n loaded");

    } catch (err) {
        console.error("❌ i18n load error:", err);
    }
}


// ===============================
// 2️⃣  解析 CSV
// 格式："cat","key","en","zh"
// ===============================
function parseCSV(data) {

    const lines = data.replace(/^\uFEFF/, '').split(/\r?\n/);

    i18nData = {};
    i18nFlat = {};

    lines.forEach((line, index) => {

        const trimmed = line.trim();
        if (!trimmed || index === 0) return;

        const columns = trimmed
            .replace(/^"|"$/g, '')
            .split('","');

        if (columns.length < 4) return;

        const [category, key, en, zh] = columns;

        // 建立分類結構
        if (!i18nData[category]) i18nData[category] = {};
        i18nData[category][key] = { en, zh };

        // 建立快取結構（效能用）
        i18nFlat[key] = { en, zh };
    });
}


// ===============================
// 3️⃣  核心翻譯函式 (JS 用)
// ===============================
function t(key, params = {}) {

    const entry = i18nFlat[key];
    if (!entry) return key;

    let text = entry[currentLang] || key;

    // 參數替換 {name}
    Object.keys(params).forEach(p => {
        text = text.replace(new RegExp(`{${p}}`, 'g'), params[p]);
    });

    return text;
}


// ===============================
// 4️⃣  套用到 HTML
// ===============================
function applyTranslations() {

    if (!Object.keys(i18nFlat).length) return;
    if (isTranslating) return;

    isTranslating = true;

    document.querySelectorAll('[data-i18n]').forEach(el => {

        const key = el.dataset.i18n;
        if (!key) return;

        const translated = t(key);
        const displayText = translated !== key
            ? translated
            : generateDebugText(key);

        // 更新文字
        if (el.textContent !== displayText) {
            el.textContent = displayText;
        }

        // 如果在 <option> 裡
        const parentOption = el.closest('option');
        if (parentOption) {
            parentOption.text = displayText;
            parentOption.label = displayText;
        }

        // placeholder 支援
        if (el.hasAttribute('data-i18n-placeholder')) {
            el.placeholder = displayText;
        }
    });

    setTimeout(() => {
        isTranslating = false;
    }, 50);
}


// ===============================
// 5️⃣  DOM 監聽（動態元素）
// ===============================
function observeDOM() {

    const observer = new MutationObserver((mutations) => {

        if (isTranslating) return;

        const hasNewNodes = mutations.some(m => m.addedNodes.length > 0);
        if (hasNewNodes) {
            applyTranslations();
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}


// ===============================
// 6️⃣  語言切換
// ===============================
function updateLangMode(mode) {

    currentLang = mode;
    localStorage.setItem('conlang-pref-lang', mode);

    applyTranslations();
    updateLangButtonUI(mode);
}


function updateLangButtonUI(mode) {

    document.querySelectorAll('.btn-lang').forEach(btn => {
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-sub)';
        btn.style.boxShadow = 'none';
    });

    const activeBtn = document.getElementById('btn-' + mode);
    if (activeBtn) {
        activeBtn.style.background = 'white';
        activeBtn.style.color = 'var(--primary)';
        activeBtn.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
    }
}


// ===============================
// 7️⃣  Debug 文字產生（找不到翻譯時）
// ===============================
function generateDebugText(key) {
    const cleaned = key
        .replace(/_/g, ' ')
        .replace(/-/g, ' ');
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}


// ===============================
// 8️⃣  初始化
// ===============================
document.addEventListener('DOMContentLoaded', () => {

    currentLang =
        localStorage.getItem('conlang-pref-lang') || 'zh';

    updateLangButtonUI(currentLang);

    loadTranslations();
});


// ===============================
// 9️⃣  對外開放 (讓別的 JS 可用)
// ===============================
window.t = t;
window.updateLangMode = updateLangMode;