from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Profiles, Users, OrganizerRequests, UserRentals, Rental

class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Повтор пароля")

    class Meta:
        model = Users
        fields = ['username', 'email']

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned

    def save(self, commit=True):
        user = Users(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
        )
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
        
class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Имя пользователя')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profiles
        fields = ['phone']
        
class OrganizerRequestForm(forms.ModelForm):
    class Meta:
        model = OrganizerRequests
        fields = ['name', 'phone', 'email']
class RentalForm(forms.ModelForm):
    class Meta:
        model = UserRentals
        fields = ["start_datetime", "end_datetime", "size"]

    def __init__(self, *args, **kwargs):
        rental = kwargs.pop("rental", None)
        super().__init__(*args, **kwargs)

        if rental and rental.sizes.exists():
            self.fields["size"].queryset = rental.sizes.filter(quantity__gt=0)
        else:
            self.fields["size"].widget = forms.HiddenInput()