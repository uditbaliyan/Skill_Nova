from django import forms
from .models import Assignment,ProjectCompletion

class AssignmentForm(forms.Form):
    def __init__(self, *args, **kwargs):
        assignments = kwargs.pop('assignments')
        super().__init__(*args, **kwargs)
        for assignment in assignments:
            self.fields[f'answer_{assignment.id}'] = forms.ChoiceField(
                label=assignment.question,
                choices=[
                    (assignment.option1, assignment.option1),
                    (assignment.option2, assignment.option2),
                    (assignment.option3, assignment.option3),
                    (assignment.option4, assignment.option4),
                ],
                widget=forms.RadioSelect
            )

class ProjectCompletionForm(forms.ModelForm):
    class Meta:
        model = ProjectCompletion
        fields = ['github_link', 'linkedin_link']
