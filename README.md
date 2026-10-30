# ShareLoop — Rent, Borrow & Sell Marketplace

> **"Rent it. Borrow it. Sell it."**  
> Community-focused marketplace proudly launched in **Pune, Maharashtra**, empowering citizens and local shops to share resources, rent quality gear, lend items for free, and buy/sell sustainably.

---

## 🌟 Overview & Key Capabilities

ShareLoop connects neighbors and verified businesses across Pune (Kothrud, Baner, Hinjewadi, Viman Nagar, Koregaon Park, Wakad, Aundh, Hadapsar, etc.) with three distinct transaction models:

1. **Rent:** Monetize underutilized gear (cameras, tools, camping equipment, party gear) with customizable daily rates, security deposits, and booking approvals.
2. **Borrow:** 100% free community borrowing with zero rental fees, agreed care conditions, and trust building.
3. **Sell:** Buy and sell new or pre-loved products with atomic inventory locking, preventing overselling.

---

## 🛠️ Technology Stack

- **Backend Framework:** Django 5.2 LTS (Python 3.11 / 3.12 compatible)
- **Database:** MySQL 8.0 (configured with utf8mb4 and strict transaction modes via PyMySQL)
- **Frontend:** Server-rendered Django Templates, HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons, Vanilla JavaScript
- **Image Processing:** Pillow
- **Authentication:** Custom User model (`accounts.User`) with Individual and Business Seller roles
- **Payment Processing:** Official Razorpay Python SDK with test sandbox simulation mode
- **Testing:** Django TestCase with a 21-test automated suite covering all domain logic

---

## 🏗️ Architecture & Modular Django Apps

- **`core`**: Base layout, home page, how-it-works workflow guide, safety & trust guidelines, legal pages, contact form, in-app notifications system.
- **`accounts`**: Custom User model, UserProfile, Address management, authentication, seller dashboard with real accounting separation, public seller profiles.
- **`listings`**: Categories, multi-mode listings (Rent, Borrow, Sell), image uploads, full-text database search, faceted filters, reporting system.
- **`rentals`**: Rental booking workflow, calendar conflict avoidance, cost calculations, status transitions (Pending, Accepted, Active, Completed).
- **`borrowing`**: Free peer loan workflow, duration caps, condition acceptance, status transitions (Pending, Accepted, Active, Completed).
- **`orders`**: Product sales order processing, atomic inventory reservation with `select_for_update()`, status transitions.
- **`payments`**: Razorpay payment order creation, server-side signature verification, idempotent webhook handling, refund tracking, and developer sandbox simulation.
- **`reviews`**: Private photo-backed Handover & Return Evidence logging, star ratings and verified transaction reviews.

---

## 🚀 Quickstart & Local Installation

### 1. Prerequisites
- Python 3.11 or 3.12
- MySQL Server 8.0 running locally or remotely
- Git

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone <repo-url> ShareLoop
cd ShareLoop

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update database credentials and secrets in `.env`:
```ini
DEBUG=True
SECRET_KEY=your-secure-random-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

DB_ENGINE=django.db.backends.mysql
DB_NAME=shareloop_db
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306

PLATFORM_COMMISSION_PERCENTAGE=5.0
DEFAULT_CITY=Pune
DEFAULT_STATE=Maharashtra
TIME_ZONE=Asia/Kolkata

# Razorpay credentials (leave blank for safe sandbox test mode)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
```

### 5. Create Database and Run Migrations
In MySQL:
```sql
CREATE DATABASE IF NOT EXISTS shareloop_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Run Django migrations:
```bash
python manage.py migrate
```

### 6. Seed Initial Pune Data & Demo Accounts
Run the automated seed command to populate categories, demo users, and realistic listings in Pune:
```bash
python manage.py seed_shareloop
```

#### Demo Credentials Created:
- **Admin Portal:** `admin` / `Admin@123`
- **Business Seller (Baner):** `pune_gear_hub` / `Seller@123`
- **Individual User (Kothrud):** `rahul_deshmukh` / `User@123`
- **Individual User (Viman Nagar):** `priya_sharma` / `User@123`

### 7. Run the Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🧪 Running Automated Tests

Run the complete 21-test automated suite:
```bash
python manage.py test
```

### What is tested:
- **`accounts`**: Registration, login/logout, unauthorized dashboard access prevention, role validation.
- **`listings`**: Minimum listing mode validation, negative price/deposit rejection, database search & filter by Pune locality, unauthorized editing prevention.
- **`rentals`**: Financial cost calculations, overlapping booking conflict prevention, preventing booking own items, owner approval transitions.
- **`borrowing`**: Guaranteeing ₹0 rental fee, borrow duration limits, owner acceptance.
- **`orders`**: Atomic inventory reservation with row locking, overselling prevention, automatic `SOLD` transition.
- **`payments`**: Server-side signature verification, booking confirmation, webhook idempotency against duplicate delivery.
- **`reviews`**: Handover evidence access controls (participants only), duplicate review prevention for same transaction, self-review prevention.

---

## 💳 Payment Gateway & Sandbox Modes

1. **Test Mode Simulation:** When `RAZORPAY_KEY_ID` is empty in `.env`, checkout pages activate the **ShareLoop Test Sandbox**, allowing safe, transparent demonstration of successful and failed payment flows without calling real payment APIs.
2. **Razorpay Live/Test Mode:** Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env`. The checkout view automatically loads the official Razorpay Checkout modal, creates server orders, and validates HMAC SHA256 payment signatures.
3. **Webhooks:** Webhook events are processed idempotently via `/payments/webhook/razorpay/` with verification against `RAZORPAY_WEBHOOK_SECRET`.

---

## 🛡️ Trust, Handover Evidence & Security

- **Handover & Return Evidence:** Both lenders and borrowers can upload timestamped photographs and condition assessments (`PRISTINE`, `GOOD`, `MINOR_WEAR`, `DAMAGED`) at pickup and return. Access is restricted strictly to transaction participants and admin moderators.
- **Accounting Integrity:** Refundable security deposits are never treated as revenue and are clearly distinguished from gross sales and net rental earnings on dashboards.
- **Production Security:** Configured with CSRF tokens, password hashing, parameterised ORM queries, rate-limiting-ready structures, and production security toggles (`SECURE_BROWSER_XSS_FILTER`, `SESSION_COOKIE_SECURE`).

---

## 📄 License
ShareLoop is proprietary software for community and commercial marketplace deployment.
