import pandas as pd
import datetime
import traceback
from collections import defaultdict
import random

def process_fixtures(league_config_file, team_unavailability_file):
    log = []
    try:
        xl = pd.ExcelFile(league_config_file)
        main_vars = xl.parse("Main Variables", index_col=0).squeeze()
        divisions = xl.parse("Divisions")
        teams = xl.parse("Teams")
        slots = xl.parse("Time Slots")

        unavail_df = pd.read_excel(team_unavailability_file)

        # --- Config extraction ---
        start_date = pd.to_datetime(main_vars['StartDate']).date()
        end_date = pd.to_datetime(main_vars['EndDate']).date()
        play_days = eval(main_vars['PlayDays']) if isinstance(main_vars['PlayDays'], str) else main_vars['PlayDays']

        # --- Safe parsing of HolidayBlackouts ---
        blackouts = []
        raw_blackouts = main_vars.get('HolidayBlackouts')

        if pd.notna(raw_blackouts):
            if isinstance(raw_blackouts, str):
                try:
                    parsed_dates = pd.to_datetime([d.strip() for d in raw_blackouts.split(',') if d.strip()])
                    blackouts = [d.date() for d in parsed_dates]
                except Exception as e:
                    log.append({"Step": "Parse HolidayBlackouts", "Status": f"⚠️ Failed to parse dates: {e}"})
            elif isinstance(raw_blackouts, (datetime.date, datetime.datetime)):
                blackouts = [raw_blackouts.date() if hasattr(raw_blackouts, 'date') else raw_blackouts]
            else:
                log.append({"Step": "Parse HolidayBlackouts", "Status": "⚠️ Unrecognised HolidayBlackouts format."})

        match_count = int(main_vars.get('MatchesPerTeam', 0))
        log.append({"Step": "Read Config", "Status": "Success"})

        # --- Generate play dates ---
        play_dates = pd.date_range(start=start_date, end=end_date)
        play_dates = [d.date() for d in play_dates if d.strftime('%A') in play_days and d.date() not in blackouts]

        fixture_list = []

        for div in divisions['Division']:
            div_teams = teams[teams['Division'] == div]['Team'].tolist()
            matches = [
                (home, away) for i, home in enumerate(div_teams) for j, away in enumerate(div_teams)
                if i < j
            ]
            random.shuffle(matches)
            fixture_list.extend([(div, home, away) for home, away in matches])

        match_index = 0
        output_rows = []
        for play_date in play_dates:
            daily_slots = slots.copy()
            daily_slots['Date'] = play_date
            # Track matches played per team per day to enforce R1
matches_today = set()

        for _, slot in daily_slots.iterrows():
            while match_index < len(fixture_list):
                div, home, away = fixture_list[match_index]
        
                # --- R1: Check if home or away team already scheduled today
                if (play_date, home) in matches_today or (play_date, away) in matches_today:
                    log.append({
                        "Step": f"R1 Skip ({div} - {home} vs {away})",
                        "Status": f"⚠️ Skipped: One or both teams already scheduled on {play_date}"
                    })
                    match_index += 1
                    continue
        
                output_rows.append({
                    "Date": play_date,
                    "Time Slot": slot['Time'],
                    "Court": slot['Court'],
                    "Division": div,
                    "Home Team": home,
                    "Away Team": away
                })

        matches_today.add((play_date, home))
        matches_today.add((play_date, away))
        match_index += 1
        break  # Move to next slot after successful scheduling


        fixtures_df = pd.DataFrame(output_rows)
        calendar_df = fixtures_df.copy()
        weekly_balance = fixtures_df.groupby(['Date', 'Division']).size().unstack(fill_value=0).reset_index()

        log.append({"Step": "Fixture Generation", "Status": f"Scheduled {len(fixtures_df)} matches."})
        log_df = pd.DataFrame(log)

        return fixtures_df, calendar_df, weekly_balance, log_df

    except Exception as e:
        tb = traceback.format_exc()
        log.append({"Step": "Exception", "Status": f"❌ {e}", "Traceback": tb})
        return None, None, None, pd.DataFrame(log)
