from django.db import IntegrityError, connection, transaction


class DomainError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.message = message
        self.code = code


def _dict_fetchall(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _dict_fetchone(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def list_maskapai_choices():
    with connection.cursor() as cursor:
        cursor.execute("SELECT kode_maskapai, nama_maskapai FROM maskapai ORDER BY kode_maskapai")
        return [(row[0], f"{row[1]} ({row[0]})") for row in cursor.fetchall()]


def list_airport_choices():
    with connection.cursor() as cursor:
        cursor.execute("SELECT iata_code, nama, kota FROM bandara ORDER BY iata_code")
        return [(row[0].strip(), f"{row[0].strip()} - {row[1]}, {row[2]}") for row in cursor.fetchall()]


def get_member(email):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT m.email, m.nomor_member, m.award_miles, m.total_miles, m.id_tier,
                   p.first_mid_name, p.last_name
            FROM member m
            JOIN pengguna p ON p.email = m.email
            WHERE m.email = %s
            """,
            [email],
        )
        return _dict_fetchone(cursor)


def get_staff(email):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.email, s.id_staf, s.kode_maskapai, p.first_mid_name, p.last_name
            FROM staf s
            JOIN pengguna p ON p.email = s.email
            WHERE s.email = %s
            """,
            [email],
        )
        return _dict_fetchone(cursor)


def full_name(row):
    if not row:
        return ""
    return f"{row.get('first_mid_name', '')} {row.get('last_name', '')}".strip()


def list_member_claims(email, status=None):
    params = [email]
    status_filter = ""
    if status:
        status_filter = "AND c.status_penerimaan = %s"
        params.append(status)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT c.id, c.maskapai, ma.nama_maskapai, c.bandara_asal, c.bandara_tujuan,
                   c.tanggal_penerbangan, c.flight_number, c.nomor_tiket,
                   c.kelas_kabin, c.pnr, c.status_penerimaan, c.time_stamp, c.email_staf
            FROM claim_missing_miles c
            JOIN maskapai ma ON ma.kode_maskapai = c.maskapai
            WHERE c.email_member = %s {status_filter}
            ORDER BY c.time_stamp DESC
            """,
            params,
        )
        return _dict_fetchall(cursor)


def get_member_claim(email, claim_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, maskapai, bandara_asal, bandara_tujuan, tanggal_penerbangan,
                   flight_number, nomor_tiket, kelas_kabin, pnr, status_penerimaan
            FROM claim_missing_miles
            WHERE id = %s AND email_member = %s
            """,
            [claim_id, email],
        )
        return _dict_fetchone(cursor)


def create_claim(email, data):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO claim_missing_miles
                    (email_member, maskapai, bandara_asal, bandara_tujuan,
                     tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [
                    email,
                    data["maskapai"],
                    data["bandara_asal"],
                    data["bandara_tujuan"],
                    data["tanggal_penerbangan"],
                    data["flight_number"],
                    data["nomor_tiket"],
                    data["kelas_kabin"],
                    data["pnr"],
                ],
            )
            return cursor.fetchone()[0]
    except IntegrityError as exc:
        raise DomainError("Klaim duplikat atau data referensi tidak valid.") from exc


def update_claim(email, claim_id, data):
    claim = get_member_claim(email, claim_id)
    if not claim:
        raise DomainError("Klaim tidak ditemukan.", code=404)
    if claim["status_penerimaan"] != "Menunggu":
        raise DomainError("Klaim hanya dapat diubah saat status masih Menunggu.", code=403)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE claim_missing_miles
                SET maskapai = %s, bandara_asal = %s, bandara_tujuan = %s,
                    tanggal_penerbangan = %s, flight_number = %s, nomor_tiket = %s,
                    kelas_kabin = %s, pnr = %s
                WHERE id = %s AND email_member = %s AND status_penerimaan = 'Menunggu'
                """,
                [
                    data["maskapai"],
                    data["bandara_asal"],
                    data["bandara_tujuan"],
                    data["tanggal_penerbangan"],
                    data["flight_number"],
                    data["nomor_tiket"],
                    data["kelas_kabin"],
                    data["pnr"],
                    claim_id,
                    email,
                ],
            )
    except IntegrityError as exc:
        raise DomainError("Klaim duplikat atau data referensi tidak valid.") from exc


def cancel_claim(email, claim_id):
    claim = get_member_claim(email, claim_id)
    if not claim:
        raise DomainError("Klaim tidak ditemukan.", code=404)
    if claim["status_penerimaan"] != "Menunggu":
        raise DomainError("Klaim hanya dapat dibatalkan saat status masih Menunggu.", code=403)
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM claim_missing_miles WHERE id = %s AND email_member = %s AND status_penerimaan = 'Menunggu'",
            [claim_id, email],
        )


def get_claim_summary(email):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status_penerimaan, COUNT(*)
            FROM claim_missing_miles
            WHERE email_member = %s
            GROUP BY status_penerimaan
            """,
            [email],
        )
        summary = {"Menunggu": 0, "Disetujui": 0, "Ditolak": 0}
        for status, count in cursor.fetchall():
            summary[status] = count
        return summary


