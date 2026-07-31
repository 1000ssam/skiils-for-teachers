#!/usr/bin/env python3
# 세특 초안 표면축 검증(결정론). 안목/의미는 검증하지 않음 — 그건 교사 몫.
# 사용: python3 tool/validate_draft.py <hakbun>   또는  --text "..."
import sys, os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 상한만 강제(초과 금지). 하한 없음 — 얇게 평가했으면 세특도 짧아서 그 얇음이 보여야 함(교사 원칙).
#
# 🚨 바이트 예산과 금지어휘는 **배치마다 다르다.** 여기 상수로 박으면 이전 배치 설정이 조용히
#    다음 배치를 오염시킨다. 실제로 그랬다 — 715B(다른 배치 예산)와 금지어 "시청자"가 남아 있었고,
#    '시청자에게 전달하고 싶은 의미'를 묻는 과제에서 **평가 렌즈의 핵심 어휘를 지우라고 압박**했다.
#    그래서 subject_terms() 와 같은 규약으로 **프로젝트가 공급**한다.
DEFAULT_BYTE_MAX = 1500    # 과목별 세특 500자 = NEIS 상한. 규칙 파일이 없을 때의 느슨한 안전값.
DEFAULT_BYTE_SHORT = 0     # 0 = '얇음' 경고 끔


def draft_rules():
    """<프로젝트 루트>/draft-rules.json — 스펙(length_budget·extra_forbidden)에서 온 값.

        {"byte_max": 780, "byte_short": 400,
         "forbidden": ["..."],        # 하드 실패
         "soft":      ["..."]}        # 단독 등장 시 경고만

    없으면 금지어 검사를 **생략**하고 상한은 NEIS 과목 상한으로 둔다(+stderr 경고).
    모르는 채 이전 배치 값을 적용하는 것보다, 검사를 안 하고 그렇다고 말하는 편이 안전하다.
    """
    p = os.path.join(ROOT, "draft-rules.json")
    if not os.path.exists(p):
        print(f"⚠ draft-rules.json 없음 ({p}) — 금지어 검사 생략, 바이트 상한 {DEFAULT_BYTE_MAX}B 적용. "
              f"인테이크 스펙의 length_budget·extra_forbidden 으로 이 파일을 만들 것.", file=sys.stderr)
        return {"byte_max": DEFAULT_BYTE_MAX, "byte_short": DEFAULT_BYTE_SHORT, "forbidden": [], "soft": []}
    r = json.load(open(p, encoding="utf-8"))
    return {"byte_max": int(r.get("byte_max", DEFAULT_BYTE_MAX)),
            "byte_short": int(r.get("byte_short", DEFAULT_BYTE_SHORT)),
            "forbidden": list(r.get("forbidden") or []),
            "soft": list(r.get("soft") or [])}


_R = draft_rules()
BYTE_MAX, BYTE_SHORT = _R["byte_max"], _R["byte_short"]
FORBIDDEN, SOFT = _R["forbidden"], _R["soft"]

# 도달 문장(계약서 3박자 ③) 탐지 — 어휘 목록이 아니라 '그 절이 있느냐'만 본다.
# level=하 는 이 절을 쓰지 않기로 교사가 정한 것이므로 등장 시 하드 실패.
REACH = re.compile(r"이를\s*통해|이로써|역량을\s*드러냄|인식을\s*드러냄|단초를\s*마련함|로\s*그려냄")
# 통설 전환 절 = level=상 에만 허가(중은 '한 겹만').
TURN = re.compile(r"에서\s*벗어나|극복하여|극복하고|에서\s*탈피")

# 동어반복 화이트리스트 — 어느 과목에서나 반복돼도 자연스러운 범용 구조어.
WHITELIST_BASE = {"역량", "인식", "개인", "국가", "서사", "담론", "역사", "상상", "주류",
    "소재", "장면", "인물", "대화", "이야기", "활동", "이후", "중심", "모습", "놓인", "시기"}


def subject_terms():
    """그 과목의 주제어. 과목마다 다르므로 **프로젝트가 공급한다.**

    <프로젝트 루트>/repeat-whitelist.txt — 한 줄에 한 낱말, `#` 주석·빈 줄 무시.
    없으면 빈 집합(=범용 구조어만 면제). 예시는 repeat-whitelist.example.txt 참조.
    """
    p = os.path.join(ROOT, "repeat-whitelist.txt")
    if not os.path.exists(p):
        return set()
    out = set()
    for line in open(p, encoding="utf-8"):
        w = line.split("#", 1)[0].strip()
        if w:
            out.add(w)
    return out


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:  # 바이트는 단일 출처 — NEIS 규칙(비ASCII=3)이지 UTF-8 길이가 아니다.
    from neis_bytes import neis_bytes as _neis_bytes           # 스킬 references/ 에서 실행할 때
except ImportError:                                            # 프로젝트 tool/ 로 복사돼 옆에 없을 때
    def _neis_bytes(s, newline_bytes=1):
        return sum(newline_bytes if c == "\n" else (1 if ord(c) < 128 else 3) for c in s)


def bytelen(s): return _neis_bytes(s)

