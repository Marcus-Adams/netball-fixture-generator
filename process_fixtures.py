
import pandas as pd
import datetime
import itertools
import random
from collections import defaultdict

def process_fixtures(league_file, unavailability_file):
    log_entries = []
    try:
        # Read all configuration sheets
        league_xls = pd.ExcelFile(league_file)
        main_vars = league_xls.parse("Main Variables", index_col=0).squeeze()
        divisions = league_xls.parse("Divisions")
        teams = league_xls.parse("Teams")
        time_slots = league_xls.parse("Time Slots")

        log_entries.append(f"✅ Loaded league configuration: {len(divisions)} divisions, {len(teams)} teams")

        unavail = pd.read_excel(unavailability_file)
        log_entries.append(f"✅ Loaded team unavailability for {unavail['Team'].nunique()} teams")

        start_date = pd.to_datetime(main_vars['StartDate'])
        end_date = pd.to_datetime(main_vars['EndDate'])
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
        log.append({"Step": "Parse HolidayBlackouts", "Status": "⚠️ Unrecognised HolidayBlackouts format."}).split(','))] if pd.notna(main_vars['HolidayBlackouts']) else []

        # Generate valid play dates
        play_dates = [d for d in pd.date_range(start=start_date, end=end_date)
                      if d.strftime('%A') in play_days and d.date() not in blackouts]
        log_entries.append(f"📅 Generated {len(play_dates)} valid play dates")

        # Build time slot pool
        slot_pool = []
        for d in play_dates:
            for _, slot in time_slots.iterrows():
                slot_pool.append({
                    "Date": d.date(),
                    "Time Slot": slot['Time'],
                    "Court": slot['Court'],
                    "Slot ID": f"{d.date()}_{slot['Court']}_{slot['Time']}"
                })
        random.shuffle(slot_pool)
        log_entries.append(f"⏱️ Built {len(slot_pool)} total time slots")

        match_list = []
        div_match_counts = {}

        for div in divisions['Division']:
            div_teams = teams[teams['Division'] == div]['Team'].tolist()
            if len(div_teams) < 2:
                log_entries.append(f"⚠️ Skipping division {div} due to insufficient teams")
                continue

            # Full round-robin schedule
            pairs = list(itertools.combinations(div_teams, 2))
            matches = [{"Division": div, "Home Team": h, "Away Team": a} for h, a in pairs]
            match_list.extend(matches)
            div_match_counts[div] = len(matches)
            log_entries.append(f"✅ Generated {len(matches)} matches for division {div}")

        log_entries.append(f"🎯 Total matches to schedule: {len(match_list)}")

        # Scheduling
        scheduled_matches = []
        unscheduled = []
        used_slots = set()

        for match in match_list:
            placed = False
            for slot in slot_pool:
                slot_id = slot["Slot ID"]
                if slot_id in used_slots:
                    continue

                d = slot["Date"]
                t = slot["Time Slot"]
                c = slot["Court"]
                team1 = match["Home Team"]
                team2 = match["Away Team"]

                # Check unavailability
                if ((unavail['Team'] == team1) & (unavail['Date'] == d)).any():
                    continue
                if ((unavail['Team'] == team2) & (unavail['Date'] == d)).any():
                    continue

                # Schedule match
                scheduled_matches.append({
                    "Date": d,
                    "Time": t,
                    "Court": c,
                    "Division": match["Division"],
                    "Home Team": team1,
                    "Away Team": team2
                })
                used_slots.add(slot_id)
                placed = True
                break

            if not placed:
                unscheduled.append(match)

        log_entries.append(f"✅ {len(scheduled_matches)} matches scheduled")
        if unscheduled:
            log_entries.append(f"❌ {len(unscheduled)} matches could not be scheduled")
            for m in unscheduled[:10]:
                log_entries.append(f" - {m['Division']}: {m['Home Team']} vs {m['Away Team']}")

        # Weekly division balance
        wbal = pd.DataFrame(scheduled_matches)
        if not wbal.empty:
            wbal = wbal.groupby(['Date', 'Division']).size().unstack(fill_value=0).reset_index()
        else:
            wbal = pd.DataFrame()

        # Team calendars
        tcal = pd.DataFrame(scheduled_matches)
        if not tcal.empty:
            tcal = tcal.melt(id_vars=["Date", "Division", "Time", "Court"], value_vars=["Home Team", "Away Team"],
                             var_name="Role", value_name="Team").sort_values("Date")
        else:
            tcal = pd.DataFrame()

        # Main schedule
        fsched = pd.DataFrame(scheduled_matches) if scheduled_matches else pd.DataFrame()

        log = pd.DataFrame({"Log": log_entries})
        return fsched, tcal, wbal, log

    except Exception as e:
        error_log = traceback.format_exc()
        return None, None, None, pd.DataFrame({"Log": [str(e), error_log]})
