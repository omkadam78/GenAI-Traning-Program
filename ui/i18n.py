"""Reviewed UI strings. Widget values stay canonical; only labels are translated."""

LANGUAGES = {"en": "English", "mr": "मराठी", "hi": "हिन्दी"}

# English key -> Marathi, Hindi. No model calls are needed to render the UI.
STRINGS = {
    "A helping hand for your harvest": ("तुमच्या पिकासाठी विश्वासू साथ", "आपकी फसल के लिए भरोसेमंद साथी"),
    "Understand your crop cover, estimate your premium, and know when to report a loss.": (
        "पीक विमा समजून घ्या, हप्त्याचा अंदाज काढा आणि नुकसान कधी कळवायचे ते जाणून घ्या.",
        "फसल बीमा समझें, प्रीमियम का अनुमान लगाएँ और नुकसान की सूचना देने का समय जानें।",
    ),
    "Information from official guidelines. Your insurer and state decide coverage and claims.": (
        "अधिकृत मार्गदर्शक तत्त्वांवर आधारित माहिती. विमा संरक्षण आणि दाव्याचा निर्णय विमा कंपनी व राज्य घेतात.",
        "आधिकारिक दिशानिर्देशों पर आधारित जानकारी। बीमा कंपनी और राज्य कवरेज व दावे का निर्णय लेते हैं।",
    ),
    "Start a new conversation": ("नवीन संवाद", "नई बातचीत"),
    "Official PMFBY portal": ("अधिकृत PMFBY पोर्टल", "आधिकारिक PMFBY पोर्टल"),
    "How can we help?": ("आम्ही कशी मदत करू?", "हम कैसे मदद करें?"),
    "Ask a question": ("प्रश्न विचारा", "सवाल पूछें"),
    "Estimate premium": ("हप्त्याचा अंदाज", "प्रीमियम का अनुमान"),
    "Report crop loss": ("नुकसान कळवण्याची मदत", "नुकसान की सूचना में मदद"),
    "Estimate what you may pay": ("तुमच्या विमा हप्त्याचा अंदाज", "आपके बीमा प्रीमियम का अनुमान"),
    "Use the scale of finance from your bank or notified crop details. This is not a quotation or payment.": (
        "बँक किंवा अधिसूचनेतील प्रति हेक्टर/एकर वित्तमान वापरा. हा अंदाज आहे; कोटेशन किंवा भरणा नाही.",
        "बैंक या अधिसूचना में दिया प्रति हेक्टेयर/एकड़ वित्तमान लें। यह अनुमान है, कोटेशन या भुगतान नहीं।",
    ),
    "Your crop": ("तुमचे पीक", "आपकी फसल"),
    "Choose a crop": ("पीक निवडा", "फसल चुनें"),
    "Growing season": ("पीक हंगाम", "फसल का मौसम"),
    "Choose a season": ("हंगाम निवडा", "मौसम चुनें"),
    "Soybean": ("सोयाबीन", "सोयाबीन"),
    "Wheat": ("गहू", "गेहूँ"),
    "Paddy": ("भात", "धान"),
    "Cotton": ("कापूस", "कपास"),
    "Gram": ("हरभरा", "चना"),
    "Mustard": ("मोहरी", "सरसों"),
    "Maize": ("मका", "मक्का"),
    "Onion": ("कांदा", "प्याज"),
    "Kharif": ("खरीप", "खरीफ"),
    "Rabi": ("रब्बी", "रबी"),
    "Land area": ("जमिनीचे क्षेत्र", "जमीन का क्षेत्र"),
    "Area measured in": ("क्षेत्राचे एकक", "क्षेत्र की इकाई"),
    "Hectares": ("हेक्टर", "हेक्टेयर"),
    "Acres": ("एकर", "एकड़"),
    "Scale of finance (₹)": ("प्रति एकक वित्तमान (₹)", "प्रति इकाई वित्तमान (₹)"),
    "Finance amount is for": ("वित्तमानाचे एकक", "वित्तमान की इकाई"),
    "One hectare": ("एक हेक्टर", "एक हेक्टेयर"),
    "One acre": ("एक एकर", "एक एकड़"),
    "Review my estimate": ("माहिती तपासून अंदाज काढा", "जानकारी जाँचकर अनुमान लगाएँ"),
    "Please choose your crop and season, and enter an area and finance amount greater than zero.": (
        "पीक व हंगाम निवडा. क्षेत्र आणि वित्तमान शून्यापेक्षा जास्त भरा.",
        "फसल व मौसम चुनें। क्षेत्र और वित्तमान शून्य से अधिक भरें।",
    ),
    "Know your reporting deadline": ("नुकसान कळवण्याची अंतिम वेळ", "नुकसान की सूचना की अंतिम समय-सीमा"),
    "When did the loss happen?": ("नुकसान कोणत्या दिवशी झाले?", "नुकसान किस दिन हुआ?"),
    "Approximate time of loss (India time)": (
        "नुकसानाची अंदाजे वेळ (भारतीय वेळ)",
        "नुकसान का लगभग समय (भारतीय समय)",
    ),
    "Show my deadline": ("अंतिम वेळ पाहा", "अंतिम समय देखें"),
    "Please enter both the date and the approximate time. We will not guess either.": (
        "तारीख आणि अंदाजे वेळ दोन्ही भरा. आम्ही ती गृहीत धरणार नाही.",
        "तारीख और लगभग समय दोनों भरें। हम अनुमान नहीं लगाएँगे।",
    ),
    "Please check the loss date and time. It must not be in the future.": (
        "नुकसानाची तारीख व वेळ तपासा. भविष्यातील वेळ चालणार नाही.",
        "नुकसान की तारीख व समय जाँचें। भविष्य का समय मान्य नहीं है।",
    ),
    "Time left to report": ("कळवण्यासाठी उरलेला वेळ", "सूचना देने का बचा समय"),
    "Ways to report": ("नुकसान कळवण्याचे मार्ग", "सूचना देने के तरीके"),
    "Read the official guidelines": ("अधिकृत मार्गदर्शक तत्त्वे वाचा", "आधिकारिक दिशानिर्देश पढ़ें"),
    "What would you like to know?": ("तुम्हाला काय जाणून घ्यायचे आहे?", "आप क्या जानना चाहेंगे?"),
    "Ask in your own words. For example:": (
        "तुमच्या भाषेत प्रश्न विचारा. उदाहरणार्थ:",
        "अपनी भाषा में सवाल पूछें। उदाहरण:",
    ),
    "What does insurance cover?": ("विमा कशासाठी मिळतो?", "बीमा किन नुकसानों को कवर करता है?"),
    "How much is the premium?": ("हप्ता किती आहे?", "प्रीमियम कितना है?"),
    "How do I report a loss?": ("नुकसान कसे कळवायचे?", "नुकसान की सूचना कैसे दें?"),
    "Read the official sources": ("अधिकृत स्रोत पाहा", "आधिकारिक स्रोत देखें"),
    "Are these details correct?": ("ही माहिती बरोबर आहे का?", "क्या यह जानकारी सही है?"),
    "Yes, calculate my estimate": ("होय, अंदाज काढा", "हाँ, अनुमान लगाएँ"),
    "Cancel": ("रद्द करा", "रद्द करें"),
    "Ask about your crop insurance…": ("पीक विम्याबद्दल प्रश्न विचारा…", "फसल बीमा के बारे में पूछें…"),
    "Checking the official guidance…": (
        "अधिकृत माहिती तपासत आहोत…",
        "आधिकारिक जानकारी जाँची जा रही है…",
    ),
    "Recovering your request…": ("तुमची विनंती पुन्हा तपासत आहोत…", "आपका अनुरोध फिर जाँचा जा रहा है…"),
    "Try again": ("पुन्हा प्रयत्न करा", "फिर कोशिश करें"),
    "Thank you. Your feedback has been saved.": (
        "धन्यवाद. तुमचा अभिप्राय जतन झाला.",
        "धन्यवाद। आपकी प्रतिक्रिया सहेजी गई।",
    ),
    "Feedback could not be saved. Please try again.": (
        "अभिप्राय जतन झाला नाही. पुन्हा प्रयत्न करा.",
        "प्रतिक्रिया सहेजी नहीं गई। फिर कोशिश करें।",
    ),
    "Keep these ready": ("ही माहिती तयार ठेवा", "यह जानकारी तैयार रखें"),
    "Download my reporting note": ("माझी नुकसान नोंद डाउनलोड करा", "मेरी नुकसान सूचना नोट डाउनलोड करें"),
    "This is a personal checklist, not a submitted claim.": (
        "ही वैयक्तिक यादी आहे; दावा सादर झालेला नाही.",
        "यह निजी सूची है; दावा जमा नहीं हुआ है।",
    ),
    "Crop and field location": ("पीक आणि शेताचे ठिकाण", "फसल और खेत का स्थान"),
    "Date, time and type of loss": ("नुकसानाची तारीख, वेळ व प्रकार", "नुकसान की तारीख, समय और प्रकार"),
    "Policy/application reference, if available": (
        "उपलब्ध असल्यास विमा/अर्ज क्रमांक",
        "उपलब्ध हो तो पॉलिसी/आवेदन संदर्भ",
    ),
    "Photos of the damage, if safe to take": (
        "सुरक्षित असल्यास नुकसानीचे फोटो",
        "सुरक्षित हो तो नुकसान की तस्वीरें",
    ),
    "Insurer or bank contact and reporting acknowledgement": (
        "विमा कंपनी/बँकेचा संपर्क आणि सूचना दिल्याची पावती",
        "बीमा कंपनी/बैंक संपर्क और सूचना की रसीद",
    ),
    "Your harvest, better understood.": ("तुमच्या पिकाला समजूतदार साथ.", "आपकी फसल को समझदार साथ।"),
    "Built for farmers. Independent guidance, not a government service.": (
        "शेतकऱ्यांसाठी. स्वतंत्र मार्गदर्शन; सरकारी सेवा नाही.",
        "किसानों के लिए। स्वतंत्र मार्गदर्शन, सरकारी सेवा नहीं।",
    ),
    "Confirmation only calculates an estimate. It does not buy insurance, take payment or submit a claim.": (
        "संमतीमुळे फक्त अंदाज काढला जातो. विमा खरेदी, भरणा किंवा दावा सादर होत नाही.",
        "पुष्टि से केवल अनुमान निकलेगा। बीमा खरीद, भुगतान या दावा जमा नहीं होगा।",
    ),
    "We cannot check your personal claim status or bank payments. Never share an Aadhaar number, account number, OTP or API key here.": (
        "वैयक्तिक दावा किंवा बँक भरणा आम्ही तपासू शकत नाही. आधार, खाते क्रमांक, OTP किंवा API key येथे देऊ नका.",
        "हम निजी दावे या बैंक भुगतान नहीं जाँच सकते। आधार, खाता नंबर, OTP या API key यहाँ न दें।",
    ),
}


