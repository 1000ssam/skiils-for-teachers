#!/usr/bin/env python3
"""Step 3 매핑 (범용) — 스캔 낱장 → 학생. 헌법 1 의 기계화.

왜 이 파일이 있나: `build_students.py` 는 `out/mapping_reconciled.csv` 를 **입력으로 전제**하는데,
그 CSV 를 만드는 도구가 없어 배치마다 새로 짜야 했다. 그런데 이 단계는 순진하게 짜면 **조용히
틀린다** — 낱장이 빠진 반에서 파일 순서대로 zip 하면 결손 지점 이후 전원이 한 칸씩 밀려
**전수 오매핑**이 된다(실측: 28명 반에 52쪽 → 26명분). 그래서 코드로 고정한다.

신호 셋을 독립으로 뽑아 결합한다(헌법 1 의 3중 대조).
  ① 위치 prior : 스캔 연번. **단조성 제약으로만** 쓰고 1:1 zip 은 하지 않는다.
  ② 학번       : 자필 헤더 OCR (실측 정확일치 ~70%).
  ③ 이름       : 자필 헤더 OCR (실측 정확일치 ~62%, 그 밖 25%는 명렬표에 없는 오독
                 — 받침 한 글자가 어긋나 '○○연'이 '○○면'으로 읽히는 식 → 반 명렬표 대상
                 fuzzy 로 복원. 이때 오독값은 명렬표에 **실재하지 않으므로** 오매핑이 아니다).

정렬은 **단조성 보존 DP**(로스터 쪽 gap = 미제출). 그 뒤 두 보정을 얹는다.
  · 순서 이탈 구제 — 스캔이 제자리를 벗어나면 단조 DP 는 못 붙인다. 학번·이름이 **둘 다 정확일치**
    할 때만 구제하고, 위치가 어긋났으므로 ⚠️ 로 남겨 사람에게 넘긴다.
  · 구조적 확정(샌드위치) — 신호가 없는 학생도 앞뒤가 확정이고 연번이 감싸면 다른 학생이 들어올
    자리가 없다. **자동 확정하지 않고**(신호 부재 ≠ 3중 일치) 교사가 초 단위로 승인하도록 근거만 붙인다.

같이 수행하는 것 — **백지 게이트**(no-fab 최전선). 손글씨 활동지는 학생이 한 글자도 안 써도
인쇄된 양식 문구가 OCR 에 잡혀 순수 char-count 로는 백지가 50~80자로 보인다. 그대로 작성에
넣으면 미제출자에게 세특을 발명한다. 그래서 양식 문구를 정규식으로 걷어내고 **학생 실기재량**을
잰 뒤, 양식 앵커 유무로 백지(앵커 있음)와 OCR붕괴(앵커조차 없음)를 가른다.

사용:
    python3 map_pages.py [--config mapping-config.json] [--root <프로젝트루트>]
설정 파일이 이 배치의 활동지 형태를 공급한다(mapping-config.example.json 참조).
스킬에 양식 문구·칸 구성을 박지 않는다 — 과제마다 다르다.

출력:
    out/mapping_reconciled.csv  build_students.py 입력 (순서,반,학번,이름,<페이지키>...,상태,재료)
    out/mapping_review.md       교사 검수 테이블 전량
    stdout                      요약 + 사람이 봐야 하는 건(hold)만
"""
import argparse, collections, csv, json, os, re, sys
from difflib import SequenceMatcher

NAME_FUZZ = 0.60      # 이름 fuzzy 하한
NAME_MARGIN = 0.08    # 최적-차선 간격(좁으면 모호로 처리)
GAP_ROSTER, GAP_GROUP = -0.5, -2.0


