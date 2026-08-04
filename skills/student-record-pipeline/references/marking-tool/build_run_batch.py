#!/usr/bin/env python3
"""렌더 입력을 워크플로 스크립트에 **직접 주입**한다 — 메인 에이전트가 원문을 안 보게.

  python3 tool/build_run_batch.py                        # 대기열 전원
  python3 tool/build_run_batch.py <학번> [<학번> …]       # 지정 학번만
  python3 tool/build_run_batch.py --batch batch_render_opus.js   # 다른 배치 스크립트로

산출: out/_run_batch.js  (배치 스크립트 + args 리터럴이 박힌 자족 스크립트)
그다음 메인 에이전트는 이것만 부른다:
  Workflow({scriptPath: '<project>/out/_run_batch.js'})      # args 없음

왜 이게 필요한가 — 실측 사고(2026-08-02):
  Workflow 의 `args` 는 메인 에이전트가 **도구 호출에 손으로 적어 넣는 값**이다. 워크플로
  스크립트에는 파일시스템 접근이 없어서 경로를 넘길 수가 없다. 그래서 메인이 렌더 입력
  JSON 을 Read 로 통째로 열었고, 학생 원문이 그대로 메인 컨텍스트에 얹혔다(2명에 ~9K 토큰,
  남은 8명 전원 위임이면 ~40K 예상). 초안 본문을 서브에이전트만 보게 막아 놓고 **입력**
  쪽으로 샌 것이다.
  일반화: **워크플로 args 로 넘길 데이터를 메인이 Read 하면 그 순간 격리는 깨진다.**
  args 는 손으로 적지 말고 스크립트에 결정론적으로 주입하고, 메인은 개수·바이트만 받는다.

메인이 받아야 하는 것은 stderr 로만 나간다(학번·인원·바이트). 원문은 stdout·stderr 어디로도
나가지 않는다 — 이 스크립트의 출력은 그대로 메인 컨텍스트에 실리기 때문이다.
"""
import sys, os, json, subprocess

TOOL = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOL)
OUT = os.path.join(ROOT, "out")
RENDER_ARGS = os.path.join(TOOL, "render_args.py")
TARGET = os.path.join(OUT, "_run_batch.js")
MARKER = "/* @@ARGS-INJECTION-POINT@@"
DEFAULT_BATCH = "batch_render_sonnet.js"


def main():
    argv = sys.argv[1:]
    # --batch <파일> — 재작성 라인 등 다른 배치 스크립트를 쓸 때. 나머지는 학번으로 넘긴다.
    batch_name = DEFAULT_BATCH
    if "--batch" in argv:
        i = argv.index("--batch")
        if i + 1 >= len(argv):
            print("❌ --batch 뒤에 스크립트 파일명이 필요합니다.", file=sys.stderr)
            sys.exit(2)
        batch_name = argv[i + 1]
        del argv[i:i + 2]
    BATCH = batch_name if os.path.isabs(batch_name) else os.path.join(TOOL, batch_name)
    if not os.path.exists(BATCH):
        print(f"❌ 배치 스크립트 없음: {BATCH}", file=sys.stderr)
        sys.exit(2)
    targets = argv

    # ① 렌더 입력 조립 — render_args.py 를 그대로 재사용한다(로직 복제 금지).
    #    --stdout 이라 out/render_args.json 을 아예 만들지 않는다. 중간 파일이 없으면
    #    누군가(사람이든 에이전트든) 그걸 열어 볼 일도 없다.
    #    stderr 는 넘기지 않고 그대로 흘려보낸다 — 위임 인원·3회 물림·같은 사유 반복 같은
    #    교사가 봐야 할 신호가 거기로 나온다.
    proc = subprocess.run([sys.executable, RENDER_ARGS, "--stdout", *targets],
                          capture_output=True, text=True)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        sys.exit(proc.returncode)
    payload_raw = proc.stdout.strip()
    if not payload_raw:
        print("렌더할 학생이 없습니다 — _run_batch.js 를 만들지 않았습니다.", file=sys.stderr)
        sys.exit(0)
    payload = json.loads(payload_raw)

    students = payload.get("students", [])
    if not students:
        print("students 가 비었습니다 — _run_batch.js 를 만들지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    # ② 워크플로 스크립트에 주입. 마커를 못 찾으면 추측하지 않고 멈춘다 —
    #    meta 블록 위치를 어림잡아 자르면 워크플로가 "meta 로 시작해야 한다" 규칙을 깬다.
    src = open(BATCH, encoding="utf-8").read()
    idx = src.find(MARKER)
    if idx < 0:
        print(f"❌ {os.path.basename(BATCH)} 에 '{MARKER}' 마커가 없습니다 — 주입 위치를 "
              "추측하지 않습니다. 마커를 되살린 뒤 다시 실행하세요.", file=sys.stderr)
        sys.exit(2)
    end = src.find("*/", idx)
    if end < 0:
        print("❌ 마커 주석이 닫히지 않았습니다(*/ 없음).", file=sys.stderr)
        sys.exit(2)
    head, tail = src[:idx], src[end + 2:]

    # </script> 류 종료 시퀀스는 없지만, JSON 리터럴이 JS 주석·문자열을 깨지 않게
    # </ 와 유니코드 줄바꿈만 이스케이프한다(JSON.parse 대신 리터럴로 박기 때문).
    literal = (json.dumps(payload, ensure_ascii=False)
               .replace("</", "<\\/")
               .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))

    banner = (
        "/* 자동 생성 — build_run_batch.py. 직접 고치지 마라(다음 배치에서 덮어쓴다).\n"
        "   학생 원문이 들어 있다 = PII. 리포에 커밋하지 마라. */\n"
    )
    os.makedirs(OUT, exist_ok=True)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(head + banner + "const args = " + literal + "\n" + tail)

    size = os.path.getsize(TARGET)
    delegated = [s for s in students if not s.get("highlights") and s.get("sources")]
    # 메인이 받는 건 여기까지다 — 학번·인원·바이트. 원문은 한 글자도 올리지 않는다.
    print(f"→ {TARGET}", file=sys.stderr)
    print(f"   {len(students)}명 ({' '.join(s['hakbun'] for s in students)}) · {size:,}B"
          + (f" · 위임 {len(delegated)}명" if delegated else ""), file=sys.stderr)
    print(f"   다음: Workflow({{scriptPath:'{TARGET}'}})  ← args 없음", file=sys.stderr)


if __name__ == "__main__":
    main()
