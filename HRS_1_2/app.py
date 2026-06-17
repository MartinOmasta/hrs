import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from finance import compute_projections, get_ami_for_household_size, HOUSEHOLD_SIZE_FACTORS
from data_loader import load_data, load_google_sheet_with_service_account

st.set_page_config(page_title="VALE Housing Resale Simulator", layout="wide")

st.title("VALE Housing Resale Simulator (HRS) - Prototype")

# ==========================================
# SIDEBAR: DATA SOURCE & GLOBAL DRIVERS
# ==========================================
st.sidebar.header("Data & Inputs")
data_source_selection = st.sidebar.selectbox(
    "Data source",
    [
        "Sample CSV",
        "Upload File",
        "Google Sheet CSV URL",
        "Google Sheet (service account)",
        "Paste Table / DataFrame",
    ],
)

loaded_historical_ami_dataframe = None
if data_source_selection == "Sample CSV":
    loaded_historical_ami_dataframe = load_data("data/sample_data.csv")
    st.sidebar.write("Loaded sample AMI series")
elif data_source_selection == "Upload File":
    user_uploaded_file_buffer = st.sidebar.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if user_uploaded_file_buffer is not None:
        try:
            loaded_historical_ami_dataframe = load_data(user_uploaded_file_buffer)
            st.sidebar.write("Loaded uploaded file")
        except Exception as file_read_error:
            st.sidebar.error(f"Failed to load: {file_read_error}")
            loaded_historical_ami_dataframe = None
elif data_source_selection == "Google Sheet CSV URL":
    public_google_sheet_csv_export_url = st.sidebar.text_input("Public CSV export URL")
    if public_google_sheet_csv_export_url:
        try:
            loaded_historical_ami_dataframe = load_data(public_google_sheet_csv_export_url)
            st.sidebar.write("Loaded Google Sheet CSV")
        except Exception as url_fetch_error:
            st.sidebar.error(f"Failed to load URL: {url_fetch_error}")
            loaded_historical_ami_dataframe = None
elif data_source_selection == "Google Sheet (service account)":
    st.sidebar.markdown("Upload a Google service account JSON key and provide the spreadsheet URL or ID.")
    google_service_account_json_file = st.sidebar.file_uploader("Service account JSON", type=["json"])
    google_spreadsheet_unique_id_or_url = st.sidebar.text_input("Spreadsheet ID or URL")
    google_worksheet_name_or_index = st.sidebar.text_input("Worksheet name or index (optional)", value="0")
    if google_service_account_json_file is not None and google_spreadsheet_unique_id_or_url:
        try:
            import json
            parsed_service_account_credentials_info = json.load(google_service_account_json_file)
            try:
                evaluated_worksheet_selector = int(google_worksheet_name_or_index)
            except Exception:
                evaluated_worksheet_selector = google_worksheet_name_or_index
            try:
                loaded_historical_ami_dataframe = load_google_sheet_with_service_account(
                    parsed_service_account_credentials_info, 
                    google_spreadsheet_unique_id_or_url, 
                    worksheet=evaluated_worksheet_selector
                )
                st.sidebar.write("Loaded spreadsheet via service account")
            except Exception as sheet_access_error:
                st.sidebar.error(f"Failed to load via service account: {sheet_access_error}")
                loaded_historical_ami_dataframe = None
        except Exception as json_parse_error:
            st.sidebar.error(f"Invalid JSON or read error: {json_parse_error}")
            loaded_historical_ami_dataframe = None
else:
    pasted_csv_text_area_input = st.sidebar.text_area("Paste CSV or small table (Year, AMI)")
    if pasted_csv_text_area_input:
        from io import StringIO
        loaded_historical_ami_dataframe = pd.read_csv(StringIO(pasted_csv_text_area_input))
        st.sidebar.write("Loaded pasted data")

st.sidebar.header("Economic Drivers")
annual_market_home_price_inflation_rate = st.sidebar.number_input("Home price inflation %", value=2.7, step=0.1)
annual_median_income_inflation_rate = st.sidebar.number_input("Median income inflation %", value=4.0, step=0.1)
initial_property_unsubsidized_market_value = st.sidebar.number_input("Initial market value", value=348000)
percentage_of_household_income_spent_on_housing = st.sidebar.number_input("Percentage of Income Spent on Housing", value=30, step=1)
base_one_hundred_percent_ami_benchmark = st.sidebar.number_input("100% AMI (4-person household, e.g. Franklin County MA)", value=93100, step=100)

