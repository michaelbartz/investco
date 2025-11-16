from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import (
    Portfolio, Investment, Transaction, InvestmentValue, PredictionModel,
    Stock, Bond, ETF, MutualFund, Retirement401k, Annuity, BrokerageAccount, RealEstate,
    Cryptocurrency, OtherInvestment, GuaranteedWithdrawalBalance,
    Statement, AnnuityStatement, Retirement401kStatement, BrokerageAccountStatement,
    RetirementPlan
)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'retirement_date', 'created_at', 'total_value']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'user__username']
    readonly_fields = ['total_value']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'user', 'description')
        }),
        ('Retirement Planning', {
            'fields': ('retirement_date',)
        }),
        ('Summary', {
            'fields': ('total_value',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Investment)
class InvestmentAdmin(PolymorphicParentModelAdmin):
    """Parent admin for polymorphic Investment model"""
    base_model = Investment
    child_models = (Stock, Bond, ETF, MutualFund, Retirement401k, Annuity, BrokerageAccount, RealEstate, Cryptocurrency, OtherInvestment)
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


@admin.register(BrokerageAccount)
class BrokerageAccountAdmin(PolymorphicChildModelAdmin):
    list_display = ['name', 'account_type', 'brokerage_firm', 'portfolio', 'current_value', 'cash_balance']
    list_filter = ['account_type', 'brokerage_firm', 'tax_advantaged', 'portfolio', 'created_at']
    search_fields = ['name', 'brokerage_firm', 'account_number']
    readonly_fields = ['total_cost', 'current_value', 'gain_loss', 'gain_loss_percentage', 'is_retirement_account']


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
    child_models = (AnnuityStatement, Retirement401kStatement, BrokerageAccountStatement)
    list_display = ['investment', 'get_statement_type', 'statement_date', 'period_start', 'period_end']
    list_filter = ['investment', 'statement_date', 'investment__portfolio']
    search_fields = ['investment__name', 'notes']
    date_hierarchy = 'statement_date'


@admin.register(AnnuityStatement)
class AnnuityStatementAdmin(PolymorphicChildModelAdmin):
    list_display = [
        'investment', 'statement_date', 'beginning_value', 'ending_value',
        'premiums', 'net_change', 'withdrawals', 'reconciles_display', 'chains_display'
    ]
    list_filter = ['investment', 'statement_date', 'investment__portfolio']
    search_fields = ['investment__name', 'notes']
    readonly_fields = ['calculated_change', 'reconciles_display', 'chains_with_previous_display', 'chain_gap']
    date_hierarchy = 'statement_date'

    def get_urls(self):
        """Add custom URL for PDF import"""
        urls = super().get_urls()
        custom_urls = [
            path('import-pdf/', self.admin_site.admin_view(self.import_pdf_view), name='investco_annuitystatement_import_pdf'),
        ]
        return custom_urls + urls

    def import_pdf_view(self, request):
        """View for importing annuity statement from PDF"""
        from .pdf_parser import parse_annuity_statement
        from decimal import Decimal
        import os

        if request.method == 'POST':
            if 'pdf_file' in request.FILES:
                # Step 1: Parse the PDF
                pdf_file = request.FILES['pdf_file']

                # Save temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    for chunk in pdf_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                try:
                    # Parse the PDF
                    data, validation = parse_annuity_statement(tmp_path)

                    # Try to find matching annuity by policy number
                    matched_annuity_id = None
                    if data.get('policy_number'):
                        try:
                            matched_annuity = Annuity.objects.get(policy_number=data.get('policy_number'))
                            matched_annuity_id = matched_annuity.id
                            messages.info(request, f'✓ Found matching annuity: {matched_annuity.name}')
                        except Annuity.DoesNotExist:
                            messages.warning(request, f'Policy number {data.get("policy_number")} extracted, but no matching annuity found. Please select manually.')
                        except Annuity.MultipleObjectsReturned:
                            messages.warning(request, f'Multiple annuities found with policy number {data.get("policy_number")}. Please select manually.')

                    # Store parsed data in session for verification step
                    request.session['parsed_statement_data'] = {
                        'statement_date': data.get('statement_date').isoformat() if data.get('statement_date') else None,
                        'period_start': data.get('period_start').isoformat() if data.get('period_start') else None,
                        'period_end': data.get('period_end').isoformat() if data.get('period_end') else None,
                        'beginning_value': str(data.get('beginning_value', '0')),
                        'ending_value': str(data.get('ending_value', '0')),
                        'premiums': str(data.get('premiums', '0')),
                        'withdrawals': str(data.get('withdrawals', '0')),
                        'tax_withholding': str(data.get('tax_withholding', '0')),
                        'net_change': str(data.get('net_change', '0')),
                        'remaining_guaranteed_balance': str(data.get('remaining_guaranteed_balance', '0')),
                        'death_benefit': str(data.get('death_benefit', '0')),
                        'earnings_determination_baseline': str(data.get('earnings_determination_baseline', '0')) if data.get('earnings_determination_baseline') else '',
                        'guaranteed_withdrawal_balance_bonus_baseline': str(data.get('guaranteed_withdrawal_balance_bonus_baseline', '0')) if data.get('guaranteed_withdrawal_balance_bonus_baseline') else '',
                        'policy_number': data.get('policy_number', ''),
                        'matched_annuity_id': matched_annuity_id,
                        'pdf_filename': pdf_file.name,
                    }
                    request.session['validation_result'] = validation

                    # Show validation messages
                    if validation['errors']:
                        for error in validation['errors']:
                            messages.error(request, error)

                    if validation['warnings']:
                        for warning in validation['warnings']:
                            messages.warning(request, warning)

                    if not validation['errors']:
                        messages.success(request, 'PDF parsed successfully! Please review and confirm the values below.')

                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)

                # Redirect to verification form
                return redirect(request.path)

            elif 'confirm_import' in request.POST:
                # Step 2: Create the statement from verified data
                parsed_data = request.session.get('parsed_statement_data')
                if not parsed_data:
                    messages.error(request, 'Session expired. Please upload the PDF again.')
                    return redirect(request.path)

                try:
                    from datetime import date

                    # Get the annuity
                    annuity_id = request.POST.get('annuity')
                    annuity = Annuity.objects.get(id=annuity_id)

                    # Create statement with user-verified values
                    statement = AnnuityStatement.objects.create(
                        investment=annuity,
                        statement_date=date.fromisoformat(request.POST.get('statement_date')),
                        period_start=date.fromisoformat(request.POST.get('period_start')),
                        period_end=date.fromisoformat(request.POST.get('period_end')),
                        beginning_value=Decimal(request.POST.get('beginning_value')),
                        ending_value=Decimal(request.POST.get('ending_value')),
                        premiums=Decimal(request.POST.get('premiums')),
                        withdrawals=Decimal(request.POST.get('withdrawals')),
                        tax_withholding=Decimal(request.POST.get('tax_withholding')),
                        net_change=Decimal(request.POST.get('net_change')),
                        remaining_guaranteed_balance=Decimal(request.POST.get('remaining_guaranteed_balance')) if request.POST.get('remaining_guaranteed_balance') else None,
                        death_benefit=Decimal(request.POST.get('death_benefit')) if request.POST.get('death_benefit') else None,
                        earnings_determination_baseline=Decimal(request.POST.get('earnings_determination_baseline')) if request.POST.get('earnings_determination_baseline') else None,
                        guaranteed_withdrawal_balance_bonus_baseline=Decimal(request.POST.get('guaranteed_withdrawal_balance_bonus_baseline')) if request.POST.get('guaranteed_withdrawal_balance_bonus_baseline') else None,
                        notes=f"Imported from PDF: {parsed_data.get('pdf_filename', 'unknown')}"
                    )

                    # Clear session data
                    del request.session['parsed_statement_data']
                    if 'validation_result' in request.session:
                        del request.session['validation_result']

                    messages.success(request, f'Statement created successfully for {statement.statement_date}')

                    # Redirect to the created statement
                    return redirect(f'/admin/investco/annuitystatement/{statement.id}/change/')

                except Exception as e:
                    messages.error(request, f'Error creating statement: {str(e)}')

            elif 'cancel_import' in request.POST:
                # Clear session data
                if 'parsed_statement_data' in request.session:
                    del request.session['parsed_statement_data']
                if 'validation_result' in request.session:
                    del request.session['validation_result']
                messages.info(request, 'Import cancelled')
                return redirect('/admin/investco/annuitystatement/')

        # GET request or after parsing - show form
        parsed_data = request.session.get('parsed_statement_data')
        validation = request.session.get('validation_result')
        annuities = Annuity.objects.all()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import Annuity Statement from PDF',
            'parsed_data': parsed_data,
            'validation': validation,
            'annuities': annuities,
            'opts': self.model._meta,
        }

        return render(request, 'admin/investco/import_pdf.html', context)

    def changelist_view(self, request, extra_context=None):
        """Add 'Import from PDF' button to changelist"""
        extra_context = extra_context or {}
        extra_context['show_import_pdf_button'] = True
        return super().changelist_view(request, extra_context)

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
            # Check if we can calculate the difference
            if obj.calculated_change is not None and obj.ending_value is not None:
                difference = abs(obj.calculated_change - obj.ending_value)
                return f'✗ Off by ${difference:.2f}'
            else:
                return '✗ Incomplete data'
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


