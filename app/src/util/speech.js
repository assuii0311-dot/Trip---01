// 음성 듣기(R-17, D-033): 브라우저 내장 음성 합성(Web Speech API)으로 한국어 설명을 읽는다.
// 글을 다듬는 함수는 순수 함수다. 테스트는 tests/app/speech.test.js
const HANGUL = /[가-힣]/;

/**
 * 읽을 글로 다듬는다. 괄호 안의 원어 병기(한글이 없는 부분)는 한국어 음성이 어색하게 읽으므로 뺀다.
 * 예: "가우디(Antoni Gaudí)가" → "가우디가", "모자이크(트렌카디스, trencadís)" → "모자이크(트렌카디스)"
 */
export function speechText(text) {
  return String(text || "")
    .replace(/(\s*)\(([^()]*)\)/g, (m, ws, inner) => {
      const keep = inner.split(/,\s*/).filter((part) => HANGUL.test(part));
      return keep.length ? `${ws}(${keep.join(", ")})` : "";
    })
    .replace(/\s+/g, " ")
    .trim();
}

/** 문장 나누기. 마침표 뒤가 공백이거나 글의 끝일 때만 나눈다(소수점, "R." 같은 머리글자는 나누지 않는다) */
function sentences(s) {
  const out = [];
  let start = 0;
  for (let i = 0; i < s.length; i++) {
    if (!".!?".includes(s[i])) continue;
    if (i + 1 < s.length && s[i + 1] !== " ") continue;
    if (s[i] === "." && /(^|\s)[A-Za-z]$/.test(s.slice(0, i))) continue;
    out.push(s.slice(start, i + 1).trim());
    start = i + 1;
  }
  if (start < s.length) out.push(s.slice(start).trim());
  return out.filter(Boolean);
}

/**
 * 읽기 조각 목록. 긴 발화는 일부 브라우저에서 중간에 끊기므로 문장 단위로 나누고, max자를 넘는 문장은 쉼표에서 다시 나눈다.
 * @param {string|string[]} texts
 */
export function speechChunks(texts, max = 160) {
  const out = [];
  for (const t of [].concat(texts || [])) {
    for (const sen of sentences(speechText(t))) {
      if (sen.length <= max) { out.push(sen); continue; }
      const parts = sen.split(", ");
      let cur = "";
      parts.forEach((part, i) => {
        const piece = i < parts.length - 1 ? part + "," : part;
        if (cur && (cur + " " + piece).length > max) { out.push(cur); cur = piece; } else cur = cur ? cur + " " + piece : piece;
      });
      if (cur) out.push(cur);
    }
  }
  return out;
}

/** 한국어 기기 내장 음성을 고른다. 원격 음성(localService가 아닌 것)은 글을 밖으로 보내므로 쓰지 않는다(규칙 11) */
export function pickKoreanVoice(voices) {
  const ko = Array.from(voices || []).filter((v) => /^ko([-_]|$)/i.test(v.lang || "") && v.localService);
  return ko.find((v) => v.default) || ko[0] || null;
}

/**
 * 읽기 제어기. synth는 speechSynthesis, Utter는 SpeechSynthesisUtterance(테스트에서는 가짜를 넣는다).
 * speak는 읽기를 시작했으면 true, 지원하지 않거나 한국어 내장 음성이 없으면 false를 돌려준다.
 */
export function makeSpeaker(synth = globalThis.speechSynthesis, Utter = globalThis.SpeechSynthesisUtterance) {
  const supported = !!synth && typeof Utter === "function";
  let token = 0;
  const voice = () => (supported ? pickKoreanVoice(synth.getVoices()) : null);
  return {
    supported,
    hasVoice: () => !!voice(),
    speak(texts, { onEnd, rate = 1 } = {}) {
      const v = voice();
      const chunks = speechChunks(texts);
      if (!v || !chunks.length) return false;
      synth.cancel();
      const my = ++token;
      chunks.forEach((c, i) => {
        const u = new Utter(c);
        u.lang = "ko-KR"; u.voice = v; u.rate = rate;
        if (i === chunks.length - 1) u.onend = () => { if (my === token && onEnd) onEnd(); };
        u.onerror = () => { if (my === token) { token++; synth.cancel(); if (onEnd) onEnd(); } };
        synth.speak(u);
      });
      return true;
    },
    stop() { token++; if (supported) synth.cancel(); },
  };
}
