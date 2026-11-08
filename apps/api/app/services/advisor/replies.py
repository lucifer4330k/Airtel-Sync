"""Advisor phrases in English, Hindi (Devanagari) and Hinglish (Latin)."""

T: dict[str, dict[str, str]] = {
    "greet": {
        "en": "Namaste! I'll suggest internet, phone and billing services that fit your business, with one monthly price. What kind of business do you run?",
        "hi": "नमस्ते! मैं आपके बिज़नेस के लिए इंटरनेट, फ़ोन और बिलिंग की सेवाएँ एक मासिक कीमत में सुझाऊँगा। आपका बिज़नेस किस तरह का है?",
        "hinglish": "Namaste! Main aapke business ke liye internet, phone aur billing services ek monthly price mein suggest karunga. Aapka business kis type ka hai?",
    },
    "ask_segment": {
        "en": "What kind of business do you run?",
        "hi": "आपका बिज़नेस किस तरह का है?",
        "hinglish": "Aapka business kis type ka hai?",
    },
    "ask_employees": {
        "en": "How many people work there, including you?",
        "hi": "आपको मिलाकर वहाँ कितने लोग काम करते हैं?",
        "hinglish": "Aapko milakar wahan kitne log kaam karte hain?",
    },
    "ask_sites": {
        "en": "How many locations need to be connected?",
        "hi": "कितनी जगहों पर कनेक्शन चाहिए?",
        "hinglish": "Kitni jagah connection chahiye?",
    },
    "ask_city": {
        "en": "Which city are you in?",
        "hi": "आप किस शहर में हैं?",
        "hinglish": "Aap kis shehar mein hain?",
    },
    "ask_gst": {
        "en": "Do you have a GST number? You can type it, or say no. Some services need an active GST registration.",
        "hi": "क्या आपके पास GST नंबर है? नंबर लिखें, या 'नहीं' कहें। कुछ सेवाओं के लिए सक्रिय GST ज़रूरी है।",
        "hinglish": "Kya aapke paas GST number hai? Number likhiye ya 'nahi' boliye. Kuch services ke liye active GST zaroori hai.",
    },
    "ask_gst_number": {
        "en": "Please type your 15-character GSTIN so I can check it. Or say 'skip' and I'll leave out services that need GST.",
        "hi": "कृपया अपना 15 अक्षर का GSTIN लिखें ताकि मैं जाँच सकूँ। या 'skip' लिखें, तब GST वाली सेवाएँ नहीं जोड़ूँगा।",
        "hinglish": "Apna 15 character ka GSTIN likhiye taaki main check kar sakun. Ya 'skip' likhiye, phir GST wali services nahi judengi.",
    },
    "ask_needs": {
        "en": "Anything specific you need? For example UPI billing, CCTV, WhatsApp for orders, email, or Wi-Fi for customers. Or say 'nothing else'.",
        "hi": "कुछ ख़ास चाहिए? जैसे UPI बिलिंग, CCTV, ऑर्डर के लिए WhatsApp, ईमेल, या ग्राहकों के लिए Wi-Fi। या 'बस इतना' लिखें।",
        "hinglish": "Kuch khaas chahiye? Jaise UPI billing, CCTV, orders ke liye WhatsApp, email, ya customers ke liye Wi-Fi. Ya 'bas itna' likhiye.",
    },
    "gst_invalid": {
        "en": "That GSTIN didn't pass the check ({reason}). Please re-type it, or say 'skip'.",
        "hi": "यह GSTIN जाँच में सही नहीं निकला ({reason})। दोबारा लिखें या 'skip' कहें।",
        "hinglish": "Yeh GSTIN check mein sahi nahi nikla ({reason}). Dobara likhiye ya 'skip' boliye.",
    },
    "gst_inactive": {
        "en": "Your GST registration shows as {status}. I'll suggest services that don't need GST for now.",
        "hi": "आपका GST रजिस्ट्रेशन {status} दिख रहा है। अभी के लिए बिना GST वाली सेवाएँ सुझा रहा हूँ।",
        "hinglish": "Aapka GST registration {status} dikh raha hai. Abhi ke liye bina GST wali services suggest kar raha hoon.",
    },
    "gst_ok": {
        "en": "GST verified for {name}.",
        "hi": "{name} का GST सत्यापित।",
        "hinglish": "{name} ka GST verified.",
    },
    "plan_intro": {
        "en": "Here's what fits a {type} with {staff} people{sites_text}:",
        "hi": "{staff} लोगों वाले {type}{sites_text} के लिए यह सही रहेगा:",
        "hinglish": "{staff} logon wale {type}{sites_text} ke liye yeh sahi rahega:",
    },
    "plan_outro": {
        "en": "That's {price} a month, all-in. Open the plan to compare options or add services.",
        "hi": "कुल {price} प्रति माह, सब शामिल। विकल्प देखने या सेवाएँ जोड़ने के लिए प्लान खोलें।",
        "hinglish": "Total {price} har mahine, sab shamil. Options dekhne ya services jodne ke liye plan kholiye.",
    },
    "survey": {
        "en": "A leased line needs a quick site survey. I've asked a specialist to call you to book it; your plan below works in the meantime.",
        "hi": "लीज़्ड लाइन के लिए साइट सर्वे ज़रूरी है। एक विशेषज्ञ आपको कॉल करेगा; तब तक नीचे वाला प्लान चल सकता है।",
        "hinglish": "Leased line ke liye site survey zaroori hai. Ek specialist aapko call karega; tab tak neeche wala plan chal sakta hai.",
    },
    "human": {
        "en": "Sure. A specialist from your city will call you. Share a mobile number if you'd like a specific one used.",
        "hi": "ज़रूर। आपके शहर से एक विशेषज्ञ आपको कॉल करेगा। चाहें तो मोबाइल नंबर लिख दें।",
        "hinglish": "Zaroor. Aapke shehar se ek specialist aapko call karega. Chahein to mobile number likh dijiye.",
    },
    "human_ok": {
        "en": "Thanks, a specialist will call you on {phone}.",
        "hi": "धन्यवाद, विशेषज्ञ आपको {phone} पर कॉल करेगा।",
        "hinglish": "Shukriya, specialist aapko {phone} par call karega.",
    },
    "unclear": {
        "en": "Sorry, I didn't catch that.",
        "hi": "माफ़ कीजिए, समझ नहीं पाया।",
        "hinglish": "Maaf kijiye, samajh nahi paaya.",
    },
    "done_followup": {
        "en": "I've updated your plan.",
        "hi": "आपका प्लान अपडेट कर दिया है।",
        "hinglish": "Aapka plan update kar diya hai.",
    },
}

