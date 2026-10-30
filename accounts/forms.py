from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from .models import UserProfile, Address
from .validators import validate_and_normalize_indian_phone, validate_email_format
from .otp_service import check_email_is_verified_for_registration, mark_registration_verification_used

User = get_user_model()


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_first_name',
            'placeholder': 'First Name',
            'autocomplete': 'given-name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_last_name',
            'placeholder': 'Last Name',
            'autocomplete': 'family-name'
        })
    )
    email = forms.CharField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'id': 'id_email',
            'placeholder': 'user@example.com',
            'autocomplete': 'email'
        })
    )
    phone_number = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_phone_number',
            'placeholder': '+91 98765 43210',
            'autocomplete': 'tel'
        })
    )
    user_type = forms.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_user_type'
        }),
        help_text='Choose "Business Seller" if you own a registered shop or rental business.',
        required=True,
    )
    shop_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_shop_name',
            'placeholder': 'Shop / Business Name (Optional for individual)',
            'maxlength': '100'
        }),
        help_text='Required for Business Sellers in Pune. Optional for Individual Users.'
    )
    email_verification_token = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_email_verification_token'})
    )

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password1',
            'placeholder': 'At least 8 characters',
            'autocomplete': 'new-password'
        }),
        help_text="Your password must contain at least 8 characters."
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'id_password2',
            'placeholder': 'Re-enter password',
            'autocomplete': 'new-password'
        }),
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone_number', 'user_type')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_username',
                'placeholder': 'Choose a username',
                'autocomplete': 'username'
            }),
        }

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError("First name is required.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise forms.ValidationError("Last name is required.")
        return last_name

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError("An account with this username already exists.")
        return username

    def clean_email(self):
        raw_email = self.cleaned_data.get('email', '')
        normalized_email = validate_email_format(raw_email)
        if User.objects.filter(email__iexact=normalized_email).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError("An account with this email address already exists.")

        # Enforce email OTP verification on backend
        token = self.data.get('email_verification_token')
        if not check_email_is_verified_for_registration(normalized_email, verification_token=token):
            raise forms.ValidationError("Please verify your email address with the verification code before registering.")

        return normalized_email

    def clean_phone_number(self):
        raw_phone = self.cleaned_data.get('phone_number', '')
        normalized_phone = validate_and_normalize_indian_phone(raw_phone)
        mobile_10 = normalized_phone.replace('+91', '')
        
        # Check uniqueness across standard variations
        phone_variations = [
            normalized_phone,
            mobile_10,
            f"0{mobile_10}",
            f"+91 {mobile_10[:5]} {mobile_10[5:]}",
            f"+91 {mobile_10}",
        ]
        if User.objects.filter(phone_number__in=phone_variations).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError("An account with this phone number already exists.")
        return normalized_phone

    def clean_user_type(self):
        user_type = self.cleaned_data.get('user_type')
        if not user_type or user_type not in ('INDIVIDUAL', 'BUSINESS'):
            raise forms.ValidationError("Please select a valid account role (Individual User or Business Seller).")
        return user_type

    def clean_shop_name(self):
        shop_name = self.cleaned_data.get('shop_name', '')
        if shop_name:
            shop_name = shop_name.strip()
        if len(shop_name) > 100:
            raise forms.ValidationError("Shop or business name cannot exceed 100 characters.")
        return shop_name

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if not password1:
            raise forms.ValidationError("Password is required.")
        if not password1.strip():
            raise forms.ValidationError("Password cannot consist entirely of whitespace.")
        if len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        if len(password1) > 128:
            raise forms.ValidationError("Password cannot exceed 128 characters.")
        return password1

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        shop_name = cleaned_data.get('shop_name', '')
        if shop_name:
            shop_name = shop_name.strip()

        # Business sellers MUST provide a non-empty shop name
        if user_type == 'BUSINESS' and not shop_name:
            self.add_error('shop_name', "Shop or business name is required for Business Sellers.")

        # Validate password match
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', "Passwords do not match. Please re-enter your password.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.user_type = self.cleaned_data['user_type']
        if commit:
            user.save()
            shop_name = self.cleaned_data.get('shop_name')
            if shop_name and hasattr(user, 'profile'):
                user.profile.shop_name = shop_name
                user.profile.save()
            mark_registration_verification_used(user.email)
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number', 'avatar', 'bio')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief intro about yourself...'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('shop_name', 'shop_description', 'gst_number', 'business_registration_number', 'alternate_phone', 'emergency_contact')
        widgets = {
            'shop_name': forms.TextInput(attrs={'class': 'form-control'}),
            'shop_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'GSTIN'}),
            'business_registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ('full_name', 'phone_number', 'address_line1', 'address_line2', 'locality', 'city', 'state', 'pincode', 'is_default')
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Flat / House / Building'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street / Landmark'}),
            'locality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Kothrud, Baner, Hinjewadi'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'value': 'Pune'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'value': 'Maharashtra'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '411038'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
