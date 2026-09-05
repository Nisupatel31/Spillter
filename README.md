# ✈️ Spillter - Travel Group Expense Tracker & Splitter

**Spillter** is a group expense management and debt settlement application designed specifically for travel enthusiasts, road trippers, and group vacations. It eliminates post-trip confusion over who paid, who participated in which activities, and how much everyone owes each other.

---

## 🌟 Key Features

### 1. 💰 Flexible Expense Logging & Multi-Split
- **Equal Split**: Split automatically across all travelers or toggle members on/off.
- **Selected Members**: Only charge specific travelers who participated (e.g., scuba diving, rental bikes, private tours).
- **Percentage-wise Split**: Assign custom percentages (e.g., 50% / 30% / 20%) with live calculation and 100% total validation.
- **Categories**: Stay 🏨, Food & Dining 🍽️, Travel & Fuel 🚗, Activities & Adventure 🏄, Sightseeing 📸, Shopping 🛍️, and Misc 📦.
- **Payer Tracking**: Select which member paid upfront.

### 2. ⚡ Smart Settlement ("Who Pays Whom")
- **Debt Simplification Algorithm**: Eliminates circular and convoluted debts by finding the minimum number of transactions needed to settle all accounts.
- **No Confusion**: Shows clear, direct cards like `Sneha ➔ pays Nisarg ₹7,085.00`.
- **Member Balances**: Live net balance indicator showing who gets back money (🟢) and who owes money (🔴).

### 3. 📲 1-Click WhatsApp Group Sharing
- Generates a clean, emoji-formatted WhatsApp settlement summary ready for your group chat.
- **"Open in WhatsApp"** button: Opens WhatsApp Web or mobile app with pre-filled message.
- **"Copy Message"** button: 1-click clipboard copy.

### 4. 📊 Rich Analytics Dashboard
- **KPI Metrics**: Total Trip Spend, Average per Member, Top Spender, and Pending Settlements count.
- **Interactive Charts**:
  - **Category Breakdown** Donut Chart.
  - **Member Paid Upfront vs Fair Share** Grouped Bar Chart.
  - **Daily Spending Trend** Timeline Line Chart.
- **Recent Expenses** quick feed.

### 5. 📄 Professional Statement Reports (PDF & Excel)
- **PDF Statement**: Ready-to-print multi-page travel report with trip header, KPI cards, settlement table, member balance table, and full itemized expenses log.
- **Excel (.xlsx) Workbook**: Multi-sheet formatted spreadsheet (`Summary & Settlements` and `All Expenses Statement`).

### 6. 🏖️ Preloaded Demo Trip
- Comes pre-seeded with a sample trip: **"Goa Beach & Road Trip 🏖️"** with 5 travelers and realistic expenses across stay, car rental, beach shacks, scuba diving, and shopping.

---

## 🚀 How to Run the App

### Option A: Double-Click (Windows)
Double-click `run.bat` in the project folder. It will launch the server and open your browser automatically.

### Option B: Command Line (PowerShell / Terminal)
```powershell
python run.py
```
Or with uvicorn:
```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

Once started, visit: **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Automated Testing

To run the automated API and split logic tests:
```powershell
python backend/test_api.py
```
