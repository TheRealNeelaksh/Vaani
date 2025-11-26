
import os
import json
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import logging
import pkg_resources

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_environment_variables():
    """Check for the presence of required environment variables."""
    required_keys = [
        "SUPABASE_URL", "SUPABASE_ANON_KEY", "MISTRAL_API_KEY",
        "SARVAM_API_KEY", "ELEVENLABS_API_KEY"
    ]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        return f"Missing environment variables: {', '.join(missing_keys)}"
    return None

def check_supabase_connection():
    """Verify the connection to Supabase and authentication."""
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
        if not supabase_url or not supabase_key:
            return "Supabase URL or Key is not configured."

        supabase: Client = create_client(supabase_url, supabase_key)
        # Attempt a simple query to check the connection
        response = supabase.table('users').select('id').limit(1).execute()

        # Check if the response indicates an issue (though this may not cover all auth errors)
        if hasattr(response, 'error') and response.error:
            logging.error(f"Supabase connection error: {response.error.message}")
            return f"Supabase connection failed: {response.error.message}"

        return None
    except Exception as e:
        logging.error(f"Exception during Supabase check: {e}")
        return f"An exception occurred while connecting to Supabase: {e}"

def check_required_files():
    """Check for the presence of essential project files."""
    required_files = [
        "server.py", "requirements.txt",
        "web/templates/index.html", "web/static/script.js",
        "vad_model/silero-vad-master/hubconf.py"
    ]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        return f"Missing required files: {', '.join(missing_files)}"
    return None

def check_elevenlabs_credits():
    """Check the remaining character credits for the ElevenLabs API."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return "ElevenLabs API key is missing."

    try:
        url = "https://api.elevenlabs.io/v1/user"
        headers = {"xi-api-key": api_key}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        user_data = response.json()
        subscription = user_data.get("subscription", {})
        character_count = subscription.get("character_count", 0)
        character_limit = subscription.get("character_limit", 0)

        if character_count >= character_limit:
            return f"ElevenLabs credits are exhausted. Used: {character_count}/{character_limit}"

        return None
    except requests.RequestException as e:
        logging.error(f"Could not connect to ElevenLabs API: {e}")
        return f"Failed to connect to ElevenLabs API: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred during ElevenLabs check: {e}")
        return f"An unexpected error occurred while checking ElevenLabs credits: {e}"

def check_requirements():
    """Check if all packages from requirements.txt are installed."""
    try:
        with open('requirements.txt', 'r') as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        missing_packages = []
        for req in requirements:
            try:
                pkg_resources.require(req)
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
                missing_packages.append(str(e))

        if missing_packages:
            return f"Missing or conflicting packages: {', '.join(missing_packages)}"

        return None
    except FileNotFoundError:
        return "requirements.txt not found."
    except Exception as e:
        logging.error(f"An unexpected error occurred during requirements check: {e}")
        return f"An unexpected error occurred while checking requirements: {e}"

def run_health_check():
    """Run all health checks and return a dictionary of results."""
    load_dotenv()

    checks = {
        "Environment Variables": check_environment_variables(),
        "Supabase Connection": check_supabase_connection(),
        "Required Files": check_required_files(),
        "ElevenLabs Credits": check_elevenlabs_credits(),
        "Python Packages": check_requirements(),
    }

    # Filter out checks that passed (returned None)
    failures = {key: value for key, value in checks.items() if value is not None}

    if not failures:
        logging.info("All health checks passed successfully.")
        return {"status": "ok", "errors": {}}
    else:
        logging.warning("Health check failed with the following errors:")
        for key, value in failures.items():
            logging.warning(f"- {key}: {value}")
        return {"status": "error", "errors": failures}

def main():
    """Main function to run the health check and save results to a file."""
    results = run_health_check()

    # Ensure the 'logs' directory exists
    os.makedirs("logs", exist_ok=True)

    # Save results to a JSON file
    with open("logs/health_check_results.json", "w") as f:
        json.dump(results, f, indent=4)

    logging.info("Health check results saved to logs/health_check_results.json")

if __name__ == "__main__":
    main()