def load_config(root, path):
    p = path if os.path.isabs(path) else os.path.join(root, path)
    if not os.path.exists(p):
        sys.exit(f"설정 파일이 없습니다: {p}\n"
                 f"  스킬의 references/mapping-config.example.json 을 복사해 이 배치에 맞게 채우십시오.\n"
                 f"  (활동지 칸 구성·양식 문구는 과제마다 달라 스킬이 추측하지 않습니다.)")
    cfg = json.load(open(p, encoding="utf-8"))
    cfg.setdefault("roster", "out/roster.csv")
    cfg.setdefault("clean_dir", "out/clean")
    cfg.setdefault("scan_pattern", r"(\d+)\s*\.txt$")
    cfg.setdefault("header_lines", 6)
    cfg.setdefault("id_pattern", r"1[0-9]{4}")
    cfg.setdefault("name_labels", ["이름"])
    cfg.setdefault("id_labels", ["학번"])
    cfg.setdefault("boilerplate", [])
    cfg.setdefault("blank_chars", 15)
    cfg.setdefault("thin_chars", 120)
    cfg.setdefault("columns", {})
    if not cfg.get("pages"):
        sys.exit("설정에 pages 가 없습니다 — 활동지 낱장 구성(키·판별 문구)을 정의해야 합니다.")
    return cfg


class Batch:
    def __init__(self, root, cfg):
        self.root, self.cfg = root, cfg
        self.clean = os.path.join(root, cfg["clean_dir"])
        self.keys = [p["key"] for p in cfg["pages"]]
        self.boiler = [re.compile(p) for p in cfg["boilerplate"]]
        c = cfg["columns"]
        self.col_order = c.get("order", "순서")
        self.col_cls = c.get("cls", "반")
        self.col_id = c.get("id", "학번")
        self.col_name = c.get("name", "이름")

    # ── 낱장 역할 판정 : 인쇄된 양식 문구로 가른다(학생 필적과 무관해 안정적) ──────
    def role_of(self, body):
        hits = [p["key"] for p in self.cfg["pages"]
                if any(m in body for m in p.get("markers", []))]
        return hits[0] if len(hits) == 1 else None

    # ── 헤더에서 학번·이름 추출 (칸 바꿔쓰기까지 흡수) ──────────────────────────
    def extract(self, head):
        names, ids = [], []
        idp = self.cfg["id_pattern"]
        for lab in self.cfg["name_labels"] + self.cfg["id_labels"]:   # 라벨 바꿔 쓴 경우까지
            names += re.findall(lab + r'[^가-힣0-9\n]{0,12}([가-힣]{2,4})', head)
        for lab in self.cfg["id_labels"] + self.cfg["name_labels"]:
            ids += re.findall(lab + r'[^0-9\n]{0,12}(\d{4,6})', head)
        ids += re.findall(r'\b(' + idp + r')\b', head)
        return names, ids

    def scan_no(self, fn):
        m = re.search(self.cfg["scan_pattern"], fn)
        return int(m.group(1)) if m else None

    # ── 백지 게이트 ──────────────────────────────────────────────────────────
    def student_chars(self, rel):
        """(양식 앵커 수, 학생 실기재량). 앵커 0 = 그 페이지를 못 읽은 것(백지가 아니다)."""
        if not rel:
            return 0, 0
        p = os.path.join(self.clean, rel)
        if not os.path.exists(p):
            return 0, 0
        anchors, kept = 0, []
        for line in open(p, encoding="utf-8"):
            if any(rx.match(line) for rx in self.boiler):
                anchors += 1
            else:
                kept.append(line)
        return anchors, len(re.sub(r'\s', '', "".join(kept)))


def ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def best_name(cands, roster_names):
    best, second = (0.0, None), 0.0
    for c in cands:
        for rn in roster_names:
            r = 1.0 if c == rn else ratio(c, rn)
            if r > best[0]:
                second, best = best[0], (r, rn)
            elif r > second:
                second = r
    if best[0] >= NAME_FUZZ and (best[0] - second) >= NAME_MARGIN:
        return best[1], best[0]
    return None, best[0]


