#!/usr/bin/env python3
"""옆줄 대조표 생성 (범용) — 세특↔근거스팬 병렬표 = 사람 Tier-2의 핵심 산출물.

무엇을/왜: 각 세특 문장 옆에 그 문장의 근거 스팬(학생 원문 verbatim)을 나란히 놓아,
교사가 원문 전체를 뒤지지 않고 **두 줄만 보고 대조**하게 한다. 이것이 상시 AI Tier-2를
대체하는 무료·고정밀 검수 장치다(DESIGN-DECISIONS D4). 결정론 검증(ledger_verify·verify_anchors)이
"스팬이 원문에 있나"까지 봤다면, 이 표는 사람이 "스팬이 그 문장을 **정말 뒷받침하나**(방향·주체·인과)"를 본다.
  실증: "대동강 이남을 넘겨받고" ↔ 스팬 "당나라형씨들은 대동강 이남지역을 가져가세요"
       → 방향 뒤집힘이 옆줄에서 즉시 보임(스팬은 원문에 실재하므로 결정론은 통과, 사람만 잡음).

표기 규칙:
  · 근거 스팬 있음    → 스팬을 그대로 병기(source 라벨 첨자).
  · 결론/해석층 문장   → ⓘ (스팬 부재가 정상 — 통설·②항 재구성).      [마커: --conclusion-marker]
  · 도입/요약 문장     → ⓘ (근거는 뒤 문장 스팬이 담당하는 구조).       [범위: --head-sentences]
  · 그 외 스팬 없는 문장 → ⚠️ **우선 확인**(빈 목적어 칸 채우기 후보 = 최다 날조 지점).

─────────────────────────────────────────────────────────────────────────────
일반화 노트(도메인 결합부):
  · 골격 마커(결론층 시작·도입 문장 범위)를 **파라미터**로 뺐다(도메인은 '이를 통해'·첫 문장 하드코딩).
  · 더 견고한 대안: 작성 스키마가 A/B/C 경계를 직접 반환하게 하고(레코드에 `segments`) 그걸 쓰기.
    이 스크립트는 레코드에 `segments`(문장 인덱스 라벨링)가 있으면 우선 사용, 없으면 마커 휴리스틱.
  · id/axis 등 도메인 필드는 선택 처리(있으면 표시, 없으면 생략).
─────────────────────────────────────────────────────────────────────────────

사용: python3 make_review_table.py <records.json> [-o out/review.md]
        [--id-key id] [--conclusion-marker '이를 통해'] [--head-sentences 1] [--compare <prev_dir>]
  records: [{id, name, setuk, ledger:[{claim,span,source}], ...}] 또는 {records:[...]}
  --compare <dir>: 이전 버전 개별 JSON(<id>.json, {setuk, axis?}) 을 각 학생 하단에 접이식 병기.
출력: 마크다운 대조표 + ⚠️(스팬 없는 문장) 건수 요약.
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # deep/ → references/
from neis_bytes import neis_bytes  # 바이트는 단일 출처 — UTF-8 길이가 아니라 NEIS 규칙(비ASCII=3)

# 이 밑으로 떨어지는 배정은 '근거로 안 친다'. 하한이 없으면 유사도가 0에 가까워도 어딘가엔 붙어,
# ⚠️(스팬 없음)로 떠야 할 문장을 '근거 있음'으로 **가리는** 방향의 오류가 난다(사람 Tier-2 무력화).
ASSIGN_MIN = 0.25


def sentences(setuk: str) -> list[str]:
    parts = re.split(r'(?<=\.)\s+', (setuk or '').strip())
    return [p.strip() for p in parts if p.strip()]


def assign(entries: list[dict], sents: list[str], min_ratio: float = ASSIGN_MIN) -> tuple[dict, list]:
    """각 ledger 엔트리를 claim과 가장 닮은 세특 문장에 배정. 하한 미달은 미배정으로 뺀다."""
    out: dict = {i: [] for i in range(len(sents))}
    orphans: list = []
    for e in entries:
        claim = e.get('claim', '')
        best, at = -1.0, 0
        for i, s in enumerate(sents):
            r = SequenceMatcher(None, claim, s).ratio()
            if r > best:
                best, at = r, i
        if best < min_ratio:
            orphans.append((e, best))
        else:
            out[at].append(e)
    return out, orphans


def is_head(i: int, rec: dict, head_n: int) -> bool:
    """도입/요약 문장인가. segments 가 있으면 그걸, 없으면 앞 head_n 문장."""
    seg = rec.get('segments')
    if isinstance(seg, dict) and 'head_indices' in seg:
        return i in seg['head_indices']
    return i < head_n


def is_conclusion(i: int, sent: str, rec: dict, marker: str | None) -> bool:
    """결론/해석층 문장인가. segments 우선, 없으면 마커 prefix."""
    seg = rec.get('segments')
    if isinstance(seg, dict) and 'conclusion_indices' in seg:
        return i in seg['conclusion_indices']
    return bool(marker) and sent.startswith(marker)


def render_student(rec: dict, id_key: str, marker: str | None, head_n: int, prev: dict | None) -> str:
    sid = rec.get(id_key) or rec.get('id') or rec.get('hakbun') or ''
    name = rec.get('name', '')
    cls = rec.get('cls', '')
    setuk = rec.get('setuk', '')
    sents = sentences(setuk)
    lg, orphans = assign(rec.get('ledger') or [], sents)
    b = neis_bytes(setuk)

    axis_part = f"축{rec['axis']} · " if rec.get('axis') else ''
    lines = [f"## {cls} {sid} {name} — {axis_part}{b}B", '']
    if rec.get('fact_error_avoided'):
        lines += [f"> 🔴 A안 우회 신고: {rec['fact_error_avoided']}", '']
    lines += ['| 세특 문장 | 근거 스팬 (학생 원문 그대로) |', '|---|---|']
    for i, s in enumerate(sents):
        spans = lg.get(i) or []
        if spans:
            cell = '<br>'.join(f"「{e.get('span', '')}」 <sub>{e.get('source', '')}</sub>" for e in spans)
        elif is_conclusion(i, s, rec, marker):
            cell = 'ⓘ 결론/해석층 (스팬 없음 정상 가능)'
        elif is_head(i, rec, head_n):
            cell = 'ⓘ 도입/요약 문장 — 아래 근거 스팬으로 대조'
        else:
            cell = '⚠️ **근거 스팬 없음 — 우선 확인**'
        # 표 셀 안전: 파이프·개행 이스케이프
        s_cell = s.replace('|', '\\|')
        cell = cell.replace('\n', ' ')
        lines.append(f"| {s_cell} | {cell} |")
    if orphans:
        # 어느 문장도 뒷받침하지 않는 근거 = 조용히 붙이면 오히려 ⚠️ 를 가린다. 따로 세워 보여준다.
        lines += ['', '> 🔻 **어느 문장에도 못 붙은 근거** — 세특이 이 근거를 실제로 쓰지 않았거나, '
                      '문장이 근거에서 멀어진 것. 둘 다 확인 대상.']
        for e, r in orphans:
            lines.append(f"> - 「{e.get('span','')}」 <sub>{e.get('source','')}</sub> "
                         f"(주장: {e.get('claim','')} · 최대유사도 {r:.2f})")
    if prev:
        pb = neis_bytes(prev.get('setuk', ''))
        pax = f"축{prev['axis']} · " if prev.get('axis') else ''
        lines += ['', f"<details><summary>이전 버전 ({pax}{pb}B)</summary>", '',
                  prev.get('setuk', ''), '', '</details>']
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description='옆줄 대조표(사람 Tier-2) 생성')
    ap.add_argument('records')
    ap.add_argument('-o', '--out', default='out/review.md')
    ap.add_argument('--id-key', default='id')
    ap.add_argument('--conclusion-marker', default=None,
                    help="결론/해석층 문장 시작 마커(스팬 부재 정상 처리). 예: '이를 통해'")
    ap.add_argument('--head-sentences', type=int, default=1,
                    help='도입/요약으로 취급할 앞 문장 수(스팬 부재 정상 처리)')
    ap.add_argument('--compare', default=None, help='이전 버전 개별 JSON 디렉토리(<id>.json)')
    a = ap.parse_args()

    data = json.loads(Path(a.records).read_text(encoding='utf-8'))
    if isinstance(data, dict):
        recs = data['records'] if 'records' in data else list(data.values())
    else:
        recs = data

    blocks = ['# 세특 옆줄 대조표 (교사 검수)', '',
              '각 문장 옆의 스팬(학생 원문 verbatim)과 대조하세요. '
              '스팬이 문장을 **정말 뒷받침하는지**(방향·주체·인과) 확인이 핵심. '
              '⚠️=스팬 없는 문장(우선 확인) · ⓘ=스팬 부재 정상.', '']
    n_warn = 0
    for r in recs:
        prev = None
        if a.compare:
            sid = r.get(a.id_key) or r.get('id') or r.get('hakbun') or ''
            p = Path(a.compare) / f'{sid}.json'
            if p.exists():
                prev = json.loads(p.read_text(encoding='utf-8'))
        block = render_student(r, a.id_key, a.conclusion_marker, a.head_sentences, prev)
        n_warn += block.count('⚠️ **근거 스팬 없음')
        blocks.append(block)

    Path(a.out).write_text('\n'.join(blocks), encoding='utf-8')
    print(f"{a.out} — {len(recs)}명, ⚠️ 스팬 없는 문장 {n_warn}건")


if __name__ == '__main__':
    main()
