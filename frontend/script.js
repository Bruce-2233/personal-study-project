const form = document.getElementById("searchForm");
const input = document.getElementById("searchInput");
const button = document.getElementById("search");
const status = document.getElementById("searchStatus");
const panels = ["baseline", "finetuned", "logistic_regression", "linear_svm"].map((key) => ({
    key,
    results: document.getElementById(key + "Results"),
    score: document.getElementById(key + "Score"),
}));
const apiBase = location.protocol === "file:" ? "http://localhost:5000" : location.origin;
const labelFields = [
    ["shoe_type", "Shoe Type"],
    ["color_primary", "Primary Color"],
    ["material_primary", "Primary Material"],
    ["colors_present", "Colors Present"],
    ["materials_present", "Materials Present"],
];

function renderResults({ key, results: panel, score }, result, availability) {
    panel.replaceChildren();
    if (!result || result.imagePaths.length === 0) {
        const message = document.createElement("p");
        message.className = "empty";
        if (result) {
            message.textContent = "No images found.";
        } else if (key === "finetuned") {
            message.textContent = "Fine-tuned model unavailable. Finish training and restart the server.";
        } else {
            message.textContent = availability === "predictions_incompatible"
                ? "Predictions do not match this gallery. Rebuild them and restart the server."
                : "Attribute predictions unavailable. Train the rerankers and restart the server.";
        }
        panel.append(message);
        return;
    }
    score.textContent = result.p_at_8 == null
        ? "P@8 unavailable"
        : "P@8 " + result.p_at_8.toFixed(3) + " · Hits " + result.relevant_count + "/8";
    const metric = result.rankingScores ? "Ranking Score" : "Similarity";
    const values = result.rankingScores || result.similarity;
    result.imagePaths.forEach((path, rank) => {
        const card = document.createElement("figure");
        const image = document.createElement("img");
        image.src = apiBase + "/" + path.split("/").map(encodeURIComponent).join("/");
        image.alt = path.split("/").pop();
        image.loading = "lazy";
        const caption = document.createElement("figcaption");
        const ranking = document.createElement("div");
        ranking.textContent = "#" + (rank + 1) + " · " + metric + " " + values[rank].toFixed(4);
        caption.append(ranking);
        const hit = result.isRelevant?.[rank];
        const judgment = document.createElement("span");
        judgment.className = "judgment " + (hit === true ? "hit" : hit === false ? "miss" : "unscored");
        judgment.textContent = hit === true ? "Hit" : hit === false ? "Miss" : "Not scored";
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
                value.textContent = (Array.isArray(entry) ? entry.join(", ") : entry) || "—";
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
    status.textContent = "Searching…";
    for (const panel of panels) {
        panel.results.replaceChildren();
        panel.score.textContent = "";
    }
    try {
        const response = await fetch(apiBase + "/lookup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Request failed.");
        for (const panel of panels) {
            renderResults(panel, data[panel.key], data.reranker_status?.[panel.key]);
        }
        status.textContent = data.baseline.p_at_8 == null
            ? 'No relevance labels are available for this query. Try "white sneakers".'
            : "";
    } catch (error) {
        status.textContent = "Search failed: " + error.message;
    } finally {
        button.disabled = false;
    }
});
