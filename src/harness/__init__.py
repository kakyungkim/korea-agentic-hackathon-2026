"""공통 하네스 패키지.

- register.py   NAT 함수(function)와 평가기(evaluator) 등록. `nat.components` entry point 가 이 모듈을 import 한다.
- schemas.py    작성자 출력(AuthorOutput)과 크리틱 판정(CriticReport) pydantic 스키마.
- critic.py     크리틱 판정 함수(critic_judge). 결정 규칙은 순수 파이썬, 의미 판단만 LLM.
- evaluators.py `nat eval` 용 크리틱 적발률 평가기(critic_verdict).
- tools/        도메인 도구(pharmasignal_*, nightshift_*). 별도 담당.
"""
