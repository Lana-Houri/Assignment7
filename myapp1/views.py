from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Contact
from .form import CreateContactForm, RecommendationForm
import re
import random
import json

# ==================== GEMINI API SETUP ====================
try:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')  # Updated model name
except ImportError:
    model = None
    print("Warning: google-generativeai not installed. Run: pip install google-generativeai")

# ==================== PROFILE IMAGE HELPER ====================

def get_random_profile_image():
    """Generate placeholder profile image URL"""
    num = random.randint(1, 100)
    return f"https://ui-avatars.com/api/?name=Dr+{num}&size=128&background=random&bold=true"

# ==================== EXISTING VIEWS ====================

def home(request):
    contacts = Contact.objects.all()
    for contact in contacts:
        contact.profile_image = get_random_profile_image()
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
    contact.profile_image = get_random_profile_image()
    return render(request, 'myapp1/contact_detail.html', {'contact': contact})

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
            for r in results:
                r.profile_image = get_random_profile_image()
    else:
        form = RecommendationForm()
    return render(request, "myapp1/recommend.html", {"form": form, "results": results})

def search(request):
    query = request.GET.get('q', '')
    results = Contact.objects.filter(full_name__icontains=query) | \
              Contact.objects.filter(specialty__icontains=query) | \
              Contact.objects.filter(city__icontains=query)
    for r in results:
        r.profile_image = get_random_profile_image()
    return render(request, "myapp1/search.html", {"query": query, "results": results})

# ==================== AI CHATBOT WITH GEMINI ====================

SYSTEM_PROMPT = """You are an AI medical assistant for MediConnect, a doctor finder platform.

Your capabilities:
1. Help users find doctors by understanding natural language queries
2. Search the database when users ask for doctor recommendations
3. Provide friendly, helpful medical guidance (not medical advice)

When users ask to find doctors, you should:
- Extract: specialty, city, max fees, min rating from their query
- Respond in JSON format for database search
- After showing results, continue natural conversation

Response Formats:

1. FOR DOCTOR SEARCH (when user asks to find/search/show doctors):
Respond ONLY with valid JSON:
{
    "action": "search",
    "specialty": "pediatrician" or null,
    "city": "New York" or null,
    "max_fees": 200 or null,
    "min_rating": 4.5 or null,
    "message": "Looking for pediatricians in New York..."
}

2. FOR REGULAR CONVERSATION:
{
    "action": "chat",
    "message": "Your friendly response here"
}

Examples:
User: "Find me a cardiologist in Chicago under $200"
You: {"action": "search", "specialty": "cardiologist", "city": "Chicago", "max_fees": 200, "min_rating": null, "message": "Searching for affordable cardiologists in Chicago..."}

User: "What's the difference between a dermatologist and a pediatrician?"
You: {"action": "chat", "message": "A dermatologist specializes in skin conditions, while a pediatrician focuses on children's health. Would you like me to find either one for you?"}

User: "Show me top rated surgeons"
You: {"action": "search", "specialty": "surgeon", "city": null, "max_fees": null, "min_rating": 4.5, "message": "Finding top-rated surgeons for you..."}

IMPORTANT:
- Always respond with valid JSON only
- Never include markdown, code blocks, or extra text
- Be conversational but concise
- Encourage users to search for doctors when appropriate
"""

def get_database_summary():
    """Get quick database summary for AI context"""
    try:
        total = Contact.objects.count()
        specialties = list(Contact.objects.values_list('specialty', flat=True).distinct()[:10])
        cities = list(Contact.objects.values_list('city', flat=True).distinct()[:10])
        return f"\nDatabase: {total} doctors. Specialties: {', '.join(specialties)}. Cities: {', '.join(cities)}."
    except:
        return ""

