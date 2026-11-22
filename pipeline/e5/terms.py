#!/usr/bin/env python3
"""E5 표기 사전(E5 4절 13항, D-063): 장소 설명의 지명·인명·용어를 한 꼴로 맞춘다.

- 사전 파일(pipeline/e5/content/terms_ko.json): {"keep": [건드리지 않을 구절], "terms": [항목]}.
  항목은 {"to": 기준 표기, "from": [쓰지 않을 변형] 또는 "re": 정규식, 선택 조건 "city"·"community"·"not_community", "note": 근거}.
  조건이 있는 항목은 그 도시(city: 지자체 ID 목록)나 자치주(community: 자치주 ID 목록)의 장소에만 적용한다.
  not_community는 자치주를 아는 장소 가운데 그 목록 밖의 장소에만 적용한다.
- 치환은 사전의 순서대로 하고, 더 바뀌는 것이 없을 때까지 되풀이한다(같은 글에 두 번 적용해도 결과가 같다).
- 변형과 기준 표기의 받침 유무가 다르면(몬주이크 → 몬주익) 바로 뒤에 붙은 조사도 맞춘다(몬주이크가 → 몬주익이).
- 순수 함수뿐이다. 파일과 네트워크를 모른다. 테스트는 pipeline/tests/test_e5.py.
"""
import re

FIELDS = ("name_ko", "summary_ko", "detail_ko")
MARK = "\u0000"  # 보호 구절을 가릴 때 쓰는 자리표시자(본문에 나오지 않는 문자)


# 받침에 따라 꼴이 달라지는 조사: (받침 뒤, 모음 뒤). 긴 것부터 견준다
JOSA = [("으로", "로"), ("이라", "라"), ("이었", "였"), ("이다", "다"), ("이며", "며"), ("이자", "자"), ("이나", "나"), ("이고", "고"), ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와")]
JOSA_RE = "|".join(x for pair in JOSA for x in pair)
JOSA_NEXT = {"라": "는고서도", "였": "다고으는던"}  # 이 조사 뒤에 이어질 수 있는 글자. 그 밖의 조사는 뒤가 한글이 아니어야 조사로 본다


def final_of(ch):
    """한글 음절의 받침 번호(0이면 받침 없음). 한글 음절이 아니면 None"""
    c = ord(ch) - 0xAC00
    return c % 28 if 0 <= c < 11172 else None


def josa_for(word, josa):
    """조사를 word의 끝 글자에 맞는 꼴로 바꾼다(은/는, 이/가, 을/를, 과/와, 으로/로, 이다/다 등)."""
    f = final_of(word[-1]) if word else None
    if f is None:
        return josa
    for a, b in JOSA:
        if josa in (a, b):
            if a == "으로":
                return b if f in (0, 8) else a  # 모음과 ㄹ 받침 뒤는 "로"
            return a if f else b
    return josa


def changes_final(variants, to):
    """변형과 기준 표기의 끝 글자에서 받침 유무가 달라지는가(그러면 뒤따르는 조사도 맞춰야 한다)"""
    ft = final_of(to[-1]) if to else None
    return ft is not None and any(final_of(v[-1]) is not None and bool(final_of(v[-1])) != bool(ft) for v in variants if v)


def replacer(to, with_josa):
    """치환 함수. with_josa면 변형 뒤에 붙은 조사를 기준 표기의 받침에 맞춘다. 조사 뒤가 다른 낱말로 이어지면 조사로 보지 않는다."""
    if not with_josa:
        return lambda m: to
    def sub(m):
        j = m.group("j")
        if not j:
            return to
        nxt = m.string[m.end():m.end() + 1]
        base = next((b for a, b in JOSA if j in (a, b)), j)
        is_josa = nxt == "" or not ("가" <= nxt <= "힣") or nxt in JOSA_NEXT.get(base, "")
        return to + (josa_for(to, j) if is_josa else j)
    return sub


def compile_terms(doc):
    """사전 객체 → {"keep": [구절], "rules": [(정규식, 치환 함수, 조건)]}"""
    rules = []
    for t in doc.get("terms") or []:
        with_josa = False
        if t.get("re"):
            pat = re.compile(t["re"])
        else:
            alts = "|".join(re.escape(x) for x in sorted(t["from"], key=len, reverse=True))
            with_josa = changes_final(t["from"], t["to"])
            pat = re.compile(f"(?:{alts})(?P<j>{JOSA_RE})?" if with_josa else alts)
        cond = {k: set(t[k]) for k in ("city", "community", "not_community") if t.get(k)}
        rules.append((pat, replacer(t["to"], with_josa), cond))
    return {"keep": sorted(doc.get("keep") or [], key=len, reverse=True), "rules": rules}


def applies(cond, ctx):
    """조건이 없는 항목은 늘 적용한다. 조건이 있는 항목은 장소의 도시·자치주를 알 때만 따진다."""
    if not cond:
        return True
    if not ctx:
        return False
    if "city" in cond and ctx.get("city") not in cond["city"]:
        return False
    if "community" in cond and ctx.get("community") not in cond["community"]:
        return False
    if "not_community" in cond and (not ctx.get("community") or ctx["community"] in cond["not_community"]):
        return False
    return True


def normalize(text, terms, ctx=None, protect=()):
    """글의 변형을 기준 표기로 바꾼다. 사전의 keep 구절과 protect 구절은 그대로 둔다."""
    if not text:
        return text
    held = []
    for phrase in sorted(set(protect) | set(terms["keep"]), key=len, reverse=True):
        if phrase and phrase in text:
            text = text.replace(phrase, f"{MARK}{len(held)}{MARK}"); held.append(phrase)
    rules = [(pat, to) for pat, to, cond in terms["rules"] if applies(cond, ctx)]
    for _ in range(4):
        before = text
        for pat, to in rules:
            text = pat.sub(to, text)
        if text == before:
            break
    for i, phrase in enumerate(held):
        text = text.replace(f"{MARK}{i}{MARK}", phrase)
    return text


def normalize_record(rec, terms, ctx=None, base_name=None):
    """한 장소의 생성 이름과 요약, 상세에 사전을 적용한 새 레코드. base_name은 기준 데이터에 있는 그 장소의 한국어 이름이다.
    요약은 그 이름으로 시작해야 하므로(형식 검사) 요약 맨 앞의 이름은 바꾸지 않는다."""
    out = dict(rec)
    for f in FIELDS:
        v = rec.get(f)
        if not v:
            continue
        if f == "summary_ko" and base_name and v.startswith(base_name):
            out[f] = base_name + normalize(v[len(base_name):], terms, ctx)
        else:
            out[f] = normalize(v, terms, ctx)
    return out


def violations(rec, terms, ctx=None, base_name=None):
    """사전과 다른 표기가 남은 필드 목록. 비어 있으면 통과."""
    fixed = normalize_record(rec, terms, ctx, base_name)
    return [f for f in FIELDS if (rec.get(f) or None) != (fixed.get(f) or None)]
