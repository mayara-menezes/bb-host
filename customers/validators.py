"""Brazilian tax ID (CPF/CNPJ) validation."""

import re

from django.core.exceptions import ValidationError


def digits_only(value):
    return re.sub(r'\D', '', value or '')


def _cpf_is_valid(n):
    if len(n) != 11 or n == n[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(n[i]) * (size + 1 - i) for i in range(size))
        check_digit = (total * 10) % 11 % 10
        if check_digit != int(n[size]):
            return False
    return True


def _cnpj_is_valid(n):
    if len(n) != 14 or n == n[0] * 14:
        return False
    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for size in (12, 13):
        w = weights if size == 12 else [6, *weights]
        total = sum(int(n[i]) * w[i] for i in range(size))
        check_digit = 0 if total % 11 < 2 else 11 - total % 11
        if check_digit != int(n[size]):
            return False
    return True


def format_document(value):
    n = digits_only(value)
    if len(n) == 11:
        return f'{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}'
    if len(n) == 14:
        return f'{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}'
    return value


def validate_document(value, document_type):
    """Check CPF/CNPJ check digits and return it formatted. Passports and foreign IDs are only normalized."""
    n = digits_only(value)
    if document_type == 'CPF':
        if not _cpf_is_valid(n):
            raise ValidationError('Invalid CPF.')
        return format_document(n)
    if document_type == 'CNPJ':
        if not _cnpj_is_valid(n):
            raise ValidationError('Invalid CNPJ.')
        return format_document(n)
    value = (value or '').strip().upper()
    if len(value) < 5:
        raise ValidationError('Document number is too short.')
    return value
