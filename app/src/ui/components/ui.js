import { html } from "../../lib.js";
export { html };
export const Chip = ({ kind = "", children, onClick }) => html`<span class=${"chip " + kind} onClick=${onClick}>${children}</span>`;
export const Empty = ({ children }) => html`<div class="empty">${children}</div>`;
