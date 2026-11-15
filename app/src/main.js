// 부팅: 기준 데이터 읽기 → App 렌더. 실패하면 원인을 화면에 보인다.
import { h, render } from "./lib.js";
import { App } from "./ui/app.js";
import { makeLoader } from "./data/loader.js";
import { applyDestinationKo } from "./data/dest.js";
import { applyPlaceKo } from "./data/places.js";

const root = document.getElementById("app");
const loader = makeLoader("data/");
(async () => {
  try {
    const [attribution, cities0, categoriesFile, airports, tier1raw, regions, e5, e5Index] = await Promise.all([loader.attribution(), loader.cities(), loader.categories(), loader.airports(), loader.tier1(), loader.regions().catch(() => []), loader.e5Destinations().catch(() => null), loader.e5Index().catch(() => null)]);
    const cities = applyDestinationKo(cities0, e5); // 여행지 한국어 소개와 생성 이름(E5). 파일이 없으면 영문 소개를 그대로 쓴다
    const tier1 = applyPlaceKo(tier1raw, e5Index); // 장소의 생성 한글 이름(E5). 색인이 없으면 그대로 쓴다
    const data = { attribution, cities, categories: categoriesFile.categories, airports, tier1, regions, e5Index, tier2cache: new Map() };
    render(h(App, { data, loader }), root);
  } catch (e) {
    root.innerHTML = `<div class="boot">데이터를 읽지 못했습니다. ${String(e.message || e)}<br><span class="note">기준 데이터(data/)가 배포되어 있는지 확인하세요.</span></div>`;
  }
})();