@admin.register(Retirement401kStatement)
class Retirement401kStatementAdmin(PolymorphicChildModelAdmin):
    list_display = [
        'investment', 'statement_date', 'beginning_value', 'ending_value',
        'employee_contributions', 'employer_contributions', 'investment_gain_loss',
        'reconciles_display', 'chains_display'
    ]
    list_filter = ['investment', 'statement_date', 'investment__portfolio']
    search_fields = ['investment__name', 'notes']
    readonly_fields = ['calculated_change', 'reconciles_display', 'chains_with_previous_display', 'chain_gap', 'total_contributions']
    date_hierarchy = 'statement_date'

    def get_urls(self):
        """Add custom URL for PDF import"""
        urls = super().get_urls()
        custom_urls = [
            path('import-pdf/', self.admin_site.admin_view(self.import_pdf_view), name='investco_retirement401kstatement_import_pdf'),
        ]
        return custom_urls + urls

    def import_pdf_view(self, request):
        """View for importing 401k statement from PDF"""
        from .pdf_parser import parse_statement
        from decimal import Decimal
        import os

        if request.method == 'POST':
            if 'pdf_file' in request.FILES:
                # Step 1: Parse the PDF
                pdf_file = request.FILES['pdf_file']

                # Save temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    for chunk in pdf_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                try:
                    # Parse the PDF
                    data, validation = parse_statement(tmp_path)

                    # Try to find matching 401k by account number
                    matched_401k_id = None
                    if data.get('account_number'):
                        try:
                            matched_401k = Retirement401k.objects.get(account_number=data.get('account_number'))
                            matched_401k_id = matched_401k.id
                            messages.info(request, f'✓ Found matching 401k: {matched_401k.name}')
                        except Retirement401k.DoesNotExist:
                            messages.warning(request, f'Account number {data.get("account_number")} extracted, but no matching 401k found. Please select manually.')
                        except Retirement401k.MultipleObjectsReturned:
                            messages.warning(request, f'Multiple 401k accounts found with account number {data.get("account_number")}. Please select manually.')

                    # Store parsed data in session for verification step
                    request.session['parsed_statement_data'] = {
                        'statement_date': data.get('statement_date').isoformat() if data.get('statement_date') else None,
                        'period_start': data.get('period_start').isoformat() if data.get('period_start') else None,
                        'period_end': data.get('period_end').isoformat() if data.get('period_end') else None,
                        'beginning_value': str(data.get('beginning_value', '0')),
                        'ending_value': str(data.get('ending_value', '0')),
                        'employee_contributions': str(data.get('employee_contributions', '0')),
                        'employer_contributions': str(data.get('employer_contributions', '0')),
                        'investment_gain_loss': str(data.get('investment_gain_loss', '0')),
                        'withdrawals': str(data.get('withdrawals', '0')),
                        'fees': str(data.get('fees', '0')),
                        'loan_payments': str(data.get('loan_payments', '0')),
                        'vested_balance': str(data.get('vested_balance', '0')) if data.get('vested_balance') else '',
                        'account_number': data.get('account_number', ''),
                        'matched_401k_id': matched_401k_id,
                        'pdf_filename': pdf_file.name,
                    }
                    request.session['validation_result'] = validation

                    # Show validation messages
                    if validation['errors']:
                        for error in validation['errors']:
                            messages.error(request, error)

                    if validation['warnings']:
                        for warning in validation['warnings']:
                            messages.warning(request, warning)

                    if not validation['errors']:
                        messages.success(request, 'PDF parsed successfully! Please review and confirm the values below.')

                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)

                # Redirect to verification form
                return redirect(request.path)

            elif 'confirm_import' in request.POST:
                # Step 2: Create the statement from verified data
                parsed_data = request.session.get('parsed_statement_data')
                if not parsed_data:
                    messages.error(request, 'Session expired. Please upload the PDF again.')
                    return redirect(request.path)

                try:
                    from datetime import date

                    # Get the 401k account
                    account_id = request.POST.get('account')
                    account = Retirement401k.objects.get(id=account_id)

                    # Create statement with user-verified values
                    statement = Retirement401kStatement.objects.create(
                        investment=account,
                        statement_date=date.fromisoformat(request.POST.get('statement_date')),
                        period_start=date.fromisoformat(request.POST.get('period_start')),
                        period_end=date.fromisoformat(request.POST.get('period_end')),
                        beginning_value=Decimal(request.POST.get('beginning_value')),
                        ending_value=Decimal(request.POST.get('ending_value')),
                        employee_contributions=Decimal(request.POST.get('employee_contributions')),
                        employer_contributions=Decimal(request.POST.get('employer_contributions')),
                        investment_gain_loss=Decimal(request.POST.get('investment_gain_loss')),
                        withdrawals=Decimal(request.POST.get('withdrawals')),
                        fees=Decimal(request.POST.get('fees')),
                        loan_payments=Decimal(request.POST.get('loan_payments')),
                        vested_balance=Decimal(request.POST.get('vested_balance')) if request.POST.get('vested_balance') else None,
                        notes=f"Imported from PDF: {parsed_data.get('pdf_filename', 'unknown')}"
                    )

                    # Clear session data
                    del request.session['parsed_statement_data']
                    if 'validation_result' in request.session:
                        del request.session['validation_result']

                    messages.success(request, f'Statement created successfully for {statement.statement_date}')

                    # Redirect to the created statement
                    return redirect(f'/admin/investco/retirement401kstatement/{statement.id}/change/')

                except Exception as e:
                    messages.error(request, f'Error creating statement: {str(e)}')

            elif 'cancel_import' in request.POST:
                # Clear session data
                if 'parsed_statement_data' in request.session:
                    del request.session['parsed_statement_data']
                if 'validation_result' in request.session:
                    del request.session['validation_result']
                messages.info(request, 'Import cancelled')
                return redirect('/admin/investco/retirement401kstatement/')

        # GET request or after parsing - show form
        parsed_data = request.session.get('parsed_statement_data')
        validation = request.session.get('validation_result')
        accounts = Retirement401k.objects.all()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import 401k Statement from PDF',
            'parsed_data': parsed_data,
            'validation': validation,
            'accounts': accounts,
            'opts': self.model._meta,
            'statement_type': '401k',
        }

        return render(request, 'admin/investco/import_pdf.html', context)

    def changelist_view(self, request, extra_context=None):
        """Add 'Import from PDF' button to changelist"""
        extra_context = extra_context or {}
        extra_context['show_import_pdf_button'] = True
        return super().changelist_view(request, extra_context)

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
        ('Contributions', {
            'fields': ('employee_contributions', 'employer_contributions', 'total_contributions'),
            'description': 'Contribution activity during the statement period'
        }),
        ('Period Activity', {
            'fields': ('investment_gain_loss', 'withdrawals', 'fees', 'loan_payments'),
            'description': 'Investment and transaction activity during the statement period'
        }),
        ('Vesting Information', {
            'fields': ('vested_balance',),
            'description': 'Vested balance as of statement date',
            'classes': ('collapse',)
        }),
    )

    def reconciles_display(self, obj):
        """Display reconciliation status with color coding"""
        if obj.reconciles is None:
            return '-'
        elif obj.reconciles:
            return '✓ Reconciles'
        else:
            # Check if we can calculate the difference
            if obj.calculated_change is not None and obj.ending_value is not None:
                difference = abs(obj.calculated_change - obj.ending_value)
                return f'✗ Off by ${difference:.2f}'
            else:
                return '✗ Incomplete data'
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

        if not hasattr(prev, 'retirement401kstatement'):
            return 'N/A - Previous is not a 401k statement'

        prev_stmt = prev.retirement401kstatement

        if obj.chains_with_previous:
            return f'✓ Chains correctly with {prev_stmt.statement_date}'
        else:
            gap = obj.chain_gap
            if gap:
                return f'✗ Gap of ${gap:,.2f} from previous statement ({prev_stmt.statement_date}). ' \
                       f'Previous ending: ${prev_stmt.ending_value:,.2f}, This beginning: ${obj.beginning_value:,.2f}'
            return f'✗ Does not chain with {prev_stmt.statement_date}'
    chains_with_previous_display.short_description = 'Chains with Previous'


