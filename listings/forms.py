from decimal import Decimal
from django import forms
from .models import Listing, ListingImage, ListingReport, Category


class ListingForm(forms.ModelForm):
    primary_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'id_image', 'accept': 'image/*'}),
        help_text='Upload main photo for your product (JPG, PNG)',
    )
    rent_security_deposit = forms.DecimalField(
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Refundable deposit (e.g. 2000)'}),
    )
    borrow_security_deposit = forms.DecimalField(
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional deposit if strictly necessary (₹)'}),
    )
    min_rental_days = forms.IntegerField(
        required=False,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
    )
    max_rental_days = forms.IntegerField(
        required=False,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'value': 30}),
    )
    borrow_max_days = forms.IntegerField(
        required=False,
        initial=7,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'value': 7}),
    )

    class Meta:
        model = Listing
        fields = [
            'title', 'category', 'description', 'item_condition',
            'locality', 'pincode', 'pickup_available', 'delivery_available',
            'can_rent', 'rent_price_per_day', 'rent_price_per_week', 'rent_security_deposit', 'min_rental_days', 'max_rental_days', 'rental_cancellation_policy',
            'can_borrow', 'borrow_security_deposit', 'borrow_max_days', 'borrow_return_conditions',
            'can_sell', 'sell_price', 'sell_price_negotiable', 'quantity',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Sony Alpha A7 IV Camera Kit'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed specifications, inclusions, accessories, and condition...'}),
            'item_condition': forms.Select(attrs={'class': 'form-select'}),
            'locality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Kothrud, Baner, Hinjewadi'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '411038'}),
            'pickup_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'delivery_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),

            # Rent mode
            'can_rent': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_can_rent'}),
            'rent_price_per_day': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '₹ Per Day (e.g. 500)'}),
            'rent_price_per_week': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '₹ Per Week (optional)'}),
            'rent_security_deposit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Refundable deposit (e.g. 2000)'}),
            'min_rental_days': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
            'max_rental_days': forms.NumberInput(attrs={'class': 'form-control', 'value': 30}),
            'rental_cancellation_policy': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Cancellation terms'}),

            # Borrow mode
            'can_borrow': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_can_borrow'}),
            'borrow_security_deposit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional deposit if strictly necessary (₹)'}),
            'borrow_max_days': forms.NumberInput(attrs={'class': 'form-control', 'value': 7}),
            'borrow_return_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Cleanliness, handling, and return care requirements'}),

            # Sell mode
            'can_sell': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_can_sell'}),
            'sell_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Selling Price in ₹'}),
            'sell_price_negotiable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
        }

    def clean(self):
        cleaned_data = super().clean()
        can_rent = cleaned_data.get('can_rent')
        can_borrow = cleaned_data.get('can_borrow')
        can_sell = cleaned_data.get('can_sell')

        if not (can_rent or can_borrow or can_sell):
            raise forms.ValidationError("You must enable at least one listing mode (Rent, Borrow, or Sell).")

        if can_rent:
            rent_price = cleaned_data.get('rent_price_per_day')
            if not rent_price or rent_price <= 0:
                self.add_error('rent_price_per_day', 'Please specify a positive daily rental price.')
            if cleaned_data.get('rent_security_deposit') is None:
                cleaned_data['rent_security_deposit'] = Decimal('0.00')

        if can_borrow:
            if cleaned_data.get('borrow_security_deposit') is None:
                cleaned_data['borrow_security_deposit'] = Decimal('0.00')

        if can_sell:
            sell_price = cleaned_data.get('sell_price')
            if not sell_price or sell_price <= 0:
                self.add_error('sell_price', 'Please specify a positive selling price.')

        if not cleaned_data.get('min_rental_days'):
            cleaned_data['min_rental_days'] = 1
        if not cleaned_data.get('max_rental_days'):
            cleaned_data['max_rental_days'] = 30
        if not cleaned_data.get('borrow_max_days'):
            cleaned_data['borrow_max_days'] = 7

        return cleaned_data


class ListingReportForm(forms.ModelForm):
    class Meta:
        model = ListingReport
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Provide specific details regarding the violation or dispute...'}),
        }
