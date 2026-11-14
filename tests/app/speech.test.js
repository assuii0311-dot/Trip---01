import { test } from "node:test";
import assert from "node:assert/strict";
import { speechText, speechChunks, pickKoreanVoice, makeSpeaker } from "../../app/src/util/speech.js";

test("speechText: 원어 병기 괄호는 빼고 한글 풀이는 남긴다", () => {
  assert.equal(speechText("안토니 가우디(Antoni Gaudí)가 고쳐 지은 건물이다."), "안토니 가우디가 고쳐 지은 건물이다.");
  assert.equal(speechText("모자이크(트렌카디스, trencadís)로 덮여 있다."), "모자이크(트렌카디스)로 덮여 있다.");
  assert.equal(speechText("베아테리오(beaterio, 여성 신앙 공동체)에서 시작되었다."), "베아테리오(여성 신앙 공동체)에서 시작되었다.");
  assert.equal(speechText("  네르비온강 (Nervión)  가에 있다. "), "네르비온강 가에 있다.");
  assert.equal(speechText(null), "");
});
test("speechChunks: 문장 단위, 소수점과 머리글자는 나누지 않고 긴 문장은 쉼표에서 나눈다", () => {
  assert.deepEqual(speechChunks("높이는 2,444m다. 고립도는 6.34 km다."), ["높이는 2,444m다.", "고립도는 6.34 km다."]);
  assert.deepEqual(speechChunks(["솔로몬 R. 구겐하임 재단(Solomon R. Guggenheim Foundation)과 연계된 미술관이다.", "", "1997년에 문을 열었다"]), ["솔로몬 R. 구겐하임 재단과 연계된 미술관이다.", "1997년에 문을 열었다"]);
  const long = "가".repeat(60) + ", " + "나".repeat(60) + ", " + "다".repeat(60) + ".";
  const parts = speechChunks(long, 130);
  assert.deepEqual(parts, ["가".repeat(60) + ", " + "나".repeat(60) + ",", "다".repeat(60) + "."]);
  assert.ok(parts.every((p) => p.length <= 130));
  assert.deepEqual(speechChunks(undefined), []);
});
test("pickKoreanVoice: 한국어 기기 내장 음성만 고른다(원격 음성 제외)", () => {
  const voices = [{ lang: "en-US", localService: true, name: "en" }, { lang: "ko-KR", localService: false, name: "remote" }, { lang: "ko_KR", localService: true, name: "local" }, { lang: "ko-KR", localService: true, default: true, name: "default" }];
  assert.equal(pickKoreanVoice(voices).name, "default");
  assert.equal(pickKoreanVoice(voices.slice(0, 3)).name, "local");
  assert.equal(pickKoreanVoice(voices.slice(0, 2)), null);
  assert.equal(pickKoreanVoice(undefined), null);
});
test("makeSpeaker: 조각을 차례로 넣고, 끝나면 알리고, 멈추면 알리지 않는다", () => {
  const spoken = []; let cancels = 0;
  const synth = { getVoices: () => [{ lang: "ko-KR", localService: true, name: "유나" }], speak: (u) => spoken.push(u), cancel: () => { cancels++; } };
  function Utter(text) { this.text = text; }
  const sp = makeSpeaker(synth, Utter);
  assert.ok(sp.supported && sp.hasVoice());
  let ended = 0;
  assert.equal(sp.speak(["카사 바트요.", "가우디(Gaudí)가 지은 건물이다. 세계유산이다."], { onEnd: () => ended++ }), true);
  assert.deepEqual(spoken.map((u) => u.text), ["카사 바트요.", "가우디가 지은 건물이다.", "세계유산이다."]);
  assert.ok(spoken.every((u) => u.lang === "ko-KR" && u.voice.name === "유나"));
  assert.equal(spoken[0].onend, undefined);
  spoken[2].onend(); assert.equal(ended, 1);
  // 멈춘 뒤에 오는 이전 발화의 끝·오류 신호는 무시한다
  spoken.length = 0; sp.speak("다시 읽는다.", { onEnd: () => ended++ }); sp.stop();
  spoken[0].onend(); spoken[0].onerror(); assert.equal(ended, 1);
  // 읽는 중 오류가 나면 한 번만 알린다
  spoken.length = 0; sp.speak(["하나다.", "둘이다."], { onEnd: () => ended++ });
  spoken[0].onerror(); spoken[1].onerror(); spoken[1].onend(); assert.equal(ended, 2);
  assert.ok(cancels >= 4);
});
test("makeSpeaker: 지원하지 않거나 한국어 내장 음성이 없으면 읽지 않는다", () => {
  const none = makeSpeaker(undefined, undefined);
  assert.equal(none.supported, false); assert.equal(none.hasVoice(), false); assert.equal(none.speak("읽지 않는다."), false); none.stop();
  let called = 0;
  const remoteOnly = makeSpeaker({ getVoices: () => [{ lang: "ko-KR", localService: false }], speak: () => called++, cancel: () => {} }, function U() {});
  assert.equal(remoteOnly.supported, true); assert.equal(remoteOnly.speak("읽지 않는다."), false); assert.equal(called, 0);
});
