
import pandas as pd
import datetime
import random
from collections import defaultdict

def process_fixtures(config_fp, unavail_fp):
    # Read input files
    config = pd.read_excel(config_fp, sheet_name=None)
    unavail = pd.read_excel(unavail_fp)

    main_vars = config['Main Variables'].set_index('Variable')['Value'].to_dict()
    divisions = config['Divisions']
    teams = config['Teams']
    slots = config['Time Slots']

    start_date = pd.to_datetime(main_vars['StartDate'])
    end_date = pd.to_datetime(main_vars['EndDate'])
    play_days = eval(main_vars['PlayDays']) if isinstance(main_vars['PlayDays'], str) else main_vars['PlayDays']
    blackout_dates = set(pd.to_datetime(main_vars['HolidayBlackouts'].split(','))) if isinstance(main_vars['HolidayBlackouts'], str) else set()

    play_dates = pd.date_range(start=start_date, end=end_date, freq='W-SAT')
    play_dates = [d for d in play_dates if d not in blackout_dates]

    matchups = []
    for div in divisions['Division'].unique():
        div_teams = teams[teams['Division'] == div]['Team'].tolist()
        games = [(a, b) for idx, a in enumerate(div_teams) for b in div_teams[idx + 1:]]
        random.shuffle(games)
        matchups.extend([(div, a, b) for a, b in games])

    schedule = []
    slot_cycle = iter(slots.to_dict("records") * len(play_dates))
    date_cycle = iter(play_dates * 5)

    for div, home, away in matchups:
        try:
            match_date = next(date_cycle)
            slot = next(slot_cycle)
            if ((unavail['Team'] == home) & (unavail['Date'] == match_date)).any():
                continue
            if ((unavail['Team'] == away) & (unavail['Date'] == match_date)).any():
                continue
            schedule.append({
                "Date": match_date,
                "Time Slot": slot['Time'],
                "Court": slot['Court'],
                "Division": div,
                "Home Team": home,
                "Away Team": away
            })
        except StopIteration:
            break

    fsched = pd.DataFrame(schedule)

    # Build team calendar
    calendar = pd.concat([
        fsched[['Date', 'Division', 'Home Team', 'Away Team']].rename(columns={"Home Team": "Team", "Away Team": "Opponent"}),
        fsched[['Date', 'Division', 'Away Team', 'Home Team']].rename(columns={"Away Team": "Team", "Home Team": "Opponent"})
    ])
    calendar = calendar.sort_values(by=["Team", "Date"]).reset_index(drop=True)

    # Build weekly balance
    week_div_count = fsched.groupby(['Date', 'Division']).size().unstack(fill_value=0)

    # Log
    log = pd.DataFrame([{"Step": "Fixtures Generated", "Notes": f"{len(fsched)} matches scheduled."}])

    return fsched, calendar, week_div_count, log
