from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFProtect
import sqlite3
import os
from werkzeug.utils import secure_filename
from docx import Document
import logging

app = Flask(__name__)
app.secret_key = "hospital_secret"
csrf = CSRFProtect(app)
DB_NAME = "patient.db"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ======================= File Upload Config =======================
UPLOAD_FOLDER = 'Uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'docx'}

# ======================= Database Init ============================
def init_db():
    with sqlite3.connect(DB_NAME) as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                vhid TEXT PRIMARY KEY,
                date TEXT,
                name TEXT,
                age INTEGER,
                gender TEXT,
                address TEXT,
                ref_by TEXT,
                mobile TEXT,
                past_history TEXT,
                drug_history TEXT,
                surgical_history TEXT
            );
        ''')
        con.execute('''
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vhid TEXT,
                date TEXT,
                ref_by TEXT,
                complaints TEXT,
                past_history TEXT,
                drug_history TEXT,
                surgical_history TEXT,
                vitals TEXT,
                examination TEXT,
                prov_diagnosis TEXT,
                invgs TEXT,
                impression TEXT,
                treatment TEXT,
                next_review TEXT,
                imp TEXT,
                oe TEXT,
                FOREIGN KEY(vhid) REFERENCES patients(vhid)
            );
        ''')
        con.execute('CREATE INDEX IF NOT EXISTS idx_visits_vhid ON visits(vhid)')
        con.execute('CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(date)')
        cursor = con.cursor()
        cursor.execute("PRAGMA table_info(patients)")
        columns = [info[1] for info in cursor.fetchall()]
        for col in ['date', 'ref_by', 'past_history', 'drug_history', 'surgical_history']:
            if col not in columns:
                cursor.execute(f"ALTER TABLE patients ADD {col} TEXT")
        con.commit()

# ======================= Utils =====================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_word_doc(filepath):
    doc = Document(filepath)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    patients, current = [], {}
    for line in lines:
        if line.lower().startswith("patient"):
            if current:
                patients.append(current)
                current = {}
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current[key.strip().lower().replace(" ", "_")] = value.strip()
    if current:
        patients.append(current)
    return patients

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
            with sqlite3.connect(DB_NAME) as con:
                con.execute('''
                    INSERT INTO patients (vhid, date, name, age, gender, address, ref_by, mobile,
                    past_history, drug_history, surgical_history)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (vhid, date, name, age, gender, addr, ref_by, mob, past, drug, surg))
                con.commit()
            flash("Patient added successfully!", "success")
            return redirect(url_for('retrieve_patient', vhid=vhid))
        except sqlite3.IntegrityError:
            flash("VHID already exists!", "danger")
            return redirect(url_for('add_patient'))
        except Exception as e:
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
            with sqlite3.connect(DB_NAME) as con:
                con.row_factory = sqlite3.Row
                c = con.cursor()
                c.execute("SELECT * FROM patients WHERE vhid = ?", (vhid,))
                patient = c.fetchone()
                c.execute("SELECT * FROM visits WHERE vhid = ? ORDER BY date DESC, id DESC", (vhid,))
                visits = c.fetchall()

            if not patient:
                flash(f"No record found for VHID: {vhid}", "danger")
            else:
                flash(f"Patient record retrieved for VHID: {vhid}", "success")
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

        with sqlite3.connect(DB_NAME) as con:
            cursor = con.cursor()
            cursor.execute('''
                UPDATE patients 
                SET date = ?, name = ?, age = ?, gender = ?, address = ?, ref_by = ?, mobile = ?, 
                    past_history = ?, drug_history = ?, surgical_history = ?
                WHERE vhid = ?
            ''', (date, name, age, gender, address, ref_by, mobile, past_history, drug_history, surgical_history, vhid))
            con.commit()
            logger.debug(f"Updated patient with VHID: {vhid}")

        flash("Patient details updated successfully!", "success")
        return redirect(url_for('retrieve_patient', vhid=vhid))
    except Exception as e:
        logger.error(f"Error updating patient: {str(e)}")
        flash(f"Error updating patient: {str(e)}", "danger")
        return redirect(url_for('retrieve_patient', vhid=vhid))

