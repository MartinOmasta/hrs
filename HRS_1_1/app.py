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

# Throughout this document if a variable has a:
# Prefix of 'iniital' - then it is referring to the time the home is 1st purchased
# Prefix of 'resale' - then it is referring to the time that that 'initial' home is sold to a second buyer
# Contains 'market' - then it is referring to homes with costs associated with the capitalist speculative market
# Contains 'fixed' - then it is referring to a fixed index resale formula (i.e, pinned to a fixed number say 1.5%)
# Contains 'ami" - then it is referring to an AMI based index resale formula (i.e, it rises & falls based on the HUD produced AMI number)
# Contains 'affordable' - then it is referring to any home - either 'fixed' or 'ami' that meet affordability criteria

with st.sidebar.expander("**🏡 Property Value - Initial & Ongoing**", expanded=True):
    initial_market_value = st.number_input("Property Asking Price $", value=348000, format="%d", help="Unrestricted open-market appraisal or initial listing price.")
    initial_affordability_pct_of_ami = st.number_input("Prospective Buyer Income Target (% of AMI)", value=80.0, step=10.0, help="Based on regional HUD AMI tables for this Property's area - what is the intended range that this property it targeted for?")
    initial_market_home_price_inflation_rate = st.number_input("Home price inflation %", value=7.1, step=0.1)
    initial_area_median_income_inflation = st.number_input("Area Median Income (AMI) inflation %", value=4.0, step=0.1)
    initial_perc_income_spent_on_housing = st.number_input("Percentage of Income Spent on Housing %", value=30, step=1)

with st.sidebar.expander("**📈 VALE Program Tiers & Household**", expanded=True):
    initial_ami_four_person_dollar_amount = st.number_input("100% Area Median Income for 4-person household in Property's Area", value=93100, step=100)
    initial_vale_resale_fixed_index_pct = st.number_input("Fixed Index % Increase (tier)", value=3.0, step=0.1)
    #market_share_cap = st.number_input("Market Share Cap %", value=25.0, step=1.0)
    initial_household_size = st.select_slider("Target household size (for affordability calculation)", options=[1, 2, 3, 4, 5, 6, 7, 8], value=4)

with st.sidebar.expander("**💸 Financing & Costs**", expanded=True):
    initial_mortgage_rate = st.number_input("Mortgage rate (Initial Buyer)", value=6.0, step=0.1)
    resale_mortgage_rate = st.number_input("Mortgage rate (Resale Buyer)", value=6.0, step=0.1)
    initial_downpayment_pct = st.number_input("Downpayment %", value=5.0, step=0.1)
    initial_closing_cost_pct = st.number_input("Closing Costs %", value=3.0, step=0.1)
    resale_selling_cost_pct = st.number_input("Selling cost %", value=7.0, step=0.1)
    types_of_mortgage_terms = [10, 15, 20, 30, 40]
    initial_length_of_mortgage_years = st.selectbox(label="Length of Mortage (Years)", options=types_of_mortgage_terms, index=3)
    using_FHA_loan = st.checkbox("**FHA Loan**: Buyer is using FHA Loan", value=False)

with st.sidebar.expander("**⚖️ Taxes & Fees**", expanded=True):
    initial_property_tax_pct_annual = st.number_input("Property tax % Annual", value=1.570, step=0.001, format="%.3f")
    initial_insurance_pct_annual = st.number_input("Insurance % Annual", value=0.470, step=0.001, format="%.3f")
    initial_hoa_monthly = st.number_input("HOA monthly $", value=0)
    initial_ground_lease_monthly = st.number_input("Ground lease monthly $", value=50)
    initial_pmi_financing_fees_monthly = st.number_input("PMI or Additional monthly fees $", value=100.0)
    property_tax_based_on_affordable_price = st.checkbox("**Tax Basis**: Is the Property Tax calculated based on the Affordable Price?", value=True)

