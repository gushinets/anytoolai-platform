const accessForm = document.querySelector("#access-form");
const accessCodeInput = document.querySelector("#access-code");
const statusNode = document.querySelector("#status");
const catalogNode = document.querySelector("#catalog");

let accessCode = "";

accessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  accessCode = accessCodeInput.value;
  accessCodeInput.value = "";
  statusNode.textContent = "Загрузка каталога…";
  catalogNode.replaceChildren();

  try {
    const response = await fetch("/v1/atom-lab/atoms", {
      headers: {"X-Atom-Lab-Access-Code": accessCode},
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error?.message || "Не удалось открыть каталог.");
    }
    for (const atom of payload) {
      const card = document.createElement("article");
      const title = document.createElement("h2");
      const description = document.createElement("p");
      title.textContent = `${atom.atom_id} · ${atom.action_type}`;
      description.textContent = atom.description;
      card.append(title, description);
      catalogNode.append(card);
    }
    statusNode.textContent = `Доступно атомов: ${payload.length}.`;
  } catch (error) {
    accessCode = "";
    statusNode.textContent = error instanceof Error ? error.message : "Не удалось открыть каталог.";
  }
});
