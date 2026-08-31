from __future__ import annotations

from datetime import timedelta, timezone

THAI_MONTHS = {
    "มกราคม": 1, "ม.ค.": 1, "ม.ค": 1,
    "กุมภาพันธ์": 2, "ก.พ.": 2, "ก.พ": 2,
    "มีนาคม": 3, "มี.ค.": 3, "มี.ค": 3,
    "เมษายน": 4, "เม.ย.": 4, "เม.ย": 4,
    "พฤษภาคม": 5, "พ.ค.": 5, "พ.ค": 5,
    "มิถุนายน": 6, "มิ.ย.": 6, "มิ.ย": 6,
    "กรกฎาคม": 7, "ก.ค.": 7, "ก.ค": 7,
    "สิงหาคม": 8, "ส.ค.": 8, "ส.ค": 8,
    "กันยายน": 9, "ก.ย.": 9, "ก.ย": 9,
    "ตุลาคม": 10, "ต.ค.": 10, "ต.ค": 10,
    "พฤศจิกายน": 11, "พ.ย.": 11, "พ.ย": 11,
    "ธันวาคม": 12, "ธ.ค.": 12, "ธ.ค": 12,
}

EN_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

TZ_OFFSETS = {
    "UTC": timezone.utc,
    "GMT": timezone.utc,
    "ICT": timezone(timedelta(hours=7)),
    "JST": timezone(timedelta(hours=9)),
    "BST": timezone(timedelta(hours=1)),
    "CET": timezone(timedelta(hours=1)),
    "CEST": timezone(timedelta(hours=2)),
    "EST": timezone(timedelta(hours=-5)),
    "EDT": timezone(timedelta(hours=-4)),
    "CST": timezone(timedelta(hours=-6)),
    "CDT": timezone(timedelta(hours=-5)),
    "MST": timezone(timedelta(hours=-7)),
    "MDT": timezone(timedelta(hours=-6)),
    "PST": timezone(timedelta(hours=-8)),
    "PDT": timezone(timedelta(hours=-7)),
}

MEDICAL_TERMS = (
    "medical", "medicine", "clinical", "healthcare", "health care", "physician", "doctor", "nursing",
    "pathology", "surgery", "public health", "hospital", "patient", "cme", "cpd",
    "แพทย์", "การแพทย์", "เวชศาสตร์", "สุขภาพ", "พยาบาล", "โรงพยาบาล", "สาธารณสุข",
    "医療", "医学", "医師", "臨床", "看護", "病院", "ヘルスケア", "公衆衛生",
)
EVENT_TERMS = (
    "webinar", "seminar", "conference", "meeting", "workshop", "symposium", "lecture", "training", "course",
    "สัมมนา", "ประชุม", "อบรม", "เวิร์กช็อป", "บรรยาย",
    "セミナー", "ウェビナー", "講演", "研修", "学会", "勉強会", "イベント",
)
ONLINE_TERMS = (
    "online", "virtual", "webinar", "zoom", "microsoft teams", "google meet", "livestream", "live stream",
    "ออนไลน์", "ประชุมออนไลน์", "ผ่าน zoom", "ผ่านระบบ zoom",
    "オンライン", "ウェビナー", "zoom配信", "ライブ配信",
)
THAILAND_TERMS = (
    "thailand", "ประเทศไทย", "กรุงเทพ", "bangkok", "เชียงใหม่", "chiang mai", "ขอนแก่น", "khon kaen",
    "สงขลา", "songkhla", "ภูเก็ต", "phuket", "นครราชสีมา", "korat", "นนทบุรี", "nonthaburi",
    "ปทุมธานี", "pathum thani", "ชลบุรี", "chonburi",
)
FREE_TERMS = (
    "free registration", "free admission", "free attendance", "free webinar", "free seminar", "no cost",
    "complimentary", "free to attend", "attendance is free", "registration is free",
    "เข้าร่วมฟรี", "สมัครฟรี", "ลงทะเบียนฟรี", "ไม่เสียค่าใช้จ่าย", "ไม่มีค่าใช้จ่าย", "ฟรี",
    "参加費無料", "受講料無料", "入場無料", "無料ウェビナー", "無料セミナー", "無料",
)
CERT_TERMS = (
    "attendance certificate", "certificate of attendance", "certificate of participation", "e-certificate",
    "completion certificate", "certificate available", "cpd certificate", "cme credit", "cme credits", "cpd credit",
    "เกียรติบัตร", "ประกาศนียบัตร", "ใบรับรอง", "หนังสือรับรอง", "คะแนน cme", "คะแนน cpd",
    "受講証明書", "参加証", "修了証", "修了証明書", "受講証", "認定単位",
)
CLOSED_TERMS = (
    "registration closed", "registrations closed", "registration has closed", "sold out", "event has ended",
    "this event has ended", "booking closed", "applications closed",
    "ปิดรับสมัคร", "ปิดลงทะเบียน", "หมดเขตสมัคร", "เต็มแล้ว",
    "受付終了", "申込終了", "募集終了", "満席", "イベントは終了",
)
REGISTER_ANCHOR_TERMS = (
    "register", "registration", "sign up", "book now", "apply", "join event", "reserve", "event details", "details",
    "ลงทะเบียน", "สมัคร", "สำรองที่นั่ง", "เข้าร่วม",
    "お申し込み", "申込み", "申し込み", "参加登録", "予約", "登録", "詳細をみる", "詳細",
)
