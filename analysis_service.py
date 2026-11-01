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
    """등록 키워드 우선 + 제목/초록 보완형 동시출현 네트워크.

    - 논문별 등록 키워드는 그대로 유지한다.
    - 제목에서 추출한 명사구 후보는 초록 또는 다른 논문에서도 확인되는 경우만 보완한다.
    - 초록은 등록 키워드/제목 후보의 출현 여부를 확인하는 근거로 사용한다.
    - 응답은 기존 프론트엔드와 호환되는 nodes/links 구조를 유지한다.
    """
    from collections import Counter, defaultdict

    article_ids = get_analysis_article_ids(req_idntf, excn_idntfs)
    if not article_ids:
        return {"nodes": [], "links": []}

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        placeholders = make_in_clause(article_ids)

        # 제목과 초록을 함께 조회하되, 키워드 테이블의 기존 데이터를 우선 사용한다.
        cursor.execute(f"""
            SELECT ARTCL_IDNTF AS article_id, TTL AS title, ABST AS abstract
            FROM CLCT_ARTCL
            WHERE ARTCL_IDNTF IN ({placeholders})
        """, tuple(article_ids))
        articles = cursor.fetchall()

        cursor.execute(f"""
            SELECT ARTCL_IDNTF AS article_id, KWRD AS keyword
            FROM CLCT_ARTCL_KWRD
            WHERE ARTCL_IDNTF IN ({placeholders})
              AND KWRD IS NOT NULL AND TRIM(KWRD) <> ''
            ORDER BY ARTCL_IDNTF, SNO
        """, tuple(article_ids))
        keyword_rows = cursor.fetchall()

        # 형태소 분석기를 추가 설치하지 않는 안전한 후보 추출.
        # 전문용어 전체를 완벽히 인식하는 방식은 아니므로 후속 검증이 필요하다.
        stopwords = {
            "연구", "분석", "고찰", "검토", "특성", "특징", "관한", "대한",
            "중심", "중심으로", "통한", "활용", "기반", "비교", "사례",
            "방법", "결과", "영향", "관계", "현황", "방안", "문제", "의미",
            "가능성", "시사점", "논문", "대상", "측면", "과정", "구조",
            "대하여", "있다", "있으며", "위한", "그리고", "또한", "이러한",
            "the", "and", "for", "with", "from", "using", "study",
            "analysis", "based", "research", "effect", "effects", "case",
        }
        suffixes = ("에서는", "으로는", "으로", "에서", "에게", "에는", "과의",
                    "와의", "들과", "들의", "들을", "으로서", "으로써", "에", "은", "는", "이", "가", "을", "를", "과", "와", "의", "도")

        def tokens(text):
            words = re.findall(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9-]{2,}", str(text or ""))
            output = []
            for word in words:
                word = word.lower() if re.search(r"[A-Za-z]", word) else word
                if re.search(r"[가-힣]", word):
                    for suffix in suffixes:
                        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                            word = word[:-len(suffix)]
                            break
                if len(word) >= 2 and word not in stopwords:
                    output.append(word)
            return output

        def valid_term(term):
            if not term or term in {".", ",", "-", "--"}:
                return False
            words = tokens(term)
            return bool(words) and any(w not in stopwords for w in words)

        # 논문별 등록 키워드
        registered = defaultdict(set)
        display_names = {}
        registered_terms = set()
        for row in keyword_rows:
            raw = str(row["keyword"] or "").strip()
            if not valid_term(raw):
                continue
            key = normalize_keyword(raw)
            if not key:
                continue
            registered[row["article_id"]].add(key)
            registered_terms.add(key)
            display_names.setdefault(key, raw)

        # 제목에서 등장하는 후보어를 추출한다. 제목 전체를 임의로 분절해
        # 수많은 조합을 만드는 대신 단일 내용어와 인접 2어절만 사용한다.
        title_candidates = defaultdict(set)
        title_document_counts = Counter()
        text_by_article = {}
        for article in articles:
            aid = article["article_id"]
            title = str(article.get("title") or "")
            abstract = str(article.get("abstract") or "")
            text_by_article[aid] = (title, abstract)
            terms = tokens(title)
            candidate_strings = set(terms)
            candidate_strings.update(
                " ".join(terms[i:i + 2])
                for i in range(len(terms) - 1)
            )
            for raw in candidate_strings:
                if not valid_term(raw):
                    continue
                key = normalize_keyword(raw)
                title_candidates[aid].add(key)
                display_names.setdefault(key, raw)
            title_document_counts.update(title_candidates[aid])

        # 등록 키워드가 있으면 기본으로 사용하고, 제목 후보는
        # (a) 다른 논문 제목에도 등장하거나 (b) 같은 논문의 초록에
        # 등장할 때만 추가한다. 논문당 최대 3개로 제한한다.
        article_keywords = defaultdict(set)
        origin_counts = Counter()
        for article in articles:
            aid = article["article_id"]
            title, abstract = text_by_article[aid]
            existing = set(registered[aid])
            article_keywords[aid].update(existing)
            origin_counts.update(existing)

            abstract_norm = normalize_keyword(abstract) if abstract else ""
            supplemental = []
            for key in title_candidates[aid]:
                if key in existing or len(key) < 3:
                    continue
                in_abstract = bool(abstract_norm and key in abstract_norm)
                in_other_titles = title_document_counts[key] >= 2
                if not (in_abstract or in_other_titles):
                    continue
                supplemental.append((in_other_titles, in_abstract,
                                     title_document_counts[key], len(key), key))
            supplemental.sort(reverse=True)
            for _, _, _, _, key in supplemental[:3]:
                article_keywords[aid].add(key)

        # 초록에 등록된 주요 키워드가 실제로 등장하면 관계 분석에
        # 활용하되, 그 논문의 등록 키워드가 아닌 것을 무제한 추가하지 않는다.
        counts = Counter(
            kw for keywords in article_keywords.values() for kw in keywords
        )
        if not counts:
            return {"nodes": [], "links": []}

        # 저자 키워드의 우선순위를 유지하면서 반복 출현을 중시한다.
        ranked = sorted(counts, key=lambda kw: (
            -counts[kw], -origin_counts[kw], kw
        ))
        max_nodes = 40
        repeated = [kw for kw in ranked if counts[kw] >= 2]
        candidates = repeated[:max_nodes]
        if len(candidates) < min(15, len(ranked)):
            for kw in ranked:
                if kw not in candidates:
                    candidates.append(kw)
                if len(candidates) >= min(max_nodes, len(ranked)):
                    break
        selected = set(candidates)

        pair_counts = Counter()
        for keywords in article_keywords.values():
            present = sorted(keywords & selected)
            pair_counts.update(combinations(present, 2))

        def make_link(pair, cooccurrence):
            source, target = pair
            union = counts[source] + counts[target] - cooccurrence
            return {
                "source": source,
                "target": target,
                "cooccurrence": cooccurrence,
                "jaccard": round(cooccurrence / union, 4) if union else 0.0,
            }

        primary, supplemental = [], []
        for pair, cooccurrence in pair_counts.items():
            link = make_link(pair, cooccurrence)
            if (cooccurrence >= min_cooccurrence and
                    link["jaccard"] >= min_jaccard):
                primary.append(link)
            elif cooccurrence >= 1:
                supplemental.append(link)

        def priority(link):
            return (-link["cooccurrence"], -link["jaccard"],
                    link["source"], link["target"])

        primary.sort(key=priority)
        supplemental.sort(key=priority)
        max_links = max(0, int(max_links))
        chosen = primary[:max_links]
        # 연결이 적을 때는 동시출현 1회 관계도 구분 가능한 범위에서 보완.
        target_links = min(max_links, 35)
        if len(chosen) < target_links:
            used = {(x["source"], x["target"]) for x in chosen}
            for link in supplemental:
                pair = (link["source"], link["target"])
                if pair not in used:
                    chosen.append(link)
                    used.add(pair)
                if len(chosen) >= target_links:
                    break
        chosen = sorted(chosen, key=priority)[:max_links]

        connected = {kw for link in chosen
                     for kw in (link["source"], link["target"])}
        # 연결선이 없는 핵심 키워드도 화면에 일부 유지한다.
        standalone = set(candidates[:min(10, len(candidates))])
        shown = connected | standalone
        nodes = [{
            "id": kw,
            "label": display_names.get(kw, kw),
            "count": counts[kw],
        } for kw in candidates if kw in shown]
        nodes.sort(key=lambda x: (-x["count"], x["id"]))

        print(f"키워드 네트워크: 논문 {len(articles)}건, "
              f"등록 키워드 {len(registered_terms)}종, "
              f"노드 {len(nodes)}개, 연결 {len(chosen)}개")
        return {"nodes": nodes, "links": chosen}

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
