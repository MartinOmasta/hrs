import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go
from finance import compute_projections, HOUSEHOLD_SIZE_FACTORS
from data_loader import load_data, load_google_sheet_with_service_account


st.set_page_config(page_title="VALE Housing Resale Simulator", layout="wide")

st.markdown("""
    <style>
        /* Target the main container and override the default Streamlit max-width */
        [data-testid="stAppViewContainer"] .main .block-container {
            max-width: 98% !important;
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* Optional: If you want the charts to fill the column fully */
        div[data-testid="stPlotlyChart"] {
            width: 100% !important;
        }
    </style>
    """, unsafe_allow_html=True)

st.title("VALE Housing Resale Simulator (HRS) - Prototype")


#############################################################################################################
# Section 1: Setup UI for needed inputs for calculations
#############################################################################################################
#Injects custom styling directly into Streamlit to make expander headers bold, clean, and larger
st.sidebar.markdown(
    """
    <style>
        /* FIX: We drop 'div' and target the attribute directly because Streamlit uses 
           a <section> element for the sidebar. We also target 'summary' and legacy expander headers.
        */
        [data-testid="stSidebar"] [data-testid="stExpander"] summary,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary *,
        [data-testid="stSidebar"] [data-testid="stExpander"] .streamlit-expanderHeader,
        [data-testid="stSidebar"] [data-testid="stExpander"] .streamlit-expanderHeader * {
            font-size: 1.3rem !important;    /* Explicit pixel scaling for dramatic change */
            font-weight: 800 !important;    /* Extra bold weight */
            color: #1A1A1A !important;      /* Clean dark charcoal */
        }
    </style>
    """,
    unsafe_allow_html=True
)

with st.sidebar.expander("**🏡 Property Value - Initial & Ongoing**", expanded=True):
    initial_market_value = st.number_input("Property Asking Price $", value=348000, format="%d")
    affordability_pct_of_ami = st.number_input("Prospective Buyer Income Target (% of AMI)", value=80.0, step=10.0)
    market_home_price_inflation_rate = st.number_input("Home price inflation %", value=7.1, step=0.1)
    area_median_income_inflation = st.number_input("Area Median Income (AMI) inflation %", value=4.0, step=0.1)
    perc_income_spent_on_housing = st.number_input("Percentage of Income Spent on Housing %", value=30, step=1)

with st.sidebar.expander("**📈 VALE Program Tiers & Household**", expanded=True):
    ami_initial_four_person_dollar_amount = st.number_input("100% Area Median Income for 4-person household in Property's Area", value=93100, step=100)
    vale_resale_fixed_index_pct = st.number_input("Fixed Index % Increase (tier)", value=3.0, step=0.1)
    #market_share_cap = st.number_input("Market Share Cap %", value=25.0, step=1.0)
    household_size = st.select_slider("Target household size (for affordability calculation)", options=[1, 2, 3, 4, 5, 6, 7, 8], value=4)

with st.sidebar.expander("**💸 Financing & Costs**", expanded=True):
    mortgage_rate_start = st.number_input("Mortgage rate (start)", value=6.0, step=0.1)
    mortgage_rate_resale = st.number_input("Mortgage rate (resale)", value=6.0, step=0.1)
    downpayment_pct = st.number_input("Downpayment %", value=5.0, step=0.1)
    closing_cost_pct = st.number_input("Closing Costs %", value=3.0, step=0.1)
    selling_cost_pct = st.number_input("Selling cost %", value=7.0, step=0.1)
    types_of_mortgage_terms = [10, 15, 20, 30, 40]
    length_of_mortgage_years = st.selectbox(label="Length of Mortage (Years)", options=types_of_mortgage_terms, index=3)

with st.sidebar.expander("**⚖️ Taxes & Fees**", expanded=True):
    property_tax_pct_annual = st.number_input("Property tax % Annual", value=1.570, step=0.001, format="%.3f")
    insurance_pct_annual = st.number_input("Insurance % Annual", value=0.470, step=0.001, format="%.3f")
    hoa_monthly = st.number_input("HOA monthly $", value=0)
    ground_lease_monthly = st.number_input("Ground lease monthly $", value=50)
    other_costs_monthly = st.number_input("Other monthly costs $", value=0.0)
    property_tax_based_on_affordable_price = st.checkbox("**Tax Basis**: Is the Property Tax calculated based on the Affordable Price?", value=True)

