import streamlit as st
import pandas as pd
from io import BytesIO
from process_fixtures import process_fixtures

st.set_page_config(page_title="Netball Fixtures Generator", layout="wide")
st.title("🏐 Netball Fixtures Generator")

st.markdown("Upload your **League_Configuration.xlsx** and **Team_Unavailability.xlsx** files to begin.")

col1, col2 = st.columns(2)

with col1:
    league_config_file = st.file_uploader("League Configuration File", type="xlsx", key="league")
with col2:
    team_unavailability_file = st.file_uploader("Team Unavailability File", type="xlsx", key="unavail")

if league_config_file and team_unavailability_file:
    if st.button("Generate Fixture Schedule"):
        with st.spinner("Generating fixtures, applying rules and goals..."):
            fixtures, calendar, weekly_balance, logs = process_fixtures(league_config_file, team_unavailability_file)

        if fixtures is not None and not fixtures.empty:
            st.success("✅ Fixture generation successful.")

            # Show fixture schedule
            st.subheader("📅 Fixture Schedule")
            st.dataframe(fixtures)

            # Show team calendar
            st.subheader("📖 Team Calendar")
            st.dataframe(calendar)

            # Weekly division balance
            st.subheader("📊 Weekly Division Balance")
            st.dataframe(weekly_balance)

            # Logs
            st.subheader("🛠️ Processing Log")
            st.dataframe(logs)

            # Downloadable Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                fixtures.to_excel(writer, sheet_name="Fixture Schedule", index=False)
                calendar.to_excel(writer, sheet_name="Team Calendar", index=False)
                weekly_balance.to_excel(writer, sheet_name="Weekly Division Balance", index=False)
                logs.to_excel(writer, sheet_name="Processing Log", index=False)
            st.download_button("📥 Download Schedule Workbook", data=output.getvalue(), file_name="Generated_Fixtures.xlsx")

        else:
            st.error("⚠️ Unable to generate fixtures. Check Processing Log below.")
            if logs is not None:
                st.subheader("🛠️ Processing Log")
                st.dataframe(logs)
else:
    st.info("Please upload both input files to enable fixture generation.")
