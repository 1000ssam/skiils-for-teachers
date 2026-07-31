#!/usr/bin/env python3
"""대기열 규칙(pending.py) 검사 — 이 규칙이 틀리면 확정본이 조용히 덮어써진다.

  python3 tool/test_pending.py
"""
import os, sys, json, time, tempfile, importlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pending as P

TMP = tempfile.mkdtemp(prefix="pending-test-")
P.M = os.path.join(TMP, "marks"); P.D = os.path.join(TMP, "drafts")
os.makedirs(P.M); os.makedirs(P.D)

def iso(offset_s):
    return datetime.fromtimestamp(time.time() + offset_s, tz=timezone.utc).isoformat().replace("+00:00", "Z")

def mark(hk, *, done=True, approved=False, material_at=None, mtime_offset=0, **extra):
    p = os.path.join(P.M, f"{hk}.json")
    rec = {"hakbun": hk, "done": done, "approved": approved, **extra}
    if material_at is not None: rec["material_at"] = material_at
    json.dump(rec, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    if mtime_offset: os.utime(p, (time.time() + mtime_offset,) * 2)
    return p

def draft(hk, mtime_offset=0):
    p = os.path.join(P.D, f"{hk}.json")
    json.dump({"setuk": "…함."}, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    if mtime_offset: os.utime(p, (time.time() + mtime_offset,) * 2)
    return p

fails = 0
def t(name, cond):
    global fails
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond: fails += 1

# ── 기본 3조건 ────────────────────────────────────────────────────────────
mark("10001", done=False);                       draft("10001", -60)   # 요청 안 함
mark("10002", material_at=iso(-120));                                  # 요청, 초안 없음
mark("10003", material_at=iso(-120));            draft("10003", -60)   # 초안이 더 최신
mark("10004", material_at=iso(-30));             draft("10004", -60)   # 마킹 재료가 더 최신
mark("10005", approved=True, material_at=iso(-30)); draft("10005", -60) # 확정 = 완료

got = set(P.pending())
print("\n[대기열 기본 규칙]")
t("초안 요청 안 한 학생은 제외", "10001" not in got)
t("요청했고 초안 없으면 포함", "10002" in got)
t("초안이 재료보다 최신이면 제외", "10003" not in got)
t("재료가 초안보다 최신이면 포함(=[다시]·마킹 수정)", "10004" in got)
t("확정은 재료가 최신이어도 제외 — 이 줄이 없으면 확정본이 계속 다시 그려진다", "10005" not in got)

mark("10006", held=True, material_at=iso(-30)); draft("10006", -60)   # 보류 = 판정을 미룸
mark("10007", held=False, material_at=iso(-30)); draft("10007", -60)  # 보류 해제 = 평소대로
got = P.pending()
t("보류는 재료가 최신이어도 제외 — 렌더 낭비 + 미뤄 둔 문장이 덮어써진다", "10006" not in got)
t("보류 해제하면 평소 규칙으로 돌아온다", "10007" in got)

# ── material_at 이 mtime 을 이긴다 ────────────────────────────────────────
# 확정·반려 기록·git checkout 처럼 재료와 무관한 쓰기로 mtime 만 최신이 된 상황.
mark("10006", material_at=iso(-300));            draft("10006", -120)
os.utime(os.path.join(P.M, "10006.json"), (time.time(), time.time()))   # 방금 파일만 다시 씀
got = set(P.pending())
print("\n[material_at 우선] 재료와 무관한 파일 쓰기가 재렌더를 유발하지 않는가")
t("mtime 만 최신이고 재료는 옛날이면 제외", "10006" not in got)

# ── 레거시(도입 전 마킹) 폴백 ─────────────────────────────────────────────
mark("10007", mtime_offset=-300);                draft("10007", -120)   # material_at 없음
mark("10008", mtime_offset=-30);                 draft("10008", -120)
got = set(P.pending())
print("\n[레거시 폴백] material_at 없는 기존 마킹은 mtime 규칙 그대로")
t("mtime 이 초안보다 옛날이면 제외", "10007" not in got)
t("mtime 이 초안보다 최신이면 포함", "10008" in got)

# ── 깨진 파일·언더스코어 ─────────────────────────────────────────────────
open(os.path.join(P.M, "_context.json"), "w").write('{"context":"x"}')
open(os.path.join(P.M, "10009.json"), "w").write("{깨진 JSON")
got = P.pending()
print("\n[내구성]")
t("_로 시작하는 파일은 건너뜀", "_context" not in got)
t("깨진 JSON 은 대기열을 멈추지 않음", "10009" not in got)
t("결과는 정렬됨", got == sorted(got))

print(f"\n실패 {fails}건" if fails else "\n전부 통과")
sys.exit(1 if fails else 0)
