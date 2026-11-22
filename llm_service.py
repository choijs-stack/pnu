import json
import re

from langchain_ollama import ChatOllama

from db import get_db_connection
from analysis_service import get_analysis_article_ids

# =========================================================
# LLM 응답 JSON 변환
# =========================================================
def parse_llm_json(content):
    """
    LLM 응답에서 JSON 객체를 추출하여 Python dict로 변환하고
    필수 JSON 구조가 존재하는지 확인한다.
    """

    if not content:
        return None

    content = content.strip()

    # -----------------------------------------------------
    # Markdown 코드블록 제거
    #
    # 예:
    # ```json
    # {...}
    # ```
    # -----------------------------------------------------
    content = content.replace("```json", "")
    content = content.replace("```JSON", "")
    content = content.replace("```", "")
    content = content.strip()

    # -----------------------------------------------------
    # JSON 객체 시작/끝 위치 추출
    #
    # LLM이 JSON 앞뒤에 설명을 붙여도
    # 첫 번째 { 부터 마지막 } 까지만 파싱한다.
    # -----------------------------------------------------
    start = content.find("{")
    end = content.rfind("}")

    if start == -1 or end == -1 or start >= end:
        print(
            "LLM 응답에서 JSON 객체를 찾지 못했습니다."
        )

        print(
            "===== LLM RAW RESPONSE ====="
        )

        print(content)

        print(
            "============================"
        )

        return None

    json_text = content[start:end + 1]

    # -----------------------------------------------------
    # JSON 파싱
    # -----------------------------------------------------
    try:
        result = json.loads(json_text)

    except json.JSONDecodeError as e:

        print(
            f"LLM JSON 파싱 오류: "
            f"line={e.lineno}, "
            f"column={e.colno}, "
            f"message={e.msg}"
        )

        print(
            "===== JSON 파싱 대상 ====="
        )

        print(json_text)

        print(
            "=========================="
        )

        return None

    # -----------------------------------------------------
    # JSON 객체 여부 확인
    # -----------------------------------------------------
    if not isinstance(result, dict):
        print(
            "LLM 응답이 JSON 객체(dict)가 아닙니다."
        )
        return None

    # -----------------------------------------------------
    # 필수 최상위 key 확인
    # -----------------------------------------------------
    required_keys = [
        "overall_analysis",
        "key_topics",
        "implications"
    ]

    for key in required_keys:

        if key not in result:

            print(
                f"LLM 응답 필수 key 누락: {key}"
            )

            return None

    return result


# =========================================================
# LLM 분석용 데이터 조회
# =========================================================
def get_analysis_documents(
    req_idntf,
    excn_idntfs
):
    """
    특정 수집 요청(REQ_IDNTF) 중
    지정된 수집 실행(EXCN_IDNTF)의 데이터만 조회한다.
    """

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        # EXCN_IDNTF가 없으면 분석 범위를 특정할 수 없음
        if not excn_idntfs:

            raise ValueError(
                "excn_idntfs가 비어 있습니다."
            )

        # -----------------------------------------------------
        # IN 조건 placeholder 생성
        #
        # 예:
        # [87, 88, 89]
        # -> %s, %s, %s
        # -----------------------------------------------------
        placeholders = ", ".join(
            ["%s"] * len(excn_idntfs)
        )

        sql = f"""
            SELECT
                a.ARTCL_IDNTF,
                a.SRC_NM,
                a.TTL,
                a.SUBJECT,
                a.ABST,
                a.ORGINL_CN,
                a.PBLCN_YM
            FROM CLCT_ARTCL a
            INNER JOIN CLCT_EXCN e
                ON a.EXCN_IDNTF = e.EXCN_IDNTF
            WHERE e.REQ_IDNTF = %s
              AND e.EXCN_IDNTF IN ({placeholders})
            ORDER BY a.ARTCL_IDNTF
        """

        params = (
            req_idntf,
            *excn_idntfs
        )

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        print(
            f"LLM 분석 대상 조회: "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_IDNTFS={excn_idntfs}, "
            f"{len(rows)}건"
        )

        return rows

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()

# def get_analysis_documents(
#     req_idntf,
#     excn_idntfs
# ):
#     """
#     사이트별 분석 제한이 적용된 논문만
#     LLM 분석 대상으로 조회한다.
#     """

