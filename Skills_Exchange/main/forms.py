from django import forms
from .models import UserProfile, Skill


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["full_name", "bio", "location", "certifications"]


from django import forms
from .models import UserSkill, Skill


class UserSkillForm(forms.ModelForm):
    class Meta:
        model = UserSkill
        fields = ["skill", "role", "proficiency", "experience_years"]
        widgets = {
            "skill": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "proficiency": forms.Select(attrs={"class": "form-select"}),
            "experience_years": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
        }


UserSkillFormSet = forms.modelformset_factory(
    UserSkill,
    form=UserSkillForm,
    extra=1,
    can_delete=True,
)

