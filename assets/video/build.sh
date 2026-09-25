#!/bin/zsh
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 video/explain/build.sh
# 이식 시각: 2026-09-25
# 바꾼 것: PY 를 환경변수로 덮어쓸 수 있게 바꿨다.
# 슬라이드 + 나레이션 → 최종 영상
# video-narrate 스킬의 하네스. 설정은 아래 변수만 고친다.
#  · 문장 단위로 TTS를 만들어 슬라이드가 해당 멘트와 정확히 같이 뜨게 한다
#  · 문장 사이 긴 무음은 압축하고, 오디오는 하나로 이어 붙여 끊김을 없앤다
#  · 문장마다 자막을 얹고, 장면 전환은 크로스페이드로, 배경음악은 앞뒤에만 깐다
set -euo pipefail
cd "$(dirname "$0")"
# .venv 에는 edge_tts 가 없다. 기본값은 rag env 이고 PY 로 덮어쓸 수 있다.
PY=${PY:-/opt/anaconda3/envs/rag/bin/python}

# 출력 파일명. final 은 빌드 기본 출력명이라 그대로 두면 1차본을 최종본처럼 부르게 된다.
# 해커톤과 프로젝트와 판본과 날짜가 드러나게 한다. 판본은 VER=2 처럼 올린다.
# 제출 직전에는 팀명을 넣어 [NVIDIA 해커톤_<팀명>_FlyGate].mp4 로 복사한다.
OUT_BASE="NVIDIA해커톤_FlyGate_데모영상_v${VER:-1}_$(date +%Y%m%d)"
KEEP=0.13; SGAP=0.14; FPS=30
BGM_DB=-15          # 나레이션보다 약 15dB 아래. 후보 청취(-16dB)에서 한 단계 올린 값
BGM_IN=13           # 배경음악을 까는 구간: 앞쪽 초
BGM_OUT=17          #                       뒤쪽 초
XF_SLIDE=0.35       # 슬라이드가 바뀔 때
XF_CAP=0.10         # 자막만 바뀔 때
dur(){ ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" }

echo "== 1. 문장별 TTS =="
$PY - <<'PY'
import asyncio, pathlib, re, edge_tts
paras=[p.strip() for p in pathlib.Path('02_나레이션.txt').read_text(encoding='utf-8').split('\n\n') if p.strip()]
sents=[s.strip() for p in paras for s in re.split(r'(?<=[.!?])\s+', p) if s.strip()]
pathlib.Path('_sents.txt').write_text('\n'.join(sents), encoding='utf-8')
async def gen():
    for i,s in enumerate(sents,1):
        await edge_tts.Communicate(s,'ko-KR-SunHiNeural',rate='+8%').save(f's_{i:02d}.mp3')
asyncio.run(gen())
print(f'  문장 {len(sents)}개 생성')
PY

echo "== 2. 문장별 무음 압축 =="
N=$(grep -c "" _sents.txt)
: > _durs.txt
for i in $(seq 1 $N); do
  n=$(printf "%02d" $i)
  ffmpeg -nostdin -y -i "s_$n.mp3" \
    -af "silenceremove=start_periods=1:start_duration=0.10:start_threshold=-38dB:start_silence=$KEEP,silenceremove=stop_periods=-1:stop_duration=0.25:stop_threshold=-38dB:stop_silence=$KEEP" \
    -c:a libmp3lame -q:a 2 "t_$n.mp3" 2>/dev/null
  echo "$(echo "$(dur t_$n.mp3) + $SGAP" | bc)" >> _durs.txt
done
echo "  문장 $N개, 합계 $(awk '{s+=$1} END{printf "%.1f", s}' _durs.txt)초"

echo "== 3. 자막 PNG + SRT =="
OUT_BASE="$OUT_BASE" $PY 09_caption.py

echo "== 3-1. 자막 자리 침범 점검 =="
$PY "$(dirname $0)/10_overlap_check.py" . || $PY 10_overlap_check.py . || true

echo "== 4. 프레임 합성 (슬라이드 + 자막) =="
$PY - <<'PY'
import pathlib
from PIL import Image
# 문장 → 슬라이드 매핑
m = {}
for ln in pathlib.Path('08_timeline.txt').read_text(encoding='utf-8').splitlines():
    ln = ln.split('#')[0].split()
    if len(ln) >= 3:
        s, a, b = int(ln[0]), int(ln[1]), int(ln[2])
        for k in range(a, b + 1):
            m[k] = s
n = len(pathlib.Path('_durs.txt').read_text().split())
assert set(m) == set(range(1, n + 1)), f'타임라인 누락: {sorted(set(range(1,n+1)) - set(m))}'
cache = {}
for i in range(1, n + 1):
    sl = m[i]
    if sl not in cache:
        cache[sl] = Image.open(f'slides/s{sl:02d}.png').convert('RGBA')
    frame = cache[sl].copy()
    frame.alpha_composite(Image.open(f'cap_{i:02d}.png').convert('RGBA'))
    frame.convert('RGB').save(f'f_{i:02d}.png', quality=95)
pathlib.Path('_slidemap.txt').write_text('\n'.join(str(m[i]) for i in range(1, n + 1)))
print(f'  프레임 {n}장 합성')
PY

echo "== 5. 크로스페이드 필터 작성 =="
$PY - <<PY
import pathlib
d=[float(x) for x in pathlib.Path('_durs.txt').read_text().split()]
sl=[int(x) for x in pathlib.Path('_slidemap.txt').read_text().split()]
n=len(d)
# 전환 길이: 슬라이드가 바뀌면 길게, 자막만 바뀌면 짧게. D[0]과 D[n]은 0
D=[0.0]+[($XF_SLIDE if sl[i]!=sl[i-1] else $XF_CAP) for i in range(1,n)]+[0.0]
seg=[d[i]+D[i]/2+D[i+1]/2 for i in range(n)]
pathlib.Path('_seglen.txt').write_text('\n'.join(f'{x:.4f}' for x in seg) + '\n')  # 끝 개행 필수: 없으면 zsh while read가 마지막 줄을 버린다
lines,acc,prev=[],seg[0],'0:v'
for i in range(1,n):
    off=acc-D[i]
    out=f'x{i}'
    lines.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={D[i]:.3f}:offset={off:.4f}[{out}]")
    acc=acc+seg[i]-D[i]; prev=out
lines.append(f"[{prev}]format=yuv420p[v]")
pathlib.Path('_xfade.txt').write_text(';\n'.join(lines))
print(f'  전환 {n-1}개 (슬라이드 {sum(1 for i in range(1,n) if sl[i]!=sl[i-1])}회) · 영상 {acc:.1f}초')
PY

echo "== 6. 영상 렌더 =="
ARGS=(); i=1
while read -r len; do
  ARGS+=(-loop 1 -t "$len" -i "f_$(printf "%02d" $i).png"); i=$((i+1))
done < _seglen.txt
ffmpeg -nostdin -y "${ARGS[@]}" -filter_complex_script _xfade.txt \
  -map "[v]" -r $FPS -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p _silent.mp4 2>/dev/null

echo "== 7. 오디오 (나레이션 + 배경음악) =="
ffmpeg -nostdin -y -f lavfi -t $SGAP -i anullsrc=r=24000:cl=mono -c:a libmp3lame -q:a 4 _g.mp3 2>/dev/null
: > _alist.txt
for i in $(seq 1 $N); do
  echo "file 't_$(printf "%02d" $i).mp3'" >> _alist.txt
  echo "file '_g.mp3'" >> _alist.txt
done
ffmpeg -nostdin -y -f concat -safe 0 -i _alist.txt -c:a libmp3lame -q:a 2 _voice.mp3 2>/dev/null
VD=$(dur _voice.mp3)
# 배경음악은 처음과 끝에만 깐다. 내내 틀면 나레이션과 따로 놀고 귀에 걸린다.
OUT_ST=$(echo "$VD - $BGM_OUT" | bc)
ffmpeg -nostdin -y -stream_loop -1 -i bgm/bgm_src.wav -t "$BGM_IN" \
  -af "lowpass=f=6000,volume=${BGM_DB}dB,afade=t=in:st=0:d=1.5,afade=t=out:st=$(echo "$BGM_IN - 3" | bc):d=3" \
  -c:a libmp3lame -q:a 2 _bgm_in.mp3 2>/dev/null
# 뒤 구간에 다른 테마를 앉혔으면 그것을 쓴다 (bgm_pick.sh set <앞> <뒤>)
BGM_TAIL=bgm/bgm_src.wav; [ -f bgm/bgm_out.wav ] && BGM_TAIL=bgm/bgm_out.wav
ffmpeg -nostdin -y -stream_loop -1 -i "$BGM_TAIL" -t "$BGM_OUT" \
  -af "lowpass=f=6000,volume=${BGM_DB}dB,afade=t=in:st=0:d=3,afade=t=out:st=$(echo "$BGM_OUT - 4" | bc):d=4" \
  -c:a libmp3lame -q:a 2 _bgm_out.mp3 2>/dev/null
# 뒤 구간을 미는 것은 합치는 단계에서 한다. 앞 단계에서 밀면 -t에 잘려 나간다
ffmpeg -nostdin -y -i _bgm_in.mp3 -i _bgm_out.mp3 \
  -filter_complex "[1:a]adelay=$(echo "$OUT_ST * 1000 / 1" | bc):all=1[o];[0:a][o]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,apad=whole_dur=${VD}[a]" \
  -map "[a]" -c:a libmp3lame -q:a 2 _bgm.mp3 2>/dev/null
printf "  배경음악: 0~%s초, %s~%s초\n" "$BGM_IN" "$OUT_ST" "$(printf '%.0f' $VD)"
ffmpeg -nostdin -y -i _voice.mp3 -i _bgm.mp3 \
  -filter_complex "[0:a]aformat=fltp:44100:stereo[v0];[1:a]aformat=fltp:44100:stereo[b0];[v0][b0]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[m];[m]loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
  -map "[a]" -c:a libmp3lame -q:a 2 _mix.mp3 2>/dev/null

echo "== 8. 결합 =="
ffmpeg -nostdin -y -i _silent.mp4 -i _mix.mp3 -c:v copy -c:a aac -b:a 192k -shortest "${OUT_BASE}.mp4" 2>/dev/null
printf "  오디오 %.1f초 / 영상 %.1f초\n" "$(dur _mix.mp3)" "$(dur _silent.mp4)"

# 9단계는 리모션 판을 함께 낼 때만 의미가 있다. remotion/ 이 없으면 건너뛴다
if [ -d remotion/src ]; then
echo "== 9. 리모션용 자산 =="
mkdir -p remotion/public
cp _voice.mp3 remotion/public/voice.mp3; cp _bgm.mp3 remotion/public/bgm.mp3
cp fonts/Pretendard-*.otf remotion/public/ 2>/dev/null || true
grep -o "src:'[^']*'" 07_슬라이드.html | sed "s/src:'//;s/'//" | sort -u | while read -r img; do
  [ -f "$img" ] && cp "$img" remotion/public/
done
$PY - <<'PY'
import json, pathlib
sents = [s for s in pathlib.Path('_sents.txt').read_text(encoding='utf-8').split('\n') if s.strip()]
durs = [float(x) for x in pathlib.Path('_durs.txt').read_text().split()]
slides = [int(x) for x in pathlib.Path('_slidemap.txt').read_text().split()]
import importlib.util
spec = importlib.util.spec_from_file_location('cap', '09_caption.py')
cap = importlib.util.module_from_spec(spec); spec.loader.exec_module(cap)
cues = [{'slide': s, 'caption': cap.to_digits(t), 'dur': round(d, 4)}
        for s, t, d in zip(slides, sents, durs)]
pathlib.Path('remotion/src/timing.json').write_text(
    json.dumps({'fps': 30, 'cues': cues}, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'  timing.json {len(cues)}컷 · {sum(durs):.1f}초')
PY
else
  echo "== 9. 리모션 폴더 없음, 건너뜀 =="
fi
rm -f _g.mp3 _alist.txt _silent.mp4 _voice.mp3 _bgm.mp3 _bgm_in.mp3 _bgm_out.mp3 _mix.mp3 _xfade.txt _seglen.txt _slidemap.txt \
      s_*.mp3 t_*.mp3 f_*.png cap_*.png _sents.txt _durs.txt
printf "  %s.mp4 %.1f초 · %s.srt 동봉\n" "$OUT_BASE" "$(dur "${OUT_BASE}.mp4")" "$OUT_BASE"