#     conn = None
#     cursor = None

#     try:

#         # -----------------------------------------------------
#         # 1. 사이트별 분석 대상 논문 ID 선정
#         # -----------------------------------------------------

#         article_ids = get_analysis_article_ids(
#             req_idntf=req_idntf,
#             excn_idntfs=excn_idntfs
#         )

#         if not article_ids:

#             print(
#                 f"LLM 분석 대상 없음: "
#                 f"REQ_IDNTF={req_idntf}, "
#                 f"EXCN_IDNTFS={excn_idntfs}"
#             )

#             return []

#         print(
#             f"LLM 분석 대상 ID 선정 완료: "
#             f"{len(article_ids)}건"
#         )

#         # -----------------------------------------------------
#         # 2. 선정된 논문만 DB 조회
#         # -----------------------------------------------------

#         conn = get_db_connection()

#         cursor = conn.cursor(
#             dictionary=True
#         )

#         placeholders = ", ".join(
#             ["%s"] * len(article_ids)
#         )

#         sql = f"""
#             SELECT
#                 a.ARTCL_IDNTF,
#                 a.SRC_NM,
#                 a.TTL,
#                 a.SUBJECT,
#                 a.ABST,
#                 a.ORGINL_CN,
#                 a.PBLCN_YM
#             FROM CLCT_ARTCL a
#             WHERE a.ARTCL_IDNTF IN ({placeholders})
#             ORDER BY
#                 CASE
#                     WHEN a.PBLCN_YM IS NULL
#                          OR TRIM(a.PBLCN_YM) = ''
#                     THEN 1
#                     ELSE 0
#                 END ASC,
#                 a.PBLCN_YM DESC,
#                 a.ARTCL_IDNTF DESC
#         """

#         params = tuple(
#             article_ids
#         )

#         cursor.execute(
#             sql,
#             params
#         )

#         rows = cursor.fetchall()

#         # -----------------------------------------------------
#         # 3. 사이트별 실제 분석 건수 로그
#         # -----------------------------------------------------

#         site_counts = {}

#         for row in rows:

#             site_name = (
#                 row.get("SRC_NM")
#                 or ""
#             ).strip()

#             site_counts[site_name] = (
#                 site_counts.get(
#                     site_name,
#                     0
#                 )
#                 + 1
#             )

#         print(
#             f"LLM 사이트별 분석 대상: "
#             f"{site_counts}"
#         )

#         print(
#             f"LLM 분석 대상 조회: "
#             f"REQ_IDNTF={req_idntf}, "
#             f"EXCN_IDNTFS={excn_idntfs}, "
#             f"{len(rows)}건"
#         )

#         return rows

#     finally:

#         if cursor:
#             cursor.close()

#         if conn and conn.is_connected():
#             conn.close()
# =========================================================
# LLM 입력 데이터 생성
# =========================================================
def make_document_text(row):
    """
    한 건의 수집 데이터를 LLM 입력용 문자열로 변환한다.

    ABST(초록)가 있으면 초록을 사용하고,
    초록이 없으면 ORGINL_CN(원문)을 사용한다.
    """

    source = (
        row.get("SRC_NM")
        or ""
    )

    title = (
        row.get("TTL")
        or ""
    )

    subject = (
        row.get("SUBJECT")
        or ""
    )

    abstract = (
        row.get("ABST")
        or ""
    )

    original = (
        row.get("ORGINL_CN")
        or ""
    )

    publication = (
        row.get("PBLCN_YM")
        or ""
    )

    abstract = abstract.strip()
    original = original.strip()

    # 초록 우선 사용
    if abstract:
        content = abstract

    else:
        content = original

    return f"""
[수집 자료]
출처: {source}
발행시기: {publication}
제목: {title}
분야: {subject}
내용:
{content}
""".strip()


