#!/usr/bin/env python3
"""D1 증거 ledger 결정론 검증 (범용) — 헌법2 날조 가드의 기계화.

대원칙(Step5 작성 시 ledger 강제): 세특의 각 서술마다 "누가 → 누구에게/무엇을"을
학생 원문 스팬(verbatim)으로 지목하게 하고, 그 스팬이 **원문에 실제로 있는지** 여기서 대조한다.
스팬을 못 대면 그건 LLM이 채운 칸(=날조 후보)이다.

⚠️ 경계(D1·D3): 이건 '우리 추출물의 무결성' 검사이지 **날조 판결이 아니다.**
   판결은 Tier-2·교사가 한다. 여기서 내는 건 worklist(하드=사람 확인 대상)일 뿐.

🔑 OCR 노이즈 3계층 (손글씨 스캔 필수 — 순수 substring은 오탐):
   손글씨 OCR은 **같은 문서 안에서도 같은 단어를 다르게 깨뜨린다**(예: '안동도호부'가 '안동도토부'로).
   그래서 verbatim 스팬조차 원문과 글자가 어긋날 수 있다. 3계층으로 가른다:
     exact  ✅ 정규화 후 그대로 있음
     fuzzy  ⚠️ 근사 일치(≥THRESH) = OCR 오독 복원으로 추정 → advisory(Tier-2 확인거리)
     miss   🔴 유사 구간조차 없음 = 채운 칸 → 하드(사람 확인)
   임계값은 실물 저격으로 보정(실제 날조 0.45~0.60 < THRESH < OCR오독 복원 0.85~0.95).

입력:
  drafts.json : [{ "id": <학생식별>, "ledger": [{"claim":..,"span":..,"source":..}], ... }, ...]
  raw_dir     : <id>.txt = 그 학생의 원문(p3+p4 등 전체 concat). 파일 없으면 그 학생은 skip
                (디지털 외부원천·백지 등 로컬 원문이 없는 케이스 → --require-all 로 강제 가능).
사용:
  python3 ledger_verify.py drafts.json raw_dir/ [--id-key id] [--threshold 0.72]
"""
import argparse, json, re, sys, unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def norm(s: str) -> str:
    """공백·구두점 제거 정규화 — OCR 원문은 띄어쓰기·줄바꿈이 깨져 있다."""
    s = unicodedata.normalize('NFKC', s or '')
    return re.sub(r'[\s.,\-–—~:：;()\[\]<>*※★@#/\\|"\'`·]+', '', s)


def best_ratio(span: str, raw: str) -> tuple:
    """raw 안에서 span과 가장 닮은 구간의 유사도(슬라이딩 창). OCR 오독 허용용."""
    if not span:
        return 0.0, ''
    L = len(span)
    if L > len(raw):
        return SequenceMatcher(None, span, raw).ratio(), raw
    best, at, step = 0.0, '', (1 if len(raw) < 4000 else 2)
    sm = SequenceMatcher()
    sm.set_seq2(span)
    for i in range(0, len(raw) - L + 1, step):
        w = raw[i:i + L]
        sm.set_seq1(w)
        if sm.quick_ratio() < best:
            continue
        r = sm.ratio()
        if r > best:
            best, at = r, w
        if best >= 0.995:
            break
    return best, at


# 근거가 **학생 원문에서만** 오는 게 아니다. 계약서 §4 스키마가 "근거가 된 하이라이트 또는
# '교사 지정 왜·역량'"을 허용하고, 마킹 화면(mark.html)은 이미 그런 스팬을
# '교사 요구사항(원문 근거 없음)'으로 갈라 표시한다. 여기서도 같은 규약을 따른다.
#
# 안 그러면 세특이 거의 항상 "~활동에서"로 열리므로 그 근거(활동맥락)가 **학생마다 1건씩**
# 🔴 로 뜬다. 171명이면 가짜 경보 171개고, 진짜 날조가 그 사이에 묻힌다.
TEACHER_PREFIXES = ('기타 요구사항', '교사 지정', '교사 요구사항', '활동맥락')
TEACHER_SOURCES = ('context', '활동맥락', '교사지정', '교사 지정', 'teacher', 'extra')


def teacher_origin(entry, student_sources=None):
    """이 근거가 학생 원문이 아니라 교사가 준 것인가. (스팬 접두사 또는 source 필드로 판정)"""
    span = (entry.get('span') or '').lstrip()
    if any(span.startswith(p) for p in TEACHER_PREFIXES):
        return True
    src = (entry.get('source') or '').strip()
    if not src:
        return False
    if student_sources:                      # 학생 페이지 키를 프로젝트가 선언했으면 그 밖은 전부 교사 출처
        return src not in student_sources
    return src.lower() in [s.lower() for s in TEACHER_SOURCES]


