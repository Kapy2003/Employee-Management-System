#!/usr/bin/env python3
"""Employee Management System (EMS)
Minimal, complete standard-library implementation backed by SQLite.
"""

import hashlib
import sqlite3
import sys
from datetime import date

# shortcut: sha256 without salt, upgrade to argon2/bcrypt for production web auth.
def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_db(db_path: str = "ems.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS designations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            phone TEXT,
            email TEXT UNIQUE,
            address TEXT,
            department TEXT,
            designation TEXT,
            date_of_joining TEXT,
            employment_type TEXT DEFAULT 'Full-Time',
            manager TEXT,
            status TEXT DEFAULT 'Active',
            salary REAL DEFAULT 0.0,
            bank_details TEXT,
            emergency_contact TEXT,
            leave_balance INTEGER DEFAULT 20
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'employee')),
            employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'On Leave')),
            UNIQUE(employee_id, date)
        );

        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected'))
        );
        """)

        # Default admin seed if no users exist
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users;")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
                ("admin", hash_pw("admin123"), "admin"),
            )


# --- Core Service Logic ---

def authenticate(conn: sqlite3.Connection, username: str, password: str):
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role, employee_id FROM users WHERE username = ? AND password_hash = ?;",
        (username, hash_pw(password)),
    )
    return cur.fetchone()


def create_employee(conn: sqlite3.Connection, data: dict, username: str = None, password: str = None) -> int:
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employees (
                name, dob, gender, phone, email, address, department, designation,
                date_of_joining, employment_type, manager, status, salary, bank_details,
                emergency_contact, leave_balance
            ) VALUES (
                :name, :dob, :gender, :phone, :email, :address, :department, :designation,
                :date_of_joining, :employment_type, :manager, :status, :salary, :bank_details,
                :emergency_contact, :leave_balance
            );
        """, data)
        emp_id = cur.lastrowid
        if username and password:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, employee_id) VALUES (?, ?, 'employee', ?);",
                (username, hash_pw(password), emp_id),
            )
        return emp_id


