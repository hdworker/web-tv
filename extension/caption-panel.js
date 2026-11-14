self.CaptionPanel = (() => {
  const ID = "un-live-captions";

  function element() {
    let panel = document.getElementById(ID);
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = ID;
    panel.setAttribute("role", "status");
    panel.style.cssText = [
      "position:fixed",
      "z-index:2147483647",
      "left:50%",
      "bottom:8%",
      "transform:translateX(-50%)",
      "max-width:min(80vw,900px)",
      "padding:12px 18px",
      "border-radius:8px",
      "background:rgba(0,0,0,.82)",
      "color:white",
      "font:600 20px/1.4 system-ui,sans-serif",
      "text-align:center",
      "pointer-events:none",
      "white-space:pre-wrap"
    ].join(";");
    document.documentElement.append(panel);
    return panel;
  }

  function show(text, state) {
    const panel = element();
    panel.textContent = text;
    panel.dataset.state = state;
    panel.style.display = "block";
    panel.style.border = state === "error" ? "1px solid #f87171" : "1px solid transparent";
  }

  function hide() {
    element().style.display = "none";
  }

  return { show, hide };
})();