def check(text, name="", highlights=None, level=None):
    issues, warns = [], []
    b = bytelen(text)
    if b > BYTE_MAX:
        issues.append(f"바이트 {b}B — 상한 {BYTE_MAX} 초과, 트림 필요")
    elif b < BYTE_SHORT:
        warns.append(f"바이트 {b}B — 짧음(얇은 마킹 반영). 패딩 말고 이대로 두되 의도 확인")
    # 종결: 명사형(…함/…음/…ㅁ)으로 끝나는지 — **구조(ㅁ 받침)로 본다.**
    # 🚩 음절 화이트리스트 `(함|음|림|냄|짐|둠|욤|룸|봄|샘)` 를 쓰면 안 된다. 목록에 없는 정상
    #    명사형(드러남·됨·옴·감…)을 실패시킨다. 실제로 교사 정본의 결말 "…능력이 드러남"이
    #    이 게이트에 걸려, **교사 문체를 따르면 재작성 루프에 빠지는** 상태였다.
    #    verify.py 의 ends_in_mieum 과 같은 규칙이다 — 두 검증기가 명사형을 다르게 정의하면 안 된다.
    tail = text.rstrip().rstrip(".")
    last = tail[-1] if tail else ""
    ok_nominal = bool(last) and 0xAC00 <= ord(last) <= 0xD7A3 and (ord(last) - 0xAC00) % 28 in (16, 10)
    if not ok_nominal:
        issues.append(f"종결 비명사형: '…{tail[-6:]}'")
    for w in FORBIDDEN:
        if w in text: issues.append(f"금지어 '{w}' 등장")
    for w in SOFT:
        if w in text: warns.append(f"주의어 '{w}' 등장(오용 아닌지 확인)")
    # 도달 수준 게이트 — 교사가 찍은 level 이 있을 때만. 없으면 현행(추정)대로 통과.
    lv = (level or "").strip()
    if lv:
        has_reach = bool(REACH.search(text))
        if lv == "하" and has_reach:
            issues.append("level=하 인데 도달 문장('이를 통해 …') 존재 — 한 일 서술로 끝낼 것")
        elif lv in ("상", "중") and not has_reach:
            warns.append(f"level={lv} 인데 도달 문장 없음 — 레벨과 어긋나는지 확인")
        if lv == "중" and TURN.search(text):
            warns.append("level=중 인데 통설 전환 절('~에서 벗어나') 존재 — 한 겹만인지 확인")
    # 인용부호(직접인용) 경고
    if re.search(r'[""\'"].{2,}[""\'"]', text):
        warns.append("직접 인용부호 흔적 — 인용 금지 확인")
    # 타 학생 실명 누출(간단): 렌더 대상 학생 본인 이름은 세특에 안 들어가는 게 정상
    if name and name in text:
        warns.append(f"본인 이름 '{name}' 등장 — 세특에 학생명 불필요")
    # 동어반복 탐지: 조사·복수접미사를 떼어 어간 기준 2회 이상 반복 표면화(경고·판단용, 실패 아님).
    # 화이트리스트로 과민 반응을 막는다 = 범용 구조어(WHITELIST_BASE) + 그 과목의 주제어.
    # 🚨 주제어를 여기 박지 마라 — 과목마다 다르다. 한국사 낱말을 박아두면 다른 과목에서
    #    엉뚱한 말이 면제되고, 정작 그 과목의 반복은 계속 걸린다. 주제어는 프로젝트가 준다.
    WHITELIST = WHITELIST_BASE | subject_terms()
    JOSA = r"(으로써|으로|이라는|라는|에서|에게|께서|처럼|만큼|보다|부터|까지|마다|이나|하고|와|과|을|를|이|가|은|는|의|에|로|도|만|께|나)$"
    from collections import Counter
    stems = []
    for w in re.findall(r"[가-힣]{2,}", text):
        s = re.sub(JOSA, "", w)
        s = re.sub(r"들$", "", s) or s        # 복수접미사 '들' 제거(백성들→백성)
        if len(s) >= 2 and s not in WHITELIST:
            stems.append(s)
    rep = [f"{w}×{c}" for w, c in sorted(Counter(stems).items(), key=lambda x: -x[1]) if c >= 2]
    # byte_max/byte_short도 함께 반환 — 상한값을 UI가 재하드코딩하지 않게(단일 출처).
    return {"bytes": b, "byte_max": BYTE_MAX, "byte_short": BYTE_SHORT, "level": lv or None,
            "issues": issues, "warns": warns, "repeats": rep, "ok": not issues}

def _argval(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv[:-1] else None

if __name__ == "__main__":
    if "--text" in sys.argv[:-1]:
        r = check(_argval("--text"), level=_argval("--level"))
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        hk = sys.argv[1]
        d = json.load(open(os.path.join(ROOT, "out", "drafts_v3b", f"{hk}.json"), encoding="utf-8"))
        # 레벨은 초안에 없으면 마킹에서 끌어온다(초안은 레벨 도입 전 산출물).
        lv = _argval("--level") or d.get("level")
        if not lv:
            mp = os.path.join(ROOT, "out", "marks", f"{hk}.json")
            if os.path.exists(mp): lv = json.load(open(mp, encoding="utf-8")).get("level")
        r = check(d["setuk"], d.get("name", ""), level=lv)
        print(f"{hk} {d.get('name','')}: {r['bytes']}B lv={lv or '—'}  {'✅OK' if r['ok'] else '❌'+str(r['issues'])}")
        if r["warns"]: print("  ⚠️", r["warns"])
    else:
        print("usage: validate_draft.py <hakbun> [--level 상|중|하] | --text '<세특>' [--level 상|중|하]")
