import os
from flask import Flask, render_template_string, request, redirect, url_for
import psycopg2
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. Book a Lesson (Insert)
        if action == 'book_lesson':
            cur.execute(
                "CALL sp_BookLesson(%s, %s, %s, %s, %s, %s, %s);",
                (
                    request.form['customer_id'],
                    request.form['staff_id'],
                    request.form['vehicle_id'],
                    request.form['lesson_date'],
                    request.form['lesson_time'],
                    request.form['price'],
                    request.form['details']
                )
            )
            
        # 2. Record a Payment (Insert)
        elif action == 'record_payment':
            cur.execute(
                "CALL sp_RecordPayment(%s, %s, %s, %s);",
                (
                    request.form['customer_id'],
                    request.form['payment_method_code'],
                    request.form['amount_payment'],
                    request.form['details']
                )
            )

        # 3. Register New Student (Insert)
        elif action == 'add_customer':
            cur.execute(
                """
                INSERT INTO Customers (first_name, last_name, customer_status_code, date_became_customer, date_of_birth, email_address, phone_number, amount_outstanding)
                VALUES (%s, %s, 'ACTIVE', CURRENT_DATE, %s, %s, %s, 0.00);
                """,
                (
                    request.form['first_name'],
                    request.form['last_name'],
                    request.form['dob'],
                    request.form['email'],
                    request.form['phone']
                )
            )

        # 4. Update Lesson Status (Update)
        elif action == 'update_lesson_status':
            cur.execute(
                "UPDATE Lessons SET lesson_status_code = %s WHERE lesson_id = %s;",
                (
                    request.form['lesson_status_code'],
                    request.form['lesson_id']
                )
            )

        # 5. Delete Lesson (Delete)
        elif action == 'delete_lesson':
            cur.execute(
                "DELETE FROM Lessons WHERE lesson_id = %s;",
                (request.form['lesson_id'],)
            )

        # 6. Delete Customer (Delete)
        elif action == 'delete_customer':
            cur.execute(
                "DELETE FROM Customers WHERE customer_id = %s;",
                (request.form['customer_id'],)
            )

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))

    # Fetch data for dropdowns and tables
    cur.execute("SELECT customer_id, first_name || ' ' || last_name FROM Customers ORDER BY first_name;")
    customers = cur.fetchall()
    
    cur.execute("SELECT staff_id, first_name || ' ' || last_name FROM Staff ORDER BY first_name;")
    staff_list = cur.fetchall()
    
    cur.execute("SELECT vehicle_id, vehicle_details FROM Vehicles;")
    vehicles = cur.fetchall()

    cur.execute("SELECT payment_method_code, payment_method_description FROM Ref_Payment_Methods;")
    payment_methods = cur.fetchall()

    cur.execute("SELECT lesson_status_code, lesson_status_description FROM Ref_Lesson_Status;")
    lesson_statuses = cur.fetchall()

    cur.execute("SELECT * FROM vw_ActiveLessons ORDER BY lesson_id DESC;")
    lessons = cur.fetchall()

    cur.execute("""
        SELECT s.staff_id, s.first_name || ' ' || s.last_name AS instructor_name, 
               COUNT(l.lesson_id) AS total_lessons_taught, 
               COALESCE(SUM(l.price), 0.00) AS total_revenue_generated 
        FROM Staff s 
        LEFT JOIN Lessons l ON s.staff_id = l.staff_id AND l.lesson_status_code = 'COMPLETED' 
        GROUP BY s.staff_id, s.first_name, s.last_name;
    """)
    report_instructors = cur.fetchall()

    cur.execute("""
        SELECT customer_id, first_name || ' ' || last_name AS customer_name, 
               customer_status_code, amount_outstanding, email_address, phone_number
        FROM Customers ORDER BY amount_outstanding DESC;
    """)
    report_customers = cur.fetchall()

    cur.execute("""
        SELECT v.vehicle_id, v.vehicle_details, COUNT(l.lesson_id) AS total_bookings 
        FROM Vehicles v 
        LEFT JOIN Lessons l ON v.vehicle_id = l.vehicle_id 
        GROUP BY v.vehicle_id, v.vehicle_details ORDER BY total_bookings DESC;
    """)
    report_vehicles = cur.fetchall()
    
    cur.close()
    conn.close()
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Calgary Driving School - Admin Portal</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background: #f8f9fa; color: #333; display: flex; min-height: 100vh; }
            
            .sidebar { width: 240px; background: #212529; color: white; padding: 25px 20px; }
            .sidebar h2 { font-size: 18px; color: #4dabf7; margin-bottom: 5px; }
            .sidebar p { font-size: 11px; color: #adb5bd; margin-bottom: 30px; }
            .nav-link { display: block; color: #ced4da; text-decoration: none; padding: 10px 14px; border-radius: 6px; margin-bottom: 6px; font-size: 13px; font-weight: 500; background: #343a40; }
            .nav-link:hover { background: #495057; color: white; }
            
            .main { flex: 1; padding: 30px; overflow-y: auto; }
            .top-bar { margin-bottom: 25px; }
            .top-bar h1 { font-size: 24px; color: #212529; }
            .top-bar p { font-size: 13px; color: #6c757d; }
            
            .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #dee2e6; }
            .box h3 { font-size: 15px; margin-bottom: 15px; color: #212529; border-bottom: 2px solid #f1f3f5; padding-bottom: 8px; }
            
            label { display: block; font-size: 11px; font-weight: 700; color: #495057; margin-top: 10px; margin-bottom: 4px; text-transform: uppercase; }
            input, select { width: 100%; padding: 8px 10px; border: 1px solid #ced4da; border-radius: 4px; font-size: 13px; outline: none; background: #fff; }
            input:focus, select:focus { border-color: #4dabf7; box-shadow: 0 0 0 2px rgba(77,171,247,0.2); }
            
            .btn { width: 100%; padding: 10px; border: none; border-radius: 4px; font-weight: 600; font-size: 13px; cursor: pointer; margin-top: 15px; color: white; }
            .btn-blue { background: #1971c2; }
            .btn-blue:hover { background: #1864ab; }
            .btn-green { background: #2b8a3e; }
            .btn-green:hover { background: #2b8a3e; }
            .btn-dark { background: #343a40; }
            .btn-dark:hover { background: #212529; }
            .btn-red { background: #c92a2a; padding: 6px 10px; font-size: 11px; margin-top: 0; width: auto; }
            .btn-red:hover { background: #a61e4d; }
            .btn-yellow { background: #f59f00; padding: 6px 10px; font-size: 11px; margin-top: 0; width: auto; color: white; }
            
            .table-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #dee2e6; margin-bottom: 30px; }
            .table-box h3 { font-size: 16px; color: #212529; margin-bottom: 12px; }
            table { width: 100%; border-collapse: collapse; text-align: left; }
            th { background: #f1f3f5; color: #495057; font-size: 11px; text-transform: uppercase; padding: 10px; border-bottom: 2px solid #dee2e6; }
            td { padding: 10px; border-bottom: 1px solid #e9ecef; font-size: 13px; color: #212529; }
            tr:hover { background: #f8f9fa; }
            .badge { padding: 3px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; background: #ebfbee; color: #2b8a3e; }
            
            .inline-form { display: inline-flex; gap: 5px; align-items: center; }
        </style>
        <script>
            function handlePackageSelect() {
                var select = document.getElementById("pkgSelect");
                var priceInput = document.getElementById("priceBox");
                var noteInput = document.getElementById("noteBox");
                
                if (select.value === "standard") {
                    priceInput.value = "75.00";
                    noteInput.value = "Standard City Driving Lesson";
                } else if (select.value === "highway") {
                    priceInput.value = "90.00";
                    noteInput.value = "Highway & Parallel Parking Practice";
                } else if (select.value === "test_prep") {
                    priceInput.value = "120.00";
                    noteInput.value = "Road Test Preparation & Vehicle Rental";
                }
            }
            
            function confirmDelete(name) {
                return confirm("Are you sure you want to delete " + name + "?");
            }
        </script>
    </head>
    <body>

        <div class="sidebar">
            <h2>Calgary Driving School</h2>
            <p>Admin Reception Portal</p>
            <a href="#lessons" class="nav-link">Active Lessons & CRUD</a>
            <a href="#reports" class="nav-link">Business Reports</a>
            <a href="#customers" class="nav-link">Customer Accounts</a>
        </div>

        <div class="main">
            <div class="top-bar">
                <h1>Receptionist Management Dashboard</h1>
                <p>Manage student bookings, process payments, update statuses, and view real-time fleet analytics.</p>
            </div>

            <!-- INSERT FORMS -->
            <div class="grid-3">
                
                <!-- 1. Schedule Lesson -->
                <div class="box">
                    <h3>Schedule New Lesson</h3>
                    <form method="POST">
                        <input type="hidden" name="action" value="book_lesson">
                        <label>Student Account:</label>
                        <select name="customer_id" required>
                            {% for c in customers %}
                            <option value="{{ c[0] }}">{{ c[1] }}</option>
                            {% endfor %}
                        </select>
                        <label>Assigned Instructor:</label>
                        <select name="staff_id" required>
                            {% for s in staff_list %}
                            <option value="{{ s[0] }}">{{ s[1] }}</option>
                            {% endfor %}
                        </select>
                        <label>Assigned Fleet Vehicle:</label>
                        <select name="vehicle_id" required>
                            {% for v in vehicles %}
                            <option value="{{ v[0] }}">{{ v[1] }}</option>
                            {% endfor %}
                        </select>
                        <label>Lesson Package:</label>
                        <select id="pkgSelect" onchange="handlePackageSelect()">
                            <option value="standard">Standard City Lesson ($75.00)</option>
                            <option value="highway">Highway & Parallel Parking ($90.00)</option>
                            <option value="test_prep">Road Test Prep ($120.00)</option>
                        </select>
                        <label>Date & Time:</label>
                        <div style="display: flex; gap: 8px;">
                            <input type="date" name="lesson_date" required>
                            <input type="time" name="lesson_time" required>
                        </div>
                        <label>Price ($):</label>
                        <input type="number" step="0.01" id="priceBox" name="price" value="75.00" required readonly>
                        <label>Notes:</label>
                        <input type="text" id="noteBox" name="details" value="Standard City Driving Lesson">
                        <button type="submit" class="btn btn-blue">Confirm & Charge Balance</button>
                    </form>
                </div>

                <!-- 2. Record Payment -->
                <div class="box">
                    <h3>Record Student Payment</h3>
                    <form method="POST">
                        <input type="hidden" name="action" value="record_payment">
                        <label>Student Account:</label>
                        <select name="customer_id" required>
                            {% for c in customers %}
                            <option value="{{ c[0] }}">{{ c[1] }}</option>
                            {% endfor %}
                        </select>
                        <label>Payment Method:</label>
                        <select name="payment_method_code" required>
                            {% for pm in payment_methods %}
                            <option value="{{ pm[0] }}">{{ pm[1] }}</option>
                            {% endfor %}
                        </select>
                        <label>Payment Amount ($):</label>
                        <input type="number" step="0.01" name="amount_payment" value="75.00" required>
                        <label>Transaction Reference:</label>
                        <input type="text" name="details" placeholder="e.g. Interac e-Transfer #4910">
                        <button type="submit" class="btn btn-green">Process Payment</button>
                    </form>
                </div>

                <!-- 3. Register Student -->
                <div class="box">
                    <h3>Register New Student</h3>
                    <form method="POST">
                        <input type="hidden" name="action" value="add_customer">
                        <label>First Name:</label>
                        <input type="text" name="first_name" placeholder="e.g. Liam" required>
                        <label>Last Name:</label>
                        <input type="text" name="last_name" placeholder="e.g. Smith" required>
                        <label>Date of Birth:</label>
                        <input type="date" name="dob" required>
                        <label>Email Address:</label>
                        <input type="email" name="email" placeholder="liam@example.com" required>
                        <label>Phone Number:</label>
                        <input type="text" name="phone" placeholder="403-555-0199" required>
                        <button type="submit" class="btn btn-dark">Create Account</button>
                    </form>
                </div>

            </div>

            <!-- ACTIVE LESSONS TABLE WITH UPDATE & DELETE ACTIONS -->
            <div class="table-box" id="lessons">
                <h3>Active & Scheduled Lessons (Updates & Deletes)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Student</th>
                            <th>Instructor</th>
                            <th>Vehicle</th>
                            <th>Date & Time</th>
                            <th>Status (Update)</th>
                            <th>Price</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for l in lessons %}
                        <tr>
                            <td>{{ l[0] }}</td>
                            <td><strong>{{ l[1] }}</strong></td>
                            <td>{{ l[2] }}</td>
                            <td>{{ l[3] }}</td>
                            <td>{{ l[4] }} @ {{ l[5] }}</td>
                            <td>
                                <!-- UPDATE STATUS FORM -->
                                <form method="POST" class="inline-form">
                                    <input type="hidden" name="action" value="update_lesson_status">
                                    <input type="hidden" name="lesson_id" value="{{ l[0] }}">
                                    <select name="lesson_status_code" style="padding: 4px; font-size: 11px;">
                                        {% for st in lesson_statuses %}
                                        <option value="{{ st[0] }}" {% if st[0] == l[6] %}selected{% endif %}>{{ st[0] }}</option>
                                        {% endfor %}
                                    </select>
                                    <button type="submit" class="btn-yellow">Update</button>
                                </form>
                            </td>
                            <td>${{ l[7] }}</td>
                            <td>
                                <!-- DELETE LESSON FORM -->
                                <form method="POST" onsubmit="return confirmDelete('Lesson #{{ l[0] }}');" style="display:inline;">
                                    <input type="hidden" name="action" value="delete_lesson">
                                    <input type="hidden" name="lesson_id" value="{{ l[0] }}">
                                    <button type="submit" class="btn-red">Delete</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <!-- CUSTOMERS TABLE WITH DELETE ACTIONS -->
            <div class="table-box" id="customers">
                <h3>Student Accounts & Deletion</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Student Name</th>
                            <th>Status</th>
                            <th>Outstanding Balance</th>
                            <th>Email</th>
                            <th>Phone</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for c in report_customers %}
                        <tr>
                            <td>{{ c[0] }}</td>
                            <td><strong>{{ c[1] }}</strong></td>
                            <td>{{ c[2] }}</td>
                            <td>${{ c[3] }}</td>
                            <td>{{ c[4] }}</td>
                            <td>{{ c[5] }}</td>
                            <td>
                                <form method="POST" onsubmit="return confirmDelete('{{ c[1] }}');" style="display:inline;">
                                    <input type="hidden" name="action" value="delete_customer">
                                    <input type="hidden" name="customer_id" value="{{ c[0] }}">
                                    <button type="submit" class="btn-red">Delete Student</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <!-- ANALYTICAL REPORTS -->
            <h2 id="reports" style="margin-bottom: 15px; color: #212529;">Business Analytical Reports</h2>
            
            <div class="grid-3">
                
                <div class="table-box">
                    <h3>1. Instructor Revenue</h3>
                    <table>
                        <thead><tr><th>Instructor</th><th>Lessons</th><th>Total Revenue</th></tr></thead>
                        <tbody>
                            {% for r in report_instructors %}
                            <tr><td>{{ r[1] }}</td><td>{{ r[2] }}</td><td>${{ r[3] }}</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                <div class="table-box">
                    <h3>2. Student Balances</h3>
                    <table>
                        <thead><tr><th>Student</th><th>Outstanding</th><th>Phone</th></tr></thead>
                        <tbody>
                            {% for c in report_customers %}
                            <tr><td>{{ c[1] }}</td><td><strong>${{ c[3] }}</strong></td><td>{{ c[5] }}</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                <div class="table-box">
                    <h3>3. Fleet Vehicle Usage</h3>
                    <table>
                        <thead><tr><th>Vehicle</th><th>Bookings</th></tr></thead>
                        <tbody>
                            {% for v in report_vehicles %}
                            <tr><td>{{ v[1] }}</td><td>{{ v[2] }}</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

            </div>

        </div>

    </body>
    </html>
    """
    return render_template_string(
        html, 
        customers=customers, 
        staff_list=staff_list, 
        vehicles=vehicles, 
        payment_methods=payment_methods, 
        lesson_statuses=lesson_statuses,
        lessons=lessons, 
        report_instructors=report_instructors, 
        report_customers=report_customers, 
        report_vehicles=report_vehicles
    )

if __name__ == '__main__':
    app.run(debug=True)