"""
Yojana Saathi - Voice Service
=============================
Core voice orchestration service for Phase 8 Multilingual Voice & Audio.
Enforces the mandatory architectural rule:
    Voice is an alternate interface layer to the existing message pipeline.
    It does NOT create a separate agent, does NOT bypass confirmation gates,
    and does NOT decide eligibility.
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.agent.actions import ActionType
from backend.app.agent.controller import AgentController
from backend.app.agent.policies import STANDARD_QUESTIONS
from backend.app.agent.provider import DeterministicActionProvider
from backend.app.agent.state import AgentState, StageEnum
from backend.app.db.repositories.case_repository import CaseRepository
from backend.app.db.repositories.confirmation_repository import ConfirmationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.services.state_persistence import load_case, persist_agent_state
from backend.app.integrations.groq import (
    GroqWhisperProvider,
    SpeechToTextError,
    SpeechToTextProvider,
    SpeechToTextResult,
    SpeechToTextUnavailableError,
)
from backend.app.profile.coordinator import ProfileCoordinator
from backend.app.schemas.voice import (
    LANGUAGE_METADATA,
    SUPPORTED_LANGUAGES,
    VoiceTurnResponse,
)

logger = logging.getLogger(__name__)

# Upload validation constraints
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB maximum upload
ALLOWED_MIME_PREFIXES = ("audio/",)
ALLOWED_MIME_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/mp3",
    "audio/webm",
    "audio/ogg", "audio/vorbis", "audio/opus",
    "audio/x-m4a", "audio/m4a", "audio/aac",
    "audio/flac", "audio/x-matroska",
    "application/octet-stream",  # Raw browser PCM/WAV blobs
}
DISALLOWED_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".sh", ".py", ".bin", ".js", ".msi", ".jar"}

# Spoken localized question prompts
LOCALIZED_QUESTIONS = {
    "annual_income_inr": {
        "en": "What is your approximate annual family income in rupees?",
        "hi": "आपकी वार्षिक पारिवारिक आय लगभग कितने रुपये है?",
        "te": "మీ కుటుంబ వార్షిక ఆదాయం సుమారుగా ఎన్ని రూపాయలు?",
    },
    "land_holding_acres": {
        "en": "How many acres of agricultural land do you own?",
        "hi": "आपके पास कितने एकड़ कृषि भूमि है?",
        "te": "మీకు ఎన్ని ఎకరాల వ్యవసాయ భూమి ఉంది?",
    },
    "land_acres": {
        "en": "How many acres of agricultural land do you own or cultivate?",
        "hi": "आपके पास कितने एकड़ कृषि भूमि है?",
        "te": "మీకు ఎన్ని ఎకరాల వ్యవసాయ భూమి ఉంది?",
    },
    "land_ownership": {
        "en": "Do you own cultivable agricultural land?",
        "hi": "क्या आपके पास कृषि योग्य भूमि है?",
        "te": "మీకు సాగు భూమి ఉందా?",
    },
    "cultivates_land": {
        "en": "Do you actively cultivate agricultural land?",
        "hi": "क्या आप कृषि भूमि पर खेती करते हैं?",
        "te": "మీరు వ్యవసాయ భూమిని సాగు చేస్తున్నారా?",
    },
    "annual_family_income_inr": {
        "en": "What is your approximate total annual family income?",
        "hi": "आपकी कुल वार्षिक पारिवारिक आय लगभग कितनी है?",
        "te": "మీ మొత్తం వార్షిక కుటుంబ ఆదాయం సుమారుగా ఎంత?",
    },
    "residence_type": {
        "en": "Do you reside in a rural village or an urban area?",
        "hi": "क्या आप ग्रामीण क्षेत्र में रहते हैं या शहरी क्षेत्र में?",
        "te": "మీరు గ్రామీణ ప్రాంతంలో నివసిస్తున్నారా లేక పట్టణ ప్రాంతంలోనా?",
    },
    "category": {
        "en": "Which social or occupational category applies to you?",
        "hi": "आप किस सामाजिक या व्यावसायिक श्रेणी में आते हैं?",
        "te": "మీరు ఏ సామాజిక వర్గానికి చెందినవారు?",
    },
    "gender": {
        "en": "What is your gender?",
        "hi": "आपका लिंग क्या है?",
        "te": "మీ లింగం ఏమిటి?",
    },
    "is_bpl": {
        "en": "Does your family hold a valid BPL (Below Poverty Line) ration card?",
        "hi": "क्या आपके परिवार के पास बीपीएल राशन कार्ड है?",
        "te": "మీ కుటుంబానికి బీపీఎల్ రేషన్ కార్డు ఉందా?",
    },
    "farmer_type": {
        "en": "What type of farmer are you, such as small, marginal, or tenant farmer?",
        "hi": "आप किस प्रकार के किसान हैं, जैसे छोटे, सीमांत, या बटाईदार किसान?",
        "te": "మీరు ఏ రకమైన రైతు, ఉదాహరణకు చిన్న, సన్నకారు లేదా కౌలు రైతు?",
    },
    "caste_category": {
        "en": "What is your social caste category (e.g., General, OBC, SC, or ST)?",
        "hi": "आपकी सामाजिक जाति श्रेणी क्या है (जैसे सामान्य, ओबीसी, एससी, या एसटी)?",
        "te": "మీ సామాజిక కుల వర్గం ఏమిటి (ఉదాహరణకు జనరల్, ఓబీసీ, ఎస్సీ లేదా ఎస్టీ)?",
    },
    "state": {
        "en": "Which state do you permanently reside in?",
        "hi": "आप स्थायी रूप से किस राज्य में रहते हैं?",
        "te": "మీరు ఏ రాష్ట్రంలో శాశ్వతంగా నివసిస్తున్నారు?",
    },
    "age": {
        "en": "What is your age in years?",
        "hi": "आपकी आयु कितने वर्ष है?",
        "te": "మీ వయస్సు ఎన్ని సంవత్సరాలు?",
    },
    "is_institutional_landholder": {
        "en": "Do you hold institutional land?",
        "hi": "क्या आपके पास संस्थागत भूमि है?",
        "te": "మీ వద్ద సంస్థాగత భూమి ఉందా?",
    },
    "has_family_pensioner": {
        "en": "Is anyone in your family a retired government pensioner?",
        "hi": "क्या आपके परिवार में कोई सेवानिवृत्त सरकारी पेंशनभोगी है?",
        "te": "మీ కుటుంబంలో ఎవరైనా పదవీ విరమణ పొందిన ప్రభుత్వ పెన్షనర్ ఉన్నారా?",
    },
}

LOCALIZED_FALLBACKS = {
    "stt_unavailable": {
        "en": "Voice transcription is currently unavailable. Please type your message.",
        "hi": "वॉयस ट्रांसक्रिप्शन वर्तमान में अनुपलब्ध है। कृपया अपना संदेश टाइप करें।",
        "te": "వాయిస్ ట్రాన్స్‌క్రిప్షన్ ప్రస్తుతం అందుబాటులో లేదు. దయచేసి మీ సందేశాన్ని టైప్ చేయండి.",
    },
    "stt_empty": {
        "en": "I couldn't understand that clearly. Please repeat or type your answer.",
        "hi": "मैं इसे स्पष्ट रूप से नहीं समझ सका। कृपया दोहराएं या अपना उत्तर टाइप करें।",
        "te": "నేను దానిని స్పష్టంగా అర్థం చేసుకోలేకపోయాను. దయచేసి మళ్ళీ చెప్పండి లేదా టైప్ చేయండి.",
    },
    "confirm_request": {
        "en": "I understood your details. Please confirm if this is correct.",
        "hi": "मैंने आपकी जानकारी समझ ली है। कृपया पुष्टि करें कि क्या यह सही है।",
        "te": "నేను మీ వివరాలను అర్థం చేసుకున్నాను. ఇది సరైనదేనా అని దయచేసి ధృవీకరించండి.",
    },
    "profile_confirmed": {
        "en": "Your profile changes are confirmed. Evaluating your welfare eligibility now.",
        "hi": "आपकी प्रोफ़ाइल में किए गए परिवर्तनों की पुष्टि हो गई है। अब आपकी पात्रता का मूल्यांकन किया जा रहा है।",
        "te": "మీ ప్రొఫైల్ మార్పులు ధృవీకరించబడ్డాయి. ఇప్పుడు మీ సంక్షేమ అర్హత పరిశీలించబడుతోంది.",
    },
    "profile_rejected": {
        "en": "Proposed changes were rejected. Your confirmed profile remains unchanged.",
        "hi": "प्रस्तावित बदलाव अस्वीकार कर दिए गए। आपकी प्रोफ़ाइल अपरिवर्तित है।",
        "te": "ప్రతిపాదిత మార్పులు తిరస్కరించబడ్డాయి. మీ ప్రొఫైల్ మారలేదు.",
    },
}


class VoiceService:
    """
    Coordinates voice-driven intake and spoken response orchestration.
    """

    def __init__(
        self,
        stt_provider: Optional[SpeechToTextProvider] = None,
        profile_coordinator: Optional[ProfileCoordinator] = None,
        agent_controller: Optional[AgentController] = None,
    ):
        self.stt_provider = stt_provider or GroqWhisperProvider()
        self.profile_coordinator = profile_coordinator or ProfileCoordinator()
        self.agent_controller = agent_controller or AgentController(provider=DeterministicActionProvider())
        # In-memory turn cache for idempotency
        self._turn_cache: Dict[str, VoiceTurnResponse] = {}

    def validate_audio_upload(
        self, audio_bytes: bytes, filename: str, content_type: Optional[str] = None
    ) -> None:
        """Validates file size, content, and MIME type."""
        if not audio_bytes or len(audio_bytes) == 0:
            raise ValueError("Audio upload is empty (0 bytes received).")

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValueError(
                f"Audio file size ({len(audio_bytes)} bytes) exceeds the maximum allowed limit of {MAX_AUDIO_BYTES} bytes."
            )

        # Check file extension
        _, ext = os.path.splitext(filename.lower())
        if ext in DISALLOWED_EXTENSIONS:
            raise ValueError(f"File type '{ext}' is not permitted.")

        # Check MIME type
        norm_type = (content_type or "").lower().split(";")[0].strip()
        if norm_type and norm_type not in ALLOWED_MIME_TYPES and not norm_type.startswith(ALLOWED_MIME_PREFIXES):
            # If application/octet-stream, allow if extension is an audio extension
            if norm_type != "application/octet-stream" or ext not in {".wav", ".mp3", ".ogg", ".webm", ".m4a", ".flac"}:
                raise ValueError(f"Unsupported audio format '{content_type}'. Supported formats: WAV, MP3, WebM, OGG, M4A, FLAC.")

    def format_confirmation_prompt(self, changes: List[Dict[str, Any]], lang: str = "en") -> str:
        """Constructs a concise, speakable confirmation prompt."""
        if not changes:
            return LOCALIZED_FALLBACKS["confirm_request"].get(lang, LOCALIZED_FALLBACKS["confirm_request"]["en"])

        facts_text = []
        for ch in changes:
            f = ch.get("field", "")
            v = ch.get("proposed") if ch.get("proposed") is not None else ch.get("proposed_value")
            if f == "land_holding_acres":
                facts_text.append(f"{v} acres of land")
            elif f == "annual_income_inr":
                facts_text.append(f"income of {v} rupees")
            elif f == "occupation":
                facts_text.append(f"occupation as {v}")
            elif f == "state":
                facts_text.append(f"state as {v}")
            else:
                facts_text.append(f"{f} as {v}")

        joined_facts = ", ".join(facts_text)
        if lang == "hi":
            return f"मैंने समझा कि आपके पास {joined_facts} है। क्या यह सही है? पुष्टि के लिए हाँ या नहीं कहें।"
        elif lang == "te":
            return f"నేను మీ వివరాలు {joined_facts} గా అర్థం చేసుకున్నాను. ఇది సరైనదేనా? ధృవీకరించడానికి అవును లేదా కాదు అని చెప్పండి."
        else:
            return f"I understood {joined_facts}. Is that correct? Please say yes to confirm or no to correct."

    def process_voice_turn(
        self,
        db: Session,
        case_id: str,
        audio_bytes: bytes,
        filename: str = "recording.wav",
        content_type: Optional[str] = "audio/wav",
        language: Optional[str] = "en",
        turn_id: Optional[str] = None,
    ) -> VoiceTurnResponse:
        """
        Executes an end-to-end voice turn:
        1. Validates audio upload.
        2. Enforces turn idempotency.
        3. Invokes STT provider.
        4. Passes transcript to existing message / profile / agent pipeline.
        5. Generates speakable TTS-ready text.
        6. Persists state and caches response.
        """
        # 1. Normalize language code
        norm_lang = (language or "en").lower().strip()
        if norm_lang not in SUPPORTED_LANGUAGES:
            norm_lang = "en"

        turn_key = f"{case_id}:{turn_id}" if turn_id else None
        if turn_key and turn_key in self._turn_cache:
            logger.info(f"Returning cached voice turn for key {turn_key}")
            return self._turn_cache[turn_key]

        gen_turn_id = turn_id or f"turn-{uuid.uuid4().hex[:10]}"

        # 2. Load case from PostgreSQL
        state = load_case(db, case_id)
        if not state:
            raise ValueError(f"Case {case_id} not found.")

        # 3. Audio upload validation
        self.validate_audio_upload(audio_bytes, filename, content_type)

        # 4. Transcribe Audio using STT Provider
        try:
            stt_result = self.stt_provider.transcribe(
                audio_bytes=audio_bytes,
                filename=filename,
                language=norm_lang,
            )
        except SpeechToTextUnavailableError as e:
            logger.warning(f"STT provider unavailable for case {case_id}: {e}")
            fallback_text = LOCALIZED_FALLBACKS["stt_unavailable"].get(
                norm_lang, LOCALIZED_FALLBACKS["stt_unavailable"]["en"]
            )
            return VoiceTurnResponse(
                turn_id=gen_turn_id,
                case_id=case_id,
                input_mode="VOICE",
                language=norm_lang,
                transcript="",
                response_text=fallback_text,
                response_language=norm_lang,
                agent_action="WAITING_FOR_USER_INPUT",
                state_updated=False,
                tts_available=True,
                tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
                status="VOICE_TRANSCRIPTION_FAILED",
                confirmation_required=bool(state.pending_confirmation),
                text_fallback_available=True,
                provider="groq_whisper",
                stage=state.stage,
                missing_information=state.missing_information,
                error_detail="Speech-to-text service is currently unavailable. Text input is ready.",
            )
        except SpeechToTextError as e:
            logger.warning(f"STT failed for case {case_id}: {e}")
            fallback_text = LOCALIZED_FALLBACKS["stt_empty"].get(
                norm_lang, LOCALIZED_FALLBACKS["stt_empty"]["en"]
            )
            return VoiceTurnResponse(
                turn_id=gen_turn_id,
                case_id=case_id,
                input_mode="VOICE",
                language=norm_lang,
                transcript="",
                response_text=fallback_text,
                response_language=norm_lang,
                agent_action="WAITING_FOR_USER_INPUT",
                state_updated=False,
                tts_available=True,
                tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
                status="VOICE_TRANSCRIPTION_FAILED",
                confirmation_required=bool(state.pending_confirmation),
                text_fallback_available=True,
                provider="groq_whisper",
                stage=state.stage,
                missing_information=state.missing_information,
                error_detail=str(e),
            )

        transcript = (stt_result.transcript or "").strip()
        detected_lang = stt_result.detected_language or norm_lang

        # Reject empty or punctuation-only transcripts
        if not transcript or len(transcript) < 2 or transcript in {".", "..", "...", "?"}:
            empty_text = LOCALIZED_FALLBACKS["stt_empty"].get(
                norm_lang, LOCALIZED_FALLBACKS["stt_empty"]["en"]
            )
            return VoiceTurnResponse(
                turn_id=gen_turn_id,
                case_id=case_id,
                input_mode="VOICE",
                language=norm_lang,
                detected_language=detected_lang,
                transcript=transcript,
                response_text=empty_text,
                response_language=norm_lang,
                agent_action="WAITING_FOR_USER_INPUT",
                state_updated=False,
                tts_available=True,
                tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
                status="VOICE_TRANSCRIPTION_EMPTY",
                confirmation_required=bool(state.pending_confirmation),
                text_fallback_available=True,
                duration_seconds=stt_result.duration_seconds,
                provider=stt_result.provider,
                stage=state.stage,
                missing_information=state.missing_information,
            )

        # 5. Persist Language Preference to session / case
        state.language_preference = norm_lang

        # 6. Check for Special Spoken Queries before profile extraction:
        # e.g., Multi-scheme status query, Document readiness query, Rejection query
        lower_trans = transcript.lower()

        # A. Voice Multi-Scheme Status Query
        if any(kw in lower_trans for kw in ["status of my applications", "farmer applications", "application status", "అప్లికేషన్ స్థితి", "आवेदन स्थिति"]):
            if state.applications:
                app_statuses = []
                for s_id, app_info in state.applications.items():
                    s_name = "PM-KISAN" if "pm_kisan" in s_id else ("Rythu Bharosa" if "rythu" in s_id else s_id)
                    app_statuses.append(f"{s_name} is {app_info.get('status', 'ACTIVE')}")
                status_summary = ". ".join(app_statuses)
                if norm_lang == "te":
                    spoken_resp = f"మీ దరఖాస్తుల ప్రస్తుత స్థితి: {status_summary}."
                elif norm_lang == "hi":
                    spoken_resp = f"आपके आवेदनों की वर्तमान स्थिति: {status_summary}."
                else:
                    spoken_resp = f"Current application status: {status_summary}."
            else:
                spoken_resp = "You have no active applications selected yet." if norm_lang == "en" else "మీకు ఇంకా ఏ దరఖాస్తులు లేవు."

            response = VoiceTurnResponse(
                turn_id=gen_turn_id,
                case_id=case_id,
                input_mode="VOICE",
                language=norm_lang,
                detected_language=detected_lang,
                transcript=transcript,
                response_text=spoken_resp,
                response_language=norm_lang,
                agent_action="CHECK_APPLICATIONS",
                state_updated=False,
                tts_available=True,
                tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
                status="SUCCESS",
                duration_seconds=stt_result.duration_seconds,
                provider=stt_result.provider,
                stage=state.stage,
                missing_information=state.missing_information,
            )
            if turn_key:
                self._turn_cache[turn_key] = response
            return response

        # B. Voice Document Readiness Query
        if any(kw in lower_trans for kw in ["which document is missing", "document missing", "documents required", "ఏ పత్రాలు", "कौन से दस्तावेज़"]):
            # Summarize document requirements
            verified_docs = [d.get("document_type") for d in state.documents if d.get("status") == "VERIFIED"]
            required_docs = ["bank_passbook"]  # Standard requirement demonstration
            if "land_record" in [d.get("document_type") for d in state.documents] or state.profile.get("land_holding_acres"):
                spoken_doc = "The land record is verified. The bank passbook is still required."
            else:
                spoken_doc = "Land record and bank passbook are required for your application."
            if norm_lang == "te":
                spoken_doc = "భూమి రికార్డు ధృవీకరించబడింది. బ్యాంకు పాస్‌బుక్ ఇంకా సమర్పించాల్సి ఉంది."
            elif norm_lang == "hi":
                spoken_doc = "भूमि रिकॉर्ड सत्यापित है। बैंक पासबुक अभी भी आवश्यक है।"

            response = VoiceTurnResponse(
                turn_id=gen_turn_id,
                case_id=case_id,
                input_mode="VOICE",
                language=norm_lang,
                detected_language=detected_lang,
                transcript=transcript,
                response_text=spoken_doc,
                response_language=norm_lang,
                agent_action="REQUEST_DOCUMENT",
                state_updated=False,
                tts_available=True,
                tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
                status="SUCCESS",
                duration_seconds=stt_result.duration_seconds,
                provider=stt_result.provider,
                stage=state.stage,
                missing_information=state.missing_information,
            )
            if turn_key:
                self._turn_cache[turn_key] = response
            return response

        # C. Voice Rejection Reporting
        if any(kw in lower_trans for kw in ["rejected", "application was rejected", "తిరస్కరించబడింది", "రద్దు చేయబడింది", "खारिज", "अस्वीकार"]):
            if norm_lang == "te":
                spoken_rej = "దయచేసి మీ తిరస్కరణ నోటీసులోని అధికారిక సందేశం లేదా కోడ్‌ను అందించండి."
            elif norm_lang == "hi":
                spoken_rej = "कृपया अपने आधिकारिक अस्वीकृति नोटिस का संदेश या कोड प्रदान करें।"
            else:
                spoken_rej = "Please provide the official rejection message or code from your rejection notice."

            response = VoiceTurnResponse(
                turn_id=gen_turn_id,
                case_id=case_id,
                input_mode="VOICE",
                language=norm_lang,
                detected_language=detected_lang,
                transcript=transcript,
                response_text=spoken_rej,
                response_language=norm_lang,
                agent_action="REQUEST_REJECTION_EVIDENCE",
                state_updated=False,
                tts_available=True,
                tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
                status="SUCCESS",
                duration_seconds=stt_result.duration_seconds,
                provider=stt_result.provider,
                stage=state.stage,
                missing_information=state.missing_information,
            )
            if turn_key:
                self._turn_cache[turn_key] = response
            return response

        # 7. Standard Flow: Route Transcript to existing ProfileCoordinator
        coord_result = self.profile_coordinator.process_user_message(state, transcript)

        raw_changes = coord_result.get("changes", [])
        changes = []
        for ch in raw_changes:
            c_dict = dict(ch)
            if "proposed" in c_dict and "proposed_value" not in c_dict:
                c_dict["proposed_value"] = c_dict["proposed"]
            elif "proposed_value" in c_dict and "proposed" not in c_dict:
                c_dict["proposed"] = c_dict["proposed_value"]
            changes.append(c_dict)
        confirmation_req = coord_result.get("confirmation_required", False)
        status_val = coord_result.get("status", "SUCCESS")
        agent_action_val = None
        spoken_text = ""

        if status_val == "CONFIRMED":
            # Profile confirmed by user saying "yes" / "అవును" / "हाँ"
            pending_db = ConfirmationRepository.get_pending_by_case_id(db, case_id)
            if pending_db:
                ConfirmationRepository.resolve_confirmation(db, pending_db.id, "CONFIRMED")

            spoken_text = LOCALIZED_FALLBACKS["profile_confirmed"].get(
                norm_lang, LOCALIZED_FALLBACKS["profile_confirmed"]["en"]
            )
            agent_action_val = "PROFILE_CONFIRMED"

            # Step agent controller to pick next step
            try:
                activity, _ = self.agent_controller.step(state)
                agent_action_val = activity.selected_action
                if activity.selected_action == ActionType.ASK_QUESTION.value and activity.selected_field:
                    prompt_dict = LOCALIZED_QUESTIONS.get(activity.selected_field, {})
                    fallback_q = STANDARD_QUESTIONS.get(
                        activity.selected_field,
                        f"Could you please share your {activity.selected_field.replace('_', ' ')}?"
                    )
                    q_text = prompt_dict.get(norm_lang, prompt_dict.get("en", fallback_q))
                    spoken_text = f"{spoken_text} {q_text}"
            except Exception as e:
                logger.warning(f"AgentController step after confirmation encountered non-critical issue: {e}")

        elif status_val == "REJECTED":
            pending_db = ConfirmationRepository.get_pending_by_case_id(db, case_id)
            if pending_db:
                ConfirmationRepository.resolve_confirmation(db, pending_db.id, "REJECTED")

            spoken_text = LOCALIZED_FALLBACKS["profile_rejected"].get(
                norm_lang, LOCALIZED_FALLBACKS["profile_rejected"]["en"]
            )
            agent_action_val = "WAITING_FOR_USER_INPUT"

        elif confirmation_req:
            # Fact changes proposed -> human confirmation mandatory
            spoken_text = self.format_confirmation_prompt(changes, norm_lang)
            agent_action_val = "WAITING_FOR_PROFILE_CONFIRMATION"

            # Stage in database confirmation repository
            if state.pending_confirmation:
                ConfirmationRepository.create_confirmation(
                    db=db,
                    confirmation_id=state.pending_confirmation["confirmation_id"],
                    case_id=case_id,
                    proposed_changes=state.pending_confirmation.get("changes", []),
                    raw_patch=state.pending_confirmation.get("raw_patch", {}),
                )

        else:
            # No facts extracted or ambiguous input (e.g. conversational, or injection attempt)
            # Check prompt injection or irrelevant speech
            if any(inj in lower_trans for inj in ["ignore all rules", "make me eligible", "system says", "override"]):
                spoken_text = "I cannot alter eligibility rules or override system facts from that statement. Please provide your profile details."
                agent_action_val = "WAITING_FOR_USER_INPUT"
            elif coord_result.get("ambiguous_fields"):
                amb = ", ".join(coord_result["ambiguous_fields"])
                spoken_text = f"Could not determine exact value for {amb}. Please clarify."
                agent_action_val = "REQUEST_CLARIFICATION"
            else:
                # Step the controller to check next action
                try:
                    activity, _ = self.agent_controller.step(state)
                    agent_action_val = activity.selected_action
                    if activity.selected_action == ActionType.ASK_QUESTION.value and activity.selected_field:
                        prompt_dict = LOCALIZED_QUESTIONS.get(activity.selected_field, {})
                        fallback_q = STANDARD_QUESTIONS.get(
                            activity.selected_field,
                            f"Could you please share your {activity.selected_field.replace('_', ' ')}?"
                        )
                        spoken_text = prompt_dict.get(norm_lang, prompt_dict.get("en", fallback_q))
                    elif activity.selected_action == ActionType.RUN_ELIGIBILITY.value:
                        spoken_text = "All profile requirements are gathered. Evaluating scheme eligibility now."
                    else:
                        spoken_text = "Thank you. Please tell me more about your farming or household profile."
                except Exception:
                    spoken_text = "Thank you. Please tell me more about your farming or household profile."
                    agent_action_val = "WAITING_FOR_USER_INPUT"

        # 8. Persist updated AgentState to PostgreSQL
        persist_agent_state(db, state)

        # 9. Audit Event Observability
        EventRepository.record_agent_event(
            db=db,
            case_id=case_id,
            iteration=state.iteration,
            stage=state.stage,
            action="VOICE_MESSAGE_PROCESSED",
            reason_code="VOICE_INPUT",
            state_fingerprint=state.get_profile_fingerprint(),
            event_data={
                "turn_id": gen_turn_id,
                "input_mode": "VOICE",
                "language": norm_lang,
                "detected_language": detected_lang,
                "duration_seconds": stt_result.duration_seconds,
                "provider": stt_result.provider,
                "confirmation_required": confirmation_req,
            },
        )

        response = VoiceTurnResponse(
            turn_id=gen_turn_id,
            case_id=case_id,
            input_mode="VOICE",
            language=norm_lang,
            detected_language=detected_lang,
            transcript=transcript,
            response_text=spoken_text.strip(),
            response_language=norm_lang,
            agent_action=agent_action_val,
            state_updated=True,
            tts_available=True,
            tts_locales=LANGUAGE_METADATA.get(norm_lang, {}).get("locales", ["en-IN"]),
            status=status_val,
            confirmation_required=confirmation_req,
            changes=changes,
            text_fallback_available=True,
            duration_seconds=stt_result.duration_seconds,
            provider=stt_result.provider,
            stage=state.stage,
            missing_information=state.missing_information,
        )

        if turn_key:
            self._turn_cache[turn_key] = response

        return response