def build_groups(B, cls):
    """낱장을 학생 묶음으로. pages[0] 을 만나면 새 묶음을 연다."""
    d = os.path.join(B.clean, cls)
    scans, digitals = [], []
    for fn in os.listdir(d):
        (scans if B.scan_no(fn) is not None else digitals).append(fn)
    scans.sort(key=B.scan_no)
    first = B.keys[0]

    groups, cur = [], None

    def new_group():
        g = {k: None for k in B.keys}
        g.update(names=[], ids=[], note=[])
        groups.append(g)
        return g

    for fn in scans:
        body = open(os.path.join(d, fn), encoding="utf-8").read()
        role = B.role_of(body)
        head = "\n".join(body.split("\n")[:B.cfg["header_lines"]])
        nm, ids = B.extract(head)

        if role == first or (role is None and (cur is None or all(cur[k] for k in B.keys))):
            cur = new_group()
            slot = first
        elif role:
            if cur is None:
                cur = new_group()
            slot = role
        else:
            slot = next((k for k in B.keys if not cur[k]), B.keys[-1])
            cur["note"].append(f"{fn} 역할판정 실패")
        if cur[slot]:
            cur["note"].append(f"{slot} 중복({cur[slot]}→{fn})")
        cur[slot] = fn
        cur["names"] += nm
        cur["ids"] += ids
    return groups, digitals


def score(g, s, roster_names, B):
    sc, why = 0.5, []
    sid, snm = s[B.col_id], s[B.col_name]
    if any(h == sid for h in g["ids"]):
        sc += 3; why.append("학번=")
    elif any(len(h) == len(sid) and sum(a != b for a, b in zip(h, sid)) == 1 for h in g["ids"]):
        sc += 1; why.append("학번≈")
    if any(n == snm for n in g["names"]):
        sc += 2; why.append("이름=")
    else:
        nm, r = best_name(g["names"], roster_names)
        if nm == snm:
            sc += 1; why.append(f"이름≈{r:.2f}")
    return sc, why


def align(groups, students, roster_names, B):
    n, m = len(groups), len(students)
    S = [[score(groups[i], students[j], roster_names, B) for j in range(m)] for i in range(n)]
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP_GROUP
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP_ROSTER
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = max(dp[i - 1][j - 1] + S[i - 1][j - 1][0],
                           dp[i - 1][j] + GAP_GROUP,
                           dp[i][j - 1] + GAP_ROSTER)
    i, j, out = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(dp[i][j] - (dp[i - 1][j - 1] + S[i - 1][j - 1][0])) < 1e-9:
            out.append((i - 1, j - 1, S[i - 1][j - 1][1])); i, j = i - 1, j - 1
        elif i > 0 and abs(dp[i][j] - (dp[i - 1][j] + GAP_GROUP)) < 1e-9:
            out.append((i - 1, None, [])); i -= 1
        else:
            out.append((None, j - 1, [])); j -= 1
    return list(reversed(out))


