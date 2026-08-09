import numpy as np
import pandas as pd
import math
import streamlit as st


# TENTATIVE: Household size adjustment factors per HUD guidance
# Base factor = 1.0 for 4-person household
# These adjust AMI values for different household sizes
HOUSEHOLD_SIZE_FACTORS = {
    1: 0.70,
    2: 0.80,
    3: 0.90,
    4: 1.00,
    5: 1.08,
    6: 1.16,
    7: 1.24,
    8: 1.32,
}


# def get_ami_for_household_size(ami_4person_100pct, household_size, affordability_pct=100):
#     """
#     Calculate AMI for a given household size based on 4-person 100% AMI.
    
#     TENTATIVE: Uses HUD standard adjustment factors.
    
#     - ami_4person_100pct: the 100% AMI for a 4-person household (e.g., $93,100)
#     - household_size: household size (1-8)
#     - affordability_pct: the affordability tier as a percentage (e.g., 80 for 80% AMI)
    
#     Returns: affordability bound for the given household size and tier
#     """
#     factor = HOUSEHOLD_SIZE_FACTORS.get(household_size, 1.0)
#     ami_for_size = ami_4person_100pct * factor
#     affordability_bound = ami_for_size * (affordability_pct / 100.0)
#     return affordability_bound


def compute_projections(
    initial_market_value,
    affordability_pct_of_ami,
    market_home_price_inflation_rate,
    area_median_income_inflation,
    perc_income_spent_on_housing,
    ami_initial_four_person_dollar_amount,
    vale_resale_fixed_index_pct,
    household_size,
    mortgage_rate_start,
    mortgage_rate_resale,
    downpayment_pct,
    closing_cost_pct,
    selling_cost_pct,
    length_of_mortgage_years,
    property_tax_pct_annual,
    insurance_pct_annual,
    hoa_monthly,
    ground_lease_monthly,
    other_costs_monthly,
    property_tax_based_on_affordable_price,
    holding_period_years,
    vale_resale_capped,
):
    """
    Compute year-by-year projections for market value vs fixed resale formula.

    Notes / assumptions (TENTATIVE - please review and refine):
    - Market value grows at `market_inflation_rate` compounded annually.
    - Fixed price follows `initial_market_value * (1 + fixed_index_rate)^t`.
    - Affordability price bound is calculated from household-size-adjusted AMI:
      For a given household_size and affordability_pct_of_ami, the bound is:
      `(ami_initial * household_size_factor) * affordability_pct * year_index^(inflation_rate)`
      This allows a "next buyer" to understand what the home would cost at different affordability tiers.
    - Mortgage costs and net proceeds: net_proceeds = sale_price - remaining_mortgage_balance - selling_costs - operating_costs.
      Remaining mortgage balance uses simple 30-year amortization (no PMI, escrow, or property-tax-in-escrow modeling).
    - Property taxes, insurance, HOA, and other costs are annualized and deducted at sale.
    
    Domain flags:
    - Property tax rate (1.2%) is annual on market value; may need to account for Prop 2.5 (Mass.) or other state caps.
    - Ground lease ($50) is currently treated as a fixed annual cost; may need to model as escalating rent.
    - CAP ensures resale formula values do not exceed market rate home prices in the event that speculative market rates drop for extended periods.
    - Market share cap prevents fixed price from rising above market value * cap_pct.
    """

    # Calculate the annual resale value of the home for 1) Market Rate; 2) VALE Fixed Rate; 3) AMI Rate
    # This creates a series/vector/array of values from year 0 until the end of the holding_period_years
    years = np.arange(0, holding_period_years + 1)
    market_rate_value = initial_market_value * ((1 + market_home_price_inflation_rate / 100) ** years)
    vale_fixed_rate_value = initial_market_value * ((1 + vale_resale_fixed_index_pct / 100) ** years)
    ami_rate_value = initial_market_value  * ((1 + area_median_income_inflation / 100) ** years)

    # Establish the baseline income that is available for the buyer
    household_size_factor = HOUSEHOLD_SIZE_FACTORS.get(household_size, 1.0)
    target_income_annual = ami_initial_four_person_dollar_amount * (affordability_pct_of_ami / 100) * household_size_factor
    target_income_annual_available_for_housing = target_income_annual * (perc_income_spent_on_housing / 100)
    target_income_monthly = target_income_annual / 12
    target_income_monthly_available_for_housing = target_income_annual_available_for_housing / 12



    ###############################################################
    # Section A: Figure out Affordable Price
    ###############################################################
    # Calculate Static Costs
    static_costs_monthly = hoa_monthly + ground_lease_monthly + other_costs_monthly

    # Monthly mortgage amortization factor (30 years is 360 months)
    mortgage_rate_monthly = (mortgage_rate_start / 100.0) / 12.0
    length_of_mortgage_in_months = length_of_mortgage_years * 12

    if mortgage_rate_monthly > 0:
        amortization_factor = (mortgage_rate_monthly * math.pow(1 + mortgage_rate_monthly, length_of_mortgage_in_months)) / (math.pow(1 + mortgage_rate_monthly, length_of_mortgage_in_months) - 1)
    else:
        amortization_factor = 1.0 / length_of_mortgage_in_months
    
    # Convert Property Tax & Insurance rates to decimal
    property_tax_rate_annual_decimal = (property_tax_pct_annual / 100.0)
    insurance_rate_annual_decimal = (insurance_pct_annual / 100.0)
    downpayment_rate_decimal = (downpayment_pct / 100.0)

    # Insurance is ALWAYS calculated based on Initial Market Value (rebuild/appraisal benchmark)
    # Insurance Adjustment Factor is a constant made up/derived/calculated based on assumptions
    # to keep calculated insurance prices in-line with reality
    INSURANCE_AJUSTMENT_FACTOR = 0.70588
    insurance_amount_annual = math.ceil((initial_market_value * insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
    insurance_amount_monthly = insurance_amount_annual / 12.0

    if property_tax_based_on_affordable_price:
        # Scenario 1: Taxes are based on Affordable Purchase Price (Circular)
        # Insurance is treated as a fixed monthly cost in the numerator
        # Taxes scale dynamically with solved Affordable Purchase Price
        numerator = target_income_monthly_available_for_housing - static_costs_monthly - insurance_amount_monthly
        # Denominator scales with P&I and Taxes (No Insurance factor in denominator!)
        denominator = ((1.0 - downpayment_rate_decimal) * amortization_factor) + (property_tax_rate_annual_decimal / 12.0)
    else:
        # Scenario 2: Taxes are based on Market Value (Fixed)
        property_taxes_amount_annual = math.ceil(initial_market_value * property_tax_rate_annual_decimal)
        property_taxes_amount_monthly = math.ceil(property_taxes_amount_annual / 12.0)
        
        # Both Taxes and Insurance act as fixed deductions in the numerator
        numerator = target_income_monthly_available_for_housing - static_costs_monthly - insurance_amount_monthly - property_taxes_amount_monthly
        
        # Denominator only scales with P&I
        denominator = (1.0 - downpayment_rate_decimal) * amortization_factor


    if denominator > 0 and numerator > 0:
        affordable_purchase_price = numerator / denominator
    else:
        affordable_purchase_price = 0.0
    
    # Deriving linear outputs from the solved Purchase Price
    max_loan_amount = affordable_purchase_price * (1.0 - downpayment_rate_decimal)
    downpayment_amount = math.ceil(affordable_purchase_price * downpayment_rate_decimal)

    # Calculate Property Taxes - based on affordable if the box is checked - some municipalities might base it on market rate
    if property_tax_based_on_affordable_price:
        property_taxes_amount_annual = math.ceil(affordable_purchase_price * property_tax_rate_annual_decimal)
        property_taxes_amount_monthly = math.ceil(property_taxes_amount_annual / 12.0)

    avail_mortgage_payment_monthly = max_loan_amount * amortization_factor
    subsidy_required = max(0.0, initial_market_value - affordable_purchase_price)
    # END Section A: Figure out Affordable Price ##############################################################



    ###############################################################
    # Section B: Resale
    ###############################################################
    


    # END Section B: Resale ##############################################################


    financials_df = pd.DataFrame(
        {
            "Year": years,
            "MarketRateValue": np.round(market_rate_value, 2),
            "VALEFixedRateValue": np.round(vale_fixed_rate_value, 2),
            "AMIRateValue": np.round(ami_rate_value, 2),
            "AnnualTargetIncome": target_income_annual,
            "AnnualTargetIncomeAvailForHousing": target_income_annual_available_for_housing,
            "MonthlyTargetIncome": target_income_monthly,
            "MonthlyTargetIncomeAvailForHousing": target_income_monthly_available_for_housing,
            "StaticCostsMonthly": static_costs_monthly,
            "MaxLoanAmount": max_loan_amount,
            "DownpaymentAmount": downpayment_amount,
            "PropertyTaxAmountAnnual": property_taxes_amount_annual,
            "PropertyTaxAmountMonthly": property_taxes_amount_monthly,
            "InsuranceAmountAnnual": insurance_amount_annual,
            "InsuranceAmountMonthly": insurance_amount_monthly,
            "AvailMortgagePaymentMonthly": avail_mortgage_payment_monthly,
            "SubsidyRequired": subsidy_required,
        }
    )

    return financials_df



