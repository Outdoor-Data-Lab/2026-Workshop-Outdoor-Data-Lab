// Show the expected file of the selected source (examples come from each parser's EXAMPLE).
document.addEventListener("DOMContentLoaded", () => {
  const example = document.getElementById("import-example");
  const select = document.getElementById("id_source");
  if (!example || !select) return;
  const examples = JSON.parse(example.dataset.examples);
  const show = () => {
    example.textContent = select.value
      ? examples[select.value] || "Aucun parser pour cette source : le fichier sera enregistré sans être importé."
      : "";
  };
  select.addEventListener("change", show);
  show();
});
