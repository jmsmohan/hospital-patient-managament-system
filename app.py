from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
import os
import logging
import sqlalchemy.exc

app = Flask(__name__)
app.secret_key = "hospital_secret"  # Consistent with your original secret key

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Use DATABASE_URL environment variable (for Render deployment)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///patient.db'  # fallback for local development
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ======================= Database Models ==========================
class Patient(db.Model):
    __tablename__ = 'patients'
    vhid = db.Column(db.String, primary_key=True)
    date = db.Column(db.String)
    name = db.Column(db.String, nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String)
    address = db.Column(db.String)
    ref_by = db.Column(db.String)
    mobile = db.Column(db.String)
    past_history = db.Column(db.String)
    drug_history = db.Column(db.String)
    surgical_history = db.Column(db.String)
    visits = db.relationship('Visit', backref='patient', lazy=True)

class Visit(db.Model):
    __tablename__ = 'visits'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    vhid = db.Column(db.String, db.ForeignKey('patients.vhid'), nullable=False)
    date = db.Column(db.String)
    ref_by = db.Column(db.String)
    complaints = db.Column(db.String)
    past_history = db.Column(db.String)
    drug_history = db.Column(db.String)
    surgical_history = db.Column(db.String)
    vitals = db.Column(db.String)
    examination = db.Column(db.String)
    prov_diagnosis = db.Column(db.String)
    invgs = db.Column(db.String)
    impression = db.Column(db.String)
    treatment = db.Column(db.String)
    next_review = db.Column(db.String)
    imp = db.Column(db.String)
    oe = db.Column(db.String)

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()