with st.sidebar.expander("**🫴🪙Outside Subsidy**", expanded=True):
    initial_downpayment_assistance_amount = st.number_input("Downpayment Assistance (DPA) $ Amount", value=0, step=10)
    initial_downpayment_assistance_covers_buyer_contribution_check = st.checkbox("**DPA**: Covers Buyer's Contribution", value=True)
    initial_affordability_gap_amount = st.number_input("Affordability Gap $ Amount", value=0, step=10, help="Amount already fundraised to cover the affordability subsidy.")

with st.sidebar.expander("**⚙️Simulation**", expanded=True):
    initial_holding_period_years = st.slider("Holding Period (years)", min_value=1, max_value=40, value=15)
    vale_resale_capped = st.checkbox("**CAP**: Prevent Resale Formula Proceeds from Exceeding Market Rate Proceeds", value=True)
    subtract_sunk_costs = st.checkbox("**NET POSITION**: Subtract sunk living costs (Taxes, Insurance, Interest, HOA) from Wealth Built", value=False)
    
    st.markdown("---")
    cost_model = st.radio(
        "Housing Cost Model",
        options=["Realistic (Market-Tied & Static Fees)", "Idealized (Flat Affordability)"],
        index=0,
        help="Realistic ties insurance to market value and calculates actual FHA/Conventional PMI drop-offs. Idealized perfectly scales all costs with AMI."
    )
    
    st.markdown("---")
    adjust_for_inflation = st.checkbox(
        "Adjust Values for Inflation (Present Value)", 
        value=False,
        help="Display future financial returns in today's purchasing power."
    )
    general_inflation_rate = st.number_input(
        "General Economic Inflation Rate (%)", 
        min_value=0.0, 
        max_value=15.0, 
        value=2.0, 
        step=0.1
    )
# END SECTION 1 #############################################################################################



#############################################################################################################
# Section 2: Utilize finance.py package to compute financials and statistics
#############################################################################################################
proj = compute_projections(
    initial_market_value=initial_market_value,
    initial_affordability_pct_of_ami=initial_affordability_pct_of_ami,
    initial_market_home_price_inflation_rate=initial_market_home_price_inflation_rate,
    initial_area_median_income_inflation=initial_area_median_income_inflation,
    initial_perc_income_spent_on_housing=initial_perc_income_spent_on_housing,
    initial_ami_four_person_dollar_amount=initial_ami_four_person_dollar_amount,
    initial_vale_resale_fixed_index_pct=initial_vale_resale_fixed_index_pct,
    initial_household_size=initial_household_size,
    initial_mortgage_rate=initial_mortgage_rate,
    resale_mortgage_rate=resale_mortgage_rate,
    initial_downpayment_pct=initial_downpayment_pct,
    initial_closing_cost_pct=initial_closing_cost_pct,
    resale_selling_cost_pct=resale_selling_cost_pct,
    initial_length_of_mortgage_years=initial_length_of_mortgage_years,
    using_FHA_loan=using_FHA_loan,
    initial_property_tax_pct_annual=initial_property_tax_pct_annual,
    initial_insurance_pct_annual=initial_insurance_pct_annual,
    initial_hoa_monthly=initial_hoa_monthly,
    initial_ground_lease_monthly=initial_ground_lease_monthly,
    initial_pmi_financing_fees_monthly=initial_pmi_financing_fees_monthly,
    property_tax_based_on_affordable_price=property_tax_based_on_affordable_price,
    initial_downpayment_assistance_amount=initial_downpayment_assistance_amount,
    initial_downpayment_assistance_covers_buyer_contribution_check=initial_downpayment_assistance_covers_buyer_contribution_check,
    initial_affordability_gap_amount=initial_affordability_gap_amount,
    initial_holding_period_years=initial_holding_period_years,
    vale_resale_capped=vale_resale_capped,
    subtract_sunk_costs=subtract_sunk_costs,
    cost_model=cost_model,
    adjust_for_inflation=adjust_for_inflation,
    general_inflation_rate=(general_inflation_rate / 100.0)
)
# END Section 2 #############################################################################################



