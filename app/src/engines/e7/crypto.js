// E7 암호화(docs/engines/E7-sync.md 4절 1항, D-025): PBKDF2-SHA-256 600,000회 → AES-GCM 256, 파일마다 무작위 IV 12바이트.
// 브라우저와 Node 22 모두 globalThis.crypto.subtle을 쓴다. 순수 모듈.
export const PBKDF2_ITERATIONS = 600000;
export const KEY_MIN_LENGTH = 12;
const enc = new TextEncoder(), dec = new TextDecoder();

export function toB64(bytes) { let s = ""; for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b); return btoa(s); }
export function fromB64(s) { const bin = atob(s); const out = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i); return out; }

export function randomSalt() { return toB64(crypto.getRandomValues(new Uint8Array(16))); }

export function validateKey(key) {
  if (typeof key !== "string" || key.length < KEY_MIN_LENGTH) return `Key는 ${KEY_MIN_LENGTH}자 이상이어야 합니다.`;
  return null;
}

/** 비밀 문구와 salt(base64)로 AES-GCM 키를 만든다. 반복수는 meta.json에 기록된 값을 쓴다. */
export async function deriveKey(passphrase, saltB64, iterations = PBKDF2_ITERATIONS) {
  const base = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", salt: fromB64(saltB64), iterations, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

/** JSON → {v, iv, data} (base64). 파일 형식 v=1 */
export async function encryptJson(obj, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(JSON.stringify(obj)));
  return { v: 1, iv: toB64(iv), data: toB64(data) };
}

export async function decryptJson(blob, key) {
  if (!blob || blob.v !== 1) throw new Error("알 수 없는 파일 형식");
  try {
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(blob.iv) }, key, fromB64(blob.data));
    return JSON.parse(dec.decode(plain));
  } catch {
    throw new Error("복호화 실패. Key가 다르거나 파일이 손상되었습니다.");
  }
}

/** 내용 해시(내보내기 동일성 확인용, SHA-256 hex) */
export async function sha256Hex(text) {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(text));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
