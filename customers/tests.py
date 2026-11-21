from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .validators import format_document, validate_document


class DocumentValidatorTest(SimpleTestCase):
    def test_valid_cpf_is_formatted(self):
        self.assertEqual(validate_document('52998224725', 'CPF'), '529.982.247-25')

    def test_invalid_cpf(self):
        for cpf in ['52998224724', '111.111.111-11', '123']:
            with self.subTest(cpf=cpf), self.assertRaises(ValidationError):
                validate_document(cpf, 'CPF')

    def test_valid_cnpj_is_formatted(self):
        self.assertEqual(validate_document('27041737000109', 'CNPJ'), '27.041.737/0001-09')

    def test_invalid_cnpj(self):
        with self.assertRaises(ValidationError):
            validate_document('27.041.737/0001-00', 'CNPJ')

    def test_foreign_documents_are_only_normalized(self):
        self.assertEqual(validate_document(' ab123456 ', 'PASSPORT'), 'AB123456')

    def test_format_keeps_unknown_values(self):
        self.assertEqual(format_document('abc'), 'abc')
