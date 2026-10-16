from flask import Blueprint, request, jsonify

from db import get_db_connection
from result_service import get_analysis_result
from analysis_service import get_collected_articles


result_bp = Blueprint(
    "analysis_result",
    __name__
)


# =========================================================
# 실행회차 기준 EXCN_IDNTF 목록 조회
# =========================================================
def get_excn_idntfs(
    req_idntf,
    excn_sno
):

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
            SELECT
                EXCN_IDNTF
            FROM CLCT_EXCN
            WHERE REQ_IDNTF = %s
              AND EXCN_SNO = %s
            ORDER BY EXCN_IDNTF
        """

        cursor.execute(
            sql,
            (
                req_idntf,
                excn_sno
            )
        )

        rows = cursor.fetchall()

        return [
            row[0]
            for row in rows
        ]

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


# =========================================================
# 분석 결과 조회 API
# =========================================================
@result_bp.route(
    "/api/analysis/result",
    methods=["POST"]
)
def analysis_result():

    try:

        # -----------------------------------------------------
        # 1. 요청 데이터 확인
        # -----------------------------------------------------
        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "code": 400,
                "message": "요청 데이터가 없습니다."
            }), 400


        # -----------------------------------------------------
        # 2. REQ_IDNTF 확인
        # -----------------------------------------------------
        req_idntf = data.get(
            "req_idntf"
        )

        if req_idntf is None:

            return jsonify({
                "code": 400,
                "message": "req_idntf가 필요합니다."
            }), 400


        # -----------------------------------------------------
        # 3. EXCN_SNO 확인
        # -----------------------------------------------------
        excn_sno = data.get(
            "excn_sno"
        )

        if excn_sno is None:

            return jsonify({
                "code": 400,
                "message": "excn_sno가 필요합니다."
            }), 400


        # -----------------------------------------------------
        # 4. 숫자 형식 변환
        # -----------------------------------------------------
        try:

            req_idntf = int(
                req_idntf
            )

            excn_sno = int(
                excn_sno
            )

        except (TypeError, ValueError):

            return jsonify({
                "code": 400,
                "message": (
                    "req_idntf와 excn_sno는 "
                    "숫자 형식이어야 합니다."
                )
            }), 400


        print(
            f"분석 결과 조회 API 호출: "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_SNO={excn_sno}"
        )


        # -----------------------------------------------------
        # 5. 해당 실행회차의 EXCN_IDNTF 목록 조회
        # -----------------------------------------------------
        excn_idntfs = get_excn_idntfs(
            req_idntf=req_idntf,
            excn_sno=excn_sno
        )

        if not excn_idntfs:

            return jsonify({
                "code": 404,
                "message": (
                    "해당 요청 및 실행회차의 "
                    "수집 실행 정보가 없습니다."
                )
            }), 404


        print(
            f"분석 대상 EXCN 조회 완료: "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_SNO={excn_sno}, "
            f"EXCN_IDNTFS={excn_idntfs}"
        )


        # -----------------------------------------------------
        # 6. 저장된 분석 결과 조회
        # -----------------------------------------------------
        result = get_analysis_result(
            req_idntf=req_idntf,
            excn_idntfs=excn_idntfs
        )

        if result is None:

            return jsonify({
                "code": 404,
                "message": "분석 결과가 없습니다."
            }), 404


        # -----------------------------------------------------
        # 7. 수집 데이터 목록 조회
        # -----------------------------------------------------
        articles = get_collected_articles(
            req_idntf=req_idntf,
            excn_idntfs=excn_idntfs
        )


        # -----------------------------------------------------
        # 8. 분석 결과 + 수집 데이터 목록 결합
        # -----------------------------------------------------
        result["articles"] = articles


        # -----------------------------------------------------
        # 9. 최종 결과 반환
        # -----------------------------------------------------
        return jsonify({
            "code": 200,
            "message": "정상",
            "req_idntf": req_idntf,
            "excn_sno": excn_sno,
            "excn_idntfs": excn_idntfs,
            "data": result
        }), 200


    except Exception as e:

        print(
            f"분석 결과 조회 오류: {e}"
        )

        return jsonify({
            "code": 500,
            "message": "분석 결과 조회 중 오류가 발생했습니다.",
            "error": str(e)
        }), 500