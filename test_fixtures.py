# test_fixtures.py

import pandas as pd
from datetime import datetime
from netball_fixtures_app import process_fixtures

# Load test data
config_path = "League_Configuration.xlsx"
unavail_path = "Team_Unavailability.xlsx"

print("Running fixture scheduling test...")

# Run fixture processing
test_fixture, test_calendar, test_balance, test_log = process_fixtures(config_path, unavail_path)

# Basic assertions
assert test_fixture is not None, "Fixture generation failed."
assert not test_fixture.empty, "Fixture schedule is empty."
assert test_calendar is not None, "Team calendar not returned."
assert test_balance is not None, "Weekly division balance not returned."
assert test_log is not None, "Processing log not returned."

print("\nFixture Schedule:")
print(test_fixture.head())

print("\nTeam Calendar:")
print(test_calendar.head())

print("\nWeekly Division Balance:")
print(test_balance.head())

print("\nProcessing Log:")
print(test_log.head())

print("\n✅ All basic tests passed.")
