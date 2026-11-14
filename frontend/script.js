const DICT = {
    zh: {
        "title": "鞋子文搜图",
        "label.search": "请输入英文描述",
        "btn.search": "搜索",
        "model.baseline": "原始模型",
        "model.finetuned": "微调模型",
        "score.none": "P@8 暂无评分",
        "score.line": "P@8 {p} · 命中 {n}/8",
        "rank.similarity": "相似度",
        "judgment.hit": "命中",
        "judgment.miss": "未命中",
        "judgment.unscored": "未评分",
        "label.shoe_type": "鞋型",
        "label.color_primary": "主色",
        "label.material_primary": "主材质",
        "label.colors_present": "颜色成分",
        "label.materials_present": "材质成分",
        "join": "、",
        "msg.empty": "没有可显示的图片。",
        "msg.noWeights": "微调权重尚未加载。请完成训练并重启服务。",
        "status.searching": "正在搜索…",
        "status.noQrels": "当前查询暂无可用的相关性标注。可试 white sneakers。",
        "status.requestFailed": "请求失败",
        "status.searchFailed": "搜索失败："
    },
    en: {
        "title": "Text-to-Image Shoe Search",
        "label.search": "Enter an English description",
        "btn.search": "Search",
        "model.baseline": "Baseline model",
        "model.finetuned": "Fine-tuned model",
        "score.none": "P@8 not scored",
        "score.line": "P@8 {p} · Hits {n}/8",
        "rank.similarity": "Similarity",
        "judgment.hit": "Hit",
        "judgment.miss": "Miss",
        "judgment.unscored": "Unscored",
        "label.shoe_type": "Shoe type",
        "label.color_primary": "Primary color",
        "label.material_primary": "Primary material",
        "label.colors_present": "Colors",
        "label.materials_present": "Materials",
        "join": ", ",
        "msg.empty": "No images to display.",
        "msg.noWeights": "Fine-tuned weights not loaded. Finish training and restart the server.",
        "status.searching": "Searching…",
        "status.noQrels": "No relevance judgments for this query. Try \"white sneakers\".",
        "status.requestFailed": "Request failed",
        "status.searchFailed": "Search failed: "
    }
};

const form = document.getElementById("searchForm");
const input = document.getElementById("searchInput");
const button = document.getElementById("search");
const status = document.getElementById("searchStatus");
const baseline = document.getElementById("baselineResults");
const finetuned = document.getElementById("finetunedResults");
const baselineScore = document.getElementById("baselineScore");
const finetunedScore = document.getElementById("finetunedScore");
const langToggle = document.getElementById("langToggle");
const apiBase = location.protocol === "file:" ? "http://localhost:5000" : location.origin;
const labelFields = ["shoe_type", "color_primary", "material_primary", "colors_present", "materials_present"];

let lang = localStorage.getItem("lang") === "en" ? "en" : "zh";
let last = { baseline: null, finetuned: null };
let lastStatusKey = null;
let lastStatusArg = "";

function t(key) {
    return DICT[lang][key];
}

function renderStatus() {
    status.textContent = lastStatusKey == null ? "" : t(lastStatusKey) + (lastStatusArg || "");
}

function applyStatic() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        el.textContent = t(el.dataset.i18n);
    });
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = t("title");
    langToggle.textContent = lang === "zh" ? "EN" : "中";
}

function renderResults(panel, score, result) {
    panel.replaceChildren();
    if (!result || result.imagePaths.length === 0) {
        const message = document.createElement("p");
        message.className = "empty";
        message.textContent = result ? t("msg.empty") : t("msg.noWeights");
        panel.append(message);
        return;
    }
    score.textContent = result.p_at_8 == null
        ? t("score.none")
        : t("score.line").replace("{p}", result.p_at_8.toFixed(3)).replace("{n}", result.relevant_count);
    result.imagePaths.forEach((path, rank) => {
        const card = document.createElement("figure");
        const image = document.createElement("img");
        image.src = apiBase + "/" + path.split("/").map(encodeURIComponent).join("/");
        image.alt = path.split("/").pop();
        image.loading = "lazy";
        const caption = document.createElement("figcaption");
        const ranking = document.createElement("div");
        ranking.textContent = "#" + (rank + 1) + " · " + t("rank.similarity") + " " + result.similarity[rank].toFixed(4);
        caption.append(ranking);
        const hit = result.isRelevant?.[rank];
        const state = hit === true ? "hit" : hit === false ? "miss" : "unscored";
        const judgment = document.createElement("span");
        judgment.className = "judgment " + state;
        judgment.textContent = t("judgment." + state);
        caption.append(judgment);

        const labels = result.labels?.[rank];
        if (labels) {
            const values = document.createElement("dl");
            values.className = "image-labels";
            for (const field of labelFields) {
                const term = document.createElement("dt");
                const value = document.createElement("dd");
                term.textContent = t("label." + field);
                const entry = labels[field];
                value.textContent = (Array.isArray(entry) ? entry.join(t("join")) : entry) || "—";
                values.append(term, value);
            }
            caption.append(values);
        }
        card.append(image, caption);
        panel.append(card);
    });
}

function rerenderLast() {
    if (last.baseline) renderResults(baseline, baselineScore, last.baseline);
    if (last.finetuned) renderResults(finetuned, finetunedScore, last.finetuned);
    renderStatus();
}

langToggle.addEventListener("click", () => {
    lang = lang === "zh" ? "en" : "zh";
    localStorage.setItem("lang", lang);
    applyStatic();
    rerenderLast();
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || button.disabled) return;
    button.disabled = true;
    last = { baseline: null, finetuned: null };
    lastStatusKey = "status.searching";
    lastStatusArg = "";
    renderStatus();
    baseline.replaceChildren();
    finetuned.replaceChildren();
    baselineScore.textContent = "";
    finetunedScore.textContent = "";
    try {
        const response = await fetch(apiBase + "/lookup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || t("status.requestFailed"));
        last = { baseline: data.baseline, finetuned: data.finetuned };
        renderResults(baseline, baselineScore, data.baseline);
        renderResults(finetuned, finetunedScore, data.finetuned);
        if (data.baseline.p_at_8 == null) {
            lastStatusKey = "status.noQrels";
            lastStatusArg = "";
        } else {
            lastStatusKey = null;
            lastStatusArg = "";
        }
        renderStatus();
    } catch (error) {
        lastStatusKey = "status.searchFailed";
        lastStatusArg = error.message;
        renderStatus();
    } finally {
        button.disabled = false;
    }
});

applyStatic();
