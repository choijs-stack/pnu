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
    # 4. GPT-OSS 20B 분석 프롬프트
    # 기존 JSON 키와 API 계약 유지
    # ---------------------------------------------------------
    prompt = f"""
당신은 학술 연구동향을 분석하는 연구기획 전문 분석가입니다.
반드시 한국어로 답하고, 아래 JSON 객체 하나만 반환하세요.

[검색 키워드]
{search_keyword_text}

[분석 자료 범위]
- 제공된 수집 자료 {len(rows)}건이 전체 분석 모집단입니다.
- 검색 키워드와 직접 관련된 자료를 우선하고, 무관한 자료는 핵심 결론에서 제외하세요.
- 수집 자료만으로 전체 학계·산업계의 경향을 대표한다고 주장하지 마세요.
- 제목·초록·제공된 원문에 없는 수치, 비교 결과, 인과관계, 정책·법률 효과를 만들지 마세요.
- 서로 다른 논문의 수치·성과를 동일 조건에서 비교한 것처럼 서술하지 마세요.
- 실제 논문에 제시된 결과, 여러 논문을 비교한 분석적 해석, 미래 연구 제안을 구분하세요.
- 원문에서 확인할 수 없는 한계(예: 해석가능성이 낮음, 실증 부족)를 사실로 단정하지 마세요.
- 연도별 비교 근거가 없으면 증가·감소·급부상·확대·쇠퇴·최근 각광 등의 추세 표현을 금지합니다.
- 데이터가 단일 연도 또는 소수 논문에 한정되면 그 한계를 정확히 밝히세요.
- 자료에 등장하지 않은 기술을 연구 성과처럼 소개하지 마세요.
- 외부 URL, 논문 식별자, 내부 DB ID, 인용번호를 만들어 넣지 마세요.

[필드별 역할 — 중복 금지]
1. overall_analysis.summary: 연구 성과와 연구 간 차별성·연계성 및 종합 결론.
2. overall_analysis.trend: 자료로 확인 가능한 연구 접근법의 분포·특징 및 미래 기술 발전 가능성.
3. key_topics: 실제 자료에 나타난 핵심 연구주제 3~5개를 간결하게 설명.
4. implications: 연구자가 기획할 수 있는 구체적 후속 연구과제 2~4개 제안.
같은 문장이나 같은 제안을 여러 필드에 반복하지 마세요.

[overall_analysis.summary 작성 지침]
- 아래 세 개의 Markdown 소제목을 정확히 이 순서로 사용하세요.
  ### 핵심 연구 흐름 및 주요 성과
  ### 연구 간 차별성 및 연계성
  ### 종합 결론 및 분석 한계
- 첫째 절: 검색 주제와 관련된 주요 연구군을 묶어 기술·방법·검증 결과를 구체적으로 설명하세요.
  자료에 수치가 실제 제시된 경우에만 수치를 사용하고, 어떤 연구의 수치인지 구분하세요.
- 둘째 절: 유사 연구 간 접근법 차이, 보완 관계, 통합 가능성을 근거 중심으로 설명하세요.
  단순한 공통 목적만으로 직접적인 연구 연계가 입증된 것처럼 쓰지 마세요.
- 셋째 절: 관찰 가능한 공통 결론, 분석 대상의 대표성 및 검증 한계를 설명하세요.
- 각 절은 내용이 충분하면 2~4개의 완결된 문장 또는 짧은 문단으로 구성하세요.
  자료가 적으면 분량을 줄이세요. 같은 논문 설명을 반복하지 마세요.
- Markdown은 제목(###), 단락, 필요한 경우 글머리표(-)만 사용하세요.
  별표와 역슬래시를 이중으로 이스케이프하지 마세요.

[overall_analysis.trend 작성 지침]
- 아래 두 개의 Markdown 소제목을 순서대로 사용하세요.
  ### 연구동향 및 변화
  ### 신흥 연구 후보 및 기술 발전 방향
- 첫째 절: 현재 수집 자료에서 확인되는 연구 방법·응용 분야의 분포와 특징을 설명하세요.
  연도별 비교 자료가 실제 존재할 때만 시계열 변화 방향을 언급하세요.
  비교가 불가능하면 '수집 자료에서 관찰되는 연구 방향'이라고 명시하세요.
- 둘째 절: 현재 확인된 기술을 토대로 2~3개의 구체적인 기술 융합 또는 발전 가능성을 제시하세요.
  각 후보는 (1) 기존 연구의 근거, (2) 제안되는 기술 결합·확장, (3) 검증할 핵심 쟁점을 포함하세요.
  이는 확인된 연구 성과가 아니라 '향후 연구 후보'라는 표현을 사용하세요.
- '실제 환경에서 검증이 필요하다'라는 일반론만 반복하지 마세요.
- 해당 방향을 뒷받침할 근거가 부족하면 억지로 후보를 채우지 마세요.

[key_topics 작성 지침]
- 실제 수집 자료에 나타난 연구군을 대표하는 3~5개 주제를 선정하세요.
- topic은 짧은 주제명만 작성하세요. 숫자, 순위, Markdown 번호, 별표를 넣지 마세요.
  예: '태양광 발전량 예측 및 MPPT 제어'
- description은 해당 분야에서 다룬 기술과 연구 대상을 2문장 내외로 설명하세요.
- 미래 기술 제안이나 정책 권고는 이 필드에 쓰지 마세요.
- 의미 있는 주제가 3개 미만이면 실제 확인된 주제 수만 작성하세요.

[implications 작성 지침]
- 전체 자료에서 도출할 수 있는 후속 연구기획 과제 2~4개를 제안하세요.
- title은 번호 없는 구체적인 과제명으로 작성하세요.
- description은 2~3문장으로 다음을 명확히 제시하세요.
  ① 어떤 연구 결과·한계에서 출발하는지
  ② 무엇을 결합·개선·비교할 것인지
  ③ 어떤 데이터·실험·평가 지표로 검증할 것인지
- trend에서 제시한 미래 기술 후보를 문장만 바꿔 반복하지 마세요.
  trend는 기술 발전 가능성, implications는 실행 가능한 연구설계와 검증방법에 집중하세요.
- 실현 가능성과 효과가 아직 검증되지 않았다면 예상 효과를 확정적으로 쓰지 마세요.

[출력 규칙]
- JSON 외의 해설, 코드펜스, 서두, 맺음말을 출력하지 마세요.
- JSON 문자열 내 실제 줄바꿈은 반드시 \n으로 이스케이프하세요.
- 키 이름 및 자료형을 정확히 유지하고 추가 키를 만들지 마세요.
- Markdown은 overall_analysis.summary 및 overall_analysis.trend 문자열 안에서만 사용하세요.
- key_topics 및 implications에는 Markdown 번호를 사용하지 마세요.
- 충분한 근거가 없는 항목은 내용을 지어내지 말고 생략하세요.

[수집 자료]
{document_text}

[반환 JSON 형식]
{{
  "overall_analysis": {{
    "summary": "### 핵심 연구 흐름 및 주요 성과\n...\n\n### 연구 간 차별성 및 연계성\n...\n\n### 종합 결론 및 분석 한계\n...",
    "trend": "### 연구동향 및 변화\n...\n\n### 신흥 연구 후보 및 기술 발전 방향\n..."
  }},
  "key_topics": [
    {{"topic": "번호 없는 연구주제명", "description": "근거 중심의 설명"}}
  ],
  "implications": [
    {{"title": "번호 없는 후속 연구과제명", "description": "근거, 연구설계, 검증방법"}}
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
