document.addEventListener('DOMContentLoaded', () => {
    let supabase;
    const userEmail = document.getElementById('user-email');
    const micSelector = document.getElementById('mic-selector');
    const logoutBtn = document.getElementById('logout-btn');

    const initializeSupabase = async () => {
        const response = await fetch('/config');
        const config = await response.json();
        supabase = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);
        checkUserSession();
    };

    const checkUserSession = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
            window.location.href = '/login';
        } else {
            if (userEmail) {
                userEmail.textContent = session.user.email;
            }
            populateMicrophoneSelector();
        }
    };

    const populateMicrophoneSelector = async () => {
        if (!micSelector) return;

        try {
            // Request permission to access media devices
            await navigator.mediaDevices.getUserMedia({ audio: true });

            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioInputDevices = devices.filter(device => device.kind === 'audioinput');

            micSelector.innerHTML = ''; // Clear existing options

            if (audioInputDevices.length === 0) {
                micSelector.add(new Option('No microphones found', ''));
                micSelector.disabled = true;
                return;
            }

            audioInputDevices.forEach(device => {
                const option = new Option(device.label || `Microphone ${micSelector.options.length + 1}`, device.deviceId);
                micSelector.add(option);
            });

            const savedMic = localStorage.getItem('selectedMicrophone');
            if (savedMic) {
                micSelector.value = savedMic;
            }

            micSelector.disabled = false;
        } catch (err) {
            console.error('Error enumerating audio devices:', err);
            micSelector.add(new Option('Could not access microphones', ''));
            micSelector.disabled = true;
        }
    };

    if (micSelector) {
        micSelector.addEventListener('change', () => {
            localStorage.setItem('selectedMicrophone', micSelector.value);
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (supabase) {
                const { error } = await supabase.auth.signOut();
                if (error) {
                    console.error('Error logging out:', error);
                } else {
                    window.location.href = '/login';
                }
            }
        });
    }

    initializeSupabase();
});