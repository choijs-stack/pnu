import json

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
    # 4. 분석 프롬프트
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # 4. 분석 프롬프트
    # ---------------------------------------------------------
    prompt = f"""
        당신은 학술 논문 연구 동향 분석 전문가입니다.
        모든 분석 결과는 반드시 한국어로 작성하세요.

        [사용자 검색 키워드]
        {search_keyword_text}

        [분석 목적]
        사용자가 입력한 검색 키워드를 중심으로
        수집된 논문의 주요 연구 동향과 핵심 연구주제,
        연구 시사점을 도출하세요.

        [분석 원칙]
        1. 수집된 논문의 제목, 연구분야, 초록을 바탕으로
        검색 키워드와의 관련성을 판단하세요.

        2. 검색 키워드와 직접 관련된 논문을 우선적으로
        고려하여 주요 연구 동향을 분석하세요.

        3. 검색 키워드와 간접적으로 관련된 연구는
        실제 연관성이 확인되는 경우에만 반영하세요.

        4. 검색 키워드와 관련성이 낮은 연구 분야는
        핵심 연구주제 및 주요 시사점으로 선정하지 마세요.

        5. 서로 다른 연구 분야를 근거 없이
        하나의 연구 흐름으로 연결하지 마세요.

        6. 전체 수집 데이터에 다양한 연구 분야가 포함되어
        있더라도 검색 주제와의 관련성을 우선 고려하세요.

        7. 검색 주제와 관련된 근거가 부족한 경우
        임의로 연구 동향을 만들어내지 마세요.


    [1. 종합 분석]

    summary
    - 사용자 검색 키워드와 실질적으로 관련된 수집 논문만 근거로 학술적인 종합결론을 작성하세요.
    - 아래 3개 소제목을 순서대로 사용하고, 각 소제목 아래에 자연스러운 문단으로 서술하세요.
      ① 연구 분야 및 주요 분석 대상
      ② 주요 연구 내용 및 분석 결과
      ③ 연구 종합 및 결론
    - 자료가 충분할 때 전체 15~20문장 내외로 상세하게 작성하되, 문장 수를 채우기 위해 내용을 반복하거나 근거 없는 사실을 추가하지 마세요.
    - ①에서는 수집 자료에서 확인되는 주요 연구 분야, 대상과 범위를 개괄하되 개별 논문 내용을 장황하게 나열하지 마세요.
    - ②에서는 초록 또는 제공된 원문에 명시된 연구 내용과 실제 확인된 결과를 중심으로 구체적으로 설명하세요.
      연구 목적, 가설, 검토 대상만 제시된 경우 이를 확정된 연구 결과처럼 서술하지 마세요.
    - ③에서는 앞 문단의 연구 분야와 사례를 재나열하지 말고, 복수 자료에서 근거가 확인되는 공통점과 차이점 및 종합적으로 확인 가능한 결론을 작성하세요.
      공통 결론을 확인할 근거가 없다면 서로 다른 연구의 범위와 종합 분석의 한계를 명확히 설명하세요.
    - 연구 결과와 분석자의 해석을 혼동하지 말고, 자료에 명시되지 않은 역사적 사실, 수치, 인과관계, 추세, 학계의 합의나 연구 성과를 생성하지 마세요.
    - 일부 논문에서만 확인된 내용을 전체 연구의 공통 결과로 일반화하지 마세요.
    - 핵심 연구주제 TOP5의 세부 설명이나 연구 시사점의 내용을 그대로 반복하지 마세요.
    - 소제목 사이에는 빈 줄을 두고, 각 소제목의 본문도 필요하면 짧은 문단으로 나누세요.
    - 근거가 부족하면 15문장보다 짧게 작성하더라도 사실성과 비반복성을 우선하세요.

    trend
    - 검색 주제와 관련된 수집 자료에서 실제 확인되는 연구 접근 방식과 특징을 2~3문장으로 간결하게 작성하세요.
    - summary의 세부 사례를 반복하지 말고, 별도로 확인 가능한 특징만 서술하세요.
    - 시계열 비교 근거가 없으면 증가·감소·확대·최근 부상 등의 시간적 추세를 단정하지 마세요.
    - 별도로 확인 가능한 흐름이 없다면 빈 문자열로 작성하세요.


    [2. 핵심 주제]

    - 전체 자료에서 반복적으로 중요하게 다뤄지는 주제 3~5개를 선정하세요.
    - 유사한 주제는 하나로 통합하세요.
    - 특정 일부 자료에만 나타나는 내용보다 전체 자료에서 의미 있게 확인되는 주제를 우선하세요.
    - 단순 키워드가 아니라 내용을 대표할 수 있는 구체적인 주제명으로 작성하세요.
    - description은 반드시 2~3개의 완결된 문장으로 작성하세요.
    - description에는 해당 주제에서 실제로 다뤄지는 내용, 대상, 활용 분야 또는 주요 쟁점을 구체적으로 설명하세요.
    - 정책 제안이나 향후 대응방안은 작성하지 마세요.


    [3. 주요 시사점]

    - 여러 자료를 함께 보았을 때 확인되는 특징, 공통 쟁점,
      주제 간 관계 또는 관점의 차이를 2~4개 도출하세요.
    - 핵심 주제를 단순히 다시 요약하지 마세요.
    - 각 description은 반드시 2~3개의 완결된 문장으로 작성하세요.
    - 서로 다른 주제나 분야가 어떤 관계를 보이는지, 또는 전체 자료에서 어떤 특징이 확인되는지를 구체적으로 설명하세요.
    - 시사점은 제안이나 개선방안이 아니라 현재 수집 자료에서 관찰되는 의미를 설명하세요.
    - "~가 필요하다", "~해야 한다", "~이 필수적이다",
      "~이 요구된다", "~이 중요하다"와 같은
      권고·처방형 결론을 작성하지 마세요.
    - 자료에서 확인되지 않은 미래 전망이나 효과를 추측하지 마세요.


    [공통 원칙]

    - 반드시 제공된 자료에 근거하세요.
    - 일부 자료의 내용을 전체 경향으로 일반화하지 마세요.
    - 특정 분야에 자료가 집중되어 있더라도 다른 주요 분야가 충분히 존재한다면 함께 반영하세요.
    - 종합 분석, 핵심 주제, 주요 시사점의 내용이 반복되지 않도록 하세요.
    - 모든 분석 내용은 반드시 한국어로 작성하세요.
    - 문장 수보다 자료에 근거한 정확성과 비반복성을 우선하세요.
    - 초록이나 원문에 없는 결과를 보충하거나 추측하지 마세요.


    [수집 자료]

    {document_text}


    [출력 형식]

    아래 JSON 구조를 정확하게 지켜서 JSON만 출력하세요.
    key 이름을 변경하거나 새로운 key를 추가하지 마세요.
    모든 value는 반드시 한국어로 작성하세요.

    {{
        "overall_analysis": {{
            "summary": "3개 소제목과 문단으로 구분한 근거 중심 종합결론",
            "trend": "중복되지 않는 2~3문장의 자료 기반 특징 또는 빈 문자열"
        }},
        "key_topics": [
            {{
                "topic": "핵심 주제명",
                "description": "2~3문장으로 작성한 주요 내용"
            }}
        ],
        "implications": [
            {{
                "title": "시사점 제목",
                "description": "2~3문장으로 작성한 특징 또는 의미"
            }}
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
    # 7. 완료    # ---------------------------------------------------------
    print(
        "LLM 분석 완료"
    )

    return result
