import numpy as np
import pandas as pd
import math
import streamlit as st


# Throughout this document if a variable has a:
# Prefix of 'iniital' - then it is referring to the time the home is 1st purchased
# Prefix of 'resale' - then it is referring to the time that that 'initial' home is sold to a second buyer
# Contains 'market' - then it is referring to homes with costs associated with the capitalist speculative market
# Contains 'fixed' - then it is referring to a fixed index resale formula (i.e, pinned to a fixed number say 1.5%)
# Contains 'ami" - then it is referring to an AMI based index resale formula (i.e, it rises & falls based on the HUD produced AMI number)
# Contains 'affordable' - then it is referring to any home - either 'fixed' or 'ami' that meet affordability criteria


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
    initial_downpayment_assistance_amount,
    initial_downpayment_assistance_covers_buyer_contribution_check,
    initial_affordability_gap_amount,
    initial_holding_period_years,
    vale_resale_capped,
   
):
    """
    Compute year-by-year projections for market value vs fixed resale formula.

    Notes / assumptions (TENTATIVE - please review and refine):
    - Market value grows at `market_inflation_rate` compounded annually.
    - Fixed price follows `initial_market_value * (1 + fixed_index_rate)^t`.
    - Affordability price bound is calculated from household-size-adjusted AMI:
      For a given initial_household_size and initial_affordability_pct_of_ami, the bound is:
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
    # This creates a series/vector/array of values from year 0 until the end of the initial_holding_period_years
    initial_years = np.arange(0, initial_holding_period_years)
    

    # Establish the baseline income that is available for the buyer
    initial_household_size_factor = HOUSEHOLD_SIZE_FACTORS.get(initial_household_size, 1.0)
    initial_target_income_annual = initial_ami_four_person_dollar_amount * (initial_affordability_pct_of_ami / 100) * initial_household_size_factor
    initial_target_income_annual_available_for_housing = initial_target_income_annual * (initial_perc_income_spent_on_housing / 100)
    initial_target_income_monthly = initial_target_income_annual / 12
    initial_target_income_monthly_available_for_housing = initial_target_income_annual_available_for_housing / 12



    ###############################################################
    # Section A: Figure out Affordable Price (Two-Pass for PMI)
    ###############################################################
    # Calculate Static Costs (EXCLUDING PMI FOR NOW)
    initial_static_costs_monthly_no_pmi = initial_hoa_monthly + initial_ground_lease_monthly 
    initial_hoa_annually = initial_hoa_monthly * 12
    initial_ground_lease_annually = initial_ground_lease_monthly * 12

    # Monthly mortgage amortization factor
    initial_mortgage_rate_annually = initial_mortgage_rate / 100.0
    initial_mortgage_rate_monthly = initial_mortgage_rate_annually / 12.0
    initial_length_of_mortgage_in_months = initial_length_of_mortgage_years * 12

    if initial_mortgage_rate_monthly > 0:
        amortization_factor = (initial_mortgage_rate_monthly * math.pow(1 + initial_mortgage_rate_monthly, initial_length_of_mortgage_in_months)) / (math.pow(1 + initial_mortgage_rate_monthly, initial_length_of_mortgage_in_months) - 1)
    else:
        amortization_factor = 1.0 / initial_length_of_mortgage_in_months
    
    # Convert Rates
    initial_property_tax_rate_annual_decimal = (initial_property_tax_pct_annual / 100.0)
    initial_insurance_rate_annual_decimal = (initial_insurance_pct_annual / 100.0)
    initial_downpayment_rate_decimal = (initial_downpayment_pct / 100.0)

    # Insurance
    INSURANCE_AJUSTMENT_FACTOR = 0.70588
    initial_insurance_amount_annual = math.ceil((initial_market_value * initial_insurance_rate_annual_decimal) * INSURANCE_AJUSTMENT_FACTOR)
    initial_insurance_amount_monthly = initial_insurance_amount_annual / 12.0

    # ==========================================
    # PASS 1: Calculate Price Assuming NO PMI
    # ==========================================
    base_budget = initial_target_income_monthly_available_for_housing - initial_static_costs_monthly_no_pmi - initial_insurance_amount_monthly

    if initial_downpayment_assistance_covers_buyer_contribution_check:
        # DPA covers the % requirement. It does NOT increase total purchasing power.
        base_numerator = base_budget
    else:
        # DPA is EXTRA equity on top of the buyer's %. It INCREASES total purchasing power.
        base_numerator = base_budget + (initial_downpayment_assistance_amount * amortization_factor)

    if property_tax_based_on_affordable_price:
        denominator = ((1.0 - initial_downpayment_rate_decimal) * amortization_factor) + (initial_property_tax_rate_annual_decimal / 12.0)
        numerator_pass_1 = base_numerator
    else:
        initial_property_taxes_amount_annual = math.ceil(initial_market_value * initial_property_tax_rate_annual_decimal)
        initial_property_taxes_amount_monthly = math.ceil(initial_property_taxes_amount_annual / 12.0)
        denominator = (1.0 - initial_downpayment_rate_decimal) * amortization_factor
        numerator_pass_1 = base_numerator - initial_property_taxes_amount_monthly

    P_pass_1 = numerator_pass_1 / denominator if (denominator > 0 and numerator_pass_1 > 0) else 0.0

    # ==========================================
    # EQUITY CHECK & PASS 2 (Apply PMI if needed)
    # ==========================================
    
    def calculate_downpayments(price):
        """Helper to cleanly apply the checkbox logic to any calculated price."""
        required_downpayment = math.ceil(price * initial_downpayment_rate_decimal)
        
        if initial_downpayment_assistance_covers_buyer_contribution_check:
            # Buyer pays the requirement MINUS the DPA, but never less than $500
            buyer_cash = max(500.0, required_downpayment - initial_downpayment_assistance_amount)
        else:
            # Buyer pays the full requirement, DPA is extra
            buyer_cash = max(500.0, required_downpayment)
            
        total_equity = buyer_cash + initial_downpayment_assistance_amount
        return buyer_cash, total_equity

    # 1. Calculate Pass 1 cash down & equity
    buyer_cash_pass_1, total_equity_pass_1 = calculate_downpayments(P_pass_1)
    
    # 2. Check total equity percentage
    initial_buyer_equity_pct = total_equity_pass_1 / P_pass_1 if P_pass_1 > 0 else 0.0

    # 3. Apply PMI logic
    if initial_buyer_equity_pct >= 0.20 and not using_FHA_loan:
        # Avoids PMI! Keep Pass 1 results.
        initial_affordable_purchase_price = P_pass_1
        applied_pmi_monthly = 0.0
        
        initial_buyer_cash_contribution_downpayment = buyer_cash_pass_1
        initial_total_downpayment_amount_affordable = total_equity_pass_1
        
    else:
        # Hit with PMI. Subtract PMI from numerator and recalculate.
        applied_pmi_monthly = initial_pmi_financing_fees_monthly
        numerator_pass_2 = numerator_pass_1 - applied_pmi_monthly
        P_pass_2 = numerator_pass_2 / denominator if (denominator > 0 and numerator_pass_2 > 0) else 0.0
        
        initial_affordable_purchase_price = P_pass_2
        
        # Recalculate downpayments with the new, slightly lower purchase price
        buyer_cash_pass_2, total_equity_pass_2 = calculate_downpayments(P_pass_2)
        
        initial_buyer_cash_contribution_downpayment = buyer_cash_pass_2
        initial_total_downpayment_amount_affordable = total_equity_pass_2
        
        # Update equity percentage for records
        initial_buyer_equity_pct = total_equity_pass_2 / P_pass_2 if P_pass_2 > 0 else 0.0

    # ==========================================
    # FINALIZE VARIABLES
    # ==========================================
    initial_pmi_financing_fees_annually = applied_pmi_monthly * 12
    initial_static_costs_monthly = initial_static_costs_monthly_no_pmi + applied_pmi_monthly
    
    #initial_downpayment_amount_affordable = initial_buyer_cash_contribution_downpayment
    #initial_total_downpayment_amount_affordable = initial_total_buyer_equity_dollars
    
    # Loan is whatever is left over after the Buyer Cash and DPA Grant are applied
    initial_max_loan_amount_affordable = initial_affordable_purchase_price - initial_total_downpayment_amount_affordable

    if property_tax_based_on_affordable_price:
        initial_property_taxes_amount_annual = math.ceil(initial_affordable_purchase_price * initial_property_tax_rate_annual_decimal)
        initial_property_taxes_amount_monthly = math.ceil(initial_property_taxes_amount_annual / 12.0)

    initial_subsidy_required = max(0.0, initial_market_value - initial_affordable_purchase_price)

    # 1. Calculate the other housing costs first
    initial_total_other_housing_annual = math.ceil((initial_static_costs_monthly * 12) + initial_property_taxes_amount_annual + initial_insurance_amount_annual)
    initial_total_other_housing_monthly = initial_total_other_housing_annual / 12

    # 2. Redefine "Available for mortgage payment" conceptually (Target Income Budget - Other Costs)
    initial_avail_mortgage_payment_monthly_affordable = initial_target_income_monthly_available_for_housing - initial_total_other_housing_monthly

    # END Section A: Figure out Affordable Price ##############################################################



    ###############################################################
    # Section B: Resale
    ###############################################################

    ###################################################
    # B.I. Calculate both Market and Afforable Mortgage
    ###################################################
    # 1. Resale Valuations (Initial Mortgage value at year 0, i.e. initial_vale_fixed_rate_value[0])
    initial_market_rate_value = initial_market_value * ((1 + initial_market_home_price_inflation_rate / 100.0) ** initial_years)
    initial_vale_fixed_rate_value = initial_affordable_purchase_price * ((1 + initial_vale_resale_fixed_index_pct / 100.0) ** initial_years)
    
    # AMI-Indexed Resale Value
    initial_ami_scalar = (1 + initial_area_median_income_inflation / 100.0) ** initial_years
    initial_ami_rate_value = initial_affordable_purchase_price * initial_ami_scalar

    # Optional Cap Logic: resale price cannot exceed 80% of market value
    if vale_resale_capped:
        for t in initial_years:
            initial_vale_fixed_rate_value[t] = min(initial_vale_fixed_rate_value[t], (initial_market_rate_value[t] * CAP_PERCENTAGE_FOR_MAINTAINING_AFFORDABILITY_DURING_MARKET_DOWNTURN))
            initial_ami_rate_value[t] = min(initial_ami_rate_value[t], (initial_market_rate_value[t] * CAP_PERCENTAGE_FOR_MAINTAINING_AFFORDABILITY_DURING_MARKET_DOWNTURN))

    
    initial_downpayment_amount_market = math.ceil(initial_market_rate_value[0] * initial_downpayment_rate_decimal)
    initial_mortgage_market_closing_costs = initial_market_rate_value[0] * (initial_closing_cost_pct / 100.0)
    initial_mortgage_market = initial_market_rate_value[0] - initial_downpayment_amount_market
    
    initial_mortgage_affordable_closing_costs = initial_affordable_purchase_price * (initial_closing_cost_pct / 100.0)
    initial_mortgage_affordable = initial_max_loan_amount_affordable #Already has downpayment subtracted above initial_total_downpayment_amount_affordable
    initial_affordable_purchase_price_paid_by_resident_owner = initial_mortgage_affordable + initial_total_downpayment_amount_affordable
    
    # End Calculate both Market and Afforable Mortgage ###########

    
    ##################################################
    # B.II. Now calculate Principal & Interest payments
    ##################################################
    # Need to know the Monthly Market payment avaiable
    initial_avail_mortgage_payment_monthly_market = initial_mortgage_market * (initial_mortgage_rate_monthly * (1 + initial_mortgage_rate_monthly)**initial_length_of_mortgage_in_months) / ((1 + initial_mortgage_rate_monthly)**initial_length_of_mortgage_in_months - 1)
    
    
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

    for current_month_inspected in range((initial_holding_period_years) * 12):
        # 1. Interest is always: Current Balance * Monthly Rate
        interest_payment_market = balance_initial_mortgage_market * initial_mortgage_rate_monthly
        interest_payment_affordable = balance_initial_mortgage_affordable * initial_mortgage_rate_monthly
        
        # 2. Rest of the fixed payment goes to principal
        principal_payment_market = initial_avail_mortgage_payment_monthly_market - interest_payment_market
        principal_payment_affordable = initial_avail_mortgage_payment_monthly_affordable - interest_payment_affordable
        
        # 3. Reduce the balance for the next month
        balance_initial_mortgage_market -= principal_payment_market
        balance_initial_mortgage_affordable -= principal_payment_affordable
        
        # Store values

        if ((current_month_inspected + 1) % 12 == 0):
            initial_monthly_total_interest_payment_market = initial_monthly_total_interest_payment_market + interest_payment_market
            initial_monthly_total_principal_payment_market = initial_monthly_total_principal_payment_market + principal_payment_market
            initial_monthly_total_interest_payment_affordable = initial_monthly_total_interest_payment_affordable + interest_payment_affordable
            initial_monthly_total_principal_payment_affordable = initial_monthly_total_principal_payment_affordable + principal_payment_affordable

            if (balance_initial_mortgage_market > 0):
                initial_interest_per_period_market.append(initial_monthly_total_interest_payment_market)
                initial_principal_per_period_market.append(initial_monthly_total_principal_payment_market)
                initial_balance_per_period_market.append(balance_initial_mortgage_market)
            else:
                initial_interest_per_period_market.append(0)
                initial_principal_per_period_market.append(0)
                initial_balance_per_period_market.append(0)

            if (balance_initial_mortgage_affordable > 0):
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
        else:
            initial_monthly_total_interest_payment_market = initial_monthly_total_interest_payment_market + interest_payment_market
            initial_monthly_total_principal_payment_market = initial_monthly_total_principal_payment_market + principal_payment_market
            initial_monthly_total_interest_payment_affordable = initial_monthly_total_interest_payment_affordable + interest_payment_affordable
            initial_monthly_total_principal_payment_affordable = initial_monthly_total_principal_payment_affordable + principal_payment_affordable

    # End calculate Principal & Interest payments ########################


    ##################################################
    # B.III. Buyer's Equity & Net Proceeds; CLT's Equity & Net Proceeds; Continuing Affordability
    # Considerations: Buyer's Equity & Net Proceeds: Establish Initial Buyer's equity percentage - Homeowner's Ownership Interest as well as their 'walk-away cash amount' 
    # This is the projected earnings that a Home Owner could roughly expect to earn as wealth as a result of selling their home. This considers how much
    # they sell the house for - and subtracts out the 1) Cumulative Costs of Ownership (Mortgage Payments & Interest, Property Taxes, Home Insurance); 
    # 2) Transaction & Holding Costs (Selling Costs, Closing Costs, Maintenance & Capital Improvements); and any remaing 3) Liabilities (Remaining Mortgage Payoff, HELOC or Secondary Loans)
    # Could also be useful to track the total appreciation year-on-year over time
    # Some Relevant Variables:
    # initial_subsidy_required = max(0.0, initial_market_value - initial_affordable_purchase_price)
    # initial_affordable_purchase_price_paid_by_resident_owner = initial_mortgage_affordable + initial_total_downpayment_amount_affordable
    # initial_buyer_equity_pct
    
    # CLT's Equity & Net Proceeds: This involves the amount that the community land trust (CLT) has put into this project to ensure its affordability - and how that portion of the stake has also evolved over time
    # Some Relevant Variables:
    # initial_subsidy_required # perhaps the inverse of initial_buyer_equity_pct
    # initial_affordability_gap_amount

    # Continuing Affordability: Determine the new affordability AMI percentage for the second buyer
    # Considerations: At resale time, considering the second buyer's downpayment, second buyer's mortgage, monthly payment, housing costs (basically all of the same things as the initial buyer)
    # figure out the AMI index percentage to which this house is now affordable. Ideally, if things are done right - this amount should be either equal to or LOWER than initial_affordability_pct_of_ami
    # Also useful to track the gain or loss in AMI affordability to be able to plot year-on-year over time
    # Some Relevant Variables:
    # initial_affordability_pct_of_ami; initial_market_home_price_inflation_rate; initial_area_median_income_inflation
    # initial_perc_income_spent_on_housing; resale_mortgage_rate; resale_selling_cost_pct; initial_downpayment_pct (use as resale downpayment_pct also)
    ##################################################



    # End Establish Initial Buyer's equity percentage ####################


    # ==========================================
    # CONSTRUCT RETURN DATAFRAME
    # ==========================================
    financials_df = pd.DataFrame(
        {
            "Year": initial_years + 1,
            "InitialMarketRateValue": np.round(initial_market_rate_value, 2),
            "InitialVALEFixedRateValue": np.round(initial_vale_fixed_rate_value, 2),
            "InitialAMIRateValue": np.round(initial_ami_rate_value, 2),
            "InitialAnnualTargetIncome": np.round(initial_target_income_annual, 2),
            "InitialAnnualTargetIncomeAvailForHousing": np.round(initial_target_income_annual_available_for_housing, 2),
            "InitialMonthlyTargetIncome": np.round(initial_target_income_monthly, 2),
            "InitialMonthlyTargetIncomeAvailForHousing": np.round(initial_target_income_monthly_available_for_housing, 2),
            "InitialHOAMonthly": np.round(initial_hoa_monthly, 2),
            "InitialHOAAnnually": np.round(initial_hoa_annually, 2),
            "InitialGroundLeaseMonthly": np.round(initial_ground_lease_monthly, 2),
            "InitialGroundLeaseAnnually": np.round(initial_ground_lease_annually, 2),
            "InitialPMIandFinancingFeesMonthly": np.round(applied_pmi_monthly, 2),
            "InitialPMIandFinancingFeesAnnually": np.round(initial_pmi_financing_fees_annually, 2), 
            "InitialStaticCostsMonthly": np.round(initial_static_costs_monthly, 2),
            "InitialMaxLoanAmountAffordable": np.round(initial_max_loan_amount_affordable, 2),
            "InitialTotalDownpaymentAmountAffordable": np.round(initial_total_downpayment_amount_affordable, 2),
            "InitialBuyerCashContributionDownpayment": np.round(initial_buyer_cash_contribution_downpayment,2),
            "InitialDownpaymentAssistanceAmount": np.round(initial_downpayment_assistance_amount, 2),
            "InitialPurchasePriceAffordable": np.round(initial_affordable_purchase_price_paid_by_resident_owner, 2),
            "InitialDownpaymentAmountMarket": np.round(initial_downpayment_amount_market,2),
            "InitialClosingCostsAffordable": np.round(initial_mortgage_affordable_closing_costs, 2),
            "InitialClosingCostsMarket": np.round(initial_mortgage_market_closing_costs, 2),
            "InitialPropertyTaxAmountAnnual": np.round(initial_property_taxes_amount_annual, 2),
            "InitialPropertyTaxAmountMonthly": np.round(initial_property_taxes_amount_monthly, 2),
            "InitialInsuranceAmountAnnual": np.round(initial_insurance_amount_annual, 2),
            "InitialInsuranceAmountMonthly": np.round(initial_insurance_amount_monthly, 2),
            "InitialAvailMortgagePaymentMonthlyAffordable": np.round(initial_avail_mortgage_payment_monthly_affordable, 2),
            "InitialAvailMortgagePaymentMonthlyMarket": np.round(initial_avail_mortgage_payment_monthly_market, 2),
            "InitialSubsidyRequired": np.round(initial_subsidy_required, 2),
            "InitialTotalOtherHousingAnnual": np.round(initial_total_other_housing_annual, 2),
            "InitialTotalOtherHousingMonthly": np.round(initial_total_other_housing_monthly, 2),
            "InitialMortgageMarket": np.round(initial_mortgage_market, 2),
            "InitialMortgageAffordable": np.round(initial_mortgage_affordable, 2),
            "AmortizationFactor": amortization_factor,
            "InitialMortgageRateAnnually": initial_mortgage_rate_annually,
            "InitialMortgageRateMonthly": initial_mortgage_rate_monthly,
            "InitialInterestYearlyMarket": np.round(initial_interest_per_period_market, 2),
            "InitialPrincipalYearlyMarket": np.round(initial_principal_per_period_market, 2),
            "InitialBalanceMarket": np.round(initial_balance_per_period_market, 2),
            "InitialInterstYearlyAffordable": np.round(initial_interest_per_period_affordable, 2),
            "InitialPrincipalYearlyAffordable": np.round(initial_principal_per_period_affordable, 2),
            "InitialBalanceAffordable": np.round(initial_balance_per_period_affordable, 2),
            # Net Proceeds
            #"ProceedsAtSaleMarket": np.round(proceeds_market, 2),
            #"ProceedsAtSaleFixed": np.round(proceeds_fixed, 2),
            #"ProceedsAtSaleAMI": np.round(proceeds_ami, 2), 
            # Individual Equity/Wealth built
            #"EquityGainMarket": np.round(equity_gain_market, 2),
            #"EquityGainFixed": np.round(equity_gain_fixed, 2),
            #"EquityGainAMI": np.round(equity_gain_ami, 2), 
            # Full lifecycle cashflow
            #"NetCashflowChangeMarket": np.round(net_cashflow_change_market, 2),
            #"NetCashflowChangeFixed": np.round(net_cashflow_change_fixed, 2),
            #"NetCashflowChangeAMI": np.round(net_cashflow_change_ami, 2), 
            # Amortization details
            #"RemainingMortgageBalance": np.round(remaining_mortgage_balance, 2),
            #"CumulativePrincipalPaid": np.round(cumulative_principal_paid, 2),
            #"CumulativeInterestPaid": np.round(cumulative_interest_paid, 2),
            # Cumulative expenses
            #"CumulativePropertyTaxes": np.round(cumulative_property_taxes, 2),
            #"CumulativeInsurance": np.round(cumulative_insurance, 2),
            #"CumulativeHOA": np.round(cumulative_hoa, 2),
            #"CumulativeOtherCosts": np.round(cumulative_other, 2),
            #"TotalPayments": np.round(cumulative_total_payments, 2),
            #"AffordabilityBound": np.round(affordability_bound, 2)
        }
    )

    return financials_df



