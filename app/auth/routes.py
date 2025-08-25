from flask import Blueprint, render_template

bp = Blueprint("auth", __name__)


@bp.route("/login")
def login():
    # V1 Dummy Login Seite
    return render_template("login.html")
