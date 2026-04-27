from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from .forms import ClaimForm, ReviewClaimForm, TransferMilesForm


class AeroMilesFeatureFormTests(SimpleTestCase):
    def _claim_form(self, data):
        return ClaimForm(
            data=data,
            maskapai_choices=[("GA", "Garuda Indonesia (GA)")],
            airport_choices=[("CGK", "CGK - Soekarno Hatta"), ("DPS", "DPS - Ngurah Rai")],
        )

    def test_claim_form_rejects_future_flight_dates(self):
        form = self._claim_form(
            {
                "maskapai": "GA",
                "bandara_asal": "CGK",
                "bandara_tujuan": "DPS",
                "tanggal_penerbangan": timezone.localdate() + timedelta(days=1),
                "flight_number": "ga001",
                "nomor_tiket": "123456",
                "kelas_kabin": "Economy",
                "pnr": "abc123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("tanggal_penerbangan", form.errors)

    def test_claim_form_normalizes_codes(self):
        form = self._claim_form(
            {
                "maskapai": "GA",
                "bandara_asal": "CGK",
                "bandara_tujuan": "DPS",
                "tanggal_penerbangan": timezone.localdate() - timedelta(days=1),
                "flight_number": "ga001",
                "nomor_tiket": "123456",
                "kelas_kabin": "Business",
                "pnr": "abc123",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["flight_number"], "GA001")
        self.assertEqual(form.cleaned_data["pnr"], "ABC123")

    def test_transfer_form_requires_positive_miles(self):
        form = TransferMilesForm(
            data={"email_penerima": "other@mail.com", "jumlah": 0, "catatan": ""}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("jumlah", form.errors)

    def test_review_form_requires_approved_miles_for_approval(self):
        form = ReviewClaimForm(data={"status": "Disetujui", "jumlah_miles_disetujui": "", "alasan_penolakan": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("jumlah_miles_disetujui", form.errors)
