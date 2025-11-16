"""
PDF Parser for Investment Statements

Extracts key financial data from investment statements.
Supports multiple formats:
- Jackson annuity statements
- TIAA annuity statements
- Valic/Corebridge Financial annuity statements
- John Hancock 401k statements
- M Holdings brokerage statements
"""

import re
from decimal import Decimal
from datetime import datetime
import pdfplumber


class AnnuityStatementParser:
    """Parser for Jackson annuity quarterly statements."""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.data = {}

    def parse(self):
        """
        Parse the PDF and extract statement data.

        Returns:
            dict: Extracted statement data with keys:
                - statement_date: date
                - beginning_value: Decimal
                - ending_value: Decimal
                - premiums: Decimal
                - withdrawals: Decimal
                - tax_withholding: Decimal
                - net_change: Decimal
                - remaining_guaranteed_balance: Decimal
                - death_benefit: Decimal
        """
        text = None

        # Try method 1: pdfplumber
        with pdfplumber.open(self.pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()

        # Try method 2: PyPDF2
        if not text or len(text.strip()) < 100:
            from PyPDF2 import PdfReader
            reader = PdfReader(self.pdf_path)
            text = reader.pages[0].extract_text()

        # Try method 3: OCR (for image-based PDFs)
        if not text or len(text.strip()) < 100:
            text = self._extract_text_with_ocr()

        if not text or len(text.strip()) < 100:
            raise ValueError(
                "Unable to extract text from PDF using any method. "
                "Please check the PDF file or use manual entry."
            )

        # Parse contract info
        self._parse_contract_info(text)

        # Parse period dates
        self._parse_period_dates(text)

        # Parse contract summary values
        self._parse_contract_summary(text)

        # Parse benefit values
        self._parse_benefit_values(text)

        return self.data

    def _extract_text_with_ocr(self):
        """
        Extract text from image-based PDF using OCR.

        Returns:
            str: Extracted text from PDF
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract

            # Convert first page of PDF to image
            images = convert_from_path(self.pdf_path, first_page=1, last_page=1)

            if not images:
                return ""

            # Perform OCR on the image
            text = pytesseract.image_to_string(images[0])

            return text

        except Exception as e:
            # OCR failed, return empty string
            print(f"OCR extraction failed: {e}")
            return ""

    def _parse_period_dates(self, text):
        """Extract statement period dates."""
        # Look for "For the period of July 1, 2024 to September 30, 2024"
        period_match = re.search(r'For the period of (\w+ \d+, \d{4}) to (\w+ \d+, \d{4})', text, re.IGNORECASE)
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            self.data['period_start'] = datetime.strptime(start_str, '%B %d, %Y').date()
            self.data['period_end'] = datetime.strptime(end_str, '%B %d, %Y').date()
            self.data['statement_date'] = self.data['period_end']  # Statement date = period end

        # Alternative: Look for "Ending Value on MM/DD/YYYY"
        if 'statement_date' not in self.data:
            ending_date_match = re.search(r'Ending.Value.on.(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if ending_date_match:
                date_str = ending_date_match.group(1)
                self.data['statement_date'] = datetime.strptime(date_str, '%m/%d/%Y').date()
                self.data['period_end'] = self.data['statement_date']

        # Try to find beginning date for period_start
        if 'period_start' not in self.data:
            beginning_date_match = re.search(r'Beginning.Value.on.(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if beginning_date_match:
                date_str = beginning_date_match.group(1)
                self.data['period_start'] = datetime.strptime(date_str, '%m/%d/%Y').date()

    def _parse_contract_info(self, text):
        """Extract contract/policy information."""
        # Look for Contract Number or Policy Number
        contract_match = re.search(r'Contract\s+Number[:\s]+(\d+)', text, re.IGNORECASE)
        if contract_match:
            self.data['policy_number'] = contract_match.group(1)
        else:
            # Try alternative pattern
            policy_match = re.search(r'Policy\s+Number[:\s]+(\d+)', text, re.IGNORECASE)
            if policy_match:
                self.data['policy_number'] = policy_match.group(1)

    def _parse_contract_summary(self, text):
        """Extract values from Contract Summary section."""
        # Look for "This Quarter" column values
        # Pattern: "Beginning Value on MM/DD/YYYY" followed by dollar amount

        # Beginning Value - handle OCR variations
        beginning_match = re.search(r'Beginning\s+Value\s+on\s+\d{2}/\d{2}/\d{4}\s+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if beginning_match:
            self.data['beginning_value'] = self._parse_currency(beginning_match.group(1))

        # Ending Value - handle OCR variations and multiple patterns
        # OCR may misread spaces as apostrophes or other characters, so use . to match any single character
        ending_match = re.search(r'Ending.Value.on.\d{2}/\d{2}/\d{4}.\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if ending_match:
            self.data['ending_value'] = self._parse_currency(ending_match.group(1))
        else:
            # Alternative: look for "Ending Value" followed by amount (different line structure)
            ending_match2 = re.search(r'Ending\s+Value[^$\d]*\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
            if ending_match2:
                self.data['ending_value'] = self._parse_currency(ending_match2.group(1))

        # Total Premium (in Contract Summary section)
        premium_match = re.search(r'Total\s+Premium\s+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if premium_match:
            self.data['premiums'] = self._parse_currency(premium_match.group(1))

        # Total Withdrawals
        withdrawal_match = re.search(r'Total\s+Withdrawals\s+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if withdrawal_match:
            self.data['withdrawals'] = self._parse_currency(withdrawal_match.group(1))

        # Total Tax Withheld
        tax_match = re.search(r'Total\s+Tax\s+With[ht]eld\s+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if tax_match:
            self.data['tax_withholding'] = self._parse_currency(tax_match.group(1))

        # Net Change (can be negative with parentheses)
        # First try to match positive value
        net_change_match = re.search(r'Net\s+Change\s+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if net_change_match:
            self.data['net_change'] = self._parse_currency(net_change_match.group(1))
        else:
            # Try to match negative value with parentheses: ($1,234.56)
            net_change_negative = re.search(r'Net\s+Change\s+\(\$?([\d,]+\.\d{2})\)', text, re.IGNORECASE)
            if net_change_negative:
                value = self._parse_currency(net_change_negative.group(1))
                self.data['net_change'] = -value  # Make it negative

    def _parse_benefit_values(self, text):
        """Extract values from Benefit Values section."""
        # Remaining Guaranteed Withdrawal Balance
        gwb_match = re.search(r'Remaining\s+Guaranteed\s+Withdrawal\s+Balance[:\s]+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if gwb_match:
            self.data['remaining_guaranteed_balance'] = self._parse_currency(gwb_match.group(1))

        # Death Benefit Value
        death_benefit_match = re.search(r'Death\s+Benefit\s+Value[:\s]+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if death_benefit_match:
            self.data['death_benefit'] = self._parse_currency(death_benefit_match.group(1))

        # Earnings Determination Baseline
        earnings_baseline_match = re.search(r'Earnings\s+Determination\s+Baseline[:\s]+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if earnings_baseline_match:
            self.data['earnings_determination_baseline'] = self._parse_currency(earnings_baseline_match.group(1))

        # Guaranteed Withdrawal Balance Bonus Base
        gwb_bonus_match = re.search(r'Guaranteed\s+Withdrawal\s+Balance\s+Bonus\s+Base[:\s]+\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
        if gwb_bonus_match:
            self.data['guaranteed_withdrawal_balance_bonus_baseline'] = self._parse_currency(gwb_bonus_match.group(1))

    def _parse_currency(self, value_str):
        """
        Convert currency string to Decimal.

        Args:
            value_str: String like "254,888.45" or "$254,888.45"

        Returns:
            Decimal value
        """
        # Remove dollar signs and commas
        cleaned = value_str.replace('$', '').replace(',', '')
        return Decimal(cleaned)

    def validate(self):
        """
        Validate parsed data and return any errors or warnings.

        Returns:
            dict: Contains 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []

        # Check required fields
        required_fields = [
            'statement_date', 'period_start', 'period_end',
            'beginning_value', 'ending_value',
            'premiums', 'withdrawals', 'tax_withholding', 'net_change'
        ]

        for field in required_fields:
            if field not in self.data:
                errors.append(f"Missing required field: {field}")

        # Validate reconciliation if all fields present
        if not errors:
            expected_ending = (
                self.data['beginning_value'] +
                self.data['premiums'] +
                self.data['net_change'] -
                self.data['withdrawals'] -
                self.data['tax_withholding']
            )

            difference = abs(self.data['ending_value'] - expected_ending)

            # Allow for small rounding differences (up to $1)
            if difference > Decimal('1.00'):
                warnings.append(
                    f"Reconciliation mismatch: Expected ending ${expected_ending}, "
                    f"but PDF shows ${self.data['ending_value']} "
                    f"(difference: ${difference})"
                )

        return {
            'errors': errors,
            'warnings': warnings
        }


class TIAAStatementParser:
    """Parser for TIAA annuity quarterly statements."""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.data = {}

    def parse(self):
        """
        Parse the PDF and extract statement data.

        Returns:
            dict: Extracted statement data
        """
        text = None

        # For TIAA statements, try OCR first as they often have balance data in images/tables
        text_ocr = self._extract_text_with_ocr()

        # Also get regular text extraction for other fields
        with pdfplumber.open(self.pdf_path) as pdf:
            first_page = pdf.pages[0]
            text_regular = first_page.extract_text()

        # Try method 2: PyPDF2
        if not text_regular or len(text_regular.strip()) < 100:
            from PyPDF2 import PdfReader
            reader = PdfReader(self.pdf_path)
            text_regular = reader.pages[0].extract_text()

        # Combine both texts for parsing
        text = text_ocr + '\n' + (text_regular or '')

        if not text or len(text.strip()) < 100:
            raise ValueError(
                "Unable to extract text from PDF using any method. "
                "Please check the PDF file or use manual entry."
            )

        # Parse TIAA statement sections
        self._parse_contract_info(text)
        self._parse_period_dates(text)
        self._parse_account_values(text)

        return self.data

    def _extract_text_with_ocr(self):
        """Extract text from image-based PDF using OCR."""
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(self.pdf_path, first_page=1, last_page=1)
            if not images:
                return ""

            text = pytesseract.image_to_string(images[0])
            return text

        except Exception as e:
            print(f"OCR extraction failed: {e}")
            return ""

    def _parse_period_dates(self, text):
        """Extract statement period dates."""
        # Look for "July 1, 2025 to September 30, 2025" or "July 1, 2025 - September 30, 2025"
        # Also handle "FOR July 1, 2025 TO September 30, 2025" (case-insensitive)
        period_match = re.search(r'(?:FOR\s+)?(\w+ \d+, \d{4})\s+(?:to|TO)\s+(\w+ \d+, \d{4})', text, re.IGNORECASE)
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            self.data['period_start'] = datetime.strptime(start_str, '%B %d, %Y').date()
            self.data['period_end'] = datetime.strptime(end_str, '%B %d, %Y').date()
            self.data['statement_date'] = self.data['period_end']

    def _parse_contract_info(self, text):
        """Extract contract/policy information from TIAA statement."""
        # Look for TIAA contract numbers (format: C167959-0 or U167959-8)
        contract_matches = re.findall(r'([CU]\d{6}-\d)', text)
        if contract_matches:
            # Store first contract number as policy number
            self.data['policy_number'] = contract_matches[0]

    def _parse_account_values(self, text):
        """Extract account values from TIAA statement."""
        # Beginning balance
        beginning_match = re.search(r'Beginning\s+balance\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if beginning_match:
            self.data['beginning_value'] = self._parse_currency(beginning_match.group(1))

        # Ending balance - first occurrence (there are multiple in the statement)
        ending_match = re.search(r'Ending\s+balance\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if ending_match:
            self.data['ending_value'] = self._parse_currency(ending_match.group(1))

        # Other Credits (map to premiums)
        credits_match = re.search(r'Other\s+Credits\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if credits_match:
            self.data['premiums'] = self._parse_currency(credits_match.group(1))
        else:
            self.data['premiums'] = Decimal('0')

        # TIAA doesn't have withdrawals in this statement, default to 0
        self.data['withdrawals'] = Decimal('0')
        self.data['tax_withholding'] = Decimal('0')

        # Calculate net_change from Gains/Loss + TIAA Interest
        gains_loss_match = re.search(r'Gains/Loss\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        tiaa_interest_match = re.search(r'TIAA\s+Interest\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)

        net_change = Decimal('0')
        if gains_loss_match:
            net_change += self._parse_currency(gains_loss_match.group(1))
        if tiaa_interest_match:
            net_change += self._parse_currency(tiaa_interest_match.group(1))

        # Check if Gains/Loss should be negative (parentheses notation)
        if re.search(r'Gains/Loss\s+\(\$\s*[\d,]+\.\d{2}\)', text, re.IGNORECASE):
            gains_loss_negative = re.search(r'Gains/Loss\s+\(\$\s*([\d,]+\.\d{2})\)', text, re.IGNORECASE)
            if gains_loss_negative:
                net_change = -self._parse_currency(gains_loss_negative.group(1))
                if tiaa_interest_match:
                    net_change += self._parse_currency(tiaa_interest_match.group(1))

        self.data['net_change'] = net_change

    def _parse_currency(self, value_str):
        """Convert currency string to Decimal."""
        cleaned = value_str.replace('$', '').replace(',', '')
        return Decimal(cleaned)

    def validate(self):
        """Validate parsed data and return any errors or warnings."""
        errors = []
        warnings = []

        # Check required fields
        required_fields = [
            'statement_date', 'period_start', 'period_end',
            'beginning_value', 'ending_value',
            'premiums', 'withdrawals', 'tax_withholding', 'net_change'
        ]

        for field in required_fields:
            if field not in self.data:
                errors.append(f"Missing required field: {field}")

        # Validate reconciliation if all fields present
        if not errors:
            expected_ending = (
                self.data['beginning_value'] +
                self.data['premiums'] +
                self.data['net_change'] -
                self.data['withdrawals'] -
                self.data['tax_withholding']
            )

            difference = abs(self.data['ending_value'] - expected_ending)

            # Allow for small rounding differences (up to $1)
            if difference > Decimal('1.00'):
                warnings.append(
                    f"Reconciliation mismatch: Expected ending ${expected_ending}, "
                    f"but PDF shows ${self.data['ending_value']} "
                    f"(difference: ${difference})"
                )

        return {
            'errors': errors,
            'warnings': warnings
        }


class ValicStatementParser:
    """Parser for Valic/Corebridge Financial annuity quarterly statements."""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.data = {}

    def parse(self):
        """
        Parse the PDF and extract statement data.

        Returns:
            dict: Extracted statement data
        """
        text = None

        # Try pdfplumber first
        with pdfplumber.open(self.pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()

        # Try PyPDF2 if needed
        if not text or len(text.strip()) < 100:
            from PyPDF2 import PdfReader
            reader = PdfReader(self.pdf_path)
            text = reader.pages[0].extract_text()

        # Try OCR if still insufficient
        if not text or len(text.strip()) < 100:
            text = self._extract_text_with_ocr()

        if not text or len(text.strip()) < 100:
            raise ValueError(
                "Unable to extract text from PDF using any method. "
                "Please check the PDF file or use manual entry."
            )

        # Parse Valic statement sections
        self._parse_account_info(text)
        self._parse_period_dates(text)
        self._parse_value_summary(text)

        return self.data

    def _extract_text_with_ocr(self):
        """Extract text from image-based PDF using OCR."""
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(self.pdf_path, first_page=1, last_page=1)
            if not images:
                return ""

            text = pytesseract.image_to_string(images[0])
            return text

        except Exception as e:
            print(f"OCR extraction failed: {e}")
            return ""

    def _parse_period_dates(self, text):
        """Extract statement period dates."""
        # Look for "July 01, 2025 - September 30, 2025"
        period_match = re.search(r'(\w+ \d{2}, \d{4})\s*-\s*(\w+ \d{2}, \d{4})', text, re.IGNORECASE)
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            self.data['period_start'] = datetime.strptime(start_str, '%B %d, %Y').date()
            self.data['period_end'] = datetime.strptime(end_str, '%B %d, %Y').date()
            self.data['statement_date'] = self.data['period_end']

    def _parse_account_info(self, text):
        """Extract account/policy information from Valic statement."""
        # Look for Account Number
        account_match = re.search(r'Account\s+Number:\s*(\d+)', text, re.IGNORECASE)
        if account_match:
            self.data['policy_number'] = account_match.group(1)

    def _parse_value_summary(self, text):
        """Extract account values from Value Summary section."""
        # Beginning Value
        beginning_match = re.search(r'Beginning\s+Value\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if beginning_match:
            self.data['beginning_value'] = self._parse_currency(beginning_match.group(1))

        # Ending Value
        ending_match = re.search(r'Ending\s+Value\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if ending_match:
            self.data['ending_value'] = self._parse_currency(ending_match.group(1))

        # Employer contributions (map to premiums)
        contributions_match = re.search(r'Employer\s+contributions\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if contributions_match:
            self.data['premiums'] = self._parse_currency(contributions_match.group(1))
        else:
            self.data['premiums'] = Decimal('0')

        # Net change in value
        net_change_match = re.search(r'Net\s+change\s+in\s+value\s+\$\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if net_change_match:
            self.data['net_change'] = self._parse_currency(net_change_match.group(1))
        else:
            # Try with negative (parentheses notation)
            net_change_negative = re.search(r'Net\s+change\s+in\s+value\s+\(\$\s*([\d,]+\.\d{2})\)', text, re.IGNORECASE)
            if net_change_negative:
                self.data['net_change'] = -self._parse_currency(net_change_negative.group(1))

        # Valic doesn't have withdrawals or tax withholding in this format
        self.data['withdrawals'] = Decimal('0')
        self.data['tax_withholding'] = Decimal('0')

    def _parse_currency(self, value_str):
        """Convert currency string to Decimal."""
        cleaned = value_str.replace('$', '').replace(',', '')
        return Decimal(cleaned)

    def validate(self):
        """Validate parsed data and return any errors or warnings."""
        errors = []
        warnings = []

        # Check required fields
        required_fields = [
            'statement_date', 'period_start', 'period_end',
            'beginning_value', 'ending_value',
            'premiums', 'withdrawals', 'tax_withholding', 'net_change'
        ]

        for field in required_fields:
            if field not in self.data:
                errors.append(f"Missing required field: {field}")

        # Validate reconciliation if all fields present
        if not errors:
            expected_ending = (
                self.data['beginning_value'] +
                self.data['premiums'] +
                self.data['net_change'] -
                self.data['withdrawals'] -
                self.data['tax_withholding']
            )

            difference = abs(self.data['ending_value'] - expected_ending)

            # Allow for small rounding differences (up to $1)
            if difference > Decimal('1.00'):
                warnings.append(
                    f"Reconciliation mismatch: Expected ending ${expected_ending}, "
                    f"but PDF shows ${self.data['ending_value']} "
                    f"(difference: ${difference})"
                )

        return {
            'errors': errors,
            'warnings': warnings
        }


class JohnHancock401kParser:
    """Parser for John Hancock 401k quarterly statements."""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.data = {}

    def parse(self):
        """
        Parse the PDF and extract statement data.

        Returns:
            dict: Extracted statement data
        """
        text = None

        # Try pdfplumber first - extract all pages, handling rotations
        with pdfplumber.open(self.pdf_path) as pdf:
            all_text = []
            for page in pdf.pages:
                # Try normal orientation first
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)

                # Also try extracting with different rotations for rotated sections
                # John Hancock statements often have tables rotated 90 degrees
                for angle in [90, 270]:
                    try:
                        rotated_page = page.rotate(angle)
                        rotated_text = rotated_page.extract_text()
                        if rotated_text and len(rotated_text.strip()) > 50:
                            all_text.append(rotated_text)
                    except:
                        pass

            text = '\n'.join(all_text)

        # Try PyPDF2 if needed
        if not text or len(text.strip()) < 100:
            from PyPDF2 import PdfReader
            reader = PdfReader(self.pdf_path)
            all_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
            text = '\n'.join(all_text)

        # Try OCR if still insufficient
        if not text or len(text.strip()) < 100:
            text = self._extract_text_with_ocr()

        if not text or len(text.strip()) < 100:
            raise ValueError(
                "Unable to extract text from PDF using any method. "
                "Please check the PDF file or use manual entry."
            )

        # John Hancock PDFs sometimes have mixed normal and reversed text in tables
        # Reverse lines that contain reversed keywords
        if 'YRAMMUS' in text or 'TNEMTSEVNI' in text or 'DOIREP' in text:
            lines = text.split('\n')
            processed_lines = []
            reversed_keywords = [
                'YRAMMUS', 'TNEMTSEVNI', 'DOIREP', 'TNEMETATS', 'ecnalaB', 'eulaV', 'htworG',
                'gninepO', 'gnisolC', 'dnuF', 'paC', 'lanoitanretnI', 'emocnI', 'snoitubirtnoC',
                'tnapicitraP', 'stnemyaP', 'snoitpmedeR', 'tekraM', 'egnahC'
            ]
            # Also reverse lines that look like reversed currency (e.g., "77.824,151")
            currency_pattern = re.compile(r'\d{2}\.\d{3},\d{2,3}')

            for line in lines:
                # If line contains reversed keywords or reversed currency pattern, reverse it
                if any(keyword in line for keyword in reversed_keywords) or currency_pattern.search(line):
                    processed_lines.append(line[::-1])
                else:
                    processed_lines.append(line)

            text = '\n'.join(processed_lines)

        # Parse John Hancock 401k statement sections
        self._parse_account_info(text)
        self._parse_period_dates(text)
        self._parse_account_values(text)

        return self.data

    def _extract_text_with_ocr(self):
        """Extract text from image-based PDF using OCR."""
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(self.pdf_path, first_page=1, last_page=1)
            if not images:
                return ""

            text = pytesseract.image_to_string(images[0])
            return text

        except Exception as e:
            print(f"OCR extraction failed: {e}")
            return ""

    def _parse_period_dates(self, text):
        """Extract statement period dates."""
        # John Hancock format: "07/01/2025 - 09/30/2025" or "STATEMENT PERIOD: 07/01/2025 - 09/30/2025"
        period_match = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', text)
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            self.data['period_start'] = datetime.strptime(start_str, '%m/%d/%Y').date()
            self.data['period_end'] = datetime.strptime(end_str, '%m/%d/%Y').date()
            self.data['statement_date'] = self.data['period_end']

        # Alternative: Look for "AS OF MM/DD/YYYY"
        if 'statement_date' not in self.data:
            as_of_match = re.search(r'(?:AS\s+OF|as\s+of)[:\s]+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if as_of_match:
                date_str = as_of_match.group(1)
                self.data['statement_date'] = datetime.strptime(date_str, '%m/%d/%Y').date()
                self.data['period_end'] = self.data['statement_date']

    def _parse_account_info(self, text):
        """Extract account information from John Hancock statement."""
        # Look for account number
        account_match = re.search(r'Account\s+(?:Number|#)[:\s]*(\d+)', text, re.IGNORECASE)
        if account_match:
            self.data['account_number'] = account_match.group(1)

        # Look for participant/policy number
        participant_match = re.search(r'Participant\s+(?:Number|ID)[:\s]*(\d+)', text, re.IGNORECASE)
        if participant_match:
            self.data['participant_number'] = participant_match.group(1)

    def _parse_account_values(self, text):
        """Extract account values from John Hancock 401k statement."""
        # John Hancock format: Amount may be on previous line(s) before "Opening Balance"
        # Try multi-line pattern first: capture amount before "Opening" or "Balance Opening"
        multiline_beginning_patterns = [
            r'([\d,]+\.\d{2})\s*\$?\s*Balance\s+Opening',
            r'([\d,]+\.\d{2})\s*\$?\s*Opening\s+Balance',
        ]
        for pattern in multiline_beginning_patterns:
            beginning_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if beginning_match:
                self.data['beginning_value'] = self._parse_currency(beginning_match.group(1))
                break

        # Try single-line patterns if multi-line didn't work
        if 'beginning_value' not in self.data:
            beginning_patterns = [
                r'Opening\s+Balance\s+\$?\s*([\d,]+\.\d{2})',
                r'Balance\s+Opening\s+\$?\s*([\d,]+\.\d{2})',
                r'Beginning\s+[Bb]alance\s+\$?\s*([\d,]+\.\d{2})'
            ]
            for pattern in beginning_patterns:
                beginning_match = re.search(pattern, text, re.IGNORECASE)
                if beginning_match:
                    self.data['beginning_value'] = self._parse_currency(beginning_match.group(1))
                    break

        # John Hancock format: "Closing Balance" followed by amount or "$168,202.73 Balance Closing"
        ending_patterns = [
            r'Closing\s+Balance\s+\$?\s*([\d,]+\.\d{2})',
            r'\$\s*([\d,]+\.\d{2})\s+Balance\s+Closing',
            r'Balance\s+Closing\s+\$?\s*([\d,]+\.\d{2})',
            r'Ending\s+[Bb]alance\s+\$?\s*([\d,]+\.\d{2})'
        ]
        for pattern in ending_patterns:
            ending_match = re.search(pattern, text, re.IGNORECASE)
            if ending_match:
                self.data['ending_value'] = self._parse_currency(ending_match.group(1))
                break

        # John Hancock format: "Participant Contributions" or "Employee Pre-Tax Contribution" in table
        # Look for total in the activity table (usually on page 2)
        employee_patterns = [
            # Table format: "Employee Pre-Tax Contribution" followed by amounts, we want the last (total)
            r'Employee\s+Pre-Tax\s+Contribution\s+(?:[\d,]+\.\d{2}\s+){0,10}([\d,]+\.\d{2})',
            r'Participant\s+Contributions?\s+\$?\s*([\d,]+\.\d{2})',
            r'Contributions?\s+Participant\s+\$?\s*([\d,]+\.\d{2})',
            r'Employee\s+[Cc]ontributions?\s+\$?\s*([\d,]+\.\d{2})',
            r'Pre-Tax\s+Contribution\s+\$?\s*([\d,]+\.\d{2})'
        ]
        for pattern in employee_patterns:
            employee_matches = re.findall(pattern, text, re.IGNORECASE)
            if employee_matches:
                # Take the last match (usually the total)
                self.data['employee_contributions'] = self._parse_currency(employee_matches[-1])
                break
        if 'employee_contributions' not in self.data:
            self.data['employee_contributions'] = Decimal('0')

        # Employer contributions - John Hancock may not show this separately in profit sharing plans
        employer_patterns = [
            r'Employer\s+[Cc]ontributions?\s+\$?\s*([\d,]+\.\d{2})',
            r'Company\s+[Cc]ontributions?\s+\$?\s*([\d,]+\.\d{2})',
            r'Matching\s+[Cc]ontributions?\s+\$?\s*([\d,]+\.\d{2})'
        ]
        for pattern in employer_patterns:
            employer_match = re.search(pattern, text, re.IGNORECASE)
            if employer_match:
                self.data['employer_contributions'] = self._parse_currency(employer_match.group(1))
                break
        if 'employer_contributions' not in self.data:
            self.data['employer_contributions'] = Decimal('0')

        # John Hancock format: "Gain/Loss" in activity table - look for total (last value)
        # Need to capture negative values with minus sign
        gainloss_patterns = [
            # Table format: "Gain/Loss" followed by multiple amounts, we want the last (total)
            # Capture both positive and negative (with minus sign)
            r'Gain/Loss\s+(?:[\d,\-\.]+\s+){0,10}(-?[\d,]+\.\d{2})',
            r'Change\s+in\s+Market\s+Value\s+\$?\s*(-?[\d,]+\.\d{2})',
            r'Market\s+Value\s+in\s+Change\s+\$?\s*(-?[\d,]+\.\d{2})',
            r'Investment\s+[Gg]ain(?:/[Ll]oss)?\s+\$?\s*(-?[\d,]+\.\d{2})'
        ]
        for pattern in gainloss_patterns:
            gain_matches = re.findall(pattern, text, re.IGNORECASE)
            if gain_matches:
                # Take the last match (usually the total)
                value_str = gain_matches[-1]
                # Handle negative values (starts with minus sign)
                if value_str.startswith('-'):
                    self.data['investment_gain_loss'] = -self._parse_currency(value_str[1:])
                else:
                    self.data['investment_gain_loss'] = self._parse_currency(value_str)
                break

        # Check for negative gain/loss (with parentheses)
        if 'investment_gain_loss' not in self.data:
            for pattern in gainloss_patterns:
                # Remove the -? prefix and wrap in parentheses
                negative_pattern = pattern.replace(r'(-?[\d,]+\.\d{2})', r'\(([\d,]+\.\d{2})\)')
                loss_matches = re.findall(negative_pattern, text, re.IGNORECASE)
                if loss_matches:
                    self.data['investment_gain_loss'] = -self._parse_currency(loss_matches[-1])
                    break

        if 'investment_gain_loss' not in self.data:
            self.data['investment_gain_loss'] = Decimal('0')

        # John Hancock includes dividends/interest separately in the table - add to investment gain/loss
        dividend_patterns = [
            r'Dividends?/Interest\s+(?:[\d,\-\.]+\s+){0,10}([\d,]+\.\d{2})'
        ]
        for pattern in dividend_patterns:
            dividend_matches = re.findall(pattern, text, re.IGNORECASE)
            if dividend_matches:
                dividends = self._parse_currency(dividend_matches[-1])
                self.data['investment_gain_loss'] = self.data['investment_gain_loss'] + dividends
                break

        # John Hancock format: "Redemptions & Payments" (can be negative)
        withdrawal_patterns = [
            r'Redemptions?\s+&\s+Payments?\s+\$?\s*([\d,]+\.\d{2})',
            r'Payments?\s+&\s+Redemptions?\s+\$?\s*([\d,]+\.\d{2})',
            r'Withdrawals?\s+\$?\s*([\d,]+\.\d{2})',
            r'Distributions?\s+\$?\s*([\d,]+\.\d{2})'
        ]

        # First check for negative values with minus sign
        for pattern in withdrawal_patterns:
            negative_pattern = pattern.replace(r'\$?\s*([\d,]+\.\d{2})', r'-\$?\s*([\d,]+\.\d{2})')
            withdrawal_match = re.search(negative_pattern, text, re.IGNORECASE)
            if withdrawal_match:
                # Value is already negative in text, so take absolute value
                self.data['withdrawals'] = self._parse_currency(withdrawal_match.group(1))
                break

        # If not found as negative, try regular pattern
        if 'withdrawals' not in self.data:
            for pattern in withdrawal_patterns:
                withdrawal_match = re.search(pattern, text, re.IGNORECASE)
                if withdrawal_match:
                    self.data['withdrawals'] = self._parse_currency(withdrawal_match.group(1))
                    break

        if 'withdrawals' not in self.data:
            self.data['withdrawals'] = Decimal('0')

        # John Hancock format: "Administrative Fee" in table (often negative)
        fee_patterns = [
            # Table format: "Administrative Fee" followed by amounts (may have negatives with -)
            r'Administrative\s+Fee\s+(?:[\d,\-\.]+\s+){0,10}-?([\d,]+\.\d{2})',
            r'Fee\s+Administrative\s+-?\$?\s*([\d,]+\.\d{2})',
            r'Fees?\s+-?\$?\s*([\d,]+\.\d{2})'
        ]

        for pattern in fee_patterns:
            fee_matches = re.findall(pattern, text, re.IGNORECASE)
            if fee_matches:
                # Take the last match (usually the total), and take absolute value
                self.data['fees'] = abs(self._parse_currency(fee_matches[-1]))
                break

        if 'fees' not in self.data:
            self.data['fees'] = Decimal('0')

        # Loan payments
        loan_patterns = [
            r'Loan\s+[Pp]ayments?\s+\$\s*([\d,]+\.\d{2})',
            r'Loan\s+[Rr]epayments?\s+\$\s*([\d,]+\.\d{2})'
        ]
        for pattern in loan_patterns:
            loan_match = re.search(pattern, text, re.IGNORECASE)
            if loan_match:
                self.data['loan_payments'] = self._parse_currency(loan_match.group(1))
                break
        if 'loan_payments' not in self.data:
            self.data['loan_payments'] = Decimal('0')

        # Vested balance
        vested_patterns = [
            r'Vested\s+[Bb]alance\s+\$\s*([\d,]+\.\d{2})',
            r'Total\s+[Vv]ested\s+\$\s*([\d,]+\.\d{2})'
        ]
        for pattern in vested_patterns:
            vested_match = re.search(pattern, text, re.IGNORECASE)
            if vested_match:
                self.data['vested_balance'] = self._parse_currency(vested_match.group(1))
                break

    def _parse_currency(self, value_str):
        """Convert currency string to Decimal."""
        cleaned = value_str.replace('$', '').replace(',', '')
        return Decimal(cleaned)

    def validate(self):
        """Validate parsed data and return any errors or warnings."""
        errors = []
        warnings = []

        # Check required fields
        required_fields = [
            'statement_date', 'period_start', 'period_end',
            'beginning_value', 'ending_value',
            'employee_contributions', 'employer_contributions',
            'investment_gain_loss', 'withdrawals', 'fees', 'loan_payments'
        ]

        for field in required_fields:
            if field not in self.data:
                errors.append(f"Missing required field: {field}")

        # Validate reconciliation if all fields present
        if not errors:
            expected_ending = (
                self.data['beginning_value'] +
                self.data['employee_contributions'] +
                self.data['employer_contributions'] +
                self.data['investment_gain_loss'] +
                self.data['loan_payments'] -
                self.data['withdrawals'] -
                self.data['fees']
            )

            difference = abs(self.data['ending_value'] - expected_ending)

            # Allow for small rounding differences (up to $1)
            if difference > Decimal('1.00'):
                warnings.append(
                    f"Reconciliation mismatch: Expected ending ${expected_ending}, "
                    f"but PDF shows ${self.data['ending_value']} "
                    f"(difference: ${difference})"
                )

        return {
            'errors': errors,
            'warnings': warnings
        }


class MHoldingsBrokerageParser:
    """Parser for M Holdings Securities brokerage statements."""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.data = {}

    def parse(self):
        """
        Parse the PDF and extract statement data.

        Returns:
            dict: Extracted statement data
        """
        text = None

        # Try pdfplumber first - extract all pages
        with pdfplumber.open(self.pdf_path) as pdf:
            all_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
            text = '\n'.join(all_text)

        # Try PyPDF2 if needed
        if not text or len(text.strip()) < 100:
            from PyPDF2 import PdfReader
            reader = PdfReader(self.pdf_path)
            all_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
            text = '\n'.join(all_text)

        # Try OCR if still insufficient
        if not text or len(text.strip()) < 100:
            text = self._extract_text_with_ocr()

        if not text or len(text.strip()) < 100:
            raise ValueError(
                "Unable to extract text from PDF using any method. "
                "Please check the PDF file or use manual entry."
            )

        # Parse M Holdings brokerage statement sections
        self._parse_account_info(text)
        self._parse_period_dates(text)
        self._parse_account_overview(text)
        self._parse_account_allocation(text)

        return self.data

    def _extract_text_with_ocr(self):
        """Extract text from image-based PDF using OCR."""
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(self.pdf_path, first_page=1, last_page=2)
            if not images:
                return ""

            text = ""
            for image in images:
                text += pytesseract.image_to_string(image) + "\n"
            return text

        except Exception as e:
            print(f"OCR extraction failed: {e}")
            return ""

    def _parse_period_dates(self, text):
        """Extract statement period dates."""
        # M Holdings format: "STATEMENT FOR THE PERIOD SEPTEMBER 1, 2025 TO SEPTEMBER 30, 2025"
        # or "Statement for the Period September 1, 2025 to September 30, 2025"
        period_match = re.search(
            r'(?:STATEMENT\s+FOR\s+THE\s+PERIOD|Statement\s+for\s+the\s+Period)\s+(\w+\s+\d{1,2},\s+\d{4})\s+(?:TO|to)\s+(\w+\s+\d{1,2},\s+\d{4})',
            text,
            re.IGNORECASE
        )
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            try:
                self.data['period_start'] = datetime.strptime(start_str, '%B %d, %Y').date()
                self.data['period_end'] = datetime.strptime(end_str, '%B %d, %Y').date()
                self.data['statement_date'] = self.data['period_end']
            except ValueError:
                pass

        # Alternative: Look for "AS OF MM/DD/YY" format in ending value line
        if 'statement_date' not in self.data:
            as_of_match = re.search(r'ENDING\s+VALUE\s+\(AS\s+OF\s+(\d{2}/\d{2}/\d{2})\)', text, re.IGNORECASE)
            if as_of_match:
                date_str = as_of_match.group(1)
                try:
                    self.data['statement_date'] = datetime.strptime(date_str, '%m/%d/%y').date()
                    self.data['period_end'] = self.data['statement_date']
                except ValueError:
                    pass

    def _parse_account_info(self, text):
        """Extract account information from M Holdings statement."""
        # Look for account number
        account_match = re.search(r'Account\s+(?:Number|#)[:\s]*([A-Z0-9\-]+)', text, re.IGNORECASE)
        if account_match:
            self.data['account_number'] = account_match.group(1)

    def _parse_account_overview(self, text):
        """Extract account values from Account Overview section."""
        # M Holdings format has "Account Overview" section with table format:
        # CHANGE IN ACCOUNT VALUE    Current Period    Year-to-Date
        # BEGINNING VALUE            $0.00             $0.00
        # Additions and Withdrawals  $54,232.62        $54,232.62
        # ...

        # Look for the Account Overview section on page 2
        # It starts with "Account Overview" and ends before "INCOME Account Allocation"
        overview_match = re.search(r'Account\s+Overview.*?(?=INCOME\s+Account\s+Allocation)', text, re.IGNORECASE | re.DOTALL)
        if overview_match:
            overview_text = overview_match.group(0)
        else:
            # Fallback: just use all text
            overview_text = text

        # Beginning Value - matches "BEGINNING VALUE $0.00 $0.00" and takes first value (Current Period)
        beginning_match = re.search(r'BEGINNING\s+VALUE\s+\$\s*([\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if beginning_match:
            self.data['beginning_value'] = self._parse_currency(beginning_match.group(1))
        else:
            self.data['beginning_value'] = Decimal('0')

        # Ending Value - matches "ENDING VALUE (AS OF 09/30/25) $213,513.74 $213,513.74"
        ending_match = re.search(r'ENDING\s+VALUE\s+\(AS\s+OF\s+[^)]+\)\s+\$\s*([\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if ending_match:
            self.data['ending_value'] = self._parse_currency(ending_match.group(1))
        elif not ending_match:
            # Try without the date part
            ending_match = re.search(r'ENDING\s+VALUE\s+\$\s*([\d,]+\.\d{2})', overview_text, re.IGNORECASE)
            if ending_match:
                self.data['ending_value'] = self._parse_currency(ending_match.group(1))

        # Deposits - "Additions and Withdrawals $54,232.62 $54,232.62"
        # or "Additions and Withdrawals ($1,000.00)" for net withdrawals
        # This line actually shows NET additions/withdrawals, so we need to be careful
        additions_match = re.search(r'Additions\s+and\s+Withdrawals\s+\$\s*([\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if additions_match:
            # This is net additions (deposits - withdrawals)
            net_additions = self._parse_currency(additions_match.group(1))
            # Positive value = net deposits
            self.data['deposits'] = net_additions
            self.data['withdrawals'] = Decimal('0')
        else:
            # Try parentheses format for negative values (net withdrawals)
            additions_match = re.search(r'Additions\s+and\s+Withdrawals\s+\(\$\s*([\d,]+\.\d{2})\)', overview_text, re.IGNORECASE)
            if additions_match:
                # Parentheses indicate net withdrawals
                net_withdrawals = self._parse_currency(additions_match.group(1))
                self.data['deposits'] = Decimal('0')
                self.data['withdrawals'] = net_withdrawals
            else:
                self.data['deposits'] = Decimal('0')
                self.data['withdrawals'] = Decimal('0')

        # Income - "Income $247.20 $247.20"
        income_match = re.search(r'Income\s+\$\s*([\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if income_match:
            income_value = self._parse_currency(income_match.group(1))
            # M Holdings shows total income, we'll look for breakdown in INCOME section
            self.data['total_income'] = income_value
        else:
            income_value = Decimal('0')

        # Look for breakdown in INCOME section - "Taxable Dividends $247.20 $247.20"
        income_section_match = re.search(r'INCOME.*?(?=MESSAGES|Account\s+Allocation|$)', text, re.IGNORECASE | re.DOTALL)
        if income_section_match:
            income_section = income_section_match.group(0)

            # Taxable Dividends
            dividend_match = re.search(r'Taxable\s+Dividends\s+\$\s*([\d,]+\.\d{2})', income_section, re.IGNORECASE)
            if dividend_match:
                self.data['dividends'] = self._parse_currency(dividend_match.group(1))
            else:
                self.data['dividends'] = Decimal('0')

            # Interest (if shown separately)
            interest_match = re.search(r'Interest\s+\$\s*([\d,]+\.\d{2})', income_section, re.IGNORECASE)
            if interest_match:
                self.data['interest'] = self._parse_currency(interest_match.group(1))
            else:
                self.data['interest'] = Decimal('0')

            # If no breakdown, put all income in dividends
            if self.data['dividends'] == Decimal('0') and self.data['interest'] == Decimal('0') and income_value > 0:
                self.data['dividends'] = income_value
        else:
            # Default: put all income in dividends
            self.data['dividends'] = income_value
            self.data['interest'] = Decimal('0')

        # Change in Value - "Change in Value $159,033.92 $159,033.92"
        # or "Change in Value ($5,000.00)" for losses
        change_match = re.search(r'Change\s+in\s+Value\s+\$\s*(-?[\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if change_match:
            value_str = change_match.group(1)
            if value_str.startswith('-'):
                self.data['market_change'] = -self._parse_currency(value_str[1:])
            else:
                self.data['market_change'] = self._parse_currency(value_str)
        else:
            # Try parentheses format for negative values
            change_match = re.search(r'Change\s+in\s+Value\s+\(\$\s*([\d,]+\.\d{2})\)', overview_text, re.IGNORECASE)
            if change_match:
                self.data['market_change'] = -self._parse_currency(change_match.group(1))
            else:
                self.data['market_change'] = Decimal('0')

        # Taxes, Fees and Expenses - "Taxes,Fees and Expenses $0.00 $0.00"
        # or "Taxes, Fees and Expenses ($530.51)" for negative values
        fee_match = re.search(r'Taxes,\s*Fees\s+and\s+Expenses\s+\$\s*([\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if fee_match:
            self.data['fees'] = self._parse_currency(fee_match.group(1))
        else:
            # Try parentheses format for negative values
            fee_match = re.search(r'Taxes,\s*Fees\s+and\s+Expenses\s+\(\$\s*([\d,]+\.\d{2})\)', overview_text, re.IGNORECASE)
            if fee_match:
                # Parentheses indicate negative, but fees are always stored as positive
                self.data['fees'] = self._parse_currency(fee_match.group(1))
            else:
                self.data['fees'] = Decimal('0')

        # Misc. & Corporate Actions - could include capital gains
        # Can be positive or negative, with parentheses for negative
        misc_match = re.search(r'Misc\.\s+&\s+Corporate\s+Actions\s+\$\s*(-?[\d,]+\.\d{2})', overview_text, re.IGNORECASE)
        if misc_match:
            value_str = misc_match.group(1)
            if value_str.startswith('-'):
                self.data['other_activity'] = -self._parse_currency(value_str[1:])
            else:
                self.data['other_activity'] = self._parse_currency(value_str)
        else:
            # Try parentheses format for negative values
            misc_match = re.search(r'Misc\.\s+&\s+Corporate\s+Actions\s+\(\$\s*([\d,]+\.\d{2})\)', overview_text, re.IGNORECASE)
            if misc_match:
                self.data['other_activity'] = -self._parse_currency(misc_match.group(1))
            else:
                self.data['other_activity'] = Decimal('0')

        # Capital gains - typically not shown separately in M Holdings
        self.data['capital_gains'] = Decimal('0')

    def _parse_account_allocation(self, text):
        """Extract account allocation breakdown from M Holdings statement."""
        # M Holdings format has an "Account Allocation" section with percentages:
        # Fixed Income 3.2%
        # Money Markets 25.5%
        # Equities 71.3%

        # Look for Account Allocation section
        allocation_section_match = re.search(
            r'ACCOUNT\s+ALLOCATION.*?(?=MESSAGES|Refer to|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if allocation_section_match:
            allocation_text = allocation_section_match.group(0)

            # Get ending value for calculating dollar amounts
            ending_value = self.data.get('ending_value', Decimal('0'))

            # Money Market (might be "Money Market" or "Money Markets")
            money_market_match = re.search(
                r'Money\s+Markets?\s+([\d.]+)%',
                allocation_text,
                re.IGNORECASE
            )
            if money_market_match and ending_value > 0:
                percentage = Decimal(money_market_match.group(1))
                self.data['money_market'] = (ending_value * percentage / Decimal('100')).quantize(Decimal('0.01'))
            else:
                self.data['money_market'] = None

            # Equities (might be labeled as "Stocks" or "Equity")
            equities_match = re.search(
                r'(?:Equities|Equity|Stocks)\s+([\d.]+)%',
                allocation_text,
                re.IGNORECASE
            )
            if equities_match and ending_value > 0:
                percentage = Decimal(equities_match.group(1))
                self.data['equities'] = (ending_value * percentage / Decimal('100')).quantize(Decimal('0.01'))
            else:
                self.data['equities'] = None

            # Fixed Income (might be labeled as "Bonds")
            fixed_income_match = re.search(
                r'(?:Fixed\s+Income|Bonds)\s+([\d.]+)%',
                allocation_text,
                re.IGNORECASE
            )
            if fixed_income_match and ending_value > 0:
                percentage = Decimal(fixed_income_match.group(1))
                self.data['fixed_income'] = (ending_value * percentage / Decimal('100')).quantize(Decimal('0.01'))
            else:
                self.data['fixed_income'] = None
        else:
            # If no allocation section found, set all to None
            self.data['money_market'] = None
            self.data['equities'] = None
            self.data['fixed_income'] = None

    def _parse_currency(self, value_str):
        """Convert currency string to Decimal."""
        cleaned = value_str.replace('$', '').replace(',', '')
        return Decimal(cleaned)

    def validate(self):
        """Validate parsed data and return any errors or warnings."""
        errors = []
        warnings = []

        # Check required fields
        required_fields = [
            'statement_date', 'beginning_value', 'ending_value',
            'deposits', 'withdrawals', 'dividends', 'interest',
            'market_change', 'fees'
        ]

        for field in required_fields:
            if field not in self.data:
                errors.append(f"Missing required field: {field}")

        # Validate reconciliation if all fields present
        if not errors:
            expected_ending = (
                self.data['beginning_value'] +
                self.data['deposits'] -
                self.data['withdrawals'] +
                self.data['dividends'] +
                self.data['interest'] +
                self.data['capital_gains'] +
                self.data['market_change'] +
                self.data.get('other_activity', Decimal('0')) -
                self.data['fees']
            )

            difference = abs(self.data['ending_value'] - expected_ending)

            # Allow for small rounding differences (up to $1)
            if difference > Decimal('1.00'):
                warnings.append(
                    f"Reconciliation mismatch: Expected ending ${expected_ending}, "
                    f"but PDF shows ${self.data['ending_value']} "
                    f"(difference: ${difference})"
                )

        return {
            'errors': errors,
            'warnings': warnings
        }


def _detect_statement_type(pdf_path):
    """
    Detect which type of investment statement this is.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        str: 'jackson', 'tiaa', 'valic', 'johnhancock401k', 'mholdings', or 'unknown'
    """
    try:
        # Extract text from first page using ALL methods for best detection
        text = ''

        # Try pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text_regular = first_page.extract_text() or ''
            text += text_regular

        # Also try PyPDF2 (sometimes it extracts different text)
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(pdf_path)
            text_pypdf = reader.pages[0].extract_text() or ''
            text += '\n' + text_pypdf
        except:
            pass

        # Try OCR if we still don't have enough text
        if len(text.strip()) < 100:
            try:
                from pdf2image import convert_from_path
                import pytesseract
                images = convert_from_path(pdf_path, first_page=1, last_page=1)
                if images:
                    text_ocr = pytesseract.image_to_string(images[0])
                    text += '\n' + text_ocr
            except:
                pass

        if not text or len(text.strip()) < 50:
            return 'unknown'

        # Check for M Holdings brokerage indicators
        if re.search(r'M\s+Holdings', text, re.IGNORECASE) or re.search(r'M\s+Financial\s+Holdings', text, re.IGNORECASE):
            return 'mholdings'

        # Check for John Hancock 401k/Profit Sharing indicators
        # John Hancock PDFs sometimes have mixed normal/reversed text
        if (re.search(r'John\s+Hancock', text, re.IGNORECASE) or re.search(r'johnhancock\.com', text, re.IGNORECASE)) and (
            re.search(r'401\(?k\)?', text, re.IGNORECASE) or
            re.search(r'Retirement\s+Plan', text, re.IGNORECASE) or
            re.search(r'Profit\s+Sharing\s+Plan', text, re.IGNORECASE) or
            (re.search(r'Participant', text, re.IGNORECASE) and re.search(r'Contributions?', text, re.IGNORECASE))
        ):
            return 'johnhancock401k'

        # Check for Valic/Corebridge indicators
        if re.search(r'Corebridge', text, re.IGNORECASE) or re.search(r'VALIC', text, re.IGNORECASE):
            return 'valic'

        # Check for TIAA indicators
        if re.search(r'TIAA', text, re.IGNORECASE) or re.search(r'CREF', text, re.IGNORECASE):
            return 'tiaa'

        # Check for Jackson indicators
        if re.search(r'Jackson', text, re.IGNORECASE) or re.search(r'Contract\s+Number', text, re.IGNORECASE):
            return 'jackson'

        return 'unknown'

    except Exception as e:
        print(f"Error detecting statement type: {e}")
        return 'unknown'


def parse_statement(pdf_path):
    """
    Convenience function to parse an investment statement PDF.
    Auto-detects statement type and uses appropriate parser.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        tuple: (data_dict, validation_dict)
    """
    # Detect statement type
    statement_type = _detect_statement_type(pdf_path)

    # Use appropriate parser
    if statement_type == 'mholdings':
        parser = MHoldingsBrokerageParser(pdf_path)
    elif statement_type == 'johnhancock401k':
        parser = JohnHancock401kParser(pdf_path)
    elif statement_type == 'valic':
        parser = ValicStatementParser(pdf_path)
    elif statement_type == 'tiaa':
        parser = TIAAStatementParser(pdf_path)
    elif statement_type == 'jackson':
        parser = AnnuityStatementParser(pdf_path)
    else:
        # Default to Jackson parser for unknown types
        parser = AnnuityStatementParser(pdf_path)

    data = parser.parse()
    validation = parser.validate()

    return data, validation


def parse_annuity_statement(pdf_path):
    """
    Convenience function to parse an annuity statement PDF.
    Auto-detects statement type and uses appropriate parser.

    Deprecated: Use parse_statement() instead for broader support.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        tuple: (data_dict, validation_dict)
    """
    return parse_statement(pdf_path)
