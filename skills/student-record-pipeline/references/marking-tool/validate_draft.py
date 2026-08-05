#!/usr/bin/env python3
"""validate_draft.py — 화면이 쓰는 검사 껍데기. 규칙은 여기 없다.

🔑 **규칙은 `gate.py` 한 곳에만 있다.** 이 파일은 그 결과를 화면이 먹을 수 있는 JSON 으로
바꿔 줄 뿐이다. 예전에는 이 파일이 자기 규칙을 따로 갖고 있었고, 그래서 같은 원고를 두고
화면은 '통과' · 검사(gate.py)는 '하드 실패' 라고 답하는 일이 있었다 —
가운뎃점은 gate 만 잡고, 레벨 문구는 화면만 봤다(2026-08-06 실사용 지적).

🚫 **도달 수준(상/중/하) 어휘 검사는 없앴다.** 예전엔 `이를 통해`·`에서 벗어나` 같은
관용구가 있는지를 정규식으로 봤는데, 그건 **한 사람의 문체를 기계 규칙으로 굳힌 것**이라
다른 선생님이 쓰는 순간 자기 문체마다 경고가 떴다. 레벨은 계약서 §3 퓨샷의
상/중/하 예시로 가르치고, 지킴 여부는 **선생님이 검수에서** 보신다(규칙 6).

  python3 tool/validate_draft.py --text '<세특>'      # JSON
  python3 tool/validate_draft.py <학번>               # 사람이 읽는 한 줄
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import check_text, load_rules, neis_bytes, repeat_stems  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RULES = None


def rules():
    global _RULES
    if _RULES is None:
        _RULES = load_rules(os.path.join(ROOT, "draft-rules.json"))
    return _RULES


def check(text, name="", level=None):
    """화면이 먹는 모양으로 돌려준다.

    level 은 받기만 하고 쓰지 않는다 — 부르는 쪽(server.mjs)과의 하위호환용이다.
    """
    r = rules()
    text = text or ""
    hard, soft = check_text(text, r, name=name)
    def fmt(items):
        return [f"[{tag}] {msg}" for tag, msg in items]
    return {
        "bytes": neis_bytes(text),
        "byte_max": r.get("byte_max", 1500),
        "byte_short": r.get("byte_short", 0),
        "level": level or None,
        "issues": fmt(hard),
        "warns": fmt(soft),
        # 화면이 반복어를 따로 한 줄로 보여준다(위 warns 와 겹치지만 표시 자리가 다르다).
        "repeats": repeat_stems(text, r),
        "ok": not hard,
    }


def _argval(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv[:-1] else None


if __name__ == "__main__":
    if "--text" in sys.argv[:-1]:
        print(json.dumps(check(_argval("--text"), level=_argval("--level")),
                         ensure_ascii=False, indent=1))
    elif len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        hk = sys.argv[1]
        with open(os.path.join(ROOT, "out", "drafts_v3b", f"{hk}.json"), encoding="utf-8") as f:
            d = json.load(f)
        r = check(d["setuk"], d.get("name", ""))
        print(f"{hk} {d.get('name','')}: {r['bytes']}B  "
              f"{'✅ 이상 없음' if r['ok'] else '❌ ' + str(r['issues'])}")
        if r["warns"]:
            print("  ⚠️", r["warns"])
    else:
        print("usage: validate_draft.py <학번> | --text '<세특>'")
