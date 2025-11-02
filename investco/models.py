from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from polymorphic.models import PolymorphicModel


class TimeStampMixin(models.Model):
    """Abstract base class to provide timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Portfolio(TimeStampMixin):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def total_value(self):
        return sum(investment.current_value for investment in self.investments.all())


class Investment(PolymorphicModel, TimeStampMixin):
    """Polymorphic base class for all investment types"""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='investments')
    name = models.CharField(max_length=200)
    symbol = models.CharField(max_length=20, blank=True)
    # current_price kept for backwards compatibility and simple value tracking
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.symbol or self.name} ({self.get_investment_type()})"

    def get_investment_type(self):
        """Return the specific investment type"""
        return self.__class__.__name__

    @property
    def total_cost(self):
        """Override in subclasses"""
        return Decimal('0')

    @property
    def current_value(self):
        """Override in subclasses"""
        return Decimal('0')

    @property
    def gain_loss(self):
        return self.current_value - self.total_cost

    @property
    def gain_loss_percentage(self):
        if self.total_cost == 0:
            return 0
        return (self.gain_loss / self.total_cost) * 100

    def get_historical_values(self, days=30):
        """Get historical values for the last N days"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        return self.historical_values.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')

    def get_performance_metrics(self, days=30):
        """Calculate performance metrics over specified period"""
        values = self.get_historical_values(days)
        if values.count() < 2:
            return None

        first_value = values.first().price
        last_value = values.last().price

        # Calculate total return for the period
        total_return = ((last_value - first_value) / first_value)

        # Annualize the return
        annualized_return = self._annualize_return(total_return, days)

        return {
            'period_return': total_return * 100,  # Total period return
            'annualized_return': annualized_return,  # Annualized return
            'volatility': self._calculate_volatility(values),
            'avg_price': values.aggregate(models.Avg('price'))['price__avg'],
            'high': values.aggregate(models.Max('price'))['price__max'],
            'low': values.aggregate(models.Min('price'))['price__min'],
        }

    def _annualize_return(self, total_return, days):
        """Convert total return to annualized return

        Args:
            total_return: Total return as a decimal (e.g., 0.15 for 15%)
            days: Number of days in the period

        Returns:
            Annualized return as a percentage
        """
        from decimal import Decimal

        if days == 0:
            return 0

        # Convert to float for calculation
        total_return_float = float(total_return)

        # For periods less than a year, just show the period return
        # Annualizing very short periods can be misleading
        if days <= 30:
            return total_return_float * 100

        # Annualize: ((1 + r) ^ (365/days) - 1) * 100
        years = days / 365.0
        annualized = (((1 + total_return_float) ** (1 / years)) - 1) * 100
        return annualized

    def _calculate_volatility(self, values):
        """Calculate price volatility (standard deviation of returns)"""
        prices = [float(v.price) for v in values]
        if len(prices) < 2:
            return 0

        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        if not returns:
            return 0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        return variance ** 0.5 * 100


class ShareBasedInvestment(Investment):
    """Abstract base class for investments tracked by shares/units"""
    shares = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=0,
        help_text="Number of shares/units/coins"
    )
    average_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Average cost per share/unit"
    )

    class Meta:
        abstract = True

    @property
    def total_cost(self):
        return self.shares * self.average_cost

    @property
    def current_value(self):
        return self.shares * self.current_price


class Stock(ShareBasedInvestment):
    """Individual stock holdings"""
    ticker_symbol = models.CharField(max_length=10)
    company_name = models.CharField(max_length=200)
    sector = models.CharField(max_length=100, blank=True)
    market_cap = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    pe_ratio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dividend_yield = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    exchange = models.CharField(max_length=50, blank=True)

    def save(self, *args, **kwargs):
        if not self.symbol:
            self.symbol = self.ticker_symbol
        if not self.name:
            self.name = self.company_name
        super().save(*args, **kwargs)