#############################################################################################################
# Section 3a: Convert fundamentals of Affordability Metrics
#############################################################################################################
#st.subheader("Affordabilty Metrics")
st.markdown("<h3 style='text-align: center;'>Affordabilty Metrics</h3>", unsafe_allow_html=True)

# Instantiate Income Availability
initial_annual_income = float(proj["InitialAnnualTargetIncome"].iloc[0])
initial_monthly_income = float(proj["InitialMonthlyTargetIncome"].iloc[0])
initial_annual_income_avail_for_housing = float(proj["InitialAnnualTargetIncomeAvailForHousing"].iloc[0])
initial_monthly_income_avail_for_housing = float(proj["InitialMonthlyTargetIncomeAvailForHousing"].iloc[0])

# Instantiate Static Costs
initial_hoa_annually = float(proj["InitialHOAAnnually"].iloc[0])
initial_ground_lease_annually = float(proj["InitialGroundLeaseAnnually"].iloc[0])
initial_pmi_financing_fees_annually = float(proj["InitialPMIandFinancingFeesAnnually"].iloc[0])
initial_pmi_financing_fees_monthly = float(proj["InitialPMIandFinancingFeesMonthly"].iloc[0])
initial_static_costs_monthly = float(proj["InitialStaticCostsMonthly"].iloc[0])
initial_mortgage_rate_annually_decimal = float(proj["InitialMortgageRateAnnually"].iloc[0])
initial_mortgage_affordable_closing_costs = float(proj["InitialClosingCostsAffordable"].iloc[0])

# Instantiate Solved Property Financials
initial_max_loan_amount_affordable = float(proj["InitialMaxLoanAmountAffordable"].iloc[0])
initial_total_downpayment_amount_affordable = float(proj["InitialTotalDownpaymentAmountAffordable"].iloc[0])
initial_buyer_cash_contribution_downpayment = float(proj["InitialBuyerCashContributionDownpayment"].iloc[0])
initial_downpayment_assistance_amount = float(proj["InitialDownpaymentAssistanceAmount"].iloc[0])
initial_affordable_purchase_price_paid_by_resident_owner = float(proj["InitialPurchasePriceAffordable"].iloc[0])
initial_property_taxes_amount_annual = float(proj["InitialPropertyTaxAmountAnnual"].iloc[0])
initial_property_taxes_amount_monthly = float(proj["InitialPropertyTaxAmountMonthly"].iloc[0])
initial_insurance_amount_annual = float(proj["InitialInsuranceAmountAnnual"].iloc[0])
initial_insurance_amount_monthly = float(proj["InitialInsuranceAmountMonthly"].iloc[0])
initial_avail_mortgage_payment_monthly_affordable = float(proj["InitialAvailMortgagePaymentMonthlyAffordable"].iloc[0])
initial_subsidy_required = float(proj["InitialSubsidyRequired"].iloc[0])
initial_affordability_gap_amount = float(proj["InitialAffordabilityGapAmount"].iloc[0])
initial_remaining_subsidy_required = float(proj["InitialRemainingSubsidyRequired"].iloc[0])
initial_total_other_housing_annual = float(proj["InitialTotalOtherHousingAnnual"].iloc[0])
initial_total_other_housing_monthly = float(proj["InitialTotalOtherHousingMonthly"].iloc[0])

# END Section 3a #############################################################################################



#############################################################################################################
# Section 3c: Show fundamentals of Affordability Metrics
#############################################################################################################

