from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Contact
from .form import CreateContactForm, RecommendationForm
import re
import random
import json
import hashlib
import base64
from io import BytesIO

# ==================== NEW GEMINI SDK SETUP ====================
try:
    from google import genai
    from google.genai import types
    
    # Initialize client with API key
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Text model is available via client
    imagen_available = True
    
except ImportError:
    client = None
    imagen_available = False
    print("Warning: google-genai not installed. Run: pip install -U google-genai")

# ==================== AVATAR GENERATION WITH IMAGEN 4.0 ====================

def generate_avatar_with_imagen(description, doctor_name):
    """Generate custom avatar using Imagen 4.0"""
    
    if not client or not imagen_available:
        print("Imagen not available, using fallback")
        return generate_avatar_from_description(description, doctor_name)
    
    try:
        # Create a professional prompt for Imagen
        imagen_prompt = f"""
Professional medical portrait of {doctor_name}.
{description}
Style: Clean, professional headshot, medical photography
Appearance: Professional attire (white coat or medical uniform), friendly and trustworthy expression
Background: Solid neutral color (soft blue, white, or gray), studio lighting
Quality: High detail, professional photography, portrait orientation
Mood: Approachable, professional, trustworthy, calm
Format: Square avatar, centered face, professional composition
"""
        
        # Generate image with Imagen 4.0 Ultra
        response = client.models.generate_images(
            model='imagen-4.0-ultra-generate-001',  # Highest quality Imagen model
            prompt=imagen_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                safety_filter_level="block_low_and_above",  # Only valid option
                person_generation="allow_adult",
                aspect_ratio="1:1",
            ),
        )
        
        # Get the generated image
        if response.generated_images:
            generated_image = response.generated_images[0].image
            
            # Convert PIL Image to base64
            buffered = BytesIO()
            generated_image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            # Return as data URL
            avatar_url = f"data:image/png;base64,{img_str}"
            
            return avatar_url, {
                "method": "imagen-4.0-ultra",
                "model": "imagen-4.0-ultra-generate-001",
                "prompt": imagen_prompt
            }
        else:
            raise Exception("No images generated")
            
    except Exception as e:
        print(f"Imagen generation error: {e}")
        # Fallback to DiceBear
        return generate_avatar_from_description(description, doctor_name)

def generate_avatar_from_description(description, doctor_name):
    """Generate avatar URL based on AI description (DiceBear fallback)"""
    
    if not client:
        return get_random_profile_image(), {"method": "fallback"}
    
    try:
        # Use Gemini text model to analyze description
        prompt = f"""
        Based on this doctor description: "{description}"
        
        Generate avatar parameters in JSON format:
        {{
            "style": "choose one: adventurer, avataaars, bottts, personas, lorelei, micah, pixel-art",
            "background_color": "hex color without # that matches personality",
            "seed": "unique seed based on description"
        }}
        
        Choose style based on:
        - adventurer: Professional, corporate
        - avataaars: Friendly, approachable
        - bottts: Tech-savvy, modern
        - personas: Artistic, creative
        - lorelei: Elegant, sophisticated
        - micah: Casual, relatable
        - pixel-art: Fun, young
        
        Return ONLY valid JSON, nothing else.
        """
        
        # Use generate_content via client
        response = client.models.generate_content(
            model='gemini-2.5-flash',  # Latest stable model
            contents=prompt
        )
        
        result_text = response.text.strip()
        
        # Clean response
        if result_text.startswith('```json'):
            result_text = result_text.split('```json')[1].split('```')[0]
        elif result_text.startswith('```'):
            result_text = result_text.split('```')[1].split('```')[0]
        
        params = json.loads(result_text.strip())
        
        # Generate DiceBear avatar URL
        style = params.get('style', 'avataaars')
        seed = params.get('seed', hashlib.md5(doctor_name.encode()).hexdigest())
        bg_color = params.get('background_color', '3b82f6')
        
        avatar_url = f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}&backgroundColor={bg_color}"
        
        params['method'] = 'dicebear'
        return avatar_url, params
        
    except Exception as e:
        print(f"Avatar generation error: {e}")
        seed = hashlib.md5(description.encode()).hexdigest()
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}", {"method": "fallback"}

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
    
    # Generate current avatar
    if not hasattr(contact, 'avatar_url') or not contact.avatar_url:
        contact.avatar_url = get_random_profile_image()
    
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
    
    return render(request, 'myapp1/update_contact.html', {
        'form': form, 
        'id': id,
        'contact': contact,
        'current_avatar': getattr(contact, 'avatar_url', get_random_profile_image())
    })

@csrf_exempt
def generate_avatar_api(request):
    """API endpoint for generating avatars with Imagen 4.0 or DiceBear"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            description = data.get('description', '')
            doctor_name = data.get('name', 'Doctor')
            use_imagen = data.get('use_imagen', True)
            
            if not description:
                return JsonResponse({
                    'error': 'Description required',
                    'avatar_url': get_random_profile_image()
                }, status=400)
            
            # Choose generation method
            if use_imagen and imagen_available:
                avatar_url, params = generate_avatar_with_imagen(description, doctor_name)
            else:
                avatar_url, params = generate_avatar_from_description(description, doctor_name)
            
            return JsonResponse({
                'success': True,
                'avatar_url': avatar_url,
                'params': params,
                'description': description
            })
            
        except Exception as e:
            print(f"Avatar API error: {e}")
            return JsonResponse({
                'error': str(e),
                'avatar_url': get_random_profile_image()
            }, status=500)
    
    return JsonResponse({'error': 'POST required'}, status=405)

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
        cleaned = response_text.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned.split('```json')[1].split('```')[0]
        elif cleaned.startswith('```'):
            cleaned = cleaned.split('```')[1].split('```')[0]
        
        data = json.loads(cleaned.strip())
        return data
    except json.JSONDecodeError:
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
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []
    
    if request.method == "POST":
        user_input = request.POST.get("message", "")
        
        if not client:
            return render(request, "myapp1/chatbot.html", {
                "messages": [
                    {"from": "user", "text": user_input},
                    {"from": "bot", "text": "AI service unavailable. Please install: pip install -U google-genai"}
                ]
            })
        
        chat_history = request.session.get('chat_history', [])
        context = SYSTEM_PROMPT + get_database_summary() + "\n\nConversation:\n"
        
        for msg in chat_history[-6:]:
            context += f"{msg['role']}: {msg['content']}\n"
        
        context += f"User: {user_input}\nAssistant:"
        
        try:
            # Use new SDK for text generation
            response = client.models.generate_content(
                model='gemini-2.5-flash',  # Latest stable model
                contents=context
            )
            ai_response = response.text
            
            parsed = parse_ai_response(ai_response)
            
            if parsed.get("action") == "search":
                doctors = search_doctors(parsed)
                intro_message = parsed.get("message", "Here are the doctors I found:")
                cards_html = generate_doctor_cards_html(doctors)
                bot_reply = f"<div style='margin-bottom: 12px;'>{intro_message}</div>{cards_html}"
            else:
                bot_reply = parsed.get("message", ai_response)
            
            chat_history.append({"role": "User", "content": user_input})
            chat_history.append({"role": "Assistant", "content": parsed.get("message", ai_response)})
            request.session['chat_history'] = chat_history[-20:]
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