# 폰트 노트 MCP 서버 (읽기 전용)
# - data/fonts.csv 를 읽어서 AI 에게 폰트 정보를 알려 주는 서버예요.
# - 파일을 쓰거나 지우는 기능은 일부러 넣지 않았어요. 읽기만 해요.
# - 설치된 mcp 버전: 2.3.0 → 2.x 방식 import 를 써요.
#   (1.x 에서는 "from mcp.server.fastmcp import FastMCP" 였는데, 2.x 에서 이름이 MCPServer 로 바뀌었어요)
#
# 참고: 도구 이름은 영문으로 했어요(find_fonts 등).
#   MCP 표준과 Claude 같은 AI 앱이 도구 이름에 영문·숫자·_·- 만 허용하기 때문이에요.
#   대신 화면에 보이는 제목(title)과 설명은 한국어로 적었어요.

import csv  # CSV(엑셀 비슷한 표 파일)를 읽는 도구
from datetime import date  # 오늘 날짜를 알아내는 도구
from pathlib import Path  # 파일 위치(경로)를 다루는 도구
from typing import Annotated  # 입력칸에 설명을 붙일 때 쓰는 도구

from pydantic import Field  # 입력칸 설명을 적는 도구 (mcp 설치할 때 같이 깔려요)

from mcp.server.mcpserver import MCPServer  # mcp 2.x 의 서버 만들기 도구
from mcp.types import ToolAnnotations  # "이 도구는 읽기만 해요" 라는 표시를 붙이는 도구

# ── 파일 위치 ─────────────────────────────────────────
# 이 파이썬 파일이 있는 폴더(mcp/) 를 찾아요.
HERE = Path(__file__).resolve().parent
# 한 칸 위 폴더(font-note-mcp/) 안의 data/fonts.csv 를 가리켜요.
CSV_PATH = HERE.parent / "data" / "fonts.csv"

# 한줄평이 비어 있을 때 대신 보여 줄 문구
EMPTY_REVIEW = "아직 안 써 봄"

# 표의 칸 이름들 (CSV 첫 줄과 같은 순서)
COLUMNS = ["폰트이름", "분류", "분위기", "추천용도", "무료여부", "메모", "한줄평"]

# 모든 도구 설명에 공통으로 붙일 안내 문구
RULE = (
    "한줄평은 사용자가 직접 쓴 평가이니 추천할 때 우선 참고하고, "
    "노트에 없는 정보는 지어내지 말 것."
)

# 모든 도구에 붙일 "읽기 전용" 표시 (AI 앱이 안전한 도구로 알아봐요)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)

# ── 서버 만들기 ───────────────────────────────────────
mcp = MCPServer(
    name="font-note",  # 서버 이름
    # 서버 전체에 대한 안내 (AI 가 처음 연결할 때 읽어요)
    instructions=(
        "디자이너가 직접 정리한 한국어 폰트 노트(fonts.csv)를 읽기 전용으로 보여 주는 서버예요. "
        + RULE
    ),
)


# ── 도우미 함수들 (AI 에게 직접 보이지 않아요) ──────────
def load_fonts() -> list[dict]:
    """fonts.csv 를 읽어서 한 줄씩 목록으로 돌려줘요. 매번 새로 읽어서 파일을 고치면 바로 반영돼요."""
    # utf-8-sig: 엑셀이 파일 맨 앞에 붙이는 보이지 않는 표시(BOM)를 지워 주는 읽기 방식
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))  # 첫 줄을 칸 이름으로 써서 한 줄씩 읽기
    fonts = []  # 정리된 결과를 담을 빈 목록
    for row in rows:  # 한 줄씩 꺼내서
        # 각 칸의 앞뒤 공백을 지우고, 비어 있는 칸은 "" 로 맞춰요
        clean = {col: (row.get(col) or "").strip() for col in COLUMNS}
        if not clean["폰트이름"]:  # 폰트 이름이 없는 줄(빈 줄)은
            continue  # 건너뛰어요
        if not clean["한줄평"]:  # 한줄평이 비어 있으면
            clean["한줄평"] = EMPTY_REVIEW  # "아직 안 써 봄" 으로 채워요
        fonts.append(clean)  # 목록에 넣기
    return fonts  # 완성된 목록 돌려주기


