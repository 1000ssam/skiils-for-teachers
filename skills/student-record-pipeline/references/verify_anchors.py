#!/usr/bin/env python3
"""앵커 추적 검사 (범용) — 재구성 세특의 구체 사실이 그 학생 원문에 정박했나 (Tier-1 표면축).

원리(D3 표면축): 세특은 교과 언어로 **재구성**하므로 문장 표현·문체는 검사하지 않는다.
그러나 재구성이 클수록 스크립트가 잡을 수 있는 유일한 날조 = **구체 앵커의 발명**
(원문에 없는 고유명·사건명·수치를 세특에 씀). 해석은 자유, 사실은 정박.
ledger_verify(스팬 무결성)와 **상보적**이다: ledger는 "제출한 근거가 원문에 있나",
앵커 검사는 "세특에 등장한 구체 명사가 원문에 있나"(ledger에 안 올린 구체명도 잡는다).

⚠️ 경계(D1·D3): 이건 '우리 추출물의 무결성' 검사이지 **날조 판결이 아니다.**
   미정박 앵커 = 사람(Tier-2·교사) 확인 대상(worklist)일 뿐. 판결은 사람이 한다.

검사 범위: 결론/해석층 앞까지만(선택 --conclusion-marker). 결론층은 통설·교과 개념을
   정당하게 언급하므로(학생이 안 쓴 교과 고유명 포함) 검사하면 오탐 → 마커 앞만 본다.
매칭: 정규화 후 exact → 실패 시 동일 길이 슬라이딩 fuzzy(OCR/전사가 이름을 깨뜨림:
   을지문덕→'울리문덕', 설인귀→'설인키'). ledger_verify 의 norm/best_ratio 재사용.

─────────────────────────────────────────────────────────────────────────────
🔑 앵커 사전은 **외부 파일**이다(--anchors). 인테이크(Step1)에서 이 배치의 앵커 사전을 수집한다:
   교과서 범위·평가 스펙·정본 프레임에서 **이 과제에 나올 법한 고유명·사건명·제도명**을 모은다.
   ⚠️ **사전에 없는 앵커는 검사되지 않는다**(무검사 통과). 실증: 한 세특의 '9서당'(제도명)이
   사전 부재로 검사를 통과할 뻔함 → 그 건은 원문 실재로 판명됐으나, **사전 누락 = 사각지대**임을 각인.
   그러므로 사전 수집을 **워크플로 단계로 명시**하고, 배치 후 세특에 등장한 미등록 고유명을 사전에 환류한다.

앵커 사전 파일(JSON) 형식 — 카테고리 키는 자유, 값은 용어 리스트:
   {
     "persons":      ["김춘추", "문무왕", "을지문덕", ...],
     "places":       ["살수", "안시성", "매소성", ...],
     "institutions": ["9서당", "안동도호부", ...],
     "numeric_patterns": ["\\d{3,4}년", "\\d+만"]   ← (예약 키) 정규식. 세특에 쓰인 연도·수치도 정박 검사.
   }
   · numeric_patterns 외의 모든 리스트 값 = 리터럴 용어(카테고리 이름은 가독·감사용일 뿐 매칭엔 무관).
   · 활동 전제라 항상 등장하는 용어(예: 국명)는 넣지 않는다(전수 통과 → 노이즈).

🎯 캘리브레이션 절차(임계값·사전 신뢰 확보 — 배치 전 1회):
   ① 이미 승인된 확정본(과거 배치)으로 돌려 **오탐 0** 확인(정상 세특이 안 걸려야 함).
   ② 확정본에 날조 3종(가짜 인물·가짜 지명·가짜 수치)을 심어 돌려 **셋 다 검출** 확인.
   통과 못 하면 임계값(--threshold-*)·사전을 조정. 실제 날조 유사도(0.45~0.60) < 임계 < OCR오독 복원(0.85~0.95).

사용: python3 verify_anchors.py <records.json> <raw_dir> --anchors <anchors.json> \
        [--id-key id] [--conclusion-marker '이를 통해'] [--threshold-short 0.66] [--threshold-long 0.72] [--out ...]
  records: [{id, setuk, ...}] 또는 {records:[...]} 또는 {id: {...}}   raw_dir: <id>.txt = 그 학생 원문 전체
출력: 콘솔 요약(+ --out JSON). exit 1 = 미정박 앵커 존재.
─────────────────────────────────────────────────────────────────────────────
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 형제 모듈(ledger_verify.py)의 정규화·유사도 재사용 — 스크립트로 직접 실행돼도 찾도록 dir 주입.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger_verify import norm, best_ratio  # noqa: E402


def load_anchors(path: Path) -> tuple[list[str], list[str]]:
    """앵커 JSON → (리터럴 용어 리스트, 정규식 패턴 리스트). numeric_patterns 는 예약 키."""
    data = json.loads(path.read_text(encoding='utf-8'))
    numeric = list(data.pop('numeric_patterns', []) or [])
    terms: list[str] = []
    for v in data.values():
        if isinstance(v, list):
            terms.extend(str(x) for x in v if x)
    # 중복 제거(순서 보존)
    seen, uniq = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq, numeric


def head_part(setuk: str, marker: str | None) -> str:
    """결론/해석층 마커 앞까지만. 마커 없으면 전체(더 보수적 — 더 많이 걸림)."""
    if not marker:
        return setuk
    i = setuk.find(marker)
    return setuk if i < 0 else setuk[:i]


def find_anchors(text: str, terms: list[str], numeric: list[str]) -> list[str]:
    out = [w for w in terms if w in text]
    for pat in numeric:
        out += re.findall(pat, text)
    return sorted(set(out))


def anchored(anchor: str, nraw: str, thr_short: float, thr_long: float) -> tuple[bool, float]:
    na = norm(anchor)
    if not na:
        return True, 1.0
    if na in nraw:
        return True, 1.0
    thresh = thr_short if len(na) <= 3 else thr_long
    r, _ = best_ratio(na, nraw)
    return r >= thresh, r


def main() -> int:
    ap = argparse.ArgumentParser(description='앵커 추적 검사(범용) — 세특 구체명 ↔ 학생 원문 정박')
    ap.add_argument('records')
    ap.add_argument('raw_dir', help='<id>.txt = 그 학생 원문 전체(ledger_verify 와 같은 규약)')
    ap.add_argument('--anchors', required=True, help='앵커 사전 JSON(인테이크에서 수집)')
    ap.add_argument('--id-key', default=None, help="레코드의 학생식별 키명(기본: id/hakbun 자동)")
    ap.add_argument('--conclusion-marker', default=None,
                    help="결론/해석층 시작 마커(이 앞까지만 검사). 예: '이를 통해'. "
                         "더 견고하게는 작성 스키마가 A/B/C 경계를 반환하게 해 그걸 쓴다.")
    ap.add_argument('--threshold-short', type=float, default=0.66, help='2~3자 앵커 fuzzy 하한')
    ap.add_argument('--threshold-long', type=float, default=0.72, help='4자+ 앵커 fuzzy 하한')
    ap.add_argument('--out', default=None, help='위반 리포트 JSON 저장 경로')
    a = ap.parse_args()

    data = json.loads(Path(a.records).read_text(encoding='utf-8'))
    if isinstance(data, dict):
        recs = data['records'] if 'records' in data else list(data.values())
    else:
        recs = data
    terms, numeric = load_anchors(Path(a.anchors))
    raw_dir = Path(a.raw_dir)

    def id_of(r):
        if a.id_key:
            return str(r.get(a.id_key, ''))
        return str(r.get('id') or r.get('hakbun') or '')

    report, n_bad, n_skip = [], 0, 0
    for r in recs:
        sid = id_of(r)
        raw_file = raw_dir / f'{sid}.txt'
        if not raw_file.exists():
            n_skip += 1
            report.append(dict(id=sid, error='원문 없음(raw 파일 부재) — skip'))
            continue
        nraw = norm(raw_file.read_text(encoding='utf-8'))
        head = head_part(r.get('setuk', ''), a.conclusion_marker)
        missing = []
        for anc in find_anchors(head, terms, numeric):
            ok, ratio = anchored(anc, nraw, a.threshold_short, a.threshold_long)
            if not ok:
                missing.append(dict(anchor=anc, ratio=round(ratio, 3)))
        if missing:
            n_bad += 1
            report.append(dict(id=sid, name=r.get('name'), cls=r.get('cls'),
                               missing=missing, setuk_head=head[:200]))

    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')

    print('=== 앵커 추적 검사 (결론층 앞 구체명·수치 → 학생 원문 정박) ===')
    print(f'  대상 {len(recs)}명 · 🔴 미정박 앵커 보유 {n_bad}명 · skip(원문없음) {n_skip}명')
    if not terms:
        print('  ⚠️ 앵커 사전이 비었다 — 아무것도 검사 못 함. --anchors 확인.')
    for x in report:
        if x.get('missing'):
            names = ', '.join(f"{m['anchor']}({m['ratio']})" for m in x['missing'])
            # 레코드에 없는 필드는 None 으로 담기므로 `or ''` 로 눌러야 한다(.get 기본값은 안 먹는다).
            head = " ".join(p for p in (x.get('cls') or '', str(x['id']), x.get('name') or '') if p)
            print(f"  🔴 {head}: {names}")
    if a.out:
        print(f'  전문: {a.out}')
    return 1 if n_bad else 0


if __name__ == '__main__':
    sys.exit(main())
