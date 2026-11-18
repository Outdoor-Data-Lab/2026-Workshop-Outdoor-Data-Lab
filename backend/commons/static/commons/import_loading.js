// Show that the file is being uploaded, read (preview) or queued for the worker
// (apply), and block double submits.
document.addEventListener("DOMContentLoaded", () => {
  // Every import form: traffic, observation and offer imports.
  const form = document.querySelector('form[id$="import_form"]');
  form?.addEventListener("submit", (event) => {
    if (event.submitter?.name === "_cancel") return;
    const file = form.querySelector("input[type=file]")?.files[0];
    const what = file ? `${file.name} (${Math.round(file.size / 1e6)} MB)` : form.dataset.file || "the file";
    // A page with a preview reads the file sent; Apply only queues the stored file.
    const preview = document.getElementById("import-example")?.dataset.preview;
    const step = !file ? "Queuing" : preview ? "Reading" : "Uploading";
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
