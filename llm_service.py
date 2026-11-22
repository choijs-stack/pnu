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
        temperature=0.1,
        num_predict=6500  # 상세 분석을 위한 출력 토큰 상한(서버 성능에 따라 조정)
    )

    # ---------------------------------------------------------
    # 4. GPT-OSS 20B 분석 프롬프트
    # 기존 JSON 키와 API 계약 유지
    # ---------------------------------------------------------
    prompt = f"""
당신은 대학 연구기획을 지원하는 학술 연구동향 분석가입니다.
GPT-OSS 20B 모델에 적합하도록 지시를 간결하고 명확하게 따르세요.
**반드시 한국어로 작성하고, 유효한 JSON 객체 하나만 출력하세요.**

[검색어]
{search_keyword_text}

[자료와 근거 규칙 — 최우선]
- 입력 자료 {len(rows)}건에서 검색 주제와 직접 관련된 논문만 분석하세요. 무관한 논문은 제외하세요.
- 개별 논문의 연구 대상, 기술명, 수치, 실험 조건을 혼합하거나 임의로 만들지 마세요.
- 예: 태양광 발전을 '광속 발전'이라고 바꾸지 마세요. 용어를 임의 번역하지 말고 일관되게 사용하세요.
- 수치 성과는 원문에 있는 경우에만 해당 연구의 조건과 함께 서술하세요. 근거가 불명확하면 수치를 생략하세요.
- 논문에 명시되지 않은 실증 부족, 해석가능성 부족 등의 한계는 사실처럼 단정하지 마세요.
- 연도별 비교 근거가 없으면 '증가', '감소', '급부상', '확대 추세'라는 표현을 사용하지 마세요.
- 미래 기술 융합 및 연구 설계는 **AI 제안**임을 명시하고, 검증된 연구 성과와 구분하세요.
- 논문에 없는 실험 기간(예: 1년), 표본 수(예: 3~5개 건물), 목표 성능 수치, 시험망 이름을 임의로 설정하지 마세요.
- SMR 등 약어의 의미가 불분명하면 확정적으로 해석하지 마세요.
- 자료에 없는 링크, 논문, 출처, 내부 ID를 출력하지 마세요.

[핵심 품질 기준]
- **짧은 요약이 아니라 충분한 깊이의 종합분석**을 작성하세요. 구체적 연구 방법·성과·차이·의미를 포함하세요.
- 문장 수를 채우기 위해 근거 없는 사실을 생성하지 마세요. 자료가 적으면 분석 깊이를 적절히 조절하세요.
- 각 섹션의 역할을 분리하고, 같은 내용을 단순히 반복하지 마세요.
- 단순한 분야 나열이나 '추가 검증 필요'라는 상투적 결론만 쓰지 마세요.
- 내용이 충분한 경우 아래 목표 분량을 따르세요. **총 문장 수보다 내용의 근거와 분석 밀도를 우선**하세요.

[overall_analysis.summary: 종합분석 — 가장 중요]
다음 세 Markdown 제목을 정확히 사용하고, 각 제목 다음에는 반드시 줄바꿈을 넣으세요.

### 핵심 연구 흐름 및 주요 성과
- 서로 관련된 논문을 3~6개 연구군으로 묶어 분석하세요.
- 연구군마다 3~5문장: 연구 목적 → 실제 사용한 방법·기술 → 확인된 결과 → 해당 성과의 기술적 의미.
- 단순히 논문을 나열하지 말고 공통 기술 과제를 중심으로 설명하세요.
- 연구군별 내용이 충분하면 Markdown 글머리표로 구분하세요.

### 연구 간 차별성 및 연계성
- 중요한 비교 3~5개를 선정해 각 비교를 3~4문장으로 상세하게 설명하세요.
- 어떤 접근이 어떤 문제에 적합한지, 기술적 차이와 상호 보완성, 연결 시 새로 검증해야 할 문제를 분석하세요.
- '상호 보완적이다'로 끝내지 말고 **왜** 연결할 가치가 있는지 설명하세요.
- 연구 간 융합은 기존에 검증된 성과가 아닌 연계 가능성임을 밝히세요.

### 종합 결론 및 분석 한계
- **이 부분을 1~3개의 짧은 일반론 문장으로 끝내지 마세요.** 근거가 충분하면 아래 네 관점을 각각 독립된 Markdown 문단으로 상세히 작성하세요.
- 첫째, 연구 성과를 종합해 확인되는 공통 기술 과제와 연구 분야 차원의 의미를 3~4문장으로 해석하세요.
- 둘째, 예측·제어·저장·경제성 등 연구군 간 연결에서 도출되는 차별적인 연구기획 기회를 3~4문장으로 설명하세요. 관련 기술이 실제 입력 자료에 있을 때만 언급하세요.
- 셋째, 연구 간 실험 환경·평가 지표·적용 대상의 차이, 자료의 대표성 등 실제 확인되는 한계를 3~4문장으로 구분하세요. 검증되지 않은 한계는 '추가 확인 필요'라고 표현하세요.
- 넷째, 위 근거를 종합한 최종 판단과 다음 단계에서 우선 확인할 연구 질문을 3~4문장으로 정리하세요.
- 앞 절의 수치와 논문 내용을 그대로 반복하지 말고 **종합적 해석과 새로운 연결점**을 중심으로 쓰세요.
- 분석 대상의 범위를 넘어 전체 학계·산업의 대표적 흐름으로 일반화하지 마세요.

[overall_analysis.trend: 동향과 발전 가능성]
다음 두 Markdown 제목을 정확히 사용하세요.

### 연구동향 및 변화
- 단순 연구주제 목록이 아니라 관찰된 연구 접근의 공통점, 기술적 연결, 해결하려는 문제를 2~4개 단락으로 분석하세요.
- 실제 연도별 비교 자료가 없으면 시계열 변화를 추정하지 말고 수집 자료에서 확인되는 **기술적 방향성**만 분석하세요.
- '연도별 자료가 부족하다'는 한계 설명은 한 번만 간결하게 언급하세요.

### 신흥 연구 후보 및 기술 발전 방향
- 입력 자료의 기술을 근거로 3~4개 후보를 제안하세요(근거가 부족하면 더 적게).
- 각 후보마다 '출발 근거 → 융합·발전 방향 → 해결할 기술적 쟁점 → 기대되는 연구적 가치'를 3~4문장으로 설명하세요.
- 아직 검증되지 않은 미래 가능성임을 명시하세요.
- 구체적 실험 설계는 implications에서 다루므로 여기서는 기술 발전 전망에 집중하세요.

[key_topics: 핵심 연구주제 TOP5]
- 실제 입력 자료에서 확인된 연구군 3~5개를 반환하세요.
- topic은 **한국어 명사형 제목만** 사용하고 번호, 순위, 별표, Markdown 기호를 넣지 마세요.
- description은 연구군의 특징을 1~2문장으로 작성하세요.

[implications: 실행 가능한 연구 시사점]
- 서로 다른 후속 연구과제 3~4개를 제안하세요(근거가 부족하면 더 적게).
- title은 **한국어 명사형**으로 작성하고 번호·Markdown을 넣지 마세요.
- description은 4~6문장으로 '논문 근거 → 해결할 문제 → 제안 방법 → 검증 데이터·지표 → 연구기획상 활용 가치'를 설명하세요.
- 원문에 없는 실험 기간, 표본 규모, 수치 목표, 특정 시험망을 임의로 확정하지 마세요.
- 평가 지표는 제안할 수 있으나 실제 성과처럼 쓰지 마세요.
- trend의 기술 전망을 복제하지 말고, 연구 실행과 검증에 초점을 맞추세요.

[출력 형식 — 엄격히 준수]
- JSON 객체 하나만 반환하세요. 코드펜스, JSON 외 설명, 추가 키 금지.
- JSON 문자열의 줄바꿈은 백슬래시+n 형태로 이스케이프하세요. 실제 줄바꿈이 들어간 잘못된 JSON 문자열은 금지합니다.
- Markdown 제목(###)과 글머리표는 overall_analysis.summary 및 trend 문자열 내부에서만 사용하세요.
- 제목 뒤에는 줄바꿈, 문단 사이에는 빈 줄을 넣으세요.
- key_topics.topic 및 implications.title에는 번호를 붙이지 마세요. 화면에서 별도로 번호가 붙습니다.
- 모든 제목은 한국어로 작성하세요.

[입력 논문 자료 시작]
{document_text}
[입력 논문 자료 끝]

[JSON 출력 구조 — 값은 실제 분석으로 채우세요]
{{
  "overall_analysis": {{
    "summary": "### 핵심 연구 흐름 및 주요 성과\\n- 연구군별 상세 분석...\\n\\n### 연구 간 차별성 및 연계성\\n- 연구 간 비교...\\n\\n### 종합 결론 및 분석 한계\\n첫 번째 종합 해석 문단...\\n\\n두 번째 연결 가능성 문단...",
    "trend": "### 연구동향 및 변화\\n연구 접근법과 기술적 방향성...\\n\\n### 신흥 연구 후보 및 기술 발전 방향\\n- 연구 근거 기반 미래 제안..."
  }},
  "key_topics": [{{"topic": "한국어 연구주제", "description": "실제 확인된 방법과 성과"}}],
  "implications": [{{"title": "한국어 후속 연구과제", "description": "근거, 제안 방법, 검증 지표 및 활용 가치"}}]
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
