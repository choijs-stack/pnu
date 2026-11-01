import re

from itertools import combinations

from db import get_db_connection


# =========================================================
# ★ 수정 필요: 사이트별 분석 대상 건수
# =========================================================
#
# 반드시 DB의 SRC_NM 값과 동일하게 작성
#
# 예:
# "KCI": 300
# "PubMed": 100
#
# 아래 값은 예시이므로 실제 사이트명/건수로 수정
# =========================================================

# SITE_ANALYSIS_LIMITS = {
#     "ARXIV": 244,
#     "PUBMED": 213,
#     "NEP": 6,
# }


# =========================================================
# SQL IN 조건 생성
# =========================================================

def make_in_clause(values):
    """
    SQL IN 조건에 사용할 placeholder 문자열 생성

    예:
        [87, 88, 89]
        -> "%s, %s, %s"
    """

    if not values:
        raise ValueError(
            "values가 비어 있습니다."
        )

    return ", ".join(
        ["%s"] * len(values)
    )


# =========================================================
# 사이트별 분석 대상 논문 선정
# =========================================================

def get_analysis_article_ids(
    req_idntf,
    excn_idntfs
):
    """
    특정 수집 요청(REQ_IDNTF) 및
    지정된 수집 실행(EXCN_IDNTF)에 해당하는
    전체 수집 데이터의 ARTCL_IDNTF를 반환한다.
    """

    conn = None
    cursor = None

    try:
        if not excn_idntfs:
            return []

        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        placeholders = make_in_clause(
            excn_idntfs
        )

        sql = f"""
            SELECT
                a.ARTCL_IDNTF
            FROM CLCT_ARTCL a
            INNER JOIN CLCT_EXCN e
                ON a.EXCN_IDNTF = e.EXCN_IDNTF
            WHERE e.REQ_IDNTF = %s
              AND e.EXCN_IDNTF IN ({placeholders})
            ORDER BY
                CASE
                    WHEN a.PBLCN_YM IS NULL
                         OR TRIM(a.PBLCN_YM) = ''
                    THEN 1
                    ELSE 0
                END ASC,
                a.PBLCN_YM DESC,
                a.ARTCL_IDNTF DESC
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

        article_ids = [
            row["ARTCL_IDNTF"]
            for row in rows
        ]

        print(
            f"전체 분석 대상 ID 선정 완료: "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_IDNTFS={excn_idntfs}, "
            f"{len(article_ids)}건"
        )

        return article_ids

    finally:
        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()

# =========================================================
# 사이트별 수집 현황
# =========================================================

def get_site_collection_status(
    req_idntf,
    excn_idntfs
):
    """
    사이트별 분석 대상 논문 건수 조회

    SITE_ANALYSIS_LIMITS가 적용된
    실제 분석 대상 기준으로 반환
    """

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        article_placeholders = make_in_clause(
            article_ids
        )

        sql = f"""
            SELECT
                TRIM(a.SRC_NM) AS site_name,
                COUNT(*) AS article_count
            FROM CLCT_ARTCL a
            WHERE a.ARTCL_IDNTF IN ({article_placeholders})
              AND a.SRC_NM IS NOT NULL
              AND TRIM(a.SRC_NM) <> ''
            GROUP BY TRIM(a.SRC_NM)
            ORDER BY article_count DESC
        """

        params = tuple(
            article_ids
        )

        cursor.execute(
            sql,
            params
        )

        return cursor.fetchall()

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


# =========================================================
# 주요 연구분야 TOP N
# =========================================================

def get_subject_distribution(
    req_idntf,
    excn_idntfs,
    limit=10
):
    """
    분석 대상 논문의 SUBJECT 기준
    주요 연구분야 TOP N
    """

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        article_placeholders = make_in_clause(
            article_ids
        )

        sql = f"""
            SELECT
                TRIM(a.SUBJECT) AS subject,
                COUNT(*) AS article_count
            FROM CLCT_ARTCL a
            WHERE a.ARTCL_IDNTF IN ({article_placeholders})
              AND a.SUBJECT IS NOT NULL
              AND TRIM(a.SUBJECT) <> ''
            GROUP BY TRIM(a.SUBJECT)
            ORDER BY
                article_count DESC,
                subject ASC
            LIMIT %s
        """

        params = (
            *article_ids,
            limit
        )

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        return [
            {
                "subject": row["subject"],
                "count": row["article_count"]
            }
            for row in rows
        ]

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


# =========================================================
# 주요 저널 TOP N
# =========================================================

def get_journal_distribution(
    req_idntf,
    excn_idntfs,
    limit=10
):
    """
    분석 대상 논문의 JRNL_NM 기준
    주요 저널 TOP N
    """

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        article_placeholders = make_in_clause(
            article_ids
        )

        sql = f"""
            SELECT
                TRIM(a.JRNL_NM) AS journal_name,
                COUNT(*) AS article_count
            FROM CLCT_ARTCL a
            WHERE a.ARTCL_IDNTF IN ({article_placeholders})
              AND a.JRNL_NM IS NOT NULL
              AND TRIM(a.JRNL_NM) <> ''
            GROUP BY TRIM(a.JRNL_NM)
            ORDER BY
                article_count DESC,
                journal_name ASC
            LIMIT %s
        """

        params = (
            *article_ids,
            limit
        )

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        return [
            {
                "journal_name": row["journal_name"],
                "count": row["article_count"]
            }
            for row in rows
        ]

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


# =========================================================
# 워드클라우드 키워드 정규화
# =========================================================

def normalize_keyword(keyword):
    """
    한국어가 포함된 키워드는 공백을 제거하여 비교하고,
    영어 키워드는 원래 공백을 유지한다.
    """

    keyword = keyword.strip()

    has_korean = bool(
        re.search(
            r'[가-힣]',
            keyword
        )
    )

    if has_korean:

        return re.sub(
            r'\s+',
            '',
            keyword
        )

    return keyword.lower()


# =========================================================
# 워드클라우드용 키워드 빈도
# =========================================================

def get_wordcloud_data(
    req_idntf,
    excn_idntfs,
    limit=50
):

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        article_placeholders = make_in_clause(
            article_ids
        )

        sql = f"""
            SELECT
                k.KWRD AS keyword
            FROM CLCT_ARTCL_KWRD k
            WHERE k.ARTCL_IDNTF IN ({article_placeholders})
              AND k.KWRD IS NOT NULL
              AND TRIM(k.KWRD) <> ''
        """

        params = tuple(
            article_ids
        )

        cursor.execute(
            sql,
            params
        )

        rows = cursor.fetchall()

        keyword_counts = {}

        display_names = {}

        for row in rows:

            keyword = (
                row["keyword"].strip()
            )

            # 의미 없는 값 제거
            if keyword in {
                ".",
                ",",
                "-",
                "--"
            }:
                continue

            normalized = normalize_keyword(
                keyword
            )

            if not normalized:
                continue

            keyword_counts[
                normalized
            ] = (
                keyword_counts.get(
                    normalized,
                    0
                )
                + 1
            )

            # 최초 등장한 원본 표현을
            # 화면 표시용으로 사용
            if normalized not in display_names:

                display_names[
                    normalized
                ] = keyword

        result = [
            {
                "keyword":
                    display_names[key],

                "count":
                    count
            }

            for key, count
            in keyword_counts.items()
        ]

        result.sort(
            key=lambda x: x["count"],
            reverse=True
        )

        return result[:limit]

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


# =========================================================
# 키워드 네트워크
# =========================================================

def get_keyword_network(
    req_idntf,
    excn_idntfs,
    min_cooccurrence=1,
    min_jaccard=0.0,
    max_links=100
):
    """
    논문에 등록된 키워드만 활용하는 동시 출현 네트워크.

    - 제목 및 초록에서 키워드를 추가 추출하지 않음
    - arXiv 분야 분류 코드 및 일반 불용어 제거
    - 논문별 키워드 동시 출현 관계 분석
    - 빈도 상위 최대 40개 키워드 활용
    - 연결 강도에 따른 최대 100개 연결선 표시
    - 실제 연결 관계를 기반으로 군집 구분
    - 기존 nodes / links 응답 구조 유지
    """
    import re
    from collections import Counter, defaultdict
    from itertools import combinations

    # =====================================================
    # 1. 분석 대상 논문 조회
    # =====================================================

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return {
            "nodes": [],
            "links": []
        }

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        placeholders = make_in_clause(article_ids)

        sql = f"""
            SELECT
                k.ARTCL_IDNTF AS article_id,
                k.KWRD AS keyword
            FROM CLCT_ARTCL_KWRD k
            WHERE k.ARTCL_IDNTF IN ({placeholders})
              AND k.KWRD IS NOT NULL
              AND TRIM(k.KWRD) <> ''
            ORDER BY
                k.ARTCL_IDNTF,
                k.SNO
        """

        cursor.execute(sql, tuple(article_ids))
        rows = cursor.fetchall()

    finally:
        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()

    # =====================================================
    # 2. 키워드 정제 기준
    # =====================================================

    arxiv_code = re.compile(
        r"^(?:"
        r"(?:cs|econ|eess|math|nlin|physics|q-bio|q-fin|stat)\.[a-z-]+"
        r"|(?:astro-ph|cond-mat|gr-qc|hep-ex|hep-lat|hep-ph|hep-th|"
        r"math-ph|nucl-ex|nucl-th|quant-ph)(?:\.[a-z-]+)?"
        r")$",
        re.I
    )

    stopwords = {
        "the", "and", "of", "for", "with", "from",
        "to", "in", "on", "at", "by", "a", "an",
        "is", "are", "or", "as", "using",
        "study", "research", "analysis",
        "result", "results", "method", "methods",
        "paper", "data", "introduction", "conclusion",
        "연구", "분석", "결과", "방법", "논문",
        "고찰", "검토", "본고", "목적", "대상",
        "내용", "관련", "중심", "통한", "기반"
    }

    def clean_keyword(raw):
        display = re.sub(
            r"\s+",
            " ",
            str(raw or "").strip()
        )

        if not display or len(display) > 80:
            return None, None

        if not re.search(r"[가-힣A-Za-z]", display):
            return None, None

        normalized = normalize_keyword(display)

        if len(normalized) < 2:
            return None, None

        if normalized.lower() in stopwords:
            return None, None

        if arxiv_code.fullmatch(display):
            return None, None

        if re.fullmatch(r"[A-Za-z ]+", display):
            words = display.lower().split()

            if len(words) > 1 and all(
                word in stopwords for word in words
            ):
                return None, None

        return normalized, display

    # =====================================================
    # 3. 논문별 등록 키워드 구성
    # =====================================================

    article_keywords = defaultdict(set)
    display_names = {}

    for row in rows:
        key, name = clean_keyword(row["keyword"])

        if key is None:
            continue

        article_id = row["article_id"]

        article_keywords[article_id].add(key)
        display_names.setdefault(key, name)

    # =====================================================
    # 4. 키워드별 출현 논문 수 계산
    # =====================================================

    counts = Counter(
        keyword
        for keywords in article_keywords.values()
        for keyword in keywords
    )

    if not counts:
        return {
            "nodes": [],
            "links": []
        }

    ranked = sorted(
        counts,
        key=lambda keyword: (
            -counts[keyword],
            keyword
        )
    )

    # 최대 40개 핵심 키워드 선정
    candidate_order = ranked[:40]
    candidate_set = set(candidate_order)

    # =====================================================
    # 5. 키워드 동시 출현 관계 계산
    # =====================================================

    pairs = Counter()

    for keywords in article_keywords.values():
        selected = sorted(
            keywords & candidate_set
        )

        pairs.update(
            combinations(selected, 2)
        )

    # =====================================================
    # 6. 연결 강도 및 Jaccard 계산
    # =====================================================

    links = []

    for (source, target), cooccurrence in pairs.items():

        union = (
            counts[source]
            + counts[target]
            - cooccurrence
        )

        jaccard = (
            cooccurrence / union
            if union else 0.0
        )

        if cooccurrence < min_cooccurrence:
            continue

        if jaccard < min_jaccard:
            continue

        links.append({
            "source": source,
            "target": target,
            "cooccurrence": cooccurrence,
            "jaccard": round(jaccard, 4)
        })

    links.sort(
        key=lambda link: (
            -link["cooccurrence"],
            -link["jaccard"],
            link["source"],
            link["target"]
        )
    )

    links = links[:max(0, int(max_links))]

    # =====================================================
    # 7. 네트워크 노드 선정
    # =====================================================

    connected = {
        keyword
        for link in links
        for keyword in (
            link["source"],
            link["target"]
        )
    }

    # 연결이 부족하면 상위 키워드를 일부 유지
    # 실제 연결이 없는 키워드에 가짜 연결선을 생성하지 않음
    if len(connected) < 8:
        connected.update(candidate_order[:8])

    selected_order = [
        keyword
        for keyword in candidate_order
        if keyword in connected
    ]

    # =====================================================
    # 8. 키워드 연결 관계 구성
    # =====================================================

    adjacency = defaultdict(dict)

    for link in links:
        source = link["source"]
        target = link["target"]
        weight = link["cooccurrence"]

        adjacency[source][target] = weight
        adjacency[target][source] = weight

    # =====================================================
    # 9. 연결 관계 기반 군집 분석
    # =====================================================

    labels = {
        keyword: keyword
        for keyword in selected_order
    }

    for _ in range(20):
        changed = False

        for keyword in selected_order:

            if not adjacency[keyword]:
                continue

            scores = Counter()

            for neighbor, weight in adjacency[keyword].items():
                scores[labels[neighbor]] += weight

            best = sorted(
                scores,
                key=lambda label: (
                    -scores[label],
                    label
                )
            )[0]

            if labels[keyword] != best:
                labels[keyword] = best
                changed = True

        if not changed:
            break

    communities = {
        label: index + 1
        for index, label in enumerate(
            sorted(set(labels.values()))
        )
    }

    # =====================================================
    # 10. 프론트엔드 노드 구성
    # =====================================================

    nodes = []

    for keyword in selected_order:

        nodes.append({
            "id": keyword,
            "label": display_names[keyword],
            "count": counts[keyword],
            "degree": len(adjacency[keyword]),
            "weighted_degree": sum(
                adjacency[keyword].values()
            ),
            "community": communities[labels[keyword]]
        })

    print(
        f"키워드 네트워크 생성 완료: "
        f"논문 {len(article_ids)}건, "
        f"등록 키워드 {len(counts)}종, "
        f"노드 {len(nodes)}개, "
        f"연결선 {len(links)}개"
    )

    return {
        "nodes": nodes,
        "links": links
    }
# =========================================================
# 수집 데이터 목록 조회
# =========================================================

def get_collected_articles(
    req_idntf,
    excn_idntfs
):

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return []

    conn = None
    cursor = None

    try:
        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        article_placeholders = make_in_clause(
            article_ids
        )

        # -----------------------------------------------------
        # 1. 분석 대상 수집 항목 조회
        # -----------------------------------------------------

        article_sql = f"""
            SELECT
                a.ARTCL_IDNTF,
                a.TTL,
                a.AUTHOR_NM,
                a.SRC_NM,
                a.JRNL_NM,
                a.PBLCN_YM,
                a.FWCI,
                a.SUBJECT,
                a.ABST
            FROM CLCT_ARTCL a
            WHERE a.ARTCL_IDNTF IN ({article_placeholders})
            ORDER BY
                CASE
                    WHEN a.PBLCN_YM IS NULL
                         OR TRIM(a.PBLCN_YM) = ''
                    THEN 1
                    ELSE 0
                END ASC,
                a.PBLCN_YM DESC,
                a.ARTCL_IDNTF DESC
        """

        article_params = tuple(
            article_ids
        )

        cursor.execute(
            article_sql,
            article_params
        )

        articles = (
            cursor.fetchall()
        )

        if not articles:
            return []

        # -----------------------------------------------------
        # 2. 해당 분석 대상의 키워드 전체 조회
        # -----------------------------------------------------

        keyword_sql = f"""
            SELECT
                k.ARTCL_IDNTF,
                k.KWRD,
                k.SNO
            FROM CLCT_ARTCL_KWRD k
            WHERE k.ARTCL_IDNTF IN ({article_placeholders})
            ORDER BY
                k.ARTCL_IDNTF,
                k.SNO
        """

        keyword_params = tuple(
            article_ids
        )

        cursor.execute(
            keyword_sql,
            keyword_params
        )

        keyword_rows = (
            cursor.fetchall()
        )

        # -----------------------------------------------------
        # 3. ARTCL_IDNTF별 키워드 묶기
        # -----------------------------------------------------

        keyword_map = {}

        for row in keyword_rows:

            article_id = (
                row["ARTCL_IDNTF"]
            )

            keyword = (
                row["KWRD"]
            )

            if article_id not in keyword_map:

                keyword_map[
                    article_id
                ] = []

            if keyword:

                keyword_map[
                    article_id
                ].append(
                    keyword
                )

        # -----------------------------------------------------
        # 4. 화면용 데이터 생성
        # -----------------------------------------------------

        result = []

        for no, row in enumerate(
            articles,
            start=1
        ):

            article_id = (
                row["ARTCL_IDNTF"]
            )

            result.append({

                "no":
                    no,

                "title":
                    row["TTL"],

                "author":
                    row["AUTHOR_NM"],

                "source":
                    row["SRC_NM"],

                "journal":
                    row["JRNL_NM"],

                "publication_ym":
                    row["PBLCN_YM"],

                "fwci":
                    row["FWCI"],

                "subject":
                    row["SUBJECT"],

                "keywords":
                    keyword_map.get(
                        article_id,
                        []
                    ),

                "abstract":
                    row["ABST"]
            })

        return result

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()
