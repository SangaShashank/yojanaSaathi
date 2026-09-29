/**
 * Yojana Saathi — Frontend Application Controller (Phase 9)
 * Orchestrates views, state reconciliation, multilingual localization,
 * voice interaction, and CSC/VLE mode.
 */

// =========================================================================
// 1. MULTILINGUAL LOCALIZATION DICTIONARY
// =========================================================================
const I18N = {
  en: {
    brand_name: "Yojana Saathi",
    brand_tagline: "AI Welfare-Access Assistant • Citizen & CSC/VLE",
    nav_home: "Home",
    nav_chat: "Saathi Chat & Voice",
    nav_profile: "Citizen Profile",
    nav_schemes: "Scheme Discovery",
    nav_applications: "Applications",
    nav_documents: "Documents & OCR",
    nav_readiness: "Readiness",
    nav_handoff: "Pre-Submission & Handoff",
    nav_recovery: "Rejection & Recovery",
    hero_badge: "✨ Agentic AI Welfare Access • Public Assistance",
    hero_title: "Empowering Citizens & CSC Operators with Clear Welfare Guidance",
    hero_desc: "Yojana Saathi guides citizens, small farmers, women, and rural beneficiaries through government scheme eligibility, document verification, preparation readiness, and rejection recovery. Speak or type in English, Hindi, or Telugu.",
    disclaimer_heading: "Supported Curated Schemes Only:",
    disclaimer_body: "Yojana Saathi assists with a curated dataset of supported central and state welfare programs. It does not claim exhaustive national coverage and does not perform direct live government portal submissions.",
    card_start_title: "Start New Case",
    card_start_desc: "Begin an assistance session. Chat or speak naturally to identify eligible schemes and collect profile facts.",
    card_resume_title: "Continue Existing Case",
    card_resume_desc: "Enter a Case ID to resume profile confirmation, document uploads, readiness evaluation, or recovery.",
    card_vle_title: "CSC / VLE Operator Mode",
    card_vle_desc: "Dedicated high-efficiency interface for Village Level Entrepreneurs. Manage citizen dossiers, manual edits, and handoff packets.",
    feat_voice_title: "Multilingual Voice",
    feat_voice_desc: "Speak in Hindi, Telugu, or English with browser audio playback and typed fallback.",
    feat_confirm_title: "Human Confirmation",
    feat_confirm_desc: "Extracted facts require your confirmation before deterministic eligibility checks.",
    feat_multi_title: "Independent Tracks",
    feat_multi_desc: "Apply for multiple schemes in parallel with isolated document and recovery states.",
    feat_handoff_title: "CSC/VLE Handoff",
    feat_handoff_desc: "Generate official reference sheets and dossiers ready for verified physical submission.",
    welcome_chat_msg: "Namaste! I am your Yojana Saathi welfare assistant. Please tell me about yourself, your occupation, land ownership, annual income, or welfare schemes you need help with. You can type or use the microphone button below.",
    chat_input_placeholder: "Type your message here... (e.g., 'I am a 32-year-old small farmer from Telangana with 2 acres of land')",
    btn_send: "Send",
    transcript_label: "Heard:",
    profile_title: "Citizen Profile",
    profile_subtitle: "Confirmed attributes, unknown parameters, and pending proposed facts.",
    confirmed_facts_title: "Authoritative Confirmed Facts",
    unknown_facts_title: "Unknown / Unspecified Parameters",
    unknown_facts_desc: "These fields have not been provided or confirmed. The eligibility engine strictly treats these as UNKNOWN (not 0, not false, and not assumed).",
    pending_heading: "Proposed Profile Updates",
    pending_desc: "Please review these facts extracted from your statements. Confirming will update your authoritative profile and re-evaluate scheme eligibility.",
    schemes_title: "Supported Welfare Schemes",
    schemes_subtitle: "All 13 supported schemes are evaluated deterministically. Schemes are displayed neutrally with no subjective scoring or ranking.",
    apps_title: "Independent Application Tracks",
    apps_subtitle: "Each selected scheme creates an isolated application with independent lifecycle, document verification, and recovery state.",
    docs_title: "Document Requirements & OCR",
    docs_subtitle: "Upload required certificates and identity records. Real OCR text extraction and discrepancy checking without automatic rejection.",
    readiness_title: "Application Readiness Check",
    readiness_subtitle: "Systematic readiness audit for profile completeness, verified documents, and handoff prerequisites.",
    handoff_title: "Pre-Submission Review & CSC/VLE Handoff",
    handoff_subtitle: "Compile verified application dossiers and physical CSC reference sheets ready for official operator submission.",
    recovery_title: "Rejection Evidence & Stateful Recovery",
    recovery_subtitle: "Bounded root-cause decoding and stateful recovery actions for rejected government welfare applications.",
  },
  hi: {
    brand_name: "योजना साथी",
    brand_tagline: "एआई कल्याणकारी सहायता • नागरिक एवं सीएससी/वीएलई",
    nav_home: "होम",
    nav_chat: "साथी चैट एवं आवाज़",
    nav_profile: "नागरिक प्रोफ़ाइल",
    nav_schemes: "योजना खोज",
    nav_applications: "आवेदन",
    nav_documents: "दस्तावेज़ एवं ओसीआर",
    nav_readiness: "तैयारी स्थिति",
    nav_handoff: "हैंडऑफ़ दस्तावेज़",
    nav_recovery: "अस्वीकृति एवं सुधार",
    hero_badge: "✨ एजेंटिक एआई कल्याणकारी पहुंच • सार्वजनिक सहायता",
    hero_title: "नागरिकों और सीएससी संचालकों को स्पष्ट सरकारी योजना मार्गदर्शन",
    hero_desc: "योजना साथी नागरिकों, छोटे किसानों, महिलाओं और ग्रामीण लाभार्थियों को पात्रता, दस्तावेज़ सत्यापन और अस्वीकृति सुधार में मार्गदर्शन करता है। हिंदी, तेलुगु या अंग्रेजी में बोलें या टाइप करें।",
    disclaimer_heading: "केवल समर्थित योजनाएं:",
    disclaimer_body: "योजना साथी समर्थित केंद्रीय और राज्य योजनाओं के साथ सहायता करता है। यह संपूर्ण राष्ट्रीय कवरेज का दावा नहीं करता और न ही सीधे सरकारी पोर्टल पर आवेदन जमा करता है।",
    card_start_title: "नया केस शुरू करें",
    card_start_desc: "सहायता सत्र शुरू करें। पात्र योजनाओं की पहचान और प्रोफ़ाइल जानकारी एकत्र करने के लिए बोलें या लिखें।",
    card_resume_title: "मौजूदा केस जारी रखें",
    card_resume_desc: "प्रोफ़ाइल पुष्टि, दस्तावेज़ अपलोड या सुधार जारी रखने के लिए केस आईडी दर्ज करें।",
    card_vle_title: "सीएससी / वीएलई संचालक मोड",
    card_vle_desc: "ग्राम स्तर के उद्यमियों के लिए समर्पित उच्च-दक्षता इंटरफ़ेस। नागरिक डोज़ियर और संदर्भ पत्र प्रबंधित करें।",
    feat_voice_title: "बहुभाषी आवाज़",
    feat_voice_desc: "हिंदी, तेलुगु या अंग्रेजी में बोलें और ब्राउज़र ऑडियो सुनें। टाइप करने का विकल्प सदैव उपलब्ध।",
    feat_confirm_title: "मानव पुष्टि",
    feat_confirm_desc: "नियम-आधारित पात्रता जांच से पहले आपकी सहमति आवश्यक है।",
    feat_multi_title: "स्वतंत्र आवेदन",
    feat_multi_desc: "अलग-अलग दस्तावेज़ों और पुनर्प्राप्ति स्थिति के साथ कई योजनाओं के लिए एक साथ आवेदन करें।",
    feat_handoff_title: "सीएससी/वीएलई हैंडऑफ़",
    feat_handoff_desc: "सत्यापित भौतिक प्रस्तुति के लिए आधिकारिक संदर्भ पत्र और डोज़ियर तैयार करें।",
    welcome_chat_msg: "नमस्ते! मैं आपका योजना साथी सहायक हूँ। कृपया मुझे अपने बारे में, अपने व्यवसाय, भूमि स्वामित्व, वार्षिक आय या उन योजनाओं के बारे में बताएं जिनमें आपको सहायता चाहिए। आप नीचे दिए गए माइक से बोल सकते हैं या टाइप कर सकते हैं।",
    chat_input_placeholder: "अपना संदेश यहाँ लिखें... (उदा. 'मैं तेलंगाना से 32 वर्षीय किसान हूँ और मेरे पास 2 एकड़ ज़मीन है')",
    btn_send: "भेजें",
    transcript_label: "सुना गया:",
    profile_title: "नागरिक प्रोफ़ाइल",
    profile_subtitle: "पुष्टि किए गए विवरण, अज्ञात पैरामीटर और लंबित प्रस्तावित तथ्य।",
    confirmed_facts_title: "आधिकारिक पुष्टि किए गए तथ्य",
    unknown_facts_title: "अज्ञात / अनिर्दिष्ट पैरामीटर",
    unknown_facts_desc: "ये विवरण अभी तक प्रदान नहीं किए गए हैं। पात्रता इंजन इन्हें अज्ञात (UNKNOWN) मानता है (शून्य या असत्य नहीं)।",
    pending_heading: "प्रस्तावित प्रोफ़ाइल अद्यतन",
    pending_desc: "कृपया अपने बयानों से निकाले गए इन तथ्यों की समीक्षा करें। पुष्टि करने से प्रोफ़ाइल अद्यतन होगी।",
    schemes_title: "समर्थित कल्याणकारी योजनाएं",
    schemes_subtitle: "सभी 13 योजनाओं का तटस्थ मूल्यांकन किया जाता है। किसी भी योजना को रैंकिंग या वरीयता नहीं दी जाती।",
    apps_title: "स्वतंत्र आवेदन ट्रैक",
    apps_subtitle: "प्रत्येक चुनी गई योजना के लिए अलग आवेदन, दस्तावेज़ और सुधार चक्र बनता है।",
    docs_title: "दस्तावेज़ आवश्यकताएं एवं ओसीआर",
    docs_subtitle: "आवश्यक प्रमाण पत्र अपलोड करें। वास्तविक ओसीआर निष्कर्षण एवं विसंगति जांच बिना स्वचालित अस्वीकृति के।",
    readiness_title: "आवेदन तैयारी जांच",
    readiness_subtitle: "प्रोफ़ाइल पूर्णता, सत्यापित दस्तावेज़ों और हैंडऑफ़ आवश्यकताओं का व्यवस्थित ऑडिट।",
    handoff_title: "पूर्व-प्रस्तुति समीक्षा एवं सीएससी हैंडऑफ़",
    handoff_subtitle: "आधिकारिक संचालक प्रस्तुति के लिए सत्यापित आवेदन डोज़ियर और सीएससी संदर्भ पत्र संकलित करें।",
    recovery_title: "अस्वीकृति प्रमाण एवं स्थिति सुधार",
    recovery_subtitle: "अस्वीकृत सरकारी कल्याणकारी आवेदनों के मूल कारण की पहचान और सुधारात्मक कार्रवाई।",
  },
  te: {
    brand_name: "యోజన సాథి",
    brand_tagline: "AI సంక్షేమ ప్రాప్యత సహాయకుడు • పౌరుడు మరియు CSC/VLE",
    nav_home: "హోమ్",
    nav_chat: "సాథి చాట్ & వాయిస్",
    nav_profile: "పౌర ప్రొఫైల్",
    nav_schemes: "పథకాల అన్వేషణ",
    nav_applications: "దరఖాస్తులు",
    nav_documents: "పత్రాలు & OCR",
    nav_readiness: "సిద్ధత తనిఖీ",
    nav_handoff: "సమర్పణ పూర్వ పత్రాలు",
    nav_recovery: "తిరస్కరణ & పునరుద్ధరణ",
    hero_badge: "✨ ఏజెంటిక్ AI సంక్షేమ ప్రాప్యత • ప్రజా సహాయం",
    hero_title: "పౌరులు మరియు CSC ఆపరేటర్లకు స్పష్టమైన సంక్షేమ పథక మార్గదర్శకత్వం",
    hero_desc: "యోజన సాథి పౌరులు, చిన్న రైతులు, మహిళలు మరియు గ్రామీణ లబ్ధిదారులకు పథకాల అర్హత, పత్రాల ధృవీకరణ మరియు పునరుద్ధరణలో సహాయం చేస్తుంది. తెలుగు, హిందీ లేదా ఇంగ్లీషులో మాట్లాడండి లేదా టైప్ చేయండి.",
    disclaimer_heading: "మద్దతు ఉన్న పథకాలు మాత్రమే:",
    disclaimer_body: "యోజన సాథి ఎంపిక చేసిన కేంద్ర మరియు రాష్ట్ర సంక్షేమ పథకాలకు మాత్రమే మార్గదర్శనం చేస్తుంది. ఇది ప్రభుత్వ పోర్టల్ సమర్పణలను నేరుగా చేయదు.",
    card_start_title: "కొత్త కేస్ ప్రారంభించండి",
    card_start_desc: "సహాయక సెషన్ ప్రారంభించండి. అర్హత గల పథకాలను కనుగొనడానికి మాట్లాడండి లేదా టైప్ చేయండి.",
    card_resume_title: "ఉన్న కేస్ కొనసాగించండి",
    card_resume_desc: "ప్రొఫైల్ ధృవీకరణ లేదా పత్రాల అప్‌లోడ్ కొనసాగించడానికి కేస్ ID నమోదు చేయండి.",
    card_vle_title: "CSC / VLE ఆపరేటర్ మోడ్",
    card_vle_desc: "గ్రామ స్థాయి వ్యవస్థాపకుల కోసం ప్రత్యేక అధిక-సామర్థ్య ఇంటర్‌ఫేస్. పౌరుల డాసియర్లు మరియు రిఫరెన్స్ షీట్లను నిర్వహించండి.",
    feat_voice_title: "బహుభాషా వాయిస్",
    feat_voice_desc: "తెలుగు, హిందీ లేదా ఇంగ్లీషులో మాట్లాడండి మరియు బ్రౌజర్ ఆడియో వినండి.",
    feat_confirm_title: "మానవ ధృవీకరణ",
    feat_confirm_desc: "అర్హత గణనకు ముందు మీ నిర్ధారణ తప్పనిసరి.",
    feat_multi_title: "స్వతంత్ర ట్రాక్స్",
    feat_multi_desc: "ఒకేసారి బహుళ పథకాలకు స్వతంత్ర పత్రాలు మరియు పునరుద్ధరణ స్థితులతో దరఖాస్తు చేసుకోండి.",
    feat_handoff_title: "CSC/VLE హ్యాండ్‌ఆఫ్",
    feat_handoff_desc: "ధృవీకరించబడిన సమర్పణ కోసం అధికారిక రిఫరెన్స్ షీట్లు మరియు డాసియర్లను రూపొందించండి.",
    welcome_chat_msg: "నమస్కారం! నేను మీ యోజన సాథి సంక్షేమ సహాయకుడిని. దయచేసి మీ గురించి, మీ వృత్తి, భూమి యాజమాన్యం, వార్షిక ఆదాయం లేదా మీకు కావాల్సిన పథకాల గురించి చెప్పండి. మైక్ ద్వారా మాట్లాడవచ్చు లేదా టైప్ చేయవచ్చు.",
    chat_input_placeholder: "మీ సందేశాన్ని ఇక్కడ టైప్ చేయండి... (ఉదా. 'నేను తెలంగాణ నుండి 32 ఏళ్ల రైతును, నాకు 2 ఎకరాల భూమి ఉంది')",
    btn_send: "పంపండి",
    transcript_label: "విన్నది:",
    profile_title: "పౌర ప్రొఫైల్",
    profile_subtitle: "ధృవీకరించబడిన వివరాలు, తెలియని పారామితులు మరియు ప్రతిపాదిత అంశాలు.",
    confirmed_facts_title: "అధికారికంగా ధృవీకరించబడిన వాస్తవాలు",
    unknown_facts_title: "తెలియని / పేర్కొనబడని వివరాలు",
    unknown_facts_desc: "ఈ వివరాలు ఇంకా అందించబడలేదు. అర్హత ఇంజిన్ వీటిని UNKNOWN గా మాత్రమే పరిగణిస్తుంది.",
    pending_heading: "ప్రతిపాదిత ప్రొఫైల్ మార్పులు",
    pending_desc: "మీ మాటల నుండి సేకరించిన అంశాలను సమీక్షించండి. నిర్ధారించిన తర్వాత ప్రొఫైల్ అప్‌డేట్ అవుతుంది.",
    schemes_title: "మద్దతు ఉన్న సంక్షేమ పథకాలు",
    schemes_subtitle: "మొత్తం 13 పథకాలు నిష్పక్షపాతంగా అంచనా వేయబడతాయి. ఎటువంటి ర్యాంకింగ్ లేదా స్కోరింగ్ ఉండదు.",
    apps_title: "స్వతంత్ర దరఖాస్తు ట్రాక్స్",
    apps_subtitle: "ఎంచుకున్న ప్రతి పథకం స్వతంత్ర లైఫ్‌సైకిల్ మరియు పునరుద్ధరణ స్థితిని కలిగి ఉంటుంది.",
    docs_title: "పత్రాల అవసరాలు & OCR",
    docs_subtitle: "అవసరమైన పత్రాలను అప్‌లోడ్ చేయండి. స్వయంచాలక తిరస్కరణ లేకుండా నిజమైన OCR టెక్స్ట్ పరిశీలన.",
    readiness_title: "దరఖాస్తు సిద్ధత తనిఖీ",
    readiness_subtitle: "ప్రొఫైల్ సంపూర్ణత మరియు పత్రాల ధృవీకరణ కోసం క్రమబద్ధమైన సిద్ధత ఆడిట్.",
    handoff_title: "సమర్పణ పూర్వ సమీక్ష & CSC హ్యాండ్‌ఆఫ్",
    handoff_subtitle: "అధికారిక సమర్పణ కోసం డాసియర్ మరియు CSC రిఫరెన్స్ షీట్‌ను సిద్ధం చేయండి.",
    recovery_title: "తిరస్కరణ ఆధారాలు & పునరుద్ధరణ",
    recovery_subtitle: "తిరస్కరించబడిన దరఖాస్తుల మూల కారణాన్ని గుర్తించి సరిదిద్దే చర్యలు చేపట్టండి.",
  }
};

