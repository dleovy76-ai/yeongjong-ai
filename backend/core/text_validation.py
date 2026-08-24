"""공유 텍스트 무결성 검사 - PILOT AUDIT TASK 1.

ValidatedText를 str 대신 쓰면 Pydantic이 값을 받을 때마다 자동으로
assert_valid_text를 거친다 (Field()의 min_length/max_length 등과 함께
Annotated로 조합 가능).

조사 결과: 실제 프로덕션 DB/직렬화/수집 파이프라인 어디에도 인코딩 손상은
없었다(2026-08-25 railway ssh로 15개 BusinessProfile 전체 재확인, 전부
UTF-8 재인코딩 가능). 원래 감사에서 지적한 깨진 값은 로컬 터미널
codepage가 curl 출력을 잘못 표시한 것이었을 뿐, 실제 데이터 문제가 아니었다.

그래도 재발 방지용으로 입력 경계(Pydantic 스키마)에 최소한의 방어를 둔다 -
DB가 사실 그대로를 담고 있다는 전제 자체가 다음에도 참이라는 보장은 없으므로."""

from typing import Annotated

from pydantic import AfterValidator

_SURROGATE_RANGE = range(0xD800, 0xE000)


def assert_valid_text(value: str) -> str:
    """Lone surrogate(예: 잘못된 decode로 생긴 U+DCxx 등)나 그 밖에
    UTF-8로 다시 인코딩할 수 없는 문자가 섞인 문자열을 거부한다.
    정상적인 한글/영문/이모지/여러 언어 혼용 텍스트는 전부 통과한다."""
    for ch in value:
        if ord(ch) in _SURROGATE_RANGE:
            raise ValueError("텍스트에 처리할 수 없는 문자(손상된 인코딩)가 포함되어 있습니다.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("텍스트를 UTF-8로 인코딩할 수 없습니다.") from exc
    return value


ValidatedText = Annotated[str, AfterValidator(assert_valid_text)]