def render_affordability_subsidy_widget(data: dict):
    """
    Renders an HTML/CSS spreadsheet-style widget matching the visual design
    and layout of image_9a4dfd.png, now complete with interactive info hovers.
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
                <td style="text-align: right;">{f_curr(data['initial_target_income_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_target_income_monthly'])}</td>
            </tr>
            <!-- Available for Housing Costs -->
            <tr>
                <td>
                    Available for housing costs
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The total budget allocated for all housing expenses under the standard 30% household affordability limit.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['initial_avail_housing_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_avail_housing_monthly'])}</td>
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
                <td style="text-align: right;">{f_curr(data['initial_prop_taxes_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_prop_taxes_monthly'])}</td>
            </tr>
            <!-- Insurance -->
            <tr>
                <td style="padding-left: 24px;">
                    Insurance
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Estimated homeowner's hazard and liability insurance premiums.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['initial_insurance_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_insurance_monthly'])}</td>
            </tr>
            <!-- HOA -->
            <tr>
                <td style="padding-left: 24px;">
                    Home Owners Association Dues
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Monthly dues required by the HOA for shared community property maintenance, if applicable.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['initial_hoa_annually'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_hoa_monthly'])}</td>
            </tr>
            <!-- Ground Lease -->
            <tr>
                <td style="padding-left: 24px;">
                    Ground Lease or Admin Fee
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Monthly fee paid to the Community Land Trust (CLT) to support the ground lease and program administration.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['initial_ground_lease_annually'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_ground_lease_monthly'])}</td>
            </tr>
            <!-- PMI/Other -->
            <tr>
                <td style="padding-left: 24px;">
                    PMI, Additional Financing Fees
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Private Mortgage Insurance or other ongoing transaction-specific financing fees.</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['initial_pmi_financing_fees_annually'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_pmi_financing_fees_monthly'])}</td>
            </tr>
            <!-- Total Other Housing Costs -->
            <tr class="sheet-row-bold sheet-row-divider">
                <td>
                    Total other housing costs
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The combined sum of non-mortgage housing expenses (taxes, insurance, lease, HOA, and PMI).</span></span>
                </td>
                <td style="text-align: right;">{f_curr(data['initial_total_other_housing_annual'])}</td>
                <td style="text-align: right;">{f_curr(data['initial_total_other_housing_monthly'])}</td>
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
                <td style="text-align: right;">{f_curr(data['initial_avail_mortgage_monthly_affordable'])}</td>
            </tr>
            <!-- Interest Rate -->
            <tr>
                <td>
                    Mortgage Interest Rate
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The mortgage interest rate applied to calculate maximum borrowing capacity.</span></span>
                </td>
                <td></td>
                <td style="text-align: right; font-weight: 500;">{f_pct(data['initial_mortgage_rate_annually_decimal'])}</td>
            </tr>
            <!-- Max Loan -->
            <tr class="sheet-row-bold">
                <td>
                    Maximum loan amount
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The maximum mortgage principal supported by the available monthly mortgage payment over a 30-year amortization.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_max_loan_amount_affordable'])}</td>
            </tr>
            <!-- Gap spacing -->
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <!-- Downpayment -->
            <tr>
                <td>
                    Buyer Downpayment Contribution
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The buyer's upfront cash down payment (e.g., 5% of the affordable purchase price).</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_buyer_cash_contribution_downpayment'])}</td>
            </tr>
            <!-- Downpayment Assistance Grant -->
            <tr>
                <td>
                    Downpayment Assistance
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Outside grant that pays downpayment - directly builds buyer's equity</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_downpayment_assistance_amount'])}</td>
            </tr>
            <!-- Total All Downpayment -->
                        <tr class="sheet-row-bold">
                            <td>
                                Total All Downpayment
                                <span class="tooltip-container">&#9432;<span class="tooltip-text">Sum of all downpayments</span></span>
                            </td>
                            <td></td>
                            <td style="text-align: right;">{f_curr(data['initial_total_downpayment_affordable'])}</td>
                        </tr>
            <!-- Gap spacing -->
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <!-- Closing Costs -->
            <tr>
                <td>
                    Closing Costs
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">These are the total closing costs that both buyers (typically can include: loan fees, appraisals, inspections, title insurance, prorated taxes) & sellers (typically can include: agent commissions, transfer taxes, property adjustment) pay</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_mortgage_affordable_closing_costs'])}</td>
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
            <tr class="sheet-row-bold sheet-row-divider">
                <td>
                    Affordable Purchase Price
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The maximum total purchase price a qualified buyer at the target income can afford to pay (Maximum Loan + Downpayment).</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_affordable_purchase_price'])}</td>
            </tr>
            <!-- Gap spacing -->
            <tr><td colspan="3" style="height: 10px;"></td></tr>
            <!-- Total Subsidy Required -->
            <tr>
                <td>
                    Total "Affordability Gap" Subsidy
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The total capital subsidy required to bridge the gap between unrestricted market value and the calculated affordable purchase price.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_subsidy_required'])}</td>
            </tr>
            <!-- Fundraised Subsidy -->
            <tr>
                <td>
                    Fundraised Subsidy (Secured)
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">Capital already raised towards bridging the affordability gap.</span></span>
                </td>
                <td></td>
                <td style="text-align: right; color: #00684a;">- {f_curr(data['initial_affordability_gap_amount'])}</td>
            </tr>
            <!-- Highlighted Bottom Row: Remaining Subsidy Required -->
            <tr class="sheet-highlight-box">
                <td>
                    Remaining Subsidy to Fundraise
                    <span class="tooltip-container">&#9432;<span class="tooltip-text">The outstanding gap that still needs to be funded to make the project viable.</span></span>
                </td>
                <td></td>
                <td style="text-align: right;">{f_curr(data['initial_remaining_subsidy_required'])}</td>
            </tr>
        </table>
    </div>
    """
    
    st.markdown(html_content, unsafe_allow_html=True)
