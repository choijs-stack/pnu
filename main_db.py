import json

from analysis_service import (
    get_site_collection_status,
    get_subject_distribution,
    get_journal_distribution,
    get_wordcloud_data,
    get_keyword_network,
    get_collected_articles
)
from llm_service import get_llm_analysis


# =========================================================
# 테스트할 수집 실행 ID
# =========================================================
excn_idntf = 8


# =========================================================
# 1. 사이트별 수집 현황
# =========================================================
print("사이트별 수집 현황 분석 시작")

site_result = get_site_collection_status(
    excn_idntf
)

print("사이트별 수집 현황 분석 완료")


# =========================================================
# 2. 주요 연구분야 TOP 10
# =========================================================
print("주요 연구분야 분석 시작")

subject_result = get_subject_distribution(
    excn_idntf=excn_idntf,
    limit=10
)

print("주요 연구분야 분석 완료")


# =========================================================
# 3. 주요 저널 TOP 10
# =========================================================
print("주요 저널 분석 시작")

journal_result = get_journal_distribution(
    excn_idntf=excn_idntf,
    limit=10
)

print("주요 저널 분석 완료")

# =========================================================
# 5. 워드클라우드
# =========================================================
print("워드클라우드 분석 시작")

wordcloud_result = get_wordcloud_data(
    excn_idntf=excn_idntf,
    limit=50
)

print("워드클라우드 분석 완료")


# =========================================================
# 6. 키워드 네트워크
# =========================================================
print("키워드 네트워크 분석 시작")

network_result = get_keyword_network(
    excn_idntf=excn_idntf,
    min_cooccurrence=2,
    min_jaccard=0.05,
    max_links=50
)

print("키워드 네트워크 분석 완료")


# =========================================================
# 7. LLM 종합 분석
# =========================================================
print("LLM 종합 분석 시작")

llm_result = get_llm_analysis(
    excn_idntf=excn_idntf
)

print("LLM 종합 분석 완료")


# =========================================================
# 8. 수집 데이터 목록
# =========================================================
print("수집 데이터 목록 조회 시작")

article_result = get_collected_articles(
    excn_idntf=excn_idntf
)

print(
    f"수집 데이터 목록 조회 완료: {len(article_result)}건"
)


# =========================================================
## =========================================================
# 최종 결과
# =========================================================
result = {

    "excn_idntf": excn_idntf,

    # 사이트별 수집 현황
    "site_collection_status": site_result,

    # 주요 연구분야 TOP 10
    "subject_distribution": subject_result,

    # 주요 저널 TOP 10
    "journal_distribution": journal_result,

    # 워드클라우드
    "wordcloud": wordcloud_result,

    # 키워드 네트워크
    "keyword_network": {
        "nodes": network_result["nodes"],
        "links": network_result["links"]
    },

    # LLM 종합 분석
    "llm_analysis": llm_result

    # 수집 데이터 목록
    #"articles": article_result
}


# =========================================================
# JSON 출력
# =========================================================
print("\n")
print("=" * 60)
print("최종 분석 결과")
print("=" * 60)

print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        default=str
    )
)