with st.sidebar.expander("**🫴🪙Outside Subsidy**", expanded=True):
    downpayment_assistance_amount = st.number_input("Downpayment Assistance $ Amount", value=0, step=10)
    affordability_gap_amount = st.number_input("Affordability Gap $ Amount", value=0, step=10)
    project_gap_amount = st.number_input("Project Gap $ Amount", value=0, step=10)

with st.sidebar.expander("**⚙️Simulation**", expanded=True):
    holding_period_years = st.slider("Holding Period (years)", min_value=1, max_value=40, value=15)
    vale_resale_capped = st.checkbox("**CAP**: Prevent Resale Formula Proceeds from Exceeding Market Rate Proceeds", value=True)
# END SECTION 1 #############################################################################################



# NOT NEEDED AT THIS TIME Compute projections
# if 'df_ami' in locals() and df_ami is not None:
#     # If user uploaded AMI table, try to use it
#     try:
#         ami_initial_four_person_dollar_amount = float(df_ami.loc[0, 'AMI'])
#     except Exception:
#         pass
# END NOT NEEDED AT THIS TIME ###############################################################################



#############################################################################################################
# Section 2: Utilize finance.py package to compute financials and statistics
#############################################################################################################
proj = compute_projections(
    initial_market_value=initial_market_value,
    affordability_pct_of_ami=affordability_pct_of_ami,
    market_home_price_inflation_rate=market_home_price_inflation_rate,
    area_median_income_inflation=area_median_income_inflation,
    perc_income_spent_on_housing=perc_income_spent_on_housing,
    ami_initial_four_person_dollar_amount=ami_initial_four_person_dollar_amount,
    vale_resale_fixed_index_pct=vale_resale_fixed_index_pct,
    household_size=household_size,
    mortgage_rate_start=mortgage_rate_start,
    mortgage_rate_resale=mortgage_rate_resale,
    downpayment_pct=downpayment_pct,
    closing_cost_pct=closing_cost_pct,
    selling_cost_pct=selling_cost_pct,
    length_of_mortgage_years=length_of_mortgage_years,
    property_tax_pct_annual=property_tax_pct_annual,
    insurance_pct_annual=insurance_pct_annual,
    hoa_monthly=hoa_monthly,
    ground_lease_monthly=ground_lease_monthly,
    other_costs_monthly=other_costs_monthly,
    property_tax_based_on_affordable_price=property_tax_based_on_affordable_price,
    holding_period_years=holding_period_years,
    vale_resale_capped=vale_resale_capped,
)
# END Section 2 #############################################################################################



#############################################################################################################
# Section 3a: Convert fundamentals of Affordability Metrics
#############################################################################################################
#st.subheader("Affordabilty Metrics")
st.markdown("<h3 style='text-align: center;'>Affordabilty Metrics</h3>", unsafe_allow_html=True)

# Instantiate Income Availability
annual_income = float(proj["AnnualTargetIncome"].iloc[0])
monthly_income = float(proj["MonthlyTargetIncome"].iloc[0])
annual_income_avail_for_housing = float(proj["AnnualTargetIncomeAvailForHousing"].iloc[0])
monthly_income_avail_for_housing = float(proj["MonthlyTargetIncomeAvailForHousing"].iloc[0])

# Instantiate Static Costs
static_costs_monthly = float(proj["StaticCostsMonthly"].iloc[0])

# Instantiate Solved Property Financials
max_loan_amount = float(proj["MaxLoanAmount"].iloc[0])
downpayment_amount = float(proj["DownpaymentAmount"].iloc[0])
property_taxes_amount_annual = float(proj["PropertyTaxAmountAnnual"].iloc[0])
property_taxes_amount_monthly = float(proj["PropertyTaxAmountMonthly"].iloc[0])
insurance_amount_annual = float(proj["InsuranceAmountAnnual"].iloc[0])
insurance_amount_monthly = float(proj["InsuranceAmountMonthly"].iloc[0])
avail_mortgage_payment_monthly = float(proj["AvailMortgagePaymentMonthly"].iloc[0])
subsidy_required = float(proj["SubsidyRequired"].iloc[0])

total_other_housing_annual = math.ceil((static_costs_monthly * 12) + property_taxes_amount_annual + insurance_amount_annual)
total_other_housing_monthly = total_other_housing_annual / 12

