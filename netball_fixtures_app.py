import streamlit as st
import pandas as pd
import datetime
import traceback
import random
from collections import defaultdict
from process_fixtures import process_fixtures


st.set_page_config(page_title="Netball Fixtures Generator", layout="wide")
st.title("Netball Fixtures Generator")
st.markdown("""
Upload your configuration and team unavailability files below to generate a fixtures schedule.

**Instructions:**
- Ensure files follow the correct Excel format with all required tabs.
- Main Variables should include StartDate, EndDate, PlayDays, HolidayBlackouts, MatchesPerTeam.
- All dates should be valid and consistent.
""")

# --- Upload Section ---
with st.expander("Upload Required Files", expanded=True):
    league_config = st.file_uploader("Upload League_Configuration.xlsx", type="xlsx", key="league")
    team_unavailability = st.file_uploader("Upload Team_Unavailability.xlsx", type="xlsx", key="unavail")

# --- Rule/Goal Display ---
with st.expander("View Rules and Goals Used in Scheduling"):
    rules_df = pd.read_excel("Fixture_Scheduling_Rules.xlsx", sheet_name=0)
    rules_df_sorted = rules_df.sort_values("ID")
    for _, row in rules_df_sorted.iterrows():
        st.write('RULES COLUMNS FOUND:', rules_df.columns.tolist())
        st.markdown(f"{row['Definition']}")
        st.markdown("---")

# Placeholder for processing output
status_placeholder = st.empty()

# --- Display summary stats placeholder ---
stats_placeholder = st.empty()

# Continue as normal...

# --- Generate Button ---
if league_config and team_unavailability:
    if st.button("Generate Fixture Schedule"):
        fsched, tcal, wbal, log = process_fixtures(league_config, team_unavailability)

        if fsched is not None:
            # Summary Stats
            total_matches = len(fsched)
            total_days = fsched['Date'].nunique()
            total_teams = fsched['Home Team'].nunique() + fsched['Away Team'].nunique()
            stats_placeholder.success(f"✅ {total_matches} matches scheduled across {total_days} play days.")

            output_path = "Netball_Fixture_Output.xlsx"
            with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
                fsched.to_excel(writer, sheet_name="Fixture Schedule", index=False)
                tcal.to_excel(writer, sheet_name="Team Calendars", index=False)
                wbal.to_excel(writer, sheet_name="Weekly Division Balance", index=False)
                log.to_excel(writer, sheet_name="Processing Log", index=False)

            with open(output_path, "rb") as f:
                st.success("Fixtures successfully generated.")
                st.download_button("Download Fixture Schedule", f, file_name=output_path)
        else:
            st.error("Unable to generate fixtures. Check Processing Log below.")
            st.dataframe(log)

elif league_config or team_unavailability:
    st.warning("Please upload both configuration and unavailability files to proceed.")