// =========================================================================
// 2. APPLICATION STATE
// =========================================================================
class AppState {
  constructor() {
    this.caseId = null;
    this.caseData = null;
    this.profile = null;
    this.evaluations = [];
    this.applications = {};
    this.activeApplicationId = null;
    this.selectedSchemeIds = new Set();
    this.activeView = 'landing';
    this.mode = 'citizen'; // 'citizen' or 'vle'
    this.language = 'en'; // 'en', 'hi', or 'te'
    this.audioRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.recordingStartTime = null;
    this.recordingTimerId = null;
    this.currentAudioBlob = null;
    this.speechUtterance = null;
  }
}

const state = new AppState();

// =========================================================================
// 3. UI INITIALIZATION & EVENT BINDINGS
// =========================================================================
document.addEventListener('DOMContentLoaded', async () => {
  initUrlParams();
  bindNavigation();
  bindHeaderControls();
  bindLandingActions();
  bindChatControls();
  bindVoiceControls();
  bindProfileActions();
  bindSchemeActions();
  bindApplicationActions();
  bindDocumentActions();
  bindReadinessActions();
  bindHandoffActions();
  bindRecoveryActions();
  bindModals();
  applyLanguage(state.language);

  // If a case ID was passed or stored in localStorage, restore it
  const storedCaseId = state.caseId || localStorage.getItem('yojana_case_id');
  if (storedCaseId) {
    try {
      await loadCase(storedCaseId);
    } catch (e) {
      console.warn("Could not restore stored case:", e);
      localStorage.removeItem('yojana_case_id');
      state.caseId = null;
      updateCaseHeaderBadge();
    }
  } else {
    updateCaseHeaderBadge();
  }

  // Preload scheme catalog in background
  loadSchemesCatalog();
});

function initUrlParams() {
  const urlParams = new URLSearchParams(window.location.search);
  const cid = urlParams.get('case_id');
  const lang = urlParams.get('lang');
  const mode = urlParams.get('mode');

  if (cid) state.caseId = cid;
  if (lang && ['en', 'hi', 'te'].includes(lang)) state.language = lang;
  if (mode && ['citizen', 'vle'].includes(mode)) state.mode = mode;

  const langSelect = document.getElementById('lang-select');
  if (langSelect) langSelect.value = state.language;

  applyMode(state.mode);
}

function updateUrlParams() {
  const url = new URL(window.location);
  if (state.caseId) url.searchParams.set('case_id', state.caseId);
  else url.searchParams.delete('case_id');
  url.searchParams.set('lang', state.language);
  url.searchParams.set('mode', state.mode);
  window.history.replaceState({}, '', url);
}

// =========================================================================
// 4. NAVIGATION & VIEW SWITCHING
// =========================================================================
function bindNavigation() {
  const navTabs = document.querySelectorAll('.nav-tab');
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetView = tab.getAttribute('data-view');
      switchView(targetView);
    });
  });

  const logo = document.getElementById('brand-logo');
  if (logo) {
    logo.addEventListener('click', () => switchView('landing'));
    logo.addEventListener('keydown', (e) => { if (e.key === 'Enter') switchView('landing'); });
  }
}

function switchView(viewName) {
  state.activeView = viewName;

  document.querySelectorAll('.nav-tab').forEach(tab => {
    const isTarget = tab.getAttribute('data-view') === viewName;
    tab.classList.toggle('active', isTarget);
    tab.setAttribute('aria-selected', isTarget ? 'true' : 'false');
  });

  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `view-${viewName}`);
  });

  // Trigger view-specific refreshes
  if (viewName === 'profile') renderProfileView();
  else if (viewName === 'schemes') renderSchemesView();
  else if (viewName === 'applications') renderApplicationsView();
  else if (viewName === 'documents') renderDocumentsView();
  else if (viewName === 'readiness') renderReadinessView();
  else if (viewName === 'handoff') renderHandoffView();
  else if (viewName === 'recovery') renderRecoveryView();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// =========================================================================
// 5. LANGUAGE & LOCALIZATION
// =========================================================================
function applyLanguage(lang) {
  state.language = lang;
  const dict = I18N[lang] || I18N.en;

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) el.textContent = dict[key];
  });

  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (dict[key]) el.placeholder = dict[key];
  });

  updateUrlParams();
}

