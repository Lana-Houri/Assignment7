import csv
from myapp1.models import Contact

def run():
    with open('contacts.csv', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            Contact.objects.create(
                full_name=row['name'],
                specialty=row['specialty'],
                city=row['city'],
                address=row['address'],
                rating=row.get('rating'),
                fees=row.get('fees'),
                phone=row['phone']
            )
