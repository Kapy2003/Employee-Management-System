# Employee Management System (EMS)

A Python-based **Employee Management System (EMS)** designed to simplify employee administration, attendance tracking, leave management, and HR operations. Built using Python and SQLite, the application provides separate portals for administrators and employees through an interactive command-line interface.

## Features

### Admin / HR Dashboard
- **Employee Management** – Add, view, search, and update employee records.
- **Department Management** – Create and list organizational departments.
- **Designation Management** – Add designations and associate them with departments.
- **Attendance Management** – Record and update daily employee attendance.
- **Leave Management** – Review, approve, and reject employee leave requests.
- **HR Reports** – Generate organizational summaries, including:
  - Total employees
  - Active and inactive employees
  - Department-wise employee distribution
  - Monthly active payroll

### Employee Portal
- **Profile Management** – View personal and employment information.
- **Contact Information** – Update phone number, email, address, and emergency contact.
- **Attendance Records** – View personal attendance history.
- **Leave Applications** – Submit leave requests with dates, duration, and reason.
- **Leave Balance** – Track available leave days and application statuses.

### Authentication & Database
- Role-based login system (Admin and Employee).
- Password hashing using SHA-256.
- SQLite database for persistent data storage.
- Automatic database and table initialization.
- Foreign key constraints for relational data integrity.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3 | Core application logic |
| SQLite3 | Database management |
| hashlib | Password hashing |
| datetime | Date handling |
| Standard Library | Application dependencies |

**No external Python packages are required.**

## Project Structure

```text
Employee-Management-System/
│
├── ems.py           # Main application and business logic
├── ems.db           # SQLite database (created automatically)
└── README.md        # Project documentation
```

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Employee-Management-System.git
```

### 2. Navigate to the Project Directory

```bash
cd Employee-Management-System
```

### 3. Run the Application

```bash
python ems.py
```

The application automatically initializes the SQLite database and creates the required tables on the first launch.

## Default Admin Credentials

On the first launch, the system automatically creates a default administrator account if no users exist.

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |
| Role | Administrator |

**Important:** Change the default credentials before using the application with real employee information.

## Running Self-Check Tests

The project includes seven built-in self-check tests to verify its core functionality.

Run the tests using:

```bash
python ems.py --test
```

The tests cover:

1. Administrator authentication.
2. Employee creation and account linking.
3. Employee authentication.
4. Search and update employee information.
5. Attendance tracking.
6. Leave application and approval.
7. HR summary report generation.

Expected output:

```text
Running self-check tests...
✓ All 7 self-check tests passed successfully!
```

## Database Overview

The application uses SQLite with the following relational tables:

| Table | Description |
|---|---|
| `employees` | Stores employee profiles and employment details |
| `users` | Stores login credentials and user roles |
| `departments` | Stores organizational departments |
| `designations` | Stores employee job designations |
| `attendance` | Maintains daily attendance records |
| `leaves` | Stores employee leave applications and approval statuses |

## Security & Limitations

This project is a minimal implementation intended for learning and demonstration purposes.

- SHA-256 is used for password hashing without a salt. Production applications should use a dedicated password-hashing algorithm such as Argon2id or bcrypt.
- The application currently uses a command-line interface rather than a web interface.
- Input validation and access-control mechanisms can be further strengthened.
- Sensitive employee information, including salary and bank details, requires additional protection before production deployment.

## Future Improvements

Potential enhancements include:

- Web-based interface using FastAPI or Flask.
- Modern dashboard with employee analytics.
- Stronger authentication and password security.
- Employee profile photo uploads.
- Payroll processing and salary slips.
- Attendance analytics and exportable reports.
- Automated leave calculations and notifications.
- Database migration to PostgreSQL.

## License

This project is open-source and available for educational and personal use. Add a specific license file if you intend to distribute it under a formal open-source license.

---

**Developed with Python and SQLite.**
