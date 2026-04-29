from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import User


class AeroMilesUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = user.role or "member"
        user.salutation = user.salutation or "Mr."
        user.first_mid_name = user.first_mid_name or ""
        user.last_name = user.last_name or ""
        user.country_code = user.country_code or "+62"
        user.mobile_number = user.mobile_number or ""
        user.tanggal_lahir = user.tanggal_lahir or timezone.datetime(2000, 1, 1).date()
        user.kewarganegaraan = user.kewarganegaraan or "Indonesia"
        if commit:
            user.save()
        return user


class ClaimForm(forms.Form):
    CABIN_CHOICES = (
        ("Economy", "Economy"),
        ("Business", "Business"),
        ("First", "First"),
    )

    maskapai = forms.ChoiceField(label="Maskapai")
    bandara_asal = forms.ChoiceField(label="Bandara Asal")
    bandara_tujuan = forms.ChoiceField(label="Bandara Tujuan")
    tanggal_penerbangan = forms.DateField(
        label="Tanggal Penerbangan",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    flight_number = forms.CharField(label="Nomor Penerbangan", max_length=10)
    nomor_tiket = forms.CharField(label="Nomor Tiket", max_length=20)
    kelas_kabin = forms.ChoiceField(label="Kelas Kabin", choices=CABIN_CHOICES)
    pnr = forms.CharField(label="PNR", max_length=10)

    def __init__(self, *args, maskapai_choices=None, airport_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["maskapai"].choices = [("", "Pilih Maskapai")] + list(maskapai_choices or [])
        empty_airport = [("", "Pilih Bandara")]
        self.fields["bandara_asal"].choices = empty_airport + list(airport_choices or [])
        self.fields["bandara_tujuan"].choices = empty_airport + list(airport_choices or [])
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-amber-500 focus:ring-amber-500"
                }
            )

    def clean_flight_number(self):
        return self.cleaned_data["flight_number"].strip().upper()

    def clean_nomor_tiket(self):
        return self.cleaned_data["nomor_tiket"].strip()

    def clean_pnr(self):
        return self.cleaned_data["pnr"].strip().upper()

    def clean_tanggal_penerbangan(self):
        tanggal = self.cleaned_data["tanggal_penerbangan"]
        if tanggal >= timezone.localdate():
            raise forms.ValidationError("Tanggal penerbangan harus sudah lewat.")
        return tanggal

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("bandara_asal") and cleaned.get("bandara_tujuan"):
            if cleaned["bandara_asal"] == cleaned["bandara_tujuan"]:
                raise forms.ValidationError("Bandara asal dan tujuan harus berbeda.")
        return cleaned


class TransferMilesForm(forms.Form):
    email_penerima = forms.EmailField(label="Email Penerima")
    jumlah = forms.IntegerField(label="Jumlah Miles", min_value=1)
    catatan = forms.CharField(label="Catatan", max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-amber-500 focus:ring-amber-500"
                }
            )

    def clean_email_penerima(self):
        return self.cleaned_data["email_penerima"].strip().lower()

    def clean_catatan(self):
        return self.cleaned_data.get("catatan", "").strip()


class ReviewClaimForm(forms.Form):
    STATUS_CHOICES = (
        ("Disetujui", "Setujui"),
        ("Ditolak", "Tolak"),
    )

    status = forms.ChoiceField(choices=STATUS_CHOICES)
    jumlah_miles_disetujui = forms.IntegerField(required=False, min_value=1)
    alasan_penolakan = forms.CharField(required=False, max_length=255)

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        if status == "Disetujui" and not cleaned.get("jumlah_miles_disetujui"):
            self.add_error("jumlah_miles_disetujui", "Jumlah miles wajib diisi saat menyetujui klaim.")
        if status == "Ditolak" and not cleaned.get("alasan_penolakan", "").strip():
            self.add_error("alasan_penolakan", "Alasan penolakan wajib diisi.")
        return cleaned
