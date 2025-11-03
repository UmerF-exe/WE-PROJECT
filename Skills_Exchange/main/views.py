# Django core imports
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.forms import modelformset_factory
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

# Local imports
from .models import (
    UserProfile,
    Skill,
    UserSkill,
    Category,
    Exchange,
    Message,
)
from .forms import UserProfileForm

User = get_user_model()


def signup_view(request):
    if request.method == "POST":
        name = request.POST.get("fullname", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm", "")

        # Validation
        if not name or not email or not password:
            messages.error(request, "All fields are required!")
            return redirect("signup")

        if password != confirm:
            messages.error(request, "Passwords do not match!")
            return redirect("signup")

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long!")
            return redirect("signup")

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address!")
            return redirect("signup")

        if User.objects.filter(username=email).exists():
            messages.error(request, "Email is already registered!")
            return redirect("signup")

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name.split(" ")[0] if name else "",
            last_name=(
                " ".join(name.split(" ")[1:]) if name and len(name.split()) > 1 else ""
            ),
        )
        user.save()

        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")

    return render(request, "signup.html")


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Logged in successfully!")
            return redirect("marketplace")
        else:
            messages.error(request, "Invalid email or password!")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("index")


def index_view(request):
    return render(request, "index.html")


@login_required
def marketplace_view(request):
    # Get all categories for sidebar
    categories = Category.objects.all()

    # Define level choices
    levels = ["Any", "Beginner", "Intermediate", "Advanced", "Expert"]

    # Read selected filters from query (?category=1&level=Beginner)
    category_id = request.GET.get("category")
    level = request.GET.get("level")

    # Start with all offered skills (exclude current user) with optimized queries
    offered_skills = (
        UserSkill.objects.filter(role="offer")
        .exclude(user=request.user)
        .select_related("user", "user__userprofile", "skill", "skill__category")
    )

    # Apply category filter if not empty or "All"
    if category_id and category_id.lower() != "all":
        offered_skills = offered_skills.filter(skill__category_id=category_id)

    # Apply skill level filter if not empty or "Any"
    if level and level.lower() != "any":
        offered_skills = offered_skills.filter(proficiency__iexact=level)

    # Prepare context
    context = {
        "categories": categories,
        "skills": offered_skills,
        "levels": levels,
        "selected_category": category_id or "all",
        "selected_level": level or "any",
    }

    return render(request, "marketplace.html", context)


@staff_member_required
def admin_dashboard(request):
    total_users = User.objects.count()
    active_exchanges = Exchange.objects.filter(status="active").count()
    pending_exchanges = Exchange.objects.filter(status="pending").count()
    completed_exchanges = Exchange.objects.filter(status="completed").count()
    recent_users = User.objects.order_by("-date_joined")[:5]

    context = {
        "total_users": total_users,
        "active_exchanges": active_exchanges,
        "pending_issues": pending_exchanges,
        "completed_exchanges": completed_exchanges,
        "recent_users": recent_users,
    }
    return render(request, "admin_dashboard.html", context)


@staff_member_required
def admin_users(request):
    query = request.GET.get("q", "")
    if query:
        users = User.objects.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
        ).order_by("-date_joined")
    else:
        users = User.objects.all().order_by("-date_joined")
    return render(request, "admin_users.html", {"users": users})


@staff_member_required
def admin_exchanges(request):
    status_filter = request.GET.get("status", "all")

    exchanges = Exchange.objects.all().select_related(
        "user1", "user2", "user1__userprofile", "user2__userprofile", "skill1", "skill2"
    )

    if status_filter and status_filter != "all":
        exchanges = exchanges.filter(status=status_filter)

    exchanges = exchanges.order_by("-start_date")

    context = {
        "exchanges": exchanges,
        "status_filter": status_filter,
    }
    return render(request, "admin_exchanges.html", context)


@staff_member_required
@require_POST
def admin_approve_exchange(request, exchange_id):
    """Admin approves a completed exchange (POST only with CSRF)."""
    exchange = get_object_or_404(Exchange, id=exchange_id)
    
    if not exchange.both_users_completed():
        messages.error(
            request,
            "Cannot approve: Both users must complete their parts first."
        )
        return redirect("admin_exchanges")
    
    if exchange.admin_approved:
        messages.info(request, "This exchange has already been approved.")
        return redirect("admin_exchanges")
    
    exchange.admin_approved = True
    exchange.admin_approved_date = timezone.now()
    exchange.status = "completed"
    exchange.save()
    
    messages.success(
        request,
        f"Exchange between {exchange.user1.username} and {exchange.user2.username} has been approved and marked as completed!"
    )
    return redirect("admin_exchanges")


