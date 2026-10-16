from flask import Flask

from analysis_api import analysis_bp
from result_api import result_bp


def create_app():

    app = Flask(__name__)

    # 분석 실행 API
    app.register_blueprint(
        analysis_bp
    )

    # 분석 결과 조회 API
    app.register_blueprint(
        result_bp
    )

    return app


if __name__ == "__main__":

    app = create_app()

    app.run(
        host="0.0.0.0",
        port=5410,
        debug=False, 
        threaded=False
    )