# =========================================================
# 전체 수집 결과 LLM 분석
# =========================================================
def get_search_keywords(req_idntf):
    conn = get_db_connection()
    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT KWRD
            FROM CLCT_REQ_KWRD
            WHERE REQ_IDNTF = %s
            ORDER BY SNO
        """

        cursor.execute(query, (req_idntf,))
        rows = cursor.fetchall()

        return [
            row["KWRD"].strip()
            for row in rows
            if row["KWRD"] and row["KWRD"].strip()
        ]

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

def get_llm_analysis(
    req_idntf,
    excn_idntfs,
    model_name="gpt-oss:20b",
    base_url="http://192.168.2.171:11434"
):
    """
    특정 수집 요청(REQ_IDNTF) 중
    지정된 수집 실행(EXCN_IDNTF)의 데이터를
    LLM으로 종합 분석한다.
    """

    # ---------------------------------------------------------
    # 1. 데이터 조회
    # ---------------------------------------------------------
    rows = get_analysis_documents(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs
    )
    # 사용자 검색 키워드 조회
    search_keywords = get_search_keywords(req_idntf)

    search_keyword_text = ", ".join(search_keywords)

    print(f"분석 검색 키워드: {search_keyword_text}")

    if not rows:

        print(
            f"LLM 분석 대상 데이터 없음: "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_IDNTFS={excn_idntfs}"
        )

        return {
            "overall_analysis": {
                "summary": "",
                "trend": ""
            },
            "key_topics": [],
            "implications": []
        }

    print(
        f"LLM 분석 시작: "
        f"REQ_IDNTF={req_idntf}, "
        f"EXCN_IDNTFS={excn_idntfs}, "
        f"데이터={len(rows)}건"
    )

    # ---------------------------------------------------------
    # 2. LLM 입력 데이터 생성
    # ---------------------------------------------------------
    documents = [
        make_document_text(row)
        for row in rows
    ]

    document_text = "\n\n".join(
        documents
    )

    print(
        f"LLM 입력 데이터 생성 완료: "
        f"{len(document_text)}자"
    )

    # ---------------------------------------------------------
    # 3. LLM 설정
    # ---------------------------------------------------------
    llm = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.1
    )

    # ---------------------------------------------------------
    # 4. GPT-OSS 20B 분석 프롬프트
    # 기존 JSON 키와 API 계약 유지
    # ---------------------------------------------------------
    prompt = f"""
당신은 대학 연구기획을 지원하는 학술 연구동향 분석가입니다.
모델은 GPT-OSS 20B입니다. 한국어로 분석하고 반드시 유효한 JSON 객체 하나만 출력하세요.

[사용자 검색어]
{search_keyword_text}

[분석 범위와 근거 원칙]
- 입력된 수집 자료는 총 {len(rows)}건입니다. 검색 주제와 관련된 자료만 핵심 분석에 활용하세요.
- 수집 자료 전체를 읽고, 유사한 논문을 연구군으로 묶어 비교·종합하세요. 논문별 나열은 피하세요.
- 기술명, 약어, 에너지원, 정책, 수치, 연구 대상, 실험 환경은 원문에 명시된 것만 '확인된 성과'로 서술하세요.
- 서로 다른 논문의 기술·수치·실험 조건을 하나의 논문 성과처럼 합치지 마세요.
- 약어 의미가 불명확하면 임의로 풀어 쓰지 마세요. 예: SMR을 문맥 없이 특정 발전원으로 단정하지 마세요.
- 특정 수치의 대상·조건이 불명확하면 그 수치를 생략하세요. 성능 수치는 연구별로 구분해 설명하세요.
- 논문에 없는 한계(실증 부재, 해석가능성 부족 등)는 단정하지 말고 검토 필요 사항으로 표현하세요.
- 시계열 비교가 불가능하면 증가·감소·급부상·확대 추세를 단정하지 마세요.
- 실제 논문 성과와 AI가 도출한 '연계 가능성', '후속 연구 제안'을 명확히 구분하세요.
- 검색어와 무관한 자료가 포함되어 있으면 연구 흐름에 억지로 끼워 넣지 마세요.
- 내부 ID, 가상의 논문·출처·URL, 존재하지 않는 수치나 실험 결과를 만들어내지 마세요.

[분석 깊이와 각 필드 역할]
- 내용이 풍부한 경우에도 지나치게 요약하지 마세요. 핵심 연구군의 구체적 기술·성과·차이를 충분히 설명하세요.
- 같은 내용을 문장만 바꿔 여러 항목에 반복하지 마세요.
- overall_analysis.summary = 검증된 성과와 연구 간 비교·해석 중심.
- overall_analysis.trend = 수집 자료에서 관찰되는 연구 방향과 기술 발전 가능성 중심.
- key_topics = 실제 확인된 연구군의 간결한 이름과 설명.
- implications = 연구기획자가 실행할 수 있는 후속 연구 과제와 검증 방안.