affordable_purchase_price_paid_by_resident_owner = max_loan_amount + downpayment_amount # + outside_affordability_gap_loan (to be added outside subsidy)

# END Section 3a #############################################################################################



#############################################################################################################
# Section 3b: Calculate Net Proceeds
#############################################################################################################



# END Section 3b: Calculate Net Proceeds #####################################################################



#############################################################################################################
# Section 3c: Show fundamentals of Affordability Metrics
#############################################################################################################

def render_affordability_subsidy_widget(data: dict):
    """
    Renders an HTML/CSS spreadsheet-style widget matching the visual design
    and layout of image_9a4dfd.png, now complete with interactive info hovers.
    
    Expected keys in `data` dict:
        - target_income_annual (float)
        - target_income_monthly (float)
        - avail_housing_annual (float)
        - avail_housing_monthly (float)
        - prop_taxes_annual (float)
        - prop_taxes_monthly (float)
        - insurance_annual (float)
        - insurance_monthly (float)
        - hoa_annual (float)
        - hoa_monthly (float)
        - ground_lease_annual (float)
        - ground_lease_monthly (float)
        - pmi_other_annual (float)
        - pmi_other_monthly (float)
        - total_other_housing_annual (float)
        - total_other_housing_monthly (float)
        - avail_mortgage_monthly (float)
        - interest_rate (float)  # e.g., 0.06 for 6.00%
        - max_loan_amount (float)
        - downpayment (float)
        - outside_gap_loan (float)
        - affordable_purchase_price (float)
        - subsidy_required (float)
    """
    
    # Currency and Percentage Formatting Helpers
    def f_curr(val):
        if val is None:
            return "—"
        return f"$ {val:,.0f}"
        
    def f_pct(val):
        if val is None:
            return "—"
        return f"{val * 100:.2f}%"

    # Custom CSS to mimic the spreadsheet in image_9a4dfd.png
    style_block = """
    <style>
        .sheet-container {
            background-color: #FFF0E6; /* Warm peach tint background */
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            border-radius: 4px;
            color: #1A1A1A;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            max-width: 700px;
            margin: 10px auto;
            position: relative;
        }
        .sheet-header {
            background-color: #EA6A20; /* Vibrant orange header */
            color: #FFFFFF;
            padding: 8px 12px;
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .sheet-subheader {
            background-color: #FFD6C2; /* Soft orange/cream subheader */
            color: #D35400;
            font-style: italic;
            padding: 4px 12px;
            font-size: 0.95rem;
            border-bottom: 2px solid #E67E22;
        }
        .sheet-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }
        .sheet-table td {
            padding: 6px 12px;
            vertical-align: middle;
        }
        .sheet-col-header {
            font-weight: 500;
            color: #4A4A4A;
            text-align: right;
            padding-bottom: 2px;
        }
        .sheet-section-title {
            font-weight: 800;
            font-size: 1.05rem;
            color: #1A1A1A;
            padding-top: 14px;
            padding-bottom: 4px;
        }
        .sheet-row-bold {
            font-weight: 700;
        }
        .sheet-row-divider {
            border-top: 1px solid #1A1A1A;
        }
        .sheet-row-double-divider {
            border-top: 1px solid #1A1A1A;
            border-bottom: 3px double #1A1A1A;
        }
        .sheet-highlight-box {
            background-color: #FFD6C2;
            font-weight: 800;
            border-top: 2px solid #1A1A1A;
            border-bottom: 2px solid #1A1A1A;
            font-size: 1.05rem;
        }
        
        /* Interactive CSS Tooltip Module */
        .tooltip-container {
            position: relative;
            display: inline-block;
            cursor: help;
            margin-left: 6px;
            color: #EA6A20; /* Vibrant orange matching theme */
            font-size: 0.9rem;
            font-weight: bold;
            vertical-align: middle;
            transition: color 0.2s;
        }
        .tooltip-container:hover {
            color: #D35400;
        }
        .tooltip-container .tooltip-text {
            visibility: hidden;
            width: 250px;
            background-color: #2D3748; /* Sleek slate-dark gray */
            color: #FFFFFF;
            text-align: left;
            border-radius: 6px;
            padding: 10px 12px;
            position: absolute;
            z-index: 999; /* Float over table components */
            bottom: 125%;
            left: 50%;
            margin-left: -125px;
            opacity: 0;
            transition: opacity 0.2s, transform 0.2s;
            transform: translateY(8px);
            font-size: 0.8rem;
            font-weight: 400;
            line-height: 1.4;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.15);
            pointer-events: none; /* Bypass pointer loops during hot spots */
        }
        .tooltip-container .tooltip-text::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -6px;
            border-width: 6px;
            border-style: solid;
            border-color: #2D3748 transparent transparent transparent;
        }
        .tooltip-container:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
            transform: translateY(0);
        }
    </style>
    """

    # Inline HTML structure mapping exactly to image_9a4dfd.png with descriptive tooltips
    html_content = f"""
    {style_block}
    <div class="sheet-container">
        <div class="sheet-header">A. Affordability Subsidy</div>
        <div class="sheet-subheader">Subsidy to bring the market value down to an affordable level</div>
        <table class="sheet-table">
            <!-- Headers -->
            <tr>
                <td></td>
                <td class="sheet-col-header" style="width: 25%;">Annual</td>
                <td class="sheet-col-header" style="width: 25%;">Monthly</td>
            </tr>
            <!-- Target Income -->
            <tr>
                <td>
                    Target Income
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The target household income limit for this unit, typically derived from a percentage of the Area Median Income (AMI).</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['target_income_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['target_income_monthly'])}</td>
            </tr>
            <!-- Available for Housing Costs -->
            <tr>
                <td>
                    Available for housing costs
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The total budget allocated for all housing expenses under the standard 30% household affordability limit.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['avail_housing_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['avail_housing_monthly'])}</td>
            </tr>
            <!-- Housing Costs Header -->
            <tr>
                <td colspan="3" class="sheet-section-title">Housing costs - other than mortgage</td>
            </tr>
            <!-- Property Taxes -->
            <tr>
                <td style="padding-left: 24px;">
                    Property Taxes
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Annual or monthly property tax estimated based on the home's affordable purchase price or valuation.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['prop_taxes_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['prop_taxes_monthly'])}</td>
            </tr>
            <!-- Insurance -->
            <tr>
                <td style="padding-left: 24px;">
                    Insurance
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Estimated homeowner's hazard and liability insurance premiums.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['insurance_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['insurance_monthly'])}</td>
            </tr>
            <!-- HOA -->
            <tr>
                <td style="padding-left: 24px;">
                    Home Owners Association Dues
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Monthly dues required by the HOA for shared community property maintenance, if applicable.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['hoa_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['hoa_monthly'])}</td>
            </tr>
            <!-- Ground Lease -->
            <tr>
                <td style="padding-left: 24px;">
                    Ground Lease or Admin Fee
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Monthly fee paid to the Community Land Trust (CLT) to support the ground lease and program administration.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['ground_lease_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['ground_lease_monthly'])}</td>
            </tr>
            <!-- PMI/Other -->
            <tr>
                <td style="padding-left: 24px;">
                    PMI, Other Costs
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Private Mortgage Insurance or other ongoing transaction-specific financing fees.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['pmi_other_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['pmi_other_monthly'])}</td>
            </tr>
            <!-- Total Other Housing Costs -->
            <tr class="sheet-row-bold sheet-row-divider">
                <td>
                    Total other housing costs
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The combined sum of non-mortgage housing expenses (taxes, insurance, lease, HOA, and PMI).</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['total_other_housing_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['total_other_housing_monthly'])}</td>
            </tr>
            <!-- Gap spacing -->
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <!-- Available for Mortgage -->
            <tr>
                <td>
                    Available for mortgage payment
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The remaining portion of the housing budget available to cover monthly mortgage principal and interest (P&I) payments.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['avail_mortgage_monthly'])}</td>
            </tr>
            <!-- Interest Rate -->
            <tr>
                <td>
                    Interest rate (Base scenario)
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The mortgage interest rate applied to calculate maximum borrowing capacity.</span></span>
                </td>
                <td></td>
                <td style="text-align: right; font-weight: 500;">{f_pct(data['interest_rate'])}</td>
            </tr>
            <!-- Max Loan -->
            <tr class="sheet-row-bold">
                <td>
                    Maximum loan amount
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The maximum mortgage principal supported by the available monthly mortgage payment over a 30-year amortization.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['max_loan_amount'])}</td>
            </tr>
            <!-- Gap spacing -->
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <!-- Downpayment -->
            <tr>
                <td>
                    Downpayment
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The buyer's upfront cash down payment (e.g., 5% of the affordable purchase price).</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['downpayment'])}</td>
            </tr>
            <!-- Outside Affordability Gap -->
            <tr>
                <td>
                    Outside Affordability Gap (Loan)
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Any supplementary financing or subordinate soft-second debt required to close.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['outside_gap_loan'])}</td>
            </tr>
            <!-- Affordable Purchase Price -->
            <tr class="sheet-row-bold">
                <td>
                    Affordable Purchase Price
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The maximum total purchase price a qualified buyer at the target income can afford to pay (Maximum Loan + Downpayment).</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['affordable_purchase_price'])}</td>
            </tr>
            <!-- Highlighted Bottom Row: Subsidy Required -->
            <tr class="sheet-highlight-box">
                <td>
                    "Affordability Gap" Subsidy Required
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The capital subsidy required to bridge the gap between unrestricted market value and the calculated affordable purchase price.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['subsidy_required'])}</td>
            </tr>
        </table>
    </div>
    """
    
    st.markdown(html_content, unsafe_allow_html=True)
