from django import forms


class LLMForm(forms.Form):
    prompt = forms.CharField(
        label="",
        widget=forms.Textarea(
            attrs={
            'rows': 1,
            'class': 'llm--textarea',
            'placeholder': 'Ask anything',
            'id': 'id_prompt'
        })
    )