class Bond(ShareBasedInvestment):
    """Bond holdings"""
    BOND_TYPES = [
        ('GOVERNMENT', 'Government Bond'),
        ('CORPORATE', 'Corporate Bond'),
        ('MUNICIPAL', 'Municipal Bond'),
        ('TREASURY', 'Treasury Bond'),
    ]

    bond_type = models.CharField(max_length=20, choices=BOND_TYPES)
    face_value = models.DecimalField(max_digits=12, decimal_places=2)
    coupon_rate = models.DecimalField(max_digits=5, decimal_places=4)
    maturity_date = models.DateField()
    issuer = models.CharField(max_length=200)
    credit_rating = models.CharField(max_length=10, blank=True)
    yield_to_maturity = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)

    @property
    def years_to_maturity(self):
        today = timezone.now().date()
        return (self.maturity_date - today).days / 365.25

    @property
    def annual_coupon_payment(self):
        return self.face_value * self.coupon_rate


class ETF(ShareBasedInvestment):
    """Exchange Traded Fund holdings"""
    fund_name = models.CharField(max_length=200)
    expense_ratio = models.DecimalField(max_digits=5, decimal_places=4)
    nav = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    assets_under_management = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    inception_date = models.DateField(null=True, blank=True)
    benchmark_index = models.CharField(max_length=200, blank=True)
    dividend_frequency = models.CharField(max_length=20, blank=True)

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.fund_name
        super().save(*args, **kwargs)


class MutualFund(ShareBasedInvestment):
    """Mutual Fund holdings"""
    FUND_TYPES = [
        ('EQUITY', 'Equity Fund'),
        ('BOND', 'Bond Fund'),
        ('BALANCED', 'Balanced Fund'),
        ('INDEX', 'Index Fund'),
        ('TARGET_DATE', 'Target Date Fund'),
        ('MONEY_MARKET', 'Money Market Fund'),
    ]

    fund_type = models.CharField(max_length=20, choices=FUND_TYPES)
    fund_name = models.CharField(max_length=200)
    expense_ratio = models.DecimalField(max_digits=5, decimal_places=4)
    nav = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    minimum_investment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fund_manager = models.CharField(max_length=200, blank=True)
    inception_date = models.DateField(null=True, blank=True)
    load_fee = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.fund_name
        super().save(*args, **kwargs)


class Retirement401k(Investment):
    """401(k) retirement account holdings"""
    CONTRIBUTION_TYPES = [
        ('TRADITIONAL', 'Traditional 401(k)'),
        ('ROTH', 'Roth 401(k)'),
        ('SAFE_HARBOR', 'Safe Harbor 401(k)'),
    ]

    contribution_type = models.CharField(max_length=20, choices=CONTRIBUTION_TYPES)
    employer_name = models.CharField(max_length=200)
    plan_name = models.CharField(max_length=200)
    employee_contribution_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    employer_match_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    vesting_schedule = models.CharField(max_length=200, blank=True)
    loan_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_contribution_limit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Value fields (401k typically tracked as total value, not shares)
    total_contributions = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total cost basis")
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Current total value")

    @property
    def employer_match_value(self):
        """Calculate employer match based on contribution rate"""
        if self.employer_match_rate and self.current_balance:
            return self.current_balance * self.employer_match_rate
        return 0

    @property
    def total_cost(self):
        return self.total_contributions

    @property
    def current_value(self):
        return self.current_balance


