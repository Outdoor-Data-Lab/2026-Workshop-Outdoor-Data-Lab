// Show what the file of the selected source holds (in bold) and an example of it
// (from each parser's CONTENT and EXAMPLE).
document.addEventListener("DOMContentLoaded", () => {
  const help = document.getElementById("import-example");
  const select = document.getElementById("id_source");
  if (!help || !select) return;
  const parsers = JSON.parse(help.dataset.examples);
  const show = () => {
    help.replaceChildren();
    if (!select.value) return;
    const parser = parsers[select.value];
    if (!parser) {
      help.textContent = "Aucun parser pour cette source : le fichier sera enregistré sans être importé.";
      return;
    }
    if (parser.content) {
      const content = document.createElement("strong");
      content.textContent = parser.content;
      help.append(content, document.createElement("br"));
    }
    help.append(parser.example);
  };
  select.addEventListener("change", show);
  show();
});
