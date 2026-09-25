"""OpenShell 정책 파일 회귀 테스트.

여기서 지키는 것은 DLI 강좌 기준선 대조(docs/notes/dli-course/module3-4.md)로 정한 세 가지다.
스키마 검증은 `openshell policy set` 이 하고(로컬에는 openshell 이 없다), 이 테스트는 우리가
의도한 제약이 파일에서 조용히 사라지지 않게 잡는 역할만 한다. 네트워크를 쓰지 않는다.

  1. 추론 엔드포인트에 떠돌이 curl 을 올리지 않는다 (flydock).
  2. process 블록을 모든 정책에 명시한다 (root 로 도는 구성을 막는다).
  3. access 대신 rules 로 메서드와 경로까지 좁힌다 (flydock). access 와 rules 는 동시 사용 금지.

실측 근거는 eval/results/openshell_smoke_flydock.txt (2026-09-25, pass=18 fail=0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

POLICY_DIR = Path(__file__).resolve().parents[1] / "policies"
ALL_POLICIES = ["base", "pharmasignal", "flydock"]

# 이미지(policies/sandbox-image/Dockerfile)가 만든 비루트 사용자.
IMAGE_UID = "1500"

# flydock 이 여는 호스트 일곱. 그 밖은 열지 않는다.
FLYDOCK_HOSTS = {
    "health.api.nvidia.com",
    "integrate.api.nvidia.com",
    "files.rcsb.org",
    "drug.flybrain.kr",
    "api.fda.gov",
    "dailymed.nlm.nih.gov",
    "eutils.ncbi.nlm.nih.gov",
}

# 구조적으로 막아야 하는 호스트. 목록에 들어오면 원본 push 와 런타임 설치가 가능해진다.
FORBIDDEN_HOSTS = {"github.com", "api.github.com", "pypi.org", "files.pythonhosted.org"}


def load(name: str) -> dict:
    return yaml.safe_load((POLICY_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def endpoints(policy: dict):
    """(블록 이름, 엔드포인트 dict) 를 차례로 낸다."""
    for block_name, block in (policy.get("network_policies") or {}).items():
        for endpoint in block.get("endpoints") or []:
            yield block_name, endpoint


@pytest.mark.parametrize("name", ALL_POLICIES)
def test_version_is_one(name: str) -> None:
    assert load(name)["version"] == 1


@pytest.mark.parametrize("name", ALL_POLICIES)
def test_process_block_is_explicit(name: str) -> None:
    """보강 2번. 생략하면 이미지 OCI USER 를 따라 root 로 돌 수 있다."""
    process = load(name).get("process")
    assert process, f"{name}.yaml 에 process 블록이 없다"
    assert process.get("run_as_user") == IMAGE_UID
    assert process.get("run_as_group") == IMAGE_UID
    # 0(root)은 스키마가 거부하지만 실수로 적히는 것을 여기서도 막는다.
    assert str(process["run_as_user"]) != "0"


@pytest.mark.parametrize("name", ALL_POLICIES)
def test_access_and_rules_are_mutually_exclusive(name: str) -> None:
    for block_name, endpoint in endpoints(load(name)):
        assert not ("access" in endpoint and "rules" in endpoint), (
            f"{name}.yaml {block_name}: access 와 rules 를 함께 쓸 수 없다"
        )


@pytest.mark.parametrize("name", ALL_POLICIES)
def test_endpoints_have_host_and_port(name: str) -> None:
    for block_name, endpoint in endpoints(load(name)):
        assert endpoint.get("host"), f"{name}.yaml {block_name}: host 누락"
        assert isinstance(endpoint.get("port"), int), f"{name}.yaml {block_name}: port 누락"


@pytest.mark.parametrize("name", ALL_POLICIES)
def test_write_paths_stay_narrow(name: str) -> None:
    """쓰기는 산출물 경로와 런타임 기본 경로만. / 나 /etc 가 들어오면 안 된다."""
    read_write = set(load(name)["filesystem_policy"]["read_write"])
    allowed = {"/work/out", "/work/repo", "/tmp", "/dev/null"}
    assert read_write <= allowed, f"{name}.yaml 의 read_write 에 예상 밖 경로가 있다: {read_write - allowed}"
    assert "/work/out" in read_write


def test_flydock_opens_exactly_seven_hosts() -> None:
    hosts = {endpoint["host"] for _, endpoint in endpoints(load("flydock"))}
    assert hosts == FLYDOCK_HOSTS
    assert len(hosts) == 7


@pytest.mark.parametrize("name", ALL_POLICIES)
def test_forbidden_hosts_are_absent(name: str) -> None:
    """github.com 을 빼 두는 것이 원본 push 를 구조적으로 막는 근거다."""
    hosts = {endpoint["host"] for _, endpoint in endpoints(load(name))}
    assert hosts & FORBIDDEN_HOSTS == set(), f"{name}.yaml 이 열어서는 안 되는 호스트를 열었다"


def test_flydock_has_no_stray_curl() -> None:
    """보강 1번. 강좌가 적색으로 분류한 경우다. 우리 도구는 전부 파이썬이다."""
    policy = load("flydock")
    for block_name, block in policy["network_policies"].items():
        paths = [b.get("path") for b in block.get("binaries") or []]
        assert paths, f"flydock.yaml {block_name}: binaries 가 비어 있다"
        assert "/usr/bin/curl" not in paths, f"flydock.yaml {block_name}: curl 이 다시 들어왔다"
        # 이미지에서 python3 는 python3.12 로 해석되므로 두 경로가 함께 있어야 한다.
        assert "/usr/bin/python3" in paths and "/usr/bin/python3.12" in paths


def test_flydock_narrows_every_endpoint_with_rules() -> None:
    """보강 3번. access: read-write 는 메서드만 정하고 경로를 가리지 않는다."""
    for block_name, endpoint in endpoints(load("flydock")):
        assert "access" not in endpoint, f"flydock.yaml {block_name}: access 대신 rules 를 쓴다"
        rules = endpoint.get("rules")
        assert rules, f"flydock.yaml {block_name}: rules 가 없다"
        for rule in rules:
            allow = rule["allow"]
            assert allow["method"] in {"GET", "POST", "PUT", "PATCH", "HEAD", "OPTIONS", "DELETE"}
            assert allow["path"].startswith("/")
        assert endpoint.get("protocol") == "rest", "rules 는 L7 검사가 켜져 있어야 뜻이 있다"
        assert endpoint.get("enforcement") == "enforce"


def test_flydock_writes_only_to_out() -> None:
    fs = load("flydock")["filesystem_policy"]
    assert fs["include_workdir"] is False
    assert fs["read_write"] == ["/work/out", "/tmp", "/dev/null"]
    assert "/sandbox" in fs["read_only"]
