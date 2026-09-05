import urllib.parse
from typing import Dict, List, Any
from backend.database import get_db_connection

def calculate_trip_settlement(trip_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get Trip info
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    trip_row = cursor.fetchone()
    if not trip_row:
        conn.close()
        raise ValueError(f"Trip with id {trip_id} not found")

    trip = dict(trip_row)
    currency = trip.get("currency", "₹")

    # Get Members
    cursor.execute("SELECT * FROM members WHERE trip_id = ? ORDER BY name ASC", (trip_id,))
    members = [dict(row) for row in cursor.fetchall()]
    member_map = {m["id"]: m for m in members}

    if not members:
        conn.close()
        return {
            "trip": trip,
            "total_expenses": 0.0,
            "member_count": 0,
            "average_expense": 0.0,
            "member_stats": [],
            "settlements": [],
            "settlement_history": [],
            "whatsapp_text": "",
            "whatsapp_url": ""
        }

    # Calculate Total Paid in Expenses by each member
    cursor.execute("""
        SELECT payer_id, COALESCE(SUM(amount), 0.0) as total_paid
        FROM expenses
        WHERE trip_id = ?
        GROUP BY payer_id
    """, (trip_id,))
    paid_rows = cursor.fetchall()
    paid_expenses_map = {row["payer_id"]: float(row["total_paid"]) for row in paid_rows}

    # Calculate Total Owed (share) in Expenses by each member
    cursor.execute("""
        SELECT es.member_id, COALESCE(SUM(es.share_amount), 0.0) as total_owed
        FROM expense_splits es
        JOIN expenses e ON es.expense_id = e.id
        WHERE e.trip_id = ?
        GROUP BY es.member_id
    """, (trip_id,))
    owed_rows = cursor.fetchall()
    owed_expenses_map = {row["member_id"]: float(row["total_owed"]) for row in owed_rows}

    # Fetch recorded Settlement Payments (who has already paid whom)
    cursor.execute("""
        SELECT sp.*, p.name as payer_name, r.name as receiver_name
        FROM settlement_payments sp
        JOIN members p ON sp.payer_id = p.id
        JOIN members r ON sp.receiver_id = r.id
        WHERE sp.trip_id = ?
        ORDER BY sp.date DESC, sp.id DESC
    """, (trip_id,))
    settle_rows = cursor.fetchall()

    settlement_history = []
    settled_paid_map = {}
    settled_received_map = {}

    for row in settle_rows:
        s_dict = dict(row)
        settlement_history.append(s_dict)
        pid = s_dict["payer_id"]
        rid = s_dict["receiver_id"]
        amt = float(s_dict["amount"])

        settled_paid_map[pid] = settled_paid_map.get(pid, 0.0) + amt
        settled_received_map[rid] = settled_received_map.get(rid, 0.0) + amt

    # Calculate total trip expenses (excluding settlements)
    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM expenses WHERE trip_id = ?", (trip_id,))
    total_expenses = float(cursor.fetchone()["total"])

    conn.close()

    # Build Member Stats with net calculations incorporating direct settlements
    member_stats = []
    debtors = []   # Those who still owe money: [id, name, amount_to_pay]
    creditors = [] # Those who still get money back: [id, name, amount_to_receive]

    for m in members:
        mid = m["id"]
        exp_paid = paid_expenses_map.get(mid, 0.0)
        exp_owed = owed_expenses_map.get(mid, 0.0)
        set_paid = settled_paid_map.get(mid, 0.0)
        set_received = settled_received_map.get(mid, 0.0)

        # Net position: (what you paid out) - (what you owed or received)
        net = round((exp_paid + set_paid) - (exp_owed + set_received), 2)

        stats = {
            "id": mid,
            "name": m["name"],
            "phone": m.get("phone") or "",
            "avatar_color": m.get("avatar_color") or "#4F46E5",
            "total_paid": round(exp_paid, 2),
            "settled_paid": round(set_paid, 2),
            "settled_received": round(set_received, 2),
            "total_owed": round(exp_owed, 2),
            "net_balance": net,
            "status": "gets_back" if net > 0.009 else ("owes" if net < -0.009 else "settled")
        }
        member_stats.append(stats)

        if net < -0.009:
            debtors.append({
                "id": mid,
                "name": m["name"],
                "amount": abs(net)
            })
        elif net > 0.009:
            creditors.append({
                "id": mid,
                "name": m["name"],
                "amount": net
            })

    # Debt Simplification Algorithm (Greedy matching) for remaining unpaid balances
    settlements = []
    deb_list = [dict(d) for d in debtors]
    cred_list = [dict(c) for c in creditors]

    while deb_list and cred_list:
        deb_list.sort(key=lambda x: x["amount"], reverse=True)
        cred_list.sort(key=lambda x: x["amount"], reverse=True)

        debtor = deb_list[0]
        creditor = cred_list[0]

        settle_amt = round(min(debtor["amount"], creditor["amount"]), 2)

        if settle_amt > 0.009:
            settlements.append({
                "from_id": debtor["id"],
                "from_name": debtor["name"],
                "to_id": creditor["id"],
                "to_name": creditor["name"],
                "amount": settle_amt,
                "formatted": f"{debtor['name']} pays {creditor['name']} {currency}{settle_amt:,.2f}"
            })

        debtor["amount"] = round(debtor["amount"] - settle_amt, 2)
        creditor["amount"] = round(creditor["amount"] - settle_amt, 2)

        if debtor["amount"] < 0.01:
            deb_list.pop(0)
        if creditor["amount"] < 0.01:
            cred_list.pop(0)

    avg_expense = round(total_expenses / len(members), 2) if members else 0.0

    # WhatsApp message generation
    whatsapp_text = generate_whatsapp_summary(trip, currency, total_expenses, members, avg_expense, member_stats, settlements, settlement_history)
    whatsapp_url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(whatsapp_text)}"

    return {
        "trip": trip,
        "total_expenses": total_expenses,
        "member_count": len(members),
        "average_expense": avg_expense,
        "member_stats": member_stats,
        "settlements": settlements,
        "settlement_history": settlement_history,
        "whatsapp_text": whatsapp_text,
        "whatsapp_url": whatsapp_url
    }