def list_staff_claims(status=None, maskapai=None):
    params = []
    filters = []
    if status:
        filters.append("c.status_penerimaan = %s")
        params.append(status)
    if maskapai:
        filters.append("c.maskapai = %s")
        params.append(maskapai)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT c.id, c.email_member, m.nomor_member, p.first_mid_name, p.last_name,
                   c.maskapai, c.bandara_asal, c.bandara_tujuan, c.tanggal_penerbangan,
                   c.flight_number, c.nomor_tiket, c.kelas_kabin, c.pnr,
                   c.status_penerimaan, c.time_stamp, c.email_staf
            FROM claim_missing_miles c
            JOIN member m ON m.email = c.email_member
            JOIN pengguna p ON p.email = c.email_member
            {where}
            ORDER BY
                CASE c.status_penerimaan WHEN 'Menunggu' THEN 0 WHEN 'Ditolak' THEN 1 ELSE 2 END,
                c.time_stamp DESC
            """,
            params,
        )
        return _dict_fetchall(cursor)


def count_pending_claims():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM claim_missing_miles WHERE status_penerimaan = 'Menunggu'")
        return cursor.fetchone()[0]


def get_staff_claim(claim_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.id, c.email_member, m.nomor_member, m.id_tier,
                   p.first_mid_name, p.last_name, c.maskapai, c.bandara_asal,
                   c.bandara_tujuan, c.tanggal_penerbangan, c.flight_number,
                   c.nomor_tiket, c.kelas_kabin, c.pnr, c.status_penerimaan,
                   c.time_stamp, c.email_staf
            FROM claim_missing_miles c
            JOIN member m ON m.email = c.email_member
            JOIN pengguna p ON p.email = c.email_member
            WHERE c.id = %s
            """,
            [claim_id],
        )
        return _dict_fetchone(cursor)


def review_claim(staff_email, claim_id, status, approved_miles=None):
    if status not in {"Disetujui", "Ditolak"}:
        raise DomainError("Status tidak valid.")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email_member, status_penerimaan
                FROM claim_missing_miles
                WHERE id = %s
                FOR UPDATE
                """,
                [claim_id],
            )
            claim = _dict_fetchone(cursor)
            if not claim:
                raise DomainError("Klaim tidak ditemukan.", code=404)
            if claim["status_penerimaan"] != "Menunggu":
                raise DomainError("Klaim sudah diproses sebelumnya.", code=409)

            new_balance = None
            if status == "Disetujui":
                if not approved_miles or approved_miles <= 0:
                    raise DomainError("Jumlah miles disetujui harus lebih dari 0.")
                cursor.execute(
                    """
                    UPDATE member
                    SET award_miles = award_miles + %s,
                        total_miles = total_miles + %s
                    WHERE email = %s
                    RETURNING award_miles
                    """,
                    [approved_miles, approved_miles, claim["email_member"]],
                )
                new_balance = cursor.fetchone()[0]

            cursor.execute(
                """
                UPDATE claim_missing_miles
                SET status_penerimaan = %s, email_staf = %s
                WHERE id = %s
                """,
                [status, staff_email, claim_id],
            )
            return new_balance


def list_transfers(email, tipe=None):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT t.email_member_1, t.email_member_2, t.time_stamp, t.jumlah, t.catatan,
                   p1.first_mid_name AS sender_first, p1.last_name AS sender_last,
                   p2.first_mid_name AS receiver_first, p2.last_name AS receiver_last
            FROM transfer t
            JOIN pengguna p1 ON p1.email = t.email_member_1
            JOIN pengguna p2 ON p2.email = t.email_member_2
            WHERE t.email_member_1 = %s OR t.email_member_2 = %s
            ORDER BY t.time_stamp DESC
            """,
            [email, email],
        )
        rows = _dict_fetchall(cursor)

    transfers = []
    for row in rows:
        is_sender = row["email_member_1"] == email
        transfer_type = "Kirim" if is_sender else "Terima"
        if tipe and transfer_type != tipe:
            continue
        transfers.append(
            {
                "tipe": transfer_type,
                "email_member": row["email_member_2"] if is_sender else row["email_member_1"],
                "nama_member": (
                    f"{row['receiver_first']} {row['receiver_last']}"
                    if is_sender
                    else f"{row['sender_first']} {row['sender_last']}"
                ).strip(),
                "time_stamp": row["time_stamp"],
                "jumlah": row["jumlah"],
                "catatan": row["catatan"],
            }
        )
    return transfers


