// Show what a file of the selected format holds (in bold) and an example of it
// (from each parser's CONTENT and EXAMPLE).
document.addEventListener("DOMContentLoaded", () => {
  const help = document.getElementById("import-example");
  const select = document.getElementById("id_format");
  if (!help || !select) return;
  const parsers = JSON.parse(help.dataset.examples);
  const show = () => {
    help.replaceChildren();
    if (!select.value) return;
    const parser = parsers[select.value];
    if (!parser) {
      help.textContent = "No parser for this format: the import will be refused.";
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
