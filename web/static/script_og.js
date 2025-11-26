document.addEventListener('DOMContentLoaded', () => {
    // Screen elements
    const contactScreen = document.getElementById('contact-screen');
    const loadingScreen = document.getElementById('loading-screen');
    const callScreen = document.getElementById('call-screen');
    const screens = [contactScreen, loadingScreen, callScreen];

    // Button elements
    const calltaaraBtn = document.getElementById('call-taara');
    const callveerBtn = document.getElementById('call-veer');
    const endCallBtn = document.getElementById('end-call-btn');
    const unmuteBtn = document.getElementById('unmute-btn');

    // Dynamic text elements
    const loadingText = document.getElementById('loading-text');
    const callName = document.getElementById('call-name');
    const callTimer = document.getElementById('call-timer');

    // variables
    // State variables
    let timerInterval;
    let seconds = 0;
    let isMuted = true;

    // --- Functions ---

    function showScreen(screenToShow) {
        // Hide all screens by removing the 'active' class
        screens.forEach(screen => {
            screen.classList.remove('active');
        });

        // Show the target screen by adding the 'active' class
        screenToShow.classList.add('active');
    }

    function startCall(contact) {
        // 1. Show loading screen
        loadingText.textContent = `Connecting to ${contact}...`;
        showScreen(loadingScreen);

        // 2. Simulate connection delay (2.5 seconds)
        setTimeout(() => {
            // 3. Switch to call screen
            callName.textContent = contact;
            showScreen(callScreen);
            
            // 4. Start the call timer
            startTimer();
        }, 2500);
    }

    function endCall() {
        // 1. Stop the timer
        clearInterval(timerInterval);
        
        // 2. Reset timer and state
        seconds = 0;
        callTimer.textContent = '00:00';
        isMuted = true; // Reset mute state
        updateMuteButton();
        
        // 3. Show contact screen
        showScreen(contactScreen);
    }

    function startTimer() {
        timerInterval = setInterval(() => {
            seconds++;
            const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
            const secs = (seconds % 60).toString().padStart(2, '0');
            callTimer.textContent = `${mins}:${secs}`;
        }, 1000);
    }

    function toggleMute() {
        isMuted = !isMuted;
        updateMuteButton();
    }

    function updateMuteButton() {
        if (isMuted) {
            unmuteBtn.innerHTML = `<i class="fas fa-microphone-slash"></i> Unmute`;
        } else {
            unmuteBtn.innerHTML = `<i class="fas fa-microphone"></i> Mute`;
        }
    }


    // --- Event Listeners ---
    
    calltaaraBtn.addEventListener('click', () => startCall('taara'));
    callveerBtn.addEventListener('click', () => startCall('veer'));
    endCallBtn.addEventListener('click', endCall);
    unmuteBtn.addEventListener('click', toggleMute);

    // --- Initial State ---

    // Initially show the contact screen when the page loads
    showScreen(contactScreen);
});

// web/static/script.js

