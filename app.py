import os
from datetime import datetime, timedelta
from functools import wraps

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for, Response
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
os.makedirs(app.instance_path, exist_ok=True)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "local-dev-key-change-before-deployment")
db_url = os.getenv("DATABASE_URL", "sqlite:///port_logistics.db")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if db_url.startswith("postgresql://"):
    db_url = db_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."


@app.before_request
def require_login_for_private_pages():
    """Require authentication before any private application page can load."""
    if request.endpoint in ("login", "health", "static"):
        return None
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=request.url))
    return None


ROLES = [
    "Administrator", "Port Operations Officer", "Terminal/Logistics Officer",
    "Cargo/Container Officer", "Truck/Transport Officer", "Management"
]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(60), nullable=False, default="Management")
    active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Vessel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    imo_number = db.Column(db.String(30), unique=True)
    voyage_number = db.Column(db.String(40))
    eta = db.Column(db.DateTime, nullable=False)
    etd = db.Column(db.DateTime)
    status = db.Column(db.String(30), nullable=False, default="Expected")
    priority = db.Column(db.String(20), nullable=False, default="Normal")
    required_berth_hours = db.Column(db.Integer, nullable=False, default=8)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Berth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    description = db.Column(db.String(160))
    available = db.Column(db.Boolean, default=True, nullable=False)
    max_vessel_length_m = db.Column(db.Float, default=300)


class CargoContainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    container_number = db.Column(db.String(30), unique=True, nullable=False)
    vessel_id = db.Column(db.Integer, db.ForeignKey("vessel.id"))
    cargo_description = db.Column(db.String(180), nullable=False)
    container_type = db.Column(db.String(30), default="20ft")
    weight_tonnes = db.Column(db.Float, default=0)
    priority = db.Column(db.String(20), default="Normal", nullable=False)
    status = db.Column(db.String(35), default="At port", nullable=False)
    expected_collection = db.Column(db.DateTime)
    yard_location_id = db.Column(db.Integer, db.ForeignKey("yard_location.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vessel = db.relationship("Vessel", backref="containers")
    yard_location = db.relationship("YardLocation", backref="containers")


class YardLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    zone = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=20)
    notes = db.Column(db.String(200))

    @property
    def occupied(self):
        return CargoContainer.query.filter_by(yard_location_id=self.id).filter(
            CargoContainer.status.notin_(["Released", "Departed"])
        ).count()

    @property
    def available_slots(self):
        return max(0, self.capacity - self.occupied)


class Truck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(40), unique=True, nullable=False)
    company = db.Column(db.String(120))
    driver_name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    active = db.Column(db.Boolean, default=True, nullable=False)


class TruckAppointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey("truck.id"), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey("cargo_container.id"))
    appointment_time = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.String(30), default="Collection")
    status = db.Column(db.String(30), default="Scheduled")
    notes = db.Column(db.String(250))
    truck = db.relationship("Truck", backref="appointments")
    container = db.relationship("CargoContainer", backref="appointments")


class ContainerMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.Integer, db.ForeignKey("cargo_container.id"), nullable=False)
    movement_type = db.Column(db.String(50), nullable=False)
    from_location = db.Column(db.String(80))
    to_location = db.Column(db.String(80))
    notes = db.Column(db.String(250))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    container = db.relationship("CargoContainer", backref="movements")


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    severity = db.Column(db.String(20), default="Information")
    title = db.Column(db.String(140), nullable=False)
    message = db.Column(db.Text, nullable=False)
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in allowed_roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def dt_local(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


@app.context_processor
def inject_globals():
    return {"now": datetime.utcnow, "roles": ROLES}


@app.route("/health")
def health():
    return {"status": "ok", "service": "Freetown Port Logistics Platform"}


@app.route("/")
@login_required
def dashboard():
    vessel_count = Vessel.query.count()
    container_count = CargoContainer.query.count()
    waiting_vessels = Vessel.query.filter(Vessel.status.in_(["Expected", "Waiting"])).count()
    truck_count = TruckAppointment.query.filter_by(status="Scheduled").count()
    yard_total = db.session.query(func.sum(YardLocation.capacity)).scalar() or 0
    yard_available = sum(y.available_slots for y in YardLocation.query.all())
    yard_used = max(0, yard_total - yard_available)
    yard_pct = round((yard_used / yard_total) * 100, 1) if yard_total else 0
    alerts = Alert.query.filter_by(resolved=False).order_by(Alert.created_at.desc()).limit(6).all()
    vessels = Vessel.query.order_by(Vessel.eta.asc()).limit(6).all()
    appointments = TruckAppointment.query.filter_by(status="Scheduled").order_by(
        TruckAppointment.appointment_time.asc()).limit(6).all()
    return render_template("dashboard.html", vessel_count=vessel_count,
        container_count=container_count, waiting_vessels=waiting_vessels,
        truck_count=truck_count, yard_total=yard_total, yard_used=yard_used,
        yard_pct=yard_pct, alerts=alerts, vessels=vessels, appointments=appointments)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.active and user.check_password(password):
            login_user(user)
            flash("Welcome back.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have signed out.", "info")
    return redirect(url_for("login"))


@app.route("/vessels")
@login_required
def vessels():
    records = Vessel.query.order_by(Vessel.eta.asc()).all()
    return render_template("vessels.html", records=records)


@app.route("/vessels/new", methods=["GET", "POST"])
@roles_required("Administrator", "Port Operations Officer", "Terminal/Logistics Officer")
def vessel_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        eta = dt_local(request.form.get("eta"))
        if not name or not eta:
            flash("Vessel name and a valid expected arrival time are required.", "danger")
        else:
            vessel = Vessel(name=name, imo_number=request.form.get("imo_number", "").strip() or None,
                voyage_number=request.form.get("voyage_number", "").strip(), eta=eta,
                etd=dt_local(request.form.get("etd")), status=request.form.get("status", "Expected"),
                priority=request.form.get("priority", "Normal"),
                required_berth_hours=max(1, int(request.form.get("required_berth_hours", 8) or 8)),
                notes=request.form.get("notes", "").strip())
            db.session.add(vessel)
            try:
                db.session.commit()
                flash("Vessel record saved.", "success")
                return redirect(url_for("vessels"))
            except Exception:
                db.session.rollback()
                flash("Could not save this vessel. Check that the IMO number is unique.", "danger")
    return render_template("vessel_form.html", record=None)


@app.route("/vessels/<int:item_id>/status", methods=["POST"])
@roles_required("Administrator", "Port Operations Officer", "Terminal/Logistics Officer")
def vessel_status(item_id):
    item = db.get_or_404(Vessel, item_id)
    item.status = request.form.get("status", item.status)
    db.session.commit()
    flash("Vessel status updated.", "success")
    return redirect(url_for("vessels"))


@app.route("/containers")
@login_required
def containers():
    query = CargoContainer.query
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    if search:
        query = query.filter(CargoContainer.container_number.ilike(f"%{search}%"))
    if status:
        query = query.filter_by(status=status)
    records = query.order_by(CargoContainer.created_at.desc()).all()
    return render_template("containers.html", records=records, search=search, selected_status=status)


@app.route("/containers/new", methods=["GET", "POST"])
@roles_required("Administrator", "Cargo/Container Officer", "Terminal/Logistics Officer")
def container_new():
    vessel_options = Vessel.query.order_by(Vessel.eta.desc()).all()
    if request.method == "POST":
        number = request.form.get("container_number", "").strip().upper()
        description = request.form.get("cargo_description", "").strip()
        if not number or not description:
            flash("Container number and cargo description are required.", "danger")
        else:
            try:
                record = CargoContainer(container_number=number,
                    vessel_id=int(request.form["vessel_id"]) if request.form.get("vessel_id") else None,
                    cargo_description=description, container_type=request.form.get("container_type", "20ft"),
                    weight_tonnes=float(request.form.get("weight_tonnes", 0) or 0),
                    priority=request.form.get("priority", "Normal"), status=request.form.get("status", "At port"),
                    expected_collection=dt_local(request.form.get("expected_collection")))
                db.session.add(record)
                db.session.flush()
                db.session.add(ContainerMovement(container_id=record.id, movement_type="Registered",
                    to_location="Port system", notes="Container record created"))
                db.session.commit()
                flash("Container and cargo record saved.", "success")
                return redirect(url_for("containers"))
            except Exception:
                db.session.rollback()
                flash("Could not save container. Check the container number and numeric fields.", "danger")
    return render_template("container_form.html", vessels=vessel_options)


@app.route("/containers/<int:item_id>/status", methods=["POST"])
@roles_required("Administrator", "Cargo/Container Officer", "Terminal/Logistics Officer")
def container_status(item_id):
    item = db.get_or_404(CargoContainer, item_id)
    new_status = request.form.get("status", item.status)
    db.session.add(ContainerMovement(container_id=item.id, movement_type="Status changed",
        from_location=item.status, to_location=new_status, notes=f"Updated by {current_user.username}"))
    item.status = new_status
    db.session.commit()
    flash("Container status and movement history updated.", "success")
    return redirect(url_for("containers"))


@app.route("/containers/export.csv")
@login_required
def export_containers():
    records = CargoContainer.query.order_by(CargoContainer.created_at.desc()).all()
    rows = [{"container_number": c.container_number, "vessel": c.vessel.name if c.vessel else "",
        "cargo_description": c.cargo_description, "container_type": c.container_type,
        "weight_tonnes": c.weight_tonnes, "priority": c.priority, "status": c.status,
        "yard_location": c.yard_location.code if c.yard_location else ""} for c in records]
    output = pd.DataFrame(rows).to_csv(index=False)
    return Response(output, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=containers.csv"})


@app.route("/yard")
@login_required
def yard():
    locations = YardLocation.query.order_by(YardLocation.zone, YardLocation.code).all()
    return render_template("yard.html", locations=locations)


@app.route("/yard/allocate", methods=["POST"])
@roles_required("Administrator", "Cargo/Container Officer", "Terminal/Logistics Officer")
def yard_allocate():
    unallocated = CargoContainer.query.filter(CargoContainer.yard_location_id.is_(None)).filter(
        CargoContainer.status.notin_(["Released", "Departed"])).order_by(
        CargoContainer.priority.desc(), CargoContainer.created_at.asc()).all()
    locations = YardLocation.query.order_by(YardLocation.zone, YardLocation.code).all()
    assigned = 0
    for container in unallocated:
        candidate = next((loc for loc in locations if loc.available_slots > 0), None)
        if candidate:
            container.yard_location_id = candidate.id
            db.session.add(ContainerMovement(container_id=container.id, movement_type="Yard allocation",
                from_location="Unallocated", to_location=candidate.code,
                notes="Rule-based capacity recommendation accepted by user"))
            assigned += 1
    db.session.commit()
    flash(f"Allocated {assigned} container(s) to available yard slots. Review the results before operational use.", "success" if assigned else "warning")
    return redirect(url_for("yard"))


@app.route("/trucks")
@login_required
def trucks():
    truck_records = Truck.query.order_by(Truck.registration_number).all()
    appointments = TruckAppointment.query.order_by(TruckAppointment.appointment_time.desc()).limit(100).all()
    containers = CargoContainer.query.filter(CargoContainer.status.notin_(["Released", "Departed"])).all()
    return render_template("trucks.html", trucks=truck_records, appointments=appointments, containers=containers)


@app.route("/trucks/new", methods=["POST"])
@roles_required("Administrator", "Truck/Transport Officer")
def truck_new():
    reg = request.form.get("registration_number", "").strip().upper()
    if not reg:
        flash("Truck registration number is required.", "danger")
    else:
        db.session.add(Truck(registration_number=reg, company=request.form.get("company", "").strip(),
            driver_name=request.form.get("driver_name", "").strip(), phone=request.form.get("phone", "").strip()))
        try:
            db.session.commit()
            flash("Truck registered.", "success")
        except Exception:
            db.session.rollback()
            flash("Truck registration already exists or could not be saved.", "danger")
    return redirect(url_for("trucks"))


@app.route("/trucks/appointment", methods=["POST"])
@roles_required("Administrator", "Truck/Transport Officer", "Terminal/Logistics Officer")
def appointment_new():
    try:
        truck_id = int(request.form["truck_id"])
        appointment_time = dt_local(request.form.get("appointment_time"))
        if not appointment_time:
            raise ValueError("time")
        db.session.add(TruckAppointment(truck_id=truck_id,
            container_id=int(request.form["container_id"]) if request.form.get("container_id") else None,
            appointment_time=appointment_time, purpose=request.form.get("purpose", "Collection"),
            notes=request.form.get("notes", "").strip()))
        db.session.commit()
        flash("Truck appointment scheduled.", "success")
    except Exception:
        db.session.rollback()
        flash("Appointment could not be saved. Select a truck and a valid date/time.", "danger")
    return redirect(url_for("trucks"))


@app.route("/scheduling")
@login_required
def scheduling():
    all_vessels = Vessel.query.filter(Vessel.status.in_(["Expected", "Waiting"])).order_by(Vessel.eta.asc()).all()
    berths = Berth.query.filter_by(available=True).order_by(Berth.code).all()
    recommendations = []
    next_free = datetime.utcnow()
    for vessel in all_vessels:
        start = max(vessel.eta, next_free)
        duration = max(1, vessel.required_berth_hours)
        recommendations.append({"vessel": vessel, "start": start, "end": start + timedelta(hours=duration),
                                "reason": "Earliest feasible slot in this prototype sequence; verify berth suitability."})
        next_free = start + timedelta(hours=duration)
    return render_template("scheduling.html", recommendations=recommendations, berths=berths)


@app.route("/analytics")
@login_required
def analytics():
    movement_rows = db.session.query(
        func.date(ContainerMovement.recorded_at), func.count(ContainerMovement.id)
    ).group_by(func.date(ContainerMovement.recorded_at)).order_by(func.date(ContainerMovement.recorded_at)).all()
    labels = [str(row[0]) for row in movement_rows]
    values = [int(row[1]) for row in movement_rows]
    total = ContainerMovement.query.count()
    released = CargoContainer.query.filter_by(status="Released").count() + CargoContainer.query.filter_by(status="Departed").count()
    flow_estimate = round(total / max(1, len(labels)), 2) if labels else 0
    return render_template("analytics.html", labels=labels, values=values, total=total,
        released=released, flow_estimate=flow_estimate)


@app.route("/alerts")
@login_required
def alerts():
    records = Alert.query.order_by(Alert.resolved.asc(), Alert.created_at.desc()).all()
    return render_template("alerts.html", records=records)


@app.route("/alerts/<int:item_id>/resolve", methods=["POST"])
@roles_required("Administrator", "Port Operations Officer", "Terminal/Logistics Officer")
def alert_resolve(item_id):
    item = db.get_or_404(Alert, item_id)
    item.resolved = True
    db.session.commit()
    flash("Alert marked as resolved.", "success")
    return redirect(url_for("alerts"))


@app.route("/admin/users", methods=["GET", "POST"])
@roles_required("Administrator")
def users_admin():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "Management")
        if not username or len(password) < 10 or role not in ROLES:
            flash("Enter a username, a password of at least 10 characters, and a valid role.", "danger")
        elif User.query.filter_by(username=username).first():
            flash("That username already exists.", "danger")
        else:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("User account created.", "success")
            return redirect(url_for("users_admin"))
    return render_template("users.html", records=User.query.order_by(User.username).all())


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="Your role does not have permission to perform this action."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The requested page or record could not be found."), 404


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