class Annuity(Investment):
    """Annuity holdings"""
    ANNUITY_TYPES = [
        ('FIXED', 'Fixed Annuity'),
        ('VARIABLE', 'Variable Annuity'),
        ('IMMEDIATE', 'Immediate Annuity'),
        ('DEFERRED', 'Deferred Annuity'),
        ('INDEXED', 'Indexed Annuity'),
    ]

    annuity_type = models.CharField(max_length=20, choices=ANNUITY_TYPES)
    insurance_company = models.CharField(max_length=200)
    policy_number = models.CharField(max_length=100)
    issue_date = models.DateField(help_text="Date the annuity contract was issued")
    guaranteed_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    payout_start_date = models.DateField(null=True, blank=True)
    monthly_payout = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    surrender_charge_period = models.IntegerField(null=True, blank=True)
    death_benefit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rider_fees = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    @property
    def is_in_payout_phase(self):
        """Check if annuity is currently paying out"""
        if self.payout_start_date:
            return timezone.now().date() >= self.payout_start_date
        return False

    @property
    def annual_payout(self):
        """Calculate annual payout if in payout phase"""
        if self.monthly_payout and self.is_in_payout_phase:
            return self.monthly_payout * 12
        return 0

    @property
    def total_cost(self):
        """Calculate total premiums paid from PREMIUM transactions"""
        from decimal import Decimal
        premium_transactions = self.transactions.filter(transaction_type='PREMIUM')
        return sum(t.total_amount for t in premium_transactions) or Decimal('0')

    @property
    def current_value(self):
        """Get current value from the most recent statement's ending value

        This is the authoritative value from the insurance company. If no statements
        exist, falls back to calculating from transactions.
        """
        from decimal import Decimal
        from django.db.models import Sum

        # Use the most recent statement's ending value as the authoritative current value
        latest_statement = self.statements.order_by('-statement_date').first()
        if latest_statement and hasattr(latest_statement, 'annuitystatement'):
            return latest_statement.annuitystatement.ending_value

        # Fallback: calculate from transactions if no statements exist
        transactions = self.transactions.all()

        premiums = transactions.filter(transaction_type='PREMIUM').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        withdrawals = transactions.filter(transaction_type='WITHDRAWAL').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        tax_withholdings = transactions.filter(transaction_type='TAX_WITHHOLDING').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        net_changes = transactions.filter(transaction_type='NET_CHANGE').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')

        return premiums - withdrawals - tax_withholdings + net_changes

    def get_performance_breakdown(self, as_of_date=None):
        """Get detailed breakdown of annuity components for performance tracking

        This allows tracking the constituent parts separately to judge underlying
        performance over time.
        """
        from decimal import Decimal
        from django.db.models import Sum

        transactions = self.transactions.all()
        if as_of_date:
            transactions = transactions.filter(date__lte=as_of_date)

        premiums = transactions.filter(transaction_type='PREMIUM').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        withdrawals = transactions.filter(transaction_type='WITHDRAWAL').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        tax_withholdings = transactions.filter(transaction_type='TAX_WITHHOLDING').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        net_changes = transactions.filter(transaction_type='NET_CHANGE').aggregate(
            total=Sum('amount'))['total'] or Decimal('0')

        # Get the initial balance from the earliest statement's beginning_value
        initial_balance = Decimal('0')
        statements = self.statements.all()
        if as_of_date:
            statements = statements.filter(statement_date__lte=as_of_date)
        earliest_statement = statements.order_by('statement_date').first()
        if earliest_statement and hasattr(earliest_statement, 'annuitystatement'):
            initial_balance = earliest_statement.annuitystatement.beginning_value or Decimal('0')

        current_val = initial_balance + premiums - withdrawals - tax_withholdings + net_changes

        return {
            'initial_balance': initial_balance,
            'total_premiums': premiums,
            'withdrawals': withdrawals,
            'tax_withholdings': tax_withholdings,
            'net_investment_change': net_changes,
            'current_value': current_val,
            'investment_gain_loss': net_changes,  # Net change IS the gain/loss
            'total_out_of_pocket': premiums,      # What you paid in
        }

    def get_statement_gaps(self):
        """Identify all gaps in statement chaining

        Returns a list of dictionaries containing information about each gap.
        """
        from decimal import Decimal

        gaps = []
        statements = list(self.statements.order_by('statement_date'))

        for i in range(1, len(statements)):
            curr_stmt = statements[i]
            prev_stmt = statements[i-1]

            if hasattr(curr_stmt, 'annuitystatement') and hasattr(prev_stmt, 'annuitystatement'):
                curr = curr_stmt.annuitystatement
                prev = prev_stmt.annuitystatement

                gap = curr.beginning_value - prev.ending_value
                if abs(gap) >= Decimal('0.01'):  # More than 1 cent difference
                    gaps.append({
                        'statement_date': curr.statement_date,
                        'previous_date': prev.statement_date,
                        'gap_amount': gap,
                        'previous_ending': prev.ending_value,
                        'current_beginning': curr.beginning_value,
                    })

        return gaps

    def get_historical_values(self, days=30):
        """Annuities don't use InvestmentValue - return empty queryset

        This override prevents errors when views try to query historical_values
        for annuities. Use get_performance_breakdown() instead.
        """
        return InvestmentValue.objects.none()

    def get_performance_metrics(self, days=30):
        """Calculate annuity-specific performance metrics from transactions

        Unlike share-based investments, annuities calculate performance from
        transaction history rather than daily market prices.
        """
        from datetime import timedelta

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get values at start and end of period
        start_breakdown = self.get_performance_breakdown(as_of_date=start_date)
        end_breakdown = self.get_performance_breakdown(as_of_date=end_date)

        start_value = start_breakdown['current_value']
        end_value = end_breakdown['current_value']

        # Calculate period-specific values first (needed even if start_value is 0)
        period_premiums = float(end_breakdown['total_premiums'] - start_breakdown['total_premiums'])
        period_withdrawals = float(end_breakdown['withdrawals'] - start_breakdown['withdrawals'])
        period_net_investment_change = float(end_breakdown['net_investment_change'] - start_breakdown['net_investment_change'])

        # Calculate total return for the period
        if start_value == 0 and period_premiums > 0:
            # Special case: starting from zero (inception)
            # Calculate return based on premiums contributed as the "cost basis"
            # This shows return on contributions rather than growth from a starting balance
            from decimal import Decimal
            total_return = ((end_value - Decimal(str(period_premiums))) / Decimal(str(period_premiums)))
            period_return = float(total_return * 100)
        elif start_value == 0:
            return None  # No data at all
        else:
            total_return = ((end_value - start_value) / start_value)
            period_return = float(total_return * 100)

        # Annualize the return (reuse parent class method)
        annualized_return = Investment._annualize_return(self, total_return, days)

        return {
            'period_return': period_return,  # Total period return
            'annualized_return': annualized_return,  # Annualized return
            'start_value': float(start_value),  # Value at start of period
            'end_value': float(end_value),  # Value at end of period
            'period_gain': float(end_value - start_value),  # Dollar gain/loss in period
            'period_premiums': period_premiums,  # Premiums paid during period
            'period_withdrawals': period_withdrawals,  # Withdrawals taken during period
            'period_net_investment_change': period_net_investment_change,  # Investment gain/loss during period
        }

    class Meta:
        verbose_name_plural = "Annuities"


