import os


BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)


class Config:


    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "render-secret-key"
    )


    DATABASE = os.path.join(
        BASE_DIR,
        "turnuva.db"
    )


    ADMIN_PASSWORD = os.environ.get(
        "ADMIN_PASSWORD",
        "admin123"
    )


    TOURNAMENT_NAME = "PUBG MOBILE TOURNAMENT"


    MAX_PLAYERS = 100


    TEAM_SIZE = 4


    ENTRY_PRICE = "5 Manat"


    MAP_NAME = "Erangel"


    TOURNAMENT_DATE = "25 July 2026"


    TOURNAMENT_TIME = "20:00"


    SESSION_COOKIE_HTTPONLY = True


    SESSION_COOKIE_SAMESITE = "Lax"


    SESSION_COOKIE_SECURE = True