@staff_member_required
@require_POST
def admin_delete_user(request, user_id):
    """Delete a user (POST only for CSRF protection)"""
    user_to_delete = get_object_or_404(User, id=user_id)

    # Prevent deleting yourself
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete your own account!")
        return redirect("admin_users")

    username = user_to_delete.username
    user_to_delete.delete()
    messages.success(request, f"User '{username}' has been deleted successfully.")
    return redirect("admin_users")


@staff_member_required
@require_POST
def admin_toggle_staff(request, user_id):
    """Toggle user staff status (POST only for CSRF protection)"""
    user_to_toggle = get_object_or_404(User, id=user_id)

    # Prevent removing your own staff status
    if user_to_toggle == request.user:
        messages.error(request, "You cannot change your own staff status!")
        return redirect("admin_users")

    user_to_toggle.is_staff = not user_to_toggle.is_staff
    user_to_toggle.is_superuser = user_to_toggle.is_staff
    user_to_toggle.save()

    status = "Admin" if user_to_toggle.is_staff else "Regular User"
    messages.success(request, f"User '{user_to_toggle.username}' is now a {status}.")
    return redirect("admin_users")


@login_required
def profile_view(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # Redirect to profile creation page if profile not found
    try:
        profile = UserProfile.objects.select_related("user").get(user=user)
    except UserProfile.DoesNotExist:
        # If current logged-in user is viewing their own profile
        if request.user == user:
            return redirect("create_profile")
        else:
            # Show 404 if trying to view someone else's missing profile
            return render(request, "profile_not_found.html", {"profile_user": user})

    # Fetch offered and wanted skills
    offered_skills = UserSkill.objects.filter(user=user, role="offer").select_related(
        "skill"
    )
    wanted_skills = UserSkill.objects.filter(user=user, role="seek").select_related(
        "skill"
    )

    context = {
        "profile_user": user,
        "profile": profile,
        "offered_skills": offered_skills,
        "wanted_skills": wanted_skills,
    }

    return render(request, "profile.html", context)


@login_required
def create_profile(request):
    if hasattr(request.user, "userprofile"):
        messages.info(request, "You already have a profile.")
        return redirect("profile", user_id=request.user.id)

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, "Profile created successfully!")
            return redirect("profile", user_id=request.user.id)
    else:
        form = UserProfileForm()

    return render(request, "create_profile.html", {"form": form})