class GuaranteedWithdrawalBalance(TimeStampMixin):
    """Track guaranteed withdrawal balance for annuities over time"""
    annuity = models.ForeignKey(
        'Annuity',
        on_delete=models.CASCADE,
        related_name='gwb_history'
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Guaranteed withdrawal balance at this point in time"
    )
    effective_date = models.DateField(help_text="Date this balance became effective")
    notes = models.TextField(blank=True, help_text="Reason for change (e.g., premium payment, step-up, withdrawal)")

    class Meta:
        ordering = ['-effective_date']
        verbose_name = "Guaranteed Withdrawal Balance"
        verbose_name_plural = "Guaranteed Withdrawal Balances"

    def __str__(self):
        return f"{self.annuity.name} - ${self.balance} on {self.effective_date}"


class RealEstate(Investment):
    """Real estate holdings"""
    PROPERTY_TYPES = [
        ('RESIDENTIAL', 'Residential Property'),
        ('COMMERCIAL', 'Commercial Property'),
        ('INDUSTRIAL', 'Industrial Property'),
        ('LAND', 'Raw Land'),
        ('REIT', 'Real Estate Investment Trust'),
        ('RENTAL', 'Rental Property'),
    ]
    
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    address = models.TextField(blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    appraised_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    monthly_rental_income = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    property_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mortgage_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    square_footage = models.IntegerField(null=True, blank=True)

    @property
    def net_monthly_income(self):
        """Calculate net monthly income after expenses"""
        return self.monthly_rental_income - self.monthly_expenses

    @property
    def annual_net_income(self):
        """Calculate annual net income"""
        return self.net_monthly_income * 12

    @property
    def equity(self):
        """Calculate property equity"""
        if self.appraised_value or self.current_price:
            property_value = self.appraised_value or self.current_price
            return property_value - self.mortgage_balance
        return 0

    @property
    def cap_rate(self):
        """Calculate capitalization rate"""
        if self.appraised_value and self.annual_net_income > 0:
            return (self.annual_net_income / self.appraised_value) * 100
        return 0

    @property
    def total_cost(self):
        """Total cost is the purchase price"""
        return self.purchase_price or Decimal('0')

    @property
    def current_value(self):
        """Current value is the appraised value"""
        return self.appraised_value or self.current_price or Decimal('0')


class Cryptocurrency(ShareBasedInvestment):
    """Cryptocurrency holdings"""
    CRYPTO_TYPES = [
        ('BITCOIN', 'Bitcoin'),
        ('ETHEREUM', 'Ethereum'),
        ('ALTCOIN', 'Altcoin'),
        ('STABLECOIN', 'Stablecoin'),
        ('DEFI', 'DeFi Token'),
        ('NFT', 'NFT Collection'),
    ]

    crypto_type = models.CharField(max_length=20, choices=CRYPTO_TYPES)
    blockchain = models.CharField(max_length=100, blank=True)
    wallet_address = models.CharField(max_length=200, blank=True)
    exchange = models.CharField(max_length=100, blank=True)
    staking_rewards = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    staking_apy = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    market_cap_rank = models.IntegerField(null=True, blank=True)
    circulating_supply = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    max_supply = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    @property
    def annual_staking_rewards(self):
        """Calculate annual staking rewards"""
        if self.staking_apy and self.current_value:
            return self.current_value * self.staking_apy
        return 0

    @property
    def is_staked(self):
        """Check if cryptocurrency is being staked"""
        return self.staking_rewards > 0 or self.staking_apy is not None


class OtherInvestment(Investment):
    """Catch-all for other investment types"""
    INVESTMENT_CATEGORIES = [
        ('COMMODITY', 'Commodity'),
        ('COLLECTIBLE', 'Collectible'),
        ('PRECIOUS_METALS', 'Precious Metals'),
        ('PRIVATE_EQUITY', 'Private Equity'),
        ('HEDGE_FUND', 'Hedge Fund'),
        ('VENTURE_CAPITAL', 'Venture Capital'),
        ('OPTIONS', 'Options'),
        ('FUTURES', 'Futures'),
        ('FOREX', 'Foreign Exchange'),
        ('STRUCTURED_PRODUCT', 'Structured Product'),
    ]

    investment_category = models.CharField(max_length=30, choices=INVESTMENT_CATEGORIES)
    description = models.TextField(blank=True)
    custodian = models.CharField(max_length=200, blank=True)
    maturity_date = models.DateField(null=True, blank=True)
    risk_rating = models.CharField(max_length=20, blank=True)
    liquidity_timeframe = models.CharField(max_length=100, blank=True)
    minimum_investment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    management_fee = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # Value fields (generic investment tracked as total value)
    cost_basis = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total amount invested")
    market_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Current market value")

    @property
    def days_to_maturity(self):
        """Calculate days until maturity if applicable"""
        if self.maturity_date:
            today = timezone.now().date()
            return (self.maturity_date - today).days
        return None

    @property
    def annual_management_fee(self):
        """Calculate annual management fee"""
        if self.management_fee and self.current_value:
            return self.current_value * self.management_fee
        return 0

    @property
    def total_cost(self):
        return self.cost_basis

    @property
    def current_value(self):
        return self.market_value


class Transaction(TimeStampMixin):
    TRANSACTION_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('DIVIDEND', 'Dividend'),
        ('SPLIT', 'Stock Split'),
        ('PREMIUM', 'Premium Payment'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('TAX_WITHHOLDING', 'Tax Withholding'),
        ('NET_CHANGE', 'Net Investment Change'),
    ]

    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    shares = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="For lump-sum transactions like premium payments")
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateTimeField()
    notes = models.TextField(blank=True)
    # Track which statement created this transaction (for automatic cleanup)
    source_statement = models.ForeignKey(
        'Statement',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='generated_transactions',
        help_text="Statement that generated this transaction (if auto-generated)"
    )

    def __str__(self):
        # For lump-sum transactions (premium payments, etc.)
        if self.amount is not None:
            return f"{self.transaction_type} ${self.amount} for {self.investment.symbol or self.investment.name}"
        # For share-based transactions (buy, sell, etc.)
        return f"{self.transaction_type} {self.shares} {self.investment.symbol} @ ${self.price}"

    @property
    def total_amount(self):
        fee = self.fee or 0
        # For lump-sum transactions (premium payments, etc.)
        if self.amount is not None:
            return self.amount + fee
        # For share-based transactions (buy, sell, etc.)
        shares = self.shares or 0
        price = self.price or 0
        return (shares * price) + fee

    class Meta:
        ordering = ['-date']


