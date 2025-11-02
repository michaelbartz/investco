from django.contrib import admin
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import (
    Portfolio, Investment, Transaction, InvestmentValue, PredictionModel,
    Stock, Bond, ETF, MutualFund, Retirement401k, Annuity, RealEstate,
    Cryptocurrency, OtherInvestment, GuaranteedWithdrawalBalance,
    Statement, AnnuityStatement
)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'created_at', 'total_value']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'user__username']
    readonly_fields = ['total_value']


@admin.register(Investment)
class InvestmentAdmin(PolymorphicParentModelAdmin):
    """Parent admin for polymorphic Investment model"""
    base_model = Investment
    child_models = (Stock, Bond, ETF, MutualFund, Retirement401k, Annuity, RealEstate, Cryptocurrency, OtherInvestment)
    list_display = ['symbol', 'name', 'get_investment_type', 'portfolio', 'current_value']
    list_filter = ['portfolio', 'created_at', 'polymorphic_ctype']
    search_fields = ['symbol', 'name']


@admin.register(Stock)
class StockAdmin(PolymorphicChildModelAdmin):
    list_display = ['ticker_symbol', 'company_name', 'sector', 'portfolio', 'shares', 'current_price', 'current_value']
    list_filter = ['sector', 'exchange', 'portfolio', 'created_at']
    search_fields = ['ticker_symbol', 'company_name', 'sector']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage']
    fieldsets = (
        ('Basic Information', {
            'fields': ('portfolio', 'ticker_symbol', 'company_name', 'sector', 'exchange')
        }),
        ('Investment Details', {
            'fields': ('shares', 'average_cost', 'current_price', 'market_cap', 'pe_ratio', 'dividend_yield')
        }),
        ('Calculated Values', {
            'fields': ('total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Bond)
class BondAdmin(PolymorphicChildModelAdmin):
    list_display = ['name', 'bond_type', 'issuer', 'coupon_rate', 'maturity_date', 'current_value']
    list_filter = ['bond_type', 'maturity_date', 'portfolio', 'created_at']
    search_fields = ['name', 'issuer', 'credit_rating']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'years_to_maturity', 'annual_coupon_payment']


@admin.register(ETF)
class ETFAdmin(PolymorphicChildModelAdmin):
    list_display = ['symbol', 'fund_name', 'expense_ratio', 'portfolio', 'shares', 'current_value']
    list_filter = ['portfolio', 'created_at']
    search_fields = ['symbol', 'fund_name', 'benchmark_index']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage']


@admin.register(MutualFund)
class MutualFundAdmin(PolymorphicChildModelAdmin):
    list_display = ['symbol', 'fund_name', 'fund_type', 'expense_ratio', 'portfolio', 'current_value']
    list_filter = ['fund_type', 'portfolio', 'created_at']
    search_fields = ['symbol', 'fund_name', 'fund_manager']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage']


@admin.register(Retirement401k)
class Retirement401kAdmin(PolymorphicChildModelAdmin):
    list_display = ['name', 'contribution_type', 'employer_name', 'portfolio', 'current_value']
    list_filter = ['contribution_type', 'employer_name', 'portfolio', 'created_at']
    search_fields = ['name', 'employer_name', 'plan_name']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'employer_match_value']


@admin.register(Annuity)
class AnnuityAdmin(PolymorphicChildModelAdmin):
    list_display = ['name', 'annuity_type', 'insurance_company', 'issue_date', 'portfolio', 'current_value', 'statement_gaps_count']
    list_filter = ['annuity_type', 'insurance_company', 'issue_date', 'portfolio', 'created_at']
    search_fields = ['name', 'insurance_company', 'policy_number']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'is_in_payout_phase', 'annual_payout', 'statement_gaps_summary']
    actions = ['check_statement_gaps']

    def statement_gaps_count(self, obj):
        """Display count of statement gaps"""
        gaps = obj.get_statement_gaps()
        if not gaps:
            return '✓ No gaps'
        return f'⚠️ {len(gaps)} gap(s)'
    statement_gaps_count.short_description = 'Statement Chain'

    def statement_gaps_summary(self, obj):
        """Display detailed gap information in the detail view"""
        gaps = obj.get_statement_gaps()
        if not gaps:
            return '✓ All statements chain correctly'

        from django.utils.html import format_html
        result = f'<strong>⚠️ Found {len(gaps)} gap(s):</strong><br><br>'
        for gap in gaps:
            result += f'<div style="margin-left: 20px; margin-bottom: 10px;">'
            result += f'<strong>{gap["statement_date"]}</strong><br>'
            result += f'Previous ending ({gap["previous_date"]}): ${gap["previous_ending"]:,.2f}<br>'
            result += f'Current beginning: ${gap["current_beginning"]:,.2f}<br>'
            result += f'<span style="color: red;">Gap: ${gap["gap_amount"]:,.2f}</span>'
            result += f'</div>'
        return format_html(result)
    statement_gaps_summary.short_description = 'Statement Chain Analysis'

    def check_statement_gaps(self, request, queryset):
        """Admin action to check for gaps in selected annuities"""
        from django.contrib import messages

        total_gaps = 0
        for annuity in queryset:
            gaps = annuity.get_statement_gaps()
            if gaps:
                total_gaps += len(gaps)
                gap_msg = ', '.join([f'{g["statement_date"]} (${g["gap_amount"]:,.2f})' for g in gaps])
                messages.warning(request, f'{annuity.name}: {len(gaps)} gap(s) - {gap_msg}')
            else:
                messages.success(request, f'{annuity.name}: All statements chain correctly')

        if total_gaps > 0:
            messages.warning(request, f'Total: {total_gaps} gap(s) found across {queryset.count()} annuity/annuities')
        else:
            messages.success(request, f'No gaps found in {queryset.count()} annuity/annuities')
    check_statement_gaps.short_description = 'Check for statement gaps'


@admin.register(RealEstate)
class RealEstateAdmin(PolymorphicChildModelAdmin):
    list_display = ['name', 'property_type', 'address', 'portfolio', 'current_value', 'equity']
    list_filter = ['property_type', 'portfolio', 'created_at']
    search_fields = ['name', 'address']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'net_monthly_income', 'annual_net_income', 'equity', 'cap_rate']