@admin.register(BrokerageAccountStatement)
class BrokerageAccountStatementAdmin(PolymorphicChildModelAdmin):
    list_display = [
        'investment', 'statement_date', 'beginning_value', 'ending_value',
        'deposits', 'dividends', 'market_change',
        'reconciles_display', 'chains_display'
    ]
    list_filter = ['investment', 'statement_date', 'investment__portfolio']
    search_fields = ['investment__name', 'notes']
    readonly_fields = ['calculated_change', 'reconciles_display', 'chains_with_previous_display', 'chain_gap', 'total_income', 'net_deposits']
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
        ('Deposits and Withdrawals', {
            'fields': ('deposits', 'withdrawals', 'net_deposits'),
            'description': 'Cash flow activity during the statement period'
        }),
        ('Income', {
            'fields': ('dividends', 'interest', 'capital_gains', 'total_income'),
            'description': 'Income earned during the statement period'
        }),
        ('Period Activity', {
            'fields': ('market_change', 'fees', 'other_activity'),
            'description': 'Market changes and other activity during the statement period'
        }),
        ('Account Allocation', {
            'fields': ('money_market', 'equities', 'fixed_income'),
            'description': 'Asset allocation breakdown as of statement date',
            'classes': ('collapse',)
        }),
        ('Cost Basis', {
            'fields': ('total_cost_basis',),
            'description': 'Cost basis tracking (optional)',
            'classes': ('collapse',)
        }),
    )

    def get_urls(self):
        """Add custom URL for PDF import"""
        urls = super().get_urls()
        custom_urls = [
            path('import-pdf/', self.admin_site.admin_view(self.import_pdf_view), name='investco_brokerageaccountstatement_import_pdf'),
        ]
        return custom_urls + urls

    def import_pdf_view(self, request):
        """View for importing brokerage statement from PDF"""
        from .pdf_parser import parse_statement
        from decimal import Decimal
        import os

        if request.method == 'POST':
            if 'pdf_file' in request.FILES:
                # Step 1: Parse the PDF
                pdf_file = request.FILES['pdf_file']

                # Save temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    for chunk in pdf_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                try:
                    # Parse the PDF
                    data, validation = parse_statement(tmp_path)

                    # Try to find matching brokerage account by account number
                    matched_account_id = None
                    if data.get('account_number'):
                        try:
                            matched_account = BrokerageAccount.objects.get(account_number=data.get('account_number'))
                            matched_account_id = matched_account.id
                            messages.info(request, f'✓ Found matching account: {matched_account.name}')
                        except BrokerageAccount.DoesNotExist:
                            messages.warning(request, f'Account number {data.get("account_number")} extracted, but no matching account found. Please select manually.')
                        except BrokerageAccount.MultipleObjectsReturned:
                            messages.warning(request, f'Multiple accounts found with account number {data.get("account_number")}. Please select manually.')

                    # Store parsed data in session for verification step
                    request.session['parsed_statement_data'] = {
                        'statement_date': data.get('statement_date').isoformat() if data.get('statement_date') else None,
                        'period_start': data.get('period_start').isoformat() if data.get('period_start') else None,
                        'period_end': data.get('period_end').isoformat() if data.get('period_end') else None,
                        'beginning_value': str(data.get('beginning_value', '0')),
                        'ending_value': str(data.get('ending_value', '0')),
                        'deposits': str(data.get('deposits', '0')),
                        'withdrawals': str(data.get('withdrawals', '0')),
                        'dividends': str(data.get('dividends', '0')),
                        'interest': str(data.get('interest', '0')),
                        'capital_gains': str(data.get('capital_gains', '0')),
                        'market_change': str(data.get('market_change', '0')),
                        'fees': str(data.get('fees', '0')),
                        'other_activity': str(data.get('other_activity', '0')),
                        'account_number': data.get('account_number', ''),
                        'matched_account_id': matched_account_id,
                        'pdf_filename': pdf_file.name,
                    }
                    request.session['validation_result'] = validation

                    # Show validation messages
                    if validation['errors']:
                        for error in validation['errors']:
                            messages.error(request, error)

                    if validation['warnings']:
                        for warning in validation['warnings']:
                            messages.warning(request, warning)

                    if not validation['errors']:
                        messages.success(request, 'PDF parsed successfully! Please review and confirm the values below.')

                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)

                # Redirect to verification form
                return redirect(request.path)

            elif 'confirm_import' in request.POST:
                # Step 2: Create the statement from verified data
                parsed_data = request.session.get('parsed_statement_data')
                if not parsed_data:
                    messages.error(request, 'Session expired. Please upload the PDF again.')
                    return redirect(request.path)

                try:
                    from datetime import date

                    # Get the brokerage account
                    account_id = request.POST.get('account')
                    account = BrokerageAccount.objects.get(id=account_id)

                    # Create statement with user-verified values
                    statement = BrokerageAccountStatement.objects.create(
                        investment=account,
                        statement_date=date.fromisoformat(request.POST.get('statement_date')),
                        period_start=date.fromisoformat(request.POST.get('period_start')) if request.POST.get('period_start') else None,
                        period_end=date.fromisoformat(request.POST.get('period_end')) if request.POST.get('period_end') else None,
                        beginning_value=Decimal(request.POST.get('beginning_value')),
                        ending_value=Decimal(request.POST.get('ending_value')),
                        deposits=Decimal(request.POST.get('deposits')),
                        withdrawals=Decimal(request.POST.get('withdrawals')),
                        dividends=Decimal(request.POST.get('dividends')),
                        interest=Decimal(request.POST.get('interest')),
                        capital_gains=Decimal(request.POST.get('capital_gains')),
                        market_change=Decimal(request.POST.get('market_change')),
                        fees=Decimal(request.POST.get('fees')),
                        other_activity=Decimal(request.POST.get('other_activity')),
                        # Account allocation (optional)
                        money_market=Decimal(request.POST.get('money_market')) if request.POST.get('money_market') else None,
                        equities=Decimal(request.POST.get('equities')) if request.POST.get('equities') else None,
                        fixed_income=Decimal(request.POST.get('fixed_income')) if request.POST.get('fixed_income') else None,
                        notes=f"Imported from PDF: {parsed_data.get('pdf_filename', 'unknown')}"
                    )

                    # Clear session data
                    del request.session['parsed_statement_data']
                    if 'validation_result' in request.session:
                        del request.session['validation_result']

                    messages.success(request, f'Statement created successfully for {statement.statement_date}')

                    # Redirect to the created statement
                    return redirect(f'/admin/investco/brokerageaccountstatement/{statement.id}/change/')

                except Exception as e:
                    messages.error(request, f'Error creating statement: {str(e)}')

            elif 'cancel_import' in request.POST:
                # Clear session data
                if 'parsed_statement_data' in request.session:
                    del request.session['parsed_statement_data']
                if 'validation_result' in request.session:
                    del request.session['validation_result']
                messages.info(request, 'Import cancelled')
                return redirect('/admin/investco/brokerageaccountstatement/')

        # GET request or after parsing - show form
        parsed_data = request.session.get('parsed_statement_data')
        validation = request.session.get('validation_result')
        accounts = BrokerageAccount.objects.all()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import Brokerage Statement from PDF',
            'parsed_data': parsed_data,
            'validation': validation,
            'accounts': accounts,
            'opts': self.model._meta,
            'statement_type': 'brokerage',
        }

        return render(request, 'admin/investco/import_pdf.html', context)

    def changelist_view(self, request, extra_context=None):
        """Add 'Import from PDF' button to changelist"""
        extra_context = extra_context or {}
        extra_context['show_import_pdf'] = True
        return super().changelist_view(request, extra_context)

    def reconciles_display(self, obj):
        if obj.reconciles is None:
            return '-'
        elif obj.reconciles:
            return '✓ Reconciles'
        else:
            # Check if we can calculate the difference
            if obj.calculated_change is not None and obj.ending_value is not None:
                return f'✗ Mismatch: ${abs(obj.calculated_change - obj.ending_value):,.2f}'
            else:
                return '✗ Incomplete data'
    reconciles_display.short_description = 'Reconciles'

    def chains_display(self, obj):
        return '✓' if obj.chains_with_previous else '✗'
    chains_display.short_description = 'Chains'

    def chains_with_previous_display(self, obj):
        prev_stmt = obj.investment.statements.filter(
            statement_date__lt=obj.statement_date
        ).order_by('-statement_date').first()

        if not prev_stmt:
            return 'No previous statement'

        # Get the actual polymorphic type
        prev_stmt = prev_stmt.get_real_instance()
        if not hasattr(prev_stmt, 'ending_value'):
            return 'Previous statement has no ending_value'

        if obj.chains_with_previous:
            return f'✓ Chains correctly with {prev_stmt.statement_date}'
        else:
            gap = obj.chain_gap
            if gap:
                return f'✗ Gap of ${gap:,.2f} from previous statement ({prev_stmt.statement_date}). ' \
                       f'Previous ending: ${prev_stmt.ending_value:,.2f}, This beginning: ${obj.beginning_value:,.2f}'
            return f'✗ Does not chain with {prev_stmt.statement_date}'
    chains_with_previous_display.short_description = 'Chains with Previous'


@admin.register(RetirementPlan)
class RetirementPlanAdmin(admin.ModelAdmin):
    list_display = ["investment", "expected_return", "continued_investment_amount", "continued_investment_frequency", "withdrawal_type"]
    list_filter = ["continued_investment_frequency", "withdrawal_type"]
    search_fields = ["investment__name", "investment__symbol"]

    fieldsets = (
        ("Investment", {
            "fields": ("investment",)
        }),
        ("Future Value Parameters (Pre-Retirement)", {
            "fields": ("expected_return", "continued_investment_amount", "continued_investment_frequency", "contribution_years"),
            "description": "Parameters for calculating future value at retirement. Leave contribution_years blank to contribute until retirement."
        }),
        ("Post-Retirement Income Parameters", {
            "fields": ("withdrawal_type", "withdrawal_percentage", "withdrawal_amount"),
            "description": "Parameters for calculating annual retirement income. For annuities with guaranteed withdrawal benefits, the GWB amount will be used automatically."
        }),
    )