# END def render_affordability_subsidy_widget ####################################################################################
# END Section 3c: Show fundamentals of Affordability Metrics #####################################################################



#RENDER
# --- Example Dashboard Harness (for Testing) ---
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    #st.title("VALE Program Sandbox")
    #st.subheader("High-Fidelity UI Layout Verification")

    
    sample_financials = {
        "target_income_annual": annual_income,
        "target_income_monthly": monthly_income,
        "avail_housing_annual": annual_income_avail_for_housing,
        "avail_housing_monthly": monthly_income_avail_for_housing,
        "prop_taxes_annual": property_taxes_amount_annual, #3634.0,
        "prop_taxes_monthly": property_taxes_amount_monthly, #303.0,
        "insurance_annual": insurance_amount_annual, #1088.0,
        "insurance_monthly": insurance_amount_monthly, #91.0,
        "hoa_annual": (hoa_monthly * 12),
        "hoa_monthly": hoa_monthly,
        "ground_lease_annual": (ground_lease_monthly * 12),
        "ground_lease_monthly": ground_lease_monthly,
        "pmi_other_annual": (other_costs_monthly * 12),
        "pmi_other_monthly": other_costs_monthly,
        "total_other_housing_annual": total_other_housing_annual, #6522.0,
        "total_other_housing_monthly": total_other_housing_monthly, #544.0,
        "avail_mortgage_monthly": avail_mortgage_payment_monthly, #1318.0,
        "interest_rate": mortgage_rate_start / 100, # 6.00%
        "max_loan_amount": max_loan_amount, #219911.0,
        "downpayment": downpayment_amount, #11574.0,
        "outside_gap_loan": 0.0,
        "affordable_purchase_price": affordable_purchase_price_paid_by_resident_owner, #231485.0,
        "subsidy_required": subsidy_required, #116515.0
    }

    #st.write("Below is the custom rendering component matching your requirements:")
    render_affordability_subsidy_widget(sample_financials)