function bindHeaderControls() {
  const langSelect = document.getElementById('lang-select');
  if (langSelect) {
    langSelect.addEventListener('change', (e) => {
      applyLanguage(e.target.value);
      showToast(`Language set to ${e.target.value.toUpperCase()}`, 'info');
    });
  }

  const modeBtn = document.getElementById('mode-toggle-btn');
  if (modeBtn) {
    modeBtn.addEventListener('click', () => {
      const newMode = state.mode === 'citizen' ? 'vle' : 'citizen';
      applyMode(newMode);
      showToast(newMode === 'vle' ? 'Switched to CSC/VLE Assisted Mode' : 'Switched to Citizen Mode', 'info');
    });
  }

  const openModalBtn = document.getElementById('btn-open-case-modal');
  if (openModalBtn) openModalBtn.addEventListener('click', () => openModal('modal-open-case'));

  const newModalBtn = document.getElementById('btn-new-case-modal');
  if (newModalBtn) newModalBtn.addEventListener('click', () => openModal('modal-new-case'));

  const vleAuditBtn = document.getElementById('btn-view-audit-log');
  if (vleAuditBtn) vleAuditBtn.addEventListener('click', openAuditLogModal);

  const vleSyncBtn = document.getElementById('btn-refresh-state');
  if (vleSyncBtn) vleSyncBtn.addEventListener('click', async () => {
    if (state.caseId) {
      await refreshCaseState();
      showToast('Case state synchronized with PostgreSQL', 'success');
    }
  });
}

function applyMode(mode) {
  state.mode = mode;
  const isVle = mode === 'vle';
  const vleBar = document.getElementById('vle-operator-bar');
  const modeLabel = document.getElementById('mode-label');
  const modeIcon = document.getElementById('mode-icon');

  if (vleBar) vleBar.style.display = isVle ? 'flex' : 'none';
  if (modeLabel) modeLabel.textContent = isVle ? 'CSC / VLE Mode' : 'Citizen Mode';
  if (modeIcon) modeIcon.textContent = isVle ? '🏢' : '👤';

  document.body.classList.toggle('mode-vle-active', isVle);
  updateUrlParams();
}

function updateCaseHeaderBadge() {
  const badge = document.getElementById('case-status-badge');
  const badgeText = document.getElementById('case-badge-text');
  const vleCaseId = document.getElementById('vle-case-id');
  const vleStage = document.getElementById('vle-stage');
  const vleGaps = document.getElementById('vle-gaps-count');
  const vleApps = document.getElementById('vle-apps-count');

  if (!state.caseId) {
    if (badge) badge.className = 'case-badge';
    if (badgeText) badgeText.textContent = 'No Active Case';
    if (vleCaseId) vleCaseId.textContent = 'None';
    return;
  }

  const shortId = state.caseId.slice(0, 8);
  const stage = state.caseData ? state.caseData.stage : 'ACTIVE';
  if (badge) badge.className = 'case-badge active';
  if (badgeText) badgeText.textContent = `Case #${shortId} • ${stage}`;
  if (vleCaseId) vleCaseId.textContent = state.caseId;
  if (vleStage) vleStage.textContent = stage;

  if (vleGaps && state.caseData) {
    vleGaps.textContent = (state.caseData.missing_information || []).length;
  }
  if (vleApps) {
    vleApps.textContent = Object.keys(state.applications || {}).length;
  }
}

// =========================================================================
// 6. CASE LIFECYCLE (CREATE / LOAD / REFRESH)
// =========================================================================
async function createNewCase(goal) {
  try {
    const res = await window.api.createCase(goal || "Identify applicable welfare schemes and orchestrate readiness");
    state.caseId = res.case_id;
    state.caseData = res;
    localStorage.setItem('yojana_case_id', state.caseId);
    updateUrlParams();
    updateCaseHeaderBadge();
    closeModal('modal-new-case');
    showToast(`Case #${res.case_id.slice(0, 8)} created successfully`, 'success');
    
    // Clear chat and add welcome
    clearChatMessages();
    addChatMessage('agent', I18N[state.language].welcome_chat_msg);

    await refreshCaseState();
    switchView('chat');
  } catch (err) {
    showToast(`Failed to create case: ${err.message}`, 'error');
  }
}

async function loadCase(caseId) {
  if (!caseId) return;
  try {
    const caseData = await window.api.getCase(caseId);
    state.caseId = caseId;
    state.caseData = caseData;
    localStorage.setItem('yojana_case_id', caseId);
    updateUrlParams();
    updateCaseHeaderBadge();
    closeModal('modal-open-case');
    showToast(`Loaded Case #${caseId.slice(0, 8)}`, 'success');

    await refreshCaseState();
    switchView('profile');
  } catch (err) {
    showToast(`Could not load case '${caseId}': ${err.message}`, 'error');
    throw err;
  }
}

async function refreshCaseState() {
  if (!state.caseId) return;
  try {
    const [caseData, profileData, schemesData, appsData] = await Promise.all([
      window.api.getCase(state.caseId),
      window.api.getProfile(state.caseId),
      window.api.getCaseSchemes(state.caseId).catch(() => ({ schemes: [] })),
      window.api.getApplications(state.caseId).catch(() => ({ applications: [] })),
    ]);

    state.caseData = caseData;
    state.profile = profileData;
    state.evaluations = schemesData.schemes || [];
    
    // Rebuild applications map
    state.applications = {};
    if (appsData.applications) {
      appsData.applications.forEach(app => {
        state.applications[app.application_id] = app;
      });
      // Set active application if none selected or not in map
      const appIds = Object.keys(state.applications);
      if (appIds.length > 0 && (!state.activeApplicationId || !state.applications[state.activeApplicationId])) {
        state.activeApplicationId = appIds[0];
      }
    }

    updateCaseHeaderBadge();
    updatePendingConfirmationBanner();
    populateApplicationSelectors();

    // Re-render current active view
    if (state.activeView === 'profile') renderProfileView();
    else if (state.activeView === 'schemes') renderSchemesView();
    else if (state.activeView === 'applications') renderApplicationsView();
    else if (state.activeView === 'documents') renderDocumentsView();
    else if (state.activeView === 'readiness') renderReadinessView();
    else if (state.activeView === 'handoff') renderHandoffView();
    else if (state.activeView === 'recovery') renderRecoveryView();

  } catch (err) {
    console.error("Error refreshing case state:", err);
  }
}

// =========================================================================
// 7. LANDING PAGE ACTIONS
// =========================================================================
function bindLandingActions() {
  const btnStart = document.getElementById('btn-landing-start');
  const cardStart = document.getElementById('card-start-case');
  const btnResume = document.getElementById('btn-landing-resume');
  const cardResume = document.getElementById('card-resume-case');
  const btnVle = document.getElementById('btn-landing-vle');
  const cardVle = document.getElementById('card-vle-mode');

  const triggerStart = () => openModal('modal-new-case');
  const triggerResume = () => openModal('modal-open-case');
  const triggerVle = () => {
    applyMode('vle');
    if (!state.caseId) openModal('modal-new-case');
    else switchView('profile');
  };

  if (btnStart) btnStart.addEventListener('click', (e) => { e.stopPropagation(); triggerStart(); });
  if (cardStart) cardStart.addEventListener('click', triggerStart);
  if (btnResume) btnResume.addEventListener('click', (e) => { e.stopPropagation(); triggerResume(); });
  if (cardResume) cardResume.addEventListener('click', triggerResume);
  if (btnVle) btnVle.addEventListener('click', (e) => { e.stopPropagation(); triggerVle(); });
  if (cardVle) cardVle.addEventListener('click', triggerVle);
}

// =========================================================================
// 8. CHAT & CONVERSATIONAL WORKSPACE
// =========================================================================
function bindChatControls() {
  const form = document.getElementById('chat-form');
  const textarea = document.getElementById('chat-text-input');

  if (form && textarea) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = textarea.value.trim();
      if (!text) return;

      if (!state.caseId) {
        showToast("Please start or open a case first.", "warning");
        openModal('modal-new-case');
        return;
      }

      textarea.value = '';
      await sendUserMessage(text);
    });

    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.dispatchEvent(new Event('submit'));
      }
    });
  }
}

async function sendUserMessage(text) {
  addChatMessage('user', text);
  showChatLoading();

  try {
    const res = await window.api.sendMessage(state.caseId, text);
    hideChatLoading();

    let responseMsg = res.message || "Message processed.";
    addChatMessage('agent', responseMsg);

    // If confirmation required, show interactive confirmation card in chat
    if (res.confirmation_required && res.changes && res.changes.length > 0) {
      renderChatConfirmationCard(res.changes);
    } else {
      // If message was conversational or didn't propose changes, check for next question
      await promptNextAgentQuestion();
    }

    // Refresh state in background
    await refreshCaseState();

    // Trigger TTS speech playback if available
    speakResponseText(responseMsg);

  } catch (err) {
    hideChatLoading();
    addChatMessage('agent', `⚠️ Could not process message: ${err.message}`);
    showToast(`Error sending message: ${err.message}`, 'error');
  }
}

function clearChatMessages() {
  const container = document.getElementById('chat-messages');
  if (container) container.innerHTML = '';
}

function addChatMessage(sender, text) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-message ${sender === 'user' ? 'user-msg' : 'agent-msg'}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = sender === 'user' ? (state.mode === 'vle' ? 'OP' : 'ME') : 'YS';

  const content = document.createElement('div');
  content.className = 'msg-content';

  const senderRow = document.createElement('div');
  senderRow.className = 'msg-sender-row';
  senderRow.style.display = 'flex';
  senderRow.style.alignItems = 'center';
  senderRow.style.justifyContent = 'space-between';
  senderRow.style.gap = '8px';

  const senderLabel = document.createElement('div');
  senderLabel.className = 'msg-sender';
  senderLabel.textContent = sender === 'user' ? (state.mode === 'vle' ? 'CSC Operator' : 'Citizen') : 'Saathi AI';
  senderRow.appendChild(senderLabel);

  if (sender === 'agent') {
    const listenBtn = document.createElement('button');
    listenBtn.className = 'btn-msg-listen';
    listenBtn.title = 'Listen to this message';
    listenBtn.innerHTML = '🔊 Listen';
    listenBtn.style.background = 'none';
    listenBtn.style.border = '1px solid rgba(255,255,255,0.15)';
    listenBtn.style.borderRadius = '12px';
    listenBtn.style.fontSize = '0.72rem';
    listenBtn.style.padding = '2px 8px';
    listenBtn.style.color = '#94a3b8';
    listenBtn.style.cursor = 'pointer';
    listenBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      speakResponseText(text);
    });
    senderRow.appendChild(listenBtn);
  }

  const msgText = document.createElement('div');
  msgText.className = 'msg-text';
  msgText.textContent = text;

  content.appendChild(senderRow);
  content.appendChild(msgText);
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(content);

  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}