def translate(text: str, language: str = "en") -> str:
    if language == "en" or text not in STRINGS:
        return text
    return STRINGS[text][0 if language == "mr" else 1]


STRINGS.update(
    {
        "Check the details below, then confirm or cancel the estimate.": (
            "खालील माहिती तपासा, नंतर अंदाजासाठी संमती द्या किंवा रद्द करा.",
            "नीचे जानकारी जाँचें, फिर अनुमान की पुष्टि करें या रद्द करें।",
        ),
        "Your latest estimate": ("तुमचा नवीनतम अंदाज", "आपका नवीनतम अनुमान"),
        "Sum insured": ("विम्याची रक्कम", "बीमित राशि"),
        "Estimated maximum premium": ("हप्त्याचा कमाल अंदाज", "अधिकतम प्रीमियम अनुमान"),
        "Farmer premium": ("शेतकऱ्याचा हप्ता", "किसान का प्रीमियम"),
        "An estimate, not a payment or claim approval.": (
            "हा अंदाज आहे; भरणा किंवा दाव्याची मंजुरी नाही.",
            "यह अनुमान है; भुगतान या दावे की मंजूरी नहीं।",
        ),
        "Report by": ("कळवण्याची अंतिम वेळ:", "सूचना देने का अंतिम समय:"),
        "**Ways to report**": ("**नुकसान कळवण्याचे मार्ग**", "**सूचना देने के तरीके**"),
        "For the localized-calamity / post-harvest cases covered by the cited guidelines, the reporting window is 72 hours. Do not wait for this app to submit a claim: contact your insurer, bank or agriculture office.": (
            "मार्गदर्शक तत्त्वांतील स्थानिक आपत्ती व काढणीनंतरच्या लागू नुकसानीसाठी ७२ तासांत कळवा. हे अ‍ॅप दावा सादर करत नाही. विमा कंपनी, बँक किंवा कृषी कार्यालयाशी त्वरित संपर्क करा.",
            "दिशानिर्देशों में लागू स्थानीय आपदा व कटाई के बाद के नुकसान की सूचना ७२ घंटों में दें। यह ऐप दावा जमा नहीं करता। बीमा कंपनी, बैंक या कृषि कार्यालय से तुरंत संपर्क करें।",
        ),
        "The deadline could not be read. Please check the event again.": (
            "अंतिम वेळ वाचता आली नाही. तारीख व वेळ पुन्हा तपासा.",
            "अंतिम समय पढ़ा नहीं जा सका। तारीख व समय फिर जाँचें।",
        ),
        "The calculated reporting window has passed. Contact your insurer or agriculture office promptly for guidance. This app cannot decide claim eligibility.": (
            "गणनेनुसार कळवण्याची वेळ संपली आहे. विमा कंपनी किंवा कृषी कार्यालयाशी त्वरित संपर्क करा. दाव्याची पात्रता हे अ‍ॅप ठरवत नाही.",
            "गणना के अनुसार सूचना का समय बीत चुका है। बीमा कंपनी या कृषि कार्यालय से तुरंत संपर्क करें। यह ऐप दावे की पात्रता तय नहीं करता।",
        ),
        "The deadline service is unavailable. Please report urgent losses directly to your insurer.": (
            "सेवा उपलब्ध नाही. तातडीचे नुकसान थेट विमा कंपनीला कळवा.",
            "सेवा उपलब्ध नहीं है। जरूरी नुकसान की सूचना सीधे बीमा कंपनी को दें।",
        ),
        "The service is not reachable right now. Please try again shortly.": (
            "सेवा सध्या उपलब्ध नाही. थोड्या वेळाने पुन्हा प्रयत्न करा.",
            "सेवा अभी उपलब्ध नहीं है। थोड़ी देर में फिर कोशिश करें।",
        ),
        "We could not complete this request. Please try again.": (
            "विनंती पूर्ण झाली नाही. पुन्हा प्रयत्न करा.",
            "अनुरोध पूरा नहीं हुआ। फिर कोशिश करें।",
        ),
        "Crop Insurance App (National Crop Insurance Portal)": (
            "पीक विमा अ‍ॅप (राष्ट्रीय पीक विमा पोर्टल)",
            "फसल बीमा ऐप (राष्ट्रीय फसल बीमा पोर्टल)",
        ),
        "Krishi Rakshak Helpline: 14447": ("कृषी रक्षक हेल्पलाइन: 14447", "कृषि रक्षक हेल्पलाइन: 14447"),
        "Concerned Insurance Company Toll-Free Number": (
            "संबंधित विमा कंपनीचा टोल-फ्री क्रमांक",
            "संबंधित बीमा कंपनी का टोल-फ्री नंबर",
        ),
        "Bank Branch / PACS where premium was debited": (
            "हप्ता भरलेली बँक शाखा / PACS",
            "जिस बैंक शाखा / PACS में प्रीमियम जमा हुआ",
        ),
        "Local Agriculture Officer / Revenue Authority": (
            "स्थानिक कृषी अधिकारी / महसूल विभाग",
            "स्थानीय कृषि अधिकारी / राजस्व विभाग",
        ),
    }
)
