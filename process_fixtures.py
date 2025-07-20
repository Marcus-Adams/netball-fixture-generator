import pandas as pd
import datetime
import traceback
from collections import defaultdict, Counter
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

        # --- Prioritise Matches By Team Availability Density ---
        def team_availability(team):
            total_available = sum(~unavail_df[unavail_df['Team'] == team]['Date'].isin(play_dates))
            return total_available

        fixtures_to_schedule.sort(key=lambda match: team_availability(match[1]) + team_availability(match[2]))

        scheduled = []
        scheduled_match_ids = set()
        scheduled_pairings = set()
        team_week_map = defaultdict(list)
        team_time_slots = defaultdict(list)
        division_day_counts = defaultdict(lambda: defaultdict(int))
        team_match_dates = defaultdict(list)

        for play_date in play_dates:
            matches_today = set()
            div_today = defaultdict(int)
            for court in court_names:
                for time in slot_times:
                    slot_used = False
                    candidate_matches = sorted(
                        fixtures_to_schedule,
                        key=lambda x: (
                            div_today[x[0]],
                            team_availability(x[1]) + team_availability(x[2]),
                            len([d for d in team_match_dates[x[1]] if abs((play_date - d).days) <= 7]) +
                            len([d for d in team_match_dates[x[2]] if abs((play_date - d).days) <= 7])
                        )
                    )
                    for idx, (div, home, away) in enumerate(candidate_matches):
                        match_id = (div, home, away, play_date, time, court)
                        if home in matches_today or away in matches_today:
                            continue
                        if not unavail_df[(unavail_df['Team'] == home) & (unavail_df['Date'] == pd.to_datetime(play_date))].empty:
                            continue
                        if not unavail_df[(unavail_df['Team'] == away) & (unavail_df['Date'] == pd.to_datetime(play_date))].empty:
                            continue
                        if match_id in scheduled_match_ids:
                            continue
                        if (div, home, away) in scheduled_pairings or (div, away, home) in scheduled_pairings:
                            continue

                        # Goal 1: Default 2 per division, allow 3 only if no other division is underrepresented
                        if div_today[div] >= 3:
                            continue
                        elif div_today[div] >= 2:
                            other_divs_with_less = any(count < 2 for d, count in div_today.items() if d != div)
                            if other_divs_with_less:
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
                        team_week_map[home].append(play_date)
                        team_week_map[away].append(play_date)
                        team_time_slots[home].append(time)
                        team_time_slots[away].append(time)
                        team_match_dates[home].append(play_date)
                        team_match_dates[away].append(play_date)
                        division_day_counts[play_date][div] += 1
                        fixtures_to_schedule.remove((div, home, away))
                        slot_used = True
                        break
                    if not slot_used:
                        log.append({"Step": "Rule 6/7", "Status": f"⚠️ Slot unused on {play_date} {time} {court}"})

        df_sched = pd.DataFrame(scheduled)

        # --- G4: Time Slot Fairness Logging ---
        slot_fairness_log = []
        for team, times in team_time_slots.items():
            count = Counter(times)
            if max(count.values()) > (len(play_dates) // len(slot_times)) + 2:
                slot_fairness_log.append({"Step": "Goal 4", "Status": f"⚠️ {team} appears in same slot too often: {dict(count)}"})

        log.extend(slot_fairness_log)

        # --- G1: Division Match Distribution Logging ---
        for date, divs in division_day_counts.items():
            balanced = all(2 <= v <= 3 for v in divs.values()) and len(divs) == 4
            if balanced:
                log.append({"Step": "Goal 1", "Status": f"✅ {date}: {dict(divs)} matches balanced by division"})
            else:
                log.append({"Step": "Goal 1", "Status": f"⚠️ {date}: {dict(divs)} matches imbalanced by division"})

        # --- Final Checks ---
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
