import os
import re
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "petadopt_secret_2026_key"

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pet_adoption.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB Limit

db = SQLAlchemy(app)

# --- INTERACTIVE SQL MODELS ---
class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    breed = db.Column(db.String(50))
    photo = db.Column(db.String(200))
    medical_history = db.Column(db.Text, default="Healthy, vaccinated, and ready for a home.")
    status = db.Column(db.String(20), default="Available")
    # Relationship: One pet can have many adoption requests
    requests = db.relationship('AdoptionRequest', backref='pet', cascade="all, delete", lazy=True)

class AdoptionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pet.id'), nullable=False)
    adopter_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    id_proof = db.Column(db.String(200))

# Initialize Database
with app.app_context():
    db.create_all()

# --- UTILS ---
def is_authentic_email(email):
    # Validates standard email structure (e.g., name@domain.com)
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)

# --- USER ROUTES ---

@app.route('/')
def index():
    # Only show pets that are available for adoption
    pets = Pet.query.filter_by(status="Available").all()
    return render_template('index.html', pets=pets)

@app.route('/adopt/<int:pet_id>', methods=['GET', 'POST'])
def adopt(pet_id):
    # Fetch the pet object to show its info (Name, Photo, Medical History) in the form
    pet = Pet.query.get_or_404(pet_id)

    if request.method == 'POST':
        email = request.form['email']
        
        # 1. Authentic Email Check
        if not is_authentic_email(email):
            flash("Invalid email! Please use an authentic address like @gmail.com.", "danger")
            return redirect(url_for('adopt', pet_id=pet_id))

        # 2. File Upload Handling
        file = request.files.get('id_proof')
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # 3. Save Request to SQL Database
            new_req = AdoptionRequest(
                pet_id=pet.id,
                adopter_name=request.form['name'],
                email=email,
                id_proof=filename
            )
            db.session.add(new_req)
            db.session.commit()
            flash(f"Application for {pet.name} submitted! We will review your ID.", "success")
            return redirect(url_for('index'))

    return render_template('adopt.html', pet=pet)

# --- ADMIN ROUTES ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        # Default credentials
        if request.form['username'] == "admin" and request.form['password'] == "password123":
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials!", "danger")
    return render_template('admin.html', login_mode=True)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('logged_in'): 
        return redirect(url_for('admin_login'))
    
    all_pets = Pet.query.all()
    all_requests = AdoptionRequest.query.all()
    return render_template('admin.html', pets=all_pets, requests=all_requests, login_mode=False)

@app.route('/admin/add_pet', methods=['POST'])
def add_pet():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    
    file = request.files.get('photo')
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_pet = Pet(
            name=request.form['name'],
            breed=request.form['breed'],
            medical_history=request.form['medical'],
            photo=filename
        )
        db.session.add(new_pet)
        db.session.commit()
        flash("New pet added to the gallery!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve/<int:req_id>')
def approve(req_id):
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    
    req = AdoptionRequest.query.get(req_id)
    if req:
        # Interactive DB update: Mark the specific pet as adopted
        pet = Pet.query.get(req.pet_id)
        if pet:
            pet.status = "Adopted"
        
        # Remove the request after approval
        db.session.delete(req)
        db.session.commit()
        flash("Adoption approved!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    app.run(debug=True)