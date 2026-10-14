from datetime import datetime, timedelta
from app import app, db, User, Vessel, Berth, CargoContainer, YardLocation, Truck, TruckAppointment, ContainerMovement, Alert

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="Administrator")
        admin.set_password("PortDemo2026!")
        db.session.add(admin)

    if Berth.query.count() == 0:
        db.session.add_all([
            Berth(code="B-01", description="Main berth - demo record", max_vessel_length_m=300),
            Berth(code="B-02", description="Secondary berth - demo record", max_vessel_length_m=250),
            Berth(code="B-03", description="Flexible berth - demo record", max_vessel_length_m=220),
        ])

    if YardLocation.query.count() == 0:
        db.session.add_all([
            YardLocation(code="A-01", zone="Zone A", capacity=30, notes="General cargo"),
            YardLocation(code="A-02", zone="Zone A", capacity=25, notes="General cargo"),
            YardLocation(code="B-01", zone="Zone B", capacity=20, notes="Priority cargo"),
            YardLocation(code="C-01", zone="Zone C", capacity=15, notes="Overflow area"),
        ])

    if Vessel.query.count() == 0:
        now = datetime.utcnow()
        vessels = [
            Vessel(name="MV Atlantic Hope", imo_number="DEMO-IMO-1001", voyage_number="AH-026",
                   eta=now + timedelta(hours=3), status="Expected", priority="High", required_berth_hours=7),
            Vessel(name="MV Sierra Star", imo_number="DEMO-IMO-1002", voyage_number="SS-114",
                   eta=now + timedelta(hours=8), status="Waiting", priority="Normal", required_berth_hours=9),
            Vessel(name="MV Coastal Trader", imo_number="DEMO-IMO-1003", voyage_number="CT-008",
                   eta=now + timedelta(days=1), status="Expected", priority="Normal", required_berth_hours=5),
        ]
        db.session.add_all(vessels)
        db.session.flush()

    if CargoContainer.query.count() == 0:
        vessel_list = Vessel.query.order_by(Vessel.id).all()
        containers = [
            CargoContainer(container_number="SLPU1000001", vessel_id=vessel_list[0].id,
                cargo_description="Packaged food products", container_type="20ft", weight_tonnes=12.5,
                priority="High", status="At port", expected_collection=datetime.utcnow()+timedelta(hours=12)),
            CargoContainer(container_number="SLPU1000002", vessel_id=vessel_list[0].id,
                cargo_description="Building materials", container_type="40ft", weight_tonnes=22,
                priority="Normal", status="At port"),
            CargoContainer(container_number="SLPU1000003", vessel_id=vessel_list[1].id,
                cargo_description="Medical supplies - demo", container_type="20ft", weight_tonnes=8,
                priority="Urgent", status="Discharged"),
            CargoContainer(container_number="SLPU1000004", vessel_id=vessel_list[2].id,
                cargo_description="Household goods", container_type="40ft", weight_tonnes=19,
                priority="Normal", status="In transit"),
        ]
        db.session.add_all(containers)
        db.session.flush()
        db.session.add_all([
            ContainerMovement(container_id=containers[0].id, movement_type="Discharged", from_location="Vessel", to_location="Port yard"),
            ContainerMovement(container_id=containers[1].id, movement_type="Registered", from_location="", to_location="Port system"),
            ContainerMovement(container_id=containers[2].id, movement_type="Priority cargo noted", from_location="Vessel", to_location="Port yard"),
            ContainerMovement(container_id=containers[3].id, movement_type="Gate-out", from_location="Port gate", to_location="Inland transport"),
        ])

    if Truck.query.count() == 0:
        trucks = [
            Truck(registration_number="AFB-204", company="Demo Haulage Ltd", driver_name="Demo Driver A", phone="000-000"),
            Truck(registration_number="AFB-318", company="Coastal Transport", driver_name="Demo Driver B", phone="000-001"),
        ]
        db.session.add_all(trucks)
        db.session.flush()
        container = CargoContainer.query.first()
        db.session.add(TruckAppointment(truck_id=trucks[0].id, container_id=container.id,
            appointment_time=datetime.utcnow()+timedelta(hours=5), purpose="Collection", status="Scheduled"))
        db.session.add(TruckAppointment(truck_id=trucks[1].id, appointment_time=datetime.utcnow()+timedelta(hours=8),
            purpose="Delivery", status="Scheduled"))

    if Alert.query.count() == 0:
        db.session.add_all([
            Alert(severity="Warning", title="Review upcoming vessel sequence",
                  message="Two demo vessel calls are close together. Review berth availability before confirming a schedule."),
            Alert(severity="Information", title="Demo data loaded",
                  message="These sample records are fictional and are intended for testing only."),
            Alert(severity="Critical", title="Confirm priority cargo handling",
                  message="A demo container is marked urgent. Verify cargo documentation and handling requirements before operational decisions."),
        ])

    db.session.commit()
    print("Demo data ready.")
    print("Login: admin")
    print("Password: PortDemo2026!")
