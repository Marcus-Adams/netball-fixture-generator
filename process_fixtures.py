import pandas as pd
import datetime
import traceback
from collections import defaultdict
import random


def process_fixtures(league_config_file, team_unavailability_file):
    log = []
    try:
        # --- Load Excel Inputs ---
        xl = pd.ExcelFile(league_config_file)
        main_vars = xl.parse("Main Variables", index_col=0).squeeze()
        divisions_df = xl.parse("Divisions")
        teams_df = xl.parse("Teams")
        slots_df = xl.parse("Time Slots")
        unavail_df = pd.read_excel(team_unavailability_file)

        # --- Parse Config Fields (Rules 1–3) ---
        start_date = pd.to_datetime(main_vars['StartDate']).date()
        end_date = pd.to_datetime(main_vars['EndDate']).date()
        play_days = eval(main_vars['PlayDays']) if isinstance(main_vars['PlayDays'], str) else main_vars['PlayDays']

        blackouts = []
        raw_blackouts = main_vars.get('HolidayBlackouts')
        if pd.notna(raw_blackouts):
            try:
                parsed_dates = pd.to_datetime([d.strip() for d in str(raw_blackouts).split(',') if d.strip()])
                blackouts = [d.date() for d in parsed_dates]
            except Exception as e:
                log.append({"Step": "Rule 3", "Status": f"⚠️ Failed to parse HolidayBlackouts: {e}"})

        log.append({"Step": "Rules 1-3", "Status": f"✅ Loaded StartDate {start_date}, EndDate {end_date}, PlayDays {play_days}, Blackouts {blackouts}"})

        # --- Rule 6: Courts & Rule 7: Time Slots ---
        court_names = slots_df['Court'].unique().tolist()
        slot_times = slots_df['Time'].unique().tolist()
        log.append({"Step": "Rule 6 & 7", "Status": f"✅ Found Courts: {court_names}, Time Slots: {slot_times}"})

        # --- Generate Playable Dates (Rules 1–3) ---
        play_dates = pd.date_range(start=start_date, end=end_date)
        play_dates = [d.date() for d in play_dates if d.strftime('%A') in play_days and d.date() not in blackouts]

        # --- Rule 4: Build Fixtures Per Division ---
        fixtures_to_schedule = []
        required_matches = {}
        for div in divisions_df['Division']:
            teams = teams_df[teams_df['Division'] == div]['Team'].tolist()
            matches = [(home, away) for i, home in enumerate(teams) for j, away in enumerate(teams) if i < j]
            fixtures_to_schedule.extend([(div, home, away) for home, away in matches])
            required_matches[div] = len(matches)

        log.append({"Step": "Rule 4", "Status": f"✅ Matches to schedule by division: {required_matches}"})

        scheduled = []
        scheduled_match_ids = set()
        scheduled_pairings = set()
        unscheduled = []

        for play_date in play_dates:
            matches_today = set()
            for court in court_names:
                for time in slot_times:
                    slot_used = False
                    for idx, (div, home, away) in enumerate(fixtures_to_schedule):
                        match_id = (div, home, away, play_date, time, court)

                        # Rule 5: One match per team per week
                        if home in matches_today or away in matches_today:
                            continue

                        # Rule 8: Team Unavailability
                        home_un = unavail_df[(unavail_df['Team'] == home) & (unavail_df['Date'] == pd.to_datetime(play_date))]
                        away_un = unavail_df[(unavail_df['Team'] == away) & (unavail_df['Date'] == pd.to_datetime(play_date))]
                        if not home_un.empty or not away_un.empty:
                            continue

                        # Prevent duplicate match and court/time collision
                        if match_id in scheduled_match_ids:
                            continue
                        if (div, home, away) in scheduled_pairings or (div, away, home) in scheduled_pairings:
                            continue

                        scheduled.append({
                            "Date": play_date,
                            "Time Slot": time,
                            "Court": court,
                            "Division": div,
                            "Home Team": home,
                            "Away Team": away
                        })
                        scheduled_match_ids.add(match_id)
                        scheduled_pairings.add((div, home, away))
                        matches_today.update([home, away])
                        del fixtures_to_schedule[idx]
                        slot_used = True
                        break
                    if not slot_used:
                        log.append({"Step": "Rule 6/7", "Status": f"⚠️ Slot unused on {play_date} {time} {court}"})

        # Retry Logic (Phase 1): Try swapping in unscheduled matches
        for div, home, away in fixtures_to_schedule[:]:
            for i, sched in enumerate(scheduled):
                orig_div, orig_home, orig_away = sched["Division"], sched["Home Team"], sched["Away Team"]
                match_date = sched["Date"]

                # Check if the unscheduled match can be swapped in
                if div != orig_div:
                    continue
                
                same_day_unavailable = not unavail_df[
                    ((unavail_df['Team'] == home) | (unavail_df['Team'] == away)) & (unavail_df['Date'] == pd.to_datetime(match_date))
                ].empty

                if same_day_unavailable:
                    continue

                if (home in [orig_home, orig_away]) or (away in [orig_home, orig_away]):
                    continue  # conflict

                # Execute swap
                scheduled[i]["Home Team"] = home
                scheduled[i]["Away Team"] = away
                scheduled_pairings.add((div, home, away))
                fixtures_to_schedule.remove((div, home, away))
                log.append({"Step": "Retry Logic", "Status": f"✅ Swapped in {home} vs {away} on {match_date} replacing {orig_home} vs {orig_away}"})
                break

        # --- Final Checks for Rule 4 ---
        df_sched = pd.DataFrame(scheduled)
        for div in required_matches:
            actual = len(df_sched[df_sched['Division'] == div])
            expected = required_matches[div]
            if actual < expected:
                log.append({"Step": "Rule 4", "Status": f"⚠️ Division {div} incomplete — scheduled {actual} of {expected} matches."})
            else:
                log.append({"Step": "Rule 4", "Status": f"✅ Division {div} fully scheduled with {actual} matches."})

        for div, home, away in fixtures_to_schedule:
            log.append({"Step": "Rule 8", "Status": f"⚠️ Unscheduled match: {home} vs {away} in {div}"})

        calendar_df = df_sched.copy()
        weekly_balance_df = df_sched.groupby(['Date', 'Division']).size().unstack(fill_value=0).reset_index()
        log.append({"Step": "Final", "Status": f"✅ {len(df_sched)} matches scheduled across {len(play_dates)} play dates."})

        return df_sched, calendar_df, weekly_balance_df, pd.DataFrame(log)

    except Exception as e:
        tb = traceback.format_exc()
        return None, None, None, pd.DataFrame([{"Step": "Exception", "Status": str(e), "Traceback": tb}])