# ```
# *eof*

# ### How to Integrate this into Your Pipeline

# 1. **Calculations in `finance.py`**:
#    Ensure your Python backend calculations return a clean dictionary containing the exact raw numbers. It is best to pass **floats/ints** directly to the widget, as formatting them to currencies (with correct commas, dollar signs, and decimal truncations) is handled natively by the rendering helper functions `f_curr` and `f_pct`.

# 2. **Connecting inside your main `app.py`**:
#    You can easily import this rendering component and feed it your pipeline outputs:

#    ```python
#    # In app.py
#    import streamlit as st
#    from finance import compute_projections  # Your backend engine
#    from streamlit_subsidy_display import render_affordability_subsidy_widget

#    # ... Gather user inputs via sliders (holding period, interest rate, etc.) ...
   
#    # Run calculations to retrieve the dictionary
#    calculation_results = compute_projections(
#        # pass user input parameters here
#    )
   
#    # Render the clean spreadsheet UI
#    render_affordability_subsidy_widget(calculation_results)

# END Section 3b #############################################################################################
# END Section 3 ##############################################################################################



#############################################################################################################
# Section 4: Layout two main charts side-by-side and table of results
#############################################################################################################
#col1, col2 = st.columns(2)
col1, col2 = st.columns([1, 1])

