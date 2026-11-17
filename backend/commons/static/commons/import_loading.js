// The parser runs during the request: show that the import is running and block double submits.
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("dataimport_form");
  form?.addEventListener("submit", () => {
    const file = form.querySelector("input[type=file]")?.files[0];
    const what = file ? `${file.name} (${Math.round(file.size / 1e6)} Mo)` : "le fichier";
    form.querySelectorAll("[type=submit]").forEach((button) => (button.disabled = true));

    // Same markup as Django admin messages, so it gets their style.
    const list = document.createElement("ul");
    list.className = "messagelist";
    const message = list.appendChild(document.createElement("li"));
    message.className = "info";
    form.prepend(list);

    const start = Date.now();
    const tick = () => {
      const seconds = Math.round((Date.now() - start) / 1000);
      message.textContent = `Import en cours de ${what}… ${seconds} s. Ne quittez pas la page.`;
    };
    tick();
    setInterval(tick, 1000);
  });
});