[overall_analysis.summary 작성]
다음 Markdown 소제목을 정확히 순서대로 사용하세요.
### 핵심 연구 흐름 및 주요 성과
### 연구 간 차별성 및 연계성
### 종합 결론 및 분석 한계

1) 핵심 연구 흐름 및 주요 성과
- 실제 자료에서 확인되는 주요 연구군을 3~6개 선정해 각 연구군을 2~4문장으로 설명하세요.
- 각 연구군마다 연구 대상, 사용 기술·방법, 실제 제시된 성과와 의미를 구분하세요.
- 실험 수치가 있으면 그 논문의 조건과 범위를 함께 설명하세요. 근거 없는 수치 비교는 금지합니다.
- 내용이 충분하면 Markdown 글머리표를 사용하되 각 항목을 한 줄짜리 단문으로 끝내지 마세요.

2) 연구 간 차별성 및 연계성
- 의미 있는 비교 3~5개를 제시하세요. 각각 연구 A와 B의 방법·적용 범위 차이, 상호 보완성, 연결 시 해결할 문제를 설명하세요.
- 서로 다른 논문의 연계는 확인된 사실이 아니라 '연계 가능성'으로 표시하세요.
- 같은 논문의 성과를 첫 절에서와 똑같이 반복하지 마세요.

3) 종합 결론 및 분석 한계
- 검색 주제와 관련된 공통 기술 과제와 연구기획상 의미를 2~3문단으로 정리하세요.
- 자료 건수·연도·수집 범위의 한계, 논문에 명시된 검증 한계를 구분하세요.
- 전체 학계의 대표적 추세처럼 일반화하지 마세요.

[overall_analysis.trend 작성]
다음 Markdown 소제목을 정확히 순서대로 사용하세요.
### 연구동향 및 변화
### 신흥 연구 후보 및 기술 발전 방향

1) 연구동향 및 변화
- 논문을 단순히 분야별로 열거하지 말고, 수집 자료에서 드러나는 연구 접근법의 공통점·차이·기술적 연결을 2~4개 항목으로 분석하세요.
- 연도별 비교가 없으면 '수집 자료에서 관찰된 연구 방향'으로만 기술하고 증가·감소를 주장하지 마세요.
- 변화 근거가 없다는 설명을 반복하지 말고 실제 기술적 관찰과 해석에 집중하세요.

2) 신흥 연구 후보 및 기술 발전 방향
- 입력 논문에서 확인된 기술 2~4개를 바탕으로 새로운 기술 융합·확장 가능성을 제시하세요.
- 각 항목에 '기존 연구 근거 → 발전 방향 → 해결해야 할 기술적 쟁점'을 포함하세요.
- 미래 제안임을 분명히 하고 이미 실증된 결과처럼 쓰지 마세요.
- 후속 연구과제의 상세 실험 설계는 implications에 맡기세요.

[key_topics 작성]
- 수집 자료에서 실제 확인되는 대표 연구군 3~5개를 선정하세요. 근거가 부족하면 더 적게 제시하세요.
- topic은 한국어 명사형 주제명만 작성하세요. 영어 제목을 그대로 복사하지 마세요.
- topic에 숫자·순위·번호·Markdown 기호를 넣지 마세요. 화면에서 별도로 번호를 붙입니다.
- description은 해당 연구군의 핵심 방법·대상·성과를 1~2문장으로 설명하세요.

[implications 작성]
- 서로 다른 후속 연구기획 과제 2~4개를 제안하세요. title은 한국어 명사형으로 작성하세요.
- 각 description은 3~5문장으로 충분히 구체적으로 작성하세요.
- 다음 네 요소를 자연스럽게 포함하세요: (1) 출발 근거 (2) 해결할 문제 (3) 제안 연구 방법 (4) 검증 데이터·평가 지표.
- 검증 지표는 기술적으로 적합한 항목을 제안할 수 있으나, 원문에 없는 목표 수치·실험 기간·실험 대상 수·특정 표준 시험망을 임의로 확정하지 마세요.
- 필요시 '예를 들어'로 제안 방법을 명시하고, 실제 수행·검증이 완료된 것처럼 표현하지 마세요.
- trend와 주제가 겹치더라도 동일한 설명을 복제하지 말고 구체적인 연구 설계·검증 차별성에 집중하세요.
- 결과가 검증되지 않은 제안의 효과를 확정적으로 표현하지 마세요.

