import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .forms import ClaimForm, ReviewClaimForm, TransferMilesForm
from . import aeromiles_services as services


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise services.DomainError("JSON body tidak valid.")


def _auth_email(request):
    if not request.user.is_authenticated:
        raise services.DomainError("Autentikasi diperlukan.", code=401)
    return request.user.email


def _require_member(request):
    email = _auth_email(request)
    if not services.get_member(email):
        raise services.DomainError("User bukan member aktif.", code=403)
    return email


def _require_staff(request):
    email = _auth_email(request)
    if not services.get_staff(email):
        raise services.DomainError("User bukan staf aktif.", code=403)
    return email


def _claim_choices():
    return {
        "maskapai_choices": services.list_maskapai_choices(),
        "airport_choices": services.list_airport_choices(),
    }


def _claim_payload(claim):
    return {
        "id": claim["id"],
        "maskapai": claim["maskapai"],
        "bandara_asal": claim["bandara_asal"].strip(),
        "bandara_tujuan": claim["bandara_tujuan"].strip(),
        "tanggal_penerbangan": claim["tanggal_penerbangan"],
        "flight_number": claim["flight_number"],
        "nomor_tiket": claim["nomor_tiket"],
        "kelas_kabin": claim["kelas_kabin"],
        "pnr": claim["pnr"],
        "status_penerimaan": claim["status_penerimaan"],
        "jumlah_miles_disetujui": 0,
        "alasan_penolakan": None,
        "diproses_oleh": claim.get("email_staf"),
        "diproses_pada": None,
        "timestamp": claim.get("time_stamp"),
    }


def _error_response(exc):
    return JsonResponse({"error": exc.message}, status=exc.code)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_member_claims(request):
    try:
        email = _require_member(request)
        if request.method == "GET":
            status = request.GET.get("status") or None
            claims = [_claim_payload(row) for row in services.list_member_claims(email, status)]
            return JsonResponse({"data": claims, "total": len(claims), "page": 1, "limit": len(claims)})

        form = ClaimForm(data=_json_body(request), **_claim_choices())
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        claim_id = services.create_claim(email, form.cleaned_data)
        return JsonResponse(
            {"message": "Klaim berhasil diajukan", "id": claim_id, "status_penerimaan": "Menunggu"},
            status=201,
        )
    except services.DomainError as exc:
        return _error_response(exc)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_member_claim_detail(request, claim_id):
    try:
        email = _require_member(request)
        claim = services.get_member_claim(email, claim_id)
        if not claim:
            raise services.DomainError("Klaim tidak ditemukan.", code=404)

        if request.method == "GET":
            return JsonResponse(_claim_payload(claim))
        if request.method == "DELETE":
            services.cancel_claim(email, claim_id)
            return JsonResponse({"message": "Klaim berhasil dibatalkan", "id": claim_id})

        form = ClaimForm(data=_json_body(request), **_claim_choices())
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        services.update_claim(email, claim_id, form.cleaned_data)
        return JsonResponse({"message": "Klaim berhasil diperbarui", "id": claim_id, "status_penerimaan": "Menunggu"})
    except services.DomainError as exc:
        return _error_response(exc)


@require_http_methods(["GET"])
def api_staff_claims(request):
    try:
        _require_staff(request)
        claims = services.list_staff_claims(request.GET.get("status") or None, request.GET.get("maskapai") or None)
        payload = []
        for row in claims:
            item = _claim_payload(row)
            item.update(
                {
                    "email_member": row["email_member"],
                    "nomor_member": row["nomor_member"],
                    "nama_member": services.full_name(row),
                }
            )
            payload.append(item)
        return JsonResponse({"data": payload, "total": len(payload), "page": 1, "limit": len(payload)})
    except services.DomainError as exc:
        return _error_response(exc)


@require_http_methods(["GET"])
def api_staff_claim_detail(request, claim_id):
    try:
        _require_staff(request)
        claim = services.get_staff_claim(claim_id)
        if not claim:
            raise services.DomainError("Klaim tidak ditemukan.", code=404)
        return JsonResponse(
            {
                "id": claim["id"],
                "member": {
                    "email": claim["email_member"],
                    "nomor_member": claim["nomor_member"],
                    "nama_lengkap": services.full_name(claim),
                    "id_tier": claim["id_tier"],
                },
                "flight": {
                    "maskapai": claim["maskapai"],
                    "bandara_asal": claim["bandara_asal"].strip(),
                    "bandara_tujuan": claim["bandara_tujuan"].strip(),
                    "tanggal_penerbangan": claim["tanggal_penerbangan"],
                    "flight_number": claim["flight_number"],
                    "nomor_tiket": claim["nomor_tiket"],
                    "kelas_kabin": claim["kelas_kabin"],
                    "pnr": claim["pnr"],
                },
                "status_penerimaan": claim["status_penerimaan"],
                "jumlah_miles_disetujui": 0,
                "alasan_penolakan": None,
                "diproses_oleh": claim["email_staf"],
                "diproses_pada": None,
                "timestamp": claim["time_stamp"],
            }
        )
    except services.DomainError as exc:
        return _error_response(exc)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
def api_staff_claim_status(request, claim_id):
    try:
        staff_email = _require_staff(request)
        form = ReviewClaimForm(data=_json_body(request))
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        new_balance = services.review_claim(
            staff_email,
            claim_id,
            form.cleaned_data["status"],
            form.cleaned_data.get("jumlah_miles_disetujui"),
        )
        return JsonResponse(
            {
                "message": "Status klaim berhasil diperbarui",
                "id": claim_id,
                "status_penerimaan": form.cleaned_data["status"],
                "jumlah_miles_disetujui": form.cleaned_data.get("jumlah_miles_disetujui") or 0,
                "alasan_penolakan": form.cleaned_data.get("alasan_penolakan") or None,
                "award_miles_member_baru": new_balance,
                "diproses_oleh": staff_email,
                "diproses_pada": None,
            }
        )
    except services.DomainError as exc:
        return _error_response(exc)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_member_transfer(request):
    try:
        email = _require_member(request)
        if request.method == "GET":
            transfers = services.list_transfers(email, request.GET.get("tipe") or None)
            return JsonResponse({"data": transfers, "total": len(transfers), "page": 1, "limit": len(transfers)})

        form = TransferMilesForm(data=_json_body(request))
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        result = services.create_transfer(
            email,
            form.cleaned_data["email_penerima"],
            form.cleaned_data["jumlah"],
            form.cleaned_data["catatan"],
        )
        return JsonResponse(
            {
                "message": "Transfer berhasil",
                "email_penerima": form.cleaned_data["email_penerima"],
                "jumlah": form.cleaned_data["jumlah"],
                "award_miles_baru": result["award_miles_baru"],
                "timestamp": result["timestamp"],
            },
            status=201,
        )
    except services.DomainError as exc:
        return _error_response(exc)