class InvestmentValue(TimeStampMixin):
    """Historical price data for investments"""
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='historical_values')
    date = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.BigIntegerField(null=True, blank=True)
    market_cap = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=50, default='manual')

    def __str__(self):
        return f"{self.investment.symbol} - ${self.price} on {self.date.date()}"

    def save(self, *args, **kwargs):
        """Save the value and update the investment's current_price if this is the latest value"""
        super().save(*args, **kwargs)

        # Check if this is the most recent value for this investment
        latest_value = self.investment.historical_values.order_by('-date').first()
        if latest_value and latest_value.id == self.id:
            # Update the investment's current_price to match this latest value
            self.investment.current_price = self.price
            self.investment.save(update_fields=['current_price'])

    @property
    def daily_change(self):
        """Calculate daily price change from previous day"""
        if not self.date or not self.investment:
            return None

        previous_day = self.date - timedelta(days=1)
        prev_value = InvestmentValue.objects.filter(
            investment=self.investment,
            date__date=previous_day.date()
        ).first()

        if prev_value:
            change = self.price - prev_value.price
            change_percent = (change / prev_value.price) * 100 if prev_value.price > 0 else 0
            return {
                'absolute': change,
                'percentage': change_percent
            }
        return None

    class Meta:
        ordering = ['-date']
        unique_together = ['investment', 'date']
        indexes = [
            models.Index(fields=['investment', 'date']),
            models.Index(fields=['date']),
        ]