def update_employee(conn: sqlite3.Connection, emp_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [emp_id]
    with conn:
        conn.execute(f"UPDATE employees SET {set_clause} WHERE id = ?;", values)


def get_employee(conn: sqlite3.Connection, emp_id: int):
    return conn.execute("SELECT * FROM employees WHERE id = ?;", (emp_id,)).fetchone()


def list_employees(conn: sqlite3.Connection, active_only: bool = False):
    query = "SELECT * FROM employees" + (" WHERE status = 'Active'" if active_only else "") + " ORDER BY id;"
    return conn.execute(query).fetchall()


def search_employees(conn: sqlite3.Connection, term: str):
    q = f"%{term}%"
    return conn.execute("""
        SELECT * FROM employees
        WHERE name LIKE ? OR department LIKE ? OR designation LIKE ? OR email LIKE ?
        ORDER BY id;
    """, (q, q, q, q)).fetchall()


def record_attendance(conn: sqlite3.Connection, emp_id: int, att_date: str, status: str) -> None:
    with conn:
        conn.execute("""
            INSERT INTO attendance (employee_id, date, status)
            VALUES (?, ?, ?)
            ON CONFLICT(employee_id, date) DO UPDATE SET status = excluded.status;
        """, (emp_id, att_date, status))


def get_attendance(conn: sqlite3.Connection, emp_id: int):
    return conn.execute(
        "SELECT date, status FROM attendance WHERE employee_id = ? ORDER BY date DESC;", (emp_id,)
    ).fetchall()


def apply_leave(conn: sqlite3.Connection, emp_id: int, start_date: str, end_date: str, days: int, reason: str) -> int:
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO leaves (employee_id, start_date, end_date, days, reason, status)
            VALUES (?, ?, ?, ?, ?, 'Pending');
        """, (emp_id, start_date, end_date, days, reason))
        return cur.lastrowid


def review_leave(conn: sqlite3.Connection, leave_id: int, approved: bool) -> None:
    status = "Approved" if approved else "Rejected"
    with conn:
        leave = conn.execute("SELECT employee_id, days, status FROM leaves WHERE id = ?;", (leave_id,)).fetchone()
        if not leave:
            raise ValueError(f"Leave request #{leave_id} not found.")
        if leave["status"] == "Pending" and approved:
            conn.execute(
                "UPDATE employees SET leave_balance = leave_balance - ? WHERE id = ?;",
                (leave["days"], leave["employee_id"]),
            )
        conn.execute("UPDATE leaves SET status = ? WHERE id = ?;", (status, leave_id))


def get_employee_leaves(conn: sqlite3.Connection, emp_id: int):
    return conn.execute("SELECT * FROM leaves WHERE employee_id = ? ORDER BY id DESC;", (emp_id,)).fetchall()


def get_pending_leaves(conn: sqlite3.Connection):
    return conn.execute("""
        SELECT l.id, e.name, l.start_date, l.end_date, l.days, l.reason, l.status
        FROM leaves l JOIN employees e ON l.employee_id = e.id
        WHERE l.status = 'Pending'
        ORDER BY l.id;
    """).fetchall()


def hr_summary_report(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM employees;").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active';").fetchone()[0]
    dept_counts = conn.execute("""
        SELECT COALESCE(department, 'Unassigned') as dept, COUNT(*) as cnt
        FROM employees GROUP BY department;
    """).fetchall()
    total_payroll = conn.execute("SELECT COALESCE(SUM(salary), 0) FROM employees WHERE status = 'Active';").fetchone()[0]
    return {
        "total_employees": total,
        "active_employees": active,
        "inactive_employees": total - active,
        "department_distribution": {row["dept"]: row["cnt"] for row in dept_counts},
        "monthly_active_payroll": total_payroll,
    }


# --- Interactive CLI ---

def prompt(msg: str, default: str = "") -> str:
    val = input(f"{msg} [{default}]: " if default else f"{msg}: ").strip()
    return val or default


def print_table(headers: list, rows: list) -> None:
    if not rows:
        print("  (No records found)")
        return
    str_rows = [[str(item or "") for item in row] for row in rows]
    col_widths = [max(len(h), max(len(r[i]) for r in str_rows)) for i, h in enumerate(headers)]
    fmt = "  " + " | ".join(f"{{:<{w}}}" for w in col_widths)
    sep = "  " + "-+-".join("-" * w for w in col_widths)
    print(fmt.format(*headers))
    print(sep)
    for r in str_rows:
        print(fmt.format(*r))


def admin_menu(conn: sqlite3.Connection, user: sqlite3.Row) -> None:
    while True:
        print("\n=== HR / Admin Dashboard ===")
        print("1. List All Employees")
        print("2. Add Employee")
        print("3. View / Search Employee Profile")
        print("4. Update Employee Info / Salary / Status")
        print("5. Manage Departments & Designations")
        print("6. Record Attendance")
        print("7. Review Leave Requests")
        print("8. Generate HR Reports")
        print("9. Logout")

        choice = input("Enter choice (1-9): ").strip()
        if choice == "1":
            active_only = prompt("Active only? (y/n)", "n").lower() == "y"
            emps = list_employees(conn, active_only=active_only)
            headers = ["ID", "Name", "Department", "Designation", "Status", "Salary", "Leaves Left"]
            rows = [[e["id"], e["name"], e["department"], e["designation"], e["status"], f"${e['salary']:,.2f}", e["leave_balance"]] for e in emps]
            print_table(headers, rows)

        elif choice == "2":
            print("\n--- Add New Employee ---")
            data = {
                "name": prompt("Full Name"),
                "dob": prompt("Date of Birth (YYYY-MM-DD)", "1990-01-01"),
                "gender": prompt("Gender", "Not specified"),
                "phone": prompt("Phone Number"),
                "email": prompt("Email Address"),
                "address": prompt("Address"),
                "department": prompt("Department"),
                "designation": prompt("Designation"),
                "date_of_joining": prompt("Date of Joining (YYYY-MM-DD)", str(date.today())),
                "employment_type": prompt("Employment Type", "Full-Time"),
                "manager": prompt("Reporting Manager"),
                "status": "Active",
                "salary": float(prompt("Salary", "50000") or 0.0),
                "bank_details": prompt("Bank/Payment Details"),
                "emergency_contact": prompt("Emergency Contact"),
                "leave_balance": int(prompt("Initial Leave Balance", "20") or 20),
            }
            uname = prompt("Create Login Username (optional)")
            pword = prompt("Create Login Password (optional)") if uname else None
            try:
                emp_id = create_employee(conn, data, uname, pword)
                print(f"✓ Employee #{emp_id} created successfully.")
            except sqlite3.IntegrityError as err:
                print(f"✗ Failed to create employee: {err}")

        elif choice == "3":
            term = prompt("Search by ID, name, email, or department")
            if term.isdigit():
                emp = get_employee(conn, int(term))
                results = [emp] if emp else []
            else:
                results = search_employees(conn, term)
            if not results:
                print("  No employees found.")
            for e in results:
                print(f"\n[Employee #{e['id']}: {e['name']}]")
                for k in e.keys():
                    print(f"  {k:20}: {e[k]}")

        elif choice == "4":
            emp_id = int(prompt("Employee ID to update"))
            emp = get_employee(conn, emp_id)
            if not emp:
                print("Employee not found.")
                continue
            print(f"Editing #{emp['id']} {emp['name']}. Leave blank to keep current.")
            updates = {}
            for col in ["name", "phone", "email", "address", "department", "designation", "status", "emergency_contact"]:
                val = input(f"  {col} [{emp[col]}]: ").strip()
                if val:
                    updates[col] = val
            sal = input(f"  salary [{emp['salary']}]: ").strip()
            if sal:
                updates["salary"] = float(sal)
            update_employee(conn, emp_id, updates)
            print("✓ Employee updated.")

        elif choice == "5":
            print("\n1. Add Department  2. List Departments  3. Add Designation  4. List Designations")
            sub = input("Select: ").strip()
            if sub == "1":
                dname = prompt("Department Name")
                with conn:
                    conn.execute("INSERT OR IGNORE INTO departments (name) VALUES (?);", (dname,))
                print("✓ Saved.")
            elif sub == "2":
                rows = conn.execute("SELECT id, name FROM departments;").fetchall()
                print_table(["ID", "Department"], [[r["id"], r["name"]] for r in rows])
            elif sub == "3":
                title = prompt("Designation Title")
                dept_id = int(prompt("Department ID") or 0)
                with conn:
                    conn.execute("INSERT INTO designations (name, department_id) VALUES (?, ?);", (title, dept_id or None))
                print("✓ Saved.")
            elif sub == "4":
                rows = conn.execute("""
                    SELECT d.id, d.name, COALESCE(dept.name, '-') as dept
                    FROM designations d LEFT JOIN departments dept ON d.department_id = dept.id;
                """).fetchall()
                print_table(["ID", "Designation", "Department"], [[r["id"], r["name"], r["dept"]] for r in rows])

        elif choice == "6":
            emp_id = int(prompt("Employee ID"))
            att_date = prompt("Date (YYYY-MM-DD)", str(date.today()))
            status = prompt("Status (Present/Absent/On Leave)", "Present")
            if status not in ("Present", "Absent", "On Leave"):
                print("Invalid status.")
                continue
            record_attendance(conn, emp_id, att_date, status)
            print("✓ Attendance recorded.")

        elif choice == "7":
            leaves = get_pending_leaves(conn)
            if not leaves:
                print("No pending leave applications.")
                continue
            print_table(
                ["Leave ID", "Employee", "Start", "End", "Days", "Reason"],
                [[l["id"], l["name"], l["start_date"], l["end_date"], l["days"], l["reason"]] for l in leaves],
            )
            lid = prompt("Enter Leave ID to review (or press enter to skip)")
            if lid and lid.isdigit():
                action = prompt("Approve (a) or Reject (r)?", "a").lower()
                review_leave(conn, int(lid), approved=(action == "a"))
                print(f"✓ Leave #{lid} {'Approved' if action == 'a' else 'Rejected'}.")

        elif choice == "8":
            rep = hr_summary_report(conn)
            print("\n--- Organization Summary Report ---")
            print(f"Total Staff       : {rep['total_employees']}")
            print(f"Active Staff      : {rep['active_employees']}")
            print(f"Inactive / Exited : {rep['inactive_employees']}")
            print(f"Monthly Payroll   : ${rep['monthly_active_payroll']:,.2f}")
            print("Department Breakdown:")
            for dept, count in rep["department_distribution"].items():
                print(f"  • {dept:20}: {count}")

        elif choice == "9":
            break


def employee_menu(conn: sqlite3.Connection, user: sqlite3.Row) -> None:
    emp_id = user["employee_id"]
    if not emp_id:
        print("No employee record linked to this user account.")
        return

    while True:
        emp = get_employee(conn, emp_id)
        print(f"\n=== Employee Portal ({emp['name']}) ===")
        print("1. View Profile & Salary")
        print("2. Update Personal Contact Info")
        print("3. View Attendance Records")
        print("4. Apply for Leave")
        print("5. View Leave Requests & Balance")
        print("6. Logout")

        choice = input("Enter choice (1-6): ").strip()
        if choice == "1":
            print("\n--- My Profile ---")
            for k in ["id", "name", "dob", "gender", "department", "designation", "employment_type", "manager", "status", "salary", "leave_balance"]:
                print(f"  {k:18}: {emp[k]}")
        elif choice == "2":
            print("Update contact info (leave blank to keep current):")
            updates = {}
            for k in ["phone", "email", "address", "emergency_contact"]:
                v = input(f"  {k} [{emp[k]}]: ").strip()
                if v:
                    updates[k] = v
            update_employee(conn, emp_id, updates)
            print("✓ Information updated.")
        elif choice == "3":
            rows = get_attendance(conn, emp_id)
            print_table(["Date", "Status"], [[r["date"], r["status"]] for r in rows])
        elif choice == "4":
            print(f"Current leave balance: {emp['leave_balance']} days")
            start = prompt("Start Date (YYYY-MM-DD)")
            end = prompt("End Date (YYYY-MM-DD)")
            days = int(prompt("Number of Days", "1") or 1)
            reason = prompt("Reason for leave")
            apply_leave(conn, emp_id, start, end, days, reason)
            print("✓ Leave application submitted.")
        elif choice == "5":
            leaves = get_employee_leaves(conn, emp_id)
            print(f"Available Leave Balance: {emp['leave_balance']} days")
            print_table(
                ["ID", "Start Date", "End Date", "Days", "Status", "Reason"],
                [[l["id"], l["start_date"], l["end_date"], l["days"], l["status"], l["reason"]] for l in leaves],
            )
        elif choice == "6":
            break


def main() -> None:
    # shortcut: CLI menu navigation, upgrade to FastAPI/Flask if modern web browser client is requested.
    conn = get_db()
    init_db(conn)

    print("========================================")
    print("      Employee Management System        ")
    print("========================================")

    while True:
        print("\n1. Login")
        print("2. Exit")
        choice = input("Select option (1-2): ").strip()
        if choice == "1":
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            user = authenticate(conn, username, password)
            if not user:
                print("✗ Invalid credentials.")
                continue
            print(f"\nWelcome, {user['username']} ({user['role'].upper()})!")
            if user["role"] == "admin":
                admin_menu(conn, user)
            else:
                employee_menu(conn, user)
        elif choice == "2":
            print("Goodbye.")
            break


# --- Self-check verification ---

def run_tests() -> None:
    print("Running self-check tests...")
    conn = get_db(":memory:")
    init_db(conn)

    # 1. Admin authentication check
    admin = authenticate(conn, "admin", "admin123")
    assert admin is not None and admin["role"] == "admin", "Admin login failed"

    # 2. Create employee & user account
    emp_data = {
        "name": "Jane Doe",
        "dob": "1994-05-12",
        "gender": "Female",
        "phone": "+1-555-0199",
        "email": "jane.doe@example.com",
        "address": "123 Market St",
        "department": "Engineering",
        "designation": "Software Engineer",
        "date_of_joining": "2023-01-15",
        "employment_type": "Full-Time",
        "manager": "Alex Smith",
        "status": "Active",
        "salary": 95000.0,
        "bank_details": "Chase Acct #1234",
        "emergency_contact": "+1-555-9999",
        "leave_balance": 20,
    }
    emp_id = create_employee(conn, emp_data, username="janedoe", password="password123")
    assert emp_id > 0, "Employee creation failed"

    # 3. Employee authentication
    emp_user = authenticate(conn, "janedoe", "password123")
    assert emp_user and emp_user["employee_id"] == emp_id, "Employee login failed"

    # 4. Search and update
    results = search_employees(conn, "Jane")
    assert len(results) == 1 and results[0]["id"] == emp_id, "Employee search failed"
    update_employee(conn, emp_id, {"phone": "+1-555-0200"})
    assert get_employee(conn, emp_id)["phone"] == "+1-555-0200", "Employee update failed"

    # 5. Attendance tracking
    record_attendance(conn, emp_id, "2026-11-16", "Present")
    att = get_attendance(conn, emp_id)
    assert len(att) == 1 and att[0]["status"] == "Present", "Attendance recording failed"

    # 6. Leave application & approval
    lid = apply_leave(conn, emp_id, "2026-12-01", "2026-12-03", 3, "Vacation")
    pending = get_pending_leaves(conn)
    assert any(l["id"] == lid for l in pending), "Leave application not listed in pending"

    review_leave(conn, lid, approved=True)
    emp_after = get_employee(conn, emp_id)
    assert emp_after["leave_balance"] == 17, f"Expected 17 leaves, got {emp_after['leave_balance']}"

    # 7. HR Report
    rep = hr_summary_report(conn)
    assert rep["total_employees"] == 1 and rep["active_employees"] == 1
    assert rep["monthly_active_payroll"] == 95000.0

    print("✓ All 7 self-check tests passed successfully!")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        main()
