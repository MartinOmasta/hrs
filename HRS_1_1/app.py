import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from finance import compute_projections, HOUSEHOLD_SIZE_FACTORS

st.set_page_config(page_title="VALE Housing Resale Simulator", layout="wide")

st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] .main .block-container {
            max-width: 98% !important; padding-top: 2rem !important;
            padding-bottom: 2rem !important; padding-left: 1rem !important; padding-right: 1rem !important;
        }
        div[data-testid="stPlotlyChart"] { width: 100% !important; }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary *,
        [data-testid="stSidebar"] [data-testid="stExpander"] .streamlit-expanderHeader,
        [data-testid="stSidebar"] [data-testid="stExpander"] .streamlit-expanderHeader * {
            font-size: 1.3rem !important; font-weight: 800 !important; color: #1A1A1A !important;
        }
        /* Custom Tooltip styling for Streamlit native sidebar tooltips */
        div[data-testid="stTooltipContent"] {
            background-color: #2D3748 !important; /* Sleek slate-dark gray */
            color: #FFFFFF !important;
        }
        
        /* --- KITCHEN SINK DROPDOWN MENU FIXES --- */
        /* 1. Target the popover container */
        div[data-baseweb="popover"] > div,
        div[data-baseweb="popover"] > div > div,
        div[data-testid="stPopoverBody"] {
            width: max-content !important;
            min-width: 450px !important;
            max-width: 95vw !important;
        }
        
        /* 2. Target the unordered list inside the popover */
        ul[data-baseweb="menu"],
        div[data-baseweb="popover"] ul {
            width: max-content !important;
            min-width: 100% !important;
            overflow-x: hidden !important;
        }
        
        /* 3. Target the list items to allow full text display (wrap or expand) */
        li[data-baseweb="menu-item"],
        div[data-baseweb="popover"] li {
            width: max-content !important;
            min-width: 100% !important;
            white-space: normal !important; /* Allows wrapping instead of truncating */
            word-wrap: break-word !important;
            overflow: visible !important;
            text-overflow: clip !important;
            padding-right: 20px !important;
        }
        
        /* 4. Target spans inside the list items */
        li[data-baseweb="menu-item"] span,
        div[data-baseweb="popover"] li span,
        div[data-baseweb="popover"] span[title] {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }
        
        /* 5. Force the widget's closed input display box to show text if possible */
        div[data-baseweb="select"] div[text-overflow="ellipsis"] {
            text-overflow: clip !important;
            white-space: normal !important;
            overflow: visible !important;
        }
    </style>
    """, unsafe_allow_html=True)

st.title("VALE Housing Resale Simulator (HRS) - Prototype")

#############################################################################################################
# Color Definitions & Handlers
#############################################################################################################
SCENARIO_COLOR_OPTIONS = {
    '💙 Blue': '#636EFA',
    '❤️ Red': '#EF553B',
    '💚 Green': '#00CC96',
    '💜 Purple': '#AB63FA',
    '🧡 Orange': '#FFA15A',
    '🩵 Cyan': '#19D3F3'
}

SCENARIO_COLORS_LIST = list(SCENARIO_COLOR_OPTIONS.keys())

def handle_color_change(changed_scen, old_color):
    """Handles color swaps and reassignments dynamically via on_change callback."""
    new_color = st.session_state[f"color_select_{changed_scen}"]
    if new_color == old_color:
        return
    
    # Identify if another scenario is already using the newly selected color
    conflicts = [s for s in st.session_state.scenarios if s != changed_scen and st.session_state.scenario_colors.get(s) == new_color]
    
    if conflicts:
        conflict_scen = conflicts[0]
        if len(st.session_state.scenarios) < 6:
            # Reassign the conflicting scenario to an unused color
            used_colors = [st.session_state.scenario_colors[s] for s in st.session_state.scenarios if s != conflict_scen and s != changed_scen]
            used_colors.append(new_color)
            available = [c for c in SCENARIO_COLORS_LIST if c not in used_colors]
            if available:
                st.session_state.scenario_colors[conflict_scen] = available[0]
                st.session_state[f"color_select_{conflict_scen}"] = available[0]
        else:
            # Swap colors between the two scenarios
            st.session_state.scenario_colors[conflict_scen] = old_color
            st.session_state[f"color_select_{conflict_scen}"] = old_color
    
    # Update state for the scenario that triggered the change
    st.session_state.scenario_colors[changed_scen] = new_color

#############################################################################################################
# Section 1: Sidebar Setup
#############################################################################################################
st.sidebar.markdown("*Note: Base values here are overridden by any identical variables established in the Scenario Matrix.*")

with st.sidebar.expander("**🏡 Property Value - Initial & Ongoing**", expanded=True):
    initial_market_value = st.number_input("Property Asking Price $", value=348000, format="%d", help="Unrestricted open-market appraisal or initial listing price.")
    initial_affordability_pct_of_ami = st.number_input("Prospective Buyer Income Target (% of AMI)", value=80.0, step=10.0, help="Based on regional HUD AMI tables for this Property's area - what is the intended range that this property it targeted for?")
    initial_market_home_price_inflation_rate = st.number_input("Home price inflation %", value=7.1, step=0.1, help="Expected annual percentage increase in open-market home prices.")
    initial_area_median_income_inflation = st.number_input("Area Median Income (AMI) inflation %", value=4.0, step=0.1, help="Expected annual percentage increase in the Area Median Income (AMI).")
    initial_perc_income_spent_on_housing = st.number_input("Percentage of Income Spent on Housing %", value=30, step=1, help="The maximum percentage of gross household income allowed to be spent on housing costs (typically 30%).")

with st.sidebar.expander("**📈 VALE Program Tiers & Household**", expanded=True):
    initial_ami_four_person_dollar_amount = st.number_input("100% Area Median Income for 4-person household", value=93100, step=100, help="The baseline 100% AMI dollar amount for a household of four in the local region.")
    initial_vale_resale_fixed_index_pct = st.number_input("Fixed Index % Increase (tier)", value=3.0, step=0.1, help="The fixed annual percentage rate at which the restricted resale price increases.")
    initial_household_size = st.select_slider("Target household size", options=[1, 2, 3, 4, 5, 6, 7, 8], value=4, help="The size of the household used to adjust the AMI for calculating affordability.")

with st.sidebar.expander("**💸 Financing & Costs**", expanded=True):
    initial_mortgage_rate = st.number_input("Mortgage rate (Initial Buyer)", value=6.0, step=0.1, help="The interest rate on the first buyer's mortgage loan.")
    resale_mortgage_rate = st.number_input("Mortgage rate (Resale Buyer)", value=6.0, step=0.1, help="The projected interest rate on a future buyer's mortgage loan.")
    initial_downpayment_pct = st.number_input("Downpayment %", value=5.0, step=0.1, help="The percentage of the purchase price the buyer pays upfront.")
    initial_closing_cost_pct = st.number_input("Closing Costs %", value=3.0, step=0.1, help="Estimated buyer closing costs as a percentage of the purchase price.")
    resale_selling_cost_pct = st.number_input("Selling cost %", value=7.0, step=0.1, help="Estimated costs (e.g., realtor fees, repairs) for the seller at resale, as a percentage of the sale price.")
    initial_length_of_mortgage_years = st.selectbox(label="Length of Mortage (Years)", options=[10, 15, 20, 30, 40], index=3, help="The term length of the mortgage loan in years.")
    using_FHA_loan = st.checkbox("**FHA Loan**: Buyer is using FHA Loan", value=False, help="Check if the buyer is utilizing an FHA loan (affects PMI drop-off rules).")

with st.sidebar.expander("**⚖️ Taxes & Fees**", expanded=True):
    initial_property_tax_pct_annual = st.number_input("Property tax % Annual", value=1.570, step=0.001, format="%.3f", help="The annual property tax rate as a percentage of the assessed value.")
    initial_insurance_pct_annual = st.number_input("Insurance % Annual", value=0.470, step=0.001, format="%.3f", help="The annual homeowner's insurance premium as a percentage of the home's value.")
    initial_hoa_monthly = st.number_input("HOA monthly $", value=0, help="Monthly Homeowners Association (HOA) dues, if applicable.")
    initial_ground_lease_monthly = st.number_input("Ground lease monthly $", value=50, help="Monthly fee paid to the land trust for the ground lease.")
    initial_pmi_financing_fees_monthly = st.number_input("PMI or Additional monthly fees $", value=100.0, help="Monthly Private Mortgage Insurance (PMI) or other recurring financing fees.")
    property_tax_based_on_affordable_price = st.checkbox("**Tax Basis**: Tax calculated on Affordable Price?", value=True, help="If checked, property taxes are assessed on the restricted affordable value rather than the market value.")
    insurance_based_on_affordable_price = st.checkbox("**Insurance Basis**: Insurance calculated on Affordable Price?", value=False, help="If checked, insurance premiums are based on the affordable restricted price.")

with st.sidebar.expander("**🫴🪙Outside Subsidy**", expanded=True):
    initial_downpayment_assistance_amount = st.number_input("Downpayment Assistance (DPA) $ Amount", value=0, step=10, help="Total grant or assistance funds provided to help with the buyer's downpayment.")
    initial_downpayment_assistance_covers_buyer_contribution_check = st.checkbox("**DPA**: Covers Buyer's Contribution", value=True, help="If checked, the assistance funds go towards fulfilling the buyer's minimum required downpayment.")
    initial_affordability_gap_amount = st.number_input("Affordability Gap $ Amount", value=0, step=10, help="Amount of outside subsidy or gap funding already secured for the project.")

with st.sidebar.expander("**⚙️Simulation**", expanded=True):
    initial_holding_period_years = st.slider("Holding Period (years)", min_value=1, max_value=40, value=15, help="The number of years the initial buyer holds the property before selling.")
    vale_resale_capped = st.checkbox("**CAP**: Prevent Resale Formula Proceeds from Exceeding Market", value=True, help="Prevents the calculated resale price from exceeding the unrestricted open-market value.")
    subtract_sunk_costs = st.checkbox("**NET POSITION**: Subtract sunk living costs from Wealth Built", value=False, help="Subtracts non-recoverable costs (taxes, insurance, interest, etc.) from the seller's final wealth calculation.")
    cost_model = st.radio("Housing Cost Model", options=["Realistic (Market-Tied & Static Fees)", "Idealized (Flat Affordability)"], index=0, help="Realistic ties insurance to market value and calculates actual FHA/Conventional PMI drop-offs. Idealized perfectly scales all costs with AMI.")
    adjust_for_inflation = st.checkbox("Adjust Values for Inflation (Present Value)", value=False, help="Display future financial returns in today's purchasing power.")
    general_inflation_rate = st.number_input("General Economic Inflation Rate (%)", value=2.5, step=0.1, help="The assumed annual rate of general economic inflation used to calculate present value.")


#############################################################################################################
# Section 1.5: Scenario Matrix Manager (Dynamic Widget Grid)
#############################################################################################################
st.subheader("Scenario Matrix")
st.write("Add variable rows to the matrix to override the global sidebar defaults for specific scenarios.")

# 1. Define all available sidebar variables and their exact properties
ALL_VARIABLES = {
    "initial_market_value": {"label": "Property Asking Price $", "type": "number", "default": 348000, "step": 1000},
    "initial_affordability_pct_of_ami": {"label": "Prospective Buyer Income Target (% of AMI)", "type": "number", "default": 80.0, "step": 10.0},
    "initial_market_home_price_inflation_rate": {"label": "Home price inflation %", "type": "number", "default": 7.1, "step": 0.1},
    "initial_area_median_income_inflation": {"label": "Area Median Income (AMI) inflation %", "type": "number", "default": 4.0, "step": 0.1},
    "initial_perc_income_spent_on_housing": {"label": "Percentage of Income Spent on Housing %", "type": "number", "default": 30, "step": 1},
    "initial_ami_four_person_dollar_amount": {"label": "100% AMI for 4-person household", "type": "number", "default": 93100, "step": 100},
    "initial_vale_resale_fixed_index_pct": {"label": "Fixed Index % Increase (tier)", "type": "number", "default": 3.0, "step": 0.1},
    "initial_household_size": {"label": "Target household size", "type": "select", "options": [1, 2, 3, 4, 5, 6, 7, 8], "default": 4},
    "initial_mortgage_rate": {"label": "Mortgage rate (Initial Buyer)", "type": "number", "default": 6.0, "step": 0.1},
    "resale_mortgage_rate": {"label": "Mortgage rate (Resale Buyer)", "type": "number", "default": 6.0, "step": 0.1},
    "initial_downpayment_pct": {"label": "Downpayment %", "type": "number", "default": 5.0, "step": 0.1},
    "initial_closing_cost_pct": {"label": "Closing Costs %", "type": "number", "default": 3.0, "step": 0.1},
    "resale_selling_cost_pct": {"label": "Selling cost %", "type": "number", "default": 7.0, "step": 0.1},
    "initial_length_of_mortgage_years": {"label": "Length of Mortage (Years)", "type": "select", "options": [10, 15, 20, 30, 40], "default": 30},
    "using_FHA_loan": {"label": "FHA Loan: Buyer is using FHA Loan", "type": "checkbox", "default": False},
    "initial_property_tax_pct_annual": {"label": "Property tax % Annual", "type": "number", "default": 1.570, "step": 0.001, "format": "%.3f"},
    "initial_insurance_pct_annual": {"label": "Insurance % Annual", "type": "number", "default": 0.470, "step": 0.001, "format": "%.3f"},
    "initial_hoa_monthly": {"label": "HOA monthly $", "type": "number", "default": 0, "step": 10},
    "initial_ground_lease_monthly": {"label": "Ground lease monthly $", "type": "number", "default": 50, "step": 10},
    "initial_pmi_financing_fees_monthly": {"label": "PMI or Additional monthly fees $", "type": "number", "default": 100.0, "step": 10.0},
    "property_tax_based_on_affordable_price": {"label": "Tax Basis: Tax calculated on Affordable Price?", "type": "checkbox", "default": True},
    "insurance_based_on_affordable_price": {"label": "Insurance Basis: Insurance calculated on Affordable Price?", "type": "checkbox", "default": False},
    "initial_downpayment_assistance_amount": {"label": "Downpayment Assistance (DPA) $ Amount", "type": "number", "default": 0, "step": 10},
    "initial_downpayment_assistance_covers_buyer_contribution_check": {"label": "DPA: Covers Buyer's Contribution", "type": "checkbox", "default": True},
    "initial_affordability_gap_amount": {"label": "Affordability Gap $ Amount", "type": "number", "default": 0, "step": 10},
    "initial_holding_period_years": {"label": "Holding Period (years)", "type": "number", "default": 15, "min": 1, "max": 40, "step": 1},
    "vale_resale_capped": {"label": "CAP: Prevent Resale Formula Proceeds from Exceeding Market", "type": "checkbox", "default": True},
    "subtract_sunk_costs": {"label": "NET POSITION: Subtract sunk living costs from Wealth Built", "type": "checkbox", "default": False},
    "cost_model": {"label": "Housing Cost Model", "type": "select", "options": ["Realistic (Market-Tied & Static Fees)", "Idealized (Flat Affordability)"], "default": "Realistic (Market-Tied & Static Fees)"},
    "adjust_for_inflation": {"label": "Adjust Values for Inflation (Present Value)", "type": "checkbox", "default": False},
    "general_inflation_rate": {"label": "General Economic Inflation Rate (%)", "type": "number", "default": 2.5, "step": 0.1}
}

# 2. Initialize Matrix State
if "scenarios" not in st.session_state:
    st.session_state.scenarios = ['Base Economic Scenario', 
                                  'Flat Housing Market', 
                                  'Housing Market Price Spike', 
                                  'Housing Price Bust', 
                                  'Wage Stagnation & Housing Prices Spike']
    
if "matrix_data" not in st.session_state:
    st.session_state.matrix_data = {scen: {} for scen in st.session_state.scenarios}
    defaults_mapping = {
        'Base Economic Scenario': {"initial_holding_period_years": 40, "initial_market_home_price_inflation_rate": 7.1, "initial_area_median_income_inflation": 4.0, "general_inflation_rate": 2.5, "initial_mortgage_rate": 6.0, "resale_mortgage_rate": 6.0},
        'Flat Housing Market': {"initial_holding_period_years": 40, "initial_market_home_price_inflation_rate": 1.0, "initial_area_median_income_inflation": 3.0, "general_inflation_rate": 2.5, "initial_mortgage_rate": 6.0, "resale_mortgage_rate": 6.0},
        'Housing Market Price Spike': {"initial_holding_period_years": 40, "initial_market_home_price_inflation_rate": 9.0, "initial_area_median_income_inflation": 4.0, "general_inflation_rate": 2.5, "initial_mortgage_rate": 6.0, "resale_mortgage_rate": 6.0},
        'Housing Price Bust': {"initial_holding_period_years": 40, "initial_market_home_price_inflation_rate": -4.0, "initial_area_median_income_inflation": 3.0, "general_inflation_rate": 2.5, "initial_mortgage_rate": 6.0, "resale_mortgage_rate": 6.0},
        'Wage Stagnation & Housing Prices Spike': {"initial_holding_period_years": 40, "initial_market_home_price_inflation_rate": 9.0, "initial_area_median_income_inflation": 0.5, "general_inflation_rate": 2.5, "initial_mortgage_rate": 12.0, "resale_mortgage_rate": 6.0}
    }
    for sc, vals in defaults_mapping.items():
        st.session_state.matrix_data[sc] = vals

if "active_variables" not in st.session_state:
    st.session_state.active_variables = [
        "initial_holding_period_years", "initial_market_home_price_inflation_rate", 
        "initial_area_median_income_inflation", "general_inflation_rate", 
        "initial_mortgage_rate", "resale_mortgage_rate"
    ]

if "scenario_colors" not in st.session_state:
    st.session_state.scenario_colors = {}
    for i, sc in enumerate(st.session_state.scenarios):
        st.session_state.scenario_colors[sc] = SCENARIO_COLORS_LIST[i % len(SCENARIO_COLORS_LIST)]

# Initialize trackers to retain non-visible CSV uploaded variables for specific scenarios 
if "uploaded_scenarios" not in st.session_state:
    st.session_state.uploaded_scenarios = []

if "csv_uploaded_keys" not in st.session_state:
    st.session_state.csv_uploaded_keys = {}

# Initialize global active legend items tracker
if "visible_legend_items" not in st.session_state:
    st.session_state.visible_legend_items = []
    for sc in st.session_state.scenarios:
        st.session_state.visible_legend_items.extend([f"{sc} (Market)", f"{sc} (Fixed)", f"{sc} (AMI)"])

# 3. Controls to Add/Remove Scenarios and Variables

# Row 1: Scenario Controls
row1_cols = st.columns(3)
with row1_cols[0]:
    with st.form("add_scen_form", clear_on_submit=True):
        new_scen = st.text_input("New Scenario Name (Maximum of 6 Scenarios):", placeholder="E.g., High Taxes")
        submitted = st.form_submit_button("➕ Add Scenario")
        if submitted:
            if len(st.session_state.scenarios) >= 6:
                st.warning("You've reached the maximum of 6 scenarios! Please remove one before adding another.", icon="⚠️")
            elif new_scen and new_scen not in st.session_state.scenarios:
                st.session_state.scenarios.append(new_scen)
                
                # Copy ONLY the active variables from scenario 0 so that unlisted variables track sidebar defaults
                new_scen_data = {}
                for var in st.session_state.active_variables:
                    if var in st.session_state.matrix_data[st.session_state.scenarios[0]]:
                        new_scen_data[var] = st.session_state.matrix_data[st.session_state.scenarios[0]][var]
                st.session_state.matrix_data[new_scen] = new_scen_data
                
                # Intelligent color assignment upon addition
                used_colors = list(st.session_state.scenario_colors.values())
                available_colors = [c for c in SCENARIO_COLORS_LIST if c not in used_colors]
                assigned_color = available_colors[0] if available_colors else SCENARIO_COLORS_LIST[(len(st.session_state.scenarios) - 1) % len(SCENARIO_COLORS_LIST)]
                
                st.session_state.scenario_colors[new_scen] = assigned_color
                st.session_state[f"color_select_{new_scen}"] = assigned_color
                
                # Auto-append new scenario to active legend items
                st.session_state.visible_legend_items.extend([f"{new_scen} (Market)", f"{new_scen} (Fixed)", f"{new_scen} (AMI)"])
                st.rerun()

with row1_cols[1]:
    uploaded_file = st.file_uploader("Upload Scenario (.csv)", type=["csv"], label_visibility="visible")
    if uploaded_file is not None:
        if st.button("📥 Upload Scenario", use_container_width=True):
            try:
                df_in = pd.read_csv(uploaded_file)
                if "Scenario_Name" in df_in.columns:
                    scenarios_in_file = df_in["Scenario_Name"].unique()
                else:
                    scenarios_in_file = ["Uploaded Scenario"]
                    
                for scen_in in scenarios_in_file:
                    if len(st.session_state.scenarios) >= 6:
                        st.warning("Reached maximum of 6 scenarios. Some were skipped.")
                        break
                        
                    base_name = str(scen_in)
                    
                    scen_name_to_add = base_name
                    counter = 1
                    while scen_name_to_add in st.session_state.scenarios:
                        scen_name_to_add = f"{base_name} {counter}"
                        counter += 1
                    
                    st.session_state.scenarios.append(scen_name_to_add)
                    st.session_state.matrix_data[scen_name_to_add] = {}
                    
                    if scen_name_to_add not in st.session_state.uploaded_scenarios:
                        st.session_state.uploaded_scenarios.append(scen_name_to_add)
                    st.session_state.csv_uploaded_keys[scen_name_to_add] = []
                    
                    # Assign available color
                    used_colors = list(st.session_state.scenario_colors.values())
                    available_colors = [c for c in SCENARIO_COLORS_LIST if c not in used_colors]
                    assigned_color = available_colors[0] if available_colors else SCENARIO_COLORS_LIST[(len(st.session_state.scenarios) - 1) % len(SCENARIO_COLORS_LIST)]
                    
                    st.session_state.scenario_colors[scen_name_to_add] = assigned_color
                    st.session_state[f"color_select_{scen_name_to_add}"] = assigned_color
                    
                    # Auto-append uploaded scenario to active legend items
                    st.session_state.visible_legend_items.extend([f"{scen_name_to_add} (Market)", f"{scen_name_to_add} (Fixed)", f"{scen_name_to_add} (AMI)"])
                    
                    if "Scenario_Name" in df_in.columns:
                        row_data = df_in[df_in["Scenario_Name"] == scen_in].iloc[0]
                    else:
                        row_data = df_in.iloc[0]
                    
                    # Apply ALL variables found in the CSV file regardless of active visibility 
                    for var in ALL_VARIABLES.keys():
                        if var in row_data.index:
                            val = row_data[var]
                            if pd.isna(val):
                                continue # Skip mapping NaN to allow fallback
                                
                            st.session_state.csv_uploaded_keys[scen_name_to_add].append(var)
                            var_type = ALL_VARIABLES[var]["type"]
                            
                            if var_type == "checkbox":
                                if str(val).lower() in ['false', '0', 'no', 'nan', 'none']:
                                    st.session_state.matrix_data[scen_name_to_add][var] = False
                                else:
                                    st.session_state.matrix_data[scen_name_to_add][var] = True
                            elif var_type == "number":
                                try:
                                    if isinstance(ALL_VARIABLES[var]["default"], float):
                                        st.session_state.matrix_data[scen_name_to_add][var] = float(val)
                                    else:
                                        st.session_state.matrix_data[scen_name_to_add][var] = int(float(val))
                                except ValueError:
                                    pass # Keep default if parsing fails
                            elif var_type == "select":
                                if val in ALL_VARIABLES[var]["options"]:
                                    st.session_state.matrix_data[scen_name_to_add][var] = val
                                else:
                                    try:
                                        num_val = int(float(val))
                                        if num_val in ALL_VARIABLES[var]["options"]:
                                            st.session_state.matrix_data[scen_name_to_add][var] = num_val
                                    except:
                                        pass
                st.rerun()
            except Exception as e:
                st.error(f"Failed to read CSV file: {e}")

with row1_cols[2]:
    with st.form("del_scen_form"):
        to_remove_scen = st.selectbox("Remove Scenario:", options=st.session_state.scenarios)
        if st.form_submit_button("🗑️ Remove Scenario") and len(st.session_state.scenarios) > 1:
            st.session_state.scenarios.remove(to_remove_scen)
            del st.session_state.matrix_data[to_remove_scen]
            if to_remove_scen in st.session_state.scenario_colors:
                del st.session_state.scenario_colors[to_remove_scen]
            if f"color_select_{to_remove_scen}" in st.session_state:
                del st.session_state[f"color_select_{to_remove_scen}"]
            if to_remove_scen in st.session_state.uploaded_scenarios:
                st.session_state.uploaded_scenarios.remove(to_remove_scen)
            if to_remove_scen in st.session_state.csv_uploaded_keys:
                del st.session_state.csv_uploaded_keys[to_remove_scen]
                
            # Strip out removed scenario items from active legend list
            st.session_state.visible_legend_items = [
                item for item in st.session_state.visible_legend_items 
                if not item.startswith(f"{to_remove_scen} (")
            ]
            st.rerun()

st.write("") # Spacer

# Row 2: Variable Controls
row2_cols = st.columns(2)
with row2_cols[0]:
    with st.form("add_var_form"):
        available_vars = {k: v["label"] for k, v in ALL_VARIABLES.items() if k not in st.session_state.active_variables}
        new_var_key = st.selectbox(
            "Select a variable to add:", 
            options=list(available_vars.keys()), 
            format_func=lambda x: available_vars[x]
        )
        if st.form_submit_button("➕ Add Variable Row") and new_var_key:
            st.session_state.active_variables.append(new_var_key)
            for sc in st.session_state.scenarios:
                # Set fallback default ONLY if a background value wasn't already stored by a CSV upload 
                if new_var_key not in st.session_state.matrix_data[sc]:
                    st.session_state.matrix_data[sc][new_var_key] = ALL_VARIABLES[new_var_key]["default"]
            st.rerun()

with row2_cols[1]:
    with st.form("del_var_form"):
        to_remove_var = st.selectbox("Remove Row Variable:", options=st.session_state.active_variables, format_func=lambda x: ALL_VARIABLES[x]["label"])
        if st.form_submit_button("🗑️ Remove Row Variable"):
            st.session_state.active_variables.remove(to_remove_var)
            st.rerun()

# 4. Render the Interactive Matrix Grid
st.markdown("---")

grid_cols = st.columns([1.5] + [1] * len(st.session_state.scenarios))
grid_cols[0].markdown("**Variable**")
for i, sc in enumerate(st.session_state.scenarios):
    grid_cols[i+1].markdown(f"**{sc}**")

# Scenario Color Row 
color_cols = st.columns([1.5] + [1] * len(st.session_state.scenarios))
color_cols[0].markdown("<div style='padding-top:10px; font-size:0.9em; color:#4a4a4a; font-weight: bold;'>Scenario Color</div>", unsafe_allow_html=True)
for i, sc in enumerate(st.session_state.scenarios):
    with color_cols[i+1]:
        # Pre-seed session state for widget to maintain flawless sync during swaps
        if f"color_select_{sc}" not in st.session_state:
            st.session_state[f"color_select_{sc}"] = st.session_state.scenario_colors.get(sc, SCENARIO_COLORS_LIST[i % len(SCENARIO_COLORS_LIST)])
            
        current_color_name = st.session_state[f"color_select_{sc}"]
            
        st.selectbox(
            "Color",
            options=SCENARIO_COLORS_LIST,
            key=f"color_select_{sc}",
            label_visibility="collapsed",
            on_change=handle_color_change,
            args=(sc, current_color_name)
        )

# Standard Variable Rows
for var in st.session_state.active_variables:
    var_info = ALL_VARIABLES[var]
    grid_cols = st.columns([1.5] + [1] * len(st.session_state.scenarios))
    grid_cols[0].markdown(f"<div style='padding-top:10px; font-size:0.9em; color:#4a4a4a'>{var_info['label']}</div>", unsafe_allow_html=True)
    
    for i, sc in enumerate(st.session_state.scenarios):
        with grid_cols[i+1]:
            widget_key = f"{sc}_{var}"
            current_val = st.session_state.matrix_data[sc].get(var, var_info["default"])
            
            if var_info["type"] == "checkbox":
                new_val = st.checkbox("Enable", value=bool(current_val), key=widget_key, label_visibility="collapsed")
            elif var_info["type"] == "select":
                idx = var_info["options"].index(current_val) if current_val in var_info["options"] else 0
                new_val = st.selectbox("Select", options=var_info["options"], index=idx, key=widget_key, label_visibility="collapsed")
            elif var_info["type"] == "number":
                step = var_info.get("step", 1.0)
                fmt = var_info.get("format", None)
                min_val = var_info.get("min", None)
                max_val = var_info.get("max", None)
                new_val = st.number_input("Number", value=float(current_val) if isinstance(current_val, float) else int(current_val), min_value=min_val, max_value=max_val, step=step, format=fmt, key=widget_key, label_visibility="collapsed")
            
            st.session_state.matrix_data[sc][var] = new_val

st.markdown("---")

#############################################################################################################
# Section 2: Run Scenarios & Capture Plot Traces
#############################################################################################################
base_kwargs = {
    "initial_market_value": initial_market_value,
    "initial_affordability_pct_of_ami": initial_affordability_pct_of_ami,
    "initial_market_home_price_inflation_rate": initial_market_home_price_inflation_rate,
    "initial_area_median_income_inflation": initial_area_median_income_inflation,
    "initial_perc_income_spent_on_housing": initial_perc_income_spent_on_housing,
    "initial_ami_four_person_dollar_amount": initial_ami_four_person_dollar_amount,
    "initial_vale_resale_fixed_index_pct": initial_vale_resale_fixed_index_pct,
    "initial_household_size": initial_household_size,
    "initial_mortgage_rate": initial_mortgage_rate,
    "resale_mortgage_rate": resale_mortgage_rate,
    "initial_downpayment_pct": initial_downpayment_pct,
    "initial_closing_cost_pct": initial_closing_cost_pct,
    "resale_selling_cost_pct": resale_selling_cost_pct,
    "initial_length_of_mortgage_years": initial_length_of_mortgage_years,
    "using_FHA_loan": using_FHA_loan,
    "initial_property_tax_pct_annual": initial_property_tax_pct_annual,
    "initial_insurance_pct_annual": initial_insurance_pct_annual,
    "initial_hoa_monthly": initial_hoa_monthly,
    "initial_ground_lease_monthly": initial_ground_lease_monthly,
    "initial_pmi_financing_fees_monthly": initial_pmi_financing_fees_monthly,
    "property_tax_based_on_affordable_price": property_tax_based_on_affordable_price,
    "insurance_based_on_affordable_price": insurance_based_on_affordable_price,
    "initial_downpayment_assistance_amount": initial_downpayment_assistance_amount,
    "initial_downpayment_assistance_covers_buyer_contribution_check": initial_downpayment_assistance_covers_buyer_contribution_check,
    "initial_affordability_gap_amount": initial_affordability_gap_amount,
    "initial_holding_period_years": initial_holding_period_years,
    "vale_resale_capped": vale_resale_capped,
    "subtract_sunk_costs": subtract_sunk_costs,
    "cost_model": cost_model,
    "adjust_for_inflation": adjust_for_inflation,
    "general_inflation_rate": (general_inflation_rate / 100.0)
}

# Preserve the raw unconverted base vars purely for cleanly exporting matching inputs to CSV
raw_base_kwargs = base_kwargs.copy()
raw_base_kwargs["general_inflation_rate"] = general_inflation_rate 

scenario_results = {}
scenarios_to_run = st.session_state.scenarios[:6]

for col_name in scenarios_to_run:
    kwargs = base_kwargs.copy()
    scenario_overrides = st.session_state.matrix_data.get(col_name, {})
    for var_key, val in scenario_overrides.items():
        # Apply the value if it's explicitly active in the matrix, OR if it's a non-visible key pulled from an uploaded CSV
        if var_key in st.session_state.active_variables:
            kwargs[var_key] = val
        elif col_name in st.session_state.uploaded_scenarios and var_key in st.session_state.csv_uploaded_keys.get(col_name, []):
            kwargs[var_key] = val

    try:
        scenario_results[col_name] = compute_projections(**kwargs)
    except Exception as e:
        st.error(f"Error computing Scenario: {col_name}. Missing or invalid matrix parameter: {e}")

# Compile Scenario Data for Export 
st.markdown("#### Download Scenarios")
dl_col1, dl_col2 = st.columns([1, 2])
with dl_col1:
    select_all_dl = st.checkbox("Select All Scenarios for Download", value=True)

all_available_scenarios = list(scenario_results.keys())
with dl_col2:
    if select_all_dl:
        selected_for_dl = st.multiselect("Select scenarios to download:", options=all_available_scenarios, default=all_available_scenarios)
    else:
        selected_for_dl = st.multiselect("Select scenarios to download:", options=all_available_scenarios, default=[])

all_scenarios_df_list = []
for col_name in selected_for_dl:
    if col_name in scenario_results:
        proj_df = scenario_results[col_name]
        df_copy = proj_df.copy()
        df_copy.insert(0, "Scenario_Name", col_name)
        
        scen_raw_kwargs = raw_base_kwargs.copy()
        scenario_overrides = st.session_state.matrix_data.get(col_name, {})
        
        # Save active variables and hidden CSV-uploaded variables for the scenario into the CSV
        for var_key, val in scenario_overrides.items():
            if var_key in st.session_state.active_variables:
                scen_raw_kwargs[var_key] = val
            elif col_name in st.session_state.uploaded_scenarios and var_key in st.session_state.csv_uploaded_keys.get(col_name, []):
                scen_raw_kwargs[var_key] = val
                
        # Append all scenario parameter variables to the dataframe columns
        for k, v in scen_raw_kwargs.items():
            df_copy[k] = v
            
        all_scenarios_df_list.append(df_copy)
    
if all_scenarios_df_list:
    combined_df = pd.concat(all_scenarios_df_list, ignore_index=True)
    csv_data = combined_df.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="💾 Download Selected Scenarios Data to CSV",
        data=csv_data,
        file_name="vale_housing_scenarios.csv",
        mime="text/csv",
        help="Saves all computed projections and current matrix parameters to a standard .csv file. This file can be re-uploaded to load scenario parameters."
    )
elif len(scenario_results) > 0:
    st.info("Select at least one scenario to enable downloading.")

st.markdown("---")

#############################################################################################################
# Section 3: Show fundamentals of Affordability Metrics Widget
#############################################################################################################
st.markdown("<h3 style='text-align: center; margin-top: 2rem;'>Affordability Metrics Viewer</h3>", unsafe_allow_html=True)
selected_scenario_metrics = st.selectbox("Select Scenario for Year 0 Affordability Breakdown", options=list(scenario_results.keys()))

if selected_scenario_metrics and selected_scenario_metrics in scenario_results:
    m_proj = scenario_results[selected_scenario_metrics]
    
    sample_financials = {
        "initial_target_income_annual": float(m_proj["InitialAnnualTargetIncome"].iloc[0]),
        "initial_target_income_monthly": float(m_proj["InitialMonthlyTargetIncome"].iloc[0]),
        "initial_avail_housing_annual": float(m_proj["InitialAnnualTargetIncomeAvailForHousing"].iloc[0]),
        "initial_avail_housing_monthly": float(m_proj["InitialMonthlyTargetIncomeAvailForHousing"].iloc[0]),
        "initial_prop_taxes_annual": float(m_proj["InitialPropertyTaxAmountAnnual"].iloc[0]),
        "initial_prop_taxes_monthly": float(m_proj["InitialPropertyTaxAmountMonthly"].iloc[0]),
        "initial_insurance_annual": float(m_proj["InitialInsuranceAmountAnnual"].iloc[0]),
        "initial_insurance_monthly": float(m_proj["InitialInsuranceAmountMonthly"].iloc[0]),
        "initial_hoa_annually": float(m_proj["InitialHOAAnnually"].iloc[0]),
        "initial_hoa_monthly": float(m_proj["InitialStaticCostsMonthly"].iloc[0] - m_proj["InitialPMIandFinancingFeesMonthly"].iloc[0] - m_proj["InitialGroundLeaseAnnually"].iloc[0]/12), 
        "initial_ground_lease_annually": float(m_proj["InitialGroundLeaseAnnually"].iloc[0]),
        "initial_ground_lease_monthly": float(m_proj["InitialGroundLeaseAnnually"].iloc[0] / 12),
        "initial_pmi_financing_fees_annually": float(m_proj["InitialPMIandFinancingFeesAnnually"].iloc[0]),
        "initial_pmi_financing_fees_monthly": float(m_proj["InitialPMIandFinancingFeesMonthly"].iloc[0]),
        "initial_total_other_housing_annual": float(m_proj["InitialTotalOtherHousingAnnual"].iloc[0]),
        "initial_total_other_housing_monthly": float(m_proj["InitialTotalOtherHousingMonthly"].iloc[0]),
        "initial_avail_mortgage_monthly_affordable": float(m_proj["InitialAvailMortgagePaymentMonthlyAffordable"].iloc[0]),
        "initial_mortgage_rate_annually_decimal": float(m_proj["InitialMortgageRateAnnually"].iloc[0]),
        "initial_max_loan_amount_affordable": float(m_proj["InitialMaxLoanAmountAffordable"].iloc[0]),
        "initial_total_downpayment_affordable": float(m_proj["InitialTotalDownpaymentAmountAffordable"].iloc[0]),
        "initial_buyer_cash_contribution_downpayment": float(m_proj["InitialBuyerCashContributionDownpayment"].iloc[0]),
        "initial_downpayment_assistance_amount": float(m_proj["InitialDownpaymentAssistanceAmount"].iloc[0]),
        "initial_mortgage_affordable_closing_costs": float(m_proj["InitialClosingCostsAffordable"].iloc[0]),
        "outside_gap_loan": 0.0,
        "initial_affordable_purchase_price": float(m_proj["InitialPurchasePriceAffordable"].iloc[0]),
        "initial_subsidy_required": float(m_proj["InitialSubsidyRequired"].iloc[0]),
        "initial_affordability_gap_amount": float(m_proj["InitialAffordabilityGapAmount"].iloc[0]),
        "initial_remaining_subsidy_required": float(m_proj["InitialRemainingSubsidyRequired"].iloc[0]),
    }

    def f_curr(val): return "—" if val is None else f"$ {val:,.0f}"
    def f_pct(val): return "—" if val is None else f"{val * 100:.2f}%"

    style_block = """
    <style>
        .sheet-container { background-color: #FFF0E6; font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; border-radius: 4px; color: #1A1A1A; max-width: 700px; margin: 10px auto; position: relative; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
        .sheet-header { background-color: #EA6A20; color: #FFFFFF; padding: 8px 12px; font-size: 1.25rem; font-weight: 700; letter-spacing: -0.02em; }
        .sheet-subheader { background-color: #FFD6C2; color: #D35400; font-style: italic; padding: 4px 12px; border-bottom: 2px solid #E67E22; font-size: 0.95rem; }
        .sheet-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
        .sheet-table td { padding: 6px 12px; vertical-align: middle; }
        .sheet-col-header { font-weight: 500; color: #4A4A4A; text-align: right; padding-bottom: 2px; }
        .sheet-section-title { font-weight: 800; font-size: 1.05rem; padding-top: 14px; padding-bottom: 4px; }
        .sheet-row-bold { font-weight: 700; }
        .sheet-row-divider { border-top: 1px solid #1A1A1A; }
        .sheet-highlight-box { background-color: #FFD6C2; font-weight: 800; border-top: 2px solid #1A1A1A; border-bottom: 2px solid #1A1A1A; font-size: 1.05rem; }
        
        /* Interactive CSS Tooltip Module */
        .tooltip-container { position: relative; display: inline-block; cursor: help; margin-left: 6px; color: #EA6A20; font-size: 0.9rem; font-weight: bold; vertical-align: middle; transition: color 0.2s; }
        .tooltip-container:hover { color: #D35400; }
        .tooltip-container .tooltip-text {
            visibility: hidden; width: 250px; background-color: #2D3748; color: #FFFFFF; text-align: left;
            border-radius: 6px; padding: 10px 12px; position: absolute; z-index: 999;
            bottom: 125%; left: 50%; margin-left: -125px; opacity: 0;
            transition: opacity 0.2s, transform 0.2s; transform: translateY(8px);
            font-size: 0.8rem; font-weight: 400; line-height: 1.4;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.15); pointer-events: none;
        }
        .tooltip-container .tooltip-text::after {
            content: ""; position: absolute; top: 100%; left: 50%; margin-left: -6px;
            border-width: 6px; border-style: solid; border-color: #2D3748 transparent transparent transparent;
        }
        .tooltip-container:hover .tooltip-text { visibility: visible; opacity: 1; transform: translateY(0); }
    </style>
    """

    html_content = f"""
    {style_block}
    <div class="sheet-container">
        <div class="sheet-header">A. Affordability Subsidy ({selected_scenario_metrics})</div>
        <div class="sheet-subheader">Subsidy to bring the market value down to an affordable level</div>
        <table class="sheet-table">
            <tr><td></td><td class="sheet-col-header" style="width: 25%;">Annual</td><td class="sheet-col-header" style="width: 25%;">Monthly</td></tr>
            <tr>
                <td>Target Income <span class="tooltip-container">&#9432;<span class="tooltip-text">The target household income limit for this unit, typically derived from a percentage of the Area Median Income (AMI).</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_target_income_annual'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_target_income_monthly'])}</td>
            </tr>
            <tr>
                <td>Available for housing costs <span class="tooltip-container">&#9432;<span class="tooltip-text">The total budget allocated for all housing expenses under the standard 30% household affordability limit.</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_avail_housing_annual'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_avail_housing_monthly'])}</td>
            </tr>
            <tr><td colspan="3" class="sheet-section-title">Housing costs - other than mortgage</td></tr>
            <tr>
                <td style="padding-left: 24px;">Property Taxes <span class="tooltip-container">&#9432;<span class="tooltip-text">Annual or monthly property tax estimated based on the home's affordable purchase price or valuation.</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_prop_taxes_annual'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_prop_taxes_monthly'])}</td>
            </tr>
            <tr>
                <td style="padding-left: 24px;">Insurance <span class="tooltip-container">&#9432;<span class="tooltip-text">Estimated homeowner's hazard and liability insurance premiums.</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_insurance_annual'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_insurance_monthly'])}</td>
            </tr>
            <tr>
                <td style="padding-left: 24px;">Ground Lease or Admin Fee <span class="tooltip-container">&#9432;<span class="tooltip-text">Monthly fee paid to the Community Land Trust (CLT) to support the ground lease and program administration.</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_ground_lease_annually'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_ground_lease_monthly'])}</td>
            </tr>
            <tr>
                <td style="padding-left: 24px;">PMI, Additional Financing Fees <span class="tooltip-container">&#9432;<span class="tooltip-text">Private Mortgage Insurance or other ongoing transaction-specific financing fees.</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_pmi_financing_fees_annually'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_pmi_financing_fees_monthly'])}</td>
            </tr>
            <tr class="sheet-row-bold sheet-row-divider">
                <td>Total other housing costs <span class="tooltip-container">&#9432;<span class="tooltip-text">The combined sum of non-mortgage housing expenses (taxes, insurance, lease, HOA, and PMI).</span></span></td>
                <td style="text-align: right;">{f_curr(sample_financials['initial_total_other_housing_annual'])}</td><td style="text-align: right;">{f_curr(sample_financials['initial_total_other_housing_monthly'])}</td>
            </tr>
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <tr>
                <td>Available for mortgage payment <span class="tooltip-container">&#9432;<span class="tooltip-text">The remaining portion of the housing budget available to cover monthly mortgage principal and interest (P&I) payments.</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_avail_mortgage_monthly_affordable'])}</td>
            </tr>
            <tr>
                <td>Mortgage Interest Rate <span class="tooltip-container">&#9432;<span class="tooltip-text">The mortgage interest rate applied to calculate maximum borrowing capacity.</span></span></td>
                <td></td><td style="text-align: right; font-weight: 500;">{f_pct(sample_financials['initial_mortgage_rate_annually_decimal'])}</td>
            </tr>
            <tr class="sheet-row-bold">
                <td>Maximum loan amount <span class="tooltip-container">&#9432;<span class="tooltip-text">The maximum mortgage principal supported by the available monthly mortgage payment over a 30-year amortization.</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_max_loan_amount_affordable'])}</td>
            </tr>
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <tr>
                <td>Buyer Downpayment Contribution <span class="tooltip-container">&#9432;<span class="tooltip-text">The buyer's upfront cash down payment (e.g., 5% of the affordable purchase price).</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_buyer_cash_contribution_downpayment'])}</td>
            </tr>
            <tr>
                <td>Downpayment Assistance <span class="tooltip-container">&#9432;<span class="tooltip-text">Outside grant that pays downpayment - directly builds buyer's equity.</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_downpayment_assistance_amount'])}</td>
            </tr>
            <tr class="sheet-row-bold">
                <td>Total All Downpayment <span class="tooltip-container">&#9432;<span class="tooltip-text">Sum of all downpayments.</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_total_downpayment_affordable'])}</td>
            </tr>
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <tr class="sheet-row-bold sheet-row-divider">
                <td>Affordable Purchase Price <span class="tooltip-container">&#9432;<span class="tooltip-text">The maximum total purchase price a qualified buyer at the target income can afford to pay (Maximum Loan + Downpayment).</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_affordable_purchase_price'])}</td>
            </tr>
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <tr>
                <td>Total "Affordability Gap" Subsidy <span class="tooltip-container">&#9432;<span class="tooltip-text">The total capital subsidy required to bridge the gap between unrestricted market value and the calculated affordable purchase price.</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_subsidy_required'])}</td>
            </tr>
            <tr class="sheet-highlight-box">
                <td>Remaining Subsidy to Fundraise <span class="tooltip-container">&#9432;<span class="tooltip-text">The outstanding gap that still needs to be funded to make the project viable.</span></span></td>
                <td></td><td style="text-align: right;">{f_curr(sample_financials['initial_remaining_subsidy_required'])}</td>
            </tr>
        </table>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

#############################################################################################################
# Section 4: Unified 2x2 Plotly Grid with Persistent Legend & Layout Spacing
#############################################################################################################
st.markdown("<h3 style='text-align: center; margin-top: 1rem; margin-bottom: 0.5rem;'>Simulation Projections</h3>", unsafe_allow_html=True)

# Generate list of all possible legend items across active scenarios
all_possible_legend_items = []
for scen in scenario_results.keys():
    all_possible_legend_items.extend([f"{scen} (Market)", f"{scen} (Fixed)", f"{scen} (AMI)"])

selected_legends = st.multiselect(
    "Active Legend Items (Preserved across scenario updates):",
    options=all_possible_legend_items,
    default=[item for item in st.session_state.visible_legend_items if item in all_possible_legend_items],
    key="legend_selector"
)
st.session_state.visible_legend_items = selected_legends

show_scenario_targets = st.checkbox("Show Scenario-Specific Target AMI Lines", value=False, help="Display a targeted 'X' line matching the color of each scenario's Prospective Buyer Income Target.")

y_axis_suffix = " (in Today's Dollars)" if adjust_for_inflation else " ($)"

# Create a single Plotly figure with 2x2 subplots
fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=(
        "Resale Asking Price",
        "Homeowner Net Proceeds/Wealth",
        "Continuing Affordability (Target AMI %)",
        "CLT Community Equity Share"
    ),
    vertical_spacing=0.14,
    horizontal_spacing=0.14
)

# Increase font size (e.g., to 18)
fig.update_annotations(font_size=18)

# Make all subplot titles bold
fig.for_each_annotation(lambda a: a.update(text=f"<b>{a.text}</b>"))

for idx, (scen_name, proj_df) in enumerate(scenario_results.items()):
    c_color_name = st.session_state.scenario_colors.get(scen_name, '🟦 Blue')
    c_color = SCENARIO_COLOR_OPTIONS.get(c_color_name, '#636EFA')
    
    # 1. Market Traces
    lg_market = f"{scen_name} (Market)"
    vis_market = True if lg_market in st.session_state.visible_legend_items else "legendonly"
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['InitialMarketRateValue'], mode='lines', name=lg_market, legendgroup=lg_market, showlegend=True, visible=vis_market, line=dict(color=c_color, dash='solid', width=2), hovertemplate=f"<b>{lg_market}: Year - %{{x}}</b><br>Home Price: $%{{y:,.0f}}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleNetWealthBuiltMarket'], mode='lines', name=lg_market, legendgroup=lg_market, showlegend=False, visible=vis_market, line=dict(color=c_color, dash='solid', width=2), hovertemplate=f"<b>{lg_market}: Year - %{{x}}</b><br>Wealth Built: $%{{y:,.0f}}<extra></extra>"), row=1, col=2)

    # 2. Fixed Index Traces
    lg_fixed = f"{scen_name} (Fixed)"
    vis_fixed = True if lg_fixed in st.session_state.visible_legend_items else "legendonly"
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['InitialVALEFixedRateValue'], mode='lines', name=lg_fixed, legendgroup=lg_fixed, showlegend=True, visible=vis_fixed, line=dict(color=c_color, dash='dash', width=2), hovertemplate=f"<b>{lg_fixed}: Year - %{{x}}</b><br>Home Price: $%{{y:,.0f}}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleNetWealthBuiltFixed'], mode='lines', name=lg_fixed, legendgroup=lg_fixed, showlegend=False, visible=vis_fixed, line=dict(color=c_color, dash='dash', width=2), hovertemplate=f"<b>{lg_fixed}: Year - %{{x}}</b><br>Wealth Built: $%{{y:,.0f}}<extra></extra>"), row=1, col=2)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleContinuingAffordabilityPctOfAMIFixed'], mode='lines', name=lg_fixed, legendgroup=lg_fixed, showlegend=False, visible=vis_fixed, line=dict(color=c_color, dash='dash', width=2), hovertemplate=f"<b>{lg_fixed}: Year - %{{x}}</b><br>AMI Required: %{{y:.1f}}%<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleCLTEquityAmountFixed'], mode='lines', name=lg_fixed, legendgroup=lg_fixed, showlegend=False, visible=vis_fixed, line=dict(color=c_color, dash='dash', width=2), hovertemplate=f"<b>{lg_fixed}: Year - %{{x}}</b><br>CLT Equity: $%{{y:,.0f}}<extra></extra>"), row=2, col=2)

    # 3. AMI Traces
    lg_ami = f"{scen_name} (AMI)"
    vis_ami = True if lg_ami in st.session_state.visible_legend_items else "legendonly"
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['InitialAMIRateValue'], mode='lines', name=lg_ami, legendgroup=lg_ami, showlegend=True, visible=vis_ami, line=dict(color=c_color, dash='dot', width=2), hovertemplate=f"<b>{lg_ami}: Year - %{{x}}</b><br>Home Price: $%{{y:,.0f}}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleNetWealthBuiltAMI'], mode='lines', name=lg_ami, legendgroup=lg_ami, showlegend=False, visible=vis_ami, line=dict(color=c_color, dash='dot', width=2), hovertemplate=f"<b>{lg_ami}: Year - %{{x}}</b><br>Wealth Built: $%{{y:,.0f}}<extra></extra>"), row=1, col=2)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleContinuingAffordabilityPctOfAMIAMI'], mode='lines', name=lg_ami, legendgroup=lg_ami, showlegend=False, visible=vis_ami, line=dict(color=c_color, dash='dot', width=2), hovertemplate=f"<b>{lg_ami}: Year - %{{x}}</b><br>AMI Required: %{{y:.1f}}%<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Scatter(x=proj_df['Year'], y=proj_df['ResaleCLTEquityAmountAMI'], mode='lines', name=lg_ami, legendgroup=lg_ami, showlegend=False, visible=vis_ami, line=dict(color=c_color, dash='dot', width=2), hovertemplate=f"<b>{lg_ami}: Year - %{{x}}</b><br>CLT Equity: $%{{y:,.0f}}<extra></extra>"), row=2, col=2)

    # Add dynamically targeted line using 'X' markers when the checkbox is enabled
    if show_scenario_targets:
        target_val = initial_affordability_pct_of_ami
        if "initial_affordability_pct_of_ami" in st.session_state.active_variables:
            target_val = st.session_state.matrix_data.get(scen_name, {}).get("initial_affordability_pct_of_ami", initial_affordability_pct_of_ami)
        
        fig.add_trace(go.Scatter(
            x=proj_df['Year'],
            y=[target_val] * len(proj_df['Year']),
            mode='lines+markers',
            marker=dict(symbol='x', color=c_color, size=6),
            line=dict(color=c_color, width=1, dash='dot'),
            name=f"{scen_name} Target",
            showlegend=False,
            hoverinfo='skip'
        ), row=2, col=1)
        
        fig.add_annotation(
            x=proj_df['Year'].max(),
            y=target_val,
            text=f"{target_val:g}% Target",
            showarrow=False,
            font=dict(color=c_color, size=12),
            xanchor='right',
            yanchor='bottom',
            yshift=4,
            row=2, col=1
        )

# Render standard gray line baseline if custom targets aren't toggled
if not show_scenario_targets:
    fig.add_hline(y=initial_affordability_pct_of_ami, line_dash="dash", line_color="gray", annotation_text="Initial Target", row=2, col=1)

# Axis formatting
fig.update_xaxes(title_text="<b>Years</b>")
fig.update_yaxes(title_text=f"<b>Proceeds at Sale{y_axis_suffix}</b>", row=1, col=1)
fig.update_yaxes(title_text=f"<b>Net Proceeds / Wealth Built{y_axis_suffix}</b>", row=1, col=2)
fig.update_yaxes(title_text="<b>Required AMI %</b>", row=2, col=1)
fig.update_yaxes(title_text=f"<b>Retained Subsidy / Equity{y_axis_suffix}</b>", row=2, col=2)

# Layout & Top Legend configuration with generous top clearance
fig.update_layout(
    height=1080,
    margin=dict(t=220, b=60, l=60, r=60),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.12,
        xanchor="center",
        x=0.5,
        font=dict(size=12),
        borderwidth=1,
        bordercolor="#888888",
        entrywidthmode="fraction",
        entrywidth=0.31
    )
)

st.plotly_chart(fig, use_container_width=True)

#############################################################################################################
# Section 5: Disclaimers and Notes
#############################################################################################################

st.markdown(
    """
    <div style="
        background-color: #e6f4f1; 
        padding: 16px; 
        border-radius: 4px; 
        border-left: 6px solid #00684a; 
        color: #1e1e1e;
        display: flex;
        align-items: flex-start;
        gap: 16px;
    ">
        <!-- Left Side: Icon Container -->
        <div style="font-size: 1.8em; line-height: 1.2;">👥</div>
        <!-- Right Side: Text Container -->
        <div>
            <span style="font-size: 1.2em; font-weight: bold; color: #00684a;">Program Intent:</span><br>
            <span style="display: block; margin-top: 4px;">
                By setting the <b>Fixed Index % Increase</b> (tier), VALE can decouple home prices from volatile market inflation. 
                A 1% tier preserves extreme affordability for lower AMI buyers, while a 3% tier allows homeowners to build moderate equity 
                over time. Adjust the Affordability as Percent of AMI to simulate how target income shifts affect the initial entry price. 
                Financial calculations are provisional. All calculations can be off by ~$1 due to rounding.
                See finance.py comments for assumptions that should be reviewed or updated.
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
# END Section 5 #############################################################################################