# END def render_affordability_subsidy_widget ####################################################################################
# END Section 3c: Show fundamentals of Affordability Metrics #####################################################################



#RENDER
if __name__ == "__main__":
    
    sample_financials = {
        "initial_target_income_annual": initial_annual_income,
        "initial_target_income_monthly": initial_monthly_income,
        "initial_avail_housing_annual": initial_annual_income_avail_for_housing,
        "initial_avail_housing_monthly": initial_monthly_income_avail_for_housing,
        "initial_prop_taxes_annual": initial_property_taxes_amount_annual,
        "initial_prop_taxes_monthly": initial_property_taxes_amount_monthly,
        "initial_insurance_annual": initial_insurance_amount_annual,
        "initial_insurance_monthly": initial_insurance_amount_monthly,
        "initial_hoa_annually": initial_hoa_annually,
        "initial_hoa_monthly": initial_hoa_monthly,
        "initial_ground_lease_annually": initial_ground_lease_annually,
        "initial_ground_lease_monthly": initial_ground_lease_monthly,
        "initial_pmi_financing_fees_annually": initial_pmi_financing_fees_annually,
        "initial_pmi_financing_fees_monthly": initial_pmi_financing_fees_monthly,
        "initial_total_other_housing_annual": initial_total_other_housing_annual,
        "initial_total_other_housing_monthly": initial_total_other_housing_monthly,
        "initial_avail_mortgage_monthly_affordable": initial_avail_mortgage_payment_monthly_affordable,
        "initial_mortgage_rate_annually_decimal": initial_mortgage_rate_annually_decimal,
        "initial_max_loan_amount_affordable": initial_max_loan_amount_affordable,
        "initial_total_downpayment_affordable": initial_total_downpayment_amount_affordable,
        "initial_buyer_cash_contribution_downpayment": initial_buyer_cash_contribution_downpayment,
        "initial_downpayment_assistance_amount": initial_downpayment_assistance_amount,
        "initial_mortgage_affordable_closing_costs": initial_mortgage_affordable_closing_costs,
        "outside_gap_loan": 0.0,
        "initial_affordable_purchase_price": initial_affordable_purchase_price_paid_by_resident_owner,
        "initial_subsidy_required": initial_subsidy_required,
        "initial_affordability_gap_amount": initial_affordability_gap_amount,
        "initial_remaining_subsidy_required": initial_remaining_subsidy_required,
    }

    render_affordability_subsidy_widget(sample_financials)


