import numpy as np
import pandas as pd


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


def get_ami_for_household_size(ami_4person_100pct, household_size, affordability_pct=100):
    """
    Calculate AMI for a given household size based on 4-person 100% AMI.
    
    TENTATIVE: Uses HUD standard adjustment factors.
    
    - ami_4person_100pct: the 100% AMI for a 4-person household (e.g., $93,100)
    - household_size: household size (1-8)
    - affordability_pct: the affordability tier as a percentage (e.g., 80 for 80% AMI)
    
    Returns: affordability bound for the given household size and tier
    """
    factor = HOUSEHOLD_SIZE_FACTORS.get(household_size, 1.0)
    ami_for_size = ami_4person_100pct * factor
    affordability_bound = ami_for_size * (affordability_pct / 100.0)
    return affordability_bound


def compute_projections(
    initial_market_value,
    holding_period_years,
    market_inflation_rate,
    fixed_index_rate,
    affordability_pct_of_ami,
    ami_initial,
    household_size=4,
    mortgage_rate_start=6.0,
    mortgage_rate_resale=6.0,
    downpayment_pct=3.0,
    selling_cost_pct=6.0,
    property_tax_pct=1.2,
    insurance_pct=0.35,
    hoa_monthly=150,
    ground_lease=50,
    other_costs=0.0,
    median_income_inflation=4.0,
    safety_net_floor=True,
    market_share_cap_pct=100.0,
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
    - Safety net floor sets negative proceeds to 0, ensuring homeowner never has negative equity at sale.
    - Market share cap prevents fixed price from rising above market value * cap_pct.
    """

    years = np.arange(0, holding_period_years + 1)
    market_vals = initial_market_value * (1 + market_inflation_rate / 100) ** years
    fixed_vals = initial_market_value * (1 + fixed_index_rate / 100) ** years

    # Apply market share cap only when safety_net_floor is enabled.
    # The safety net here caps the fixed-index resale price so it does not exceed a share of market value (e.g., 80%).
    cap_factor = market_share_cap_pct / 100.0
    if safety_net_floor:
        fixed_capped = np.minimum(fixed_vals, market_vals * cap_factor)
    else:
        fixed_capped = fixed_vals

    # Safety net floor: prevent negative equity for homeowner at resale
    # We'll model downpayment and simple mortgage amortization over the holding period.
    principal = initial_market_value * (1 - downpayment_pct / 100.0)
    annual_rate = mortgage_rate_start / 100.0
    # TENTATIVE: Assume 30-year fixed mortgage amortization
    n_periods = 30
    monthly_rate = annual_rate / 12.0
    months = n_periods * 12
    if monthly_rate > 0:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    else:
        monthly_payment = principal / months

    # Remaining balance after t years
    def remaining_balance(principal, monthly_payment, monthly_rate, years_elapsed):
        k = int(years_elapsed * 12)
        if monthly_rate == 0:
            return max(0.0, principal - monthly_payment * k)
        return principal * (1 + monthly_rate) ** k - monthly_payment * ((1 + monthly_rate) ** k - 1) / monthly_rate

    rem_balances = [remaining_balance(principal, monthly_payment, monthly_rate, y) for y in years]

    # Selling costs, taxes, and fees (TENTATIVE assumptions; review with domain experts)
    selling_costs = market_vals * (selling_cost_pct / 100.0)
    property_taxes = market_vals * (property_tax_pct / 100.0)  # annual property tax per year
    insurance_annual = market_vals * (insurance_pct / 100.0)
    hoa_annual = np.array([hoa_monthly * 12.0] * len(years))
    other_annual = np.array([other_costs + ground_lease] * len(years))

    # Cumulative arrays to track lifetime payments (principal, interest, taxes, insurance, other)
    cumulative_principal_paid = []
    cumulative_interest_paid = []
    cumulative_property_taxes = []
    cumulative_insurance = []
    cumulative_hoa = []
    cumulative_other = []
    cumulative_total_payments = []

    for idx, y in enumerate(years):
        months_elapsed = int(y * 12)
        total_payments = monthly_payment * months_elapsed
        rem_bal = rem_balances[idx]
        principal_paid = max(0.0, principal - rem_bal)
        interest_paid = max(0.0, total_payments - principal_paid)

        cum_tax = float(np.sum(property_taxes[: idx + 1]))
        cum_ins = float(np.sum(insurance_annual[: idx + 1]))
        cum_hoa = float(np.sum(hoa_annual[: idx + 1]))
        cum_other = float(np.sum(other_annual[: idx + 1]))

        cumulative_principal_paid.append(principal_paid)
        cumulative_interest_paid.append(interest_paid)
        cumulative_property_taxes.append(cum_tax)
        cumulative_insurance.append(cum_ins)
        cumulative_hoa.append(cum_hoa)
        cumulative_other.append(cum_other)
        cumulative_total_payments.append(total_payments)

    cumulative_principal_paid = np.array(cumulative_principal_paid)
    cumulative_interest_paid = np.array(cumulative_interest_paid)
    cumulative_property_taxes = np.array(cumulative_property_taxes)
    cumulative_insurance = np.array(cumulative_insurance)
    cumulative_hoa = np.array(cumulative_hoa)
    cumulative_other = np.array(cumulative_other)
    cumulative_total_payments = np.array(cumulative_total_payments)

    # Homeowner proceeds at sale should be sale price minus remaining mortgage payoff and selling/transaction costs.
    proceeds_market = market_vals - rem_balances - selling_costs
    proceeds_fixed = fixed_capped - rem_balances - (fixed_capped * (selling_cost_pct / 100.0))

    # Equity and detailed cashflow metrics
    initial_downpayment = initial_market_value * (downpayment_pct / 100.0)

    # Equity gain = proceeds at sale minus the initial downpayment (pure capital gain)
    equity_gain_market = proceeds_market - initial_downpayment
    equity_gain_fixed = proceeds_fixed - initial_downpayment

    # Net lifetime cashflow change = proceeds minus initial downpayment and cumulative carrying costs (interest + taxes + insurance + HOA + other)
    net_cashflow_change_market = (
        proceeds_market
        - (
            initial_downpayment
            + cumulative_interest_paid
            + cumulative_property_taxes
            + cumulative_insurance
            + cumulative_hoa
            + cumulative_other
        )
    )
    net_cashflow_change_fixed = (
        proceeds_fixed
        - (
            initial_downpayment
            + cumulative_interest_paid
            + cumulative_property_taxes
            + cumulative_insurance
            + cumulative_hoa
            + cumulative_other
        )
    )

    # ----- Translate .txt model key calculations for second-buyer affordability and homeowner proceeds -----
    # Second buyer assumptions
    percent_income_affordable = 0.30  # Percentage of income considered affordable (can be parameterized)
    years_to_months = 12

    # Pre-allocate arrays
    second_monthly_mortgage_market = []
    second_total_monthly_costs_market = []
    max_supportable_mortgage_market = []
    affordable_pct_of_ami_market = []
    additional_subsidy_required_market = []
    homeowner_net_proceeds_ami = []
    homeowner_net_proceeds_fixed = []

    for i, y in enumerate(years):
        # Market path: compute second buyer mortgage and monthly payment at resale
        resale_price_market = market_vals[i]
        resale_price_fixed = fixed_capped[i]

        # Downpayment by second buyer
        second_downpayment_market = resale_price_market * (downpayment_pct / 100.0)
        second_downpayment_fixed = resale_price_fixed * (downpayment_pct / 100.0)

        # Mortgage amounts
        second_mortgage_market = resale_price_market - second_downpayment_market
        second_mortgage_fixed = resale_price_fixed - second_downpayment_fixed

        # Second buyer monthly mortgage rate (use mortgage_rate_resale)
        second_monthly_rate = (mortgage_rate_resale / 100.0) / years_to_months

        def monthly_payment_for(mortgage, monthly_rate, n_months=360):
            if monthly_rate == 0:
                return mortgage / n_months
            return mortgage * (monthly_rate * (1 + monthly_rate) ** n_months) / (((1 + monthly_rate) ** n_months) - 1)

        second_monthly_payment_market = monthly_payment_for(second_mortgage_market, second_monthly_rate)
        second_monthly_payment_fixed = monthly_payment_for(second_mortgage_fixed, second_monthly_rate)

        # Second buyer non-mortgage monthly costs: property tax + insurance + static housing costs, escalated by median income inflation
        tax_monthly_market = resale_price_market * (property_tax_pct / 100.0) / 12.0
        insurance_monthly_market = resale_price_market * (insurance_pct / 100.0) / 12.0
        static_monthly = (ground_lease + hoa_monthly + (other_costs / 12.0)) * ((1 + median_income_inflation) ** y)

        total_monthly_cost_market = second_monthly_payment_market + tax_monthly_market + insurance_monthly_market + static_monthly

        # Maximum supportable monthly mortgage payment based on AMI (for target affordability tier)
        # Likely future median income for affordability target at second sale
        likely_future_median_income = ami_initial * ((1 + median_income_inflation) ** y)
        monthly_income_available = (likely_future_median_income * (affordability_pct_of_ami / 100.0) * percent_income_affordable) / 12.0

        # Maximum supportable mortgage (PV of annuity) given monthly_income_available less taxes/insurance/static
        max_supportable_monthly_mortgage = max(0.0, monthly_income_available - (tax_monthly_market + insurance_monthly_market + static_monthly))
        if max_supportable_monthly_mortgage <= 0:
            max_supportable_mortgage = 0.0
        else:
            # PV formula: max_mortgage = payment * (1 - (1+rate)^-n) / rate
            if second_monthly_rate == 0:
                max_supportable_mortgage = max_supportable_monthly_mortgage * 360
            else:
                max_supportable_mortgage = max_supportable_monthly_mortgage * (1 - (1 + second_monthly_rate) ** (-360)) / second_monthly_rate

        # Affordable price at resale (AMI-based bound)
        ami_for_household_now = (ami_initial * HOUSEHOLD_SIZE_FACTORS.get(household_size, 1.0)) * ((1 + median_income_inflation) ** y)
        estimated_affordable_price = ami_for_household_now * (affordability_pct_of_ami / 100.0)

        # Additional subsidy required = second mortgage - max supportable mortgage
        additional_subsidy = max(0.0, second_mortgage_market - max_supportable_mortgage)

        # Transaction costs
        transaction_cost_ami = estimated_affordable_price * (selling_cost_pct / 100.0)
        transaction_cost_fixed = resale_price_fixed * (selling_cost_pct / 100.0)

        # Homeowner net proceeds per .txt definitions
        homeowner_np_ami = estimated_affordable_price - max_supportable_mortgage - transaction_cost_ami
        homeowner_np_fixed = resale_price_fixed - max_supportable_mortgage - transaction_cost_fixed

        # Percent market share affordability (what percent of AMI buyers could afford)
        if likely_future_median_income > 0:
            affordable_pct = (total_monthly_cost_market * (1 / percent_income_affordable) * 12.0) / likely_future_median_income
        else:
            affordable_pct = np.nan

        # Append
        second_monthly_mortgage_market.append(second_monthly_payment_market)
        second_total_monthly_costs_market.append(total_monthly_cost_market)
        max_supportable_mortgage_market.append(max_supportable_mortgage)
        affordable_pct_of_ami_market.append(affordable_pct)
        additional_subsidy_required_market.append(additional_subsidy)
        homeowner_net_proceeds_ami.append(homeowner_np_ami)
        homeowner_net_proceeds_fixed.append(homeowner_np_fixed)

    # convert lists to arrays
    second_monthly_mortgage_market = np.array(second_monthly_mortgage_market)
    second_total_monthly_costs_market = np.array(second_total_monthly_costs_market)
    max_supportable_mortgage_market = np.array(max_supportable_mortgage_market)
    affordable_pct_of_ami_market = np.array(affordable_pct_of_ami_market)
    additional_subsidy_required_market = np.array(additional_subsidy_required_market)
    homeowner_net_proceeds_ami = np.array(homeowner_net_proceeds_ami)
    homeowner_net_proceeds_fixed = np.array(homeowner_net_proceeds_fixed)

    if safety_net_floor:
        # Apply floor to proceeds at sale so homeowners cannot owe money at sale (prevent negative equity).
        proceeds_market = np.maximum(proceeds_market, 0.0)
        proceeds_fixed = np.maximum(proceeds_fixed, 0.0)

    # Affordability: price bound for next buyer (household-size-adjusted AMI tier)
    # TENTATIVE: Use household_size factor to adjust the affordability bound
    ami_for_household = ami_initial * HOUSEHOLD_SIZE_FACTORS.get(household_size, 1.0)
    ami_for_household_vals = ami_for_household * (1 + market_inflation_rate / 100.0) ** years
    affordability_bound = ami_for_household_vals * (affordability_pct_of_ami / 100.0)

    df = pd.DataFrame(
        {
            "Year": years,
            "MarketValue": market_vals,
            "FixedPriceRaw": fixed_vals,
            "FixedPriceCapped": fixed_capped,
            "RemainingMortgageBalance": rem_balances,
            "SellingCosts": selling_costs,
            "ProceedsAtSaleMarket": proceeds_market,
            "ProceedsAtSaleFixed": proceeds_fixed,
            "EquityGainMarket": equity_gain_market,
            "EquityGainFixed": equity_gain_fixed,
            "NetCashflowChangeMarket": net_cashflow_change_market,
            "NetCashflowChangeFixed": net_cashflow_change_fixed,
            "CumulativePrincipalPaid": cumulative_principal_paid,
            "CumulativeInterestPaid": cumulative_interest_paid,
            "CumulativePropertyTaxes": cumulative_property_taxes,
            "CumulativeInsurance": cumulative_insurance,
            "CumulativeHOA": cumulative_hoa,
            "CumulativeOtherCosts": cumulative_other,
            "TotalPayments": cumulative_total_payments,
            "AMIForHousehold": ami_for_household_vals,
            "AffordabilityBound": affordability_bound,
            # .mdl-derived columns
            "SecondBuyerMonthlyMortgage_Market": second_monthly_mortgage_market,
            "SecondBuyerTotalMonthlyCost_Market": second_total_monthly_costs_market,
            "MaxSupportableMortgage_Market": max_supportable_mortgage_market,
            "AffordablePctOfAMI_Market": affordable_pct_of_ami_market,
            "AdditionalSubsidyRequired_Market": additional_subsidy_required_market,
            "HomeownerNetProceeds_AMI": homeowner_net_proceeds_ami,
            "HomeownerNetProceeds_Fixed": homeowner_net_proceeds_fixed,
        }
    )

    return df
