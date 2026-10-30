from django import forms
from .models import HandoverLog, Review


class HandoverLogForm(forms.ModelForm):
    class Meta:
        model = HandoverLog
        fields = ['log_type', 'item_condition', 'notes', 'evidence_photo']
        widgets = {
            'log_type': forms.Select(attrs={'class': 'form-select'}),
            'item_condition': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe current physical appearance, accessories present, and operating status...'}),
            'evidence_photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(5, '5 Stars - Outstanding'), (4, '4 Stars - Great'), (3, '3 Stars - Satisfactory'), (2, '2 Stars - Poor'), (1, '1 Star - Terrible')],
                attrs={'class': 'form-select'},
            ),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Prompt handover, camera was like new!'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Share your authentic experience with the item and lender/buyer...'}),
        }
