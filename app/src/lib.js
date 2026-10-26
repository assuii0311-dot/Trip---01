// 동봉 라이브러리 재수출. UI 코드는 이 파일에서만 가져온다(규칙 11: 외부 CDN 금지).
export { h, render, Component, Fragment, createContext } from "../vendor/preact.module.js";
export { useState, useEffect, useMemo, useRef, useCallback, useContext } from "../vendor/hooks.module.js";
import htm from "../vendor/htm.module.js";
import { h } from "../vendor/preact.module.js";
export const html = htm.bind(h);