def create_transfer(sender_email, receiver_email, amount, note=""):
    if sender_email == receiver_email:
        raise DomainError("Tidak dapat transfer ke diri sendiri.")
    if amount <= 0:
        raise DomainError("Jumlah miles harus lebih dari 0.")

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT award_miles FROM member WHERE email = %s FOR UPDATE", [sender_email])
            sender = cursor.fetchone()
            if not sender:
                raise DomainError("Pengirim bukan member aktif.", code=404)
            if sender[0] < amount:
                raise DomainError("Award miles tidak mencukupi.")

            cursor.execute("SELECT email FROM member WHERE email = %s FOR UPDATE", [receiver_email])
            if cursor.fetchone() is None:
                raise DomainError("Email penerima bukan member aktif.", code=404)

            cursor.execute(
                "UPDATE member SET award_miles = award_miles - %s WHERE email = %s RETURNING award_miles",
                [amount, sender_email],
            )
            new_balance = cursor.fetchone()[0]
            cursor.execute(
                """
                UPDATE member
                SET award_miles = award_miles + %s,
                    total_miles = total_miles + %s
                WHERE email = %s
                """,
                [amount, amount, receiver_email],
            )
            cursor.execute(
                """
                INSERT INTO transfer (email_member_1, email_member_2, jumlah, catatan)
                VALUES (%s, %s, %s, %s)
                RETURNING time_stamp
                """,
                [sender_email, receiver_email, amount, note or None],
            )
            timestamp = cursor.fetchone()[0]
            return {"award_miles_baru": new_balance, "timestamp": timestamp}


def get_katalog_hadiah():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT h.kode_hadiah, h.nama, h.miles, h.deskripsi, h.valid_start_date, h.program_end,
                   COALESCE(m.nama_maskapai, mi.nama_mitra, 'Penyedia Lain') AS nama_penyedia
            FROM hadiah h
            JOIN penyedia p ON h.id_penyedia = p.id
            LEFT JOIN maskapai m ON p.id = m.id_penyedia
            LEFT JOIN mitra mi ON p.id = mi.id_penyedia
            WHERE CURRENT_DATE <= h.program_end
            ORDER BY h.nama
            """
        )
        return _dict_fetchall(cursor)


def get_riwayat_redeem(email):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.time_stamp, h.nama AS nama_hadiah, h.miles
            FROM redeem r
            JOIN hadiah h ON r.kode_hadiah = h.kode_hadiah
            WHERE r.email_member = %s
            ORDER BY r.time_stamp DESC
            """,
            [email],
        )
        return _dict_fetchall(cursor)


def execute_redeem(email, kode_hadiah):
    with transaction.atomic():
        with connection.cursor() as cursor:
            # a. Fetches the required miles and validates the current date
            cursor.execute(
                """
                SELECT miles, valid_start_date, program_end
                FROM hadiah
                WHERE kode_hadiah = %s
                FOR SHARE
                """,
                [kode_hadiah],
            )
            hadiah = _dict_fetchone(cursor)
            if not hadiah:
                raise DomainError("Hadiah tidak ditemukan.", code=404)

            # Validate date
            cursor.execute("SELECT CURRENT_DATE")
            now = cursor.fetchone()[0]
            if now < hadiah["valid_start_date"] or now > hadiah["program_end"]:
                raise DomainError("Hadiah tidak tersedia untuk di-redeem saat ini.")

            # b. Fetches the member's current award_miles
            cursor.execute(
                "SELECT award_miles FROM member WHERE email = %s FOR UPDATE",
                [email],
            )
            member = cursor.fetchone()
            if not member:
                raise DomainError("Member tidak ditemukan.", code=404)

            award_miles = member[0]
            required_miles = hadiah["miles"]

            # c. Raises an exception if award_miles < required miles
            if award_miles < required_miles:
                raise DomainError(
                    f"Award miles tidak mencukupi. Dibutuhkan {required_miles} miles, Anda hanya memiliki {award_miles} miles."
                )

            # d. Subtracts the miles from the MEMBER table
            cursor.execute(
                "UPDATE member SET award_miles = award_miles - %s WHERE email = %s",
                [required_miles, email],
            )

            # e. Inserts a new record into the REDEEM table
            cursor.execute(
                "INSERT INTO redeem (email_member, kode_hadiah, time_stamp) VALUES (%s, %s, CURRENT_TIMESTAMP)",
                [email, kode_hadiah],
            )
