"""Plain-language reasons tied to what the owner told us, and the nearest
eligible alternative when they ask for something they can't have."""

from app.services.catalogue import get_catalogue
from app.services.eligibility import BusinessProfile, eligible

# product -> nearest alternatives, best first
ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "P03": ("P02", "P01"),
    "P05": ("P03", "P02"),
    "P06": ("P05", "P03", "P02"),
    "P10": ("P09",),
    "P12": ("P08", "P07"),
    "P13": ("P08", "P07"),
    "P14": ("P18",),
    "P15": ("P18",),
    "P21": ("P20",),
    "P24": ("P25",),
}


def reason(pid: str, s: dict, lang: str) -> str | None:
    """One sentence on why this product is in the plan, using their own answers."""
    sites = s.get("sites") or 1
    staff = s.get("employees") or 1
    internet = (s.get("current_internet") or "").lower()
    hi = lang == "hi"
    hn = lang == "hinglish"
    r = {
        "P01": (
            f"आपकी {sites} जगह के लिए भरोसेमंद फाइबर इंटरनेट।"
            if hi
            else f"{sites} jagah ke liye stable fibre internet."
            if hn
            else f"Reliable fibre for your {'site' if sites == 1 else f'{sites} sites'}"
            + (", instead of a mobile hotspot." if "hotspot" in internet else ".")
        ),
        "P02": (
            f"{staff} लोग एक साथ काम करें तो भी तेज़ 300 Mbps।"
            if hi
            else f"{staff} log saath kaam karein tab bhi fast 300 Mbps."
            if hn
            else f"300 Mbps keeps {staff} people working at once without slowdowns."
        ),
        "P03": "1 Gbps for heavy uploads like scans and design files."
        if not (hi or hn)
        else "भारी फ़ाइलों के लिए 1 Gbps।",
        "P05": "A dedicated line with a 99.5% uptime promise for the shop floor.",
        "P07": (
            f"{staff} लोगों के लिए बिज़नेस मोबाइल लाइनें।"
            if hi
            else "Staff ke liye business mobile lines."
            if hn
            else "Business mobile lines so customer calls go to a company number."
        ),
        "P08": "Postpaid lines with roaming and priority care for staff who travel.",
        "P09": (
            f"आपकी {sites} जगहें हैं, लाइन बंद हो तो भी बिलिंग चलती रहेगी।"
            if hi and sites > 1
            else f"{sites} jagah hain, ek line band ho to bhi billing chalti rahegi."
            if hn and sites > 1
            else f"You have {sites} sites, so failover keeps billing running if one line drops."
            if sites > 1
            else "Failover keeps you online if the main line drops."
        ),
        "P10": f"Manage all {sites} sites' internet from one place and keep billing traffic first.",
        "P11": "A fixed IP so you can view CCTV or reach your server from outside.",
        "P12": "Business phone lines with IVR and call recording.",
        "P13": "A 1800 number customers can call for free.",
        "P15": "A verified WhatsApp channel for orders and reminders.",
        "P16": "अपने डोमेन पर ईमेल।"
        if hi
        else f"{staff} logon ke liye apne domain par email."
        if hn
        else f"Email on your own domain for {staff} people.",
        "P17": "Automatic backup of PCs and phones, 1 TB.",
        "P18": "A simple website so customers can find you online.",
        "P19": (
            "UPI और कार्ड से भुगतान, GST बिलिंग के साथ।"
            if hi
            else "UPI aur card payment, GST billing ke saath."
            if hn
            else "Take UPI and card payments with GST-ready billing."
        ),
        "P20": f"Antivirus and ransomware protection for {max(1, round(staff * 0.4))} devices.",
        "P21": "A managed firewall for the site, watched by our security team.",
        "P22": (
            "ग्राहकों के लिए अलग Wi-Fi, आपका नेटवर्क सुरक्षित रहेगा।"
            if hi
            else "Customers ke liye alag Wi-Fi."
            if hn
            else "Separate customer Wi-Fi keeps your billing network private."
        ),
        "P23": f"Cloud CCTV with 30 days of recordings for {'your shop' if sites == 1 else f'all {sites} sites'}.",
        "P24": "Sensors that track machine uptime and energy use.",
        "P25": "GPS tracking for your vehicles.",
    }
    return r.get(pid)


def ineligible_note(pid: str, biz: BusinessProfile, lang: str) -> str | None:
    """Why they can't have pid, and the nearest option they can have."""
    catalogue = get_catalogue()
    product = catalogue[pid]
    elig = eligible(product, biz)
    if elig.ok:
        return None
    why = elig.reasons[0]
    alt = next((a for a in ALTERNATIVES.get(pid, ()) if eligible(catalogue[a], biz).ok), None)
    if lang == "hi":
        base = f"{product.name} अभी नहीं मिल सकता: {why}."
        return base + (f" इसकी जगह {catalogue[alt].name} सबसे नज़दीकी विकल्प है।" if alt else "")
    if lang == "hinglish":
        base = f"{product.name} abhi nahi mil sakta: {why}."
        return base + (f" Iski jagah {catalogue[alt].name} sabse kareeb option hai." if alt else "")
    base = f"{product.name} isn't available for you yet: {why}."
    return base + (f" The closest option you can get is {catalogue[alt].name}." if alt else "")
