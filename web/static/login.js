document.addEventListener('DOMContentLoaded', () => {
    let supabase;
    const loginForm = document.getElementById('login-form');
    const emailInput = document.getElementById('email-input');
    const authMessage = document.getElementById('auth-message');

    const initializeSupabase = async () => {
        const response = await fetch('/config');
        const config = await response.json();
        supabase = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = emailInput.value;
            authMessage.textContent = 'Sending magic link...';
            const { error } = await supabase.auth.signInWithOtp({
                email: email,
            });

            if (error) {
                authMessage.textContent = `Error: ${error.message}`;
            } else {
                authMessage.textContent = 'Check your email for the magic link!';
                loginForm.style.display = 'none';
            }
        });

        supabase.auth.onAuthStateChange((event, session) => {
            if (session && session.user) {
                window.location.href = '/app';
            }
        });
    };

    initializeSupabase();
});