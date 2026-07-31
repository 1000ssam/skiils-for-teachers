#!/usr/bin/env python3
"""렌더 입력(args) 조립 — 결정론. 메인 에이전트가 손으로 args를 만들지 않게 한다.

  python3 tool/render_args.py                   # 대기열(pending.py) 전원
  python3 tool/render_args.py <학번> [<학번> …]  # 지정 학번만
  python3 tool/render_args.py --stdout          # 파일 대신 표준출력으로 JSON

출력(기본 out/render_args.json):
  {"contract": "<이 라인의 render_contract.md 절대경로>",
   "students": [{hakbun, name, context, competency, level, extra, highlights, rejects, prev_setuk}]}

· contract — 스크립트에 경로를 박지 않는다. 라인(실작업/실험)마다 계약서 내용이 다르므로
  하드코딩하면 다른 라인의 규칙으로 렌더되는 조용한 사고가 난다(HANDOFF 2026-07-28 §2).
· rejects  — 교사가 [다시]를 누른 사유 누적. 다음 렌더 프롬프트에 실려 같은 실수를 막는다.
· prev_setuk — 직전 초안 본문. 사유가 비었을 때 "이건 물렸다, 다르게 써라"의 근거가 된다.

⚠️ out/marks/ · out/drafts_v3b/ 는 읽기만 한다.
"""
import sys, os, json, glob, subprocess
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tool")
MARKS = os.path.join(ROOT, "out", "marks")
DRAFTS = os.path.join(ROOT, "out", "drafts_v3b")
CONTRACT = os.path.join(TOOL, "render_contract.md")
STUDENTS = os.path.join(TOOL, "students.json")
CTX_DEFAULT = ""   # 활동맥락은 과목마다 다르다 — 화면에서 교사가 넣는다(기본값을 박지 않는다)
REJECT_HINT = 3   # 이만큼 물리면 문장이 아니라 재료 문제일 가능성이 높다

def context():
    p = os.path.join(MARKS, "_context.json")
    if os.path.exists(p):
        try:
            c = (json.load(open(p, encoding="utf-8")).get("context") or "").strip()
            if c: return c
        except Exception: pass
    return CTX_DEFAULT

def pending():
    r = subprocess.run([sys.executable, os.path.join(TOOL, "pending.py")],
                       capture_output=True, text=True, cwd=ROOT)
    return [x.strip() for x in r.stdout.splitlines() if x.strip()]

def load(path):
    try: return json.load(open(path, encoding="utf-8"))
    except Exception: return None

