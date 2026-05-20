from django import forms
from courses.models import Course


class CourseEnrollForm(forms.Form):
    # Hidden field that carries the selected course in POST data.
    # ModelChoiceField ensures the submitted value is a valid Course.
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),  # temporary empty queryset
        widget=forms.HiddenInput         # do not show field in the template
    )

    def __init__(self, *args, **kwargs):
        # Initialize the parent Form class first.
        super().__init__(*args, **kwargs)

        # Set allowed courses for validation.
        self.fields['course'].queryset = Course.objects.all()