def generate_whatsapp_summary(
    trip: Dict[str, Any],
    currency: str,
    total_expenses: float,
    members: List[Dict[str, Any]],
    avg_expense: float,
    member_stats: List[Dict[str, Any]],
    settlements: List[Dict[str, Any]],
    settlement_history: List[Dict[str, Any]] = None
) -> str:
    lines = []
    lines.append(f"🌴 *{trip['name']}* 🌴")
    if trip.get("description"):
        lines.append(f"_{trip['description']}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 *Total Group Expense:* {currency}{total_expenses:,.2f}")
    lines.append(f"👥 *Total Members:* {len(members)}")
    lines.append(f"📊 *Average Share/Person:* {currency}{avg_expense:,.2f}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    
    if settlements:
        lines.append("⚡ *PENDING SETTLEMENTS (WHO PAYS WHOM)* ⚡")
        lines.append("_(Simplified to minimum transactions)_")
        lines.append("")
        for idx, s in enumerate(settlements, 1):
            lines.append(f"👉 *{s['from_name']}* ➔ pays *{s['to_name']}*: *{currency}{s['amount']:,.2f}*")
    else:
        lines.append("🎉 *All members are completely settled up!*")

    if settlement_history:
        lines.append("")
        lines.append("✅ *SETTLED PAYMENTS COMPLETED:*")
        for sh in settlement_history[:5]:
            lines.append(f"• {sh['payer_name']} paid {sh['receiver_name']}: {currency}{float(sh['amount']):,.2f} ({sh['date']})")
        if len(settlement_history) > 5:
            lines.append(f"• ... and {len(settlement_history) - 5} more settled payments")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📋 *CURRENT NET BALANCES:*")
    for m in member_stats:
        net = m["net_balance"]
        if net > 0.009:
            status_text = f"Gets back {currency}{abs(net):,.2f} 🟢"
        elif net < -0.009:
            status_text = f"Owes {currency}{abs(net):,.2f} 🔴"
        else:
            status_text = "Settled ⚪"
        lines.append(f"• *{m['name']}:* Paid {currency}{m['total_paid']:,.2f} | Share {currency}{m['total_owed']:,.2f} ➔ {status_text}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("✨ _Generated via Spillter Travel App_")
    
    return "\n".join(lines)
