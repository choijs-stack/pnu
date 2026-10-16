from flask import Blueprint, request, jsonify

from db import get_db_connection
from analysis_runner import run_analysis
from result_service import save_analysis_result


analysis_bp = Blueprint(
    "analysis",
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
# 분석 실행 API
# =========================================================
@analysis_bp.route(
    "/api/analysis/run",
    methods=["POST"]
)
def execute_analysis():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "code": 400,
                "success": False,
                "message": "요청 JSON이 없습니다."
            }), 400


        # -----------------------------------------------------
        # REQ_IDNTF 확인
        # -----------------------------------------------------
        req_idntf = data.get(
            "req_idntf"
        )

        if req_idntf is None:

            return jsonify({
                "code": 400,
                "success": False,
                "message": "req_idntf가 필요합니다."
            }), 400


        # -----------------------------------------------------
        # EXCN_SNO 확인
        # -----------------------------------------------------
        excn_sno = data.get(
            "excn_sno"
        )

        if excn_sno is None:

            return jsonify({
                "code": 400,
                "success": False,
                "message": "excn_sno가 필요합니다."
            }), 400


        # -----------------------------------------------------
        # 숫자 형식 변환
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
                "success": False,
                "message": (
                    "req_idntf와 excn_sno는 "
                    "숫자 형식이어야 합니다."
                )
            }), 400


        print(
            f"분석 API 호출: "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_SNO={excn_sno}"
        )


        # -----------------------------------------------------
        # 해당 실행회차의 EXCN_IDNTF 목록 조회
        # -----------------------------------------------------
        excn_idntfs = get_excn_idntfs(
            req_idntf=req_idntf,
            excn_sno=excn_sno
        )


        # 해당 회차의 실행 데이터가 없는 경우
        if not excn_idntfs:

            return jsonify({
                "code": 404,
                "success": False,
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
        # 분석 실행
        # -----------------------------------------------------
        result = run_analysis(
            req_idntf=req_idntf,
            excn_idntfs=excn_idntfs
        )


        # -----------------------------------------------------
        # 분석 결과 DB 저장
        # -----------------------------------------------------
        save_analysis_result(
            req_idntf=req_idntf,
            excn_idntfs=excn_idntfs,
            result=result
        )


        # -----------------------------------------------------
        # 최종 응답
        # -----------------------------------------------------
        return jsonify({
            "code": 200,
            "success": True,
            "req_idntf": req_idntf,
            "excn_sno": excn_sno,
            "excn_idntfs": excn_idntfs,
            "message": "분석이 완료되었습니다."
        }), 200


    except Exception as e:

        print(
            f"분석 실행 오류: {e}"
        )

        return jsonify({
            "code": 500,
            "success": False,
            "message": "분석 실행 중 오류가 발생했습니다.",
            "error": str(e)
        }), 500