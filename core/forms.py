from django import forms


class FileCountForm(forms.Form):
    month = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 13)], required=True, label="Mois"
    )
    year = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(2015, 2026)], required=True, label="Année"
    )
    path_prefix = forms.CharField(
        max_length=1024, required=False, label="Préfixe de chemin"
    )
    exclusions = forms.CharField(
        max_length=1024,
        required=False,
        label="Termes à exclure (séparés par des virgules)",
    )
