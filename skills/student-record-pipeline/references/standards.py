#!/usr/bin/env python3
"""2022 개정 교육과정 성취기준 조회 (오프라인·결정론).

인테이크 Step 1에서 `standards_backing`(헌법 3의 침묵 근거)을 채울 때 쓴다.
데이터 = `achievement-standards-2022.csv` (초·중·고 전 교과 3,285건 / 160과목).
외부 API·MCP 의존 없음 — 연결이 없어도 동작한다.

사용:
  python3 standards.py --subjects 역사        # 과목명 찾기(개명 대응) ★ 보통 여기서 시작
  python3 standards.py --subject 한국사1       # 그 과목 성취기준 전량
  python3 standards.py --code 10한사1         # 코드 접두어
  python3 standards.py --query 기후 --school 중학교
  python3 standards.py --subject 한국사1 --json

🚩 과목명은 2022 개정에서 바뀐 것이 있다(동아시아사 → '동아시아 역사 기행').
   0건이 나오면 과목이 없는 게 아니라 이름이 다른 것이다 → 먼저 `--subjects`로 찾을 것.
🚩 코드는 유일키가 아니다. 접두어를 공유하는 다른 과목이 있다
   (예: [12스문] = 스포츠 문화 / 스페인어권 문화). 키는 (과목, 코드)다.
"""
import argparse, csv, json, os, re, sys

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "achievement-standards-2022.csv")
COLS = ("학교", "과목", "학년(학년군)", "성취기준 코드", "성취기준 내용")


def load():
    if not os.path.exists(CSV):
        sys.exit(f"❌ 데이터 없음: {CSV}")
    with open(CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def norm(s):
    """공백·중점 차이를 흡수해 과목명 대조를 관대하게 — '기술·가정'/'기술가정' 등."""
    return re.sub(r"[\s·⋅ㆍ()]", "", str(s or "")).lower()


def subjects(rows, needle=None):
    """과목 목록. needle이 있으면 부분일치(정규화)로 좁힌다 — 개명 과목 찾기용."""
    agg = {}
    for r in rows:
        k = (r["학교"], r["과목"])
        agg[k] = agg.get(k, 0) + 1
    out = [(sc, sb, n) for (sc, sb), n in agg.items()
           if not needle or norm(needle) in norm(sb)]
    return sorted(out, key=lambda x: (x[0], x[1]))


def search(rows, subject=None, code=None, query=None, school=None):
    hits = rows
    if school:
        hits = [r for r in hits if r["학교"] == school]
    if subject:
        hits = [r for r in hits if norm(subject) == norm(r["과목"])] or \
               [r for r in hits if norm(subject) in norm(r["과목"])]
    if code:
        c = code.strip().lstrip("[").rstrip("]")
        hits = [r for r in hits if r["성취기준 코드"].lstrip("[").startswith(c)]
    if query:
        hits = [r for r in hits if query in r["성취기준 내용"]]
    return hits


def main():
    ap = argparse.ArgumentParser(description="2022 개정 성취기준 조회")
    ap.add_argument("--subjects", nargs="?", const="", help="과목 목록(인자 주면 부분일치 검색)")
    ap.add_argument("--subject", help="과목명 (예: 한국사1)")
    ap.add_argument("--code", help="성취기준 코드 또는 접두어 (예: 10한사1, [10한사1-01-01])")
    ap.add_argument("--query", help="성취기준 내용 키워드")
    ap.add_argument("--school", choices=["초등학교", "중학교", "고등학교"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = load()

    if a.subjects is not None:
        found = subjects(rows, a.subjects or None)
        if a.json:
            print(json.dumps([{"학교": s, "과목": b, "건수": n} for s, b, n in found],
                             ensure_ascii=False, indent=1))
        else:
            for s, b, n in found:
                print(f"{s:<6} {b:<24} {n:>3}건")
            print(f"\n{len(found)}개 과목")
            if a.subjects and not found:
                print("💡 0건 — 2022 개정에서 개명됐을 수 있다(동아시아사 → 동아시아 역사 기행). "
                      "인자 없이 --subjects 로 전체를 훑어볼 것.")
        return

    if not any([a.subject, a.code, a.query]):
        ap.print_help()
        return

    hits = search(rows, a.subject, a.code, a.query, a.school)
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
        return
    for r in hits:
        print(f"{r['성취기준 코드']:<16} [{r['과목']}·{r['학년(학년군)']}] {r['성취기준 내용']}")
    print(f"\n{len(hits)}건")
    if not hits:
        print("💡 0건 — 과목명이 다를 수 있다. `--subjects <키워드>` 로 먼저 확인할 것.")
    elif len({r["과목"] for r in hits}) > 1:
        print("⚠️ 여러 과목이 걸렸다 — 코드 접두어는 과목 간 중복될 수 있다(키 = 과목+코드).")


if __name__ == "__main__":
    main()