def parse_ai_response(response_text):
    """Parse AI JSON response"""
    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned.split('```json')[1].split('```')[0]
        elif cleaned.startswith('```'):
            cleaned = cleaned.split('```')[1].split('```')[0]
        
        data = json.loads(cleaned.strip())
        return data
    except json.JSONDecodeError:
        # Fallback to chat mode if JSON parsing fails
        return {
            "action": "chat",
            "message": response_text
        }

def search_doctors(filters):
    """Search doctors based on AI-extracted filters"""
    qs = Contact.objects.all()
    
    if filters.get("specialty"):
        qs = qs.filter(specialty__icontains=filters["specialty"])
    if filters.get("city"):
        qs = qs.filter(city__icontains=filters["city"])
    if filters.get("max_fees"):
        qs = qs.filter(fees__lte=filters["max_fees"])
    if filters.get("min_rating"):
        qs = qs.filter(rating__gte=filters["min_rating"])
    
    return qs.order_by('-rating', 'fees')[:10]

def generate_doctor_cards_html(doctors):
    """Generate HTML for doctor result cards"""
    if not doctors:
        return "<p>No doctors found matching your criteria. Try adjusting your search!</p>"
    
    cards_html = ""
    for doc in doctors:
        profile_img = get_random_profile_image()
        cards_html += f"""
        <div class="doctor-result">
            <img src="{profile_img}" alt="{doc.full_name}" class="result-avatar">
            <div class="result-info">
                <div class="result-name">{doc.full_name}</div>
                <div class="result-specialty">{doc.specialty}</div>
                <div class="result-details">
                    <div class="result-detail">📍 {doc.city}</div>
                    <div class="result-detail">⭐ {doc.rating}</div>
                    <div class="result-detail">💵 ${doc.fees}</div>
                </div>
                <a class="result-link" href="/profile/{doc.id}/">View Profile →</a>
            </div>
        </div>
        """
    return cards_html

@csrf_exempt
def chatbot(request):
    # Initialize chat history in session
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []
    
    if request.method == "POST":
        user_input = request.POST.get("message", "")
        
        if not model:
            # Fallback if Gemini not available
            return render(request, "myapp1/chatbot.html", {
                "messages": [
                    {"from": "user", "text": user_input},
                    {"from": "bot", "text": "AI service unavailable. Please install: pip install google-generativeai"}
                ]
            })
        
        # Build conversation context
        chat_history = request.session.get('chat_history', [])
        context = SYSTEM_PROMPT + get_database_summary() + "\n\nConversation:\n"
        
        for msg in chat_history[-6:]:  # Last 6 messages for context
            context += f"{msg['role']}: {msg['content']}\n"
        
        context += f"User: {user_input}\nAssistant:"
        
        try:
            # Call Gemini API
            response = model.generate_content(context)
            ai_response = response.text
            
            # Parse AI response
            parsed = parse_ai_response(ai_response)
            
            # Handle different actions
            if parsed.get("action") == "search":
                # Search database
                doctors = search_doctors(parsed)
                
                # Generate response with doctor cards
                intro_message = parsed.get("message", "Here are the doctors I found:")
                cards_html = generate_doctor_cards_html(doctors)
                bot_reply = f"<div style='margin-bottom: 12px;'>{intro_message}</div>{cards_html}"
                
            else:  # action == "chat"
                bot_reply = parsed.get("message", ai_response)
            
            # Save to chat history
            chat_history.append({"role": "User", "content": user_input})
            chat_history.append({"role": "Assistant", "content": parsed.get("message", ai_response)})
            request.session['chat_history'] = chat_history[-20:]  # Keep last 20 messages
            request.session.modified = True
            
            return render(request, "myapp1/chatbot.html", {
                "messages": [
                    {"from": "user", "text": user_input},
                    {"from": "bot", "text": bot_reply},
                ]
            })
            
        except Exception as e:
            return render(request, "myapp1/chatbot.html", {
                "messages": [
                    {"from": "user", "text": user_input},
                    {"from": "bot", "text": f"Sorry, I encountered an error: {str(e)}"}
                ]
            })
    
    return render(request, "myapp1/chatbot.html")