class Statement(PolymorphicModel, TimeStampMixin):
    """Polymorphic base class for all investment statement types"""
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='statements')
    statement_date = models.DateField(help_text="Date of the statement")
    period_start = models.DateField(help_text="Start date of statement period")
    period_end = models.DateField(help_text="End date of statement period")
    document = models.FileField(upload_to='statements/', null=True, blank=True, help_text="Upload statement PDF/image")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-statement_date']
        indexes = [
            models.Index(fields=['investment', 'statement_date']),
        ]

    def __str__(self):
        return f"{self.investment.name} - Statement {self.statement_date}"

    def get_statement_type(self):
        """Return the specific statement type"""
        return self.__class__.__name__


class AnnuityStatement(Statement):
    """Statement for Annuity investments"""
    # Account Values
    beginning_value = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Account value at beginning of period"
    )
    ending_value = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Account value at end of period"
    )

    # Period Activity
    premiums = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Premium payments during period"
    )
    net_change = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Net investment gain/loss during period"
    )
    withdrawals = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Withdrawals during period"
    )
    tax_withholding = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Tax withholding during period"
    )

    # Guaranteed Benefits
    remaining_guaranteed_balance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Remaining guaranteed balance"
    )
    death_benefit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Death benefit amount"
    )
    earnings_determination_baseline = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Baseline for earnings determination"
    )
    guaranteed_withdrawal_balance_bonus_baseline = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="GWB bonus baseline"
    )

    # Withdrawal Information
    guaranteed_withdrawal_amount_annually = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Annual guaranteed withdrawal amount (can be N/A)"
    )
    guaranteed_withdrawal_amount_remaining = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Guaranteed withdrawal amount remaining this year (can be N/A)"
    )
    percent_of_guaranteed_available_for_withdrawal = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        help_text="Percent of guaranteed amount available for withdrawal (e.g., 0.05 for 5%)"
    )

    def __str__(self):
        return f"{self.investment.name} - Annuity Statement {self.statement_date}"

    @property
    def calculated_change(self):
        """Calculate what the change should be based on activity"""
        if self.beginning_value is None or self.ending_value is None:
            return None
        return self.beginning_value + self.premiums + self.net_change - self.withdrawals - self.tax_withholding

    @property
    def reconciles(self):
        """Check if the statement reconciles (calculated change matches ending value)"""
        if self.calculated_change is None or self.ending_value is None:
            return None
        return abs(self.calculated_change - self.ending_value) < Decimal('0.01')  # Within 1 cent

    @property
    def previous_statement(self):
        """Get the previous statement by date"""
        return self.investment.statements.filter(
            statement_date__lt=self.statement_date
        ).order_by('-statement_date').first()

    @property
    def chains_with_previous(self):
        """Check if this statement's beginning value matches the previous statement's ending value"""
        prev = self.previous_statement
        if not prev:
            # First statement - no previous to check against
            return True

        if not hasattr(prev, 'annuitystatement'):
            return None

        prev_stmt = prev.annuitystatement
        if self.beginning_value is None or prev_stmt.ending_value is None:
            return None

        return abs(self.beginning_value - prev_stmt.ending_value) < Decimal('0.01')  # Within 1 cent

    @property
    def chain_gap(self):
        """Calculate the gap between this statement and the previous one"""
        prev = self.previous_statement
        if not prev or not hasattr(prev, 'annuitystatement'):
            return None

        prev_stmt = prev.annuitystatement
        if self.beginning_value is None or prev_stmt.ending_value is None:
            return None

        return self.beginning_value - prev_stmt.ending_value

    def save(self, *args, **kwargs):
        """Override save to automatically create/update transactions"""
        # Check if this is an update (has pk) or new statement
        is_new = self.pk is None

        # Save the statement first
        super().save(*args, **kwargs)

        # Delete existing transactions from this statement if updating
        if not is_new:
            self.generated_transactions.all().delete()

        # Create new transactions
        self._create_transactions()

    def _create_transactions(self):
        """Internal method to create Transaction records from this statement

        Called automatically on save. Creates transactions linked to this statement
        so they can be cleaned up if the statement is deleted.
        """
        from django.utils import timezone

        statement_date_aware = timezone.make_aware(
            timezone.datetime.combine(self.statement_date, timezone.datetime.min.time())
        )

        # Create premium transaction if applicable
        if self.premiums > 0:
            Transaction.objects.create(
                investment=self.investment,
                transaction_type='PREMIUM',
                amount=self.premiums,
                date=statement_date_aware,
                notes=f'From statement {self.statement_date}',
                source_statement=self
            )

        # Create withdrawal transaction if applicable
        if self.withdrawals > 0:
            Transaction.objects.create(
                investment=self.investment,
                transaction_type='WITHDRAWAL',
                amount=self.withdrawals,
                date=statement_date_aware,
                notes=f'From statement {self.statement_date}',
                source_statement=self
            )

        # Create tax withholding transaction if applicable
        if self.tax_withholding > 0:
            Transaction.objects.create(
                investment=self.investment,
                transaction_type='TAX_WITHHOLDING',
                amount=self.tax_withholding,
                date=statement_date_aware,
                notes=f'From statement {self.statement_date}',
                source_statement=self
            )

        # Create net change transaction if applicable
        if self.net_change != 0:
            Transaction.objects.create(
                investment=self.investment,
                transaction_type='NET_CHANGE',
                amount=self.net_change,
                date=statement_date_aware,
                notes=f'From statement {self.statement_date}',
                source_statement=self
            )

    class Meta:
        verbose_name = "Annuity Statement"
        verbose_name_plural = "Annuity Statements"


