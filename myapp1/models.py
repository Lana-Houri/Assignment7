from django.db import models

class Contact(models.Model):
    full_name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    rating = models.FloatField(null=True, blank=True)
    fees = models.IntegerField(null=True, blank=True)
    phone = models.CharField(max_length=40)