@login_required
def dashboard_view(request):
    user = request.user

    pending_requests = Exchange.objects.filter(
        user2=user, status="pending"
    ).select_related("user1", "user1__userprofile", "skill1", "skill2")

    # Calculate profile completion
    profile_completion = 0
    if hasattr(user, "userprofile"):
        profile = user.userprofile
        total_fields = 4
        filled_fields = 0
        if profile.full_name:
            filled_fields += 1
        if profile.bio:
            filled_fields += 1
        if profile.location:
            filled_fields += 1
        if profile.certifications:
            filled_fields += 1
        profile_completion = int((filled_fields / total_fields) * 100)

    # Get recent activities from actual exchanges
    recent_activities = []
    recent_exchanges = (
        Exchange.objects.filter(Q(user1=user) | Q(user2=user))
        .select_related(
            "user1",
            "user2",
            "user1__userprofile",
            "user2__userprofile",
            "skill1",
            "skill2",
        )
        .order_by("-last_updated")[:5]
    )

    for exchange in recent_exchanges:
        other_user = exchange.user2 if exchange.user1 == user else exchange.user1
        other_user_name = (
            other_user.userprofile.full_name
            if hasattr(other_user, "userprofile") and other_user.userprofile.full_name
            else other_user.username
        )

        if exchange.status == "active":
            if exchange.user1 == user:
                skill_learning = exchange.skill2.name
            else:
                skill_learning = exchange.skill1.name
            recent_activities.append(
                {
                    "icon": "fa-handshake text-white",
                    "title": "Active Exchange",
                    "description": f"Exchanging skills with {other_user_name}",
                    "time": f"{(exchange.last_updated).strftime('%b %d, %Y')}",
                }
            )
        elif exchange.status == "pending":
            if exchange.user1 == user:
                recent_activities.append(
                    {
                        "icon": "fa-clock",
                        "title": "Exchange Pending",
                        "description": f"Waiting for {other_user_name} to respond",
                        "time": f"{(exchange.start_date).strftime('%b %d, %Y')}",
                    }
                )
        elif exchange.status == "completed":
            recent_activities.append(
                {
                    "icon": "fa-check-circle",
                    "title": "Exchange Completed",
                    "description": f"Completed exchange with {other_user_name}",
                    "time": f"{(exchange.last_updated).strftime('%b %d, %Y')}",
                }
            )

    # Find potential matches based on complementary skills
    my_seeking_skills = UserSkill.objects.filter(user=user, role="seek").values_list(
        "skill_id", flat=True
    )
    my_offering_skills = UserSkill.objects.filter(user=user, role="offer").values_list(
        "skill_id", flat=True
    )

    matches = []
    if my_seeking_skills and my_offering_skills:
        # Find users who offer what I seek and seek what I offer
        potential_matches = (
            UserSkill.objects.filter(skill_id__in=my_seeking_skills, role="offer")
            .exclude(user=user)
            .select_related("user", "user__userprofile", "skill")[:10]
        )

        for match_skill in potential_matches:
            other_user = match_skill.user
            # Check if they seek what I offer
            their_seeking = (
                UserSkill.objects.filter(
                    user=other_user, role="seek", skill_id__in=my_offering_skills
                )
                .select_related("skill")
                .first()
            )

            if their_seeking:
                name = (
                    other_user.userprofile.full_name
                    if hasattr(other_user, "userprofile")
                    and other_user.userprofile.full_name
                    else other_user.username
                )
                initials = name[:2].upper() if len(name) >= 2 else name[:1].upper()
                matches.append(
                    {
                        "initials": initials,
                        "name": name,
                        "user_id": other_user.id,
                        "offer": match_skill.skill.name,
                        "want": their_seeking.skill.name,
                    }
                )
                if len(matches) >= 3:
                    break

    context = {
        "offered_skills": UserSkill.objects.filter(user=user, role="offer").count(),
        "learning_skills": UserSkill.objects.filter(user=user, role="seek").count(),
        "active_exchanges": Exchange.objects.filter(
            Q(user1=user, status="active") | Q(user2=user, status="active")
        ).count(),
        "pending_requests": pending_requests,
        "profile_completion": profile_completion,
        "recent_activities": recent_activities,
        "matches": matches,
    }

    return render(request, "dashboard.html", context)


@login_required
def exchanges_view(request):
    """Display all exchanges for the current user."""
    user = request.user

    all_exchanges = (
        Exchange.objects.filter(Q(user1=user) | Q(user2=user))
        .select_related(
            "user1",
            "user2",
            "user1__userprofile",
            "user2__userprofile",
            "skill1",
            "skill2",
        )
        .order_by("-start_date")
    )

    pending_exchanges = []
    active_exchanges = []
    completed_exchanges = []
    other_exchanges = []

    for exchange in all_exchanges:
        other_user = exchange.user2 if exchange.user1 == user else exchange.user1
        other_user_name = (
            other_user.userprofile.full_name
            if hasattr(other_user, "userprofile") and other_user.userprofile.full_name
            else other_user.username
        )

        is_initiator = exchange.user1 == user

        my_completed = exchange.user1_completed if is_initiator else exchange.user2_completed
        their_completed = exchange.user2_completed if is_initiator else exchange.user1_completed
        
        exchange_data = {
            "id": exchange.id,
            "other_user": other_user,
            "other_user_name": other_user_name,
            "is_initiator": is_initiator,
            "my_skill": exchange.skill1 if is_initiator else exchange.skill2,
            "their_skill": exchange.skill2 if is_initiator else exchange.skill1,
            "status": exchange.status,
            "start_date": exchange.start_date,
            "last_updated": exchange.last_updated,
            "notes": exchange.notes,
            "my_completed": my_completed,
            "their_completed": their_completed,
            "admin_approved": exchange.admin_approved,
            "completion_status": exchange.completion_status(),
        }

        if exchange.status == "pending":
            pending_exchanges.append(exchange_data)
        elif exchange.status == "active":
            active_exchanges.append(exchange_data)
        elif exchange.status == "completed":
            completed_exchanges.append(exchange_data)
        else:
            other_exchanges.append(exchange_data)

    context = {
        "pending_exchanges": pending_exchanges,
        "active_exchanges": active_exchanges,
        "completed_exchanges": completed_exchanges,
        "other_exchanges": other_exchanges,
        "total_count": all_exchanges.count(),
    }

    return render(request, "exchanges.html", context)