@admin.register(Cryptocurrency)
class CryptocurrencyAdmin(PolymorphicChildModelAdmin):
    list_display = ['symbol', 'name', 'crypto_type', 'blockchain', 'portfolio', 'current_value']
    list_filter = ['crypto_type', 'blockchain', 'exchange', 'portfolio', 'created_at']
    search_fields = ['symbol', 'name', 'blockchain']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'annual_staking_rewards', 'is_staked']


@admin.register(OtherInvestment)
class OtherInvestmentAdmin(PolymorphicChildModelAdmin):
    list_display = ['name', 'investment_category', 'custodian', 'portfolio', 'current_value']
    list_filter = ['investment_category', 'custodian', 'portfolio', 'created_at']
    search_fields = ['name', 'custodian', 'description']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'days_to_maturity', 'annual_management_fee']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['investment', 'transaction_type', 'shares', 'price', 'display_amount', 'date', 'source_statement', 'display_total_amount']
    list_filter = ['transaction_type', 'date', 'investment__portfolio', 'source_statement']
    search_fields = ['investment__symbol', 'investment__name', 'notes']
    readonly_fields = ['total_amount', 'source_statement']
    date_hierarchy = 'date'
    fieldsets = (
        ('Basic Information', {
            'fields': ('investment', 'transaction_type', 'date', 'source_statement')
        }),
        ('Share-Based Transaction (Buy/Sell/Dividend/Split)', {
            'fields': ('shares', 'price'),
            'description': 'For transactions involving shares (stocks, bonds, etc.)'
        }),
        ('Lump-Sum Transaction (Premium Payments)', {
            'fields': ('amount',),
            'description': 'For fixed-amount transactions like IRA/annuity premium payments'
        }),
        ('Additional Details', {
            'fields': ('fee', 'notes', 'total_amount'),
        }),
    )

    def display_amount(self, obj):
        """Display amount with comma formatting"""
        if obj.amount is not None:
            from django.contrib.humanize.templatetags.humanize import intcomma
            return f'${intcomma(obj.amount)}'
        return '-'
    display_amount.short_description = 'Amount'
    display_amount.admin_order_field = 'amount'

    def display_total_amount(self, obj):
        """Display total amount with comma formatting"""
        from django.contrib.humanize.templatetags.humanize import intcomma
        return f'${intcomma(obj.total_amount)}'
    display_total_amount.short_description = 'Total Amount'
    display_total_amount.admin_order_field = 'amount'


@admin.register(InvestmentValue)
class InvestmentValueAdmin(admin.ModelAdmin):
    list_display = ['investment', 'date', 'price', 'volume', 'source']
    list_filter = ['date', 'source', 'investment__portfolio']
    search_fields = ['investment__symbol', 'investment__name']
    readonly_fields = ['daily_change']
    date_hierarchy = 'date'


@admin.register(PredictionModel)
class PredictionModelAdmin(admin.ModelAdmin):
    list_display = ['investment', 'model_type', 'prediction_date', 'predicted_price', 'accuracy_score']
    list_filter = ['model_type', 'prediction_date', 'investment__portfolio']
    search_fields = ['investment__symbol', 'investment__name']
    readonly_fields = ['prediction_accuracy']
    date_hierarchy = 'prediction_date'