def verify(drafts, raw_of, threshold=0.72, min_span=8, require_all=False, student_sources=None):
    report = []
    n_ok = n_fuzzy = n_bad = n_skip = n_teacher = 0
    for d in drafts:
        sid = d.get('id') or d.get('학생식별') or d.get('hakbun')
        raw = raw_of(sid)
        if raw is None:
            if require_all:
                report.append(dict(id=sid, error='원문 없음(require-all)')); n_bad += 1
            else:
                n_skip += 1
            continue
        nraw = norm(raw)
        hard, soft = [], []
        ledger = d.get('ledger') or []
        if not ledger:
            hard.append(dict(claim='(ledger 미제출)', span='', ratio=0.0, reason='증거 자체가 없음'))
        for e in ledger:
            span = (e.get('span') or '').strip()
            claim = e.get('claim', '')
            if not span:
                hard.append(dict(claim=claim, span='', ratio=0.0, reason='스팬 공란')); continue
            if teacher_origin(e, student_sources):
                # 학생 원문에 없는 게 정상이다 — 대조하지 않고 따로 센다.
                # (교사가 준 사실이 맞게 쓰였는지는 사람 Tier-2 가 본다. 기계가 판결할 축이 아니다.)
                n_teacher += 1
                continue
            if len(norm(span)) < min_span:
                soft.append(dict(claim=claim, span=span, ratio=1.0, reason=f'스팬 과소({len(norm(span))}<{min_span}자) — 근거 약함')); continue
            ns = norm(span)
            if ns in nraw:
                continue
            r, at = best_ratio(ns, nraw)
            row = dict(claim=claim, span=span, ratio=round(r, 3), matched=at[:60])
            if r >= threshold:
                soft.append({**row, 'reason': f'⚠️ 근사 {r:.2f} — OCR 오독 복원 추정'})
            else:
                hard.append({**row, 'reason': f'🔴 유사구간 없음({r:.2f}) = 채운 칸'})
        if hard:
            n_bad += 1
        elif soft:
            n_fuzzy += 1
        else:
            n_ok += 1
        if hard or soft:
            report.append(dict(id=sid, hard=hard, soft=soft))
    return report, dict(exact=n_ok, fuzzy=n_fuzzy, hard=n_bad, skip=n_skip, teacher=n_teacher)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drafts')
    ap.add_argument('raw_dir')
    ap.add_argument('--id-key', default=None, help='드래프트의 학생식별 키명(기본: id/학생식별/hakbun 자동)')
    ap.add_argument('--threshold', type=float, default=0.72, help='fuzzy 하한(실물 보정값)')
    ap.add_argument('--min-span', type=int, default=8)
    ap.add_argument('--require-all', action='store_true', help='원문 없는 학생도 하드 처리')
    ap.add_argument('--out', default=None, help='위반 리포트 JSON 저장 경로')
    ap.add_argument('--student-sources', default=None,
                    help="학생 원문 페이지 키(쉼표구분, 예: p3,p4). 주면 그 밖의 source 는 전부 교사 출처로 보고 원문 대조에서 제외한다.")
    a = ap.parse_args()

    drafts = json.load(open(a.drafts, encoding='utf-8'))
    if isinstance(drafts, dict):
        drafts = list(drafts.values())
    if a.id_key:
        for d in drafts:
            d.setdefault('id', d.get(a.id_key))
    raw_dir = Path(a.raw_dir)

    def raw_of(sid):
        p = raw_dir / f'{sid}.txt'
        return p.read_text(encoding='utf-8') if p.exists() else None

    ss = [x.strip() for x in a.student_sources.split(',')] if a.student_sources else None
    report, stat = verify(drafts, raw_of, a.threshold, a.min_span, a.require_all, ss)
    if a.out:
        json.dump(report, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('=== D1 증거 ledger 검증 ===')
    print(f"  ✅ exact {stat['exact']} · ⚠️ fuzzy {stat['fuzzy']} · 🔴 hard {stat['hard']} · skip {stat['skip']}"
          + (f" · 📌 교사출처 {stat['teacher']}(원문 대조 대상 아님)" if stat.get('teacher') else ""))
    for r in report:
        if r.get('error'):
            print(f"  ⚠️ {r['id']} — {r['error']}"); continue
        if not r.get('hard'):
            continue
        print(f"\n  🔴 {r['id']}")
        for v in r['hard']:
            print(f"     {v['reason']}")
            print(f"       주장: {v['claim'][:72]}")
            if v['span']:
                print(f"       스팬: {v['span'][:72]}")
    return 1 if stat['hard'] else 0


if __name__ == '__main__':
    sys.exit(main())