@login_required
def start_exchange(request, user_id, skill_id):
    """Initiate an exchange with another user."""
    other_user_skill = get_object_or_404(UserSkill, id=skill_id, user_id=user_id)
    current_user = request.user

    teach_skill = UserSkill.objects.filter(user=current_user, role="offer").first()
    if not teach_skill:
        messages.error(
            request, "You must add a skill you can offer before starting an exchange."
        )
        return redirect("dashboard")

    exchange = Exchange.objects.create(
        user1=current_user,
        user2=other_user_skill.user,
        skill1=teach_skill.skill,
        skill2=other_user_skill.skill,
        status="pending",
    )

    messages.success(
        request, f"Exchange request sent to {other_user_skill.user.username}!"
    )
    return redirect("dashboard")


@login_required
def manage_skills(request):
    SkillFormSet = modelformset_factory(
        UserSkill,
        fields=("skill", "role", "proficiency", "experience_years"),
        extra=1,
        can_delete=True,
    )

    queryset = UserSkill.objects.filter(user=request.user)
    if request.method == "POST":
        formset = SkillFormSet(request.POST, queryset=queryset)

        if formset.is_valid():
            # Save new or updated skills
            instances = formset.save(commit=False)
            for instance in instances:
                instance.user = request.user
                instance.save()

            # Delete those marked for removal
            for obj in formset.deleted_objects:
                obj.delete()

            return redirect("profile", user_id=request.user.id)
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        formset = SkillFormSet(queryset=queryset)

    return render(request, "manage_skills.html", {"formset": formset})


@login_required
def propose_exchange_view(request, user_skill_id):
    """View to propose a skill exchange with another user."""
    other_user_skill = get_object_or_404(
        UserSkill.objects.select_related("user", "user__userprofile", "skill"),
        id=user_skill_id,
        role="offer",
    )

    if other_user_skill.user == request.user:
        messages.error(request, "You cannot propose an exchange with yourself!")
        return redirect("marketplace")

    my_offered_skills = UserSkill.objects.filter(
        user=request.user, role="offer"
    ).select_related("skill")

    if request.method == "POST":
        my_skill_id = request.POST.get("my_skill")
        notes = request.POST.get("notes", "")

        if not my_skill_id:
            messages.error(request, "Please select a skill you want to offer.")
            return redirect("propose_exchange", user_skill_id=user_skill_id)

        my_skill = get_object_or_404(
            UserSkill, id=my_skill_id, user=request.user, role="offer"
        )

        exchange = Exchange.objects.create(
            user1=request.user,
            user2=other_user_skill.user,
            skill1=my_skill.skill,
            skill2=other_user_skill.skill,
            status="pending",
            notes=notes,
        )

        messages.success(
            request,
            f"Exchange proposal sent to {other_user_skill.user.userprofile.full_name if hasattr(other_user_skill.user, 'userprofile') and other_user_skill.user.userprofile.full_name else other_user_skill.user.username}!",
        )
        return redirect("dashboard")

    context = {
        "other_user_skill": other_user_skill,
        "my_offered_skills": my_offered_skills,
    }

    return render(request, "propose_exchange.html", context)


@login_required
def accept_exchange(request, exchange_id):
    """Accept a pending exchange proposal."""
    exchange = get_object_or_404(
        Exchange.objects.select_related(
            "user1", "user1__userprofile", "user2", "skill1", "skill2"
        ),
        id=exchange_id,
        user2=request.user,
        status="pending",
    )

    exchange.status = "active"
    exchange.save()

    messages.success(
        request,
        f"Exchange accepted! You can now start learning {exchange.skill1.name} from {exchange.user1.userprofile.full_name if hasattr(exchange.user1, 'userprofile') and exchange.user1.userprofile.full_name else exchange.user1.username}.",
    )
    return redirect("dashboard")


@login_required
def reject_exchange(request, exchange_id):
    """Reject a pending exchange proposal."""
    exchange = get_object_or_404(
        Exchange, id=exchange_id, user2=request.user, status="pending"
    )

    exchange.status = "cancelled"
    exchange.save()

    messages.info(request, "Exchange proposal declined.")
    return redirect("dashboard")


