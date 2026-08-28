import { createRoot } from "react-dom/client";
import { App } from "../../sidepanel/App";

const container = document.getElementById("root");
if (!container) {
  throw new Error("sidepanel root element is missing");
}
createRoot(container).render(<App />);
