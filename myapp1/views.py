from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from .models import Contact
from .form import CreateContactForm, RecommendationForm
import re
import random
import json
import hashlib

# ==================== NEW GEMINI SDK SETUP ====================
try:
    from google.genai import Client
    
    # Initialize client with API key
    client = Client(api_key=settings.GEMINI_API_KEY)
    
except ImportError:
    client = None
    print("Warning: google-genai not installed. Run: pip install -U google-genai")

# ==================== FREE AVATAR GENERATION ====================
# Using DiceBear API (completely free) with AI-powered style selection via Gemini

def select_sample_image_by_gender(doctor_name, description=""):
    """Use AI to determine gender and select appropriate sample image"""
    sample_images = [
        'sample_images/proxy-image.jpeg',
        'sample_images/proxy-image (1).jpeg',
        'sample_images/proxy-image (2).jpeg',
        'sample_images/proxy-image (3).jpeg',
        'sample_images/proxy-image (4).jpeg',
        'sample_images/proxy-image (5).jpeg',
        'sample_images/proxy-image (6).jpeg',
        'sample_images/proxy-image (7).jpeg',
    ]
    
    if not client:
        # If Gemini not available, use simple hash (not ideal but works)
        seed = hashlib.md5(doctor_name.encode()).hexdigest()
        image_index = int(seed, 16) % 8
        return sample_images[image_index]
    
    try:
        # Use Gemini to determine gender from name and description
        prompt = f"""
        Based on the doctor's name "{doctor_name}" and description "{description}",
        determine the likely gender (male or female).
        
        Respond with ONLY a JSON object:
        {{
            "gender": "male" or "female",
            "image_index": 0-7 (select an index that matches the gender)
        }}
        
        For male doctors, prefer indices: 0, 1, 2, 3
        For female doctors, prefer indices: 4, 5, 6, 7
        
        Return ONLY valid JSON, nothing else.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        result_text = response.text.strip()
        if result_text.startswith('```json'):
            result_text = result_text.split('```json')[1].split('```')[0]
        elif result_text.startswith('```'):
            result_text = result_text.split('```')[1].split('```')[0]
        
        params = json.loads(result_text.strip())
        image_index = params.get('image_index', 0) % 8
        return sample_images[image_index]
        
    except Exception as e:
        print(f"Gender detection error: {e}, using hash fallback")
        # Fallback to hash-based selection
        seed = hashlib.md5(doctor_name.encode()).hexdigest()
        image_index = int(seed, 16) % 8
        return sample_images[image_index]

def generate_avatar_from_description(description, doctor_name):
    """Generate avatar URL using free DiceBear API with AI-powered style selection.
    Falls back to sample images if APIs are unavailable."""
    
    if not client:
        # If Gemini is not available, try sample images first, then DiceBear
        try:
            # Use simple hash-based selection (not ideal but works without AI)
            seed = hashlib.md5(doctor_name.encode()).hexdigest()
            image_index = int(seed, 16) % 8
            sample_images = [
                'sample_images/proxy-image.jpeg',
                'sample_images/proxy-image (1).jpeg',
                'sample_images/proxy-image (2).jpeg',
                'sample_images/proxy-image (3).jpeg',
                'sample_images/proxy-image (4).jpeg',
                'sample_images/proxy-image (5).jpeg',
                'sample_images/proxy-image (6).jpeg',
                'sample_images/proxy-image (7).jpeg',
            ]
            avatar_url = staticfiles_storage.url(sample_images[image_index])
            return avatar_url, {"method": "sample-image", "source": "static"}
        except:
            # Final fallback to DiceBear
            seed = hashlib.md5(doctor_name.encode()).hexdigest()
            return f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}", {"method": "dicebear-simple"}
    
    try:
        # Use Gemini text model (FREE) to analyze description and choose avatar style
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
        
        # Use Gemini text model (FREE tier available)
        response = client.models.generate_content(
            model='gemini-2.5-flash',  # Free model
            contents=prompt
        )
        
        result_text = response.text.strip()
        
        # Clean response
        if result_text.startswith('```json'):
            result_text = result_text.split('```json')[1].split('```')[0]
        elif result_text.startswith('```'):
            result_text = result_text.split('```')[1].split('```')[0]
        
        params = json.loads(result_text.strip())
        
        # Generate DiceBear avatar URL (completely free API)
        style = params.get('style', 'avataaars')
        seed = params.get('seed', hashlib.md5(doctor_name.encode()).hexdigest())
        bg_color = params.get('background_color', '3b82f6')
        
        avatar_url = f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}&backgroundColor={bg_color}"
        
        params['method'] = 'dicebear-ai'
        return avatar_url, params
        
    except Exception as e:
        print(f"Avatar generation error: {e}")
        # Fallback chain: Try sample images first, then DiceBear
        try:
            # Use AI to select appropriate sample image based on gender
            selected_image = select_sample_image_by_gender(doctor_name, description)
            avatar_url = staticfiles_storage.url(selected_image)
            return avatar_url, {"method": "sample-image-fallback", "source": "static"}
        except Exception as fallback_error:
            print(f"Sample image fallback error: {fallback_error}")
            # Final fallback to DiceBear
            seed = hashlib.md5(description.encode()).hexdigest()
            return f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}", {"method": "dicebear-fallback"}

def get_sample_image():
    """Get a random sample image from static folder as fallback"""
    sample_images = [
        'sample_images/proxy-image.jpeg',
        'sample_images/proxy-image (1).jpeg',
        'sample_images/proxy-image (2).jpeg',
        'sample_images/proxy-image (3).jpeg',
        'sample_images/proxy-image (4).jpeg',
        'sample_images/proxy-image (5).jpeg',
        'sample_images/proxy-image (6).jpeg',
        'sample_images/proxy-image (7).jpeg',
    ]
    # Use hash of description/name to consistently select same image for same input
    selected_image = random.choice(sample_images)
    return staticfiles_storage.url(selected_image)

def get_random_profile_image(doctor_name=None):
    """Generate placeholder profile image URL - uses sample images with gender matching"""
    # If doctor name is provided, use gender-based selection
    if doctor_name:
        try:
            selected_image = select_sample_image_by_gender(doctor_name, "")
            return staticfiles_storage.url(selected_image)
        except:
            pass
    
    # Fallback: use random sample image
    try:
        sample_images = [
            'sample_images/proxy-image.jpeg',
            'sample_images/proxy-image (1).jpeg',
            'sample_images/proxy-image (2).jpeg',
            'sample_images/proxy-image (3).jpeg',
            'sample_images/proxy-image (4).jpeg',
            'sample_images/proxy-image (5).jpeg',
            'sample_images/proxy-image (6).jpeg',
            'sample_images/proxy-image (7).jpeg',
        ]
        selected_image = random.choice(sample_images)
        return staticfiles_storage.url(selected_image)
    except:
        # Final fallback to external API if static files not available
        num = random.randint(1, 100)
        return f"https://ui-avatars.com/api/?name=Dr+{num}&size=128&background=random&bold=true"

# ==================== EXISTING VIEWS ====================

def home(request):
    contacts = Contact.objects.all()
    for contact in contacts:
        contact.profile_image = get_random_profile_image(contact.full_name)
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
        contact.avatar_url = get_random_profile_image(contact.full_name)
    
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
        'current_avatar': getattr(contact, 'avatar_url', get_random_profile_image(contact.full_name))
    })

@csrf_exempt
def generate_avatar_api(request):
    """API endpoint for generating avatars using free DiceBear API"""
    if request.method == 'POST':
        doctor_name = 'Doctor'  # Default value
        try:
            data = json.loads(request.body)
            description = data.get('description', '')
            doctor_name = data.get('name', 'Doctor')
            
            if not description:
                return JsonResponse({
                    'error': 'Description required',
                    'avatar_url': get_random_profile_image(doctor_name)
                }, status=400)
            
            # Always use free DiceBear method
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
                'avatar_url': get_random_profile_image(doctor_name)
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
    contact.profile_image = get_random_profile_image(contact.full_name)
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
                r.profile_image = get_random_profile_image(r.full_name)
    else:
        form = RecommendationForm()
    return render(request, "myapp1/recommend.html", {"form": form, "results": results})

def search(request):
    query = request.GET.get('q', '')
    results = Contact.objects.filter(full_name__icontains=query) | \
              Contact.objects.filter(specialty__icontains=query) | \
              Contact.objects.filter(city__icontains=query)
    for r in results:
        r.profile_image = get_random_profile_image(r.full_name)
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
        profile_img = get_random_profile_image(doc.full_name)
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