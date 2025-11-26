document.addEventListener('DOMContentLoaded', () => {
    // --- THEME SWITCHER LOGIC ---
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;

    const applySavedTheme = () => {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            body.dataset.theme = 'dark';
            themeToggle.checked = true;
        } else {
            body.dataset.theme = 'light';
            themeToggle.checked = false;
        }
    };

    themeToggle.addEventListener('change', () => {
        if (themeToggle.checked) {
            body.dataset.theme = 'dark';
            localStorage.setItem('theme', 'dark');
        } else {
            body.dataset.theme = 'light';
            localStorage.setItem('theme', 'light');
        }
    });
    applySavedTheme();

    // --- MAIN APPLICATION UI ELEMENTS ---
    const accessTaaraBtn = document.querySelector('.access-button[data-model="Taara"]');
    const accessVeerBtn = document.querySelector('.access-button[data-model="Veer"]');
    const endCallBtn = document.getElementById('end-call-btn');
    const goBackBtn = document.getElementById('go-back-btn');
    const muteBtn = document.getElementById('mute-btn');
    const chatLog = document.getElementById('chat-log');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const callName = document.getElementById('call-name');
    const callTimer = document.getElementById('call-timer');
    const modeIndicator = document.getElementById('mode-indicator');
    const allGifs = {
        listening: document.getElementById('status-listening'),
        processing: document.getElementById('status-processing'),
        speaking: document.getElementById('status-speaking'),
        muted: document.getElementById('status-muted')
    };
    const callerTune = document.getElementById('caller-tune');
    const connectionChime = document.getElementById('connection-chime');
    const typingSound = document.getElementById('typing-sound');

    // State variables
    let socket;
    let audioContext, workletNode, mediaStream;
    let timerInterval, seconds = 0;
    let mediaSource, sourceBuffer, audioElement;
    let audioQueue = [], isAppending = false;
    let isAiSpeaking = false, isMuted = false;
    let currentAiMessageElement = null;

    // --- SCREEN MANAGEMENT LOGIC ---
    if (document.getElementById('model-select-screen').classList.contains('active')) {
        body.classList.add('selection-view');
    }
    
    const showScreen = (screenId) => {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        document.getElementById(screenId).classList.add('active');
        if (screenId === 'model-select-screen') {
            body.classList.add('selection-view');
        } else {
            body.classList.remove('selection-view');
        }
    };

    const updateStatusIndicator = (state) => {
        if (isMuted && state !== 'idle') { state = 'muted'; }
        Object.values(allGifs).forEach(gif => gif.classList.remove('active'));
        if (allGifs[state]) allGifs[state].classList.add('active');
    };

    const addMessageToChatLog = (sender, text) => {
        const messageBubble = document.createElement('div');
        messageBubble.className = `message-bubble ${sender}-message`;
        messageBubble.textContent = text;
        chatLog.appendChild(messageBubble);
        chatLog.scrollTop = chatLog.scrollHeight;
        return messageBubble;
    };

    const startCall = async (contact) => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session && !window.location.pathname.endsWith('/app')) {
            window.location.href = '/login';
            return;
        }

        chatLog.innerHTML = '';
        isMuted = false;
        showScreen('loading-screen');
        document.getElementById('loading-text').textContent = `Connecting to ${contact}...`;
        callerTune.play().catch(e => console.error("Caller tune failed to play:", e));
        const randomDelay = Math.random() * 4000 + 1000;

        setTimeout(() => {
            callerTune.pause();
            callerTune.currentTime = 0;
            connectionChime.play().catch(e => console.error("Chime failed to play:", e));
            try {
                setupAudioPlayback();
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const token = session.access_token;
                const wsUrl = `${wsProtocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}&character=${contact}`;
                socket = new WebSocket(wsUrl);
                
                socket.onopen = () => {
                    setupAudioProcessing();
                    callName.textContent = contact;
                    showScreen('call-screen');
                    startTimer();
                    updateMuteButton();
                    updateChatInputState();
                    updateStatusIndicator('listening');
                    setTimeout(() => { addMessageToChatLog('ai', "I'm connected! By default, we're in VOICE mode. Just start talking! To switch to TEXT mode, press the Mute button."); }, 500);
                };
                socket.onmessage = handleSocketMessage;
                socket.onclose = (event) => {
                    if (event.code === 4001) { alert("Authentication failed."); }
                    endCall(`Connection closed (code: ${event.code})`);
                };
                socket.onerror = () => endCall('A connection error occurred.');
            } catch (error) {
                endCall('Failed to initialize call.');
            }
        }, randomDelay);
    };
    
    const toggleAgentOrb = (isSpeaking) => {
        const agentOrb = document.getElementById('agent-orb');
        if (agentOrb) {
            if (isSpeaking) {
                agentOrb.classList.add('speaking');
            } else {
                agentOrb.classList.remove('speaking');
            }
        }
    };
    
    const setupAudioProcessing = async () => {
        try {
            const selectedMicId = localStorage.getItem('selectedMicrophone');
            const audioConstraints = {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            };
            if (selectedMicId) {
                audioConstraints.deviceId = { exact: selectedMicId };
            }

            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
            audioContext = new AudioContext({ sampleRate: 16000 });
            await audioContext.audioWorklet.addModule('/static/audio-processor.js');
            workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
            workletNode.port.onmessage = (event) => {
                if (isMuted || isAiSpeaking || audioQueue.length > 0 || socket?.readyState !== WebSocket.OPEN) return;
                
                const audioBuffer = event.data;
                const base64Data = btoa(String.fromCharCode.apply(null, new Uint8Array(audioBuffer)));
                socket.send(JSON.stringify({ type: 'audio_chunk', data: base64Data }));
            };
            const source = audioContext.createMediaStreamSource(mediaStream);
            source.connect(workletNode);
        } catch (err) {
            console.error("Error in setupAudioProcessing:", err);
            let errorMessage = "Could not access microphone.";
            if (err.name === 'OverconstrainedError' || err.name === 'NotFoundError') {
                errorMessage = "Selected microphone not found. Please select another from the account page.";
            }
            endCall(errorMessage);
        }
    };

    function setupAudioPlayback() {
        audioElement = new Audio();
        mediaSource = new MediaSource();
        audioElement.src = URL.createObjectURL(mediaSource);
        mediaSource.addEventListener('sourceopen', () => {
            const mimeCodec = 'audio/mpeg';
            if (MediaSource.isTypeSupported(mimeCodec)) {
                sourceBuffer = mediaSource.addSourceBuffer(mimeCodec);
                sourceBuffer.addEventListener('updateend', () => { isAppending = false; processAudioQueue(); });
            }
        });
    }

    function processAudioQueue() {
        if (isAppending || audioQueue.length === 0 || !sourceBuffer || sourceBuffer.updating) return;
        isAppending = true;
        const audioChunk = audioQueue.shift();
        sourceBuffer.appendBuffer(audioChunk);
    }

    function handleSocketMessage(event) {
        if (event.data instanceof Blob) {
            if (audioElement.paused) { audioElement.play().catch(e => console.error("Audio play failed:", e)); }
            const reader = new FileReader();
            reader.onload = function() { audioQueue.push(reader.result); processAudioQueue(); };
            reader.readAsArrayBuffer(event.data);
        } else {
            const msg = JSON.parse(event.data);
            if (msg.type === 'user_transcript') {
                addMessageToChatLog('user', msg.data);
                currentAiMessageElement = null;
                updateStatusIndicator('processing');
            } else if (msg.type === 'ai_text_chunk') {
                if (!currentAiMessageElement) { 
                    currentAiMessageElement = addMessageToChatLog('ai', msg.data);
                    if (isMuted) {
                        typingSound.volume = 0.7;
                        typingSound.play().catch(e => console.error("Typing sound failed:", e));
                    }
                } 
                else { currentAiMessageElement.textContent += msg.data; }
                chatLog.scrollTop = chatLog.scrollHeight;
            } else if (msg.type === 'tts_start') {
                isAiSpeaking = true;
                updateStatusIndicator('speaking');
                toggleAgentOrb(true);
            } else if (msg.type === 'tts_end') {
                setTimeout(() => {
                    isAiSpeaking = false;
                    updateStatusIndicator('listening');
                    toggleAgentOrb(false);
                }, 2000); 
            }
        }
    }
    
    const endCall = (reason = 'Call ended.') => {
        callerTune.pause(); callerTune.currentTime = 0;
        connectionChime.pause(); connectionChime.currentTime = 0;
        if (audioElement) { audioElement.pause(); audioElement.src = ''; }
        clearInterval(timerInterval);
        seconds = 0;
        if (workletNode) workletNode.port.close();
        if (mediaStream) mediaStream.getTracks().forEach(track => track.stop());
        if (audioContext && audioContext.state !== 'closed') audioContext.close();
        if (socket && socket.readyState !== WebSocket.CLOSED) socket.close();
        if (audioElement && audioElement.src) URL.revokeObjectURL(audioElement.src);
        audioQueue = []; isAiSpeaking = false;
        showScreen('model-select-screen');
        updateStatusIndicator('idle');
        modeIndicator.classList.remove('visible');
    };

    const startTimer = () => {
        seconds = 0;
        callTimer.textContent = '00:00';
        timerInterval = setInterval(() => {
            seconds++;
            const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
            const secs = String(seconds % 60).padStart(2, '0');
            callTimer.textContent = `${mins}:${secs}`;
        }, 1000);
    };

    const updateMuteButton = () => {
        if (isMuted) {
            muteBtn.innerHTML = `<i class="fas fa-microphone"></i> Unmute`;
            modeIndicator.textContent = "TEXT MODE";
            modeIndicator.classList.add('visible');
        } else {
            muteBtn.innerHTML = `<i class="fas fa-microphone-slash"></i> Mute`;
            modeIndicator.textContent = "VOICE MODE";
            modeIndicator.classList.add('visible');
            setTimeout(() => { modeIndicator.classList.remove('visible'); }, 2000);
        }
    };
    
    const toggleMute = () => {
        isMuted = !isMuted;
        updateMuteButton();
        updateChatInputState();
        updateStatusIndicator(isAiSpeaking ? 'speaking' : 'listening');
    };
    
    const updateChatInputState = () => {
        if (isMuted) {
            chatForm.classList.remove('disabled');
            chatInput.placeholder = "Type your message...";
        } else {
            chatForm.classList.add('disabled');
            chatInput.placeholder = "Mute the call to type a message...";
        }
    };

    const handleTextMessageSubmit = (event) => {
        event.preventDefault();
        const text = chatInput.value.trim();
        if (text && socket && socket.readyState === WebSocket.OPEN) {
            addMessageToChatLog('user', text);
            socket.send(JSON.stringify({ type: 'text_message', data: text }));
            chatInput.value = '';
            currentAiMessageElement = null;
            updateStatusIndicator('processing');
        }
    };
    
    // --- AUTH LOGIC ---
    let supabase;
    const loginButtons = document.querySelectorAll('.login-btn');

    const handleLogout = async () => {
        const { error } = await supabase.auth.signOut();
        if (error) {
            console.error('Error logging out:', error);
        }
    };

    const updateUserNav = (user) => {
        loginButtons.forEach(button => {
            if (user) {
                button.textContent = 'Account';
                button.onclick = () => window.location.href = '/account';
            } else {
                button.textContent = 'Log in';
                button.onclick = () => window.location.href = '/login';
            }
        });
    };

    const runHealthCheck = async () => {
        try {
            const response = await fetch('/health-check');
            const result = await response.json();

            if (result.status === 'error' && Object.keys(result.errors).length > 0) {
                const modal = document.getElementById('health-check-modal');
                const errorsContainer = document.getElementById('health-check-errors');
                errorsContainer.innerHTML = '';

                for (const [key, value] of Object.entries(result.errors)) {
                    const errorElement = document.createElement('p');
                    errorElement.innerHTML = `<strong>${key}:</strong> ${value}`;
                    errorsContainer.appendChild(errorElement);
                }

                modal.style.display = 'flex';

                const retryBtn = document.getElementById('retry-health-check');
                const skipBtn = document.getElementById('skip-health-check');

                retryBtn.onclick = () => {
                    modal.style.display = 'none';
                    runHealthCheck();
                };

                skipBtn.onclick = () => {
                    modal.style.display = 'none';
                };
            }
        } catch (error) {
            console.error('Health check failed:', error);
            const modal = document.getElementById('health-check-modal');
            const errorsContainer = document.getElementById('health-check-errors');
            errorsContainer.innerHTML = '<p>Could not run the health check. Please try again later.</p>';
            modal.style.display = 'flex';
        }
    };

    const initializeApp = async () => {
        await runHealthCheck();
        const response = await fetch('/config');
        const config = await response.json();
        supabase = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);

        supabase.auth.onAuthStateChange((_event, session) => {
            updateUserNav(session?.user);
        });

        const { data: { session } } = await supabase.auth.getSession();
        updateUserNav(session?.user);
        initializeUI();
    };

    const initializeUI = () => {
        const accessTaaraBtn = document.querySelector('.access-button[data-model="Taara"]');
        const accessVeerBtn = document.querySelector('.access-button[data-model="Veer"]');
        const endCallBtn = document.getElementById('end-call-btn');
        const goBackBtn = document.getElementById('go-back-btn');
        const muteBtn = document.getElementById('mute-btn');
        const chatForm = document.getElementById('chat-form');

        if (accessTaaraBtn) accessTaaraBtn.addEventListener('click', () => startCall('Taara'));
        if (accessVeerBtn) accessVeerBtn.addEventListener('click', () => startCall('Veer'));
        if (goBackBtn) goBackBtn.addEventListener('click', () => showScreen('model-select-screen'));
        if (endCallBtn) endCallBtn.addEventListener('click', () => endCall());
        if (muteBtn) muteBtn.addEventListener('click', toggleMute);
        if (chatForm) chatForm.addEventListener('submit', handleTextMessageSubmit);
    };

    initializeApp();
});