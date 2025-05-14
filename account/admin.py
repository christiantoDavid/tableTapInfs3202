from django.contrib import admin
from .models import Account

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display   = ('username', 'email')
    search_fields  = ('username', 'email')
    readonly_fields= ('user_id',)