st.sidebar.header("VALE Program Tiers & Household")
fixed_index_tier_percentage = st.sidebar.number_input("Fixed Index % (tier)", value=3.0, step=0.1)
target_affordability_tier_percentage_of_ami = st.sidebar.number_input("Affordability % of AMI", value=80.0, step=1.0)
maximum_allowed_market_share_appreciation_cap = st.sidebar.number_input("Market Share Cap %", value=25.0, step=1.0)
selected_target_household_size_metric = st.sidebar.select_slider("Target household size (for affordability calculation)", options=[1, 2, 3, 4, 5, 6, 7, 8], value=4)
st.sidebar.caption(f"Size factor: {HOUSEHOLD_SIZE_FACTORS.get(selected_target_household_size_metric, 1.0)}")

st.sidebar.header("Financing & Costs")
buyer_mortgage_interest_rate_at_start = st.sidebar.number_input("Mortgage rate (start)", value=6.0, step=0.1)
buyer_mortgage_interest_rate_at_resale = st.sidebar.number_input("Mortgage rate (resale)", value=6.0, step=0.1)
required_downpayment_percentage_of_purchase_price = st.sidebar.number_input("Downpayment %", value=5.0, step=0.1)
future_selling_transaction_cost_percentage = st.sidebar.number_input("Selling cost %", value=6.0, step=0.1)

# =========================================================================
# NEW SECTION: TEMPLATE INPUT VARIABLES (As shown in image_6d4e7f.png)
# =========================================================================
st.sidebar.header("Housing Costs - Other Than Mortgage")
annual_target_household_income = st.sidebar.number_input("Target Annual Income ($)", value=74480)
annual_property_tax_cost = st.sidebar.number_input("Property Taxes Annual ($)", value=3634)
annual_homeowners_insurance_cost = st.sidebar.number_input("Insurance Annual ($)", value=1088)
monthly_homeowners_association_dues = st.sidebar.number_input("Home Owners Association Dues Monthly ($)", value=0)
annual_ground_lease_or_admin_fee = st.sidebar.number_input("Ground Lease or Admin Fee Annual ($)", value=600)
annual_pmi_and_other_miscellaneous_costs = st.sidebar.number_input("PMI, Other Costs Annual ($)", value=1200)

st.sidebar.header("Simulation Time Horizon")
selected_homeowner_holding_period_years = st.sidebar.slider("Holding Period (years)", min_value=1, max_value=30, value=15)
enable_safety_net_floor_protection = st.sidebar.checkbox("Enable Safety Net Floor (no negative proceeds)", value=True)

# Placeholder fields for calculated items from image_6d4e7f.png matrix
monthly_target_household_income = annual_target_household_income / 12
annual_income_available_for_housing = annual_target_household_income * (percentage_of_household_income_spent_on_housing / 100)
monthly_income_available_for_housing = annual_income_available_for_housing / 12

monthly_property_tax_cost = annual_property_tax_cost / 12
monthly_homeowners_insurance_cost = annual_homeowners_insurance_cost / 12
monthly_ground_lease_or_admin_fee = annual_ground_lease_or_admin_fee / 12
monthly_pmi_and_other_miscellaneous_costs = annual_pmi_and_other_miscellaneous_costs / 12

total_other_housing_costs_annual = (
    annual_property_tax_cost + 
    annual_homeowners_insurance_cost + 
    (monthly_homeowners_association_dues * 12) + 
    annual_ground_lease_or_admin_fee + 
    annual_pmi_and_other_miscellaneous_costs
)
total_other_housing_costs_monthly = total_other_housing_costs_annual / 12

# Note: Plug in your exact loan and purchasing formulas down here later
monthly_income_available_for_mortgage_payment = monthly_income_available_for_housing - total_other_housing_costs_monthly
simulated_maximum_loan_amount_allowed = 219911 
simulated_buyer_downpayment_amount = 11574
outside_affordability_gap_secondary_loan = 0
simulated_affordable_purchase_price = 231485
simulated_affordability_gap_subsidy_required = initial_property_unsubsidized_market_value - simulated_affordable_purchase_price

# Execute core projections engine function
if 'loaded_historical_ami_dataframe' in locals() and loaded_historical_ami_dataframe is not None:
    try:
        base_one_hundred_percent_ami_benchmark = float(loaded_historical_ami_dataframe.loc[0, 'AMI'])
    except Exception:
        pass