function showChatLoading() {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const loading = document.createElement('div');
  loading.id = 'chat-loading-indicator';
  loading.className = 'chat-message agent-msg loading';
  loading.innerHTML = `
    <div class="msg-avatar">YS</div>
    <div class="msg-content">
      <div class="loading-dots">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  container.appendChild(loading);
  container.scrollTop = container.scrollHeight;
}

function hideChatLoading() {
  const el = document.getElementById('chat-loading-indicator');
  if (el) el.remove();
}

function renderChatConfirmationCard(changes) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const card = document.createElement('div');
  card.className = 'chat-inline-confirm-card';
  
  let changesHtml = changes.map(c => {
    const fieldName = c.field || '';
    const prevVal = c.previous !== undefined && c.previous !== null ? c.previous : (c.old_value !== undefined && c.old_value !== null ? c.old_value : 'UNKNOWN');
    const newVal = c.proposed !== undefined && c.proposed !== null ? c.proposed : (c.new_value !== undefined && c.new_value !== null ? c.new_value : '');
    return `
      <div class="change-diff-row">
        <strong class="field-name">${escapeHtml(fieldName)}:</strong>
        <span class="old-val">${escapeHtml(String(prevVal))}</span>
        <span class="arrow">➔</span>
        <span class="new-val">${escapeHtml(String(newVal))}</span>
      </div>
    `;
  }).join('');

  card.innerHTML = `
    <div class="confirm-card-header">
      <span class="badge badge-warning">Needs Your Confirmation</span>
      <h4>Confirm Proposed Facts</h4>
    </div>
    <div class="confirm-card-body">
      ${changesHtml}
    </div>
    <div class="confirm-card-actions">
      <button class="btn btn-success btn-sm btn-chat-confirm">✓ Confirm Facts</button>
      <button class="btn btn-danger btn-sm btn-chat-reject">✗ Reject</button>
    </div>
  `;

  card.querySelector('.btn-chat-confirm').addEventListener('click', async () => {
    try {
      const res = await window.api.confirmProfile(state.caseId);
      card.innerHTML = `<div class="badge badge-success">✓ Profile Facts Confirmed</div>`;
      showToast("Profile facts confirmed! Eligibility recalculated.", "success");

      let nextMsg = res.agent_message;
      if (!nextMsg) {
        nextMsg = "Your facts are confirmed! Checking what else is needed...";
      }
      addChatMessage('agent', nextMsg);
      speakResponseText(nextMsg);

      await refreshCaseState();

      // Trigger the proactive agent question loop
      await promptNextAgentQuestion();
    } catch (err) {
      showToast(`Confirmation failed: ${err.message}`, "error");
    }
  });

  card.querySelector('.btn-chat-reject').addEventListener('click', async () => {
    try {
      const res = await window.api.rejectProfile(state.caseId);
      card.innerHTML = `<div class="badge badge-danger">✗ Proposed Facts Rejected</div>`;
      showToast("Proposed facts rejected. Profile unchanged.", "info");

      const rejectMsg = res.message || "Understood. The proposed facts were rejected and your confirmed profile was not changed. Please tell me your correct details whenever you are ready.";
      addChatMessage('agent', rejectMsg);
      speakResponseText(rejectMsg);

      await refreshCaseState();
    } catch (err) {
      showToast(`Rejection failed: ${err.message}`, "error");
    }
  });

  container.appendChild(card);
  container.scrollTop = container.scrollHeight;
}

/**
 * Proactively checks for missing profile information required by selected schemes or general eligibility,
 * and renders a conversational question card with 1-click quick-reply options.
 */
async function promptNextAgentQuestion() {
  if (!state.caseId) return;
  try {
    const qData = await window.api.getNextAgentQuestion(state.caseId);
    if (!qData || !qData.has_question) {
      if (qData && qData.message) {
        addChatMessage('agent', `🎉 ${qData.message}`);
      }
      return;
    }
    renderAgentQuestionCard(qData);
  } catch (err) {
    console.debug("Note: Could not fetch next agent question:", err);
  }
}

function renderAgentQuestionCard(qData) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const card = document.createElement('div');
  card.className = 'agent-question-card';

  const contextBadge = qData.scheme_context 
    ? `<span class="agent-question-context">🎯 ${escapeHtml(qData.scheme_context)}</span>`
    : '';

  let repliesHtml = '';
  if (qData.quick_replies && qData.quick_replies.length > 0) {
    repliesHtml = `
      <div class="agent-quick-replies">
        ${qData.quick_replies.map(r => `
          <button class="btn-quick-reply" data-reply-text="${escapeHtml(r.text)}">
            ${escapeHtml(r.label)}
          </button>
        `).join('')}
      </div>
    `;
  }

  card.innerHTML = `
    <div class="agent-question-header" style="display:flex; justify-content:space-between; align-items:center;">
      <div style="display:flex; align-items:center; gap:8px;">
        <span class="badge badge-info">Saathi Question</span>
        ${contextBadge}
      </div>
      <button class="btn-question-listen" title="Listen to question" style="background:none; border:1px solid rgba(255,255,255,0.2); border-radius:12px; font-size:0.75rem; padding:2px 10px; color:#38bdf8; cursor:pointer;">
        🔊 Listen
      </button>
    </div>
    <div class="agent-question-text">${escapeHtml(qData.question)}</div>
    ${repliesHtml}
  `;

  // Attach listen button handler
  const listenBtn = card.querySelector('.btn-question-listen');
  if (listenBtn) {
    listenBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      speakResponseText(qData.question);
    });
  }

  // Attach 1-click quick response handlers
  card.querySelectorAll('.btn-quick-reply').forEach(btn => {
    btn.addEventListener('click', async () => {
      const text = btn.getAttribute('data-reply-text');
      // Visual feedback: disable options
      card.querySelectorAll('.btn-quick-reply').forEach(b => {
        b.disabled = true;
        b.style.opacity = '0.5';
      });
      btn.style.opacity = '1';
      btn.style.borderColor = '#10b981';

      // Send the user response through the agent workflow
      await sendUserMessage(text);
    });
  });

  container.appendChild(card);
  container.scrollTop = container.scrollHeight;

  // Speak the question aloud for accessibility
  speakResponseText(qData.question);
}

// =========================================================================
// 9. PHASE 8 MULTILINGUAL VOICE INTEGRATION & BROWSER TTS
// =========================================================================
function bindVoiceControls() {
  const micBtn = document.getElementById('btn-voice-mic');
  const transcriptBar = document.getElementById('transcript-bar');
  const transcriptInput = document.getElementById('transcript-edit-input');
  const sendTranscriptBtn = document.getElementById('btn-send-transcript');
  const discardTranscriptBtn = document.getElementById('btn-discard-transcript');
  const replayTtsBtn = document.getElementById('btn-replay-tts');
  const muteTtsBtn = document.getElementById('btn-mute-tts');

  if (micBtn) {
    micBtn.addEventListener('click', async () => {
      if (!state.caseId) {
        showToast("Please start or open a case before using voice.", "warning");
        openModal('modal-new-case');
        return;
      }

      if (state.isRecording) {
        stopVoiceRecording();
      } else {
        await startVoiceRecording();
      }
    });
  }

  if (sendTranscriptBtn && transcriptInput) {
    sendTranscriptBtn.addEventListener('click', async () => {
      const text = transcriptInput.value.trim();
      if (!text) return;
      transcriptBar.style.display = 'none';
      await sendUserMessage(text);
    });
  }

  if (discardTranscriptBtn) {
    discardTranscriptBtn.addEventListener('click', () => {
      if (transcriptBar) transcriptBar.style.display = 'none';
      state.currentAudioBlob = null;
      updateVoiceStateLabel('Click mic to speak');
    });
  }

  if (replayTtsBtn) {
    replayTtsBtn.addEventListener('click', () => {
      if (state.lastSpokenText) speakResponseText(state.lastSpokenText);
    });
  }

  if (muteTtsBtn) {
    muteTtsBtn.addEventListener('click', () => {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      muteTtsBtn.style.display = 'none';
    });
  }
}

async function startVoiceRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.audioChunks = [];
    state.audioRecorder = new MediaRecorder(stream);

    state.audioRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) state.audioChunks.push(event.data);
    };

    state.audioRecorder.onstop = async () => {
      const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
      state.currentAudioBlob = audioBlob;
      stream.getTracks().forEach(t => t.stop());
      await processVoiceUpload(audioBlob);
    };

    state.audioRecorder.start(250);
    state.isRecording = true;
    state.recordingStartTime = Date.now();

    const micBtn = document.getElementById('btn-voice-mic');
    if (micBtn) micBtn.classList.add('recording');
    updateVoiceStateLabel('Recording... Speak now');

    const timer = document.getElementById('voice-timer');
    if (timer) {
      timer.style.display = 'inline-block';
      state.recordingTimerId = setInterval(() => {
        const sec = Math.floor((Date.now() - state.recordingStartTime) / 1000);
        const mm = String(Math.floor(sec / 60)).padStart(2, '0');
        const ss = String(sec % 60).padStart(2, '0');
        timer.textContent = `${mm}:${ss}`;
      }, 500);
    }

  } catch (err) {
    console.error("Microphone access failed:", err);
    showToast("Microphone access was denied or is unavailable. Please use the text input below.", "warning");
    updateVoiceStateLabel('Voice unavailable — use text');
  }
}

function stopVoiceRecording() {
  if (state.audioRecorder && state.isRecording) {
    state.audioRecorder.stop();
    state.isRecording = false;

    const micBtn = document.getElementById('btn-voice-mic');
    if (micBtn) micBtn.classList.remove('recording');

    clearInterval(state.recordingTimerId);
    const timer = document.getElementById('voice-timer');
    if (timer) timer.style.display = 'none';

    updateVoiceStateLabel('Transcribing audio...');
  }
}

async function processVoiceUpload(audioBlob) {
  try {
    showChatLoading();
    const res = await window.api.uploadVoice(state.caseId, audioBlob, state.language);
    hideChatLoading();

    // Show transcript preview bar so user can review or edit
    const transcriptBar = document.getElementById('transcript-bar');
    const transcriptInput = document.getElementById('transcript-edit-input');
    if (transcriptBar && transcriptInput) {
      transcriptBar.style.display = 'flex';
      transcriptInput.value = res.transcript || '';
    }

    addChatMessage('user', `🎙️ "${res.transcript}"`);

    const agentReply = res.response_text || (res.voice_response ? res.voice_response.speakable_text : (res.message || "Voice turn processed."));
    addChatMessage('agent', agentReply);

    // If confirmation required, show interactive confirmation card in chat
    if (res.confirmation_required && res.changes && res.changes.length > 0) {
      renderChatConfirmationCard(res.changes);
    } else {
      // If voice message was conversational or didn't propose changes, check for next question
      await promptNextAgentQuestion();
    }

    updateVoiceStateLabel('Click mic to speak');
    await refreshCaseState();

    // Browser SpeechSynthesis playback
    speakResponseText(agentReply);

  } catch (err) {
    hideChatLoading();
    updateVoiceStateLabel('Click mic to speak');
    showToast(`Voice transcription failed: ${err.message}. You can continue by typing.`, "warning");
    addChatMessage('agent', "⚠️ Voice transcription encountered an issue. You can continue typing seamlessly.");
  }
}

function updateVoiceStateLabel(text) {
  const label = document.getElementById('voice-state-label');
  if (label) label.textContent = text;
}

function speakResponseText(text) {
  if (!('speechSynthesis' in window)) return;
  state.lastSpokenText = text;

  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Select voice matching language
    const voices = window.speechSynthesis.getVoices();
    const langCode = state.language === 'hi' ? 'hi-IN' : (state.language === 'te' ? 'te-IN' : 'en-IN');
    const matchingVoice = voices.find(v => v.lang === langCode || v.lang.startsWith(state.language));
    if (matchingVoice) utterance.voice = matchingVoice;
    utterance.lang = langCode;
    utterance.rate = 1.0;

    const replayBtn = document.getElementById('btn-replay-tts');
    const muteBtn = document.getElementById('btn-mute-tts');

    utterance.onstart = () => {
      if (muteBtn) muteBtn.style.display = 'inline-block';
      if (replayBtn) replayBtn.style.display = 'inline-block';
    };

    utterance.onend = () => {
      if (muteBtn) muteBtn.style.display = 'none';
    };

    utterance.onerror = () => {
      if (muteBtn) muteBtn.style.display = 'none';
    };

    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn("SpeechSynthesis error:", e);
  }
}

// =========================================================================
// 10. CITIZEN PROFILE & MANUAL EDIT
// =========================================================================
function bindProfileActions() {
  const btnManualEdit = document.getElementById('btn-open-manual-edit');
  if (btnManualEdit) btnManualEdit.addEventListener('click', openManualEditModal);

  const btnConfirm = document.getElementById('btn-confirm-profile');
  if (btnConfirm) {
    btnConfirm.addEventListener('click', async () => {
      try {
        const res = await window.api.confirmProfile(state.caseId);
        showToast("Profile changes confirmed. Evaluations updated.", "success");
        let nextMsg = res.agent_message || "Profile changes confirmed! Navigate to 'Scheme Discovery' to re-evaluate eligible programs.";
        addChatMessage('agent', nextMsg);
        await refreshCaseState();
      } catch (err) {
        showToast(`Confirmation failed: ${err.message}`, "error");
      }
    });
  }

  const btnReject = document.getElementById('btn-reject-profile');
  if (btnReject) {
    btnReject.addEventListener('click', async () => {
      try {
        const res = await window.api.rejectProfile(state.caseId);
        showToast("Proposed changes rejected. Confirmed profile remains unchanged.", "info");
        let rejectMsg = res.message || "Proposed changes rejected. Confirmed profile unchanged.";
        addChatMessage('agent', rejectMsg);
        await refreshCaseState();
      } catch (err) {
        showToast(`Rejection failed: ${err.message}`, "error");
      }
    });
  }

  const nlForm = document.getElementById('nl-correction-form');
  const nlInput = document.getElementById('nl-correction-input');
  if (nlForm && nlInput) {
    nlForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = nlInput.value.trim();
      if (!text) return;
      if (!state.caseId) {
        showToast("Please create or open a case first.", "warning");
        return;
      }
      nlInput.value = '';
      await sendUserMessage(text);
      switchView('chat');
    });
  }

  const submitManualEditBtn = document.getElementById('btn-submit-manual-edit');
  if (submitManualEditBtn) {
    submitManualEditBtn.addEventListener('click', async () => {
      const fieldSelect = document.getElementById('edit-field-select');
      const valInput = document.getElementById('edit-field-val');
      const autoConfirmCheck = document.getElementById('edit-auto-confirm');

      if (!fieldSelect || !valInput) return;
      const field = fieldSelect.value;
      let rawVal = valInput.value.trim();

      // Convert boolean/number types if appropriate
      let parsedVal = rawVal;
      if (rawVal.toLowerCase() === 'true') parsedVal = true;
      else if (rawVal.toLowerCase() === 'false') parsedVal = false;
      else if (!isNaN(Number(rawVal)) && rawVal !== '') parsedVal = Number(rawVal);

      try {
        await window.api.editProfile(state.caseId, field, parsedVal, autoConfirmCheck.checked);
        closeModal('modal-manual-edit-profile');
        showToast(`Profile field '${field}' updated successfully`, 'success');
        await refreshCaseState();
      } catch (err) {
        showToast(`Manual edit failed: ${err.message}`, 'error');
      }
    });
  }
}

function renderProfileView() {
  const tbody = document.getElementById('confirmed-facts-tbody');
  const confirmedCountBadge = document.getElementById('confirmed-count-badge');
  const unknownChips = document.getElementById('unknown-fields-chips');
  const unknownCountBadge = document.getElementById('unknown-count-badge');

  if (!tbody || !state.profile) return;

  const confirmed = state.profile.confirmed_profile || {};
  const confirmedKeys = Object.keys(confirmed).filter(k => confirmed[k] !== null && confirmed[k] !== undefined);

  // 1. Confirmed Facts Table
  if (confirmedKeys.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty-cell">No confirmed profile facts yet. Chat with Saathi or use manual edit.</td></tr>`;
    if (confirmedCountBadge) confirmedCountBadge.textContent = '0 Confirmed';
  } else {
    if (confirmedCountBadge) confirmedCountBadge.textContent = `${confirmedKeys.length} Confirmed`;
    tbody.innerHTML = confirmedKeys.map(key => {
      const val = confirmed[key];
      const displayVal = typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val);
      return `
        <tr>
          <td><strong>${escapeHtml(key)}</strong></td>
          <td><span class="fact-value">${escapeHtml(displayVal)}</span></td>
          <td><span class="badge badge-success">CONFIRMED</span></td>
          <td>
            <button class="btn btn-ghost btn-sm edit-field-trigger" data-field="${escapeHtml(key)}" data-val="${escapeHtml(String(val))}">
              ✏️ Edit
            </button>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.edit-field-trigger').forEach(btn => {
      btn.addEventListener('click', () => {
        const f = btn.getAttribute('data-field');
        const v = btn.getAttribute('data-val');
        openManualEditModalWithField(f, v);
      });
    });
  }

  // 2. Unknown Parameters Chips (Mandatory: NEVER represent unknown as 0, false, empty, or "no")
  if (unknownChips) {
    const allKnownFields = [
      "age", "gender", "state", "annual_income", "caste_category",
      "farmer_status", "land_holding_acres", "is_landowner", "land_record_status",
      "disability_status", "disability_percentage", "aadhaar_linked",
      "bank_account_linked", "npci_mapping_status", "occupation",
      "marital_status", "ration_card_type", "has_pukka_house",
      "pregnancy_status", "enrolled_student", "educational_level"
    ];

    const unknownList = allKnownFields.filter(f => !confirmedKeys.includes(f));
    if (unknownCountBadge) unknownCountBadge.textContent = `${unknownList.length} Unknown`;

    unknownChips.innerHTML = unknownList.map(f => `
      <div class="unknown-chip" role="button" tabindex="0" title="Click to provide value">
        <span class="chip-name">${escapeHtml(f)}:</span>
        <span class="chip-val">UNKNOWN (Not Provided)</span>
      </div>
    `).join('');

    unknownChips.querySelectorAll('.unknown-chip').forEach((chip, i) => {
      chip.addEventListener('click', () => openManualEditModalWithField(unknownList[i], ''));
    });
  }

  updatePendingConfirmationBanner();
}

function updatePendingConfirmationBanner() {
  const banner = document.getElementById('profile-pending-banner');
  const list = document.getElementById('pending-changes-list');
  if (!banner || !list) return;

  const pending = state.profile ? state.profile.pending_confirmation : null;
  if (pending && pending.changes && pending.changes.length > 0) {
    banner.style.display = 'block';
    list.innerHTML = pending.changes.map(c => `
      <div class="pending-change-item">
        <div class="change-field">${escapeHtml(c.field)}</div>
        <div class="change-diff">
          <span class="old-diff">${escapeHtml(String(c.old_value !== null ? c.old_value : 'UNKNOWN'))}</span>
          <span class="arrow-diff">➔</span>
          <span class="new-diff">${escapeHtml(String(c.new_value))}</span>
        </div>
      </div>
    `).join('');
  } else {
    banner.style.display = 'none';
  }
}

let cachedProfileFields = [];

async function openManualEditModal() {
  await populateFieldsSelect();
  updateManualEditInputForCurrentField();
  openModal('modal-manual-edit-profile');
}

async function openManualEditModalWithField(field, value) {
  await populateFieldsSelect();
  const select = document.getElementById('edit-field-select');
  if (select) select.value = field;
  updateManualEditInputForCurrentField(value);
  openModal('modal-manual-edit-profile');
}

function updateManualEditInputForCurrentField(presetValue = null) {
  const select = document.getElementById('edit-field-select');
  const questionEl = document.getElementById('edit-field-question');
  const container = document.getElementById('edit-val-container');
  if (!select || !container) return;

  const currentFieldName = select.value;
  const meta = cachedProfileFields.find(f => f.name === currentFieldName);

  if (questionEl) {
    if (meta && meta.question) {
      questionEl.textContent = `💡 Question: "${meta.question}"`;
      questionEl.style.display = 'block';
    } else {
      questionEl.style.display = 'none';
    }
  }

  // Determine kind: boolean or string/number
  const isBool = meta && meta.kind === 'boolean';
  let currentVal = presetValue;
  if (currentVal === null) {
    const existingInput = document.getElementById('edit-field-val');
    currentVal = existingInput ? existingInput.value : '';
  }

  if (isBool) {
    const isTrue = currentVal === true || String(currentVal).toLowerCase() === 'true' || currentVal === 'Yes';
    container.innerHTML = `
      <select id="edit-field-val" class="form-select">
        <option value="true" ${isTrue ? 'selected' : ''}>Yes</option>
        <option value="false" ${!isTrue ? 'selected' : ''}>No</option>
      </select>
    `;
  } else {
    container.innerHTML = `
      <input type="text" id="edit-field-val" class="form-input" placeholder="Enter value" value="${escapeHtml(String(currentVal || ''))}">
    `;
  }
}

async function populateFieldsSelect() {
  const select = document.getElementById('edit-field-select');
  if (!select) return;
  if (select.children.length > 0 && cachedProfileFields.length > 0) return;

  try {
    const res = await window.api.getProfileFields();
    cachedProfileFields = res.fields || [];
    select.innerHTML = cachedProfileFields.map(f => `
      <option value="${escapeHtml(f.name)}">${escapeHtml(f.label || f.name)}</option>
    `).join('');

    select.addEventListener('change', () => {
      updateManualEditInputForCurrentField();
    });
  } catch (e) {
    console.warn("Could not load fields metadata, using fallback:", e);
  }
}

// =========================================================================
// 11. SCHEME DISCOVERY & MULTI-SCHEME SELECTION (NON-RANKED)
// =========================================================================
let allSchemesCatalog = [];

async function loadSchemesCatalog() {
  try {
    const res = await window.api.getSchemesCatalog();
    allSchemesCatalog = res.schemes || [];
  } catch (err) {
    console.warn("Schemes catalog load error:", err);
  }
}

function bindSchemeActions() {
  const btnEval = document.getElementById('btn-evaluate-schemes');
  if (btnEval) {
    btnEval.addEventListener('click', async () => {
      if (!state.caseId) {
        showToast("Please create or open a case first.", "warning");
        openModal('modal-new-case');
        return;
      }
      try {
        btnEval.disabled = true;
        btnEval.textContent = "Evaluating...";
        const res = await window.api.evaluateSchemes(state.caseId);
        state.evaluations = res.schemes || [];
        showToast(`Evaluated ${res.total_evaluated} schemes deterministically`, 'success');
        await refreshCaseState();
        renderSchemesView();
      } catch (err) {
        showToast(`Scheme evaluation failed: ${err.message}`, 'error');
      } finally {
        btnEval.disabled = false;
        btnEval.textContent = "⚡ Evaluate All Schemes";
      }
    });
  }

  const btnCreateApps = document.getElementById('btn-create-selected-apps');
  if (btnCreateApps) {
    btnCreateApps.addEventListener('click', async () => {
      const selected = Array.from(state.selectedSchemeIds);
      if (selected.length === 0) {
        showToast("Select at least one scheme first.", "warning");
        return;
      }
      try {
        btnCreateApps.disabled = true;
        btnCreateApps.textContent = "Creating Tracks...";
        const res = await window.api.selectSchemes(state.caseId, selected);
        showToast(`Created ${res.total_selected} independent application tracks!`, 'success');
        state.selectedSchemeIds.clear();
        await refreshCaseState();

        // Check if there are missing information needed for these newly selected schemes
        if (state.caseData && state.caseData.missing_information && state.caseData.missing_information.length > 0) {
          switchView('chat');
          addChatMessage('agent', `I've opened application tracks for your chosen schemes! Before we proceed to document upload, let's complete a few missing requirements:`);
          await promptNextAgentQuestion();
        } else {
          switchView('applications');
        }
      } catch (err) {
        showToast(`Could not create applications: ${err.message}`, 'error');
      } finally {
        btnCreateApps.disabled = false;
        btnCreateApps.innerHTML = `Create Applications (<span id="selected-schemes-count">0</span>)`;
      }
    });
  }
}

function renderSchemesView() {
  const container = document.getElementById('schemes-cards-container');
  if (!container) return;

  // Use evaluations if available, otherwise display schemes from catalog
  const schemesList = state.evaluations.length > 0 ? state.evaluations : allSchemesCatalog;

  if (schemesList.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📋</div>
        <h3>No schemes loaded</h3>
        <p>Click "Evaluate All Schemes" to evaluate your profile against all 13 supported welfare programs.</p>
      </div>
    `;
    return;
  }

  // Canonical ordering without any ranking, scoring, or "top/best" badges!
  container.innerHTML = schemesList.map(item => {
    const schemeId = item.scheme_id;
    const catItem = allSchemesCatalog.find(c => c.scheme_id === schemeId) || item;
    
    // Multilingual scheme title
    let title = catItem.title_en;
    if (state.language === 'hi' && catItem.title_hi) title = catItem.title_hi;
    else if (state.language === 'te' && catItem.title_te) title = catItem.title_te;

    const outcome = item.outcome || 'INCOMPLETE / UNKNOWN';
    const isSelectable = outcome === 'FULLY_ELIGIBLE' || outcome === 'ACTIONABLE_PREPARATION_REQUIRED';
    const isSelected = state.selectedSchemeIds.has(schemeId);

    // Existing application check
    const existingApp = Object.values(state.applications).find(a => a.scheme_id === schemeId);

    let outcomeBadgeClass = 'badge-neutral';
    if (outcome === 'FULLY_ELIGIBLE') outcomeBadgeClass = 'badge-success';
    else if (outcome === 'ACTIONABLE_PREPARATION_REQUIRED') outcomeBadgeClass = 'badge-warning';
    else if (outcome === 'NOT_ELIGIBLE') outcomeBadgeClass = 'badge-danger';
    else if (outcome === 'INCOMPLETE / UNKNOWN') outcomeBadgeClass = 'badge-info';

    const missing = (item.missing_information || []).map(m => `<span class="missing-tag">${escapeHtml(m)}</span>`).join('');
    const summaryReason = item.summary_reason || (catItem.benefit_summary || '');

    return `
      <div class="scheme-card ${isSelected ? 'selected' : ''}" data-scheme-id="${escapeHtml(schemeId)}">
        <div class="scheme-card-header">
          <div class="scheme-title-wrap">
            <input 
              type="checkbox" 
              class="scheme-select-cb" 
              id="cb-scheme-${escapeHtml(schemeId)}" 
              data-scheme-id="${escapeHtml(schemeId)}" 
              ${isSelected ? 'checked' : ''}
              ${existingApp ? 'disabled' : ''}
            >
            <label for="cb-scheme-${escapeHtml(schemeId)}" class="scheme-title">${escapeHtml(title)}</label>
          </div>
          <span class="badge ${outcomeBadgeClass}">${escapeHtml(outcome)}</span>
        </div>
        <div class="scheme-card-body">
          <div class="scheme-meta-row">
            <span class="meta-dep">${escapeHtml(catItem.department || 'Government Welfare')}</span>
            ${existingApp ? `<span class="badge badge-info">Track #${existingApp.application_id.slice(0, 6)} Active</span>` : ''}
          </div>
          <p class="scheme-desc">${escapeHtml(summaryReason)}</p>
          ${missing ? `<div class="missing-info-row"><strong>Missing Facts:</strong> ${missing}</div>` : ''}
        </div>
        <div class="scheme-card-footer">
          <span class="footer-docs-count">📁 ${catItem.required_documents ? catItem.required_documents.length : '—'} Required Documents</span>
          ${isSelectable && !existingApp ? `
            <button class="btn btn-secondary btn-sm btn-quick-select" data-scheme-id="${escapeHtml(schemeId)}">
              ${isSelected ? 'Deselect' : 'Select Scheme'}
            </button>
          ` : (existingApp ? `
            <button class="btn btn-ghost btn-sm btn-go-app" data-app-id="${escapeHtml(existingApp.application_id)}">
              View Application ➔
            </button>
          ` : `<span class="not-selectable-hint">Ineligible / Missing Critical Facts</span>`)}
        </div>
      </div>
    `;
  }).join('');

  // Bind checkbox and card interactions
  container.querySelectorAll('.scheme-select-cb').forEach(cb => {
    cb.addEventListener('change', (e) => {
      const sid = e.target.getAttribute('data-scheme-id');
      if (e.target.checked) state.selectedSchemeIds.add(sid);
      else state.selectedSchemeIds.delete(sid);
      updateSelectedSchemesCounter();
    });
  });

  container.querySelectorAll('.btn-quick-select').forEach(btn => {
    btn.addEventListener('click', () => {
      const sid = btn.getAttribute('data-scheme-id');
      if (state.selectedSchemeIds.has(sid)) state.selectedSchemeIds.delete(sid);
      else state.selectedSchemeIds.add(sid);
      updateSelectedSchemesCounter();
      renderSchemesView();
    });
  });

  container.querySelectorAll('.btn-go-app').forEach(btn => {
    btn.addEventListener('click', () => {
      const aid = btn.getAttribute('data-app-id');
      state.activeApplicationId = aid;
      switchView('applications');
    });
  });

  updateSelectedSchemesCounter();
}

function updateSelectedSchemesCounter() {
  const countEl = document.getElementById('selected-schemes-count');
  const btnCreate = document.getElementById('btn-create-selected-apps');
  const count = state.selectedSchemeIds.size;
  if (countEl) countEl.textContent = count;
  if (btnCreate) btnCreate.disabled = count === 0;
}

// =========================================================================
// 12. INDEPENDENT APPLICATION TRACKS
// =========================================================================
function bindApplicationActions() {
  const btnAddMore = document.getElementById('btn-switch-scheme-eval');
  if (btnAddMore) btnAddMore.addEventListener('click', () => switchView('schemes'));
}

function renderApplicationsView() {
  const sidebar = document.getElementById('apps-list-sidebar');
  const detailContainer = document.getElementById('app-detail-container');
  if (!sidebar || !detailContainer) return;

  const appIds = Object.keys(state.applications);
  if (appIds.length === 0) {
    sidebar.innerHTML = `<div class="empty-sidebar">No active applications. Select schemes to begin tracks.</div>`;
    detailContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📑</div>
        <h3>No application tracks created yet</h3>
        <p>Navigate to "Scheme Discovery", evaluate your profile, and select one or more schemes to track applications independently.</p>
        <button class="btn btn-primary" onclick="switchView('schemes')">Go to Scheme Discovery</button>
      </div>
    `;
    return;
  }

  // Sidebar List
  sidebar.innerHTML = appIds.map(aid => {
    const app = state.applications[aid];
    const isCurrent = aid === state.activeApplicationId;
    return `
      <div class="app-sidebar-item ${isCurrent ? 'active' : ''}" data-app-id="${escapeHtml(aid)}" role="button" tabindex="0">
        <div class="app-item-title">${escapeHtml(app.scheme_name || app.scheme_id)}</div>
        <div class="app-item-status badge badge-sm ${getLifecycleBadgeClass(app.status)}">${escapeHtml(app.status)}</div>
      </div>
    `;
  }).join('');

  sidebar.querySelectorAll('.app-sidebar-item').forEach(item => {
    item.addEventListener('click', () => {
      state.activeApplicationId = item.getAttribute('data-app-id');
      renderApplicationsView();
    });
  });

  // Current Application Detail
  const activeApp = state.applications[state.activeApplicationId] || state.applications[appIds[0]];
  if (!activeApp) return;

  detailContainer.innerHTML = `
    <div class="card app-card-detail">
      <div class="card-header">
        <div>
          <span class="badge badge-info">APPLICATION #${escapeHtml(activeApp.application_id.slice(0, 8))}</span>
          <h3 class="card-header-title" style="margin-top: 0.5rem;">${escapeHtml(activeApp.scheme_name || activeApp.scheme_id)}</h3>
        </div>
        <div class="status-wrap">
          <span class="badge ${getLifecycleBadgeClass(activeApp.status)}">${escapeHtml(activeApp.status)}</span>
        </div>
      </div>
      <div class="card-body">
        <div class="app-stats-row">
          <div class="stat-box">
            <span class="stat-lbl">Eligibility Status</span>
            <span class="stat-val ${activeApp.eligible ? 'green' : 'yellow'}">${activeApp.eligible ? 'ELIGIBLE' : 'ACTION REQUIRED'}</span>
          </div>
          <div class="stat-box">
            <span class="stat-lbl">Readiness State</span>
            <span class="stat-val">${escapeHtml(activeApp.readiness_status || 'NOT_READY')}</span>
          </div>
          <div class="stat-box">
            <span class="stat-lbl">Documents Uploaded</span>
            <span class="stat-val">${activeApp.documents_count || 0}</span>
          </div>
          <div class="stat-box">
            <span class="stat-lbl">Last Modified</span>
            <span class="stat-val">${activeApp.updated_at ? new Date(activeApp.updated_at).toLocaleDateString() : 'Today'}</span>
          </div>
        </div>

        <div class="app-actions-panel">
          <h4>Next Step Workspaces for this Scheme:</h4>
          <div class="app-btn-flow">
            <button class="btn btn-secondary btn-sm" onclick="goToAppDocuments('${activeApp.application_id}')">📁 Manage Documents</button>
            <button class="btn btn-secondary btn-sm" onclick="goToAppReadiness('${activeApp.application_id}')">⚖️ Check Readiness</button>
            <button class="btn btn-primary btn-sm" onclick="goToAppHandoff('${activeApp.application_id}')">🤝 Pre-Submission Handoff</button>
            <button class="btn btn-danger btn-sm" onclick="goToAppRecovery('${activeApp.application_id}')">🚨 Report Rejection</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function getLifecycleBadgeClass(status) {
  if (status === 'READY_FOR_HANDOFF' || status === 'COMPLETED' || status === 'RECOVERED') return 'badge-success';
  if (status === 'REJECTED') return 'badge-danger';
  if (status === 'RECOVERY_IN_PROGRESS' || status === 'ACTION_REQUIRED') return 'badge-warning';
  return 'badge-info';
}

function goToAppDocuments(aid) { state.activeApplicationId = aid; switchView('documents'); }
function goToAppReadiness(aid) { state.activeApplicationId = aid; switchView('readiness'); }
function goToAppHandoff(aid) { state.activeApplicationId = aid; switchView('handoff'); }
function goToAppRecovery(aid) { state.activeApplicationId = aid; switchView('recovery'); }

function populateApplicationSelectors() {
  const selectors = [
    document.getElementById('docs-app-selector'),
    document.getElementById('readiness-app-selector'),
    document.getElementById('handoff-app-selector'),
    document.getElementById('recovery-app-selector'),
  ];

  const appIds = Object.keys(state.applications);
  selectors.forEach(sel => {
    if (!sel) return;
    const currentVal = sel.value;
    if (appIds.length === 0) {
      sel.innerHTML = `<option value="">No Active Applications</option>`;
      return;
    }

    sel.innerHTML = appIds.map(aid => {
      const app = state.applications[aid];
      const isSelected = (currentVal === aid) || (aid === state.activeApplicationId);
      return `<option value="${escapeHtml(aid)}" ${isSelected ? 'selected' : ''}>
        ${escapeHtml(app.scheme_name || app.scheme_id)} (#${escapeHtml(aid.slice(0, 6))})
      </option>`;
    }).join('');

    sel.addEventListener('change', (e) => {
      state.activeApplicationId = e.target.value;
      if (state.activeView === 'documents') renderDocumentsView();
      else if (state.activeView === 'readiness') renderReadinessView();
      else if (state.activeView === 'handoff') renderHandoffView();
      else if (state.activeView === 'recovery') renderRecoveryView();
    });
  });
}

// =========================================================================
// 13. DOCUMENTS & REAL OCR PROCESSING
// =========================================================================
function bindDocumentActions() {
  const btnUploadModal = document.getElementById('btn-upload-doc-modal');
  if (btnUploadModal) btnUploadModal.addEventListener('click', () => {
    if (!state.activeApplicationId) {
      showToast("Please select an application first.", "warning");
      return;
    }
    openModal('modal-upload-doc');
  });

  const btnSubmitDoc = document.getElementById('btn-submit-upload-doc');
  if (btnSubmitDoc) {
    btnSubmitDoc.addEventListener('click', async () => {
      const fileInput = document.getElementById('upload-doc-file');
      const typeSelect = document.getElementById('upload-doc-type');

      if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast("Please select a file to upload.", "warning");
        return;
      }

      const file = fileInput.files[0];
      const docType = typeSelect ? typeSelect.value : 'identity_proof';

      try {
        btnSubmitDoc.disabled = true;
        btnSubmitDoc.textContent = "Processing OCR...";
        const res = await window.api.uploadDocument(state.caseId, state.activeApplicationId, file, docType);
        closeModal('modal-upload-doc');
        showToast(`Document '${file.name}' uploaded and processed with OCR!`, 'success');
        fileInput.value = '';
        await refreshCaseState();
        renderDocumentsView();
      } catch (err) {
        showToast(`Upload failed: ${err.message}`, 'error');
      } finally {
        btnSubmitDoc.disabled = false;
        btnSubmitDoc.textContent = "Upload & Extract";
      }
    });
  }
}

async function renderDocumentsView() {
  const checklistContainer = document.getElementById('req-docs-checklist');
  const uploadedContainer = document.getElementById('uploaded-docs-container');
  const reqCount = document.getElementById('docs-req-count');
  const upCount = document.getElementById('docs-uploaded-count');
  const alertBanner = document.getElementById('doc-discrepancy-alert');

  if (!state.activeApplicationId) {
    if (checklistContainer) checklistContainer.innerHTML = `<div class="empty-notice">Please select an application from the dropdown above.</div>`;
    return;
  }

  try {
    const required = docsData.checklist || docsData.required_documents || [];
    const uploaded = docsData.uploaded_documents || [];

    if (reqCount) reqCount.textContent = `${required.length} Required`;
    if (upCount) upCount.textContent = `${uploaded.length} Uploaded`;

    // 1. Required Documents Checklist
    if (checklistContainer) {
      if (required.length === 0) {
        checklistContainer.innerHTML = `<div class="empty-notice">No specific document requirements configured.</div>`;
      } else {
        checklistContainer.innerHTML = required.map(r => {
          const docName = r.name || r.name_en || r.document_type || 'Document';
          const isMandatory = r.required !== undefined ? r.required : (r.is_mandatory !== undefined ? r.is_mandatory : true);
          const isUploaded = r.status === 'VERIFIED' || r.status === 'UPLOADED' || uploaded.some(u => u.document_type === r.document_type || u.document_type === r.doc_id || u.document_type === docName);
          return `
            <div class="req-doc-item ${isUploaded ? 'uploaded' : 'missing'}">
              <span class="doc-status-icon">${isUploaded ? '✓' : '⚠️'}</span>
              <div class="doc-info">
                <strong>${escapeHtml(docName)}</strong>
                <span class="doc-sub">${isMandatory ? 'Mandatory Certificate' : 'Optional Certificate'}</span>
              </div>
              <span class="badge ${isUploaded ? 'badge-success' : 'badge-warning'}">
                ${isUploaded ? 'UPLOADED' : 'REQUIRED'}
              </span>
            </div>
          `;
        }).join('');
      }
    }

    // 2. Uploaded Documents & OCR Facts
    let hasDiscrepancy = false;
    if (uploadedContainer) {
      if (uploaded.length === 0) {
        uploadedContainer.innerHTML = `<div class="empty-notice">No documents uploaded for this application yet. Click "Upload Document".</div>`;
      } else {
        uploadedContainer.innerHTML = uploaded.map(doc => {
          const facts = doc.extracted_facts || {};
          const hasFacts = Object.keys(facts).length > 0;
          const factsHtml = hasFacts ? `
            <div class="ocr-facts-box">
              <div class="ocr-facts-title">🔍 Extracted OCR Facts:</div>
              <pre class="ocr-json">${escapeHtml(JSON.stringify(facts, null, 2))}</pre>
            </div>
          ` : `<div class="ocr-facts-box empty">Text processed. No structured facts extracted.</div>`;

          if (doc.verification_status === 'DISCREPANCY') hasDiscrepancy = true;

          return `
            <div class="uploaded-doc-item">
              <div class="doc-top-row">
                <span class="doc-name">📄 ${escapeHtml(doc.filename || doc.document_type)}</span>
                <span class="badge ${doc.verification_status === 'VERIFIED' ? 'badge-success' : (doc.verification_status === 'DISCREPANCY' ? 'badge-warning' : 'badge-neutral')}">
                  ${escapeHtml(doc.verification_status || 'PROCESSED')}
                </span>
              </div>
              ${factsHtml}
            </div>
          `;
        }).join('');
      }
    }

    if (alertBanner) {
      alertBanner.style.display = hasDiscrepancy ? 'flex' : 'none';
    }

  } catch (err) {
    console.error("Error loading documents:", err);
  }
}

// =========================================================================
// 14. READINESS EVALUATION
// =========================================================================
function bindReadinessActions() {
  const btnRecheck = document.getElementById('btn-recheck-readiness');
  if (btnRecheck) {
    btnRecheck.addEventListener('click', async () => {
      if (!state.activeApplicationId) return;
      renderReadinessView();
      showToast("Readiness recalculated", "info");
    });
  }
}

async function renderReadinessView() {
  const pill = document.getElementById('readiness-status-pill');
  const heading = document.getElementById('readiness-summary-heading');
  const desc = document.getElementById('readiness-summary-desc');
  const statProfile = document.getElementById('readiness-profile-stat');
  const statDocs = document.getElementById('readiness-doc-stat');
  const statBlockers = document.getElementById('readiness-blocker-stat');
  const statAction = document.getElementById('readiness-action-stat');
  const blockersList = document.getElementById('readiness-blockers-list');
  const warningsList = document.getElementById('readiness-warnings-list');

  if (!state.activeApplicationId) {
    if (heading) heading.textContent = "Select an application to evaluate readiness";
    return;
  }

  try {
    const res = await window.api.getReadiness(state.caseId, state.activeApplicationId);
    const overall = res.status || res.overall_status || 'NOT_READY';

    if (pill) {
      pill.textContent = `STATUS: ${overall}`;
      pill.className = `readiness-status-badge ${overall === 'READY_FOR_HANDOFF' ? 'ready' : (overall === 'PARTIALLY_READY' || overall === 'PREPARATION_REQUIRED' ? 'partial' : 'not-ready')}`;
    }

    if (heading) {
      heading.textContent = overall === 'READY_FOR_HANDOFF' 
        ? "Application is Ready for CSC/VLE Handoff"
        : (overall === 'PARTIALLY_READY' || overall === 'PREPARATION_REQUIRED' ? "Actionable Preparation Required" : "Prerequisites Incomplete");
    }

    const verifiedDocs = res.verified_requirements !== undefined ? res.verified_requirements : (res.verified_documents_count || 0);
    const totalDocs = res.total_requirements !== undefined ? res.total_requirements : (res.required_documents_count || 0);
    const blockers = res.missing_documents || res.blocking_reasons || [];
    const warnings = res.unresolved_items || res.non_blocking_warnings || [];

    if (desc) desc.textContent = res.summary_explanation || (overall === 'READY_FOR_HANDOFF' ? 'All mandatory prerequisites verified.' : 'Mandatory certificates or eligibility criteria remain pending.');
    if (statProfile) statProfile.textContent = res.profile_readiness || (overall === 'READY_FOR_HANDOFF' ? 'Complete' : 'Pending Verification');
    if (statDocs) statDocs.textContent = `${verifiedDocs} / ${totalDocs} Verified`;
    if (statBlockers) statBlockers.textContent = `${blockers.length} Blockers`;
    if (statAction) statAction.textContent = res.next_recommended_action || (blockers.length > 0 ? `Upload ${blockers[0]}` : "Proceed to CSC Handoff");

    // Blockers
    if (blockersList) {
      if (blockers.length === 0) {
        blockersList.innerHTML = `<li class="empty-li">✓ No critical submission blockers found.</li>`;
      } else {
        blockersList.innerHTML = blockers.map(b => `<li>🛑 <strong>${escapeHtml(String(b))}</strong></li>`).join('');
      }
    }

    // Warnings
    if (warningsList) {
      if (warnings.length === 0) {
        warningsList.innerHTML = `<li class="empty-li">✓ No warnings recorded.</li>`;
      } else {
        warningsList.innerHTML = warnings.map(w => `<li>⚠️ ${escapeHtml(String(w))}</li>`).join('');
      }
    }

  } catch (err) {
    console.error("Readiness check error:", err);
  }
}

// =========================================================================
// 15. PRE-SUBMISSION & CSC/VLE HANDOFF (PHASE 6)
// =========================================================================
function bindHandoffActions() {
  const btnRef = document.getElementById('btn-gen-ref-sheet');
  const btnDossier = document.getElementById('btn-gen-dossier');
  const btnPkg = document.getElementById('btn-gen-package');
  const btnClose = document.getElementById('btn-close-artifact');
  const btnDownloadPdf = document.getElementById('btn-download-pdf');

  if (btnRef) {
    btnRef.addEventListener('click', async () => {
      if (!state.activeApplicationId) return;
      try {
        btnRef.disabled = true;
        const res = await window.api.generateReferenceSheet(state.caseId, state.activeApplicationId);
        const previewText = `YOJANA SAATHI — PRE-SUBMISSION REFERENCE SHEET\nPackage ID: ${res.package_id}\nApplication: ${res.application_id}\nScheme: ${res.scheme_id}\nStatus: ${res.status}\n\nDISCLAIMER: NOT AN OFFICIAL GOVERNMENT FORM — PRE-SUBMISSION AID ONLY\n\nReference Sheet generated and archived successfully.`;
        showArtifactPreview("CSC/VLE Operator Reference Sheet", previewText);
        if (res.reference_sheet && res.reference_sheet.download_url && btnDownloadPdf) {
          btnDownloadPdf.style.display = 'inline-block';
          btnDownloadPdf.onclick = () => window.open(res.reference_sheet.download_url, '_blank');
        }
      } catch (err) {
        showToast(`Reference sheet error: ${err.message}`, 'error');
      } finally {
        btnRef.disabled = false;
      }
    });
  }

  if (btnDossier) {
    btnDossier.addEventListener('click', async () => {
      if (!state.activeApplicationId) return;
      try {
        btnDossier.disabled = true;
        const res = await window.api.generateDossier(state.caseId, state.activeApplicationId);
        const previewText = `YOJANA SAATHI — PRE-SUBMISSION APPLICATION DOSSIER\nPackage ID: ${res.package_id}\nApplication: ${res.application_id}\nScheme: ${res.scheme_id}\nStatus: ${res.status}\n\nDISCLAIMER: NOT AN OFFICIAL GOVERNMENT FORM — PRE-SUBMISSION AID ONLY\n\nDossier PDF compiled with citizen profile facts, scheme conditions audit, and verified document index.`;
        showArtifactPreview("Comprehensive Application Dossier", previewText);
        if (res.dossier && res.dossier.download_url && btnDownloadPdf) {
          btnDownloadPdf.style.display = 'inline-block';
          btnDownloadPdf.onclick = () => window.open(res.dossier.download_url, '_blank');
        }
      } catch (err) {
        showToast(`Dossier error: ${err.message}`, 'error');
      } finally {
        btnDossier.disabled = false;
      }
    });
  }

  if (btnPkg) {
    btnPkg.addEventListener('click', async () => {
      if (!state.activeApplicationId) return;
      try {
        btnPkg.disabled = true;
        const res = await window.api.generateHandoffPackage(state.caseId, state.activeApplicationId);
        showToast("Complete Handoff Package compiled successfully!", 'success');
        const previewText = `YOJANA SAATHI — COMPLETE CSC/VLE HANDOFF PACKAGE\nPackage ID: ${res.package_id}\nApplication: ${res.application_id}\nScheme: ${res.scheme_id}\nStatus: ${res.status}\nReadiness: ${res.readiness}\n\nDISCLAIMER: NOT AN OFFICIAL GOVERNMENT FORM — PRE-SUBMISSION AID ONLY\n\nIncluded Artifacts:\n- Reference Sheet: ${res.reference_sheet_available ? 'Ready' : 'Pending'}\n- Comprehensive Dossier: ${res.dossier_available ? 'Ready' : 'Pending'}`;
        showArtifactPreview("Complete Handoff Package Summary", previewText);
        
        if (res.reference_sheet && res.reference_sheet.download_url && btnDownloadPdf) {
          btnDownloadPdf.style.display = 'inline-block';
          btnDownloadPdf.onclick = () => window.open(res.reference_sheet.download_url, '_blank');
        }
      } catch (err) {
        showToast(`Package creation failed: ${err.message}`, 'error');
      } finally {
        btnPkg.disabled = false;
      }
    });
  }

  if (btnClose) {
    btnClose.addEventListener('click', () => {
      const container = document.getElementById('artifact-preview-container');
      if (container) container.style.display = 'none';
    });
  }
}

function showArtifactPreview(title, content) {
  const container = document.getElementById('artifact-preview-container');
  const titleEl = document.getElementById('artifact-preview-title');
  const bodyEl = document.getElementById('artifact-content-body');

  if (container && titleEl && bodyEl) {
    container.style.display = 'block';
    titleEl.textContent = title;
    bodyEl.innerHTML = `<pre class="artifact-pre">${escapeHtml(content)}</pre>`;
    container.scrollIntoView({ behavior: 'smooth' });
  }
}

function renderHandoffView() {
  const container = document.getElementById('artifact-preview-container');
  if (container) container.style.display = 'none';
}

// =========================================================================
// 16. REJECTION & STATEFUL RECOVERY (PHASE 7)
// =========================================================================
function bindRecoveryActions() {
  const btnClaimModal = document.getElementById('btn-claim-rejection-modal');
  if (btnClaimModal) {
    btnClaimModal.addEventListener('click', () => {
      if (!state.activeApplicationId) {
        showToast("Select an application first.", "warning");
        return;
      }
      openModal('modal-claim-rejection');
    });
  }

  const btnSubmitRejection = document.getElementById('btn-submit-rejection-claim');
  if (btnSubmitRejection) {
    btnSubmitRejection.addEventListener('click', async () => {
      const codeInput = document.getElementById('rejection-code-input');
      const textInput = document.getElementById('rejection-notice-text');

      const code = codeInput ? codeInput.value.trim() : '';
      const text = textInput ? textInput.value.trim() : '';

      if (!code && !text) {
        showToast("Please provide either a rejection code or notice text.", "warning");
        return;
      }

      try {
        btnSubmitRejection.disabled = true;
        // 1. Claim
        const claimRes = await window.api.claimRejection(state.caseId, state.activeApplicationId);
        const eventId = claimRes.event_id;

        // 2. Add Evidence
        await window.api.addRejectionEvidence(state.caseId, state.activeApplicationId, eventId, 'OFFICIAL_PORTAL_NOTICE', text, code);

        // 3. Decode Root Cause
        const decodeRes = await window.api.decodeRejection(state.caseId, state.activeApplicationId, eventId);

        closeModal('modal-claim-rejection');
        showToast(`Rejection decoded: ${decodeRes.category}`, 'info');

        if (codeInput) codeInput.value = '';
        if (textInput) textInput.value = '';

        await refreshCaseState();
        renderRecoveryView();

      } catch (err) {
        showToast(`Rejection decoding failed: ${err.message}`, 'error');
      } finally {
        btnSubmitRejection.disabled = false;
      }
    });
  }
}

async function renderRecoveryView() {
  const badge = document.getElementById('recovery-state-badge');
  const heading = document.getElementById('recovery-heading');
  const desc = document.getElementById('recovery-desc');
  const rootBox = document.getElementById('decoded-root-cause-box');
  const catVal = document.getElementById('decoded-category-val');
  const reasonVal = document.getElementById('decoded-reason-val');
  const actionContainer = document.getElementById('recovery-action-container');
  const stepsList = document.getElementById('recovery-steps-list');

  if (!state.activeApplicationId) {
    if (heading) heading.textContent = "Select an application to inspect recovery state";
    return;
  }

  try {
    const res = await window.api.getRecoveryState(state.caseId, state.activeApplicationId);
    const recStatus = res.recovery_status || 'NONE';

    if (badge) {
      badge.textContent = recStatus;
      badge.className = `recovery-badge ${recStatus === 'RECOVERED' ? 'badge-success' : (recStatus === 'NONE' ? 'badge-neutral' : 'badge-danger')}`;
    }

    if (recStatus === 'NONE') {
      if (heading) heading.textContent = "No active rejection event";
      if (desc) desc.textContent = "Application is in normal progression. If rejected by official portal, click 'Report Rejection'.";
      if (rootBox) rootBox.style.display = 'none';
      if (actionContainer) actionContainer.style.display = 'none';
    } else {
      if (heading) heading.textContent = `Rejection Active: ${recStatus}`;
      if (desc) desc.textContent = res.explanation || "Bounded decoder has identified the root failure cause.";

      if (rootBox && res.decoded_category) {
        rootBox.style.display = 'block';
        if (catVal) catVal.textContent = res.decoded_category;
        if (reasonVal) reasonVal.textContent = res.root_cause_explanation || "Supported decoder pattern match.";
      }

      // Action Executor
      if (actionContainer && stepsList) {
        actionContainer.style.display = 'block';
        const actions = res.prescribed_actions || [];
        if (actions.length === 0) {
          stepsList.innerHTML = `<div class="empty-notice">No automatic recovery actions pending.</div>`;
        } else {
          stepsList.innerHTML = actions.map(act => `
            <div class="recovery-step-item">
              <div class="step-title">🔧 ${escapeHtml(act.title || act.action)}</div>
              <p class="step-desc">${escapeHtml(act.instructions || act.description || '')}</p>
              <button class="btn btn-primary btn-sm btn-exec-action" data-action="${escapeHtml(act.action)}" data-event-id="${escapeHtml(res.event_id || '')}">
                Execute Action: ${escapeHtml(act.action)}
              </button>
            </div>
          `).join('');

          stepsList.querySelectorAll('.btn-exec-action').forEach(btn => {
            btn.addEventListener('click', async () => {
              const act = btn.getAttribute('data-action');
              const evId = btn.getAttribute('data-event-id');
              try {
                btn.disabled = true;
                await window.api.executeRecoveryAction(state.caseId, state.activeApplicationId, evId, act);
                showToast(`Executed recovery action '${act}'`, 'success');
                await refreshCaseState();
                renderRecoveryView();
              } catch (e) {
                showToast(`Action failed: ${e.message}`, 'error');
              } finally {
                btn.disabled = false;
              }
            });
          });
        }
      }
    }
  } catch (err) {
    console.error("Recovery check error:", err);
  }
}

// =========================================================================
// 17. CSC/VLE AUDIT LOG VIEWER
// =========================================================================
async function openAuditLogModal() {
  if (!state.caseId) {
    showToast("No active case to inspect audit log.", "warning");
    return;
  }

  const tbody = document.getElementById('audit-log-tbody');
  openModal('modal-activity-log');

  try {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-cell">Loading audit trail from PostgreSQL...</td></tr>`;
    const res = await window.api.getActivityLog(state.caseId);
    const events = res.events || [];

    if (events.length === 0) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-cell">No audit events recorded for this case yet.</td></tr>`;
      return;
    }

    if (tbody) {
      tbody.innerHTML = events.map(ev => `
        <tr>
          <td><strong>${ev.iteration}</strong></td>
          <td><span class="badge badge-sm badge-info">${escapeHtml(ev.stage)}</span></td>
          <td>${escapeHtml(ev.action)}</td>
          <td><code>${escapeHtml(ev.reason_code || '—')}</code></td>
          <td>${escapeHtml(ev.selected_field || '—')}</td>
          <td class="time-col">${ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : '—'}</td>
        </tr>
      `).join('');
    }
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-cell">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// =========================================================================
// 18. MODALS & TOAST NOTIFICATIONS
// =========================================================================
function bindModals() {
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const mid = btn.getAttribute('data-close-modal');
      closeModal(mid);
    });
  });

  const submitNewCaseBtn = document.getElementById('btn-submit-new-case');
  if (submitNewCaseBtn) {
    submitNewCaseBtn.addEventListener('click', async () => {
      const input = document.getElementById('new-case-goal');
      const goal = input ? input.value.trim() : null;
      await createNewCase(goal);
    });
  }

  const submitOpenCaseBtn = document.getElementById('btn-submit-open-case');
  if (submitOpenCaseBtn) {
    submitOpenCaseBtn.addEventListener('click', async () => {
      const input = document.getElementById('open-case-id');
      const cid = input ? input.value.trim() : null;
      if (!cid) {
        showToast("Please enter a valid Case ID", "warning");
        return;
      }
      await loadCase(cid);
    });
  }
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.style.display = 'flex';
    const firstInput = modal.querySelector('input, select, textarea');
    if (firstInput) setTimeout(() => firstInput.focus(), 50);
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'none';
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${type === 'success' ? '✓' : (type === 'error' ? '✕' : (type === 'warning' ? '⚠️' : 'ℹ️'))}</span>
    <span class="toast-msg">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