@admin.register(GuaranteedWithdrawalBalance)
class GuaranteedWithdrawalBalanceAdmin(admin.ModelAdmin):
    list_display = ['annuity', 'balance', 'effective_date', 'created_at']
    list_filter = ['effective_date', 'created_at', 'annuity__portfolio']
    search_fields = ['annuity__name', 'notes']
    date_hierarchy = 'effective_date'
    fieldsets = (
        ('Annuity Information', {
            'fields': ('annuity',)
        }),
        ('Balance Details', {
            'fields': ('balance', 'effective_date', 'notes')
        }),
    )


@admin.register(Statement)
class StatementAdmin(PolymorphicParentModelAdmin):
    """Parent admin for polymorphic Statement model"""
    base_model = Statement
    child_models = (AnnuityStatement,)
    list_display = ['investment', 'get_statement_type', 'statement_date', 'period_start', 'period_end']
    list_filter = ['statement_date', 'investment__portfolio']
    search_fields = ['investment__name', 'notes']
    date_hierarchy = 'statement_date'


@admin.register(AnnuityStatement)
class AnnuityStatementAdmin(PolymorphicChildModelAdmin):
    list_display = [
        'investment', 'statement_date', 'beginning_value', 'ending_value',
        'premiums', 'net_change', 'withdrawals', 'reconciles_display', 'chains_display'
    ]
    list_filter = ['statement_date', 'investment__portfolio']
    search_fields = ['investment__name', 'notes']
    readonly_fields = ['calculated_change', 'reconciles_display', 'chains_with_previous_display', 'chain_gap']
    date_hierarchy = 'statement_date'

    fieldsets = (
        ('Statement Information', {
            'fields': ('investment', 'statement_date', 'period_start', 'period_end', 'document', 'notes')
        }),
        ('Account Values', {
            'fields': ('beginning_value', 'ending_value', 'calculated_change', 'reconciles_display'),
            'description': 'Beginning and ending account values for this statement period'
        }),
        ('Statement Chaining', {
            'fields': ('chains_with_previous_display', 'chain_gap'),
            'description': 'Verification that this statement chains correctly with the previous statement'
        }),
        ('Period Activity', {
            'fields': ('premiums', 'net_change', 'withdrawals', 'tax_withholding'),
            'description': 'Transaction activity during the statement period'
        }),
        ('Guaranteed Benefits', {
            'fields': (
                'remaining_guaranteed_balance', 'death_benefit',
                'earnings_determination_baseline', 'guaranteed_withdrawal_balance_bonus_baseline'
            ),
            'description': 'Guaranteed benefit values as of statement date',
            'classes': ('collapse',)
        }),
        ('Withdrawal Information', {
            'fields': (
                'guaranteed_withdrawal_amount_annually',
                'guaranteed_withdrawal_amount_remaining',
                'percent_of_guaranteed_available_for_withdrawal'
            ),
            'description': 'Guaranteed withdrawal benefit information',
            'classes': ('collapse',)
        }),
    )

    def reconciles_display(self, obj):
        """Display reconciliation status with color coding"""
        # Handle cases where values aren't set yet (new form)
        if obj.reconciles is None:
            return '-'
        elif obj.reconciles:
            return '✓ Reconciles'
        else:
            difference = abs(obj.calculated_change - obj.ending_value)
            return f'✗ Off by ${difference:.2f}'
    reconciles_display.short_description = 'Reconciles'

    def chains_display(self, obj):
        """Display chaining status in list view"""
        if obj.chains_with_previous is None:
            return '-'
        elif obj.chains_with_previous:
            return '✓'
        else:
            gap = obj.chain_gap
            if gap:
                return f'✗ ${gap:,.2f}'
            return '✗'
    chains_display.short_description = 'Chains'

    def chains_with_previous_display(self, obj):
        """Display detailed chaining status in detail view"""
        prev = obj.previous_statement
        if not prev:
            return '✓ First statement'

        if not hasattr(prev, 'annuitystatement'):
            return 'N/A - Previous is not an annuity statement'

        prev_stmt = prev.annuitystatement

        if obj.chains_with_previous:
            return f'✓ Chains correctly with {prev_stmt.statement_date}'
        else:
            gap = obj.chain_gap
            if gap:
                return f'✗ Gap of ${gap:,.2f} from previous statement ({prev_stmt.statement_date}). ' \
                       f'Previous ending: ${prev_stmt.ending_value:,.2f}, This beginning: ${obj.beginning_value:,.2f}'
            return f'✗ Does not chain with {prev_stmt.statement_date}'
    chains_with_previous_display.short_description = 'Chains with Previous'
