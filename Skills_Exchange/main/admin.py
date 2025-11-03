from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Skill, Category, UserProfile, UserSkill, Exchange, Message

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category")
    list_filter = ("category",)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "timestamp", "is_read")
    search_fields = ("sender__username", "receiver__username", "content")
    list_filter = ("is_read", "timestamp")
    readonly_fields = ("timestamp",)

@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = (
        "exchange_summary", 
        "status", 
        "completion_indicator",
        "user1_status",
        "user2_status",
        "admin_approval_status",
        "start_date"
    )
    list_filter = (
        "status", 
        "admin_approved", 
        "user1_completed", 
        "user2_completed",
        "start_date"
    )
    search_fields = (
        "user1__username",
        "user2__username", 
        "skill1__name",
        "skill2__name"
    )
    readonly_fields = (
        "start_date",
        "last_updated",
        "user1_completed_date",
        "user2_completed_date",
        "admin_approved_date"
    )
    
    fieldsets = (
        ("Exchange Details", {
            "fields": (
                ("user1", "user2"),
                ("skill1", "skill2"),
                "status",
                "notes"
            )
        }),
        ("Completion Tracking", {
            "fields": (
                ("user1_completed", "user1_completed_date"),
                ("user2_completed", "user2_completed_date"),
            ),
            "classes": ("collapse",)
        }),
        ("Admin Controls", {
            "fields": (
                ("admin_approved", "admin_approved_date"),
                "admin_notes"
            )
        }),
        ("Timestamps", {
            "fields": (
                "start_date",
                "end_date",
                "last_updated"
            ),
            "classes": ("collapse",)
        })
    )
    
    actions = ["approve_exchanges", "mark_pending_approval", "reset_completion"]
    
    def exchange_summary(self, obj):
        return f"{obj.user1.username} ↔ {obj.user2.username}"
    exchange_summary.short_description = "Exchange"
    
    def user1_status(self, obj):
        if obj.user1_completed:
            return format_html('<span style="color: green;">✓ Completed</span>')
        return format_html('<span style="color: gray;">○ Pending</span>')
    user1_status.short_description = f"User 1 Status"
    
    def user2_status(self, obj):
        if obj.user2_completed:
            return format_html('<span style="color: green;">✓ Completed</span>')
        return format_html('<span style="color: gray;">○ Pending</span>')
    user2_status.short_description = f"User 2 Status"
    
    def admin_approval_status(self, obj):
        if obj.admin_approved:
            return format_html('<span style="color: blue;">✓ Approved</span>')
        elif obj.both_users_completed():
            return format_html('<span style="color: orange;">⚠ Needs Review</span>')
        return format_html('<span style="color: gray;">○ Not Ready</span>')
    admin_approval_status.short_description = "Admin Status"
    
    def completion_indicator(self, obj):
        status = obj.completion_status()
        colors = {
            "Admin Approved": "blue",
            "Awaiting Admin Approval": "orange",
            "Partially Complete": "purple",
            "In Progress": "gray"
        }
        color = colors.get(status, "gray")
        return format_html(f'<span style="color: {color}; font-weight: bold;">{status}</span>')
    completion_indicator.short_description = "Completion"
    
    def approve_exchanges(self, request, queryset):
        updated = 0
        for exchange in queryset:
            if exchange.both_users_completed() and not exchange.admin_approved:
                exchange.admin_approved = True
                exchange.admin_approved_date = timezone.now()
                exchange.status = "completed"
                exchange.save()
                updated += 1
        
        self.message_user(
            request,
            f"Successfully approved {updated} exchange(s). Only exchanges where both users completed were approved."
        )
    approve_exchanges.short_description = "Approve selected exchanges (both users must be complete)"
    
    def mark_pending_approval(self, request, queryset):
        updated = queryset.filter(
            user1_completed=True,
            user2_completed=True,
            admin_approved=False
        ).update(status="active")
        
        self.message_user(
            request,
            f"Marked {updated} exchange(s) as pending admin approval."
        )
    mark_pending_approval.short_description = "Hold for admin review"
    
    def reset_completion(self, request, queryset):
        updated = queryset.update(
            user1_completed=False,
            user2_completed=False,
            user1_completed_date=None,
            user2_completed_date=None,
            admin_approved=False,
            admin_approved_date=None
        )
        
        self.message_user(
            request,
            f"Reset completion status for {updated} exchange(s)."
        )
    reset_completion.short_description = "Reset completion status"

admin.site.register(Category)
admin.site.register(UserProfile)
admin.site.register(UserSkill)
