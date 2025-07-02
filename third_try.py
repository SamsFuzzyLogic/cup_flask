from flask import Flask, render_template, request, redirect, url_for, flash, session
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from pytz import timezone, utc
import os, json, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from gspread_formatting import CellFormat, Color, TextFormat, format_cell_range

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key")

# Helper functions
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def send_confirmation_email(to_email, name, q1, q2, q3, q4, lead_lap):
    sender_email = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ Chicago Road Race Challenge – Confirmation"
    msg["From"] = sender_email
    msg["To"] = to_email
    html = f"""
    <html><body>
    <p>Hi {name},</p>
    <p>Thanks for participating in the Cup Car Challenge!</p>
    <ul>
        <li><strong>Chevrolet Driver:</strong> {q1}</li>
        <li><strong>Ford Driver:</strong> {q2}</li>
        <li><strong>Toyota Driver:</strong> {q3}</li>
        <li><strong>Manufacturer Winner:</strong> {q4}</li>
        <li><strong>Cars on Lead Lap:</strong> {lead_lap}</li>
    </ul>
    <p>🏁 Good luck to you and your crew!</p>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, msg.as_string())
    except Exception as e:
        print(f"❌ Email sending failed: {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    with open("driver_list.json") as f:
        driver_data = json.load(f)

    chevy_drivers = driver_data["chevrolet_drivers"]
    ford_drivers = driver_data["ford_drivers"]
    toyota_drivers = driver_data["toyota_drivers"]

    if request.method == "POST":
        entry_name = request.form.get("entry_name", "").strip()
        email = request.form.get("email", "").strip()
        q1_val = request.form.get("q1", "")
        q2_val = request.form.get("q2", "")
        q3_val = request.form.get("q3", "")
        q4 = request.form.get("q4")
        lead_lap = request.form.get("lead_lap", "").strip()

        # Split name and number
        q1_name, q1_number = q1_val.split("|")
        q2_name, q2_number = q2_val.split("|")
        q3_name, q3_number = q3_val.split("|")

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
            ts = datetime.now(utc).astimezone(timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S")

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

            headers = ["Timestamp", "Email", "Entry Name", "Chevy Driver", "Ford Driver", "Toyota Driver", "Manufacturer", "Lead Lap"]
            values = sheet.get_all_values()
            if not values or values[0] != headers:
                sheet.update("A1:H1", [headers])
                header_format = CellFormat(
                    backgroundColor=Color(0.27, 0.27, 0.27),
                    textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1))
                )
                format_cell_range(sheet, "A1:H1", header_format)

            # Save values
            sheet.append_row([
                ts,
                email,
                entry_name,
                f"#{q1_name}",
                f"#{q2_name}",
                f"#{q3_name}",
                q4,
                int(lead_lap)
            ])

            # Email
            send_confirmation_email(email, entry_name, f"#{q1_number} {q1_name}", f"#{q2_number} {q2_name}", f"#{q3_number} {q3_name}", q4, int(lead_lap))

            # Flash + redirect
            flash("✅ Thank you! Your entry has been received and a confirmation email sent.", "success")
            session["summary"] = {
                "name": entry_name,
                "email": email,
                "q1": f"#{q1_number} {q1_name}",
                "q2": f"#{q2_number} {q2_name}",
                "q3": f"#{q3_number} {q3_name}",
                "q4": q4,
                "lead_lap": lead_lap
            }
            return redirect(url_for("thank_you"))

    return render_template("form_select.html", chevy_drivers=chevy_drivers, ford_drivers=ford_drivers, toyota_drivers=toyota_drivers)

@app.route("/thank-you")
def thank_you():
    summary = session.pop("summary", None)
    return render_template("thank_you.html", summary=summary)

if __name__ == "__main__":
    app.run(debug=True)
