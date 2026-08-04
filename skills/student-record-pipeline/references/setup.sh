#!/usr/bin/env bash
# 세특 작업 폴더를 한 번에 차린다. 사전 인터뷰가 끝난 뒤 딱 한 번 실행한다.
#
#   bash <스킬경로>/references/setup.sh <작업폴더>
#
# 하는 일: 도구 복사 → 채울 파일 4개 만들기 → 학생 목록 조립 → 다음에 할 일 안내.
# 이미 있는 파일은 절대 덮어쓰지 않는다(선생님이 채워 넣은 내용을 날리면 안 되므로).
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF="$SKILL/references"

PROJECT=${1:-}
if [ -z "$PROJECT" ]; then
  echo "❌ 작업 폴더를 알려주세요:  bash setup.sh <작업폴더>" >&2
  exit 2
fi
mkdir -p "$PROJECT/tool" "$PROJECT/out" "$PROJECT/out/marks"
# out/marks 는 예전엔 서버가 처음 뜰 때 만들었다. 그런데 setup·SKILL 이 그보다 먼저
# `> out/marks/_context.json` 을 시켜서 exit 1 이 났다(실측 2026-08-03). 여기서 만든다.
cd "$PROJECT"

G=$'\033[32m'; Y=$'\033[33m'; B=$'\033[1m'; R=$'\033[0m'
kept=0

# 있으면 그대로 두고, 없을 때만 만든다.
put() {  # put <원본> <놓을자리> <설명>
  if [ -e "$2" ]; then echo "  · $2 — 이미 있어서 그대로 둡니다"; kept=$((kept+1))
  else cp "$1" "$2"; echo "  ${G}+${R} $2 — $3"; fi
}

echo "${B}도구 복사${R}"
cp -r "$REF/marking-tool/." tool/
rm -rf tool/__pycache__
# 없어진 옛 도구 치우기 — cp 는 지워진 파일을 안 지운다. 남아 있으면 둘 중 뭘 쓸지 헷갈린다.
for old in watch_done.sh neis_preflight.py watch.sh; do
  [ -e "tool/$old" ] && rm -f "tool/$old" && echo "  ${Y}-${R} tool/$old — 지금은 안 쓰는 옛 도구라 치웠습니다"
done
echo "  ${G}+${R} tool/ (화면·서버·검사·엑셀)"

echo "${B}채워야 할 파일${R}"
put "$REF/render-contract.template.md" tool/render_contract.md "세특을 어떤 틀로 쓸지"
put "$REF/draft-rules.example.json"    draft-rules.json         "길이 상한과 못 쓰는 말"
put "$REF/repeat-whitelist.example.txt" repeat-whitelist.txt    "같은 말 반복을 봐줄 과목 용어"
if [ ! -e sections.json ]; then
  cat > sections.json <<'JSON'
{
  "_설명": "학생 활동지가 몇 칸으로 되어 있는지. 사전 인터뷰 13번 답을 옮긴다.",
  "_key": "명렬표 CSV의 열 이름과 같아야 한다. label=칸 제목, tag=짧은 꼬리표, tip=안내(선택)",
  "sections": [
    {"key": "p3", "label": "3 · 칸 제목을 바꾸세요", "tag": "꼬리표",
     "tip": "드래그하면 바로 형광펜, 다시 드래그로 추가"},
    {"key": "p4", "label": "4 · 칸 제목을 바꾸세요", "tag": "꼬리표"}
  ]
}
JSON
  echo "  ${G}+${R} sections.json — 활동지 칸 구성"
else
  echo "  · sections.json — 이미 있어서 그대로 둡니다"; kept=$((kept+1))
fi

echo "${B}학생 목록 조립${R}"
if [ -f out/mapping_reconciled.csv ]; then
  python3 tool/build_students.py all && echo "  ${G}+${R} tool/students.json"
else
  echo "  ${Y}!${R} out/mapping_reconciled.csv 가 아직 없습니다."
  echo "    누구 글인지 맞추는 단계를 먼저 하세요:"
  echo "    python3 $REF/map_pages.py --root $PROJECT"
fi

cat <<EOF

${B}다음에 할 일${R}
  1) 위 4개 파일을 사전 인터뷰 내용으로 채웁니다.
     ${Y}render_contract.md 의 예시 칸이 비면 세특을 만들지 않습니다${R} — 선생님이 쓰신 세특 3~4편을 넣으세요.
  2) ${Y}활동 맥락을 미리 넣습니다${R} — 화면 입력만 믿지 마세요. 빠지면 모든 세특의 첫 문장이 사라집니다.
     echo '{"context":"<인터뷰 2번을 한 줄로>"}' > out/marks/_context.json
  3) 화면을 띄웁니다.  PORT=7335 node tool/server.mjs   → http://localhost:7335/
     (7333·7334는 다른 과목이 쓰고 있을 수 있습니다. 겹치면 PORT 를 옮기세요.)
  4) 선생님이 활동 맥락을 확인하고, 형광펜을 칠하고, 학생마다 [마킹 끝]을 켭니다.
     ${Y}지켜보는 창은 없습니다.${R} 다 하신 뒤 한 번만 말씀하시면 그때 씁니다:
       python3 tool/render_now.py     → 찍히는 Workflow 한 줄을 실행
       python3 tool/gate.py ; python3 tool/make_review_xlsx.py
  5) 검수는 out/검수.xlsx 한 곳에서만 합니다. '다시' 칸에 적으신 판정을 되먹이려면:
       python3 tool/ingest_review_xlsx.py --write ; python3 tool/render_now.py --opus
     ${Y}여러 번 나눠 불러도 이미 쓴 학생은 다시 쓰지 않습니다.${R}

이미 있어서 건드리지 않은 파일: ${kept}개
EOF

# 설정이 예시 기본값 그대로면 여기서 알려 준다. 다 채우기 전엔 어차피 render_now.py 가 막는다.
echo
echo "${B}설정 검사${R} (지금은 대부분 걸리는 게 정상입니다 — 위 파일들을 채우시면 사라집니다)"
python3 tool/check_config.py || true

