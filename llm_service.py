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
def get_llm_analysis(
    req_idntf,
    excn_idntfs,
    model_name="gpt-oss:20b",
    base_url="http://210.107.60.21:11434"
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
    prompt = f"""
    입력 자료의 언어와 관계없이 모든 분석 결과는 반드시 한국어로 작성하세요.

    다음은 사용자가 지정한 검색 조건에 따라 수집된 자료입니다.
    개별 자료를 나열하거나 각각 요약하지 말고,
    전체 자료에서 반복적으로 나타나는 내용과 공통적인 흐름을 종합하여 분석하세요.

    특정 일부 자료나 특정 분야에만 치우치지 말고,
    전체 수집 자료에서 확인되는 주요 분야와 주제를 균형 있게 반영하세요.


    [1. 종합 분석]

    summary
    - 전체 자료가 전반적으로 무엇을 다루는지 반드시 5~7개의 완결된 문장으로 작성하세요.
    - 5문장 미만으로 작성하지 마세요.
    - 전체 자료에서 공통적으로 확인되는 주요 연구 주제, 적용 분야, 기술 또는 쟁점을 포함하세요.
    - 주요 주제들이 어떤 맥락에서 함께 다뤄지고 있는지 구체적으로 설명하세요.
    - 특정 자료나 일부 분야의 내용만으로 전체 자료를 대표하지 마세요.
    - 단순한 키워드 나열이나 한두 문장의 요약으로 작성하지 마세요.

    trend
    - 전체 자료를 함께 보았을 때 관찰되는 주요 흐름이나 특징을 반드시 3~5개의 완결된 문장으로 작성하세요.
    - 3문장 미만으로 작성하지 마세요.
    - 어떤 주제, 기술, 적용 분야 또는 쟁점이 서로 연결되어 나타나는지 설명하세요.
    - 단순한 키워드 또는 짧은 구문을 나열하지 마세요.
    - 시간적 근거가 없는 경우 증가·감소·확대 등의 변화로 단정하지 마세요.


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
    - 지정한 최소 문장 수를 반드시 준수하세요.


    [수집 자료]

    {document_text}


    [출력 형식]

    아래 JSON 구조를 정확하게 지켜서 JSON만 출력하세요.
    key 이름을 변경하거나 새로운 key를 추가하지 마세요.
    모든 value는 반드시 한국어로 작성하세요.

    {{
        "overall_analysis": {{
            "summary": "5~7문장으로 작성한 종합 분석",
            "trend": "3~5문장으로 작성한 주요 흐름 또는 특징"
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
    # 7. 완료
    # ---------------------------------------------------------
    print(
        "LLM 분석 완료"
    )

    return result