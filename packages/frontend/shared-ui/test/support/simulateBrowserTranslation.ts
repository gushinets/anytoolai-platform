/** Mimics translation by replacing label text with nested font elements, detaching React's text nodes. */
export function simulateBrowserTranslation(root: Element, prefix = "EN: "): void {
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  for (const node of nodes) {
    if (!node.nodeValue?.trim()) continue;
    const outer = root.ownerDocument.createElement("font");
    const inner = root.ownerDocument.createElement("font");
    inner.textContent = `${prefix}${node.nodeValue}`;
    outer.appendChild(inner);
    node.parentNode!.replaceChild(outer, node);
  }
}