with col1:
    #st.subheader("Homeowner Selling Price (Market vs Fixed vs AMI Gross Revenue)")
    st.markdown(
    """<p style='font-size:16px; font-weight: bold; text-align: center'>Resale Asking Price (Market Rate vs Fixed Rate vs AMI 
    Rate Returns)<span class="tooltip-container">&#9432;<span class="tooltip-text">How much money a Homeowner could rough expect
     to ask for thier home - after a given time period - when selling on either the open market, or in accordance with the Resale 
    Restriction of VALE Fixed or an AMI based formula</span></span></p>""",
    unsafe_allow_html=True
)
    sale_price_fig = go.Figure()
    sale_price_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['MarketRateValue'], mode='lines+markers', name='Asking Price (Market)', line=dict(color='#3cb44b', width=2),  marker=dict(symbol='diamond', size=8), hovertemplate="Year: %{x}<br>Home Price: %{y:$,.0f}<extra></extra>"))
    sale_price_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['VALEFixedRateValue'], mode='lines+markers', name='Asking Price (Fixed)', line=dict(color='#F46A25', width=2),  marker=dict(symbol='star', size=8), hovertemplate="Year: %{x}<br>Home Price: %{y:$,.0f}<extra></extra>"))
    sale_price_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['AMIRateValue'], mode='lines+markers', name='Asking Price (AMI)', line=dict(color='#4363d8', width=2),  marker=dict(symbol='cross', size=8), hovertemplate="Year: %{x}<br>Home Price: %{y:$,.0f}<extra></extra>"))
    sale_price_fig.update_layout(xaxis_title='Years', yaxis_title='Proceeds at Sale ($)')
    sale_price_fig.update_layout(
        xaxis_title='<b>Years</b>', 
        yaxis_title='<b>Proceeds at Sale ($)</b>',
        #height=350,  # Limits the height so the chart behaves as a wide landscape rectangle
        #autosize=True,
        #width=2000,
        margin=dict(l=40, r=20, t=20, b=40),  # Reduces empty padding around the chart
        legend=dict(
            orientation="h",       # Places the legend horizontally
            yanchor="bottom",
            y=1.02,                # Positions legend cleanly above the chart
            xanchor="right",
            x=1,
            font=dict(size=16), # Adjust this number to make the text bigger or smaller
        )
    )
    st.plotly_chart(sale_price_fig, use_container_width=True)

with col2:
    #st.subheader("Homeowner Net Proceeds/Individual Wealth Built (Market vs Fixed vs AMI Net Revenue)")
    st.markdown(
    """<p style='font-size:16px; font-weight: bold; text-align: center'>Homeowner Net Proceeds/Individual Wealth Built 
    (Market vs Fixed vs AMI Net Proceeds)<span class="tooltip-container">&#9432;<span class="tooltip-text">This is the projected
    earnings that a Home Owner could roughly expect to earn as wealth as a result of selling their home. This considers how much
    they sell the house for - and subtracts out the 1) Cumulative Costs of Ownership (Mortgage Payments & Interest, Property Taxes, 
    Home Insurance); 2) Transaction & Holding Costs (Selling Costs, Closing Costs, Maintenance & Capital Improvements); and 
     any remaing 3) Liabilities (Remaining Mortgage Payoff, HELOC or Secondary Loans) </span></span></p>""",
    unsafe_allow_html=True
)
    net_proceeds_fig = go.Figure()
    #fig2.add_trace(go.Bar(x=proj['Year'], y=proj['EquityGainMarket'], name='Market Value', marker_color='lightgray'))
    #fig2.add_trace(go.Bar(x=proj['Year'], y=proj['EquityGainFixed'], name='Fixed Resale Price', marker_color='green'))
    #fig2.add_trace(go.Scatter(x=proj['Year'], y=proj['EquityGainAMI'], name='Affordability Bound (AMI %)', line=dict(color='navy', dash='dash')))
    net_proceeds_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['NetCashflowChangeMarket'], mode='lines+markers', name='Equity Gained (Market)', line=dict(color='#3cb44b', width=2),  marker=dict(symbol='diamond', size=8), hovertemplate="Year: %{x}<br>Equity Earned: %{y:$,.0f}<extra></extra>"))
    net_proceeds_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['NetCashflowChangeFixed'], mode='lines+markers', name='Equity Gained (Fixed)', line=dict(color='#F46A25', width=2),  marker=dict(symbol='star', size=8), hovertemplate="Year: %{x}<br>Equity Earned: %{y:$,.0f}<extra></extra>"))
    net_proceeds_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['NetCashflowChangeAMI'], mode='lines+markers', name='Equity Gained (AMI)', line=dict(color='#4363d8', width=2),  marker=dict(symbol='cross', size=8), hovertemplate="Year: %{x}<br>Equity Earned: %{y:$,.0f}<extra></extra>"))
    net_proceeds_fig.update_layout(barmode='group', xaxis_title='<b>Years</b>', yaxis_title='<b>Price ($)</b>')
    st.plotly_chart(net_proceeds_fig, use_container_width=True)