[JSON 및 Markdown 출력 규칙]
- 출력은 JSON 객체 하나만. 코드펜스·설명문·추가 키는 금지합니다.
- overall_analysis.summary와 overall_analysis.trend의 문자열 내부에만 Markdown 제목·글머리표·단락을 사용하세요.
- JSON 문자열의 줄바꿈은 JSON 규칙에 맞게 백슬래시+n으로 인코딩하세요.
- key_topics와 implications의 제목·설명에는 Markdown 번호, 별표, 이스케이프된 별표를 쓰지 마세요.
- 모든 제목은 한국어로 작성하세요. 학술 약어는 필요한 경우 원어 병기할 수 있습니다.
- 자료가 불충분하면 내용을 지어내지 말고 불확실성을 명시하세요.

[수집 자료 시작]
{document_text}
[수집 자료 끝]

[반환할 JSON 스키마 — 설명용이며 실제 값으로 대체]
{{
  "overall_analysis": {{
    "summary": "### 핵심 연구 흐름 및 주요 성과\n- 연구군별 구체적 성과...\n\n### 연구 간 차별성 및 연계성\n- 비교 분석...\n\n### 종합 결론 및 분석 한계\n- 종합 결론...",
    "trend": "### 연구동향 및 변화\n- 기술적 관찰...\n\n### 신흥 연구 후보 및 기술 발전 방향\n- 미래 기술 후보..."
  }},
  "key_topics": [
    {{"topic": "한국어 연구주제명", "description": "해당 연구군의 실제 내용"}}
  ],
  "implications": [
    {{"title": "한국어 후속 연구과제명", "description": "출발 근거, 제안 방법, 검증 지표"}}
  ]
}}
"""

    # ---------------------------------------------------------
    # 5. LLM 호출
    # ---------------------------------------------------------
    try:

        print(
            "LLM 호출 시작"
        )

        response = llm.invoke(
            prompt
        )

        print(
            f"LLM 응답 수신: "
            f"{len(response.content)}자"
        )

        print(
            "===== 이번 LLM 응답 ====="
        )

        print(
            response.content
        )

        print(
            "========================="
        )

    except Exception as e:

        print(
            "LLM 호출 실패"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        return {
            "overall_analysis": {
                "summary": "",
                "trend": ""
            },
            "key_topics": [],
            "implications": [],
            "error": str(e)
        }

    # ---------------------------------------------------------
    # 6. JSON 변환
    # ---------------------------------------------------------
    result = parse_llm_json(
        response.content
    )

    if result is None:

        print(
            "LLM JSON 파싱 실패"
        )

        print(
            "===== LLM RAW RESPONSE ====="
        )

        print(
            response.content
        )

        print(
            "============================"
        )

        return {
            "overall_analysis": {
                "summary": "",
                "trend": ""
            },
            "key_topics": [],
            "implications": [],
            "error":
                "LLM 응답 JSON 파싱 실패"
        }

    # ---------------------------------------------------------
    # 7. 리스트 제목 출력 보정
    # GPT-OSS 20B가 제목에 순위 번호/Markdown을 붙여도
    # 프론트엔드 번호와 중복되지 않도록 정리한다.
    # ---------------------------------------------------------
    def clean_list_title(value):
        if not isinstance(value, str):
            return value
        value = value.strip().replace(r"\*", "*")
        value = re.sub(r"^\*{1,2}(.*?)\*{1,2}$", r"\1", value).strip()
        value = re.sub(r"^\s*(?:[1-9][0-9]?\s*[.)．:：-]?\s*|[①-⑳]\s*)", "", value)
        return value.strip(" *\t\r\n")

    for item in result.get("key_topics", []):
        if isinstance(item, dict):
            item["topic"] = clean_list_title(item.get("topic", ""))

    for item in result.get("implications", []):
        if isinstance(item, dict):
            item["title"] = clean_list_title(item.get("title", ""))

    # ---------------------------------------------------------
    # 7. 완료    # ---------------------------------------------------------
    print(
        "LLM 분석 완료"
    )

    return result