# ======================= Routes ====================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add", methods=["GET", "POST"])
def add_patient():
    if request.method == "POST":
        vhid = request.form.get('vhid', '').strip().upper()
        date = request.form.get('date', '').strip()
        name = request.form.get('name', '').strip()
        age = request.form.get('age') or None
        gender = request.form.get('gender')
        addr = request.form.get('address', '').strip()
        ref_by = request.form.get('referred', '').strip()
        mob = request.form.get('mobile', '').strip()
        past = request.form.get('past_history', '').strip()
        drug = request.form.get('drug_history', '').strip()
        surg = request.form.get('surgical_history', '').strip()

        if not vhid or not name:
            flash("VHID and Name are required", "danger")
            return redirect(url_for('add_patient'))

        try:
            patient = Patient(
                vhid=vhid, date=date, name=name, age=age, gender=gender, address=addr,
                ref_by=ref_by, mobile=mob, past_history=past, drug_history=drug, surgical_history=surg
            )
            db.session.add(patient)
            db.session.commit()
            flash("Patient added successfully!", "success")
            return redirect(url_for('retrieve_patient', vhid=vhid))
        except sqlalchemy.exc.IntegrityError as e:
            db.session.rollback()
            flash("VHID already exists!", "danger")
            return redirect(url_for('add_patient'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding patient: {str(e)}", "danger")
            return redirect(url_for('add_patient'))
    return render_template("add.html")

@app.route("/retrieve", methods=["GET", "POST"])
def retrieve_patient():
    patient = None
    visits = []
    vhid = (request.form.get("vhid") if request.method == "POST" else request.args.get("vhid") or '').strip().upper()

    if vhid:
        try:
            patient = Patient.query.filter_by(vhid=vhid).first()
            if patient:
                visits = Visit.query.filter_by(vhid=vhid).order_by(Visit.date.desc(), Visit.id.desc()).all()
                flash(f"Patient record retrieved for VHID: {vhid}", "success")
            else:
                flash(f"No record found for VHID: {vhid}", "danger")
        except Exception as e:
            flash(f"Error retrieving patient: {str(e)}", "danger")

    return render_template("retrieve.html", patient=patient, visits=visits)

@app.route("/edit_patient/<vhid>", methods=["POST"])
def edit_patient(vhid):
    logger.debug(f"Received edit request for VHID: {vhid}")
    logger.debug(f"Form data: {request.form}")

    try:
        date = request.form.get('date', '').strip()
        name = request.form.get('name', '').strip()
        age = request.form.get('age') or None
        gender = request.form.get('gender', '').strip()
        address = request.form.get('address', '').strip()
        ref_by = request.form.get('ref_by', '').strip()
        mobile = request.form.get('mobile', '').strip()
        past_history = request.form.get('past_history', '').strip()
        drug_history = request.form.get('drug_history', '').strip()
        surgical_history = request.form.get('surgical_history', '').strip()

        errors = []
        if not name:
            errors.append("Name is required")
        if not date:
            errors.append("Date is required")
        if not gender:
            errors.append("Gender is required")
        if mobile and not mobile.isdigit():
            errors.append("Mobile number must contain only digits")
        if age and (not age.isdigit() or int(age) < 0 or int(age) > 150):
            errors.append("Age must be a number between 0 and 150")

        if errors:
            for error in errors:
                flash(error, "danger")
            logger.debug(f"Validation errors: {errors}")
            return redirect(url_for('retrieve_patient', vhid=vhid))

        patient = Patient.query.filter_by(vhid=vhid).first()
        if not patient:
            flash("Patient not found", "danger")
            return redirect(url_for('retrieve_patient', vhid=vhid))

        patient.date = date
        patient.name = name
        patient.age = age
        patient.gender = gender
        patient.address = address
        patient.ref_by = ref_by
        patient.mobile = mobile
        patient.past_history = past_history
        patient.drug_history = drug_history
        patient.surgical_history = surgical_history

        db.session.commit()
        logger.debug(f"Updated patient with VHID: {vhid}")
        flash("Patient details updated successfully!", "success")
        return redirect(url_for('retrieve_patient', vhid=vhid))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating patient: {str(e)}")
        flash(f"Error updating patient: {str(e)}", "danger")
        return redirect(url_for('retrieve_patient', vhid=vhid))

@app.route("/add_visit/<vhid>", methods=["POST"])
def add_visit(vhid):
    try:
        date = request.form.get('date', '').strip()
        vitals = request.form.get('vitals', '').strip()
        complaints = request.form.get('complaints', '').strip()
        oe = request.form.get('oe', '').strip()
        imp = request.form.get('imp', '').strip()
        invgs = request.form.get('invgs', '').strip()
        treatment = request.form.get('treatment', '').strip()
        ref_by = request.form.get('ref_by', '').strip()
        past_history = request.form.get('past_history', '').strip()
        drug_history = request.form.get('drug_history', '').strip()
        surgical_history = request.form.get('surgical_history', '').strip()
        examination = request.form.get('examination', '').strip()
        prov_diagnosis = request.form.get('prov_diagnosis', '').strip()
        impression = request.form.get('impression', '').strip()
        next_review = request.form.get('next_review', '').strip()

        visit = Visit(
            vhid=vhid, date=date, ref_by=ref_by, complaints=complaints, past_history=past_history,
            drug_history=drug_history, surgical_history=surgical_history, vitals=vitals,
            examination=examination, prov_diagnosis=prov_diagnosis, invgs=invgs,
            impression=impression, treatment=treatment, next_review=next_review, imp=imp, oe=oe
        )
        db.session.add(visit)
        db.session.commit()
        flash("Visit added successfully!", "success")
        return redirect(url_for('retrieve_patient', vhid=vhid))
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding visit: {str(e)}", "danger")
        return redirect(url_for('retrieve_patient', vhid=vhid))

@app.route("/edit_visit/<int:visit_id>", methods=["POST"])
def edit_visit(visit_id):
    logger.debug(f"Received edit request for visit ID: {visit_id}")
    logger.debug(f"Form data: {request.form}")

    try:
        date = request.form.get('date', '').strip()
        complaints = request.form.get('complaints', '').strip()
        vitals = request.form.get('vitals', '').strip()
        invgs = request.form.get('invgs', '').strip()
        imp = request.form.get('imp', '').strip()
        oe = request.form.get('oe', '').strip()
        treatment = request.form.get('treatment', '').strip()
        ref_by = request.form.get('ref_by', '').strip()
        past_history = request.form.get('past_history', '').strip()
        drug_history = request.form.get('drug_history', '').strip()
        surgical_history = request.form.get('surgical_history', '').strip()
        examination = request.form.get('examination', '').strip()
        prov_diagnosis = request.form.get('prov_diagnosis', '').strip()
        impression = request.form.get('impression', '').strip()
        next_review = request.form.get('next_review', '').strip()

        errors = []
        if not date:
            errors.append("Date is required")
        if not complaints:
            errors.append("Complaints are required")

        if errors:
            for error in errors:
                flash(error, "danger")
            logger.debug(f"Validation errors: {errors}")
            return redirect(url_for('retrieve_patient', vhid=request.form.get('vhid')))

        visit = Visit.query.get(visit_id)
        if not visit:
            flash("Visit not found", "danger")
            return redirect(url_for('retrieve_patient', vhid=request.form.get('vhid')))

        visit.date = date
        visit.ref_by = ref_by
        visit.complaints = complaints
        visit.past_history = past_history
        visit.drug_history = drug_history
        visit.surgical_history = surgical_history
        visit.vitals = vitals
        visit.examination = examination
        visit.prov_diagnosis = prov_diagnosis
        visit.invgs = invgs
        visit.impression = impression
        visit.treatment = treatment
        visit.next_review = next_review
        visit.imp = imp
        visit.oe = oe

        db.session.commit()
        logger.debug(f"Updated visit with ID: {visit_id}")
        flash("Visit details updated successfully!", "success")
        return redirect(url_for('retrieve_patient', vhid=visit.vhid))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating visit: {str(e)}")
        flash(f"Error updating visit: {str(e)}", "danger")
        return redirect(url_for('retrieve_patient', vhid=request.form.get('vhid')))

@app.route("/get_visit/<int:visit_id>", methods=["GET"])
def get_visit(visit_id):
    try:
        visit = Visit.query.get(visit_id)
        if visit:
            return jsonify({
                'id': visit.id, 'vhid': visit.vhid, 'date': visit.date, 'ref_by': visit.ref_by,
                'complaints': visit.complaints, 'past_history': visit.past_history,
                'drug_history': visit.drug_history, 'surgical_history': visit.surgical_history,
                'vitals': visit.vitals, 'examination': visit.examination,
                'prov_diagnosis': visit.prov_diagnosis, 'invgs': visit.invgs,
                'impression': visit.impression, 'treatment': visit.treatment,
                'next_review': visit.next_review, 'imp': visit.imp, 'oe': visit.oe
            })
        else:
            return jsonify({"error": "Visit not found"}), 404
    except Exception as e:
        logger.error(f"Error retrieving visit: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/stats")
def statistics():
    try:
        patient_count = Patient.query.count()
        visit_count = Visit.query.count()
        stats = {
            'patient_count': patient_count,
            'visit_count': visit_count,
            'db_size_mb': 'N/A'  # Cloud DB size not directly accessible
        }
        return render_template("stats.html", stats=stats)
    except Exception as e:
        flash(f"Error retrieving statistics: {str(e)}", "danger")
        return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)