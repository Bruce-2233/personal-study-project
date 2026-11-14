const form = document.getElementById("searchForm");
const input = document.getElementById("searchInput");
const button = document.getElementById("search");
const status = document.getElementById("searchStatus");
const baseline = document.getElementById("baselineResults");
const finetuned = document.getElementById("finetunedResults");
const baselineScore = document.getElementById("baselineScore");
const finetunedScore = document.getElementById("finetunedScore");
const apiBase = location.protocol === "file:" ? "http://localhost:5000" : location.origin;
const labelFields = [
    ["shoe_type", "鞋型"],
    ["color_primary", "主色"],
    ["material_primary", "主材质"],
    ["colors_present", "颜色成分"],
    ["materials_present", "材质成分"],
];

function renderResults(panel, score, result) {
    panel.replaceChildren();
    if (!result || result.imagePaths.length === 0) {
        const message = document.createElement("p");
        message.className = "empty";
        message.textContent = result ? "没有可显示的图片。" : "微调权重尚未加载。请完成训练并重启服务。";
        panel.append(message);
        return;
    }
    score.textContent = result.p_at_8 == null
        ? "P@8 暂无评分"
        : "P@8 " + result.p_at_8.toFixed(3) + " · 命中 " + result.relevant_count + "/8";
    result.imagePaths.forEach((path, rank) => {
        const card = document.createElement("figure");
        const image = document.createElement("img");
        image.src = apiBase + "/" + path.split("/").map(encodeURIComponent).join("/");
        image.alt = path.split("/").pop();
        image.loading = "lazy";
        const caption = document.createElement("figcaption");
        const ranking = document.createElement("div");
        ranking.textContent = "#" + (rank + 1) + " · 相似度 " + result.similarity[rank].toFixed(4);
        caption.append(ranking);
        const hit = result.isRelevant?.[rank];
        const judgment = document.createElement("span");
        judgment.className = "judgment " + (hit === true ? "hit" : hit === false ? "miss" : "unscored");
        judgment.textContent = hit === true ? "命中" : hit === false ? "未命中" : "未评分";
        caption.append(judgment);

        const labels = result.labels?.[rank];
        if (labels) {
            const values = document.createElement("dl");
            values.className = "image-labels";
            for (const [field, title] of labelFields) {
                const term = document.createElement("dt");
                const value = document.createElement("dd");
                term.textContent = title;
                const entry = labels[field];
                value.textContent = (Array.isArray(entry) ? entry.join("、") : entry) || "—";
                values.append(term, value);
            }
            caption.append(values);
        }
        card.append(image, caption);
        panel.append(card);
    });
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || button.disabled) return;
    button.disabled = true;
    status.textContent = "正在搜索…";
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
        if (!response.ok) throw new Error(data.error || "请求失败");
        renderResults(baseline, baselineScore, data.baseline);
        renderResults(finetuned, finetunedScore, data.finetuned);
        status.textContent = data.baseline.p_at_8 == null
            ? "当前查询暂无可用的相关性标注。可试 white sneakers。"
            : "";
    } catch (error) {
        status.textContent = "搜索失败：" + error.message;
    } finally {
        button.disabled = false;
    }
});
