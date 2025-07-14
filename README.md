# 🏐 Netball Fixtures Generator

This Streamlit web app automates the creation of a forward-looking fixture schedule for a structured netball league.

---

## 📂 Input Files (Required)

Upload the following two Excel files via the UI:

### 1. `League_Configuration.xlsx`
Contains:
- **Main Variables**: Start/End dates, PlayDays, Blackouts, MatchesPerTeam
- **Divisions**: Names of divisions
- **Teams**: Names, division assignment
- **Time Slots**: Courts and match times

### 2. `Team_Unavailability.xlsx`
Contains:
- Dates each team is unavailable for scheduling

---

## ⚙️ Scheduling Rules

Enforces 8 hard rules and applies 4 soft goals, including:
- Match count limits per team
- Blackout & holiday enforcement
- Avoid team clashes and unavailability
- Balance divisions evenly over weeks
- Vary time slots per team

Full list of Rules & Goals viewable inside the app UI.

---

## 📤 Output File

Generates a downloadable Excel workbook with 4 sheets:
1. **Fixture Schedule** – Date/time/court matches by division
2. **Team Calendars** – What each team plays and when
3. **Weekly Division Balance** – Matrix view of division spread per date
4. **Processing Log** – Steps taken, rule decisions, any errors/warnings

---

## 🚀 Run Locally

```bash
pip install -r requirements.txt
streamlit run netball_fixtures_app.py
```

Or deploy directly using [Streamlit Cloud](https://streamlit.io/cloud) and connect your GitHub repo.

---

## 📋 Notes
- Works best when team unavailability is reasonably sparse
- If not all matches can be scheduled, the log will explain how to reduce constraints
- Fully randomised pairing logic per division

---

Built with ❤️ for grassroots league planners.