def short_line(font: dict) -> str:
    """찾기 결과용 짧은 한 줄 요약을 만들어요."""
    return (
        f"- {font['폰트이름']} ({font['분류']}) | 분위기: {font['분위기']} | "
        f"추천용도: {font['추천용도']} | {font['무료여부']} | 한줄평: {font['한줄평']}"
    )


def full_card(font: dict) -> str:
    """상세 보기용으로 모든 칸을 한 줄씩 보여 줘요."""
    return "\n".join(f"{col}: {font[col] or '(비어 있음)'}" for col in COLUMNS)


def simplify(text: str) -> str:
    """이름 비교용: 띄어쓰기를 없애고 영문 대소문자를 같게 만들어요. (예: 'noto sans kr' = 'Noto Sans KR')"""
    return text.replace(" ", "").casefold()


# ── 도구 1: 폰트 찾기 ─────────────────────────────────
@mcp.tool(
    name="find_fonts",  # AI 가 부르는 이름 (영문)
    title="폰트_찾기",  # 사람에게 보이는 이름 (한글)
    annotations=READ_ONLY,  # 읽기 전용 표시
    description=(
        "폰트 노트에서 분위기와 용도로 폰트를 찾아요. "
        "'분위기' 칸에 mood 글자가 들어 있고, '추천용도' 칸에 usage 글자가 들어 있는 폰트만 골라요 "
        "(일부 글자만 맞아도 돼요. 예: mood='귀여' → '귀여운', usage='SNS' → '메모·SNS'). "
        "빈 값으로 두면 그 조건은 따지지 않고, 둘 다 비우면 노트의 전체 폰트를 보여 줘요. "
        "결과마다 폰트이름·분류·분위기·추천용도·무료여부·한줄평을 함께 보여 줘요. "
        "사용자가 '이런 느낌 폰트 추천해 줘', '포스터용 폰트 뭐 있어?' 처럼 물을 때 쓰세요. "
        "노트의 분위기 단어 예: 단정한, 고급스러운, 친근한, 차분한, 귀여운, 힘있는, 강렬한, 부드러운, 현대적인. "
        "용도 단어 예: UI, 본문, 제목, 포스터, SNS, 브랜딩, 긴 글. "
        "맞는 결과가 없으면 더 짧은 단어로 다시 찾아보세요. "
        + RULE
    ),
)
def 폰트_찾기(
    mood: Annotated[str, Field(description="분위기 칸에서 찾을 글자. 예: '귀여운', '단정'. 비우면 분위기는 따지지 않아요.")] = "",
    usage: Annotated[str, Field(description="추천용도 칸에서 찾을 글자. 예: 'SNS', '제목'. 비우면 용도는 따지지 않아요.")] = "",
) -> str:
    mood = mood.strip()  # 입력값 앞뒤 공백 지우기
    usage = usage.strip()  # 입력값 앞뒤 공백 지우기
    results = []  # 조건에 맞는 폰트를 담을 빈 목록
    for font in load_fonts():  # 노트의 폰트를 하나씩 보면서
        mood_ok = mood in font["분위기"]  # 분위기 칸에 그 글자가 있나? (빈 값이면 항상 '있음')
        usage_ok = usage in font["추천용도"]  # 추천용도 칸에 그 글자가 있나? (빈 값이면 항상 '있음')
        if mood_ok and usage_ok:  # 두 조건이 다 맞으면
            results.append(short_line(font))  # 결과에 넣기
    if not results:  # 하나도 없으면
        return f"조건(분위기: '{mood or '전체'}', 용도: '{usage or '전체'}')에 맞는 폰트가 노트에 없어요."
    # 몇 개 찾았는지 + 목록을 돌려줘요
    header = f"분위기 '{mood or '전체'}' · 용도 '{usage or '전체'}' → {len(results)}개 찾았어요."
    return header + "\n" + "\n".join(results)