st.subheader("Yearly Proceeds Detail")
cols = ['Year','MarketRateValue', 'NetCashflowChangeMarket', 'VALEFixedRateValue', 'NetCashflowChangeFixed', 'AMIRateValue', 'NetCashflowChangeAMI', 'PropertyTaxAmountAnnual']
st.dataframe(proj[cols])

# Export
csv = proj.to_csv(index=False).encode('utf-8')
st.download_button("Download projections CSV", data=csv, file_name='projections.csv', mime='text/csv')
# END Section 4 #############################################################################################




#############################################################################################################
# Section 5: Disclaimers and Notes
#############################################################################################################
# Attempt 1
# # st.markdown("---")
# st.info("""**Program Intent:**  \nBy setting the **Fixed Index % Increase** (tier), VALE can decouple home prices from volatile market inflation. 
#         A 1% tier preserves extreme affordability for lower AMI buyers, while a 3% tier allows homeowners to build moderate equity over time. 
#         Adjust the Affordability as Percent of AMI to simulate how target income shifts affect the initial entry price. 
#         Financial calculations are provisional. See finance.py comments for assumptions that should be reviewed or updated by experts.""",
#           icon="👥")
#icon="🚀")

# Attepmt 2
# st.markdown(
#     """
#     <div style="
#         background-color: #e6f4f1; 
#         padding: 16px; 
#         border-radius: 4px; 
#         border-left: 6px solid #00684a; 
#         color: #1e1e1e;
#     ">
#         <span style="font-size: 1.2em; font-weight: bold; color: #00684a;">👥 Program Intent:</span><br>
#         By setting the <b>Fixed Index % Increase</b> (tier), VALE can decouple home prices from volatile market inflation. A 1% tier preserves extreme affordability for lower AMI buyers, while a 3% tier allows homeowners to build moderate equity over time. Adjust the Affordability as Percent of AMI to simulate how target income shifts affect the initial entry price. Financial calculations are provisional. See finance.py comments for assumptions that should be reviewed or updated by experts.
#     </div>
#     """,
#     unsafe_allow_html=True
# )

# Attempt 3
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

#Attempt 4
# st.markdown(
#     """
#     <div style="
#         background-color: var(--background-color); 
#         filter: brightness(0.95);
#         padding: 16px; 
#         border-radius: 4px; 
#         border-left: 6px solid rgb(0, 104, 74); 
#         color: var(--text-color);
#         display: flex;
#         align-items: flex-start;
#         gap: 16px;
#     ">
#         <div style="font-size: 1.5em; line-height: 1.2;">👥</div>
        
#         <div>
#             <span style="font-size: 1.2em; font-weight: bold; color: rgb(0, 104, 74);">Program Intent:</span><br>
#             <span style="display: block; margin-top: 4px;">
#                 By setting the <b>Fixed Index % Increase</b> (tier), VALE can decouple home prices from volatile market inflation. A 1% tier preserves extreme affordability for lower AMI buyers, while a 3% tier allows homeowners to build moderate equity over time. Adjust the Affordability as Percent of AMI to simulate how target income shifts affect the initial entry price. Financial calculations are provisional. See finance.py comments for assumptions that should be reviewed or updated by experts.
#             </span>
#         </div>
#     </div>
#     """,
#     unsafe_allow_html=True
# )
# END Section 5 #############################################################################################
