from django.contrib import admin

from .models import (
    PBotLog,
    PBotWhitelistEmail,
    PBotWhitelistStats,
)


@admin.register(PBotLog)
class PBotLogAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'created', 'archived_path')
    readonly_fields = ('request_user', 'message', 'archived_path')
    search_fields = ('request_user', 'message')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PBotWhitelistEmailInline(admin.StackedInline):
    model = PBotWhitelistEmail


@admin.register(PBotWhitelistStats)
class PBotWhitelistStatsAdmin(admin.ModelAdmin):
    inlines = (PBotWhitelistEmailInline, )
