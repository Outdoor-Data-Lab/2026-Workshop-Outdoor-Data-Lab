// The parser runs during the request: show that the file is being read (preview) or
// imported (apply), and block double submits.
document.addEventListener("DOMContentLoaded", () => {
  // Every import form: traffic, observation and offer imports.
  const form = document.querySelector('form[id$="import_form"]');
  form?.addEventListener("submit", (event) => {
    if (event.submitter?.name === "_cancel") return;
    const file = form.querySelector("input[type=file]")?.files[0];
    const what = file ? `${file.name} (${Math.round(file.size / 1e6)} MB)` : form.dataset.file || "the file";
    // Sending the file to a page with a preview only reads it; otherwise it is imported.
    const step = file && document.getElementById("import-example")?.dataset.preview ? "Reading" : "Importing";
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
      message.textContent = `${step} ${what}… ${seconds} s. Do not leave the page.`;
    };
    tick();
    setInterval(tick, 1000);
  });
});
