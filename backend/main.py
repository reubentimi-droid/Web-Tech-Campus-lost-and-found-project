from flask import Flask, redirect, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__,
            template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///lostfound.db"
app.secret_key = "change-this-later"  # needed for sessions (login memory)
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255))


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")
    user = db.session.get(User, session["user_id"])
    return render_template("home.html", user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        email, password = request.form["email"], request.form["password"]
        if User.query.filter_by(email=email).first():
            error = "That email is already registered"
        else:
            db.session.add(User(email=email, password_hash=generate_password_hash(password)))
            db.session.commit()
            return redirect("/login")
    return render_template("auth.html", title="Register", error=error,
                           other_url="/login", other_text="Already have an account? Log in")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            session["user_id"] = user.id
            return redirect("/")
        error = "Wrong email or password"
    return render_template("auth.html", title="Login", error=error,
                           other_url="/register", other_text="Need an account? Register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
