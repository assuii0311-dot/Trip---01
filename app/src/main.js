// 부팅: 기준 데이터 읽기 → App 렌더. 실패하면 원인을 화면에 보인다.
import { h, render } from "./lib.js";
import { App } from "./ui/app.js";
import { makeLoader } from "./data/loader.js";

const root = document.getElementById("app");
const loader = makeLoader("data/");
(async () => {
  try {
    const [attribution, cities, categoriesFile, airports, tier1] = await Promise.all([loader.attribution(), loader.cities(), loader.categories(), loader.airports(), loader.tier1()]);
    const data = { attribution, cities, categories: categoriesFile.categories, airports, tier1, tier2cache: new Map() };
    render(h(App, { data, loader }), root);
  } catch (e) {
    root.innerHTML = `<div class="boot">데이터를 읽지 못했습니다. ${String(e.message || e)}<br><span class="note">기준 데이터(data/)가 배포되어 있는지 확인하세요.</span></div>`;
  }
})();
