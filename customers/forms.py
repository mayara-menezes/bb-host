from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from .models import ContactMessage, CustomerProfile, Ticket, TicketCategory
from .validators import digits_only, validate_document

User = get_user_model()


class StyledFormMixin:
    """Applies the site's Tailwind component classes (static/src/input.css) to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-checkbox')
            elif isinstance(w, forms.Select):
                w.attrs.setdefault('class', 'form-select')
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault('class', 'form-textarea')
            else:
                w.attrs.setdefault('class', 'form-input')


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(
        label='E-mail', widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'})
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Incorrect e-mail or password.',
    }

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


class SignupForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label='Full name', max_length=150)
    email = forms.EmailField(label='E-mail')
    document_type = forms.ChoiceField(label='ID type', choices=CustomerProfile.DOCUMENT_TYPES, initial='CPF')
    document_number = forms.CharField(label='Document number', max_length=30)
    company_name = forms.CharField(label='Company name', max_length=150, required=False)
    phone = forms.CharField(label='Phone / WhatsApp', max_length=20)
    password = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(
        label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'})
    )
    accept_terms = forms.BooleanField(label='I have read and accept the Terms of Use and the Privacy Policy')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this e-mail already exists. Sign in instead.')
        return email

    def clean_phone(self):
        phone = digits_only(self.cleaned_data['phone'])
        if len(phone) < 10:
            raise forms.ValidationError('Enter the phone number with area code.')
        return phone

    def clean(self):
        data = super().clean()
        if data.get('document_number') and data.get('document_type'):
            try:
                data['document_number'] = validate_document(data['document_number'], data['document_type'])
            except forms.ValidationError as e:
                self.add_error('document_number', e)
        if data.get('document_type') == 'CNPJ' and not data.get('company_name'):
            self.add_error('company_name', 'Enter the company name.')
        p1, p2 = data.get('password'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'The passwords do not match.')
        if p1:
            temp_user = User(
                username=data.get('email', ''), email=data.get('email', ''), first_name=data.get('name', '')
            )
            try:
                password_validation.validate_password(p1, temp_user)
            except forms.ValidationError as e:
                self.add_error('password', e)
        return data

    def save(self):
        d = self.cleaned_data
        parts = d['name'].strip().split(' ', 1)
        user = User.objects.create_user(
            username=d['email'],
            email=d['email'],
            password=d['password'],
            first_name=parts[0][:150],
            last_name=(parts[1] if len(parts) > 1 else '')[:150],
        )
        CustomerProfile.objects.create(
            user=user,
            document_type=d['document_type'],
            document_number=d['document_number'],
            company_name=d.get('company_name', ''),
            phone=d['phone'],
            terms_accepted_at=timezone.now(),
        )
        return user


class UserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = [
            'document_type',
            'document_number',
            'company_name',
            'phone',
            'country',
            'postal_code',
            'street',
            'number',
            'complement',
            'district',
            'city',
            'state',
        ]

    def clean(self):
        data = super().clean()
        if data.get('document_number'):
            try:
                data['document_number'] = validate_document(data['document_number'], data.get('document_type'))
            except forms.ValidationError as e:
                self.add_error('document_number', e)
        if data.get('phone'):
            data['phone'] = digits_only(data['phone'])
        return data


class ContactForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'phone', 'email', 'company', 'subject', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 7})}


class TicketForm(StyledFormMixin, forms.ModelForm):
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 6}))

    class Meta:
        model = Ticket
        fields = ['subject', 'category', 'service']
        labels = {'service': 'Related service (optional)'}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = TicketCategory.objects.filter(active=True)
        self.fields['category'].empty_label = 'Select'
        self.fields['service'].queryset = user.services.exclude(status='cancelled')
        self.fields['service'].empty_label = 'None'


class TicketReplyForm(StyledFormMixin, forms.Form):
    body = forms.CharField(label='Reply', widget=forms.Textarea(attrs={'rows': 4}))
