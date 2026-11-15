import hmac
import os
import secrets
from datetime import date, datetime

from flask import Flask, jsonify, redirect, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, or_, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///lostfound.db"
)
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default="")
    email = db.Column(db.String(190), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    listings = db.relationship("Listing", backref="user", lazy=True)


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(180), nullable=False)
    item_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, nullable=False, default=False)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    listing = db.relationship("Listing")
    reporter = db.relationship("User")


def initialize_database():
    db.create_all()
    columns = {column["name"] for column in inspect(db.engine).get_columns("user")}
    with db.engine.begin() as connection:
        if "name" not in columns:
            connection.execute(
                text("ALTER TABLE user ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT ''")
            )
        if "role" not in columns:
            connection.execute(
                text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
            )


def public_user(user):
    return {
        "id": user.id,
        "name": user.name or user.email.split("@", 1)[0],
        "email": user.email,
        "role": user.role,
    }


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id is not None else None


def api_error(message, status=400):
    return jsonify(ok=False, error=message), status


def require_user():
    user = current_user()
    if user is None:
        return None, api_error("Please log in to continue.", 401)
    return user, None


def parse_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def api_action(action):
    if request.method == "GET" and action == "csrf":
        token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
        user = current_user()
        return jsonify(ok=True, csrf=token, user=public_user(user) if user else None)

    if request.method == "GET" and action == "listings":
        query = Listing.query.join(User).filter(Listing.status == "active")
        search = request.args.get("q", "").strip()
        listing_type = request.args.get("type", "").strip()
        category = request.args.get("category", "").strip()
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Listing.title.ilike(pattern),
                    Listing.description.ilike(pattern),
                    Listing.location.ilike(pattern),
                )
            )
        if listing_type in {"lost", "found"}:
            query = query.filter(Listing.type == listing_type)
        if category:
            query = query.filter(Listing.category == category)
        listings = query.order_by(Listing.created_at.desc()).all()
        return jsonify(
            ok=True,
            listings=[
                {
                    "id": listing.id,
                    "type": listing.type,
                    "title": listing.title,
                    "category": listing.category,
                    "description": listing.description,
                    "location": listing.location,
                    "item_date": listing.item_date.isoformat() if listing.item_date else None,
                    "poster_name": listing.user.name or listing.user.email.split("@", 1)[0],
                }
                for listing in listings
            ],
        )

    if request.method == "GET" and action == "admin-reports":
        user, error = require_user()
        if error:
            return error
        if user.role != "admin":
            return api_error("Administrator access is required.", 403)
        reports = Report.query.filter_by(status="open").order_by(Report.created_at.asc()).all()
        return jsonify(
            ok=True,
            reports=[
                {
                    "report_id": report.id,
                    "listing_id": report.listing_id,
                    "title": report.listing.title,
                    "type": report.listing.type,
                    "reason": report.reason,
                    "reporter_name": report.reporter.name
                    or report.reporter.email.split("@", 1)[0],
                    "reported_at": report.created_at.strftime("%b %d, %Y"),
                }
                for report in reports
            ],
        )

    if request.method != "POST":
        return api_error("Unknown action.", 404)

    expected_token = session.get("csrf_token", "")
    supplied_token = request.headers.get("X-CSRF-Token", "")
    if not expected_token or not hmac.compare_digest(expected_token, supplied_token):
        return api_error("Your session token is invalid. Refresh the page and try again.", 403)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return api_error("A JSON request body is required.", 400)

    if action == "register":
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if not email or not password:
            return api_error("Email and password are required.")
        if len(name) > 100 or len(email) > 190 or len(password) > 1024:
            return api_error("One or more fields are too long.")
        name = name or email.split("@", 1)[0]
        if User.query.filter_by(email=email).first():
            return api_error("That email is already registered.", 409)
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return api_error("That email is already registered.", 409)
        session.clear()
        session["user_id"] = user.id
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(
            ok=True,
            message="Your account is ready.",
            user=public_user(user),
            csrf=session["csrf_token"],
        )

    if action == "login":
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        user = User.query.filter_by(email=email).first() if email else None
        if user is None or not check_password_hash(user.password_hash, password):
            return api_error("Wrong email or password", 401)
        session.clear()
        session["user_id"] = user.id
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(ok=True, user=public_user(user), csrf=session["csrf_token"])

    user, error = require_user()
    if error:
        return error

    if action == "logout":
        session.clear()
        return jsonify(ok=True)

    if action == "create-listing":
        listing_type = str(payload.get("type", "")).strip()
        title = str(payload.get("title", "")).strip()
        category = str(payload.get("category", "")).strip()
        description = str(payload.get("description", "")).strip()
        location = str(payload.get("location", "")).strip()
        item_date_value = str(payload.get("item_date", "")).strip()
        if listing_type not in {"lost", "found"}:
            return api_error("Choose whether the item was lost or found.")
        if not all((title, category, description, location)):
            return api_error("Title, category, description, and location are required.")
        if len(title) > 140 or len(category) > 80 or len(location) > 180:
            return api_error("One or more listing fields are too long.")
        try:
            item_date = date.fromisoformat(item_date_value) if item_date_value else None
        except ValueError:
            return api_error("Enter a valid item date.")
        listing = Listing(
            user_id=user.id,
            type=listing_type,
            title=title,
            category=category,
            description=description,
            location=location,
            item_date=item_date,
        )
        db.session.add(listing)
        db.session.commit()
        return jsonify(ok=True, message="Listing posted.", listing_id=listing.id)

    if action == "contact":
        listing_id = parse_id(payload.get("listing_id"))
        message_text = str(payload.get("message", "")).strip()
        listing = db.session.get(Listing, listing_id) if listing_id else None
        if listing is None or listing.status != "active":
            return api_error("That listing is no longer available.", 404)
        if listing.user_id == user.id:
            return api_error("You cannot message yourself about your listing.")
        if not message_text:
            return api_error("Enter a message.")
        message = Message(
            listing_id=listing.id,
            sender_id=user.id,
            recipient_id=listing.user_id,
            message=message_text,
        )
        db.session.add(message)
        db.session.commit()
        return jsonify(ok=True, message="Message sent.")

    if action == "report":
        listing_id = parse_id(payload.get("listing_id"))
        reason = str(payload.get("reason", "")).strip()
        listing = db.session.get(Listing, listing_id) if listing_id else None
        if listing is None or listing.status != "active":
            return api_error("That listing is no longer available.", 404)
        if not reason:
            return api_error("Enter a reason for the report.")
        if len(reason) > 1000:
            return api_error("The report reason is too long.")
        db.session.add(Report(listing_id=listing.id, reporter_id=user.id, reason=reason))
        db.session.commit()
        return jsonify(ok=True, message="Report submitted.")

    if action == "admin-resolve":
        if user.role != "admin":
            return api_error("Administrator access is required.", 403)
        report_id = parse_id(payload.get("report_id"))
        listing_id = parse_id(payload.get("listing_id"))
        decision = payload.get("decision")
        report = db.session.get(Report, report_id) if report_id else None
        if (
            decision not in {"keep", "remove"}
            or report is None
            or report.status != "open"
            or report.listing_id != listing_id
        ):
            return api_error("That report could not be resolved.", 404)
        report.status = "resolved"
        report.listing.status = "removed" if decision == "remove" else "active"
        db.session.commit()
        return jsonify(
            ok=True,
            message="Listing removed." if decision == "remove" else "Listing kept.",
        )

    return api_error("Unknown action.", 404)


@app.route("/api.php", methods=["GET", "POST"])
def api():
    return api_action(request.args.get("action", ""))


@app.route("/")
def home():
    user = current_user()
    if user is None:
        return redirect("/login")
    return render_template("home.html", user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            error = "Email and password are required."
        elif User.query.filter_by(email=email).first():
            error = "That email is already registered"
        else:
            name = email.split("@", 1)[0]
            db.session.add(
                User(email=email, name=name, password_hash=generate_password_hash(password))
            )
            db.session.commit()
            return redirect("/login")
    return render_template(
        "auth.html",
        title="Register",
        error=error,
        other_url="/login",
        other_text="Already have an account? Log in",
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            session["user_id"] = user.id
            return redirect("/")
        error = "Wrong email or password"
    return render_template(
        "auth.html",
        title="Login",
        error=error,
        other_url="/register",
        other_text="Need an account? Register",
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    with app.app_context():
        initialize_database()
    app.run(debug=True)
