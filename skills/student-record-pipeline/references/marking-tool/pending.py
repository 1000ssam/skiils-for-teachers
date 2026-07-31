#!/usr/bin/env python3
"""렌더가 필요한 학번을 한 줄씩 출력 — 대기열 규칙의 단일 출처.

  ① done=true (= 화면의 '초안 요청')
  ② approved 아님 — [확정]은 완료다. 승인도 파일 쓰기라 이 줄이 없으면 확정한 학생이
     mtime 갱신 때문에 대기열에 재진입해 계속 다시 그려진다.
  ③ 초안이 없거나, 마킹의 **재료**가 초안보다 최신

③의 기준은 파일 mtime 이 아니라 레코드의 `material_at`(있을 때)이다.
mtime 은 재료와 무관한 쓰기에도 갱신된다 — 확정/확정취소/반려 기록, git checkout,
파일 복사. 그걸 '마킹이 바뀌었다'로 읽으면 확정본이 조용히 덮어써진다.
`material_at` 은 화면이 **하이라이트·왜·역량·레벨이 실제로 바뀌었을 때만** 찍는다.
([다시]도 명시적으로 찍는다 — 다시 그리라는 요청이므로.)
없는 레코드(도입 전 마킹)는 기존대로 mtime 으로 판정한다.

화면(mark.html)은 이 규칙을 재구현하지 않고 /pending 으로 이 스크립트를 부른다.
"""
import os, json, glob
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(ROOT, "out", "marks")
D = os.path.join(ROOT, "out", "drafts_v3b")

def material_ms(mark, path):
    """이 마킹의 '재료'가 마지막으로 바뀐 시각(ms). 없으면 파일 mtime 으로 폴백."""
    at = mark.get("material_at")
    if at:
        try:
            return datetime.fromisoformat(str(at).replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            pass
    return os.path.getmtime(path) * 1000

def pending():
    out = []
    for f in glob.glob(os.path.join(M, "*.json")):
        b = os.path.basename(f)
        if b.startswith("_"): continue
        try: m = json.load(open(f, encoding="utf-8"))
        except Exception: continue
        if not m.get("done"): continue
        if m.get("approved"): continue
        # 보류 = 교사가 판정을 미뤘다. 다시 그려도 교사가 아직 안 정한 건 그대로다 —
        # 렌더만 낭비하고, 미뤄 둔 그 문장이 덮어써져 되돌아볼 수도 없게 된다.
        if m.get("held"): continue
        hk = b[:-5]
        dj = os.path.join(D, f"{hk}.json")
        if not os.path.exists(dj):
            out.append(hk); continue
        if material_ms(m, f) > os.path.getmtime(dj) * 1000:
            out.append(hk)
    return sorted(out)

if __name__ == "__main__":
    print("\n".join(pending()))
