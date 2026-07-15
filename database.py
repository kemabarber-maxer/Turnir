import sqlite3

from flask import g

from config import Config



def get_db():


    if "db" not in g:


        g.db = sqlite3.connect(
            Config.DATABASE
        )


        g.db.row_factory = sqlite3.Row


    return g.db





def close_db(error=None):


    db = g.pop(
        "db",
        None
    )


    if db is not None:

        db.close()





def init_db(app):


    with app.app_context():


        db = get_db()



        db.executescript("""

        CREATE TABLE IF NOT EXISTS users(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ref_code TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,

            pubg_id TEXT NOT NULL,

            phone TEXT NOT NULL,

            contact TEXT NOT NULL,

            team_code TEXT,

            leader INTEGER DEFAULT 0,

            payment INTEGER DEFAULT 0,

            approved INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        );



        CREATE TABLE IF NOT EXISTS teams(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            team_code TEXT UNIQUE NOT NULL,

            team_name TEXT NOT NULL,

            leader_ref TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        );



        CREATE TABLE IF NOT EXISTS settings(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT UNIQUE NOT NULL,

            value TEXT NOT NULL

        );


        """)



        settings = {


            "tournament_name":
            "PUBG MOBILE TOURNAMENT",


            "date":
            "25 July 2026",


            "time":
            "20:00",


            "map":
            "Erangel",


            "price":
            "5 Manat",


            "slots":
            "100"


        }



        for key,value in settings.items():


            db.execute(

                """
                INSERT OR IGNORE INTO settings
                (name,value)

                VALUES(?,?)

                """,

                (
                    key,
                    value
                )

            )



        db.commit()



    app.teardown_appcontext(
        close_db
    )