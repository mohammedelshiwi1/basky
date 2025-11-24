from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
# Create your views here.
def main_page(request):
    return render(request,"index.html")

def login_page(request):
     if request.method == "POST":
        email = request.POST.get('email').strip().lower()
        password = request.POST.get('password')
        remember = request.POST.get('remember')  # checkbox

        user = authenticate(request, email=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)

                # لو مش مختار "تذكرني" → السيشن ينتهي لما يقفل المتصف
                
                return redirect('/devices/device_setup')  # غيرها للاسم اللي عايزه (مثلاً 'dashboard')
            else:
                messages.error(request, "الحساب معطل، تواصل مع الإدارة.")
        else:
            messages.error(request, "البريد الإلكتروني أو كلمة المرور غير صحيحة")

     return render(request, 'login.html')

def signup_page(request):
      return render(request,'signup.html')