#############################################################################################################
# Section 4: Layout main charts in a 2x2 grid and table of results
#############################################################################################################
y_axis_suffix = " (in Today's Dollars)" if adjust_for_inflation else " ($)"

# --- TOP ROW ---
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown(
    """<p style='font-size:16px; font-weight: bold; text-align: center'>Resale Asking Price (Market Rate vs Fixed Rate vs AMI 
    Rate Returns)<span class="tooltip-container">&#9432;<span class="tooltip-text">How much money a Homeowner could roughly expect
     to ask for thier home - after a given time period - when selling on either the open market, or in accordance with the Resale 
    Restriction of VALE Fixed or an AMI based formula</span></span></p>""",
    unsafe_allow_html=True
)
    sale_price_fig = go.Figure()
    sale_price_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['InitialMarketRateValue'], mode='lines+markers', name='Resale Price (Market)', line=dict(color='#3cb44b', width=2),  marker=dict(symbol='diamond', size=8), hovertemplate="Market - Year: %{x}<br>Home Price: %{y:$,.0f}<extra></extra>"))
    sale_price_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['InitialVALEFixedRateValue'], mode='lines+markers', name='Resale Price (Fixed)', line=dict(color='#F46A25', width=2),  marker=dict(symbol='star', size=8), hovertemplate="Fixed - Year: %{x}<br>Home Price: %{y:$,.0f}<extra></extra>"))
    sale_price_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['InitialAMIRateValue'], mode='lines+markers', name='Resale Price (AMI)', line=dict(color='#4363d8', width=2),  marker=dict(symbol='cross', size=8), hovertemplate="AMI - Year: %{x}<br>Home Price: %{y:$,.0f}<extra></extra>"))
    sale_price_fig.update_layout(
        xaxis_title='<b>Years</b>', 
        yaxis_title=f'<b>Proceeds at Sale{y_axis_suffix}</b>',
        margin=dict(l=40, r=20, t=20, b=40),
        yaxis=dict(autorange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14), itemclick="toggle", itemdoubleclick="toggleothers")
    )
    st.plotly_chart(sale_price_fig, use_container_width=True)

with row1_col2:
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
    net_proceeds_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleNetWealthBuiltMarket'], mode='lines+markers', name='Equity Gained (Market)', line=dict(color='#3cb44b', width=2),  marker=dict(symbol='diamond', size=8), hovertemplate="Market - Year: %{x}<br>Equity Earned: %{y:$,.0f}<extra></extra>"))
    net_proceeds_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleNetWealthBuiltFixed'], mode='lines+markers', name='Equity Gained (Fixed)', line=dict(color='#F46A25', width=2),  marker=dict(symbol='star', size=8), hovertemplate="Fixed - Year: %{x}<br>Equity Earned: %{y:$,.0f}<extra></extra>"))
    net_proceeds_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleNetWealthBuiltAMI'], mode='lines+markers', name='Equity Gained (AMI)', line=dict(color='#4363d8', width=2),  marker=dict(symbol='cross', size=8), hovertemplate="AMI - Year: %{x}<br>Equity Earned: %{y:$,.0f}<extra></extra>"))
    net_proceeds_fig.update_layout(
        xaxis_title='<b>Years</b>', 
        yaxis_title=f'<b>Net Proceeds / Wealth Built{y_axis_suffix}</b>',
        margin=dict(l=40, r=20, t=20, b=40),
        yaxis=dict(autorange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14), itemclick="toggle", itemdoubleclick="toggleothers")
    )
    st.plotly_chart(net_proceeds_fig, use_container_width=True)

