# 해커톤용 샌드박스 워크로드 이미지.
#
# OpenShell 기본 이미지(nvcr.io/nvidia/base/ubuntu:24.04)는 최소 유저스페이스라 python3가
# 있는지 확인되지 않았고 [unverified], 정책이 요구하는 /work/out, /work/repo 디렉터리도 없다.
# Landlock은 존재하지 않는 경로를 건너뛰므로 디렉터리가 이미지 안에 미리 있어야 한다.
# 그래서 공식 BYOC 예제(examples/bring-your-own-container/Dockerfile)의 요건을 따라 만든다.
#   - 표준 리눅스 베이스(distroless, scratch 불가)
#   - 비루트 OCI USER 선언
#   - /sandbox를 작업 디렉터리로 준비하고 해당 사용자에게 쓰기 권한
#   - iproute2 설치(네트워크 네임스페이스 격리), nftables는 선택(우회 탐지)
#   - CMD는 런타임에 슈퍼바이저로 대체되므로 시작 명령은 `openshell sandbox create ... -- <cmd>`로 준다
#
# 빌드(VM 안, 게이트웨이와 같은 Docker 데몬):
#   docker build -t hackathon-sandbox:latest policies/sandbox-image
#
# Night Shift는 실험 대상 저장소 사본을 /work/repo에 넣어야 한다. 아래 주석의 COPY 또는
# 빌드 인자 REPO_URL로 clone하는 방식 중 하나를 골라 쓴다(기본은 빈 디렉터리).

FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git iproute2 nftables \
        python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ubuntu:24.04 이미지는 uid 1000(ubuntu)을 이미 쓰므로 1500을 사용한다.
# nightshift.yaml의 process.run_as_user/run_as_group(1500)과 맞춘다.
RUN groupadd --gid 1500 sandbox \
    && useradd --uid 1500 --gid sandbox --create-home sandbox

# 작업 디렉터리와 정책이 가리키는 쓰기 경로. 소유자는 sandbox.
RUN install -d -o sandbox -g sandbox /sandbox /work /work/out /work/repo

WORKDIR /sandbox

# 에이전트 코드는 여기서 COPY로 넣는다(정책상 /sandbox는 읽기 전용이므로 실행 중 업로드 대신).
# COPY --chown=sandbox:sandbox src/ /sandbox/src/
# COPY --chown=sandbox:sandbox configs/ /sandbox/configs/

# Night Shift 실험 대상 저장소 사본(선택). 빌드 시 --build-arg REPO_URL=https://... 로 지정.
ARG REPO_URL=""
RUN if [ -n "$REPO_URL" ]; then \
      git clone --depth 50 "$REPO_URL" /work/repo && chown -R sandbox:sandbox /work/repo; \
    fi

USER sandbox

# 슈퍼바이저가 대체하므로 실질적 의미는 없다. 기본값만 둔다.
CMD ["sleep", "infinity"]
