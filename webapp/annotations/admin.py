from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "must_change_password"]

# Research records are deliberately absent: label edits go through the audited view.
admin.site.site_header = "SycoCode · Cuentas"
admin.site.site_title = "Cuentas de SycoCode"
