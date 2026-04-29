from functools import wraps

from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST

from .forms import AeroMilesUserCreationForm, ClaimForm, ReviewClaimForm, TransferMilesForm, RewardForm, PartnerForm
from . import aeromiles_services as services

# Create your views here.

def show_main(request):
    return render(request, 'main.html')


def _current_email(request):
    return getattr(request.user, "email", "")


def _member_context_or_redirect(request):
    member = services.get_member(_current_email(request))
    if member:
        return member
    messages.error(request, "Akun ini belum terdaftar sebagai member AeroMiles.")
    return None


def _staff_context_or_redirect(request):
    staff = services.get_staff(_current_email(request))
    if staff:
        return staff
    messages.error(request, "Akun ini belum terdaftar sebagai staf AeroMiles.")
    return None


def member_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not _member_context_or_redirect(request):
            return redirect("main:show_main")
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not _staff_context_or_redirect(request):
            return redirect("main:show_main")
        return view_func(request, *args, **kwargs)

    return wrapper


def _claim_form(data=None, initial=None):
    return ClaimForm(
        data=data,
        initial=initial,
        maskapai_choices=services.list_maskapai_choices(),
        airport_choices=services.list_airport_choices(),
    )


@member_required
def member_claims(request):
    email = _current_email(request)
    selected_status = request.GET.get("status") or None
    form = _claim_form(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            try:
                services.create_claim(email, form.cleaned_data)
                messages.success(request, "Klaim missing miles berhasil diajukan.")
                return redirect("main:member_claims")
            except services.DomainError as exc:
                messages.error(request, exc.message)

    context = {
        "member": services.get_member(email),
        "member_name": services.full_name(services.get_member(email)),
        "summary": services.get_claim_summary(email),
        "claims": services.list_member_claims(email, selected_status),
        "selected_status": selected_status,
        "form": form,
    }
    return render(request, "member_claims.html", context)


@member_required
def member_claim_edit(request, claim_id):
    email = _current_email(request)
    claim = services.get_member_claim(email, claim_id)
    if not claim:
        messages.error(request, "Klaim tidak ditemukan.")
        return redirect("main:member_claims")
    if claim["status_penerimaan"] != "Menunggu":
        messages.error(request, "Klaim hanya dapat diubah saat status masih Menunggu.")
        return redirect("main:member_claims")

    form = _claim_form(request.POST or None, initial=claim)
    if request.method == "POST" and form.is_valid():
        try:
            services.update_claim(email, claim_id, form.cleaned_data)
            messages.success(request, "Klaim berhasil diperbarui.")
            return redirect("main:member_claims")
        except services.DomainError as exc:
            messages.error(request, exc.message)

    return render(request, "member_claim_edit.html", {"form": form, "claim": claim})


@member_required
@require_POST
def member_claim_cancel(request, claim_id):
    try:
        services.cancel_claim(_current_email(request), claim_id)
        messages.success(request, "Klaim berhasil dibatalkan.")
    except services.DomainError as exc:
        messages.error(request, exc.message)
    return redirect("main:member_claims")


@staff_required
def staff_claims(request):
    selected_status = request.GET.get("status") or None
    selected_maskapai = request.GET.get("maskapai") or None
    claims = services.list_staff_claims(selected_status, selected_maskapai)
    context = {
        "staff": services.get_staff(_current_email(request)),
        "staff_name": services.full_name(services.get_staff(_current_email(request))),
        "claims": claims,
        "pending_count": services.count_pending_claims(),
        "selected_status": selected_status,
        "selected_maskapai": selected_maskapai,
        "maskapai_choices": services.list_maskapai_choices(),
    }
    return render(request, "staff_claims.html", context)


@staff_required
@require_POST
def staff_claim_review(request, claim_id):
    form = ReviewClaimForm(request.POST)
    if form.is_valid():
        try:
            services.review_claim(
                _current_email(request),
                claim_id,
                form.cleaned_data["status"],
                form.cleaned_data.get("jumlah_miles_disetujui"),
            )
            messages.success(request, "Status klaim berhasil diperbarui.")
        except services.DomainError as exc:
            messages.error(request, exc.message)
    else:
        messages.error(request, "Keputusan klaim tidak valid. Periksa jumlah miles atau alasan penolakan.")
    return redirect("main:staff_claims")


@member_required
def member_transfer_miles(request):
    email = _current_email(request)
    form = TransferMilesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_transfer(
                email,
                form.cleaned_data["email_penerima"],
                form.cleaned_data["jumlah"],
                form.cleaned_data["catatan"],
            )
            messages.success(request, "Transfer miles berhasil.")
            return redirect("main:member_transfer_miles")
        except services.DomainError as exc:
            messages.error(request, exc.message)

    transfer_type = request.GET.get("tipe") or None
    context = {
        "member": services.get_member(email),
        "member_name": services.full_name(services.get_member(email)),
        "form": form,
        "transfers": services.list_transfers(email, transfer_type),
        "selected_type": transfer_type,
    }
    return render(request, "member_transfer_miles.html", context)

# Render reward management page (logic not yet added)
def staff_manage_reward(request):
    # rewards = services.list_rewards()
    reward_form = RewardForm
    rewards = (
        {
            'kode_hadiah': 'RWD-001',
            'nama_hadiah': 'Business Class Upgrade',
            'miles': 1000,
            'deskripsi': 'Experience better flight amenities',
            'valid_start_date': '2026-01-01',
            'program_end': '2027-01-01',
            'nama_penyedia': 'Garuda Indonesia',
            'id_penyedia': 1
        },
        {
            'kode_hadiah': 'RWD-002',
            'nama_hadiah': 'Extra Checked Bags',
            'miles': 2000,
            'deskripsi': '1 extra checked bag (max. 30 kg)',
            'valid_start_date': '2026-01-01',
            'program_end': '2027-01-01',
            'nama_penyedia': 'Lion Air',
            'id_penyedia': 2
        },
        {
            'kode_hadiah': 'RWD-003',
            'nama_hadiah': 'Standard Room',
            'miles': 3000,
            'deskripsi': 'Trade in your miles for a free hotel room (1 night)',
            'valid_start_date': '2026-01-01',
            'program_end': '2027-01-01',
            'nama_penyedia': 'Asri Hotels',
            'id_penyedia': 3
        },
        {
            'kode_hadiah': 'RWD-004',
            'nama_hadiah': 'Upgrade 1 Car Class',
            'miles': 4000,
            'deskripsi': 'Get a larger or more practical rental car',
            'valid_start_date': '2026-01-01',
            'program_end': '2027-01-01',
            'nama_penyedia': 'Easy Rent-A-Car',
            'id_penyedia': 4
        },
    )
    context = {
        'rewards': rewards,
        'form': reward_form
    }
    return render(request, 'staff_reward_management.html', context)

def delete_reward(request, reward_code):
    try:
        services.delete_reward(reward_code)
        messages.success(request, "Reward berhasil dihapus.")
    except services.DomainError as exc:
        messages.error(request, exc.message)
    return redirect("main:staff_manage_reward")

# Render partner management page (logic not yet added)
def staff_manage_partner(request):
    partner_form = PartnerForm
    partners = (
        {
            'id_penyedia': 3,
            'email_mitra': 'partner@asrihotels.com',
            'nama_mitra': 'Asri Hotels',
            'tanggal_kerjasama': '2026-01-01'
        },
        {
            'id_penyedia': 4,
            'email_mitra': 'partner@easyrentacar.com',
            'nama_mitra': 'Easy Rent-a-Car',
            'tanggal_kerjasama': '2026-01-01'
        },
    )
    context = {
        'form': partner_form,
        'partners': partners
    }
    return render(request, 'staff_partner_management.html', context)

def delete_partner(request, email):
    try:
        services.delete_reward(email)
        messages.success(request, "Reward berhasil dihapus.")
    except services.DomainError as exc:
        messages.error(request, exc.message)
    return redirect("main:staff_manage_reward")

# Registrasi user
def register(request):
    form = AeroMilesUserCreationForm()

    if request.method == 'POST':
        form = AeroMilesUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your account has been successfully created!')
            return redirect('main:login')
    context = {'form': form}
    return render(request, 'register.html', context)

# Login user
def login_user(request):
   if request.method == 'POST':
      form = AuthenticationForm(data=request.POST)

      if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('main:show_main')

   else:
      form = AuthenticationForm(request)
   context = {'form': form}
   return render(request, 'login.html', context)

# Log out user (no page)
def logout_user(request):
    logout(request)
    response = HttpResponseRedirect(reverse('main:show_main'))
    response.delete_cookie('last_login')
    return response
