import os
import logging
import requests


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('openshockclock.log')
    ]
)
logger = logging.getLogger(__name__)

# Add error logging if any environment variable is missing and exit if any are missing after spitting out all errors
def load_env():
    logger.debug("Loading environment variables")
    api_key = os.getenv('SHOCK_API_KEY')
    if not api_key:
        logger.error("Missing SHOCK_API_KEY environment variable")
        exit(1)
    else:
        logger.debug(f"Loaded API key: {'*' * len(api_key)}")
    
    shock_id = os.getenv('SHOCK_ID')
    if not shock_id:
        logger.error("Missing SHOCK_ID environment variable")
        exit(1)
    else:
        logger.debug(f"Loaded Shock ID: {'*' * 8 + shock_id[8:]}")
    
    intensity = os.getenv('INTENSITY')
    if not intensity:
        logger.error("Missing INTENSITY environment variable")
        exit(1)
    else:
        try:
            intensity = int(intensity)
            if not (0 <= intensity <= 100):
                raise ValueError
        except (TypeError, ValueError):
            logger.error("INTENSITY must be an integer between 0 and 100")
            exit(1)
        logger.debug(f"Loaded Intensity: {intensity}")
    
    duration = os.getenv('DURATION')
    if not duration:
        logger.error("Missing DURATION environment variable")
        exit(1)
    else:
        try:
            duration = int(duration)
            if duration <= 0:
                raise ValueError
        except (TypeError, ValueError):
            logger.error("DURATION must be a positive integer")
            exit(1)
        logger.debug(f"Loaded Duration: {duration}")
    
    vibrate_before = os.getenv('VIBRATE_BEFORE')
    if not vibrate_before:
        logger.error("Missing VIBRATE_BEFORE environment variable")
        exit(1)
    else:
        try:
            vibrate_before = vibrate_before.lower() in ['true', '1', 'yes']
        except ValueError:
            logger.error("VIBRATE_BEFORE must be a boolean (true/false)")
            exit(1)
        logger.debug(f"Loaded Vibrate Before: {vibrate_before}")
    
    return api_key, shock_id, intensity, duration, vibrate_before

def trigger_shock(api_key, shock_id, intensity, duration, vibrate=False):
    logger.debug(f"Triggering shock")
    url = "https://api.shocklink.net/2/shockers/control"
    headers = {
        "accept": "application/json",
        "OpenShockToken": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "shocks": [{
            "id": shock_id,
            "type": "Vibrate" if vibrate else "Shock",
            "intensity": intensity,
            "duration": duration,
            "exclusive": True
        }],
        "customName": "OpenShockClock"
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.debug(f"Shock API response: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to trigger shock: {str(e)}")
        return False

class OpenShockClock():
    def __init__(self):
        super().__init__()
        self.api_key, self.shock_id, self.intensity, self.duration, self.vibrate_before = load_env()
        logger.debug("OpenShockClock started")

    def trigger_alarm(self):
        if self.vibrate_before:
            logger.debug(f"Triggering vibration warning for alarm at intensity 100 for 10 seconds")
            vibration_data = {
                "shocks": [{
                    "id": self.shock_id,
                    "type": "Vibrate",
                    "intensity": 100,
                    "duration": 10000,
                    "exclusive": True
                }],
                "customName": "OpenShockClock - Vibration Warning"
            }

            try:
                response = requests.post(
                    "https://api.shocklink.net/2/shockers/control",
                    headers={
                        "accept": "application/json",
                        "OpenShockToken": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=vibration_data
                )
                response.raise_for_status()
                logger.debug(f"Vibration warning API response: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to trigger vibration warning: {str(e)}")

        logger.debug(f"Triggering alarm")
        trigger_shock(self.api_key, self.shock_id, self.intensity, self.duration)

        return True

if __name__ == "__main__":
    app = OpenShockClock()
    app.trigger_alarm()