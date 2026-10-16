from analysis_service import (
    get_site_collection_status,
    get_subject_distribution,
    get_journal_distribution,
    get_wordcloud_data,
    get_keyword_network
)

from llm_service import get_llm_analysis


# =========================================================
# 전체 분석 실행
# =========================================================
def run_analysis(
    req_idntf,
    excn_idntfs
):

    print(
        f"전체 분석 시작: "
        f"REQ_IDNTF={req_idntf}, "
        f"EXCN_IDNTFS={excn_idntfs}"
    )


    # ---------------------------------------------------------
    # 1. 사이트별 수집 현황
    # ---------------------------------------------------------
    print("사이트별 수집 현황 분석 시작")

    site_result = get_site_collection_status(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs
    )

    print("사이트별 수집 현황 분석 완료")


    # ---------------------------------------------------------
    # 2. 주요 연구분야 TOP 10
    # ---------------------------------------------------------
    print("주요 연구분야 분석 시작")

    subject_result = get_subject_distribution(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs,
        limit=10
    )

    print("주요 연구분야 분석 완료")


    # ---------------------------------------------------------
    # 3. 주요 저널 TOP 10
    # ---------------------------------------------------------
    print("주요 저널 분석 시작")

    journal_result = get_journal_distribution(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs,
        limit=10
    )

    print("주요 저널 분석 완료")


    # ---------------------------------------------------------
    # 4. 워드클라우드
    # ---------------------------------------------------------
    print("워드클라우드 분석 시작")

    wordcloud_result = get_wordcloud_data(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs,
        limit=50
    )

    print("워드클라우드 분석 완료")


    # ---------------------------------------------------------
    # 5. 키워드 네트워크
    # ---------------------------------------------------------
    print("키워드 네트워크 분석 시작")

    network_result = get_keyword_network(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs,
        min_cooccurrence=2,
        min_jaccard=0.05,
        max_links=50
    )

    print("키워드 네트워크 분석 완료")


    # ---------------------------------------------------------
    # 6. LLM 종합 분석
    # ---------------------------------------------------------
    print("LLM 종합 분석 시작")

    llm_result = get_llm_analysis(
        req_idntf=req_idntf,
        excn_idntfs=excn_idntfs
    )

    print("LLM 종합 분석 완료")


    # ---------------------------------------------------------
    # 최종 분석 결과
    # ---------------------------------------------------------
    result = {

        "req_idntf": req_idntf,

        "excn_idntfs": excn_idntfs,

        "site_collection_status": site_result,

        "subject_distribution": subject_result,

        "journal_distribution": journal_result,

        "wordcloud": wordcloud_result,

        "keyword_network": {
            "nodes": network_result["nodes"],
            "links": network_result["links"]
        },

        "llm_analysis": llm_result
    }


    print(
        f"전체 분석 완료: "
        f"REQ_IDNTF={req_idntf}, "
        f"EXCN_IDNTFS={excn_idntfs}"
    )

    return result