#!/bin/zsh
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 video/explain/bgm_pick.sh
# 이식 시각: 2026-09-25
# 바꾼 것: 그대로 가져왔다.
# 배경음악 테마를 고른다. 영상마다 같은 곡을 깔지 않기 위한 것이다.
#
#   bgm_pick.sh list                   테마 목록
#   bgm_pick.sh set <테마>             그 테마를 bgm/bgm_src.wav 로 앉힌다
#   bgm_pick.sh set <앞테마> <뒤테마>   앞 구간과 뒤 구간을 다른 테마로
#   bgm_pick.sh audition [voice.mp3]   전 테마를 나레이션에 얹어 들어 볼 파일을 만든다
set -uo pipefail
HERE="${0:A:h}"
THEMES="$HERE/bgm_themes.tsv"
[ -f "$THEMES" ] || THEMES="bgm_themes.tsv"
LOOPS="/Library/Audio/Apple Loops"
PY=${PY:-/opt/anaconda3/envs/rag/bin/python}

find_loop(){ find "$LOOPS" -name "$1.caf" 2>/dev/null | head -1 }
theme_loop(){ grep -v '^#' "$THEMES" | awk -F'\t' -v k="$1" '$1==k{print $2}' }

# 루프 이음매가 튀지 않게 앞뒤를 살짝 페이드해서 wav로 앉힌다
lay(){  # lay <루프이름> <출력경로>
  local src=$(find_loop "$1")
  [ -z "$src" ] && { print -r -- "  루프를 못 찾았다: $1"; return 1 }
  local d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src")
  mkdir -p "$(dirname $2)"
  ffmpeg -nostdin -y -i "$src" \
    -af "afade=t=in:st=0:d=0.30,afade=t=out:st=$(echo "$d-0.40"|bc):d=0.40" \
    -ar 44100 -ac 2 "$2" 2>/dev/null
  printf "  %-14s %5.1f초  → %s\n" "$1" "$d" "$2"
}

cmd_list(){
  printf "%-13s %-32s %s\n" "테마" "루프" "어울리는 자리"
  grep -v '^#' "$THEMES" | awk -F'\t' 'NF>=3{printf "%-13s %-32s %s\n", $1, $2, $3}'
}

cmd_set(){
  local a="${1:-}" b="${2:-}"
  [ -n "$a" ] || { print -r -- "테마를 지정한다. 목록은 bgm_pick.sh list"; return 2 }
  local la=$(theme_loop "$a")
  [ -n "$la" ] || { print -r -- "모르는 테마: $a"; return 2 }
  lay "$la" bgm/bgm_src.wav || return 1
  if [ -n "$b" ]; then
    local lb=$(theme_loop "$b")
    [ -n "$lb" ] || { print -r -- "모르는 테마: $b"; return 2 }
    lay "$lb" bgm/bgm_out.wav || return 1
    print -r -- "  앞 구간 $a / 뒤 구간 $b"
  else
    rm -f bgm/bgm_out.wav
    print -r -- "  앞뒤 모두 $a"
  fi
  # 무엇을 골랐는지 남긴다
  { print -r -- "# 이 영상의 배경음악"; print -r -- ""
    print -r -- "| 구간 | 테마 | 루프 |"; print -r -- "|---|---|---|"
    print -r -- "| 앞 | $a | $la |"
    [ -n "$b" ] && print -r -- "| 뒤 | $b | $(theme_loop $b) |"
    print -r -- ""
    print -r -- "출처: macOS 기본 제공 Apple Loops. 자기가 만든 오디오 작업물에 로열티 없이 넣고 배포할 수 있다."
  } > bgm/출처.md
}

cmd_audition(){
  local voice="${1:-remotion/public/voice.mp3}"
  [ -f "$voice" ] || { print -r -- "나레이션 파일이 없다: $voice"; return 2 }
  mkdir -p bgm/candidates; : > bgm/_list.txt
  local i=0
  # 번호는 한자어로 읽어야 한다. 아라비아 숫자를 그대로 주면 "한 번, 두 번"으로 읽는다
  local -a SINO=(일 이 삼 사 오 육 칠 팔 구 십)
  grep -v '^#' "$THEMES" | awk -F'\t' 'NF>=3{print $1"\t"$2}' | while IFS=$'\t' read -r name loop; do
    i=$((i+1)); local src=$(find_loop "$loop")
    [ -z "$src" ] && continue
    $PY -c "
import asyncio, edge_tts
asyncio.run(edge_tts.Communicate('${SINO[$i]} 번', 'ko-KR-InJoonNeural').save('bgm/candidates/_lab_$i.mp3'))" 2>/dev/null
    ffmpeg -nostdin -y -stream_loop -1 -i "$src" -i "$voice" \
      -filter_complex "[0:a]atrim=0:14,lowpass=f=6000,volume=-15dB,afade=t=in:st=0:d=1.5,afade=t=out:st=11:d=3,aformat=fltp:44100:stereo[b];[1:a]atrim=0:14,aformat=fltp:44100:stereo[v];[v][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
      -map "[a]" -t 14 -c:a libmp3lame -q:a 2 "bgm/candidates/$name.mp3" 2>/dev/null
    print -r -- "file 'candidates/_lab_$i.mp3'" >> bgm/_list.txt
    print -r -- "file 'candidates/$name.mp3'" >> bgm/_list.txt
    printf "  %d. %-13s %s\n" "$i" "$name" "$loop"
  done
  ffmpeg -nostdin -y -f concat -safe 0 -i bgm/_list.txt -c:a libmp3lame -q:a 2 bgm/BGM_후보_듣기.mp3 2>/dev/null
  rm -f bgm/_list.txt bgm/candidates/_lab_*.mp3
  printf "  → bgm/BGM_후보_듣기.mp3 (%.0f초)\n" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 bgm/BGM_후보_듣기.mp3)"
}

case "${1:-list}" in
  list)     cmd_list ;;
  set)      cmd_set "${2:-}" "${3:-}" ;;
  audition) cmd_audition "${2:-}" ;;
  *) print -r -- "사용법: bgm_pick.sh [list|set <테마> [뒤테마]|audition [voice.mp3]]"; exit 2 ;;
esac