@login_required
@require_POST
def mark_exchange_complete(request, exchange_id):
    """Mark the user's part of an exchange as complete (POST only with CSRF)."""
    user = request.user
    
    exchange = get_object_or_404(
        Exchange,
        Q(user1=user) | Q(user2=user),
        id=exchange_id,
        status="active"
    )
    
    is_user1 = user == exchange.user1
    
    if is_user1 and not exchange.user1_completed:
        exchange.user1_completed = True
        exchange.user1_completed_date = timezone.now()
        exchange.save()
        messages.success(
            request, 
            "Your part of the exchange is marked as complete! "
            "Once the other user also marks their part complete, "
            "an admin will review and approve it."
        )
    elif not is_user1 and not exchange.user2_completed:
        exchange.user2_completed = True
        exchange.user2_completed_date = timezone.now()
        exchange.save()
        messages.success(
            request,
            "Your part of the exchange is marked as complete! "
            "Once the other user also marks their part complete, "
            "an admin will review and approve it."
        )
    else:
        messages.info(request, "You've already marked this exchange as complete.")
    
    if exchange.both_users_completed() and not exchange.admin_approved:
        messages.info(
            request,
            "Both users have completed their parts! "
            "Waiting for admin approval to finalize this exchange."
        )
    
    return redirect("exchanges")


@login_required
def messages_view(request, user_id=None):
    """Display list of conversations and optionally a selected conversation."""
    current_user = request.user

    # --- Build conversation list with optimized queries ---
    # Get all users the current user has messaged with
    sent_to_ids = (
        Message.objects.filter(sender=current_user)
        .values_list("receiver_id", flat=True)
        .distinct()
    )
    received_from_ids = (
        Message.objects.filter(receiver=current_user)
        .values_list("sender_id", flat=True)
        .distinct()
    )
    conversation_user_ids = set(list(sent_to_ids) + list(received_from_ids))

    # Fetch all conversation users with profiles in one query
    conversation_users = User.objects.filter(
        id__in=conversation_user_ids
    ).select_related("userprofile")
    user_map = {user.id: user for user in conversation_users}

    # Fetch all relevant messages for conversations in bulk
    all_messages = Message.objects.filter(
        Q(sender=current_user, receiver_id__in=conversation_user_ids)
        | Q(sender_id__in=conversation_user_ids, receiver=current_user)
    ).select_related("sender", "receiver")

    # Build conversation data
    conversations = []
    for uid in conversation_user_ids:
        other_user = user_map.get(uid)
        if not other_user:
            continue

        # Find last message for this conversation
        user_messages = [
            m
            for m in all_messages
            if (m.sender_id == current_user.id and m.receiver_id == uid)
            or (m.sender_id == uid and m.receiver_id == current_user.id)
        ]
        last_message = max(user_messages, key=lambda m: m.timestamp, default=None)

        # Count unread messages
        unread_count = sum(
            1
            for m in user_messages
            if m.sender_id == uid and m.receiver_id == current_user.id and not m.is_read
        )

        conversations.append(
            {
                "user": other_user,
                "last_message": last_message,
                "unread_count": unread_count,
            }
        )

    # Sort conversations by last message timestamp
    conversations.sort(
        key=lambda x: (
            x["last_message"].timestamp if x["last_message"] else x["user"].date_joined
        ),
        reverse=True,
    )

    # --- Selected conversation (if any) ---
    selected_user = None
    messages_list = []
    if user_id:
        selected_user = get_object_or_404(
            User.objects.select_related("userprofile"), id=user_id
        )

        # Mark unread messages as read
        Message.objects.filter(
            sender=selected_user, receiver=current_user, is_read=False
        ).update(is_read=True)

        # Get all messages with this user
        messages_list = (
            Message.objects.filter(
                Q(sender=current_user, receiver=selected_user)
                | Q(sender=selected_user, receiver=current_user)
            )
            .order_by("timestamp")
            .select_related("sender", "receiver")
        )

        # Handle sending a new message
        if request.method == "POST":
            content = request.POST.get("content", "").strip()
            if content:
                Message.objects.create(
                    sender=current_user, receiver=selected_user, content=content
                )
                return redirect("conversation", user_id=user_id)

    context = {
        "conversations": conversations,
        "selected_user": selected_user,
        "messages": messages_list,
    }

    return render(request, "messages.html", context)


def devteam_view(request):
    return render(request, "devteam.html")
