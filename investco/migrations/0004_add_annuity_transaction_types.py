from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investco', '0003_annuity_issue_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('BUY', 'Buy'),
                    ('SELL', 'Sell'),
                    ('DIVIDEND', 'Dividend'),
                    ('SPLIT', 'Stock Split'),
                    ('PREMIUM', 'Premium Payment'),
                    ('WITHDRAWAL', 'Withdrawal'),
                    ('TAX_WITHHOLDING', 'Tax Withholding'),
                    ('NET_CHANGE', 'Net Investment Change'),
                ]
            ),
        ),
    ]
