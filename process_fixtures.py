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
        court_capacity = int(main_vars['Courts'])

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

        log.append({"Step": "Read Config", "Status": "Success"})

        # --- Generate play dates ---
        play_dates = pd.date_range(start=start_date, end=end_date)
        play_dates = [d.date() for d in play_dates if d.strftime('%A') in play_days and d.date() not in blackouts]

        fixture_list = []
        required_matches_per_div = {}
        played_pairs = set()  # For Rule 7

        for div in divisions['Division']:
            div_teams = teams[teams['Division'] == div]['Team'].tolist()
            matches = [
                (home, away) for i, home in enumerate(div_teams) for j, away in enumerate(div_teams)
                if i < j
            ]
            required_matches_per_div[div] = len(matches)
            random.shuffle(matches)
            fixture_list.extend([(div, home, away) for home, away in matches])

        remaining_matches = fixture_list.copy()
        output_rows = []
        scheduled_matches = set()
        unscheduled_matches = []

        for play_date in play_dates:
            matches_today = set()
            daily_slots = slots.copy()
            daily_slots['Date'] = play_date

            # --- Rule 6: Enforce court count matches Timeslot data ---
            slot_court_count = daily_slots['Court'].nunique()
            if slot_court_count != court_capacity:
                log.append({"Step": "Rule 6", "Status": f"⚠️ Mismatch in court capacity. Expected {court_capacity}, found {slot_court_count} in Time Slots for {play_date}."})
                continue  # Skip this date as invalid slot config

            for _, slot in daily_slots.iterrows():
                slot_used = False
                for idx, (div, home, away) in enumerate(remaining_matches):

                    # Rule 5: A team may not play itself
                    if home == away:
                        continue

                    # Rule 6: Skip if team is already playing today
                    if home in matches_today or away in matches_today:
                        continue

                    # Rule 1 & 2: Fixture window and PlayDay already enforced by play_date loop

                    # Rule 3: Holiday blackouts already enforced in play_dates generation

                    # Rule 8: Team Unavailability
                    unavailable_home = unavail_df[(unavail_df['Team'] == home) & (unavail_df['Date'] == pd.to_datetime(play_date))]
                    unavailable_away = unavail_df[(unavail_df['Team'] == away) & (unavail_df['Date'] == pd.to_datetime(play_date))]
                    if not unavailable_home.empty or not unavailable_away.empty:
                        continue

                    # Rule 3 (again): Prevent duplicate match on same court/time/date
                    match_id = (div, home, away, play_date, slot['Time'], slot['Court'])
                    if match_id in scheduled_matches:
                        continue

                    # Rule 7: Prevent duplicate match regardless of court/time/date
                    if (div, home, away) in played_pairs or (div, away, home) in played_pairs:
                        continue

                    # Schedule match
                    output_rows.append({
                        "Date": play_date,
                        "Time Slot": slot['Time'],
                        "Court": slot['Court'],
                        "Division": div,
                        "Home Team": home,
                        "Away Team": away
                    })

                    matches_today.update([home, away])
                    scheduled_matches.add(match_id)
                    played_pairs.add((div, home, away))
                    del remaining_matches[idx]
                    slot_used = True
                    break

                if not slot_used:
                    log.append({"Step": "Rule 8", "Status": f"⚠️ No match found for slot {slot['Time']} Court {slot['Court']} on {play_date}"})

        fixtures_df = pd.DataFrame(output_rows)
        calendar_df = fixtures_df.copy()
        weekly_balance = fixtures_df.groupby(['Date', 'Division']).size().unstack(fill_value=0).reset_index()

        # Rule 4: Division validation
        for div, expected in required_matches_per_div.items():
            actual = len(fixtures_df[fixtures_df['Division'] == div])
            if actual < expected:
                log.append({"Step": "Rule 4", "Status": f"⚠️ Division {div} incomplete — scheduled {actual} of {expected} matches."})
            else:
                log.append({"Step": "Rule 4", "Status": f"✅ Division {div} fully scheduled ({actual} matches)."})

        log.append({"Step": "Fixture Generation", "Status": f"✅ Scheduled {len(fixtures_df)} matches with Rules 1–8 enforced."})

        if remaining_matches:
            for div, home, away in remaining_matches:
                log.append({
                    "Step": "Unscheduled",
                    "Status": f"⚠️ Could not schedule match {home} vs {away} in {div}. Reasons could include unavailability, existing match on date, duplicate fixture, or no free slots."
                })

        log_df = pd.DataFrame(log)
        return fixtures_df, calendar_df, weekly_balance, log_df

    except Exception as e:
        tb = traceback.format_exc()
        log.append({"Step": "Exception", "Status": f"❌ {e}", "Traceback": tb})
        return None, None, None, pd.DataFrame(log)
