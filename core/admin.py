from django.contrib import admin

from .models import Greeting


@admin.register(Greeting)
class GreetingAdmin(admin.ModelAdmin):
    fields = ("when",)
    readonly_fields = ("when",)
    # list_display = ("when",)
