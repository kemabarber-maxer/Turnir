from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session
)

from config import Config
from database import init_db, get_db

from functools import wraps
import random
import string



app = Flask(__name__)

app.config.from_object(Config)



init_db(app)



# ==========================
# HELPERS
# ==========================


def generate_ref():

    db = get_db()

    while True:

        code = "PUBG-" + "".join(
            random.choices(
                string.ascii_uppercase +
                string.digits,
                k=6
            )
        )


        check = db.execute(
            """
            SELECT id
            FROM users
            WHERE ref_code=?
            """,
            (code,)
        ).fetchone()


        if not check:

            return code





def generate_team_code():

    db = get_db()

    while True:

        code = "TEAM-" + "".join(
            random.choices(
                string.ascii_uppercase +
                string.digits,
                k=5
            )
        )


        check = db.execute(
            """
            SELECT id
            FROM teams
            WHERE team_code=?
            """,
            (code,)
        ).fetchone()


        if not check:

            return code





def admin_required(func):

    @wraps(func)

    def wrapper(*args, **kwargs):

        if not session.get("admin"):

            return redirect("/admin")


        return func(*args, **kwargs)


    return wrapper





# ==========================
# HOME
# ==========================


@app.route("/")
def home():

    db = get_db()


    total = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM users
        """
    ).fetchone()


    return render_template(
        "index.html",
        total=total["total"]
    )





# ==========================
# REGISTER
# ==========================


@app.route(
    "/kayit",
    methods=["GET","POST"]
)

def kayit():


    if request.method == "POST":


        name = request.form.get("name")

        pubg_id = request.form.get("pubg_id")

        phone = request.form.get("phone")

        contact = request.form.get("contact")



        if not name or not pubg_id:

            return "Maglumatlary dolduryň"



        ref = generate_ref()



        db = get_db()



        db.execute(
            """
            INSERT INTO users
            (
            ref_code,
            name,
            pubg_id,
            phone,
            contact
            )

            VALUES(?,?,?,?,?)

            """,
            (
                ref,
                name,
                pubg_id,
                phone,
                contact
            )
        )


        db.commit()



        session["user_ref"] = ref



        return redirect("/profil")



    return render_template(
        "kayit.html"
    )





# ==========================
# PROFILE
# ==========================


@app.route("/profil")

def profil():


    ref = session.get(
        "user_ref"
    )


    if not ref:

        return redirect("/kayit")



    db = get_db()



    user = db.execute(
        """
        SELECT *
        FROM users
        WHERE ref_code=?

        """,
        (ref,)
    ).fetchone()



    if not user:

        return redirect("/kayit")



    return render_template(
        "profil.html",
        user=user
    )





# ==========================
# LOGOUT
# ==========================


@app.route("/logout")

def logout():

    session.clear()

    return redirect("/")





# ==========================
# TEAM CREATE
# ==========================


@app.route(
    "/team",
    methods=["GET","POST"]
)

def team():


    if request.method == "POST":


        team_name = request.form.get(
            "team_name"
        )


        ref = session.get(
            "user_ref"
        )


        if not ref:

            return redirect("/kayit")



        db = get_db()



        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE ref_code=?
            """,
            (ref,)
        ).fetchone()



        if user["team_code"]:

            return "Siz eýýäm toparly"



        code = generate_team_code()



        db.execute(
            """
            INSERT INTO teams
            (
            team_code,
            team_name,
            leader_ref
            )

            VALUES(?,?,?)

            """,
            (
                code,
                team_name,
                ref
            )
        )



        db.execute(
            """
            UPDATE users
            SET team_code=?,
            leader=1
            WHERE ref_code=?

            """,
            (
                code,
                ref
            )
        )



        db.commit()



        return redirect("/profil")



    return render_template(
        "team.html"
    )





# ==========================
# JOIN TEAM
# ==========================


@app.route(
    "/join-team",
    methods=["POST"]
)

def join_team():


    team_code = request.form.get(
        "team_code"
    )


    ref = session.get(
        "user_ref"
    )


    if not ref:

        return redirect("/kayit")



    db = get_db()



    user = db.execute(
        """
        SELECT *
        FROM users
        WHERE ref_code=?
        """,
        (ref,)
    ).fetchone()



    if user["team_code"]:

        return "Siz eýýäm toparly"



    team = db.execute(
        """
        SELECT *
        FROM teams
        WHERE team_code=?
        """,
        (team_code,)
    ).fetchone()



    if not team:

        return "Topar tapylmady"



    count = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM users
        WHERE team_code=?

        """,
        (team_code,)
    ).fetchone()



    if count["c"] >= Config.TEAM_SIZE:

        return "Topar doly"



    db.execute(
        """
        UPDATE users
        SET team_code=?

        WHERE ref_code=?

        """,
        (
            team_code,
            ref
        )
    )



    db.commit()



    return redirect("/profil")





# ==========================
# ADMIN LOGIN
# ==========================


@app.route("/admin")

def admin_login():

    return render_template(
        "admin/login.html"
    )





@app.route(
    "/admin/login",
    methods=["POST"]
)

def admin_check():


    password = request.form.get(
        "password"
    )



    if password == Config.ADMIN_PASSWORD:


        session["admin"] = True


        return redirect(
            "/admin/panel"
        )



    return "Parol nädogry"





# ==========================
# ADMIN PANEL
# ==========================


@app.route("/admin/panel")

@admin_required

def admin_panel():


    db = get_db()


    users = db.execute(
        """
        SELECT *
        FROM users
        ORDER BY id DESC

        """
    ).fetchall()



    return render_template(
        "admin/panel.html",
        users=users
    )





@app.route(
    "/admin/payment/<int:user_id>"
)

@admin_required

def payment_ok(user_id):


    db = get_db()


    db.execute(
        """
        UPDATE users
        SET payment=1
        WHERE id=?

        """,
        (user_id,)
    )


    db.commit()


    return redirect("/admin/panel")





@app.route(
    "/admin/approve/<int:user_id>"
)

@admin_required

def approve_user(user_id):


    db = get_db()


    db.execute(
        """
        UPDATE users
        SET approved=1
        WHERE id=?

        """,
        (user_id,)
    )


    db.commit()


    return redirect("/admin/panel")





@app.route("/admin/logout")

def admin_logout():

    session.pop(
        "admin",
        None
    )


    return redirect("/admin")





# ==========================
# RUN
# ==========================


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
