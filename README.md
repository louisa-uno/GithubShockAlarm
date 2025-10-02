### GithubShockAlarm

A shock alarm clock using OpenShock and GitHub Actions.

### Usage

Set the following GitHub Actions secrets:

-   SHOCK_API_KEY # Get it from https://openshock.app/#/dashboard/tokens
-   SHOCK_ID # Get it from https://openshock.app/#/dashboard/shockers/own
-   INTENSITY # Integer between 1 and 100
-   DURATION # Integer Integer between 1 and 30 (seconds)
-   VIBRATE_BEFORE # Boolean (true/false) whether to vibrate before the shock

Then edit the cron schedule in `.github/workflows/trigger-alarm.yml` to have the alarm triggered at your desired time.

You can also trigger the alarm manually via the "Run workflow" button in the "Actions" tab.

It should trigger automatically to your liking without any further interaction. Be aware that the GitHub Actions runner is in the US, so the time zone difference might affect the timing of the alarm.
