from django.urls import path
from .views import (
    login_user,
    logout_user,
    member_claim_cancel,
    member_claim_edit,
    member_claims,
    member_transfer_miles,
    redeem_hadiah_page,
    process_redeem,
    register,
    show_main,
    staff_claim_review,
    staff_claims,
)
from . import api_views

app_name = 'main'

urlpatterns = [
    path('', show_main, name='show_main'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('member/klaim-miles/', member_claims, name='member_claims'),
    path('member/klaim-miles/<int:claim_id>/edit/', member_claim_edit, name='member_claim_edit'),
    path('member/klaim-miles/<int:claim_id>/cancel/', member_claim_cancel, name='member_claim_cancel'),
    path('member/transfer-miles/', member_transfer_miles, name='member_transfer_miles'),
    path('member/redeem-hadiah/', redeem_hadiah_page, name='redeem_hadiah_page'),
    path('member/redeem-hadiah/process/', process_redeem, name='process_redeem'),
    path('staf/kelola-klaim/', staff_claims, name='staff_claims'),
    path('staf/kelola-klaim/<int:claim_id>/review/', staff_claim_review, name='staff_claim_review'),
    path('api/member/klaim', api_views.api_member_claims, name='api_member_claims'),
    path('api/member/klaim/<int:claim_id>', api_views.api_member_claim_detail, name='api_member_claim_detail'),
    path('api/staf/klaim', api_views.api_staff_claims, name='api_staff_claims'),
    path('api/staf/klaim/<int:claim_id>', api_views.api_staff_claim_detail, name='api_staff_claim_detail'),
    path('api/staf/klaim/<int:claim_id>/status', api_views.api_staff_claim_status, name='api_staff_claim_status'),
    path('api/member/transfer', api_views.api_member_transfer, name='api_member_transfer'),
]