CHIPS: dict[str, dict[str, list[str]]] = {
    "segment": {
        "en": ["Shop or store", "Clinic or office", "Several branches", "Factory or workshop"],
        "hi": ["दुकान", "क्लिनिक या ऑफ़िस", "कई ब्रांच", "फ़ैक्ट्री या वर्कशॉप"],
        "hinglish": ["Dukaan", "Clinic ya office", "Kai branch", "Factory ya workshop"],
    },
    "sites": {"en": ["1", "2", "3", "5"], "hi": ["1", "2", "3", "5"], "hinglish": ["1", "2", "3", "5"]},
    "city": {
        "en": ["Metro or big city", "Smaller city"],
        "hi": ["मेट्रो या बड़ा शहर", "छोटा शहर"],
        "hinglish": ["Metro ya bada shahar", "Chhota shahar"],
    },
    "gst": {"en": ["No GST yet"], "hi": ["अभी GST नहीं"], "hinglish": ["Abhi GST nahi"]},
    "needs": {
        "en": ["UPI billing", "CCTV", "WhatsApp", "Email", "Wi-Fi", "Nothing else"],
        "hi": ["UPI बिलिंग", "CCTV", "WhatsApp", "ईमेल", "वाईफाई", "बस इतना"],
        "hinglish": ["UPI billing", "CCTV", "WhatsApp", "Email", "Wi-Fi", "Bas itna"],
    },
}

# chip text -> what it means (so tapping a chip always extracts cleanly)
CHIP_MEANING: dict[str, str] = {
    "Shop or store": "shop",
    "Clinic or office": "office",
    "Several branches": "chain",
    "Factory or workshop": "factory",
    "दुकान": "shop",
    "क्लिनिक या ऑफ़िस": "office",
    "कई ब्रांच": "chain",
    "फ़ैक्ट्री या वर्कशॉप": "factory",
    "Dukaan": "shop",
    "Clinic ya office": "office",
    "Kai branch": "chain",
    "Factory ya workshop": "factory",
    "Metro or big city": "metro",
    "Smaller city": "smaller city",
    "मेट्रो या बड़ा शहर": "metro",
    "छोटा शहर": "smaller city",
    "Metro ya bada shahar": "metro",
    "Chhota shahar": "smaller city",
    "No GST yet": "no gst",
    "अभी GST नहीं": "no gst",
    "Abhi GST nahi": "no gst",
}

NOTHING_ELSE = (
    "nothing else",
    "bas itna",
    "बस इतना",
    "nothing",
    "no thanks",
    "that's all",
    "thats all",
    "kuch nahi",
    "nahi",
)


def t(key: str, lang: str, **kw) -> str:
    table = T[key]
    return table.get(lang, table["en"]).format(**kw)


def chips(key: str, lang: str) -> list[str]:
    table = CHIPS.get(key, {})
    return table.get(lang, table.get("en", []))
