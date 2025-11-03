"""
PDF Parser for Annuity Statements

Extracts key financial data from quarterly annuity statements.
Supports multiple formats:
- Jackson annuity statements
- TIAA annuity statements
- Valic/Corebridge Financial annuity statements
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


def _detect_statement_type(pdf_path):
    """
    Detect which type of annuity statement this is.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        str: 'jackson', 'tiaa', 'valic', or 'unknown'
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

        # Check for Valic/Corebridge indicators (check first as they're more specific)
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


def parse_annuity_statement(pdf_path):
    """
    Convenience function to parse an annuity statement PDF.
    Auto-detects statement type and uses appropriate parser.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        tuple: (data_dict, validation_dict)
    """
    # Detect statement type
    statement_type = _detect_statement_type(pdf_path)

    # Use appropriate parser
    if statement_type == 'valic':
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
