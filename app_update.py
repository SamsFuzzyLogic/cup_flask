from flask import Flask, render_template, request, redirect, url_for, flash, session
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from pytz import timezone, utc
import os
import json
import smtplib
from email.mime.text import MIMEText
from gspread_formatting import CellFormat, Color, TextFormat, format_cell_range
import re

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # securely use from .env or Render secret

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def send_confirmation_email(to_email, name, q1, q2, q3, q4, lead_lap):
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    subject = "✅ Cup Car Challenge – Confirmation Received"
    body = f"""
    Hi {name},

    Thanks for participating in the Cup Car Challenge!

    Your picks:
    - Chevrolet Driver: {q1}
    - Ford Driver: {q2}
    - Toyota Driver: {q3}
    - Manufacturer Winner: {q4}
    - Cars on Lead Lap: {lead_lap}

    🏁 Good luck and may the best team win!
    """
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        entry_name = request.form.get("entry_name", "").strip()
        email = request.form.get("email", "").strip()
        q1 = request.form.get("q1")
        q2 = request.form.get("q2")
        q3 = request.form.get("q3")
        q4 = request.form.get("q4")
        lead_lap = request.form.get("lead_lap", "").strip()

        errors = []
        if not entry_name:
            errors.append("Entry Name is required.")
        if not email or not is_valid_email(email):
            errors.append("A valid Email Address is required.")
        if not lead_lap.isdigit() or not (1 <= int(lead_lap) <= 37):
            errors.append("Enter a number between 1 and 37 for cars finishing on the lead lap.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            eastern = timezone("US/Eastern")
            timestamp = datetime.now(utc).astimezone(eastern).strftime("%Y-%m-%d %H:%M:%S")

            creds_dict = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open("Cup Survey")
            target_title = "Chicago 2025"
            worksheet_list = spreadsheet.worksheets()
            sheet = next((ws for ws in worksheet_list if ws.title.strip().lower() == target_title.lower()), None)
            if not sheet:
                sheet = spreadsheet.add_worksheet(title=target_title, rows="100", cols="10")

            headers = ["Timestamp", "Email", "Entry Name", "Chevrolet Driver", "Ford Driver", "Toyota Driver", "Manufacturer", "Lead Lap"]
            values = sheet.get_all_values()
            if not values or values[0] != headers:
                sheet.update("A1:H1", [headers])
                header_format = CellFormat(
                    backgroundColor=Color(0.27, 0.27, 0.27),
                    textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1))
                )
                format_cell_range(sheet, "A1:H1", header_format)

            sheet.append_row([timestamp, email, entry_name, q1, q2, q3, q4, int(lead_lap)])
            send_confirmation_email(email, entry_name, q1, q2, q3, q4, int(lead_lap))

            # ✅ Store in session and redirect
            session["summary"] = {
                "name": entry_name,
                "email": email,
                "q1": q1,
                "q2": q2,
                "q3": q3,
                "q4": q4,
                "lead_lap": lead_lap
            }
            return redirect(url_for("thank_you"))
    return render_template("form.html")

@app.route("/thank-you")
def thank_you():
    summary = session.pop("summary", None)
    return render_template("thank_you.html", summary=summary)

if __name__ == "__main__":
    app.run(debug=True)
