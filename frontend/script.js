const input = document.getElementById("searchInput");
const button = document.getElementById("search");
const results = document.getElementById("searchResults");
const apiBase = location.protocol === "file:" ? "http://localhost:5000" : location.origin;
input.addEventListener("keyup", (event) => {
    if (event.key === "Enter" && !button.disabled) button.click();
});
button.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text) return;
    button.disabled = true;
    results.textContent = "Loading...";
    try {
        const response = await fetch(apiBase + "/lookup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Search failed.");
        results.replaceChildren();
        if (!data.imagePaths.length) results.textContent = "No images found.";
        data.imagePaths.slice(0, 20).forEach((path, rank) => {
            const card = document.createElement("div");
            const label = document.createElement("p");
            label.textContent = `#${rank + 1} Similarity: ${data.similarity[rank].toFixed(4)}`;
            const image = document.createElement("img");
            image.src = apiBase + "/" + path.split("/").map(encodeURIComponent).join("/");
            image.alt = path;
            image.style.cssText = "width:300px;height:300px;object-fit:contain";
            card.append(label, image);
            results.append(card);
        });
    } catch (error) {
        results.textContent = "Search failed: " + error.message;
    } finally {
        button.disabled = false;
    }
});