# ── 도구 2: 폰트 상세 ─────────────────────────────────
@mcp.tool(
    name="font_detail",  # AI 가 부르는 이름 (영문)
    title="폰트_상세",  # 사람에게 보이는 이름 (한글)
    annotations=READ_ONLY,  # 읽기 전용 표시
    description=(
        "폰트 이름 하나를 받아서, 노트에 적힌 그 폰트의 모든 칸"
        "(폰트이름·분류·분위기·추천용도·무료여부·메모·한줄평)을 보여 줘요. "
        "이름은 띄어쓰기와 영문 대소문자를 무시하고 비교해요 (예: 'noto sans kr' 도 찾아요). "
        "노트에 없으면 '노트에 없는 폰트예요' 라고 답해요 — 이때 다른 곳의 정보로 채우지 마세요. "
        "사용자가 특정 폰트에 대해 '이거 어때?', '무료야?', '어디서 받아?' 처럼 물을 때 쓰세요. "
        + RULE
    ),
)
def 폰트_상세(
    font_name: Annotated[str, Field(description="찾을 폰트 이름. 예: 'Pretendard', '나눔명조'")],
) -> str:
    target = simplify(font_name)  # 비교하기 쉽게 입력값 정리
    for font in load_fonts():  # 노트의 폰트를 하나씩 보면서
        if simplify(font["폰트이름"]) == target:  # 이름이 같으면
            return full_card(font)  # 모든 칸을 보여 주고 끝
    return "노트에 없는 폰트예요"  # 끝까지 못 찾으면 이렇게 답하기


# ── 도구 3: 오늘의 폰트 ───────────────────────────────
@mcp.tool(
    name="font_of_the_day",  # AI 가 부르는 이름 (영문)
    title="오늘의_폰트",  # 사람에게 보이는 이름 (한글)
    annotations=READ_ONLY,  # 읽기 전용 표시
    description=(
        "오늘 날짜를 기준으로 노트에서 폰트 하나를 골라 모든 칸을 보여 줘요. "
        "같은 날에는 몇 번을 불러도 항상 같은 폰트가 나오고, 날짜가 바뀌면 다른 폰트가 나와요. "
        "입력값은 없어요. 사용자가 '오늘의 폰트', '아무 폰트나 하나 소개해 줘' 라고 할 때 쓰세요. "
        + RULE
    ),
)
def 오늘의_폰트() -> str:
    fonts = load_fonts()  # 노트 읽기
    if not fonts:  # 노트가 비어 있으면
        return "노트에 폰트가 하나도 없어요."
    today = date.today()  # 오늘 날짜 (컴퓨터 시계 기준)
    # 날짜를 숫자로 바꾼 뒤(서기 1년 1월 1일부터 며칠째인지) 폰트 개수로 나눈 나머지로 고르기
    # → 같은 날엔 같은 숫자라서 항상 같은 폰트, 다음 날엔 다음 폰트가 나와요
    pick = fonts[today.toordinal() % len(fonts)]
    return f"오늘({today.isoformat()})의 폰트예요.\n" + full_card(pick)


# ── 실행 ──────────────────────────────────────────────
# 실행 방법은 두 가지예요.
#   python mcp/font_server.py          → 내 PC 용 (stdio). .mcp.json 이 이 방식으로 켜요. (지금과 같아요)
#   python mcp/font_server.py --http   → 인터넷 주소용 (HTTP). 주소 끝은 /mcp 예요.
if __name__ == "__main__":
    import os  # 환경변수(서비스가 알려 주는 설정값)를 읽는 도구
    import sys  # 실행할 때 붙인 옵션(--http)을 읽는 도구
    from mcp.server.transport_security import TransportSecuritySettings  # 허용할 주소 목록 설정

    if "--http" in sys.argv:
        on_render = os.environ.get("RENDER") == "true"  # Render 위에서 실행 중인지
        port = int(os.environ.get("PORT", "8000"))  # Render 가 정해 주는 포트, 내 PC 에선 8000
        # 요청을 받아 줄 주소 목록: 내 PC 주소 + (Render 라면) Render 가 만들어 준 주소
        hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
        origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
        public = os.environ.get("RENDER_EXTERNAL_HOSTNAME")  # 예: font-note.onrender.com
        if public:
            hosts += [public, public + ":*"]
            origins += ["https://" + public]
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0" if on_render else "127.0.0.1",  # 내 PC 에선 나만 접속 가능하게
            port=port,
            stateless_http=True,  # 요청마다 독립 처리 → 서버가 재시작돼도 연결이 덜 끊겨요
            transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins),
        )
    else:
        mcp.run(transport="stdio")  # 기존과 똑같은 PC 용 실행
