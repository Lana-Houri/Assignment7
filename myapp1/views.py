from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Contact
from .form import CreateContactForm, RecommendationForm
import re
import json

# ---------------------------------------------------------
# HOME / CRUD VIEWS
# ---------------------------------------------------------

def home(request):
    contacts = Contact.objects.all()
    return render(request, 'myapp1/home.html', {'contacts': contacts})


def create_contact(request):
    if request.method == 'POST':
        form = CreateContactForm(request.POST)
        if form.is_valid():
            Contact.objects.create(**form.cleaned_data)
            return HttpResponseRedirect('/success/')
    else:
        form = CreateContactForm()

    return render(request, 'myapp1/create_contact.html', {'form': form})


def update_contact(request, id):
    contact = Contact.objects.get(id=id)

    if request.method == 'POST':
        form = CreateContactForm(request.POST)
        if form.is_valid():
            for field, value in form.cleaned_data.items():
                setattr(contact, field, value)
            contact.save()
            return HttpResponseRedirect('/')
    else:
        form = CreateContactForm(initial={
            'full_name': contact.full_name,
            'specialty': contact.specialty,
            'city': contact.city,
            'address': contact.address,
            'rating': contact.rating,
            'fees': contact.fees,
            'phone': contact.phone,
        })

    return render(request, 'myapp1/update_contact.html', {'form': form, 'id': id})


def delete_contact(request, id):
    contact = Contact.objects.get(id=id)
    contact.delete()
    return HttpResponseRedirect('/')


def success(request):
    return render(request, 'myapp1/success.html')


def contact_detail(request, id):
    contact = get_object_or_404(Contact, id=id)
    return render(request, 'myapp1/contact_detail.html', {'contact': contact})

# ---------------------------------------------------------
# RECOMMENDATION PAGE
# ---------------------------------------------------------

def recommend(request):
    results = []
    if request.method == "POST":
        form = RecommendationForm(request.POST)
        
        if form.is_valid():
            specialty = form.cleaned_data.get('specialty')
            city = form.cleaned_data.get('city')
            max_fees = form.cleaned_data.get('max_fees')
            min_rating = form.cleaned_data.get('min_rating')

            results = Contact.objects.all()

            if specialty:
                results = results.filter(specialty__icontains=specialty)

            if city:
                results = results.filter(city__icontains=city)

            if max_fees:
                results = results.filter(fees__lte=max_fees)

            if min_rating:
                results = results.filter(rating__gte=min_rating)

            results = results.order_by('-rating', 'fees')

    else:
        form = RecommendationForm()

    return render(request, "myapp1/recommend.html", {
        "form": form,
        "results": results
    })

# ---------------------------------------------------------
# SEARCH PAGE
# ---------------------------------------------------------

def search(request):
    query = request.GET.get('q', '')

    results = Contact.objects.filter(
        full_name__icontains=query
    ) | Contact.objects.filter(
        specialty__icontains=query
    ) | Contact.objects.filter(
        city__icontains=query
    )

    return render(request, "myapp1/search.html", {
        "query": query,
        "results": results
    })

# ---------------------------------------------------------
# CHATBOT LOGIC
# ---------------------------------------------------------

def run_doctor_query(filters):
    qs = Contact.objects.all()

    if filters.get("specialty"):
        qs = qs.filter(specialty__icontains=filters["specialty"])

    if filters.get("city"):
        qs = qs.filter(city__icontains=filters["city"])

    if filters.get("max_fees"):
        qs = qs.filter(fees__lte=filters["max_fees"])

    if filters.get("min_rating"):
        qs = qs.filter(rating__gte=filters["min_rating"])

    return qs


# -------------------------------
# FIXED & IMPROVED PARSER
# -------------------------------

def parse_user_query(message):
    import re
    msg = message.lower()

    # -----------------------
    # SPECIALTY DICTIONARY
    # -----------------------
    specialty_map = {
        "pediatrician": ["pediatric", "pediatrics", "children", "kid", "child"],
        "cardiologist": ["cardio", "heart"],
        "dermatologist": ["derma", "skin"],
        "surgeon": ["surgeon", "surgery"],
        "neurologist": ["neuro", "brain"],
        "psychiatrist": ["psych", "mental"],
        "dentist": ["dent", "teeth"],
        "orthopedic": ["ortho", "bone"],
        "oncologist": ["onco", "cancer"],
        "urologist": ["uro", "urinary"],
        "gynecologist": ["gyne", "women"],
        "endocrinologist": ["endo", "hormone"],
    }

    specialty = None
    for key, keywords in specialty_map.items():
        for k in keywords:
            if k in msg:
                specialty = key
                break

    # -----------------------
    # CITY DETECTION
    # -----------------------
    city = None
    match_city = re.search(r"(in|from)\s+([a-zA-Z]+)", msg)
    if match_city:
        city = match_city.group(2).capitalize()

    # -----------------------
    # FEES
    # -----------------------
    max_fees = None
    fees_match = re.search(r"(under|below|less than)\s+(\d+)", msg)
    if fees_match:
        max_fees = int(fees_match.group(2))

    # -----------------------
    # RATING
    # -----------------------
    min_rating = None
    rating_match = re.search(r"(above|over|higher than)\s+(\d\.\d)", msg)
    if rating_match:
        min_rating = float(rating_match.group(2))

    return {
        "specialty": specialty,
        "city": city,
        "max_fees": max_fees,
        "min_rating": min_rating,
    }


# ---------------------------------------------------------
# CHATBOT VIEW
# ---------------------------------------------------------

@csrf_exempt
def chatbot(request):
    if request.method == "POST":
        user_input = request.POST.get("message", "")

        filters = parse_user_query(user_input)
        qs = run_doctor_query(filters)

        if qs.exists():
            cards_html = "".join([
                f"""
                <div class="chat-card">
                    <div class="chat-card-name">{doc.full_name}</div>
                    <div class="chat-card-line">{doc.specialty} • {doc.city}</div>
                    <div class="chat-card-line">Fees: {doc.fees} | Rating: {doc.rating}</div>
                    <a class="chat-card-link" href="{reverse('contact_detail', args=[doc.id])}">View profile →</a>
                </div>
                """
                for doc in qs
            ])
            bot_reply = (
                "Here are the matching doctors:<div class=\"chat-card-list\">"
                f"{cards_html}"
                "</div>"
            )
        else:
            bot_reply = "No doctors match your request."

        return render(request, "myapp1/chatbot.html", {
            "messages": [
                {"from": "you", "text": user_input},
                {"from": "bot", "text": bot_reply},
            ]
        })

    return render(request, "myapp1/chatbot.html")
