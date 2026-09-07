import numpy as np
import pandas as pd
import math

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

# Activated when vale_resale_capped is TRUE to ensure that a CLT home does not sell for more than 80% of market rate
CAP_PERCENTAGE_FOR_MAINTAINING_AFFORDABILITY_DURING_MARKET_DOWNTURN = 0.8

def compute_projections(
    initial_market_value,
    initial_affordability_pct_of_ami,
    initial_market_home_price_inflation_rate,
    initial_area_median_income_inflation,
    initial_perc_income_spent_on_housing,
    initial_ami_four_person_dollar_amount,
    initial_vale_resale_fixed_index_pct,
    initial_household_size,
    initial_mortgage_rate,
    resale_mortgage_rate,
    initial_downpayment_pct,
    initial_closing_cost_pct,
    resale_selling_cost_pct,
    initial_length_of_mortgage_years,
    using_FHA_loan,
    initial_property_tax_pct_annual,
    initial_insurance_pct_annual,
    initial_hoa_monthly,
    initial_ground_lease_monthly,
    initial_pmi_financing_fees_monthly,
    property_tax_based_on_affordable_price,
    insurance_based_on_affordable_price,
    initial_downpayment_assistance_amount,
    initial_downpayment_assistance_covers_buyer_contribution_check,
    initial_affordability_gap_amount,
    initial_holding_period_years,
    vale_resale_capped,
    subtract_sunk_costs,
    cost_model,
    adjust_for_inflation,
    general_inflation_rate
):
    """
    Compute year-by-year projections for market value vs fixed resale formula.
    """
    
    # Ensure holding period is an integer so np.arange and array sizing functions properly
    initial_holding_period_years = int(initial_holding_period_years)
    initial_years = np.arange(0, initial_holding_period_years)
    
    # Establish the baseline income that is available for the buyer
    initial_household_size_factor = HOUSEHOLD_SIZE_FACTORS.get(initial_household_size, 1.0)
    initial_target_income_annual = initial_ami_four_person_dollar_amount * (initial_affordability_pct_of_ami / 100.0) * initial_household_size_factor
    initial_target_income_annual_available_for_housing = initial_target_income_annual * (initial_perc_income_spent_on_housing / 100.0)
    initial_target_income_monthly = initial_target_income_annual / 12.0
    initial_target_income_monthly_available_for_housing = initial_target_income_annual_available_for_housing / 12.0

    ###############################################################
    # Section A: Figure out Affordable Price (Two-Pass for PMI)
    ###############################################################
    initial_static_costs_monthly_no_pmi = initial_hoa_monthly + initial_ground_lease_monthly 
    initial_hoa_annually = initial_hoa_monthly * 12.0
    initial_ground_lease_annually = initial_ground_lease_monthly * 12.0

    initial_mortgage_rate_annually = initial_mortgage_rate / 100.0
    initial_mortgage_rate_monthly = initial_mortgage_rate_annually / 12.0
    initial_length_of_mortgage_in_months = int(initial_length_of_mortgage_years * 12)

    if initial_mortgage_rate_monthly > 0:
        amortization_factor = (initial_mortgage_rate_monthly * math.pow(1 + initial_mortgage_rate_monthly, initial_length_of_mortgage_in_months)) / (math.pow(1 + initial_mortgage_rate_monthly, initial_length_of_mortgage_in_months) - 1)
    else:
        amortization_factor = 1.0 / initial_length_of_mortgage_in_months
    
    initial_property_tax_rate_annual_decimal = (initial_property_tax_pct_annual / 100.0)
    initial_insurance_rate_annual_decimal = (initial_insurance_pct_annual / 100.0)
    initial_downpayment_rate_decimal = (initial_downpayment_pct / 100.0)
    INSURANCE_AJUSTMENT_FACTOR = 0.70588

    base_budget = initial_target_income_monthly_available_for_housing - initial_static_costs_monthly_no_pmi
    
    if insurance_based_on_affordable_price:
        ins_term = (initial_insurance_rate_annual_decimal * INSURANCE_AJUSTMENT_FACTOR / 12.0)
    else:
        ins_term = 0.0
        initial_insurance_amount_annual = math.ceil((initial_market_value * initial_insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
        initial_insurance_amount_monthly = initial_insurance_amount_annual / 12.0
        base_budget -= initial_insurance_amount_monthly

    if property_tax_based_on_affordable_price:
        tax_term = (initial_property_tax_rate_annual_decimal / 12.0)
    else:
        tax_term = 0.0
        initial_property_taxes_amount_annual = math.ceil(initial_market_value * initial_property_tax_rate_annual_decimal)
        initial_property_taxes_amount_monthly = math.ceil(initial_property_taxes_amount_annual / 12.0)
        base_budget -= initial_property_taxes_amount_monthly

    if initial_downpayment_assistance_covers_buyer_contribution_check:
        base_numerator = base_budget
    else:
        base_numerator = base_budget + (initial_downpayment_assistance_amount * amortization_factor)

    denominator = ((1.0 - initial_downpayment_rate_decimal) * amortization_factor) + tax_term + ins_term
    numerator_pass_1 = base_numerator
    P_pass_1 = numerator_pass_1 / denominator if (denominator > 0 and numerator_pass_1 > 0) else 0.0

    def calculate_downpayments(price):
        required_downpayment = math.ceil(price * initial_downpayment_rate_decimal)
        if initial_downpayment_assistance_covers_buyer_contribution_check:
            buyer_cash = max(500.0, required_downpayment - initial_downpayment_assistance_amount)
        else:
            buyer_cash = max(500.0, required_downpayment)
        total_equity = buyer_cash + initial_downpayment_assistance_amount
        return buyer_cash, total_equity

    buyer_cash_pass_1, total_equity_pass_1 = calculate_downpayments(P_pass_1)
    initial_buyer_equity_pct = total_equity_pass_1 / P_pass_1 if P_pass_1 > 0 else 0.0

    if initial_buyer_equity_pct >= 0.20 and not using_FHA_loan:
        initial_affordable_purchase_price = P_pass_1
        applied_pmi_monthly = 0.0
        initial_buyer_cash_contribution_downpayment = buyer_cash_pass_1
        initial_total_downpayment_amount_affordable = total_equity_pass_1
    else:
        applied_pmi_monthly = initial_pmi_financing_fees_monthly
        numerator_pass_2 = numerator_pass_1 - applied_pmi_monthly
        P_pass_2 = numerator_pass_2 / denominator if (denominator > 0 and numerator_pass_2 > 0) else 0.0
        
        initial_affordable_purchase_price = P_pass_2
        buyer_cash_pass_2, total_equity_pass_2 = calculate_downpayments(P_pass_2)
        initial_buyer_cash_contribution_downpayment = buyer_cash_pass_2
        initial_total_downpayment_amount_affordable = total_equity_pass_2
        initial_buyer_equity_pct = total_equity_pass_2 / P_pass_2 if P_pass_2 > 0 else 0.0

    initial_pmi_financing_fees_annually = applied_pmi_monthly * 12.0
    initial_static_costs_monthly = initial_static_costs_monthly_no_pmi + applied_pmi_monthly
    initial_max_loan_amount_affordable = initial_affordable_purchase_price - initial_total_downpayment_amount_affordable

    if property_tax_based_on_affordable_price:
        initial_property_taxes_amount_annual = math.ceil(initial_affordable_purchase_price * initial_property_tax_rate_annual_decimal)
        initial_property_taxes_amount_monthly = math.ceil(initial_property_taxes_amount_annual / 12.0)

    if insurance_based_on_affordable_price:
        initial_insurance_amount_annual = math.ceil((initial_affordable_purchase_price * initial_insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
        initial_insurance_amount_monthly = initial_insurance_amount_annual / 12.0

    initial_subsidy_required = max(0.0, initial_market_value - initial_affordable_purchase_price)
    initial_remaining_subsidy_required = max(0.0, initial_subsidy_required - initial_affordability_gap_amount)
    initial_total_other_housing_annual = math.ceil((initial_static_costs_monthly * 12) + initial_property_taxes_amount_annual + initial_insurance_amount_annual)
    initial_total_other_housing_monthly = initial_total_other_housing_annual / 12.0
    initial_avail_mortgage_payment_monthly_affordable = initial_target_income_monthly_available_for_housing - initial_total_other_housing_monthly


    ###############################################################
    # Section B: Resale & Array Computations
    ###############################################################
    initial_market_rate_value = initial_market_value * ((1 + initial_market_home_price_inflation_rate / 100.0) ** initial_years)
    initial_vale_fixed_rate_value = initial_affordable_purchase_price * ((1 + initial_vale_resale_fixed_index_pct / 100.0) ** initial_years)
    initial_ami_scalar = (1 + initial_area_median_income_inflation / 100.0) ** initial_years
    initial_ami_rate_value = initial_affordable_purchase_price * initial_ami_scalar

    if vale_resale_capped:
        for t in initial_years:
            initial_vale_fixed_rate_value[t] = min(initial_vale_fixed_rate_value[t], (initial_market_rate_value[t] * CAP_PERCENTAGE_FOR_MAINTAINING_AFFORDABILITY_DURING_MARKET_DOWNTURN))
            initial_ami_rate_value[t] = min(initial_ami_rate_value[t], (initial_market_rate_value[t] * CAP_PERCENTAGE_FOR_MAINTAINING_AFFORDABILITY_DURING_MARKET_DOWNTURN))

    initial_downpayment_amount_market = math.ceil(initial_market_rate_value[0] * initial_downpayment_rate_decimal)
    initial_mortgage_market_closing_costs = initial_market_rate_value[0] * (initial_closing_cost_pct / 100.0)
    initial_mortgage_market = initial_market_rate_value[0] - initial_downpayment_amount_market
    
    initial_mortgage_affordable_closing_costs = initial_affordable_purchase_price * (initial_closing_cost_pct / 100.0)
    initial_mortgage_affordable = initial_max_loan_amount_affordable 
    initial_affordable_purchase_price_paid_by_resident_owner = initial_mortgage_affordable + initial_total_downpayment_amount_affordable

    if initial_mortgage_rate_monthly > 0:
        initial_avail_mortgage_payment_monthly_market = initial_mortgage_market * (initial_mortgage_rate_monthly * (1 + initial_mortgage_rate_monthly)**initial_length_of_mortgage_in_months) / ((1 + initial_mortgage_rate_monthly)**initial_length_of_mortgage_in_months - 1)
    else:
        initial_avail_mortgage_payment_monthly_market = initial_mortgage_market / initial_length_of_mortgage_in_months
        
    balance_initial_mortgage_market = initial_mortgage_market
    balance_initial_mortgage_affordable = initial_mortgage_affordable

    initial_interest_per_period_market = []
    initial_principal_per_period_market = []
    initial_balance_per_period_market = []
    initial_interest_per_period_affordable = []
    initial_principal_per_period_affordable = []
    initial_balance_per_period_affordable = []

    initial_monthly_total_interest_payment_market = 0
    initial_monthly_total_principal_payment_market = 0
    initial_monthly_total_interest_payment_affordable = 0
    initial_monthly_total_principal_payment_affordable = 0

    for current_month_inspected in range(initial_holding_period_years * 12):
        interest_payment_market = balance_initial_mortgage_market * initial_mortgage_rate_monthly
        interest_payment_affordable = balance_initial_mortgage_affordable * initial_mortgage_rate_monthly
        
        principal_payment_market = initial_avail_mortgage_payment_monthly_market - interest_payment_market
        principal_payment_affordable = initial_avail_mortgage_payment_monthly_affordable - interest_payment_affordable
        
        balance_initial_mortgage_market -= principal_payment_market
        balance_initial_mortgage_affordable -= principal_payment_affordable
        
        initial_monthly_total_interest_payment_market += interest_payment_market
        initial_monthly_total_principal_payment_market += principal_payment_market
        initial_monthly_total_interest_payment_affordable += interest_payment_affordable
        initial_monthly_total_principal_payment_affordable += principal_payment_affordable

        if ((current_month_inspected + 1) % 12 == 0):
            if balance_initial_mortgage_market > 0:
                initial_interest_per_period_market.append(initial_monthly_total_interest_payment_market)
                initial_principal_per_period_market.append(initial_monthly_total_principal_payment_market)
                initial_balance_per_period_market.append(balance_initial_mortgage_market)
            else:
                initial_interest_per_period_market.append(0)
                initial_principal_per_period_market.append(0)
                initial_balance_per_period_market.append(0)

            if balance_initial_mortgage_affordable > 0:
                initial_interest_per_period_affordable.append(initial_monthly_total_interest_payment_affordable)
                initial_principal_per_period_affordable.append(initial_monthly_total_principal_payment_affordable)
                initial_balance_per_period_affordable.append(balance_initial_mortgage_affordable)
            else:
                initial_interest_per_period_affordable.append(0)
                initial_principal_per_period_affordable.append(0)
                initial_balance_per_period_affordable.append(0)

            initial_monthly_total_interest_payment_market = 0
            initial_monthly_total_principal_payment_market = 0
            initial_monthly_total_interest_payment_affordable = 0
            initial_monthly_total_principal_payment_affordable = 0

    initial_balance_per_period_market = np.array(initial_balance_per_period_market)
    initial_balance_per_period_affordable = np.array(initial_balance_per_period_affordable)

    # ------------------------------------------------
    # Array calculations for cumulative costs & Net Proceeds
    # ------------------------------------------------
    annual_property_tax_market = initial_market_rate_value * initial_property_tax_rate_annual_decimal
    if property_tax_based_on_affordable_price:
        annual_property_tax_fixed = initial_vale_fixed_rate_value * initial_property_tax_rate_annual_decimal
        annual_property_tax_ami = initial_ami_rate_value * initial_property_tax_rate_annual_decimal
    else:
        annual_property_tax_fixed = annual_property_tax_market
        annual_property_tax_ami = annual_property_tax_market

    resale_cumulative_property_tax_fixed = np.cumsum(annual_property_tax_fixed)
    resale_cumulative_property_tax_ami = np.cumsum(annual_property_tax_ami)
    resale_cumulative_property_tax_market = np.cumsum(annual_property_tax_market)

    annual_insurance_market = np.ceil((initial_market_rate_value * initial_insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
    
    if insurance_based_on_affordable_price:
        annual_insurance_fixed = np.ceil((initial_vale_fixed_rate_value * initial_insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
        annual_insurance_ami = np.ceil((initial_ami_rate_value * initial_insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
    else:
        annual_insurance_fixed = annual_insurance_market
        annual_insurance_ami = annual_insurance_market

    realistic_pmi_monthly_array = np.zeros(initial_holding_period_years)
    for t in range(initial_holding_period_years):
        if using_FHA_loan:
            if initial_downpayment_pct < 10.0:
                realistic_pmi_monthly_array[t] = applied_pmi_monthly  
            else:
                realistic_pmi_monthly_array[t] = applied_pmi_monthly if t < 11 else 0.0  
        else:
            current_ltv = initial_balance_per_period_affordable[t] / initial_affordable_purchase_price
            if current_ltv > 0.80:
                realistic_pmi_monthly_array[t] = applied_pmi_monthly
            else:
                realistic_pmi_monthly_array[t] = 0.0

    if cost_model == "Idealized (Flat Affordability)":
        resale_annual_insurance_array_fixed = initial_insurance_amount_annual * initial_ami_scalar
        resale_annual_insurance_array_ami = initial_insurance_amount_annual * initial_ami_scalar
        resale_hoa_monthly_array = initial_hoa_monthly * initial_ami_scalar
        resale_ground_lease_monthly_array = initial_ground_lease_monthly * initial_ami_scalar
        resale_pmi_monthly_array = applied_pmi_monthly * initial_ami_scalar
    else:
        resale_annual_insurance_array_fixed = annual_insurance_fixed
        resale_annual_insurance_array_ami = annual_insurance_ami
        resale_hoa_monthly_array = np.full(initial_holding_period_years, initial_hoa_monthly)
        resale_ground_lease_monthly_array = np.full(initial_holding_period_years, initial_ground_lease_monthly)
        resale_pmi_monthly_array = realistic_pmi_monthly_array
        
    resale_cumulative_insurance_fixed = np.cumsum(resale_annual_insurance_array_fixed)
    resale_cumulative_insurance_ami = np.cumsum(resale_annual_insurance_array_ami)
    resale_cumulative_insurance_market = np.cumsum(annual_insurance_market)
    
    resale_cumulative_hoa = np.cumsum(resale_hoa_monthly_array * 12.0)
    resale_cumulative_ground_lease = np.cumsum(resale_ground_lease_monthly_array * 12.0)

    resale_cumulative_mortgage_payments_affordable = np.cumsum(initial_interest_per_period_affordable) + np.cumsum(initial_principal_per_period_affordable)
    resale_cumulative_mortgage_payments_market = np.cumsum(initial_interest_per_period_market) + np.cumsum(initial_principal_per_period_market)

    # Net Proceeds
    buyer_closing_costs_affordable = initial_mortgage_affordable_closing_costs / 2.0
    buyer_closing_costs_market = initial_mortgage_market_closing_costs / 2.0
    
    seller_selling_costs_fixed = initial_vale_fixed_rate_value * (resale_selling_cost_pct / 100.0) / 2.0
    seller_selling_costs_ami = initial_ami_rate_value * (resale_selling_cost_pct / 100.0) / 2.0
    seller_selling_costs_market = initial_market_rate_value * (resale_selling_cost_pct / 100.0) / 2.0

    gross_appreciation_fixed = initial_vale_fixed_rate_value - initial_affordable_purchase_price_paid_by_resident_owner
    gross_appreciation_ami = initial_ami_rate_value - initial_affordable_purchase_price_paid_by_resident_owner

    sunk_costs_fixed = resale_cumulative_property_tax_fixed + resale_cumulative_insurance_fixed + resale_cumulative_hoa + resale_cumulative_ground_lease + np.cumsum(resale_pmi_monthly_array * 12.0) + resale_cumulative_mortgage_payments_affordable
    sunk_costs_ami = resale_cumulative_property_tax_ami + resale_cumulative_insurance_ami + resale_cumulative_hoa + resale_cumulative_ground_lease + np.cumsum(resale_pmi_monthly_array * 12.0) + resale_cumulative_mortgage_payments_affordable
    sunk_costs_market = resale_cumulative_property_tax_market + resale_cumulative_insurance_market + resale_cumulative_hoa + resale_cumulative_ground_lease + np.cumsum(resale_pmi_monthly_array * 12.0) + resale_cumulative_mortgage_payments_market

    if subtract_sunk_costs:
        resale_net_wealth_built_fixed = initial_vale_fixed_rate_value - initial_balance_per_period_affordable - seller_selling_costs_fixed - buyer_closing_costs_affordable - initial_buyer_cash_contribution_downpayment - sunk_costs_fixed
        resale_net_wealth_built_ami = initial_ami_rate_value - initial_balance_per_period_affordable - seller_selling_costs_ami - buyer_closing_costs_affordable - initial_buyer_cash_contribution_downpayment - sunk_costs_ami
        resale_net_wealth_built_market = initial_market_rate_value - initial_balance_per_period_market - seller_selling_costs_market - buyer_closing_costs_market - initial_downpayment_amount_market - sunk_costs_market
    else:
        resale_net_wealth_built_fixed = initial_vale_fixed_rate_value - initial_balance_per_period_affordable - seller_selling_costs_fixed - buyer_closing_costs_affordable - initial_buyer_cash_contribution_downpayment
        resale_net_wealth_built_ami = initial_ami_rate_value - initial_balance_per_period_affordable - seller_selling_costs_ami - buyer_closing_costs_affordable - initial_buyer_cash_contribution_downpayment
        resale_net_wealth_built_market = initial_market_rate_value - initial_balance_per_period_market - seller_selling_costs_market - buyer_closing_costs_market - initial_downpayment_amount_market

    # Inflation adjustment
    if adjust_for_inflation:
        inflation_discount = (1 + (general_inflation_rate / 100.0)) ** initial_years
        resale_net_wealth_built_fixed /= inflation_discount
        resale_net_wealth_built_ami /= inflation_discount
        resale_net_wealth_built_market /= inflation_discount
        initial_vale_fixed_rate_value /= inflation_discount
        initial_ami_rate_value /= inflation_discount
        initial_market_rate_value /= inflation_discount

    # Continuing Affordability metrics
    resale_mortgage_rate_monthly = (resale_mortgage_rate / 100.0) / 12.0
    if resale_mortgage_rate_monthly > 0:
        resale_amort_factor = (resale_mortgage_rate_monthly * math.pow(1 + resale_mortgage_rate_monthly, initial_length_of_mortgage_in_months)) / (math.pow(1 + resale_mortgage_rate_monthly, initial_length_of_mortgage_in_months) - 1)
    else:
        resale_amort_factor = 1.0 / initial_length_of_mortgage_in_months

    # Fixed Continuing Affordability
    resale_downpayment_fixed = initial_vale_fixed_rate_value * initial_downpayment_rate_decimal
    resale_loan_fixed = initial_vale_fixed_rate_value - resale_downpayment_fixed
    resale_monthly_housing_costs_fixed = (resale_loan_fixed * resale_amort_factor) + (annual_property_tax_fixed / 12.0) + (resale_annual_insurance_array_fixed / 12.0) + resale_hoa_monthly_array + resale_ground_lease_monthly_array + resale_pmi_monthly_array
    resale_required_income_fixed = (resale_monthly_housing_costs_fixed / (initial_perc_income_spent_on_housing / 100.0)) * 12.0
    resale_ami_four_person_array = initial_ami_four_person_dollar_amount * initial_ami_scalar
    resale_continuing_affordability_fixed = (resale_required_income_fixed / (resale_ami_four_person_array * initial_household_size_factor)) * 100.0

    # AMI Continuing Affordability
    resale_downpayment_ami = initial_ami_rate_value * initial_downpayment_rate_decimal
    resale_loan_ami = initial_ami_rate_value - resale_downpayment_ami
    resale_monthly_housing_costs_ami = (resale_loan_ami * resale_amort_factor) + (annual_property_tax_ami / 12.0) + (resale_annual_insurance_array_ami / 12.0) + resale_hoa_monthly_array + resale_ground_lease_monthly_array + resale_pmi_monthly_array
    resale_required_income_ami = (resale_monthly_housing_costs_ami / (initial_perc_income_spent_on_housing / 100.0)) * 12.0
    resale_continuing_affordability_ami = (resale_required_income_ami / (resale_ami_four_person_array * initial_household_size_factor)) * 100.0

    resale_clt_equity_fixed = initial_market_rate_value - initial_vale_fixed_rate_value
    resale_clt_equity_ami = initial_market_rate_value - initial_ami_rate_value

    return pd.DataFrame({
        "Year": initial_years,
        "InitialMarketRateValue": initial_market_rate_value,
        "InitialVALEFixedRateValue": initial_vale_fixed_rate_value,
        "InitialAMIRateValue": initial_ami_rate_value,
        "ResaleNetWealthBuiltMarket": resale_net_wealth_built_market,
        "ResaleNetWealthBuiltFixed": resale_net_wealth_built_fixed,
        "ResaleNetWealthBuiltAMI": resale_net_wealth_built_ami,
        "ResaleContinuingAffordabilityPctOfAMIFixed": resale_continuing_affordability_fixed,
        "ResaleContinuingAffordabilityPctOfAMIAMI": resale_continuing_affordability_ami,
        "ResaleCLTEquityAmountFixed": resale_clt_equity_fixed,
        "ResaleCLTEquityAmountAMI": resale_clt_equity_ami,
        "InitialAnnualTargetIncome": initial_target_income_annual,
        "InitialMonthlyTargetIncome": initial_target_income_monthly,
        "InitialAnnualTargetIncomeAvailForHousing": initial_target_income_annual_available_for_housing,
        "InitialMonthlyTargetIncomeAvailForHousing": initial_target_income_monthly_available_for_housing,
        "InitialHOAAnnually": initial_hoa_annually,
        "InitialGroundLeaseAnnually": initial_ground_lease_annually,
        "InitialPMIandFinancingFeesAnnually": initial_pmi_financing_fees_annually,
        "InitialPMIandFinancingFeesMonthly": applied_pmi_monthly,
        "InitialStaticCostsMonthly": initial_static_costs_monthly,
        "InitialMortgageRateAnnually": initial_mortgage_rate_annually,
        "InitialClosingCostsAffordable": initial_mortgage_affordable_closing_costs,
        "InitialMaxLoanAmountAffordable": initial_max_loan_amount_affordable,
        "InitialTotalDownpaymentAmountAffordable": initial_total_downpayment_amount_affordable,
        "InitialBuyerCashContributionDownpayment": initial_buyer_cash_contribution_downpayment,
        "InitialDownpaymentAssistanceAmount": initial_downpayment_assistance_amount,
        "InitialPurchasePriceAffordable": initial_affordable_purchase_price_paid_by_resident_owner,
        "InitialPropertyTaxAmountAnnual": initial_property_taxes_amount_annual,
        "InitialPropertyTaxAmountMonthly": initial_property_taxes_amount_monthly,
        "InitialInsuranceAmountAnnual": initial_insurance_amount_annual,
        "InitialInsuranceAmountMonthly": initial_insurance_amount_monthly,
        "InitialAvailMortgagePaymentMonthlyAffordable": initial_avail_mortgage_payment_monthly_affordable,
        "InitialSubsidyRequired": initial_subsidy_required,
        "InitialAffordabilityGapAmount": initial_affordability_gap_amount,
        "InitialRemainingSubsidyRequired": initial_remaining_subsidy_required,
        "InitialTotalOtherHousingAnnual": initial_total_other_housing_annual,
        "InitialTotalOtherHousingMonthly": initial_total_other_housing_monthly,
        "GrossAppreciationFixed": gross_appreciation_fixed,
        "PrincipalRepaidAffordable": np.cumsum(initial_principal_per_period_affordable),
        "BuyerClosingCostsAffordable": buyer_closing_costs_affordable,
        "SellerClosingCostsFixed": seller_selling_costs_fixed
    })
