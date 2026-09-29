"""
Yojana Saathi - Voice Interface Template
========================================
Interactive client-side Voice & Audio interface for Phase 8.
Features:
- Browser-native MediaRecorder audio capture
- Live state transitions: IDLE, LISTENING, UPLOADING, TRANSCRIBING, PROCESSING, SPEAKING, ERROR
- Multilingual language selection (English, हिन्दी, తెలుగు)
- Editable transcript review before confirmation
- Client-side SpeechSynthesis TTS with regional voices (en-IN, hi-IN, te-IN)
- Permanent typed text fallback
"""

VOICE_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yojana Saathi — Multilingual Voice & Audio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600&family=Noto+Sans+Devanagari:wght@400;600&family=Noto+Sans+Telugu:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0b0f19;
            --bg-card: rgba(18, 24, 38, 0.85);
            --border-card: rgba(255, 255, 255, 0.08);
            --primary: #10b981;
            --primary-hover: #059669;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.25);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --danger: #ef4444;
            --warning: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', 'Inter', 'Noto Sans Devanagari', 'Noto Sans Telugu', sans-serif;
            background: radial-gradient(circle at top center, #131d33 0%, #0b0f19 80%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem 1rem;
        }
        .container {
            width: 100%;
            max-width: 860px;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }
        header {
            text-align: center;
            margin-bottom: 0.5rem;
        }
        header h1 {
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #10b981 0%, #60a5fa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.4rem;
        }
        header p {
            color: var(--text-muted);
            font-size: 0.95rem;
        }
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .controls-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        @media (max-width: 640px) {
            .controls-row { grid-template-columns: 1fr; }
        }
        label {
            display: block;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }
        input, select, textarea {
            width: 100%;
            padding: 0.75rem 1rem;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-card);
            border-radius: 10px;
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.95rem;
            transition: all 0.2s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
        }
        .mic-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2.5rem 1rem;
            text-align: center;
            position: relative;
        }
        .mic-btn {
            width: 110px;
            height: 110px;
            border-radius: 50%;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.4rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            box-shadow: 0 0 24px rgba(16, 185, 129, 0.4);
            color: white;
        }
        .mic-btn:hover {
            transform: scale(1.06);
            box-shadow: 0 0 36px rgba(16, 185, 129, 0.6);
        }
        .mic-btn.listening {
            background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
            box-shadow: 0 0 36px rgba(239, 68, 68, 0.8);
            animation: pulse-ring 1.5s infinite;
        }
        @keyframes pulse-ring {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { transform: scale(1.08); box-shadow: 0 0 0 20px rgba(239, 68, 68, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .status-badge {
            margin-top: 1.2rem;
            padding: 0.4rem 1.2rem;
            border-radius: 9999px;
            font-size: 0.9rem;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-card);
            letter-spacing: 0.04em;
        }
        .status-listening { color: #f87171; border-color: rgba(239, 68, 68, 0.4); }
        .status-uploading, .status-transcribing, .status-processing { color: #60a5fa; border-color: rgba(59, 130, 246, 0.4); }
        .status-speaking { color: #34d399; border-color: rgba(16, 185, 129, 0.4); }
        .status-error { color: #fb7185; border-color: rgba(244, 63, 94, 0.4); }
        .dialogue-box {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .response-panel {
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 12px;
            padding: 1.2rem;
        }
        .response-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: #34d399;
            margin-bottom: 0.4rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .response-content {
            font-size: 1.1rem;
            line-height: 1.5;
            color: #f1f5f9;
        }
        .actions-bar {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-top: 0.75rem;
        }
        .btn {
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }
        .btn-primary { background: var(--primary); color: #022c22; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-secondary { background: rgba(255, 255, 255, 0.08); color: white; border: 1px solid var(--border-card); }
        .btn-secondary:hover { background: rgba(255, 255, 255, 0.14); }
        .btn-confirm { background: #10b981; color: white; }
        .btn-reject { background: #ef4444; color: white; }
        .fallback-divider {
            text-align: center;
            position: relative;
            margin: 0.5rem 0;
            color: var(--text-muted);
            font-size: 0.8rem;
        }
        .fallback-divider::before, .fallback-divider::after {
            content: '';
            position: absolute;
            top: 50%;
            width: 42%;
            height: 1px;
            background: var(--border-card);
        }
        .fallback-divider::before { left: 0; }
        .fallback-divider::after { right: 0; }
        .typed-input-group {
            display: flex;
            gap: 0.5rem;
        }
        .info-pill {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-size: 0.75rem;
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Yojana Saathi</h1>
            <p>Multilingual Voice & Audio Interface • English | हिन्दी | తెలుగు</p>
        </header>

        <!-- Case & Language Selector -->
        <div class="card">
            <div class="controls-row">
                <div>
                    <label for="case-id">Case Identifier</label>
                    <input type="text" id="case-id" placeholder="e.g. CASE-ABC12345" value="CASE-VOICE-DEMO">
                </div>
                <div>
                    <label for="lang-select">Spoken Language</label>
                    <select id="lang-select">
                        <option value="en" selected>English (India / Global)</option>
                        <option value="hi">हिन्दी (Hindi)</option>
                        <option value="te">తెలుగు (Telugu)</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Voice Interaction Hub -->
        <div class="card">
            <div class="mic-section">
                <button id="mic-btn" class="mic-btn" title="Click to start/stop speaking">
                    <span id="mic-icon">🎙️</span>
                </button>
                <div id="status-badge" class="status-badge">Ready (Click Mic to Speak)</div>
                <div style="margin-top: 0.6rem;">
                    <span id="tts-voice-indicator" class="info-pill">TTS: Browser SpeechSynthesis</span>
                </div>
            </div>

            <!-- Dialogue & Transcript Box -->
            <div class="dialogue-box">
                <div>
                    <label for="transcript-box">Recognized Speech (Review / Edit)</label>
                    <textarea id="transcript-box" rows="2" placeholder="Your spoken words will appear here. You can also edit before submitting..."></textarea>
                    <div class="actions-bar" style="justify-content: flex-end;">
                        <button id="submit-transcript-btn" class="btn btn-secondary">Submit Edited Text</button>
                        <button id="clear-btn" class="btn btn-secondary">Clear</button>
                    </div>
                </div>

                <!-- Spoken Response Display -->
                <div id="response-panel" class="response-panel" style="display: none;">
                    <div class="response-title">
                        <span>Agent Response (Spoken via TTS)</span>
                        <button id="replay-btn" class="btn btn-secondary" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;">🔊 Replay Audio</button>
                    </div>
                    <div id="response-content" class="response-content"></div>
                    <div id="confirmation-buttons" class="actions-bar" style="display: none; margin-top: 1rem;">
                        <button id="voice-confirm-btn" class="btn btn-confirm">✓ Confirm Details</button>
                        <button id="voice-reject-btn" class="btn btn-reject">✕ Reject / Correct</button>
                    </div>
                </div>
            </div>

            <!-- Fallback Typed Input -->
            <div class="fallback-divider">ALWAYS AVAILABLE TYPED FALLBACK</div>
            <div class="typed-input-group">
                <input type="text" id="typed-input" placeholder="Type your answer or statement here...">
                <button id="typed-send-btn" class="btn btn-primary">Send</button>
            </div>
        </div>
    </div>

    <script>
        // State Machine
        const AppState = {
            IDLE: 'IDLE',
            LISTENING: 'LISTENING',
            UPLOADING: 'UPLOADING',
            TRANSCRIBING: 'TRANSCRIBING',
            PROCESSING: 'PROCESSING',
            SPEAKING: 'SPEAKING',
            ERROR: 'ERROR'
        };

        let currentState = AppState.IDLE;
        let mediaRecorder = null;
        let audioChunks = [];
        let lastSpokenText = '';
        let lastSpokenLang = 'en';

        const micBtn = document.getElementById('mic-btn');
        const statusBadge = document.getElementById('status-badge');
        const transcriptBox = document.getElementById('transcript-box');
        const responsePanel = document.getElementById('response-panel');
        const responseContent = document.getElementById('response-content');
        const langSelect = document.getElementById('lang-select');
        const caseInput = document.getElementById('case-id');
        const replayBtn = document.getElementById('replay-btn');
        const confirmationBtns = document.getElementById('confirmation-buttons');
        const voiceConfirmBtn = document.getElementById('voice-confirm-btn');
        const voiceRejectBtn = document.getElementById('voice-reject-btn');
        const submitTranscriptBtn = document.getElementById('submit-transcript-btn');
        const clearBtn = document.getElementById('clear-btn');
        const typedInput = document.getElementById('typed-input');
        const typedSendBtn = document.getElementById('typed-send-btn');
        const ttsIndicator = document.getElementById('tts-voice-indicator');

        function setStatus(state, message) {
            currentState = state;
            statusBadge.className = 'status-badge status-' + state.toLowerCase();
            statusBadge.innerText = message || state;
            if (state === AppState.LISTENING) {
                micBtn.classList.add('listening');
            } else {
                micBtn.classList.remove('listening');
            }
        }

        // Initialize SpeechSynthesis Voices
        let availableVoices = [];
        function loadVoices() {
            if ('speechSynthesis' in window) {
                availableVoices = window.speechSynthesis.getVoices();
                const lang = langSelect.value;
                const match = findBestVoice(lang);
                if (match) {
                    ttsIndicator.innerText = `TTS: ${match.name} (${match.lang})`;
                } else {
                    ttsIndicator.innerText = `TTS: Default Voice (Fallback)`;
                }
            } else {
                ttsIndicator.innerText = `TTS: SpeechSynthesis not supported`;
            }
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = loadVoices;
            loadVoices();
        }

        function findBestVoice(langCode) {
            if (!availableVoices.length) return null;
            const targetLocales = {
                'en': ['en-IN', 'en-GB', 'en-US', 'en'],
                'hi': ['hi-IN', 'hi'],
                'te': ['te-IN', 'te']
            }[langCode] || ['en-IN', 'en'];

            for (const loc of targetLocales) {
                const found = availableVoices.find(v => v.lang.toLowerCase().replace('_', '-') === loc.toLowerCase());
                if (found) return found;
            }
            return availableVoices[0] || null;
        }

        function speakResponse(text, lang) {
            if (!('speechSynthesis' in window)) {
                console.warn('SpeechSynthesis unavailable.');
                return;
            }
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            const voice = findBestVoice(lang);
            if (voice) utterance.voice = voice;
            utterance.rate = 1.0;
            utterance.pitch = 1.0;

            utterance.onstart = () => setStatus(AppState.SPEAKING, 'Speaking Response...');
            utterance.onend = () => setStatus(AppState.IDLE, 'Ready');
            utterance.onerror = () => setStatus(AppState.IDLE, 'Ready');

            window.speechSynthesis.speak(utterance);
        }

        // Microphone Capture
        async function startRecording() {
            audioChunks = [];
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    await uploadAudio(audioBlob);
                    stream.getTracks().forEach(track => track.stop());
                };

                mediaRecorder.start();
                setStatus(AppState.LISTENING, 'Listening... (Speak Now)');
            } catch (err) {
                console.error('Microphone error:', err);
                setStatus(AppState.ERROR, 'Microphone Permission Denied');
                alert('Microphone access is unavailable. You can use the typed text box below.');
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                setStatus(AppState.UPLOADING, 'Uploading audio...');
            }
        }

        micBtn.addEventListener('click', () => {
            if (currentState === AppState.LISTENING) {
                stopRecording();
            } else {
                startRecording();
            }
        });

        // Audio Upload to Backend
        async function uploadAudio(audioBlob) {
            const caseId = caseInput.value.trim() || 'CASE-VOICE-DEMO';
            const lang = langSelect.value;
            const turnId = 'turn-' + Math.random().toString(36).substring(2, 10);

            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');
            formData.append('language', lang);
            formData.append('turn_id', turnId);

            setStatus(AppState.TRANSCRIBING, 'Transcribing & Processing...');

            try {
                const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}/voice`, {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Voice processing failed');
                }

                const data = await res.json();
                handleVoiceResponse(data);
            } catch (err) {
                console.error(err);
                setStatus(AppState.ERROR, 'Error: ' + err.message);
            }
        }

        function handleVoiceResponse(data) {
            transcriptBox.value = data.transcript || '';
            responsePanel.style.display = 'block';
            responseContent.innerText = data.response_text || '(No response text)';

            lastSpokenText = data.response_text;
            lastSpokenLang = data.response_language || langSelect.value;

            if (data.confirmation_required) {
                confirmationBtns.style.display = 'flex';
            } else {
                confirmationBtns.style.display = 'none';
            }

            if (data.tts_available && data.response_text) {
                speakResponse(data.response_text, lastSpokenLang);
            } else {
                setStatus(AppState.IDLE, 'Ready');
            }
        }

        replayBtn.addEventListener('click', () => {
            if (lastSpokenText) speakResponse(lastSpokenText, lastSpokenLang);
        });

        // Confirmation Actions
        async function sendConfirmation(decision) {
            const caseId = caseInput.value.trim();
            const endpoint = decision ? `/api/cases/${encodeURIComponent(caseId)}/profile/confirm` : `/api/cases/${encodeURIComponent(caseId)}/profile/reject`;
            try {
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                const resData = await res.json();
                confirmationBtns.style.display = 'none';
                responseContent.innerText = decision ? '✓ Confirmed and applied to profile.' : '✕ Proposed changes rejected.';
                speakResponse(responseContent.innerText, langSelect.value);
            } catch (err) {
                alert('Confirmation action failed: ' + err.message);
            }
        }

        voiceConfirmBtn.addEventListener('click', () => sendConfirmation(true));
        voiceRejectBtn.addEventListener('click', () => sendConfirmation(false));

        // Submit Edited Transcript / Typed Text Fallback
        async function sendTextMessage(text) {
            if (!text.trim()) return;
            const caseId = caseInput.value.trim();
            setStatus(AppState.PROCESSING, 'Processing message...');
            try {
                const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}/messages`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text.trim() })
                });
                const data = await res.json();
                responsePanel.style.display = 'block';
                responseContent.innerText = data.message || 'Message processed.';
                lastSpokenText = data.message;
                lastSpokenLang = langSelect.value;

                if (data.confirmation_required) {
                    confirmationBtns.style.display = 'flex';
                } else {
                    confirmationBtns.style.display = 'none';
                }
                speakResponse(data.message, langSelect.value);
            } catch (err) {
                setStatus(AppState.ERROR, 'Failed: ' + err.message);
            }
        }

        submitTranscriptBtn.addEventListener('click', () => sendTextMessage(transcriptBox.value));
        clearBtn.addEventListener('click', () => {
            transcriptBox.value = '';
            responsePanel.style.display = 'none';
        });

        typedSendBtn.addEventListener('click', () => {
            sendTextMessage(typedInput.value);
            typedInput.value = '';
        });
        typedInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendTextMessage(typedInput.value);
                typedInput.value = '';
            }
        });
        langSelect.addEventListener('change', loadVoices);
    </script>
</body>
</html>
"""
