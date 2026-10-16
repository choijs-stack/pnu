import json

from db import get_db_connection


# =========================================================
# EXCN 목록 정규화
# =========================================================
def normalize_excn_idntfs(excn_idntfs):
    """
    EXCN_IDNTF 목록을 숫자로 변환하고
    중복 제거 후 정렬한다.
    """

    if not excn_idntfs:
        raise ValueError(
            "excn_idntfs가 비어 있습니다."
        )

    return sorted(
        set(
            int(excn_idntf)
            for excn_idntf in excn_idntfs
        )
    )


# =========================================================
# 동일 분석 결과 찾기
# =========================================================
def find_analysis_result_id(
    cursor,
    req_idntf,
    excn_idntfs
):
    """
    동일한 REQ_IDNTF + 동일한 EXCN_IDNTF 목록으로
    저장된 분석 결과가 있는지 확인한다.
    """

    excn_idntfs = normalize_excn_idntfs(
        excn_idntfs
    )

    placeholders = ", ".join(
        ["%s"] * len(excn_idntfs)
    )

    sql = f"""
        SELECT
            r.ANLS_RSLT_IDNTF
        FROM ANLS_RSLT_NEW r
        INNER JOIN ANLS_RSLT_EXCN re
            ON r.ANLS_RSLT_IDNTF
             = re.ANLS_RSLT_IDNTF
        WHERE r.REQ_IDNTF = %s
        GROUP BY
            r.ANLS_RSLT_IDNTF
        HAVING
            COUNT(*) = %s
            AND
            SUM(
                CASE
                    WHEN re.EXCN_IDNTF IN ({placeholders})
                    THEN 1
                    ELSE 0
                END
            ) = %s
        ORDER BY
            r.ANLS_RSLT_IDNTF DESC
        LIMIT 1
    """

    params = (
        req_idntf,
        len(excn_idntfs),
        *excn_idntfs,
        len(excn_idntfs)
    )

    cursor.execute(
        sql,
        params
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row[0]


# =========================================================
# 분석 결과 저장
# =========================================================
def save_analysis_result(
    req_idntf,
    excn_idntfs,
    result
):

    conn = None
    cursor = None

    try:

        # -----------------------------------------------------
        # 1. EXCN 목록 정규화
        # -----------------------------------------------------
        excn_idntfs = normalize_excn_idntfs(
            excn_idntfs
        )

        conn = get_db_connection()
        cursor = conn.cursor()

        result_json = json.dumps(
            result,
            ensure_ascii=False,
            default=str
        )


        # -----------------------------------------------------
        # 2. 동일 REQ + EXCN 분석결과 존재 여부 확인
        # -----------------------------------------------------
        analysis_result_id = (
            find_analysis_result_id(
                cursor=cursor,
                req_idntf=req_idntf,
                excn_idntfs=excn_idntfs
            )
        )


        # -----------------------------------------------------
        # 3. 동일한 분석 대상이 이미 있으면 UPDATE
        # -----------------------------------------------------
        if analysis_result_id is not None:

            print(
                f"[UPDATE 시작] "
                f"ANLS_RSLT_IDNTF="
                f"{analysis_result_id}, "
                f"REQ_IDNTF={req_idntf}, "
                f"EXCN_IDNTFS={excn_idntfs}"
            )

            update_sql = """
                UPDATE ANLS_RSLT_NEW
                SET
                    ANLS_RSLT_JSON = %s,
                    CRT_DT = CURRENT_TIMESTAMP
                WHERE ANLS_RSLT_IDNTF = %s
            """

            cursor.execute(
                update_sql,
                (
                    result_json,
                    analysis_result_id
                )
            )

            print(
                f"[UPDATE 결과] "
                f"rowcount={cursor.rowcount}"
            )


        # -----------------------------------------------------
        # 4. 새로운 분석 대상이면 INSERT
        # -----------------------------------------------------
        else:

            print(
                f"[INSERT 시작] "
                f"REQ_IDNTF={req_idntf}, "
                f"EXCN_IDNTFS={excn_idntfs}"
            )

            insert_result_sql = """
                INSERT INTO ANLS_RSLT_NEW
                (
                    REQ_IDNTF,
                    ANLS_RSLT_JSON
                )
                VALUES
                (
                    %s,
                    %s
                )
            """

            cursor.execute(
                insert_result_sql,
                (
                    req_idntf,
                    result_json
                )
            )

            # 방금 생성된 ANLS_RSLT_IDNTF
            analysis_result_id = (
                cursor.lastrowid
            )

            print(
                f"분석결과 생성: "
                f"ANLS_RSLT_IDNTF="
                f"{analysis_result_id}"
            )


            # -------------------------------------------------
            # 5. 분석결과와 EXCN 연결 저장
            # -------------------------------------------------
            insert_excn_sql = """
                INSERT INTO ANLS_RSLT_EXCN
                (
                    ANLS_RSLT_IDNTF,
                    EXCN_IDNTF
                )
                VALUES
                (
                    %s,
                    %s
                )
            """

            excn_rows = [
                (
                    analysis_result_id,
                    excn_idntf
                )
                for excn_idntf
                in excn_idntfs
            ]

            cursor.executemany(
                insert_excn_sql,
                excn_rows
            )

            print(
                f"분석결과 EXCN 연결 저장: "
                f"{len(excn_rows)}건"
            )


        # -----------------------------------------------------
        # 6. 저장 완료
        # -----------------------------------------------------
        conn.commit()

        print(
            f"분석 결과 저장 완료: "
            f"ANLS_RSLT_IDNTF="
            f"{analysis_result_id}, "
            f"REQ_IDNTF={req_idntf}, "
            f"EXCN_IDNTFS={excn_idntfs}"
        )

        return analysis_result_id


    except Exception:

        if conn:
            conn.rollback()

        raise


    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


# =========================================================
# 분석 결과 조회
# =========================================================
def get_analysis_result(
    req_idntf,
    excn_idntfs
):

    conn = None
    cursor = None

    try:

        # -----------------------------------------------------
        # 1. EXCN 목록 정규화
        # -----------------------------------------------------
        excn_idntfs = normalize_excn_idntfs(
            excn_idntfs
        )

        conn = get_db_connection()

        # 분석결과 ID 검색은 tuple 형태가 편하므로
        # 일반 cursor 사용
        cursor = conn.cursor()


        # -----------------------------------------------------
        # 2. 동일 REQ + EXCN 분석결과 찾기
        # -----------------------------------------------------
        analysis_result_id = (
            find_analysis_result_id(
                cursor=cursor,
                req_idntf=req_idntf,
                excn_idntfs=excn_idntfs
            )
        )

        if analysis_result_id is None:
            return None


        cursor.close()

        cursor = conn.cursor(
            dictionary=True
        )


        # -----------------------------------------------------
        # 3. 분석 결과 조회
        # -----------------------------------------------------
        sql = """
            SELECT
                ANLS_RSLT_IDNTF,
                REQ_IDNTF,
                ANLS_RSLT_JSON,
                CRT_DT
            FROM ANLS_RSLT_NEW
            WHERE ANLS_RSLT_IDNTF = %s
        """

        cursor.execute(
            sql,
            (analysis_result_id,)
        )

        row = cursor.fetchone()

        if not row:
            return None


        # -----------------------------------------------------
        # 4. JSON 변환
        # -----------------------------------------------------
        result_json = row[
            "ANLS_RSLT_JSON"
        ]

        if isinstance(
            result_json,
            str
        ):

            result = json.loads(
                result_json
            )

        else:

            result = result_json


        return result


    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()