def surface():
    """표면 규칙의 실값(바이트 상한·금지어·동어반복 예외어)을 payload 에 실어 보낸다.

    계약서 §2 가 `draft-rules.json`·`repeat-whitelist.txt` 를 **이름으로 언급**하는데,
    값을 안 실어 주면 서브에이전트가 그 이름을 단서로 프로젝트를 뒤진다(실측: find 로
    두 파일을 찾아 읽고, 내친김에 out/drafts_v3b/ 까지 ls 해서 남의 옛 초안을 읽었다).
    그게 헌법 7조(재료 조달 경계) 위반이고, 승인된 적 없는 초안에 문장이 끌려간다.
    → 필요한 값은 여기서 **먹여 주고**, 프롬프트는 탐색을 금지한다.
    """
    rules = load(os.path.join(ROOT, "draft-rules.json")) or {}
    words = []
    try:
        for ln in open(os.path.join(ROOT, "repeat-whitelist.txt"), encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                words.append(ln)
    except OSError:
        pass
    return {"byte_max": rules.get("byte_max"), "byte_short": rules.get("byte_short"),
            "forbidden": rules.get("forbidden") or [], "repeat_whitelist": words}

def sections():
    """마킹 칸 정의 — 화면과 같은 출처(students.json)를 쓴다. 여기에 하드코딩하지 않는다."""
    d = load(STUDENTS) or {}
    return d.get("sections") or []

def sources(mark, secs):
    """위임 학생에게 넘길 원문. 마킹 레코드가 화면이 저장한 원문을 그대로 갖고 있다."""
    out = []
    for sec in secs:
        text = (mark.get(sec["key"]) or "").strip()
        if text:
            out.append({"key": sec["key"], "label": sec.get("label", sec["key"]), "text": text})
    return out

def snapshot(rejects):
    """가장 최근 반려 스냅샷. 옛 마킹(스냅샷 도입 전)은 빈 문자열이라 자연히 건너뛴다."""
    for r in reversed(rejects):
        if r.get("setuk"):
            return r["setuk"]
    return ""


def build(hakbuns):
    ctx, secs, rows, notes = context(), sections(), [], []
    for hk in hakbuns:
        m = load(os.path.join(MARKS, f"{hk}.json"))
        if not m:
            notes.append(f"⚠️ {hk} — 마킹 파일 없음, 건너뜀"); continue
        d = load(os.path.join(DRAFTS, f"{hk}.json")) or {}
        rejects = m.get("rejects") or []
        hls = [{"section": h.get("section", ""), "text": h.get("text", ""),
                "why": h.get("why", "")} for h in m.get("highlights", [])]
        # 🚨 위임은 하이라이트 **개수 0**으로만 갈린다. 부분 마킹은 하드바인딩이고 원문을 싣지 않는다.
        #    "마킹이 부실해 보이면 원문도 준다"는 판단을 여기에 넣지 마라 — 그 순간 하드바인딩이 샌다.
        srcs = sources(m, secs) if not hls else []
        rows.append({
            "hakbun": hk,
            "name": m.get("name", ""),
            "context": ctx,
            "competency": m.get("competency", ""),
            "level": (m.get("level") or "").strip(),
            # 기타 요구사항 — 분량·톤·교사 관찰 사실. 계약서 §0-3 이 우선순위를 정한다.
            "extra": (m.get("extra") or "").strip(),
            "highlights": hls,
            "sources": srcs,
            # 회차별 스냅샷도 함께 싣는다 — 2회 이상 물렸을 때 "이 버전들 전부 물렸다"를
            # 모델이 보게 하려면 사유만으론 부족하다(같은 문장을 다시 낼 수 있다).
            "rejects": [{"at": r.get("at", ""), "reason": (r.get("reason") or "").strip(),
                         "setuk": r.get("setuk", "")} for r in rejects],
            # 물린 적이 있을 때만 직전 초안을 싣는다 — 없으면 모델이 그 문장에 끌려간다.
            # 스냅샷(rejects[i].setuk)이 있으면 그게 우선이다. 디스크 초안은 다음 렌더가
            # 덮어쓰면 사라져서, 2회 이상 물렸을 때 "뭘 보고 물렸는지"를 잃는다.
            "prev_setuk": (snapshot(rejects) or d.get("setuk", "")) if rejects else "",
        })
        if not hls:
            if srcs:
                notes.append(f"📖 {hk} {m.get('name','')} — 하이라이트 0개 → **위임**(AI가 원문에서 직접 고름). "
                             "검수에서 먼저 볼 것")
            else:
                notes.append(f"⚠️ {hk} {m.get('name','')} — 하이라이트도 원문도 없다. 렌더할 재료가 0이다")
        if len(rejects) >= REJECT_HINT:
            notes.append(f"🔁 {hk} {m.get('name','')} — {len(rejects)}회 물림. "
                         "문장이 아니라 재료(얇은 하이라이트·빈 '왜') 문제일 가능성이 높다 — 마킹을 손볼 것")
    # drafts_dir — 서브에이전트가 초안을 **직접 써야 할** 자리. 여기서 내려보내는 이유는
    # contract 와 같다: 라인마다 경로가 다르므로 워크플로 스크립트에 박으면 다른 라인의
    # 초안 폴더에 쓰는 조용한 사고가 난다. 화면(/draft)이 읽는 곳과 반드시 같아야 한다.
    return {"contract": CONTRACT, "drafts_dir": DRAFTS, "surface": surface(),
            "students": rows}, notes

def reason_signal(rows):
    """같은 사유가 여러 학생에게 반복되면 그건 개별 문장이 아니라 계약서·스펙 문제 신호다."""
    c = Counter(r["reason"] for row in rows for r in row["rejects"] if r["reason"])
    return [(reason, n) for reason, n in c.most_common() if n >= 2]

if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    to_stdout = "--stdout" in sys.argv
    targets = argv or pending()
    if not targets:
        print("대기열이 비었습니다 — 렌더할 학생이 없습니다.", file=sys.stderr)
        sys.exit(0)
    payload, notes = build(targets)
    rows = payload["students"]
    if to_stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        out = os.path.join(ROOT, "out", "render_args.json")
        json.dump(payload, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"렌더 입력 {len(rows)}명 → {out}", file=sys.stderr)
    err = sys.stderr
    print(f"계약서: {payload['contract']}", file=err)
    print("레벨 분포:", dict(Counter(r["level"] or "미지정" for r in rows)), file=err)
    delegated = sum(1 for r in rows if not r["highlights"] and r["sources"])
    if delegated:
        print(f"위임(마킹 0개 → AI가 직접 고름) {delegated}/{len(rows)}명 "
              "— 검수 비용이 올라가는 구간이다", file=err)
    reworks = sum(1 for r in rows if r["rejects"])
    if reworks: print(f"재렌더(물린 적 있음) {reworks}명", file=err)
    extras = [r for r in rows if r["extra"]]
    if extras:
        print(f"기타 요구사항 {len(extras)}명 — 계약서 기본값을 이긴다(§0-3). 검수에서 지시대로 나왔는지 볼 것", file=err)
        for r in extras: print(f"   · {r['hakbun']} {r['name']}: “{r['extra']}”", file=err)
    for n in notes: print(n, file=err)
    for reason, n in reason_signal(rows):
        print(f"🚩 같은 사유 {n}명 반복 — 계약서·스펙 문제 신호: “{reason}”", file=err)