@app.route("/add_visit/<vhid>", methods=["POST"])
def add_visit(vhid):
    try:
        # Retrieve form data in the specified order
        date = request.form.get('date', '').strip()
        vitals = request.form.get('vitals', '').strip()
        complaints = request.form.get('complaints', '').strip()
        oe = request.form.get('oe', '').strip()
        imp = request.form.get('imp', '').strip()
        invgs = request.form.get('invgs', '').strip()
        treatment = request.form.get('treatment', '').strip()
        ref_by = request.form.get('ref_by', '').strip()
        examination = request.form.get('examination', '').strip()
        prov_diagnosis = request.form.get('prov_diagnosis', '').strip()
        impression = request.form.get('impression', '').strip()
        next_review = request.form.get('next_review', '').strip()
        past_history = request.form.get('past_history', '').strip()
        drug_history = request.form.get('drug_history', '').strip()
        surgical_history = request.form.get('surgical_history', '').strip()

        # Validate required fields
        errors = []
        if not date:
            errors.append("Date is required")
        if not complaints:
            errors.append("Complaints are required")
        if errors:
            for error in errors:
                flash(error, "danger")
            return redirect(url_for('retrieve_patient', vhid=vhid))

        # Insert data into visits table
        with sqlite3.connect(DB_NAME) as con:
            con.execute('''
                INSERT INTO visits (
                    vhid, date, vitals, complaints, oe, imp, invgs, treatment,
                    ref_by, examination, prov_diagnosis, impression, next_review,
                    past_history, drug_history, surgical_history
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                vhid, date, vitals, complaints, oe, imp, invgs, treatment,
                ref_by, examination, prov_diagnosis, impression, next_review,
                past_history, drug_history, surgical_history
            ))
            con.commit()

        flash("Visit added successfully!", "success")
        return redirect(url_for('retrieve_patient', vhid=vhid))
    except Exception as e:
        logger.error(f"Error adding visit: {str(e)}")
        flash(f"Error adding visit: {str(e)}", "danger")
        return redirect(url_for('retrieve_patient', vhid=vhid))

@app.route("/edit_visit/<int:visit_id>", methods=["POST"])
def edit_visit(visit_id):
    logger.debug(f"Received edit request for visit ID: {visit_id}")
    logger.debug(f"Form data: {request.form}")

    try:
        date = request.form.get('date', '').strip()
        vitals = request.form.get('vitals', '').strip()
        complaints = request.form.get('complaints', '').strip()
        oe = request.form.get('oe', '').strip()
        imp = request.form.get('imp', '').strip()
        invgs = request.form.get('invgs', '').strip()
        treatment = request.form.get('treatment', '').strip()
        ref_by = request.form.get('ref_by', '').strip()
        examination = request.form.get('examination', '').strip()
        prov_diagnosis = request.form.get('prov_diagnosis', '').strip()
        impression = request.form.get('impression', '').strip()
        next_review = request.form.get('next_review', '').strip()
        past_history = request.form.get('past_history', '').strip()
        drug_history = request.form.get('drug_history', '').strip()
        surgical_history = request.form.get('surgical_history', '').strip()

        errors = []
        if not date:
            errors.append("Date is required")
        if not complaints:
            errors.append("Complaints are required")
        if errors:
            for error in errors:
                flash(error, "danger")
            logger.debug(f"Validation errors: {errors}")
            cursor = sqlite3.connect(DB_NAME).cursor()
            cursor.execute("SELECT vhid FROM visits WHERE id = ?", (visit_id,))
            vhid = cursor.fetchone()[0]
            return redirect(url_for('retrieve_patient', vhid=vhid))

        with sqlite3.connect(DB_NAME) as con:
            cursor = con.cursor()
            cursor.execute('''
                UPDATE visits 
                SET date = ?, vitals = ?, complaints = ?, oe = ?, imp = ?, invgs = ?, treatment = ?,
                    ref_by = ?, examination = ?, prov_diagnosis = ?, impression = ?, next_review = ?,
                    past_history = ?, drug_history = ?, surgical_history = ?
                WHERE id = ?
            ''', (
                date, vitals, complaints, oe, imp, invgs, treatment,
                ref_by, examination, prov_diagnosis, impression, next_review,
                past_history, drug_history, surgical_history, visit_id
            ))
            con.commit()
            logger.debug(f"Updated visit with ID: {visit_id}")

        cursor.execute("SELECT vhid FROM visits WHERE id = ?", (visit_id,))
        vhid = cursor.fetchone()[0]
        flash("Visit details updated successfully!", "success")
        return redirect(url_for('retrieve_patient', vhid=vhid))
    except Exception as e:
        logger.error(f"Error updating visit: {str(e)}")
        flash(f"Error updating visit: {str(e)}", "danger")
        cursor = sqlite3.connect(DB_NAME).cursor()
        cursor.execute("SELECT vhid FROM visits WHERE id = ?", (visit_id,))
        vhid = cursor.fetchone()[0] if cursor.fetchone() else request.form.get('vhid', '')
        return redirect(url_for('retrieve_patient', vhid=vhid))

@app.route("/get_visit/<int:visit_id>", methods=["GET"])
def get_visit(visit_id):
    try:
        with sqlite3.connect(DB_NAME) as con:
            con.row_factory = sqlite3.Row
            cursor = con.cursor()
            cursor.execute("SELECT * FROM visits WHERE id = ?", (visit_id,))
            visit = cursor.fetchone()
            if visit:
                return jsonify(dict(visit))
            else:
                return jsonify({"error": "Visit not found"}), 404
    except Exception as e:
        logger.error(f"Error retrieving visit: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files.get('file')
        if not file or file.filename == '':
            flash("No file selected", "danger")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(filepath)
            try:
                patients = parse_word_doc(filepath)
                with sqlite3.connect(DB_NAME) as con:
                    c = con.cursor()
                    for data in patients:
                        vhid = data.get("vhid", "").strip().upper()
                        if not vhid:
                            continue
                        c.execute("SELECT vhid FROM patients WHERE vhid = ?", (vhid,))
                        if not c.fetchone():
                            c.execute('''
                                INSERT INTO patients (vhid, date, name, age, gender, address, ref_by, mobile,
                                    past_history, drug_history, surgical_history)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (vhid, data.get("date", ""), data.get("name", ""), data.get("age", ""),
                                  data.get("gender", ""), data.get("address", ""), data.get("ref_by", ""),
                                  data.get("mobile", ""), data.get("past_history", ""), data.get("drug_history", ""),
                                  data.get("surgical_history", "")))
                    con.commit()
                flash("Patient(s) uploaded successfully!", "success")
                return redirect(url_for('index'))
            except Exception as e:
                flash(f"Error processing file: {str(e)}", "danger")
                return redirect(request.url)
        else:
            flash("Invalid file type. Only .docx allowed", "danger")
            return redirect(request.url)
    return render_template("upload.html")

@app.route("/stats")
def statistics():
    try:
        with sqlite3.connect(DB_NAME) as con:
            c = con.cursor()
            c.execute("SELECT COUNT(*) FROM patients")
            patient_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM visits")
            visit_count = c.fetchone()[0]
            db_size = os.path.getsize(DB_NAME) / (1024 * 1024)
            stats = {
                'patient_count': patient_count,
                'visit_count': visit_count,
                'db_size_mb': round(db_size, 2)
            }
        return render_template("stats.html", stats=stats)
    except Exception as e:
        flash(f"Error retrieving statistics: {str(e)}", "danger")
        return redirect(url_for('index'))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)