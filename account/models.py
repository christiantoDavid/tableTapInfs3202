from django.db import models

class Account(models.Model):
    user_id = models.AutoField(primary_key=True)    # PK
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)     # store hashed password
    photo_profile = models.ImageField(upload_to='profiles/', null=True, blank=True)

    def __str__(self):
        return self.username
