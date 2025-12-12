
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100)
    address = forms.CharField(widget=forms.Textarea)
    age = forms.IntegerField()

    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'address', 'email', 'age', 'password1', 'password2')

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