def main():
    ap = argparse.ArgumentParser(description="Step3 매핑 — 스캔 낱장을 명렬표 정본에 3중 대조로 붙인다(헌법 1).")
    ap.add_argument("--config", default="mapping-config.json")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    cfg = load_config(root, a.config)
    B = Batch(root, cfg)

    rows = list(csv.DictReader(open(os.path.join(root, cfg["roster"]), encoding="utf-8-sig")))
    by_cls = collections.defaultdict(list)
    for r in rows:
        by_cls[r[B.col_cls].strip()].append({k.strip(): (v or "").strip() for k, v in r.items()})

    out_rows, review, summary, holds = [], [], collections.Counter(), []

    def cls_key(c):
        m = re.search(r'(\d+)\s*$', c)
        return (c[:m.start()] if m else c, int(m.group(1)) if m else 0)

    for cls in sorted(by_cls, key=cls_key):
        students = by_cls[cls]
        roster_names = [s[B.col_name] for s in students]
        id_index = {s[B.col_id]: s[B.col_name] for s in students}
        groups, digitals = build_groups(B, cls)

        # 디지털 제출: 파일명에 이름이 있어 스캔 순서와 무관하게 직접 정박
        direct = {}
        for fn in digitals:
            nm, _ = best_name([fn.split("_")[0]], roster_names)
            key = next((k for k in B.keys if f"_{k}" in fn), B.keys[0])
            if nm:
                direct.setdefault(nm, {k: None for k in B.keys})[key] = fn
            else:
                holds.append((cls, "-", "-", f"디지털 파일 이름 미확인: {fn}", "❓오독"))

        seq = [s for s in students if s[B.col_name] not in direct]
        res, spare_g, unmatched_s = {}, [], []
        for gi, sj, why in align(groups, seq, roster_names, B):
            if sj is None:
                spare_g.append(gi); continue
            s = seq[sj]
            if gi is None:
                unmatched_s.append(s)
            else:
                res[s[B.col_name]] = (groups[gi], why)

        for s in list(unmatched_s):                     # 순서 이탈 구제
            for gi in list(spare_g):
                g = groups[gi]
                if any(h == s[B.col_id] for h in g["ids"]) and any(n == s[B.col_name] for n in g["names"]):
                    res[s[B.col_name]] = (g, ["학번=", "이름=", "순서이탈"])
                    spare_g.remove(gi); unmatched_s.remove(s); break
        for gi in spare_g:
            g = groups[gi]
            pages = "/".join(str(g[k]) for k in B.keys)
            holds.append((cls, "-", "-", f"학생에 못 붙은 스캔 {pages} "
                                         f"학번{sorted(set(g['ids']))} 이름{sorted(set(g['names']))}", "🚩여분"))

        placed = {s[B.col_id] for s in students if s[B.col_name] in res or s[B.col_name] in direct}

        for s in students:
            nm, sid = s[B.col_name], s[B.col_id]
            if nm in direct:
                g = dict(direct[nm]); g.update(names=[nm], ids=[], note=["디지털 제출"])
                why, st = ["파일명=이름"], "✅디지털"
            else:
                g, why = res.get(nm, (None, []))
                if g is None:
                    st = "❌미제출"
                else:
                    conflict = [h for h in g["ids"] if h in id_index and h != sid]
                    self_id = "학번=" in why
                    self_nm = any(w.startswith("이름=") for w in why)
                    # 헌법1 ①: 충돌 학번의 실소유자가 자기 묶음을 따로 확정했다면 정렬이 1:1 이므로
                    # 그 학생이 이 묶음에 들어올 길이 없다 → 헤더 숫자 오독일 뿐 오매핑이 아니다.
                    if conflict and (self_id or self_nm) and all(h in placed for h in conflict):
                        st = "⚠️학번혼재"
                        why.append(f"타학번{conflict[0]}({id_index[conflict[0]]})=실소유자별도확정")
                    elif conflict:
                        st = "🚩충돌"; why.append(f"타학생학번{conflict[0]}({id_index[conflict[0]]})")
                    elif "순서이탈" in why:  st = "⚠️순서이탈"
                    elif self_id and self_nm: st = "✅일치"
                    elif self_id:            st = "✅학번"
                    elif self_nm:            st = "✅이름"
                    elif any(w.startswith("이름≈") for w in why): st = "⚠️오독복원"
                    else:                    st = "❓신호없음"
            summary[st] += 1

            rels = {k: (f"{cls}/{g[k]}" if g and g.get(k) else "") for k in B.keys}
            counts = {k: B.student_chars(rels[k]) for k in B.keys}
            anchors = sum(a for a, _ in counts.values())
            chars = sum(c for _, c in counts.values())
            filled = [c for _, c in counts.values()]
            if not any(rels.values()):        mat = "-"
            elif chars < cfg["blank_chars"]:  mat = "백지" if anchors else "OCR붕괴"
            elif min(filled) < cfg["blank_chars"]: mat = "한칸결손"
            elif chars < cfg["thin_chars"]:   mat = "얕음"
            else:                             mat = "정상"
            summary["재료:" + mat] += 1

            row = {"순서": s[B.col_order], "반": cls, "학번": sid, "이름": nm}
            row.update(rels)
            row.update({"상태": st, "재료": mat})
            row.update({f"실{k}": counts[k][1] for k in B.keys})
            out_rows.append(row)
            note = "; ".join(g["note"]) if g and g.get("note") else ""
            review.append((cls, sid, nm, *[os.path.basename(rels[k]) for k in B.keys],
                           st, mat, "/".join(str(counts[k][1]) for k in B.keys), " ".join(why), note))
            if st not in ("✅일치", "✅학번", "✅이름", "✅디지털") or mat in ("백지", "OCR붕괴", "한칸결손"):
                holds.append((cls, sid, nm,
                              f"{'/'.join(os.path.basename(rels[k]) for k in B.keys)} "
                              f"실기재{'/'.join(str(counts[k][1]) for k in B.keys)} {' '.join(why)} {note}",
                              f"{st}·{mat}"))

    # ── 구조적 확정(샌드위치) ────────────────────────────────────────────────
    ANCHORED = ("✅일치", "✅학번", "✅이름", "⚠️학번혼재", "✅디지털")
    sandwich, by_c = {}, collections.defaultdict(list)
    for r in out_rows:
        by_c[r["반"]].append(r)
    k0 = B.keys[0]
    for cls, rs in by_c.items():
        rs.sort(key=lambda r: int(r["순서"]) if str(r["순서"]).isdigit() else 0)
        for i, r in enumerate(rs):
            if r["상태"] not in ("❓신호없음", "⚠️오독복원") or not r[k0]:
                continue
            cur = B.scan_no(os.path.basename(r[k0]))
            if cur is None:
                continue
            ok = []
            for nb, gap in ((rs[i - 1] if i else None, -len(B.keys)),
                            (rs[i + 1] if i + 1 < len(rs) else None, +len(B.keys))):
                if nb and nb["상태"] in ANCHORED and nb[k0]:
                    if B.scan_no(os.path.basename(nb[k0])) == cur + gap:
                        ok.append(nb["이름"])
            if len(ok) == 2:
                sandwich[(cls, r["학번"])] = f"앞뒤 확정({ok[0]}·{ok[1]})이 연번으로 감쌈 → 다른 학생 불가"

    fields = ["순서", "반", "학번", "이름"] + B.keys + ["상태", "재료"] + [f"실{k}" for k in B.keys]
    op = os.path.join(root, "out", "mapping_reconciled.csv")
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(out_rows)

    with open(os.path.join(root, "out", "mapping_review.md"), "w", encoding="utf-8") as f:
        f.write("# 매핑 검수 테이블 (헌법 1 · 3중 대조 + 백지 게이트)\n\n")
        head = ["반", "학번", "이름"] + B.keys + ["상태", "재료", "실기재", "근거신호", "비고"]
        f.write("| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n")
        for r in review:
            f.write("| " + " | ".join(str(x) for x in r) + " |\n")

    print("=== 매핑 상태 ===")
    for k, v in sorted(((k, v) for k, v in summary.items() if not k.startswith("재료:")), key=lambda x: -x[1]):
        print(f"  {k}: {v}명")
    print(f"  합계 {sum(v for k, v in summary.items() if not k.startswith('재료:'))}명")
    print("\n=== 재료(백지 게이트) ===")
    for k, v in sorted(((k, v) for k, v in summary.items() if k.startswith("재료:")), key=lambda x: -x[1]):
        print(f"  {k[3:]}: {v}명")
    print(f"\n=== 사람이 봐야 하는 것 {len(holds)}건 ===")
    for h in holds:
        sw = sandwich.get((h[0], h[1]))
        print("  " + " | ".join(str(x) for x in h) + (f"\n        └ 구조근거: {sw}" if sw else ""))
    print(f"\n산출: out/mapping_reconciled.csv · out/mapping_review.md")
    print("⚠️ ⚠️/❓/🚩/❌ 는 교사가 해소한 뒤에만 다음 단계로 넘어간다(헌법 1·6).")


if __name__ == "__main__":
    main()
