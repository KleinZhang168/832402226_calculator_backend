"""Backend entry point.

Local development::

    python run.py

Environment variables (all optional)::

    CALC_HOST          bind address, default 0.0.0.0 (phones on the LAN can reach it)
    CALC_PORT          listening port, default 5000
    PORT               port injected by a cloud platform, used when CALC_PORT is unset
    CALC_DEBUG         debug mode, default false
    CALC_DB_PATH       SQLite file path, default data/calculator.db
    CALC_FRONTEND_DIR  optional static front-end directory

A cloud deployment should run a production WSGI server instead::

    gunicorn run:app --bind 0.0.0.0:$PORT
"""

from src.app import create_app
from src.config import Config

app = create_app()


def main() -> None:
    """Start the development server."""
    frontend = Config.FRONTEND_DIR
    has_frontend = (frontend / "index.html").is_file() if frontend else False

    print("=" * 68)
    print("  832402226 Calculator Backend")
    print("=" * 68)
    print("  Listening : http://%s:%d" % (Config.HOST, Config.PORT))
    print("  Database  : %s" % Config.DATABASE_PATH)
    print("  Health    : GET http://127.0.0.1:%d/api/health" % Config.PORT)
    print("  Endpoints : GET http://127.0.0.1:%d/" % Config.PORT)
    if has_frontend:
        print("  Front-end : http://127.0.0.1:%d/index.html" % Config.PORT)
        print("              (served from the same origin as the API)")
    else:
        print("  Front-end : not bundled; run the front-end project separately")
    print("=" * 68)
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)


if __name__ == "__main__":
    main()
