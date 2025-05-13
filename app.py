from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import Database, CursorFromConnectionPool
import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Initialize database connection
Database.initialize()

# Helper functions
def create_blood_bank_entry(blood_type, quantity_ml, donor_id):
    collection_date = datetime.date.today()
    expiry_date = collection_date + datetime.timedelta(days=42)  # Blood typically expires in 42 days
    
    with CursorFromConnectionPool() as cursor:
        cursor.execute(
            "INSERT INTO blood_bank (blood_type, quantity_ml, donor_id, collection_date, expiry_date) VALUES (?, ?, ?, ?, ?)",
            (blood_type, quantity_ml, donor_id, collection_date, expiry_date)
        )

def can_donor_donate(donor_id):
    """Check if donor is eligible to donate based on last donation date"""
    with CursorFromConnectionPool() as cursor:
        cursor.execute("SELECT last_donation_date FROM donors WHERE id = ?", (donor_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            last_donation_date = datetime.datetime.strptime(result[0], '%Y-%m-%d').date()
            days_since_donation = (datetime.date.today() - last_donation_date).days
            return days_since_donation >= 60
        
        return True  # If no previous donation or date is null

def can_recipient_request(recipient_id):
    """Check if recipient is eligible to request based on last request date"""
    with CursorFromConnectionPool() as cursor:
        cursor.execute("SELECT last_request_date FROM recipients WHERE id = ?", (recipient_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            last_request_date = datetime.datetime.strptime(result[0], '%Y-%m-%d').date()
            days_since_request = (datetime.date.today() - last_request_date).days
            return days_since_request >= 40
        
        return True  # If no previous request or date is null

def is_blood_available(blood_type, quantity_requested):
    """Check if requested blood type and quantity is available"""
    with CursorFromConnectionPool() as cursor:
        cursor.execute("""
            SELECT SUM(quantity_ml) as total_quantity 
            FROM blood_bank 
            WHERE blood_type = ? AND expiry_date > ?
            GROUP BY blood_type
        """, (blood_type, datetime.date.today()))
        
        result = cursor.fetchone()
        
        if result and result[0] >= int(quantity_requested):
            return True
        
        return False

def fulfill_blood_request(blood_type, quantity_requested):
    """Subtract the requested blood quantity from available blood"""
    with CursorFromConnectionPool() as cursor:
        # Get blood entries starting with oldest first (FIFO)
        cursor.execute("""
            SELECT id, quantity_ml 
            FROM blood_bank 
            WHERE blood_type = ? AND expiry_date > ? 
            ORDER BY collection_date ASC
        """, (blood_type, datetime.date.today()))
        
        blood_entries = cursor.fetchall()
        remaining_quantity = int(quantity_requested)
        
        # Process each entry until request is fulfilled
        for entry_id, entry_quantity in blood_entries:
            if remaining_quantity <= entry_quantity:
                # This entry has enough to fulfill remaining request
                new_quantity = entry_quantity - remaining_quantity
                if new_quantity == 0:
                    # Remove entry if fully used
                    cursor.execute("DELETE FROM blood_bank WHERE id = ?", (entry_id,))
                else:
                    # Update entry with reduced quantity
                    cursor.execute("UPDATE blood_bank SET quantity_ml = ? WHERE id = ?", 
                                 (new_quantity, entry_id))
                break
            else:
                # Use entire entry and continue to next
                cursor.execute("DELETE FROM blood_bank WHERE id = ?", (entry_id,))
                remaining_quantity -= entry_quantity

# Routes
@app.route('/')
def home():
    return render_template('home.html', now=datetime.datetime.now())

# Donor routes
@app.route('/donor/register', methods=['GET', 'POST'])
def donor_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        blood_type = request.form['blood_type']
        phone = request.form['phone']
        address = request.form['address']
        
        hashed_password = generate_password_hash(password)
        
        try:
            with CursorFromConnectionPool() as cursor:
                cursor.execute(
                    "INSERT INTO donors (name, email, password, blood_type, phone, address) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, email, hashed_password, blood_type, phone, address)
                )
                # Get the last inserted row id
                cursor.execute("SELECT last_insert_rowid()")
                donor_id = cursor.fetchone()[0]
                print(f"Successfully registered donor with ID: {donor_id}")
            
            flash('Registration successful! Please login.')
            return redirect(url_for('donor_login'))
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: donors.email" in str(e):
                flash('Email address already registered.')
            else:
                flash(f'An error occurred: {str(e)}')
        except Exception as e:
            flash(f'An error occurred: {str(e)}')
    
    return render_template('donor_register.html', now=datetime.datetime.now())

@app.route('/donor/login', methods=['GET', 'POST'])
def donor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            with CursorFromConnectionPool() as cursor:
                cursor.execute("SELECT id, name, password FROM donors WHERE email = ?", (email,))
                donor = cursor.fetchone()
                
                if donor:
                    # Access using index since we're using fetchone()
                    donor_id = donor[0]
                    donor_name = donor[1]
                    stored_password = donor[2]
                    
                    if check_password_hash(stored_password, password):
                        session['donor_id'] = donor_id
                        session['donor_name'] = donor_name
                        flash(f'Welcome back, {donor_name}!')
                        return redirect(url_for('donor_dashboard'))
                    else:
                        flash('Invalid email or password')
                else:
                    flash('Invalid email or password')
        except Exception as e:
            flash(f'Login error: {str(e)}')
    
    return render_template('donor_login.html', now=datetime.datetime.now())

@app.route('/donor/dashboard')
def donor_dashboard():
    if 'donor_id' not in session:
        flash('Please login first')
        return redirect(url_for('donor_login'))
    
    donor_id = session['donor_id']
    
    with CursorFromConnectionPool() as cursor:
        # Get donor details
        cursor.execute("SELECT * FROM donors WHERE id = ?", (donor_id,))
        donor = cursor.fetchone()
        
        # Get donation history
        cursor.execute("SELECT * FROM blood_bank WHERE donor_id = ? ORDER BY collection_date DESC", (donor_id,))
        donations = cursor.fetchall()
    
    # Check if donor can donate again
    can_donate = can_donor_donate(donor_id)
    next_donation_date = None
    
    if not can_donate and donor[7]:  # If last_donation_date exists
        last_date = datetime.datetime.strptime(donor[7], '%Y-%m-%d').date()
        next_donation_date = last_date + datetime.timedelta(days=60)
    
    return render_template('donor_dashboard.html', 
                          donor=donor, 
                          donations=donations, 
                          can_donate=can_donate,
                          next_donation_date=next_donation_date,
                          now=datetime.datetime.now())

@app.route('/donor/donate', methods=['POST'])
def donor_donate():
    if 'donor_id' not in session:
        flash('Please login first')
        return redirect(url_for('donor_login'))
    
    donor_id = session['donor_id']
    
    # Check if donor can donate
    if not can_donor_donate(donor_id):
        flash('You cannot donate yet. Donors must wait 60 days between donations.')
        return redirect(url_for('donor_dashboard'))
    
    quantity_ml = request.form['quantity_ml']
    
    # Get donor's blood type
    with CursorFromConnectionPool() as cursor:
        cursor.execute("SELECT blood_type FROM donors WHERE id = ?", (donor_id,))
        blood_type = cursor.fetchone()[0]
        
        # Update last donation date
        cursor.execute("UPDATE donors SET last_donation_date = ? WHERE id = ?", 
                      (datetime.date.today(), donor_id))
    
    # Create blood bank entry
    create_blood_bank_entry(blood_type, quantity_ml, donor_id)
    
    flash('Thank you for your donation!')
    return redirect(url_for('donor_dashboard'))

@app.route('/donor/logout')
def donor_logout():
    session.pop('donor_id', None)
    session.pop('donor_name', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

# Recipient routes
@app.route('/recipient/register', methods=['GET', 'POST'])
def recipient_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        blood_type = request.form['blood_type']
        phone = request.form['phone']
        address = request.form['address']
        medical_condition = request.form['medical_condition']
        
        hashed_password = generate_password_hash(password)
        
        try:
            with CursorFromConnectionPool() as cursor:
                cursor.execute(
                    "INSERT INTO recipients (name, email, password, blood_type, phone, address, medical_condition) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, email, hashed_password, blood_type, phone, address, medical_condition)
                )
                # Get the last inserted row id
                cursor.execute("SELECT last_insert_rowid()")
                recipient_id = cursor.fetchone()[0]
            
            flash('Registration successful! Please login.')
            return redirect(url_for('recipient_login'))
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: recipients.email" in str(e):
                flash('Email address already registered.')
            else:
                flash(f'An error occurred: {str(e)}')
        except Exception as e:
            flash(f'An error occurred: {str(e)}')
    
    return render_template('recipient_register.html', now=datetime.datetime.now())

@app.route('/recipient/login', methods=['GET', 'POST'])
def recipient_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            with CursorFromConnectionPool() as cursor:
                cursor.execute("SELECT id, name, password FROM recipients WHERE email = ?", (email,))
                recipient = cursor.fetchone()
                
                if recipient:
                    recipient_id = recipient[0]
                    recipient_name = recipient[1]
                    stored_password = recipient[2]
                    
                    if check_password_hash(stored_password, password):
                        session['recipient_id'] = recipient_id
                        session['recipient_name'] = recipient_name
                        flash(f'Welcome back, {recipient_name}!')
                        return redirect(url_for('recipient_dashboard'))
                    else:
                        flash('Invalid email or password')
                else:
                    flash('Invalid email or password')
        except Exception as e:
            flash(f'Login error: {str(e)}')
    
    return render_template('recipient_login.html', now=datetime.datetime.now())

@app.route('/recipient/dashboard')
def recipient_dashboard():
    if 'recipient_id' not in session:
        flash('Please login first')
        return redirect(url_for('recipient_login'))
    
    recipient_id = session['recipient_id']
    
    with CursorFromConnectionPool() as cursor:
        # Get recipient details
        cursor.execute("SELECT * FROM recipients WHERE id = ?", (recipient_id,))
        recipient = cursor.fetchone()
        
        # Get available blood of matching type
        cursor.execute("""
            SELECT blood_type, SUM(quantity_ml) as total_quantity 
            FROM blood_bank 
            WHERE blood_type = ? AND expiry_date > ?
            GROUP BY blood_type
        """, (recipient[4], datetime.date.today()))
        
        available_blood = cursor.fetchone()
        
        # Get request history
        cursor.execute("""
            SELECT * FROM blood_requests 
            WHERE recipient_id = ? 
            ORDER BY request_date DESC
        """, (recipient_id,))
        requests = cursor.fetchall()
    
    # Check if recipient can request again
    can_request = can_recipient_request(recipient_id)
    next_request_date = None
    
    if not can_request and recipient[8]:  # If last_request_date exists
        last_date = datetime.datetime.strptime(recipient[8], '%Y-%m-%d').date()
        next_request_date = last_date + datetime.timedelta(days=40)
    
    return render_template('recipient_dashboard.html', 
                          recipient=recipient, 
                          available_blood=available_blood, 
                          requests=requests,
                          can_request=can_request,
                          next_request_date=next_request_date,
                          now=datetime.datetime.now())

@app.route('/recipient/request', methods=['POST'])
def recipient_request():
    if 'recipient_id' not in session:
        flash('Please login first')
        return redirect(url_for('recipient_login'))
    
    recipient_id = session['recipient_id']
    
    # Check if recipient can request
    if not can_recipient_request(recipient_id):
        flash('You cannot request blood yet. Recipients must wait 40 days between requests.')
        return redirect(url_for('recipient_dashboard'))
    
    quantity_ml = request.form['quantity_ml']
    
    # Get recipient's blood type
    with CursorFromConnectionPool() as cursor:
        cursor.execute("SELECT blood_type FROM recipients WHERE id = ?", (recipient_id,))
        blood_type = cursor.fetchone()[0]
        
        # Check if blood is available
        if is_blood_available(blood_type, quantity_ml):
            # Create blood request entry with status "fulfilled"
            cursor.execute(
                "INSERT INTO blood_requests (blood_type, quantity_ml, recipient_id, request_date, status) VALUES (?, ?, ?, ?, ?)",
                (blood_type, quantity_ml, recipient_id, datetime.date.today(), "fulfilled")
            )
            
            # Update the last request date for the recipient
            cursor.execute("UPDATE recipients SET last_request_date = ? WHERE id = ?", 
                          (datetime.date.today(), recipient_id))
            
            # Fulfill the request (subtract from blood bank)
            fulfill_blood_request(blood_type, quantity_ml)
            
            flash('Your blood request has been approved and fulfilled!')
        else:
            # Create blood request entry with status "pending"
            cursor.execute(
                "INSERT INTO blood_requests (blood_type, quantity_ml, recipient_id, request_date, status) VALUES (?, ?, ?, ?, ?)",
                (blood_type, quantity_ml, recipient_id, datetime.date.today(), "pending")
            )
            
            # Update the last request date for the recipient
            cursor.execute("UPDATE recipients SET last_request_date = ? WHERE id = ?", 
                          (datetime.date.today(), recipient_id))
            
            flash('Your blood request has been submitted, but insufficient blood is available at the moment.')
    
    return redirect(url_for('recipient_dashboard'))

@app.route('/recipient/logout')
def recipient_logout():
    session.pop('recipient_id', None)
    session.pop('recipient_name', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
