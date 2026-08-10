import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SelectField, TextAreaField, IntegerField, DateField, TimeField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "campusquest-dev-secret")
database_url = os.environ.get("DATABASE_URL", "sqlite:///campusquest.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    registration_number = db.Column(db.String(50), unique=True, nullable=True)
    department = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student", nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)

    registrations = db.relationship("Registration", back_populates="student", cascade="all, delete-orphan")
    events = db.relationship("Event", back_populates="organizer", cascade="all, delete-orphan")


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.Time, nullable=False)
    venue = db.Column(db.String(150), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    image_type = db.Column(db.String(30), default="default", nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    organizer = db.relationship("User", back_populates="events")
    registrations = db.relationship("Registration", back_populates="event", cascade="all, delete-orphan")


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    attended = db.Column(db.Boolean, default=False, nullable=False)

    student = db.relationship("User", back_populates="registrations")
    event = db.relationship("Event", back_populates="registrations")

    __table_args__ = (
        db.UniqueConstraint("student_id", "event_id", name="unique_student_event"),
    )


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    registration_number = StringField("Registration number", validators=[Optional(), Length(max=50)])
    department = StringField("Department", validators=[Optional(), Length(max=100)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class EventForm(FlaskForm):
    title = StringField("Event title", validators=[DataRequired(), Length(min=3, max=150)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10, max=2000)])
    category = SelectField(
        "Category",
        choices=[
            ("Technical", "Technical"),
            ("Cultural", "Cultural"),
            ("Sports", "Sports"),
            ("Workshop", "Workshop"),
            ("Competition", "Competition"),
            ("Academic", "Academic"),
        ],
        validators=[DataRequired()],
    )
    event_date = DateField("Date", format="%Y-%m-%d", validators=[DataRequired()])
    event_time = TimeField("Time", format="%H:%M", validators=[DataRequired()])
    venue = StringField("Venue", validators=[DataRequired(), Length(min=2, max=150)])
    capacity = IntegerField("Maximum seats", validators=[DataRequired(), NumberRange(min=1, max=10000)])
    image_type = SelectField(
        "Visual",
        choices=[
            ("code", "Technical / Code"),
            ("mic", "Cultural / Stage"),
            ("sport", "Sports"),
            ("abstract", "Abstract Event"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Create event")


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def organizer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login"))
        if user.role != "organizer":
            flash("Organizer access is required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def home():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    events_query = Event.query.order_by(Event.event_date.asc(), Event.event_time.asc())
    if query:
        events_query = events_query.filter(
            or_(
                Event.title.ilike(f"%{query}%"),
                Event.description.ilike(f"%{query}%"),
                Event.venue.ilike(f"%{query}%"),
            )
        )
    if category:
        events_query = events_query.filter_by(category=category)
    events = events_query.all()

    stats = {
        "events": Event.query.count(),
        "students": User.query.filter_by(role="student").count(),
        "this_month": Event.query.filter(
            db.extract("month", Event.event_date) == datetime.utcnow().month,
            db.extract("year", Event.event_date) == datetime.utcnow().year,
        ).count(),
    }
    return render_template("home.html", events=events, stats=stats, query=query, category=category)


@app.route("/events")
def events():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    events_query = Event.query.order_by(Event.event_date.asc(), Event.event_time.asc())
    if query:
        events_query = events_query.filter(
            or_(
                Event.title.ilike(f"%{query}%"),
                Event.description.ilike(f"%{query}%"),
                Event.venue.ilike(f"%{query}%"),
            )
        )
    if category:
        events_query = events_query.filter_by(category=category)
    return render_template("events.html", events=events_query.all(), query=query, category=category)


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    event = db.get_or_404(Event, event_id)
    registered = False
    user = current_user()
    if user:
        registered = Registration.query.filter_by(student_id=user.id, event_id=event.id).first() is not None
    return render_template("event_detail.html", event=event, registered=registered)


@app.route("/event/<int:event_id>/register", methods=["POST"])
@login_required
def register_event(event_id):
    event = db.get_or_404(Event, event_id)
    user = current_user()
    if user.role != "student":
        flash("Only student accounts can register for events.", "error")
        return redirect(url_for("event_detail", event_id=event.id))

    existing = Registration.query.filter_by(student_id=user.id, event_id=event.id).first()
    if existing:
        flash("You are already registered for this event.", "info")
        return redirect(url_for("event_detail", event_id=event.id))

    if len(event.registrations) >= event.capacity:
        flash("This event is full.", "error")
        return redirect(url_for("event_detail", event_id=event.id))

    registration = Registration(student_id=user.id, event_id=event.id)
    user.points += 5
    db.session.add(registration)
    db.session.commit()
    flash("You're registered. 5 participation points added.", "success")
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower()).first()
        if existing:
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html", form=form)

        user = User(
            name=form.name.data,
            email=form.email.data.lower(),
            registration_number=form.registration_number.data or None,
            department=form.department.data or None,
            password_hash=generate_password_hash(form.password.data),
            role="student",
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully. You can now sign in.", "success")
        return redirect(url_for("login"))
    return render_template("auth/register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if not user or not check_password_hash(user.password_hash, form.password.data):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", form=form)

        session.clear()
        session["user_id"] = user.id
        next_page = request.args.get("next")
        return redirect(next_page or url_for("dashboard"))
    return render_template("auth/login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    registrations = Registration.query.filter_by(student_id=user.id).join(Event).order_by(Event.event_date.asc()).all()
    attended = [r for r in registrations if r.attended]
    workshops = [r for r in attended if r.event.category == "Workshop"]
    competitions = [r for r in attended if r.event.category == "Competition"]
    return render_template(
        "student/dashboard.html",
        registrations=registrations,
        attended_count=len(attended),
        workshop_count=len(workshops),
        competition_count=len(competitions),
    )


@app.route("/organizer")
@organizer_required
def organizer_dashboard():
    user = current_user()
    own_events = Event.query.filter_by(organizer_id=user.id).order_by(Event.event_date.asc()).all()
    total_registrations = sum(len(event.registrations) for event in own_events)
    return render_template(
        "organizer/dashboard.html",
        own_events=own_events,
        total_registrations=total_registrations,
    )


@app.route("/organizer/events/new", methods=["GET", "POST"])
@organizer_required
def create_event():
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            event_date=form.event_date.data,
            event_time=form.event_time.data,
            venue=form.venue.data,
            capacity=form.capacity.data,
            image_type=form.image_type.data,
            organizer_id=current_user().id,
        )
        db.session.add(event)
        db.session.commit()
        flash("Event created successfully.", "success")
        return redirect(url_for("organizer_dashboard"))
    return render_template("organizer/create_event.html", form=form)


@app.route("/organizer/event/<int:event_id>/attendance", methods=["POST"])
@organizer_required
def toggle_attendance(event_id):
    event = db.get_or_404(Event, event_id)
    if event.organizer_id != current_user().id:
        flash("You cannot manage this event.", "error")
        return redirect(url_for("organizer_dashboard"))

    registration_id = request.form.get("registration_id", type=int)
    registration = db.session.get(Registration, registration_id)
    if registration and registration.event_id == event.id:
        if not registration.attended:
            registration.attended = True
            registration.student.points += 20
            db.session.commit()
            flash("Attendance marked and 20 points added.", "success")
        else:
            flash("Attendance is already marked.", "info")
    return redirect(url_for("organizer_dashboard"))


@app.errorhandler(404)
def not_found(_):
    return render_template("errors/404.html"), 404


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
