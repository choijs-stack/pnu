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
    min_cooccurrence=2,
    min_jaccard=0.05,
    max_links=100
):
    """
    논문별 저자 키워드 및 제목/초록의 주요 용어를 활용한
    키워드 동시 출현 네트워크 분석.

    - 검색어 관련성 필터 적용하지 않음
    - 기존 수집 논문 전체 활용
    - 저자 키워드 우선
    - 한국어 명사/복합명사 보완
    - 실제 동시 출현 관계 기반 연결
    - 연결된 핵심 키워드 중심 노드 구성
    - 기존 nodes/links 반환 구조 유지
    """

    import re
    import math
    from collections import Counter, defaultdict
    from itertools import combinations

    try:
        from kiwipiepy import Kiwi
    except ImportError as exc:
        raise RuntimeError(
            "키워드 네트워크 분석에 kiwipiepy가 필요합니다. "
            "pip install kiwipiepy 를 실행하세요."
        ) from exc

    # =====================================================
    # 1. 분석 대상 논문 조회
    # =====================================================

    article_ids = get_analysis_article_ids(
        req_idntf,
        excn_idntfs
    )

    if not article_ids:
        return {"nodes": [], "links": []}

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        placeholders = make_in_clause(article_ids)

        cursor.execute(
            f"""
            SELECT
                a.ARTCL_IDNTF AS article_id,
                a.TTL AS title,
                a.ABST AS abstract
            FROM CLCT_ARTCL a
            WHERE a.ARTCL_IDNTF IN ({placeholders})
            """,
            tuple(article_ids)
        )

        articles = cursor.fetchall()

        cursor.execute(
            f"""
            SELECT
                k.ARTCL_IDNTF AS article_id,
                k.KWRD AS keyword
            FROM CLCT_ARTCL_KWRD k
            WHERE k.ARTCL_IDNTF IN ({placeholders})
              AND k.KWRD IS NOT NULL
              AND TRIM(k.KWRD) <> ''
            ORDER BY k.ARTCL_IDNTF, k.SNO
            """,
            tuple(article_ids)
        )

        keyword_rows = cursor.fetchall()

    finally:
        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()

    # =====================================================
    # 2. 키워드 정제
    # =====================================================

    kiwi = Kiwi()

    stopwords = {
        "연구", "분석", "결과", "방법", "목적",
        "대상", "논문", "본고", "고찰", "검토",
        "중심", "활용", "관련", "통한", "기반",
        "내용", "특성", "영향", "변화", "사례",
        "비교", "조사", "제시", "확인", "필요",
        "의미", "문제", "자료", "관점", "측면",
        "과정", "분야", "연구자", "저자",
        "주제", "구조", "방식", "유형",
        "study", "research", "analysis",
        "result", "results", "method", "methods",
        "paper", "approach", "based", "using",
        "effect", "effects", "data",
        "conclusion", "introduction", "purpose"
    }

    english_stop = {
        "the", "and", "of", "for", "with", "from",
        "this", "that", "these", "those",
        "were", "was", "are", "is", "be",
        "been", "being", "have", "has", "had",
        "into", "between", "among", "their",
        "its", "our", "can", "may", "using",
        "used", "also", "than", "such", "not",
        "but", "which", "who", "when", "where",
        "what", "how", "more", "less", "each",
        "both", "other", "an", "a", "to", "in",
        "on", "at", "by", "as", "or", "if",
        "study", "research", "results",
        "method", "methods", "analysis"
    }

    def normalize(term):
        term = re.sub(
            r"\s+",
            " ",
            str(term or "").strip()
        )

        if re.search(r"[가-힣]", term):
            return re.sub(r"\s+", "", term)

        return term.lower()

    def valid(term):
        term = str(term or "").strip().lower()

        if not (2 <= len(term) <= 45):
            return False

        if term in stopwords or term in english_stop:
            return False

        if not re.search(r"[가-힣a-z]", term):
            return False

        # 영어 불용어가 포함된 구문 제거
        if re.search(r"[a-z]", term):
            words = re.findall(r"[a-z]+", term)

            if any(
                word in english_stop or word in stopwords
                for word in words
            ):
                return False

        return True

    # =====================================================
    # 3. 제목/초록에서 한국어 명사 및 복합명사 추출
    # =====================================================

    def extract_terms(text):
        text = str(text or "")[:12000]

        result = set()

        if not text.strip():
            return result

        tokens = kiwi.tokenize(text)
        run = []

        def flush_run():
            if not run:
                return

            # 단일 명사
            for token in run:
                term = normalize(token)

                if valid(term):
                    result.add(term)

            # 2~3개 명사로 구성된 복합명사
            for size in (2, 3):
                for idx in range(len(run) - size + 1):
                    term = normalize(
                        "".join(run[idx:idx + size])
                    )

                    if valid(term):
                        result.add(term)

        previous_end = None

        for token in tokens:
            tag = token.tag
            word = token.form

            if tag.startswith("NN"):
                if (
                    previous_end is not None
                    and token.start > previous_end + 1
                ):
                    flush_run()
                    run = []

                run.append(word)
                previous_end = token.start + len(word)

            else:
                flush_run()
                run = []
                previous_end = None

        flush_run()

        # 영문 제목/초록의 일반 단어를
        # 무차별적으로 추가하지 않음.
        # 영문 저자 키워드는 별도로 유지.

        return result

    # =====================================================
    # 4. 저자 키워드 정리
    # =====================================================

    author = defaultdict(set)
    display = {}

    for row in keyword_rows:
        raw = str(row["keyword"] or "").strip()
        key = normalize(raw)

        if not valid(key):
            continue

        author[row["article_id"]].add(key)
        display.setdefault(key, raw)

    # =====================================================
    # 5. 제목/초록의 용어 출현 빈도 계산
    # =====================================================

    extracted = {}
    df = Counter()

    for row in articles:
        aid = row["article_id"]

        title_terms = extract_terms(row["title"])
        abstract_terms = extract_terms(row["abstract"])

        extracted[aid] = (
            title_terms,
            abstract_terms
        )

        df.update(title_terms | abstract_terms)

    total_docs = max(1, len(articles))

    # =====================================================
    # 6. 논문별 대표 키워드 구성
    # =====================================================

    article_terms = {}

    for row in articles:
        aid = row["article_id"]

        base = set(author.get(aid, set()))

        title_terms, abstract_terms = extracted[aid]

        candidates = (
            title_terms | abstract_terms
        ) - base

        scored = []

        for term in candidates:
            # 1개 논문에서만 나타나는 일반명사 제한
            # 제목에 등장한 용어는 예외 허용
            if df[term] < 2 and term not in title_terms:
                continue

            # 대부분의 논문에서 나타나는 일반 용어 제외
            if (
                total_docs >= 10
                and df[term] / total_docs > 0.65
            ):
                continue

            score = (
                2.0 if term in title_terms else 0.0
            )

            score += (
                math.log(
                    (total_docs + 1) / (df[term] + 1)
                ) + 1
            )

            # 복합명사 약한 가중치
            if len(term) >= 4:
                score += 0.25

            scored.append((score, term))

        scored.sort(
            key=lambda x: (-x[0], x[1])
        )

        additions = [
            term for _, term in scored[:4]
        ]

        article_terms[aid] = (
            base | set(additions)
        )

        for term in additions:
            display.setdefault(term, term)

    # =====================================================
    # 7. 키워드별 논문 출현 빈도
    # =====================================================

    counts = Counter(
        term
        for terms in article_terms.values()
        for term in terms
    )

    if not counts:
        return {"nodes": [], "links": []}

    author_counts = Counter(
        term
        for terms in author.values()
        for term in terms
    )

    ranked = sorted(
        counts,
        key=lambda t: (
            -(counts[t] + 0.5 * author_counts[t]),
            -counts[t],
            t
        )
    )

    # =====================================================
    # 8. 후보 키워드 간 동시 출현 관계 계산
    # =====================================================

    candidate_order = ranked[:100]
    candidate_set = set(candidate_order)

    pairs = Counter()

    for terms in article_terms.values():
        selected_terms = sorted(
            terms & candidate_set
        )

        pairs.update(
            combinations(selected_terms, 2)
        )

    links = []

    for (source, target), co in pairs.items():
        union = (
            counts[source]
            + counts[target]
            - co
        )

        jac = (
            co / union if union else 0.0
        )

        if (
            co < min_cooccurrence
            or jac < min_jaccard
        ):
            continue

        links.append({
            "source": source,
            "target": target,
            "cooccurrence": co,
            "jaccard": round(jac, 4)
        })

    links.sort(
        key=lambda x: (
            -x["cooccurrence"],
            -x["jaccard"],
            x["source"],
            x["target"]
        )
    )

    # =====================================================
    # 9. 연결 강도 중심으로 핵심 노드 선정
    # =====================================================

    strength = Counter()

    for link in links:
        strength[link["source"]] += (
            link["cooccurrence"]
        )

        strength[link["target"]] += (
            link["cooccurrence"]
        )

    selected_order = sorted(
        strength,
        key=lambda t: (
            -strength[t],
            -counts[t],
            t
        )
    )[:32]

    selected = set(selected_order)

    chosen = [
        link
        for link in links
        if (
            link["source"] in selected
            and link["target"] in selected
        )
    ][:max(0, int(max_links))]

    # 실제 연결선이 있는 노드만 유지
    connected = {
        term
        for link in chosen
        for term in (
            link["source"],
            link["target"]
        )
    }

    selected_order = [
        term
        for term in selected_order
        if term in connected
    ]

    # =====================================================
    # 10. 연결 관계 구성
    # =====================================================

    adjacency = defaultdict(dict)

    for link in chosen:
        a = link["source"]
        b = link["target"]
        w = link["cooccurrence"]

        adjacency[a][b] = w
        adjacency[b][a] = w

    # =====================================================
    # 11. 군집 분석: 가중 라벨 전파
    # =====================================================

    labels = {
        term: term
        for term in selected_order
    }

    for _ in range(15):
        changed = False
        next_labels = dict(labels)

        for term in selected_order:
            if not adjacency[term]:
                continue

            weights = Counter()

            for neighbor, weight in adjacency[term].items():
                weights[labels[neighbor]] += weight

            best = sorted(
                weights,
                key=lambda label: (
                    -weights[label],
                    label
                )
            )[0]

            if best != labels[term]:
                next_labels[term] = best
                changed = True

        labels = next_labels

        if not changed:
            break

    community_ids = {
        label: idx + 1
        for idx, label in enumerate(
            sorted(set(labels.values()))
        )
    }

    # =====================================================
    # 12. 프론트엔드 응답 데이터 구성
    # =====================================================

    nodes = []

    for term in selected_order:
        nodes.append({
            "id": term,
            "label": display.get(term, term),
            "count": counts[term],
            "degree": len(adjacency[term]),
            "weighted_degree": sum(
                adjacency[term].values()
            ),
            "community": community_ids[labels[term]]
        })

    print(
        f"키워드 네트워크 생성 완료: "
        f"논문 {len(articles)}건, "
        f"노드 {len(nodes)}개, "
        f"연결선 {len(chosen)}개"
    )

    return {
        "nodes": nodes,
        "links": chosen
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
