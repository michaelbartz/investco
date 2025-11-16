from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import (
    Portfolio, Investment, Transaction, InvestmentValue,
    Stock, Bond, ETF, MutualFund, Retirement401k, Annuity, BrokerageAccount,
    RealEstate, Cryptocurrency, OtherInvestment, Statement, AnnuityStatement,
    Retirement401kStatement, BrokerageAccountStatement
)
import json
from decimal import Decimal
from collections import defaultdict


def home(request):
    if not request.user.is_authenticated:
        return render(request, 'investco/home.html')
    
    portfolios = Portfolio.objects.filter(user=request.user)
    all_investments = Investment.objects.filter(portfolio__user=request.user)
    
    # Calculate totals
    total_value = sum(inv.current_value for inv in all_investments)
    total_cost = sum(inv.total_cost for inv in all_investments)
    total_gain_loss = total_value - total_cost
    gain_loss_percentage = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0
    
    # Investment type distribution for pie chart
    investment_types = {}
    for investment in all_investments:
        inv_type = investment.get_investment_type()
        if inv_type not in investment_types:
            investment_types[inv_type] = {'count': 0, 'value': Decimal('0')}
        investment_types[inv_type]['count'] += 1
        investment_types[inv_type]['value'] += investment.current_value
    
    # Prepare chart data
    chart_labels = list(investment_types.keys())
    chart_data = [float(data['value']) for data in investment_types.values()]
    
    context = {
        'portfolios': portfolios,
        'all_investments': all_investments,
        'total_value': total_value,
        'total_cost': total_cost,
        'total_gain_loss': total_gain_loss,
        'gain_loss_percentage': gain_loss_percentage,
        'investment_count': all_investments.count(),
        'portfolio_count': portfolios.count(),
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    
    return render(request, 'investco/home.html', context)


@login_required
def portfolio_list(request):
    portfolios = Portfolio.objects.filter(user=request.user)
    return render(request, 'investco/portfolio_list.html', {'portfolios': portfolios})


@login_required
def portfolio_detail(request, portfolio_id):
    portfolio = Portfolio.objects.get(id=portfolio_id, user=request.user)
    investments = Investment.objects.filter(portfolio=portfolio)

    # Calculate totals
    total_cost = sum(inv.total_cost for inv in investments)
    total_value = portfolio.total_value
    total_gain_loss = total_value - total_cost

    return render(request, 'investco/portfolio_detail.html', {
        'portfolio': portfolio,
        'investments': investments,
        'total_cost': total_cost,
        'total_value': total_value,
        'total_gain_loss': total_gain_loss,
    })


@login_required
def add_investment_value(request, investment_id):
    investment = get_object_or_404(Investment, id=investment_id, portfolio__user=request.user)

    if request.method == 'POST':
        price = request.POST.get('price')
        date = request.POST.get('date')
        volume = request.POST.get('volume') or None

        if price and date:
            InvestmentValue.objects.create(
                investment=investment,
                price=Decimal(price),
                date=date,
                volume=int(volume) if volume else None,
                source='manual'
            )
            # Update current price on investment
            investment.current_price = Decimal(price)
            investment.save()

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'})


# Performance Reporting Views

@login_required
def portfolio_performance(request, portfolio_id):
    """Portfolio Performance Report with charts and metrics"""
    portfolio = get_object_or_404(Portfolio, id=portfolio_id, user=request.user)
    investments = Investment.objects.filter(portfolio=portfolio)

    # Get time period from query params (default 30 days)
    days_param = request.GET.get('days', '30')

    if days_param == 'all':
        # All time: calculate from BEFORE earliest investment value
        # We add 1 day so the start_date is before the first transaction
        earliest_date = None
        for inv in investments:
            if isinstance(inv, Annuity):
                first_txn = inv.transactions.order_by('date').first()
                if first_txn and (not earliest_date or first_txn.date < earliest_date):
                    earliest_date = first_txn.date
            else:
                first_value = inv.historical_values.order_by('date').first()
                if first_value:
                    first_date = timezone.make_aware(
                        timezone.datetime.combine(first_value.date, timezone.datetime.min.time())
                    )
                    if not earliest_date or first_date < earliest_date:
                        earliest_date = first_date

        if earliest_date:
            days = (timezone.now() - earliest_date).days + 1  # +1 to go before first txn
        else:
            days = 30  # Default if no data
    else:
        days = int(days_param)

    # Calculate current totals
    total_cost = sum(inv.total_cost for inv in investments)
    total_value = portfolio.total_value
    total_gain_loss = total_value - total_cost
    gain_loss_percentage = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0

    # Get historical performance data
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    # Create regular sampling points (quarterly by default)
    from dateutil.relativedelta import relativedelta

    sample_dates = []
    current_sample = start_date
    while current_sample <= end_date:
        sample_dates.append(current_sample)
        current_sample += relativedelta(months=3)  # Quarterly

    # Ensure we include the end date
    if sample_dates[-1] < end_date:
        sample_dates.append(end_date)

    # For each investment, get its value at each sample point
    portfolio_values = []

    for sample_date in sample_dates:
        total_value_at_date = Decimal('0')

        for investment in investments:
            if isinstance(investment, (Annuity, Retirement401k)):
                # For statement-based investments, find the most recent statement on or before sample_date
                latest_statement = investment.statements.filter(
                    statement_date__lte=sample_date.date()
                ).order_by('-statement_date').first()

                if latest_statement:
                    actual_stmt = latest_statement.get_real_instance()
                    if hasattr(actual_stmt, 'ending_value'):
                        # Use the ending value from that statement (works for both Annuity and 401k)
                        total_value_at_date += actual_stmt.ending_value
                # else: no data yet for this investment at this date

            else:
                # Share-based investments: find most recent historical value
                latest_value = investment.historical_values.filter(
                    date__lte=sample_date
                ).order_by('-date').first()

                if latest_value:
                    # Check if this is a share-based investment
                    if hasattr(investment, 'shares'):
                        total_value_at_date += latest_value.price * investment.shares
                    else:
                        # For non-share investments (like real estate), price is total value
                        total_value_at_date += latest_value.price

        portfolio_values.append(total_value_at_date)

    # Prepare chart data
    chart_dates = [date.strftime('%Y-%m-%d') for date in sample_dates]
    chart_values = [float(value) for value in portfolio_values]

    # Calculate period metrics
    if chart_values and len(chart_values) >= 2:
        period_start_value = chart_values[0]
        period_end_value = chart_values[-1]
        total_return = ((period_end_value - period_start_value) / period_start_value) if period_start_value > 0 else 0
        period_return = total_return * 100

        # Annualize the return
        if days > 30:
            years = days / 365.0
            annualized_return = (((1 + total_return) ** (1 / years)) - 1) * 100
        else:
            annualized_return = period_return

        period_high = max(chart_values)
        period_low = min(chart_values)
    else:
        period_return = 0
        annualized_return = 0
        period_high = float(total_value)
        period_low = float(total_value)

    context = {
        'portfolio': portfolio,
        'investments': investments,
        'total_cost': total_cost,
        'total_value': total_value,
        'total_gain_loss': total_gain_loss,
        'gain_loss_percentage': gain_loss_percentage,
        'period_return': period_return,
        'annualized_return': annualized_return,
        'period_high': period_high,
        'period_low': period_low,
        'days': days_param if days_param == 'all' else days,
        'chart_dates': json.dumps(chart_dates),
        'chart_values': json.dumps(chart_values),
    }

    return render(request, 'investco/portfolio_performance.html', context)


@login_required
def investment_performance(request, investment_id):
    """Individual Investment Performance Report - Polymorphic for different investment types"""
    investment = get_object_or_404(Investment, id=investment_id, portfolio__user=request.user)

    # Handle custom date ranges or preset periods
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    days_param = request.GET.get('days', '365' if isinstance(investment, (Annuity, Retirement401k, BrokerageAccount)) else '30')

    if start_date_str and end_date_str:
        # Custom date range provided
        from datetime import datetime
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        start_date = timezone.make_aware(start_date)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date = timezone.make_aware(end_date)
        days = (end_date - start_date).days
        using_custom_range = True
    else:
        # Use preset period (days param)
        if days_param == 'all':
            # All time: calculate from BEFORE first transaction/value to now
            # We add 1 day so the start_date is before the first transaction
            if isinstance(investment, (Annuity, Retirement401k, BrokerageAccount)):
                first_txn = investment.transactions.order_by('date').first()
                if first_txn:
                    start_date = first_txn.date
                    days = (timezone.now() - start_date).days + 1  # +1 to go before first txn
                else:
                    days = 365  # Default if no transactions
            else:
                first_value = investment.historical_values.order_by('date').first()
                if first_value:
                    start_date = timezone.make_aware(
                        timezone.datetime.combine(first_value.date, timezone.datetime.min.time())
                    )
                    days = (timezone.now() - start_date).days + 1  # +1 to go before first value
                else:
                    days = 30  # Default if no values
        else:
            days = int(days_param)

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        using_custom_range = False

    # Get performance metrics
    metrics = investment.get_performance_metrics(days)

    # Get recent transactions
    recent_transactions = investment.transactions.all()[:10]

    # Base context for all investment types
    context = {
        'investment': investment,
        'metrics': metrics,
        'days': days_param if days_param == 'all' else days,
        'start_date': start_date,
        'end_date': end_date,
        'using_custom_range': using_custom_range,
        'recent_transactions': recent_transactions,
    }

    # Statement-based investments (Annuity, 401k, Brokerage): calculate total value over time from transactions
    if isinstance(investment, (Annuity, Retirement401k, BrokerageAccount)):
        # Get all transactions ordered by date
        all_transactions = investment.transactions.order_by('date')

        # Calculate cumulative value at each point, including starting balance
        transactions_with_values = []

        # Start with the initial balance from the earliest statement
        initial_balance = Decimal('0')
        earliest_statement = investment.statements.order_by('statement_date').first()
        if earliest_statement:
            # Use get_real_instance() to get the actual polymorphic type
            actual_statement = earliest_statement.get_real_instance()
            if isinstance(actual_statement, AnnuityStatement):
                initial_balance = actual_statement.beginning_value or Decimal('0')
            elif hasattr(actual_statement, 'beginning_value'):
                # For Retirement401kStatement or any other statement type with beginning_value
                initial_balance = actual_statement.beginning_value or Decimal('0')

        cumulative_value = initial_balance

        # First, calculate value up to the start of the period
        pre_period_txns = all_transactions.filter(date__lt=start_date)
        for txn in pre_period_txns:
            if txn.transaction_type == 'PREMIUM':
                cumulative_value += txn.amount or Decimal('0')
            elif txn.transaction_type == 'WITHDRAWAL':
                cumulative_value -= txn.amount or Decimal('0')
            elif txn.transaction_type == 'TAX_WITHHOLDING':
                cumulative_value -= txn.amount or Decimal('0')
            elif txn.transaction_type == 'NET_CHANGE':
                cumulative_value += txn.amount or Decimal('0')

        # Add starting point at beginning of period
        if cumulative_value > 0 or all_transactions.exists():
            transactions_with_values.append({
                'date': start_date,
                'value': cumulative_value
            })

        # Now process transactions within the period
        period_txns = all_transactions.filter(date__gte=start_date, date__lte=end_date)

        # Track the last date we added to avoid duplicates
        last_added_date = None

        for txn in period_txns:
            # Calculate running total based on transaction type
            if txn.transaction_type == 'PREMIUM':
                cumulative_value += txn.amount or Decimal('0')
            elif txn.transaction_type == 'WITHDRAWAL':
                cumulative_value -= txn.amount or Decimal('0')
            elif txn.transaction_type == 'TAX_WITHHOLDING':
                cumulative_value -= txn.amount or Decimal('0')
            elif txn.transaction_type == 'NET_CHANGE':
                cumulative_value += txn.amount or Decimal('0')

            # Only add one data point per date (use the final value for that date)
            txn_date = txn.date.date()
            if last_added_date != txn_date:
                # If there's a previous entry for the same date, update it instead of adding new
                if transactions_with_values and transactions_with_values[-1]['date'].date() == txn_date:
                    transactions_with_values[-1]['value'] = cumulative_value
                else:
                    transactions_with_values.append({
                        'date': txn.date,
                        'value': cumulative_value
                    })
                    last_added_date = txn_date
            else:
                # Update the last entry with the new cumulative value
                transactions_with_values[-1]['value'] = cumulative_value

        # Prepare chart data for annuity (total value over time)
        chart_dates = [tv['date'].strftime('%Y-%m-%d') for tv in transactions_with_values]
        chart_values = [float(tv['value']) for tv in transactions_with_values]

        # Get GWB (Guaranteed Withdrawal Balance) data from statements (Annuity only)
        gwb_data = []

        if isinstance(investment, Annuity):
            # First, get the GWB value from the last statement before the period (if any)
            # This gives us a starting point for the GWB line
            last_stmt_before_period = investment.statements.filter(
                statement_date__lt=start_date
            ).order_by('-statement_date').first()

            if last_stmt_before_period:
                actual_stmt = last_stmt_before_period.get_real_instance()
                if isinstance(actual_stmt, AnnuityStatement) and actual_stmt.remaining_guaranteed_balance:
                    gwb_data.append({
                        'date': start_date.strftime('%Y-%m-%d'),
                        'value': float(actual_stmt.remaining_guaranteed_balance)
                    })

            # Now get all statements within the period
            statements = investment.statements.filter(
                statement_date__gte=start_date,
                statement_date__lte=end_date
            ).order_by('statement_date')

            for stmt in statements:
                actual_stmt = stmt.get_real_instance()
                if isinstance(actual_stmt, AnnuityStatement) and actual_stmt.remaining_guaranteed_balance:
                    gwb_data.append({
                        'date': stmt.statement_date.strftime('%Y-%m-%d'),
                        'value': float(actual_stmt.remaining_guaranteed_balance)
                    })

        # Prepare GWB chart data
        gwb_dates = [gd['date'] for gd in gwb_data]
        gwb_values = [gd['value'] for gd in gwb_data]

        # Get performance breakdown for annuities only
        breakdown = None
        if isinstance(investment, Annuity):
            breakdown = investment.get_performance_breakdown()

        context.update({
            'chart_dates': json.dumps(chart_dates),
            'chart_values': json.dumps(chart_values),
            'gwb_dates': json.dumps(gwb_dates),
            'gwb_values': json.dumps(gwb_values),
            'has_gwb_data': len(gwb_data) > 0,
            'is_annuity': isinstance(investment, Annuity),
            'is_401k': isinstance(investment, Retirement401k),
            'is_brokerage': isinstance(investment, BrokerageAccount),
            'has_statements': True,
            'breakdown': breakdown,
        })
    else:
        # Share-based investments: use historical price data
        historical_values = investment.get_historical_values(days)

        # Prepare chart data (price per share)
        chart_dates = [v.date.strftime('%Y-%m-%d') for v in historical_values]
        chart_prices = [float(v.price) for v in historical_values]

        context.update({
            'chart_dates': json.dumps(chart_dates),
            'chart_prices': json.dumps(chart_prices),
            'is_annuity': False,
            'is_401k': False,
            'is_brokerage': False,
            'has_statements': False,
        })

    return render(request, 'investco/investment_performance.html', context)


@login_required
def comparative_performance(request):
    """Comparative Performance Report for multiple investments or portfolios"""
    user_portfolios = Portfolio.objects.filter(user=request.user)
    all_investments = Investment.objects.filter(portfolio__user=request.user)

    # Get selected investments/portfolios from query params
    selected_investment_ids = request.GET.getlist('investments')
    selected_portfolio_ids = request.GET.getlist('portfolios')
    days = int(request.GET.get('days', 30))

    comparison_data = []

    # Compare selected investments
    if selected_investment_ids:
        for inv_id in selected_investment_ids:
            try:
                investment = Investment.objects.get(id=inv_id, portfolio__user=request.user)
                metrics = investment.get_performance_metrics(days)
                comparison_data.append({
                    'name': investment.symbol or investment.name,
                    'type': 'Investment',
                    'current_value': investment.current_value,
                    'gain_loss': investment.gain_loss,
                    'gain_loss_percentage': investment.gain_loss_percentage,
                    'metrics': metrics,
                })
            except Investment.DoesNotExist:
                pass

    # Compare selected portfolios
    if selected_portfolio_ids:
        for port_id in selected_portfolio_ids:
            try:
                portfolio = Portfolio.objects.get(id=port_id, user=request.user)
                investments = Investment.objects.filter(portfolio=portfolio)
                total_cost = sum(inv.total_cost for inv in investments)
                total_value = portfolio.total_value
                total_gain_loss = total_value - total_cost
                gain_loss_percentage = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0

                comparison_data.append({
                    'name': portfolio.name,
                    'type': 'Portfolio',
                    'current_value': total_value,
                    'gain_loss': total_gain_loss,
                    'gain_loss_percentage': gain_loss_percentage,
                    'metrics': None,
                })
            except Portfolio.DoesNotExist:
                pass

    context = {
        'comparison_data': comparison_data,
        'all_investments': all_investments,
        'user_portfolios': user_portfolios,
        'selected_investment_ids': [int(i) for i in selected_investment_ids],
        'selected_portfolio_ids': [int(i) for i in selected_portfolio_ids],
        'days': days,
    }

    return render(request, 'investco/comparative_performance.html', context)


@login_required
def time_period_report(request, portfolio_id):
    """Performance report across multiple time periods"""
    portfolio = get_object_or_404(Portfolio, id=portfolio_id, user=request.user)
    investments = Investment.objects.filter(portfolio=portfolio)

    # Calculate totals
    total_cost = sum(inv.total_cost for inv in investments)
    total_value = portfolio.total_value
    total_gain_loss = total_value - total_cost

    # Define time periods
    periods = {
        '7d': 7,
        '30d': 30,
        '90d': 90,
        '1y': 365,
        'ytd': (timezone.now() - timezone.now().replace(month=1, day=1)).days,
    }

    period_performance = {}
    for period_name, days in periods.items():
        # Get historical values for this period
        start_date = timezone.now() - timedelta(days=days)

        period_start_value = Decimal('0')
        period_end_value = Decimal('0')

        for investment in investments:
            # Skip annuities - they use transaction-based valuation
            if isinstance(investment, Annuity):
                # For annuities, calculate value from transactions
                start_breakdown = investment.get_performance_breakdown(as_of_date=start_date)
                end_breakdown = investment.get_performance_breakdown(as_of_date=timezone.now())
                period_start_value += start_breakdown['current_value']
                period_end_value += end_breakdown['current_value']
                continue

            # Get first and last values in period
            period_values = investment.historical_values.filter(
                date__gte=start_date
            ).order_by('date')

            if period_values.exists():
                first_value = period_values.first()
                last_value = period_values.last()

                # Use shares if available (share-based investments)
                if hasattr(investment, 'shares'):
                    period_start_value += first_value.price * investment.shares
                    period_end_value += last_value.price * investment.shares
                else:
                    # For non-share investments, price is total value
                    period_start_value += first_value.price
                    period_end_value += last_value.price

        if period_start_value > 0:
            total_return = ((period_end_value - period_start_value) / period_start_value)
            period_return = total_return * 100
            period_gain = period_end_value - period_start_value

            # Annualize the return
            if days > 30:
                years = days / 365.0
                # Convert Decimal to float for power operations
                annualized_return = (((1 + float(total_return)) ** (1 / years)) - 1) * 100
            else:
                annualized_return = period_return
        else:
            period_return = 0
            annualized_return = 0
            period_gain = 0

        period_performance[period_name] = {
            'days': days,
            'return': period_return,
            'annualized_return': annualized_return,
            'gain': period_gain,
            'start_value': period_start_value,
            'end_value': period_end_value,
        }

    context = {
        'portfolio': portfolio,
        'investments': investments,
        'total_cost': total_cost,
        'total_value': total_value,
        'total_gain_loss': total_gain_loss,
        'period_performance': period_performance,
    }

    return render(request, 'investco/time_period_report.html', context)


@login_required
def asset_allocation_report(request, portfolio_id):
    """Asset allocation report with breakdown by investment type"""
    portfolio = get_object_or_404(Portfolio, id=portfolio_id, user=request.user)
    investments = Investment.objects.filter(portfolio=portfolio)

    # Calculate totals
    total_cost = sum(inv.total_cost for inv in investments)
    total_value = portfolio.total_value
    total_gain_loss = total_value - total_cost

    # Group by investment type
    allocation = defaultdict(lambda: {
        'count': 0,
        'total_value': Decimal('0'),
        'total_cost': Decimal('0'),
        'gain_loss': Decimal('0'),
        'investments': []
    })

    for investment in investments:
        inv_type = investment.get_investment_type()
        allocation[inv_type]['count'] += 1
        allocation[inv_type]['total_value'] += investment.current_value
        allocation[inv_type]['total_cost'] += investment.total_cost
        allocation[inv_type]['gain_loss'] += investment.gain_loss
        allocation[inv_type]['investments'].append(investment)

    # Calculate percentages and performance
    for inv_type in allocation:
        allocation[inv_type]['percentage'] = (
            (allocation[inv_type]['total_value'] / total_value * 100) if total_value > 0 else 0
        )
        allocation[inv_type]['gain_loss_percentage'] = (
            (allocation[inv_type]['gain_loss'] / allocation[inv_type]['total_cost'] * 100)
            if allocation[inv_type]['total_cost'] > 0 else 0
        )

    # Prepare chart data
    chart_labels = list(allocation.keys())
    chart_data = [float(allocation[label]['total_value']) for label in chart_labels]

    context = {
        'portfolio': portfolio,
        'total_cost': total_cost,
        'total_value': total_value,
        'total_gain_loss': total_gain_loss,
        'allocation': dict(allocation),
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }

    return render(request, 'investco/asset_allocation_report.html', context)


# Statement Views

@login_required
def investment_statements(request, investment_id):
    """List all statements for an investment"""
    investment = get_object_or_404(Investment, id=investment_id, portfolio__user=request.user)

    # Get all statements for this investment
    statements = Statement.objects.filter(investment=investment).order_by('-statement_date')

    context = {
        'investment': investment,
        'statements': statements,
    }

    return render(request, 'investco/investment_statements.html', context)


@login_required
def statement_detail(request, statement_id):
    """View detailed information about a statement"""
    statement = get_object_or_404(Statement, id=statement_id, investment__portfolio__user=request.user)

    # Get the actual polymorphic instance
    actual_statement = statement.get_real_instance()

    # Get transactions generated by this statement
    transactions = statement.generated_transactions.all().order_by('transaction_type')

    context = {
        'statement': actual_statement,
        'transactions': transactions,
        'investment': statement.investment,
    }

    # Use polymorphic template based on statement type
    if isinstance(actual_statement, AnnuityStatement):
        return render(request, 'investco/annuity_statement_detail.html', context)
    elif isinstance(actual_statement, Retirement401kStatement):
        return render(request, 'investco/retirement401k_statement_detail.html', context)
    else:
        return render(request, 'investco/statement_detail.html', context)

@login_required
def retirement_planner(request, portfolio_id):
    """Portfolio-level retirement planner with projections for all investments"""
    from datetime import date
    from decimal import Decimal
    from .models import RetirementPlan
    
    portfolio = get_object_or_404(Portfolio, id=portfolio_id, user=request.user)
    investments = portfolio.investments.all()
    
    # Calculate years until retirement
    years_to_retirement = None
    if portfolio.retirement_date:
        today = date.today()
        delta = portfolio.retirement_date - today
        years_to_retirement = delta.days / 365.25
    
    # Calculate projections for each investment
    investment_projections = []
    total_current_value = Decimal('0')
    total_projected_value = Decimal('0')
    total_annual_income = Decimal('0')
    
    for investment in investments:
        current_value = investment.current_value
        total_current_value += current_value
        
        # Get or create retirement plan with defaults
        try:
            plan = investment.retirement_plan
        except RetirementPlan.DoesNotExist:
            plan = None
        
        if plan and years_to_retirement and years_to_retirement > 0:
            projected_value = plan.calculate_future_value(years_to_retirement)
            annual_income = plan.calculate_annual_income(projected_value)
        else:
            projected_value = current_value
            annual_income = Decimal('0')
        
        total_projected_value += projected_value
        total_annual_income += annual_income
        
        investment_projections.append({
            'investment': investment,
            'current_value': current_value,
            'projected_value': projected_value,
            'projected_gain': projected_value - current_value,
            'annual_income': annual_income,
            'has_plan': plan is not None,
        })
    
    context = {
        'portfolio': portfolio,
        'years_to_retirement': years_to_retirement,
        'investment_projections': investment_projections,
        'total_current_value': total_current_value,
        'total_projected_value': total_projected_value,
        'total_projected_gain': total_projected_value - total_current_value,
        'total_annual_income': total_annual_income,
        'total_monthly_income': total_annual_income / 12,
    }

    return render(request, 'investco/retirement_planner.html', context)


@login_required
def investment_retirement_plan(request, investment_id):
    """Investment-level retirement planning with editable parameters"""
    from datetime import date
    from decimal import Decimal
    from .models import RetirementPlan
    
    investment = get_object_or_404(Investment, id=investment_id, portfolio__user=request.user)
    portfolio = investment.portfolio
    
    # Get or create retirement plan
    plan, created = RetirementPlan.objects.get_or_create(investment=investment)
    
    if request.method == 'POST':
        # Update retirement plan parameters
        plan.expected_return = Decimal(request.POST.get('expected_return', '7.0'))
        plan.continued_investment_amount = Decimal(request.POST.get('continued_investment_amount', '0'))
        plan.continued_investment_frequency = request.POST.get('continued_investment_frequency', 'MONTHLY')

        # Handle contribution years (optional field)
        contribution_years_str = request.POST.get('contribution_years', '')
        plan.contribution_years = Decimal(contribution_years_str) if contribution_years_str else None

        plan.withdrawal_type = request.POST.get('withdrawal_type', 'PERCENTAGE')
        plan.withdrawal_percentage = Decimal(request.POST.get('withdrawal_percentage', '4.0'))
        plan.withdrawal_amount = Decimal(request.POST.get('withdrawal_amount', '0'))
        plan.save()

        messages.success(request, 'Retirement plan updated successfully!')
        return redirect('investco:investment_retirement_plan', investment_id=investment.id)
    
    # Calculate years until retirement
    years_to_retirement = None
    retirement_date = portfolio.retirement_date
    if retirement_date:
        today = date.today()
        delta = retirement_date - today
        years_to_retirement = delta.days / 365.25
    
    # Calculate projections
    current_value = investment.current_value
    projected_value = None
    annual_income = None
    
    if years_to_retirement and years_to_retirement > 0:
        projected_value = plan.calculate_future_value(years_to_retirement)
        annual_income = plan.calculate_annual_income(projected_value)
    
    # Check if this is an annuity with GWB
    has_gwb = False
    gwb_amount = None
    actual_investment = investment.get_real_instance()
    if actual_investment.__class__.__name__ == 'Annuity':
        latest_statement = investment.statements.filter(
            annuitystatement__guaranteed_withdrawal_amount_annually__isnull=False
        ).order_by('-statement_date').first()
        if latest_statement and hasattr(latest_statement, 'annuitystatement'):
            gwb_amount = latest_statement.annuitystatement.guaranteed_withdrawal_amount_annually
            if gwb_amount:
                has_gwb = True
    
    context = {
        'investment': investment,
        'portfolio': portfolio,
        'plan': plan,
        'years_to_retirement': years_to_retirement,
        'retirement_date': retirement_date,
        'current_value': current_value,
        'projected_value': projected_value,
        'projected_gain': projected_value - current_value if projected_value else None,
        'annual_income': annual_income,
        'has_gwb': has_gwb,
        'gwb_amount': gwb_amount,
    }
    
    return render(request, 'investco/investment_retirement_plan.html', context)