document.addEventListener('DOMContentLoaded', () => {
    // Screen elements
    const contactScreen = document.getElementById('contact-screen');
    const loadingScreen = document.getElementById('loading-screen');
    const callScreen = document.getElementById('call-screen');
    const screens = [contactScreen, loadingScreen, callScreen];

    // Button elements
    const calltaaraBtn = document.getElementById('call-taara');
    const callveerBtn = document.getElementById('call-veer');
    const endCallBtn = document.getElementById('end-call-btn');
    const unmuteBtn = document.getElementById('unmute-btn'); // We'll use this to control mic sending

    // Dynamic text elements
    const loadingText = document.getElementById('loading-text');
    const callName = document.getElementById('call-name');
    const callTimer = document.getElementById('call-timer');
    const callVisualizer = document.querySelector('.call-visualizer');

    // --- WebRTC & WebSocket State ---
    let socket;
    let audioContext;
    let mediaStream;
    let scriptProcessor;
    let timerInterval;
    let seconds = 0;
    let isMuted = true; // Start muted
    let audioQueue = [];
    let isPlaying = false;

    // --- Functions ---

    function showScreen(screenToShow) {
        screens.forEach(screen => screen.classList.remove('active'));
        screenToShow.classList.add('active');
    }

    async function startCall(contact) {
        loadingText.textContent = `Connecting to ${contact}...`;
        showScreen(loadingScreen);

        try {
            // 1. Initialize WebSocket Connection
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            socket = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

            socket.onopen = () => {
                console.log("WebSocket connection established.");
                // Now that WS is open, setup audio
                setupAudioProcessing();
            };
            
            socket.onclose = () => {
                console.log("WebSocket connection closed.");
                endCall(); // Ensure call ends if server disconnects
            };

            socket.onerror = (error) => {
                console.error("WebSocket Error:", error);
                loadingText.textContent = `Connection failed. Please try again.`;
                setTimeout(() => showScreen(contactScreen), 2000);
            };

            // 2. Handle messages from server
            socket.onmessage = (event) => {
                if (event.data instanceof Blob) {
                    // It's an audio chunk
                    audioQueue.push(event.data);
                    if (!isPlaying) {
                        playNextAudioChunk();
                    }
                } else {
                    // It's a JSON string with text data
                    const message = JSON.parse(event.data);
                    handleTextMessage(message);
                }
            };

            // 3. Switch to call screen
            callName.textContent = contact;
            showScreen(callScreen);
            startTimer();
            // Start unmuted by default when call begins
            isMuted = false;
            updateMuteButton();

        } catch (error) {
            console.error("Error starting call:", error);
            loadingText.textContent = `Error: Could not start call.`;
            setTimeout(() => showScreen(contactScreen), 2000);
        }
    }
    
    function setupAudioProcessing() {
        navigator.mediaDevices.getUserMedia({ audio: {
            sampleRate: 16000, // Must match server's sample rate
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true
        } })
        .then(stream => {
            mediaStream = stream;
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const source = audioContext.createMediaStreamSource(stream);
            
            // 16384 buffer size for ~1 sec of audio at 16kHz
            scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
            
            scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
                if (isMuted || socket.readyState !== WebSocket.OPEN) return;
                
                // Get the raw PCM audio data
                const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);

                // Convert to base64 string to send as text
                const base64Data = btoa(String.fromCharCode.apply(null, new Uint8Array(inputData.buffer)));
                socket.send(base64Data);

                // Visualizer effect
                let sum = inputData.reduce((a, b) => a + Math.abs(b), 0);
                let avg = sum / inputData.length;
                callVisualizer.style.transform = `scale(${1 + avg * 10})`;
            };
            
            source.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination);
        })
        .catch(err => {
            console.error('Error getting media stream:', err);
            alert('Could not access the microphone. Please grant permission and refresh.');
            endCall();
        });
    }

    function handleTextMessage(message) {
        console.log("Received text message:", message);
        if (message.type === 'user_transcript') {
            // Maybe display user's transcript on screen? (Optional)
            console.log("User said:", message.data);
        } else if (message.type === 'ai_text') {
            // Display AI's response text (Optional)
            console.log("AI says:", message.data);
        } else if (message.type === 'tts_end') {
            // This can be used to show the AI is "done" talking
            callVisualizer.style.transform = `scale(1)`;
        }
    }
    
    async function playNextAudioChunk() {
        if (audioQueue.length === 0) {
            isPlaying = false;
            callVisualizer.style.transform = 'scale(1)'; // Reset visualizer when done
            return;
        }

        isPlaying = true;
        const audioBlob = audioQueue.shift();
        const arrayBuffer = await audioBlob.arrayBuffer();

        // Decode and play the audio chunk
        audioContext.decodeAudioData(arrayBuffer, (buffer) => {
            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);
            source.start();
            
            // Pulse the visualizer as AI speaks
            callVisualizer.style.transform = 'scale(1.1)';
            setTimeout(() => { callVisualizer.style.transform = 'scale(1)'; }, 100);

            source.onended = playNextAudioChunk; // Play the next chunk when this one finishes
        }, (error) => {
            console.error('Error decoding audio data:', error);
            playNextAudioChunk(); // Try next chunk even if one fails
        });
    }

    function endCall() {
        // 1. Stop sending/receiving audio
        if (scriptProcessor) {
            scriptProcessor.disconnect();
            scriptProcessor = null;
        }
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }

        // 2. Close WebSocket
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.close();
        }

        // 3. Stop and reset UI
        clearInterval(timerInterval);
        seconds = 0;
        callTimer.textContent = '00:00';
        isMuted = true;
        updateMuteButton();
        showScreen(contactScreen);

        // 4. Clear audio queue
        audioQueue = [];
        isPlaying = false;
    }

    function startTimer() {
        timerInterval = setInterval(() => {
            seconds++;
            const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
            const secs = (seconds % 60).toString().padStart(2, '0');
            callTimer.textContent = `${mins}:${secs}`;
        }, 1000);
    }

    function toggleMute() {
        isMuted = !isMuted;
        updateMuteButton();
    }

    function updateMuteButton() {
        if (isMuted) {
            unmuteBtn.innerHTML = `<i class="fas fa-microphone-slash"></i> Unmute`;
        } else {
            unmuteBtn.innerHTML = `<i class="fas fa-microphone"></i> Mute`;
        }
    }

    // --- Event Listeners ---
    calltaaraBtn.addEventListener('click', () => startCall('taara'));
    callveerBtn.addEventListener('click', () => startCall('veer'));
    endCallBtn.addEventListener('click', endCall);
    unmuteBtn.addEventListener('click', toggleMute);

    // --- Initial State ---
    showScreen(contactScreen);
});