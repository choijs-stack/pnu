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
    통합 연구주제 키워드 네트워크

    - 등록 키워드 + 제목·초록 핵심 명사
    - 논문별 핵심어 통합
    - 동시출현 및 Jaccard 분석
    - 연결중심성 및 군집 분석
    - 기존 nodes / links 구조 유지
    """
    import re
    import math
    from collections import Counter, defaultdict
    from itertools import combinations
    from kiwipiepy import Kiwi

    article_ids = get_analysis_article_ids(
        req_idntf, excn_idntfs
    )

    if not article_ids:
        return {"nodes": [], "links": []}

    # 일반적인 학술 표현 제거
    stopwords = {
        "연구", "분석", "결과", "방법", "목적",
        "논문", "고찰", "검토", "대상", "내용",
        "중심", "관련", "활용", "기반", "특성",
        "영향", "변화", "과정", "문제", "차이",
        "의미", "측면", "관점", "필요", "제시",
        "확인", "조사", "수행", "사용", "적용",
        "비교", "평가", "자료", "정보", "데이터",
        "경우", "부분", "수준", "정도", "가능",
        "이용", "기존", "전체", "다양", "형태",
        "방식", "구조", "시스템", "기술",
        "this", "that", "with", "from",
        "study", "research", "result", "results",
        "method", "methods", "analysis", "data",
        "using", "based", "paper", "approach"
    }

    kiwi = Kiwi()
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        placeholders = make_in_clause(article_ids)

        # 1. 논문 제목·초록 조회
        sql_articles = f"""
            SELECT
                ARTCL_IDNTF AS article_id,
                TTL AS title,
                ABST AS abstract
            FROM CLCT_ARTCL
            WHERE ARTCL_IDNTF IN ({placeholders})
        """

        cursor.execute(
            sql_articles, tuple(article_ids)
        )
        articles = cursor.fetchall()

        # 2. 기존 등록 키워드 조회
        sql_keywords = f"""
            SELECT
                ARTCL_IDNTF AS article_id,
                KWRD AS keyword
            FROM CLCT_ARTCL_KWRD
            WHERE ARTCL_IDNTF IN ({placeholders})
              AND KWRD IS NOT NULL
              AND TRIM(KWRD) <> ''
        """

        cursor.execute(
            sql_keywords, tuple(article_ids)
        )
        keyword_rows = cursor.fetchall()

        article_keywords = defaultdict(set)
        display_names = {}

        # 3. 등록 키워드 정규화
        for row in keyword_rows:
            raw = str(row["keyword"] or "").strip()
            if not raw:
                continue

            normalized = normalize_keyword(raw)

            if (
                not normalized
                or normalized in stopwords
                or len(normalized) < 2
            ):
                continue

            article_keywords[row["article_id"]].add(
                normalized
            )
            display_names.setdefault(normalized, raw)

        # 4. 제목·초록 명사 및 복합명사 추출
        def extract_terms(text):
            if not text:
                return []

            text = str(text)
            tokens = kiwi.tokenize(text)

            terms = []
            noun_buffer = []

            def flush_nouns():
                if not noun_buffer:
                    return

                # 개별 명사
                for word in noun_buffer:
                    terms.append(word)

                # 연속 명사로 구성된 복합명사
                if len(noun_buffer) >= 2:
                    for size in (2, 3):
                        for i in range(
                            len(noun_buffer) - size + 1
                        ):
                            phrase = "".join(
                                noun_buffer[i:i + size]
                            )
                            terms.append(phrase)

                noun_buffer.clear()

            for token in tokens:
                if token.tag in {"NNG", "NNP", "SL"}:
                    word = token.form.strip()

                    if re.fullmatch(
                        r"[가-힣A-Za-z0-9]+", word
                    ):
                        noun_buffer.append(word)
                    else:
                        flush_nouns()
                else:
                    flush_nouns()

            flush_nouns()

            cleaned = []

            for term in terms:
                normalized = normalize_keyword(term)

                if len(normalized) < 2:
                    continue

                if normalized.lower() in stopwords:
                    continue

                if normalized.isdigit():
                    continue

                cleaned.append(normalized)

            return cleaned

        # 5. 전체 문서 기준 핵심어 중요도 계산
        extracted_by_article = {}
        document_frequency = Counter()

        for article in articles:
            article_id = article["article_id"]

            title = article.get("title") or ""
            abstract = article.get("abstract") or ""

            title_terms = extract_terms(title)
            abstract_terms = extract_terms(abstract)

            extracted_by_article[article_id] = {
                "title": title_terms,
                "abstract": abstract_terms
            }

            document_frequency.update(
                set(title_terms + abstract_terms)
            )

        total_docs = max(len(articles), 1)

        # 6. 논문별 핵심 명사 선정 및 등록 키워드 보완
        for article_id, term_data in extracted_by_article.items():

            title_counts = Counter(term_data["title"])
            abstract_counts = Counter(term_data["abstract"])

            all_counts = title_counts + abstract_counts
            scores = {}

            for term, frequency in all_counts.items():

                df = document_frequency[term]

                # TF-IDF 기반 중요도
                idf = math.log(
                    (total_docs + 1) / (df + 1)
                ) + 1

                score = frequency * idf

                # 제목에 등장한 용어 가중
                if term in title_counts:
                    score += title_counts[term] * idf

                # 복합명사에 소폭 가중
                if len(term) >= 4:
                    score *= 1.1

                scores[term] = score

            ranked_terms = sorted(
                scores,
                key=lambda term: (
                    -scores[term],
                    -len(term),
                    term
                )
            )

            added = 0

            for term in ranked_terms:
                if term in article_keywords[article_id]:
                    continue

                article_keywords[article_id].add(term)
                display_names.setdefault(term, term)

                added += 1

                # 논문당 추출 핵심어 최대 4개 보완
                if added >= 4:
                    break

        # 7. 키워드별 등장 논문 수
        counts = Counter(
            kw
            for keywords in article_keywords.values()
            for kw in keywords
        )

        if not counts:
            return {"nodes": [], "links": []}

        # 8. 주요 키워드 최대 40개 선정
        ranked = sorted(
            counts,
            key=lambda kw: (-counts[kw], kw)
        )

        repeated = [
            kw for kw in ranked
            if counts[kw] >= 2
        ]

        if len(repeated) >= 10:
            candidates = repeated[:40]
        else:
            candidates = ranked[:40]

        selected = set(candidates)

        # 9. 논문별 키워드 동시출현 계산
        pair_counts = Counter()

        for keywords in article_keywords.values():
            present = sorted(keywords & selected)

            pair_counts.update(
                combinations(present, 2)
            )

        # 10. 연결 관계 계산
        primary = []
        supplemental = []

        for (source, target), cooccurrence in pair_counts.items():

            union = (
                counts[source]
                + counts[target]
                - cooccurrence
            )

            jaccard = (
                cooccurrence / union
                if union > 0 else 0
            )

            link = {
                "source": source,
                "target": target,
                "cooccurrence": cooccurrence,
                "jaccard": round(jaccard, 4)
            }

            if (
                cooccurrence >= min_cooccurrence
                and jaccard >= min_jaccard
            ):
                primary.append(link)
            else:
                supplemental.append(link)

        def priority(link):
            return (
                -link["cooccurrence"],
                -link["jaccard"],
                link["source"],
                link["target"]
            )

        primary.sort(key=priority)
        supplemental.sort(key=priority)

        max_links = max(0, int(max_links))
        chosen = primary[:max_links]

        # 연결 부족 시 실제 동시출현 관계 보완
        target_links = min(max_links, 30)

        if len(chosen) < target_links:
            used = {
                (link["source"], link["target"])
                for link in chosen
            }

            for link in supplemental:
                key = (
                    link["source"],
                    link["target"]
                )

                if key in used:
                    continue

                chosen.append(link)
                used.add(key)

                if len(chosen) >= target_links:
                    break

        chosen = sorted(
            chosen, key=priority
        )[:max_links]

        # 11. 인접 관계 구성
        adjacency = defaultdict(dict)

        for link in chosen:
            source = link["source"]
            target = link["target"]
            weight = link["cooccurrence"]

            adjacency[source][target] = weight
            adjacency[target][source] = weight

        connected = set(adjacency.keys())

        # 연결된 키워드 + 주요 독립 키워드
        node_ids = set(connected)

        for kw in candidates:
            if len(node_ids) >= 40:
                break
            node_ids.add(kw)

        # 12. 가중 라벨 전파 군집 분석
        labels = {
            kw: kw for kw in sorted(node_ids)
        }

        for _ in range(20):
            changed = False

            for kw in sorted(node_ids):
                neighbors = adjacency.get(kw, {})

                if not neighbors:
                    continue

                label_weights = defaultdict(float)

                for neighbor, weight in neighbors.items():
                    label_weights[
                        labels[neighbor]
                    ] += weight

                best_label = sorted(
                    label_weights,
                    key=lambda label: (
                        -label_weights[label],
                        label
                    )
                )[0]

                if labels[kw] != best_label:
                    labels[kw] = best_label
                    changed = True

            if not changed:
                break

        unique_labels = sorted(set(labels.values()))

        community_map = {
            label: i + 1
            for i, label in enumerate(unique_labels)
        }

        # 13. 노드별 중심성 및 군집 정보
        nodes = []

        for kw in node_ids:
            neighbors = adjacency.get(kw, {})

            nodes.append({
                "id": kw,
                "label": display_names[kw],
                "count": counts[kw],
                "degree": len(neighbors),
                "weighted_degree": sum(
                    neighbors.values()
                ),
                "community": community_map[labels[kw]]
            })

        nodes.sort(
            key=lambda x: (
                -x["count"],
                -x["weighted_degree"],
                x["id"]
            )
        )

        return {
            "nodes": nodes,
            "links": chosen
        }

    finally:
        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


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