simulation_output_projections_dataframe = compute_projections(
    initial_market_value=initial_property_unsubsidized_market_value,
    holding_period_years=selected_homeowner_holding_period_years,
    market_inflation_rate=annual_market_home_price_inflation_rate,
    fixed_index_rate=fixed_index_tier_percentage,
    affordability_pct_of_ami=target_affordability_tier_percentage_of_ami,
    ami_initial=base_one_hundred_percent_ami_benchmark,
    household_size=selected_target_household_size_metric,
    mortgage_rate_start=buyer_mortgage_interest_rate_at_start,
    mortgage_rate_resale=buyer_mortgage_interest_rate_at_resale,
    downpayment_pct=required_downpayment_percentage_of_purchase_price,
    selling_cost_pct=future_selling_transaction_cost_percentage,
    #property_tax_pct=property_tax_pct_placeholder_fix_later,  # Override with template fields when plugging calculations
    #insurance_pct=insurance_pct_placeholder_fix_later,        # Override with template fields when plugging calculations
    hoa_monthly=monthly_homeowners_association_dues,
    ground_lease=annual_ground_lease_or_admin_fee / 12,
    other_costs=annual_pmi_and_other_miscellaneous_costs,
    median_income_inflation=annual_median_income_inflation_rate,
    safety_net_floor=enable_safety_net_floor_protection,
    market_share_cap_pct=maximum_allowed_market_share_appreciation_cap,
)

# ==========================================
# MAIN INTERFACE DISPLAY
# ==========================================
st.subheader("Affordability Snapshot")
st.text_area(
    label="Calculated Monthly Income Available For Housing Expense:", 
    value=f"${monthly_income_available_for_housing:,.2f} per month", 
    height=70, 
    disabled=True
)

# Explicitly named columns instead of shorthand col1/col2 layout
left_hand_side_wealth_accumulation_column, right_hand_side_community_affordability_column = st.columns(2)

with left_hand_side_wealth_accumulation_column:
    st.subheader("Homeowner Net Proceeds (Fixed vs Market)")
    homeowner_net_proceeds_scatter_plot = go.Figure()
    homeowner_net_proceeds_scatter_plot.add_trace(go.Scatter(x=simulation_output_projections_dataframe['Year'], y=simulation_output_projections_dataframe['ProceedsAtSaleMarket'], mode='lines+markers', name='Proceeds at Sale (Market)', line=dict(color='royalblue')))
    homeowner_net_proceeds_scatter_plot.add_trace(go.Scatter(x=simulation_output_projections_dataframe['Year'], y=simulation_output_projections_dataframe['ProceedsAtSaleFixed'], mode='lines+markers', name='Proceeds at Sale (Fixed)', line=dict(color='firebrick')))
    homeowner_net_proceeds_scatter_plot.update_layout(xaxis_title='Years', yaxis_title='Proceeds at Sale ($)')
    st.plotly_chart(homeowner_net_proceeds_scatter_plot, use_container_width=True)

with right_hand_side_community_affordability_column:
    st.subheader("Community Affordability (Market vs Fixed)")
    community_affordability_gap_bar_chart = go.Figure()
    community_affordability_gap_bar_chart.add_trace(go.Bar(x=simulation_output_projections_dataframe['Year'], y=simulation_output_projections_dataframe['MarketValue'], name='Market Value', marker_color='lightgray'))
    community_affordability_gap_bar_chart.add_trace(go.Bar(x=simulation_output_projections_dataframe['Year'], y=simulation_output_projections_dataframe['FixedPriceCapped'], name='Fixed Resale Price', marker_color='green'))
    community_affordability_gap_bar_chart.add_trace(go.Scatter(x=simulation_output_projections_dataframe['Year'], y=simulation_output_projections_dataframe['AffordabilityBound'], name='Affordability Bound (AMI %)', line=dict(color='navy', dash='dash')))
    community_affordability_gap_bar_chart.update_layout(barmode='group', xaxis_title='Years', yaxis_title='Price ($)')
    st.plotly_chart(community_affordability_gap_bar_chart, use_container_width=True)

st.subheader("Yearly Proceeds Detail")
explicit_report_dataframe_columns_to_display = [
    'Year',
    'MarketValue',
    'FixedPriceCapped',
    'ProceedsAtSaleMarket',
    'ProceedsAtSaleFixed',
    'EquityGainMarket',
    'EquityGainFixed',
    'NetCashflowChangeMarket',
    'AffordabilityBound'
]
st.dataframe(simulation_output_projections_dataframe[explicit_report_dataframe_columns_to_display])

# Export Data Utility
raw_output_csv_binary_data = simulation_output_projections_dataframe.to_csv(index=False).encode('utf-8')
st.download_button("Download projections CSV", data=raw_output_csv_binary_data, file_name='projections.csv', mime='text/csv')

st.markdown("---")
st.info('Financial calculations are provisional. See finance.py comments for assumptions that should be reviewed or updated by experts.')