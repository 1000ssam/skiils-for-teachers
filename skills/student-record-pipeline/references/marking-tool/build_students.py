#!/usr/bin/env python3
# 명렬표(mapping_reconciled.csv) + clean 텍스트(p3 장면·생각 / p4 대화)를 tool/students.json 으로 조립.
#   단일 반:  python3 tool/build_students.py <N> <반>     예) build_students.py 30 1-4  (앞 N명)
#   전 학급:  python3 tool/build_students.py all           → 6개 반 172명 전체(반 탭용)
import csv, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "out", "mapping_reconciled.csv")
CLEAN = os.path.join(ROOT, "out", "clean")

# 학생 활동지가 몇 칸으로 되어 있는지 — 화면(mark.html)이 이걸 읽어 칸을 그린다.
#   key   = 명렬표 CSV 열 이름이자 학생 기록의 필드명
#   label = 칸 제목 · tag = 표시한 줄에 붙는 짧은 꼬리표 · tip = 칸 제목 옆 안내(선택)
#
# 🔑 과제가 바뀌면 이 파일을 고치지 말고 **<project>/sections.json** 을 만든다.
#    스크립트 상수를 손으로 고치게 하면 배치마다 스킬 원본이 오염되고, 다른 과제의
#    칸 정의가 조용히 남아 있게 된다. 아래 값은 그 파일이 없을 때만 쓰는 예시다.
SECTIONS_FILE = os.path.join(ROOT, "sections.json")
SECTIONS = [
    {"key": "p3", "label": "p3 · 장면 설정 + 나의 생각", "tag": "장면·생각",
     "tip": "드래그하면 바로 형광펜, 다시 드래그로 추가"},
    {"key": "p4", "label": "p4 · 인물 간 대화", "tag": "대화"},
]
if os.path.exists(SECTIONS_FILE):
    with open(SECTIONS_FILE, encoding="utf-8") as f:
        loaded = json.load(f)
    loaded = loaded.get("sections", loaded) if isinstance(loaded, dict) else loaded
    if not isinstance(loaded, list) or not loaded:
        sys.exit(f"❌ {SECTIONS_FILE} 는 칸 목록이어야 합니다(빈 목록 불가).")
    for sec in loaded:
        if not isinstance(sec, dict) or not sec.get("key") or not sec.get("label"):
            sys.exit(f"❌ {SECTIONS_FILE} 의 각 칸에는 key 와 label 이 있어야 합니다: {sec!r}")
    SECTIONS = loaded

def read_clean(rel):
    if not rel: return ""
    p = os.path.join(CLEAN, rel)
    if not os.path.exists(p): return f"[파일 없음: {rel}]"
    with open(p, encoding="utf-8") as f:
        return f.read().rstrip()

def mk(r):
    s = {
        "order": (r.get("순서") or "").strip(),
        "cls": r["반"].strip(),
        "hakbun": r["학번"].strip(),
        "name": r["이름"].strip(),
        "status": (r.get("상태") or "").strip(),
    }
    for sec in SECTIONS:
        s[sec["key"]] = read_clean((r.get(sec["key"]) or "").strip())
    return s

def is_blank(s):
    return not any(s.get(sec["key"]) for sec in SECTIONS)

def cls_key(c):  # "1-4" → ("1", 4) 로 자연 정렬
    a, _, b = c.partition("-")
    return (a, int(b) if b.isdigit() else 0)

def order_key(s):
    return (cls_key(s["cls"]), int(s["order"]) if s["order"].isdigit() else 0)

rows = list(csv.DictReader(open(MAP, encoding="utf-8-sig")))
# 기본값은 "all". 예전 기본값은 특정 반("5")이라 인자 없이 부르면 **0명 조립하고도**
# "조립 완료"로 성공처럼 끝났다(실측 2026-08-03). 조용히 비는 기본값은 두지 않는다.
arg1 = sys.argv[1] if len(sys.argv) > 1 else "all"
out = os.path.join(ROOT, "tool", "students.json")

if arg1 == "all":
    classes = sorted({(r.get("반") or "").strip() for r in rows if (r.get("반") or "").strip()}, key=cls_key)
    students = [mk(r) for r in rows if (r.get("반") or "").strip() in classes]
    students.sort(key=order_key)  # 반 → 순서 안정 정렬
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"classes": classes, "sections": SECTIONS, "total": len(students), "students": students},
                  f, ensure_ascii=False, indent=1)
    print(f"전 학급 조립: {len(students)}명 / {len(classes)}반 → tool/students.json")
    for c in classes:
        print(f"  {c}: {sum(1 for s in students if s['cls'] == c)}명")
    blanks = [s for s in students if is_blank(s)]
    if blanks:
        print(f"  ⚠ 원문 없음(미제출/판독불가) {len(blanks)}명 — 빈 카드로 표시(마킹 대상 아님):")
        for s in blanks:
            print(f"     {s['cls']} {s['hakbun']} {s['name']} [{s['status']}]")
else:
    N = int(arg1)
    CLS = sys.argv[2] if len(sys.argv) > 2 else "1-4"
    picked = [r for r in rows if (r.get("반") or "").strip() == CLS][:N]
    students = [mk(r) for r in picked]
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"cls": CLS, "sections": SECTIONS, "count": len(students), "students": students},
                  f, ensure_ascii=False, indent=1)
    print(f"조립 완료: {len(students)}명 → tool/students.json")
    for s in students:
        sizes = " ".join(f"{sec['key']}={len(s.get(sec['key'], ''))}자" for sec in SECTIONS)
        print(f"  {s['hakbun']} {s['name']} [{s['status']}] {sizes}")