class PredictionModel(TimeStampMixin):
    """Store prediction models and results for investments"""
    PREDICTION_TYPES = [
        ('LINEAR_REGRESSION', 'Linear Regression'),
        ('MOVING_AVERAGE', 'Moving Average'),
        ('ARIMA', 'ARIMA'),
        ('LSTM', 'LSTM Neural Network'),
    ]

    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='predictions')
    model_type = models.CharField(max_length=20, choices=PREDICTION_TYPES)
    prediction_date = models.DateTimeField()
    predicted_price = models.DecimalField(max_digits=10, decimal_places=2)
    confidence_interval_low = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    confidence_interval_high = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    training_period_days = models.IntegerField()
    model_parameters = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.investment.symbol} - {self.model_type} prediction for {self.prediction_date.date()}"

    @property
    def prediction_accuracy(self):
        """Calculate accuracy if actual price is available"""
        actual_value = InvestmentValue.objects.filter(
            investment=self.investment,
            date__date=self.prediction_date.date()
        ).first()

        if actual_value:
            error = abs(float(actual_value.price) - float(self.predicted_price))
            accuracy = max(0, 100 - (error / float(actual_value.price) * 100))
            return round(accuracy, 2)
        return None

    class Meta:
        ordering = ['-prediction_date']
        indexes = [
            models.Index(fields=['investment', 'prediction_date']),
            models.Index(fields=['model_type', 'created_at']),
        ]