# --- BOTTOM ROW ---
row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.markdown(
    """<p style='font-size:16px; font-weight: bold; text-align: center'>Continuing Affordability (Target AMI % Over Time)
    <span class="tooltip-container">&#9432;<span class="tooltip-text">Tracks the AMI percentage needed for the second buyer to 
    purchase the home without exceeding the housing cost burden, assuming the same downpayment and prevailing resale interest rate.</span></span></p>""",
    unsafe_allow_html=True
)
    continuing_affordability_fig = go.Figure()
    continuing_affordability_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleContinuingAffordabilityPctOfAMIFixed'], mode='lines+markers', name='Required AMI % (Fixed Formula)', line=dict(color='#F46A25', width=2), marker=dict(symbol='star', size=8), hovertemplate="Fixed - Year: %{x}<br>AMI Required: %{y:.1f}%<extra></extra>"))
    continuing_affordability_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleContinuingAffordabilityPctOfAMIAMI'], mode='lines+markers', name='Required AMI % (AMI Formula)', line=dict(color='#4363d8', width=2), marker=dict(symbol='cross', size=8), hovertemplate="AMI - Year: %{x}<br>AMI Required: %{y:.1f}%<extra></extra>"))
    
    # Adds a dashed horizontal threshold line denoting the original affordability target
    continuing_affordability_fig.add_hline(y=initial_affordability_pct_of_ami, line_dash="dash", line_color="gray", annotation_text=f"Initial Target ({initial_affordability_pct_of_ami}%)")
    
    continuing_affordability_fig.update_layout(
        xaxis_title='<b>Years</b>', 
        yaxis_title='<b>Required Area Median Income (AMI) %</b>',
        margin=dict(l=40, r=20, t=20, b=40),
        yaxis=dict(autorange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14))
    )
    st.plotly_chart(continuing_affordability_fig, use_container_width=True)

with row2_col2:
    st.markdown(
    """<p style='font-size:16px; font-weight: bold; text-align: center'>CLT Community Equity Share Over Time
    <span class="tooltip-container">&#9432;<span class="tooltip-text">Tracks the expanding gap between the home's open-market 
    value and its restricted affordable price. This represents the total capital/subsidy successfully retained within the community.</span></span></p>""",
    unsafe_allow_html=True
)
    clt_equity_fig = go.Figure()
    clt_equity_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleCLTEquityAmountFixed'], mode='lines+markers', name='CLT Equity (Fixed Formula)', line=dict(color='#F46A25', width=2), marker=dict(symbol='star', size=8), hovertemplate="Fixed - Year: %{x}<br>CLT Equity: %{y:$,.0f}<extra></extra>"))
    clt_equity_fig.add_trace(go.Scatter(x=proj['Year'], y=proj['ResaleCLTEquityAmountAMI'], mode='lines+markers', name='CLT Equity (AMI Formula)', line=dict(color='#4363d8', width=2), marker=dict(symbol='cross', size=8), hovertemplate="AMI - Year: %{x}<br>CLT Equity: %{y:$,.0f}<extra></extra>"))
    clt_equity_fig.update_layout(
        xaxis_title='<b>Years</b>', 
        yaxis_title=f'<b>Retained Subsidy / CLT Equity{y_axis_suffix}</b>',
        margin=dict(l=40, r=20, t=20, b=40),
        yaxis=dict(autorange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14))
    )
    st.plotly_chart(clt_equity_fig, use_container_width=True)

st.subheader("Yearly Proceeds Detail")
saved_cols = ['Year', 'InitialVALEFixedRateValue', 'ResaleNetWealthBuiltFixed', 'GrossAppreciationFixed', 'PrincipalRepaidAffordable', 'BuyerClosingCostsAffordable', 'SellerClosingCostsFixed']
st.dataframe(proj[saved_cols], hide_index=True)


# Export
csv = proj.to_csv(index=False).encode('utf-8')
st.download_button("Download projections CSV", data=csv, file_name='projections.csv', mime='text/csv')
# END Section 4 #############################################################################################



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