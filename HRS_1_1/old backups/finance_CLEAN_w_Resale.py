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
    #market_rate_value = initial_market_value * ((1 + market_home_price_inflation_rate / 100) ** years)
    #vale_fixed_rate_value = initial_market_value * ((1 + vale_resale_fixed_index_pct / 100) ** years)
    #ami_rate_value = initial_market_value  * ((1 + area_median_income_inflation / 100) ** years)

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

    # Monthly mortgage amortization factor (i.e., 30 years is 360 months)
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
    market_rate_value = []
    vale_fixed_rate_value = []
    ami_rate_value = []
    
    remaining_mortgage_balance = []
    
    # Net Proceeds (Cash back at sale)
    proceeds_market = []
    proceeds_fixed = []
    proceeds_ami = [] 
    
    # Equity Gains (Wealth Built)
    equity_gain_market = []
    equity_gain_fixed = []
    equity_gain_ami = [] 
    
    # Lifecycle Cashflow Changes (Proceeds - Holding Costs)
    net_cashflow_change_market = []
    net_cashflow_change_fixed = []
    net_cashflow_change_ami = [] 
    
    cumulative_principal_paid = []
    cumulative_interest_paid = []
    cumulative_property_taxes = []
    cumulative_insurance = []
    cumulative_hoa = []
    cumulative_other = []
    cumulative_total_payments = []
    
    affordability_bound = []

    for t in years:
        # 1. Resale Valuations (Using robust pythonic exponentiation '**')
        current_market_val = initial_market_value * ((1 + market_home_price_inflation_rate / 100.0) ** t)
        current_fixed_val = affordable_purchase_price * ((1 + vale_resale_fixed_index_pct / 100.0) ** t)
        
        # AMI-Indexed Resale Value
        current_ami_scalar = (1 + area_median_income_inflation / 100.0) ** t
        current_ami_val = affordable_purchase_price * current_ami_scalar

        # Optional Cap Logic: resale price cannot exceed market value
        if vale_resale_capped:
            current_fixed_val = min(current_fixed_val, current_market_val)
            current_ami_val = min(current_ami_val, current_market_val)

        market_rate_value.append(current_market_val)
        vale_fixed_rate_value.append(current_fixed_val)
        ami_rate_value.append(current_ami_val)

        # 2. Mortgage Paydown Amortization (t years * 12 months)
        m_elapsed = t * 12
        if m_elapsed == 0:
            loan_bal = max_loan_amount
            cum_p_paid = 0.0
            cum_i_paid = 0.0
        elif m_elapsed >= length_of_mortgage_in_months:
            loan_bal = 0.0
            cum_p_paid = max_loan_amount
            cum_i_paid = (avail_mortgage_payment_monthly * length_of_mortgage_in_months) - max_loan_amount
        else:
            # Standard Amortization Payoff Formula
            loan_bal = max_loan_amount * (((1 + mortgage_rate_monthly) ** length_of_mortgage_in_months) - ((1 + mortgage_rate_monthly) ** m_elapsed)) / (((1 + mortgage_rate_monthly) ** length_of_mortgage_in_months) - 1)
            total_payments_made = avail_mortgage_payment_monthly * m_elapsed
            cum_p_paid = max_loan_amount - loan_bal
            cum_i_paid = total_payments_made - cum_p_paid

        remaining_mortgage_balance.append(loan_bal)
        cumulative_principal_paid.append(cum_p_paid)
        cumulative_interest_paid.append(cum_i_paid)

        # 3. Cumulative Holding and Operating Outlays
        cum_taxes = property_taxes_amount_monthly * 12 * t
        cum_ins = insurance_amount_monthly * 12 * t
        cum_hoa_dues = hoa_monthly * 12 * t
        cum_other = other_costs_monthly * 12 * t

        cumulative_property_taxes.append(cum_taxes)
        cumulative_insurance.append(cum_ins)
        cumulative_hoa.append(cum_hoa_dues)
        cumulative_other.append(cum_other)
        
        total_payments = (avail_mortgage_payment_monthly * 12 * t) + cum_taxes + cum_ins + cum_hoa_dues + cum_other
        cumulative_total_payments.append(total_payments)

        # 4. Exit Costs & Net Sales Proceeds
        selling_costs_market = current_market_val * (selling_cost_pct / 100.0)
        selling_costs_fixed = current_fixed_val * (selling_cost_pct / 100.0)
        selling_costs_ami = current_ami_val * (selling_cost_pct / 100.0) 

        # Net Cash back to homeowner: Price - Loan Payoff - Selling Costs
        net_proc_market = max(0.0, current_market_val - loan_bal - selling_costs_market)
        net_proc_fixed = max(0.0, current_fixed_val - loan_bal - selling_costs_fixed)
        net_proc_ami = max(0.0, current_ami_val - loan_bal - selling_costs_ami) 

        proceeds_market.append(net_proc_market)
        proceeds_fixed.append(net_proc_fixed)
        proceeds_ami.append(net_proc_ami) 

        # 5. Wealth Earned / Individual Equity Gain
        # Net proceeds minus initial downpayment
        equity_gain_market.append(net_proc_market - downpayment_amount)
        equity_gain_fixed.append(net_proc_fixed - downpayment_amount)
        equity_gain_ami.append(net_proc_ami - downpayment_amount) 

        # Cumulative Net Cashflow (Proceeds minus total out-of-pocket costs)
        net_cashflow_change_market.append(net_proc_market - downpayment_amount - total_payments)
        net_cashflow_change_fixed.append(net_proc_fixed - downpayment_amount - total_payments)
        net_cashflow_change_ami.append(net_proc_ami - downpayment_amount - total_payments) 

        # 6. Community Affordability Index Metric
        # Percent AMI needed for a future buyer to afford this home under resale conditions
        affordability_bound.append(affordability_pct_of_ami * current_ami_scalar)

    # ==========================================
    # CONSTRUCT RETURN DATAFRAME
    # ==========================================
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
            # Net Proceeds
            "ProceedsAtSaleMarket": np.round(proceeds_market, 2),
            "ProceedsAtSaleFixed": np.round(proceeds_fixed, 2),
            "ProceedsAtSaleAMI": np.round(proceeds_ami, 2), 
            # Individual Equity/Wealth built
            "EquityGainMarket": np.round(equity_gain_market, 2),
            "EquityGainFixed": np.round(equity_gain_fixed, 2),
            "EquityGainAMI": np.round(equity_gain_ami, 2), 
            # Full lifecycle cashflow
            "NetCashflowChangeMarket": np.round(net_cashflow_change_market, 2),
            "NetCashflowChangeFixed": np.round(net_cashflow_change_fixed, 2),
            "NetCashflowChangeAMI": np.round(net_cashflow_change_ami, 2), 
            # Amortization details
            "RemainingMortgageBalance": np.round(remaining_mortgage_balance, 2),
            "CumulativePrincipalPaid": np.round(cumulative_principal_paid, 2),
            "CumulativeInterestPaid": np.round(cumulative_interest_paid, 2),
            # Cumulative expenses
            "CumulativePropertyTaxes": np.round(cumulative_property_taxes, 2),
            "CumulativeInsurance": np.round(cumulative_insurance, 2),
            "CumulativeHOA": np.round(cumulative_hoa, 2),
            "CumulativeOtherCosts": np.round(cumulative_other, 2),
            "TotalPayments": np.round(cumulative_total_payments, 2),
            "AffordabilityBound": np.round(affordability_bound, 2)
        }
    )

    return financials_df



