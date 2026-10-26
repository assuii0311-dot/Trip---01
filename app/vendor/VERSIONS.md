# 동봉 라이브러리 (D-026. 외부 CDN을 쓰지 않고 저장소에 둔다)

| 파일 | 패키지 | 버전 | 라이선스 | 출처 |
|---|---|---|---|---|
| preact.module.js, hooks.module.js | preact | 10.29.8 | MIT (LICENSE-preact.txt) | https://www.npmjs.com/package/preact |
| htm.module.js | htm | 3.1.1 | Apache-2.0 (LICENSE-htm.txt) | https://www.npmjs.com/package/htm |
| maplibre-gl.js, maplibre-gl.css | maplibre-gl | 5.24.0 | BSD-3-Clause (LICENSE-maplibre-gl.txt) | https://www.npmjs.com/package/maplibre-gl |

받은 날: 2026-10-25. 갱신은 같은 경로에서 파일을 바꾸고 이 표를 고친다.

패치: hooks.module.js의 `from"preact"`를 `from"./preact.module.js"`로 바꿨다(import map 없이 쓰기 위해. CSP가 인라인 import map을 막는다).
