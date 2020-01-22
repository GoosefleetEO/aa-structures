# Structures for Alliance Auth

This is a plugin app for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) (AA) that adds support for structures

## Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Updating](#updating)
- [Settings](#settings)
- [Permissions](#permissions)
- [Service monitoring](#service-monitoring)
- [Change Log](CHANGELOG.md)

## Overview

This app add support for structures to Alliance Auth. It's main purpose is to make it easier for corporations and alliances to manage and operate their structures.

## Features

Alliance Structures adds the following features to Alliance Auth:

- Detailed list of all structures owned by alliances / corporation showing location, services, fuel status and state
- Access to structure list can be configured based on permissions
- Ability to search and filter in structure list
- Directors can add their corporation to include it's structures
- Structure list is automatically kept up-to-date
- Structure notifications are automatically forwarded to Discord channels as alerts
- Interface for 3rd party monitoring of the services status
- Structures include Upwell structures
- Notification types include structures, moon mining
- Automatically adds timers from relevant notifications to aa-timers app (if installed)
- Self-defined tags help to better organize structures

Planned features:

- Structures include POCOs and POSes
- Notification types include sovereignty, war decs

## Screenshots

Here is an example for the structure browser:

![StructureList](https://i.imgur.com/iusH65e.png)

This is an example for a notification posted on Discord:

![Notification example](https://i.imgur.com/OrJsQfW.png)

## Installation

### 1. Install app

Install into AA virtual environment with PIP install from this repo:

```bash
pip install git+https://gitlab.com/ErikKalkoken/aa-structures.git
```

### 2 Update Eve Online app

Update the Eve Online app used for authentication in your AA installation to include the following scopes:

```plain
esi-characters.read_notifications.v1
esi-corporations.read_structures.v1
esi-universe.read_structures.v1
```

### 3. Configure AA settings

Configure your AA settings (`local.py`) as follows:

- Add `'structures'` to `INSTALLED_APPS`
- Add these lines add to bottom of your settings file:

   ```python
    CELERYBEAT_SCHEDULE['structures_update_all_structures'] = {
        'task': 'structures.tasks.update_all_structures',
        'schedule': crontab(minute='*/30'),
    }
    CELERYBEAT_SCHEDULE['structures_fetch_all_notifications'] = {
        'task': 'structures.tasks.fetch_all_notifications',
        'schedule': crontab(minute='*/5'),
    }
    CELERYBEAT_SCHEDULE['structures_send_all_new_notifications'] = {
        'task': 'structures.tasks.send_all_new_notifications',
        'schedule': crontab(minute='*/1'),
    }
   ```

- Optional: Add additional settings if you want to change any defaults. See [Settings](#settings) for the full list.

> **Recommended celery setup**:<br>The Alliance Structures apps uses celery a lot to constantly refresh data from ESI. We therefore recommend to enable the following additional settings for celery workers to enable logging and to protect against memory leaks:<br>
`-l info --max-memory-per-child 512000`
<br><br>In many setups this config is part of your supervisor configuration.<br>On Ubuntu you can run `systemctl status supervisor` to see where that config file is located. <br><br>Note that you need to restart the supervisor service itself to activate those changes.<br>
e.g. on Ubuntu:<br>`systemctl restart supervisor`

### 4. Finalize installation into AA

Run migrations & copy static files

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for AA

### 5. Setup permissions

Now you can setup permissions in Alliance Auth for your users.

See section [Permissions](#permissions) below for details.

### 6. Setup notifications to Discord

The setup and configuration for Discord webhooks is done on the admin page under **Structures**.

To setup notifications you first need to add the Discord webhook that point to the channel you want notifications to appear to **Webhooks**. We would recommend that you also enable `is_default` for your main webhook, so that newly added structure owners automatically use this webhook. Alternatively you need to manually assign webhooks to existing owners after they have been added (see below).

Finally to verify that your webhook is correctly setup you can send a test notification. This is one of the available actions on Webhooks page.

### 7. Add structure owners

Next you need to add your first structure owner with the character that will be used for fetching structures. Just open the Alliance Structures app and click on "Add Structure Owner". Note that only users with the appropriate permission will be able to see and use this function and that the character needs to be a director.

Once a structure owner is set the app will start fetching the corporation structures and related notifications. Wait a minute and then reload the structure list page to see the result.

You will need to add every corporation as Structure Owner to include their structures and notifications in the app.

Note that as admin you can review all structures and notifications on the admin panel.

## Updating

To update your existing installation of Alliance Structures first enable your virtual environment.

Then run the following commands from your AA project directory (the one that contains `manage.py`).

```bash
pip install git+https://gitlab.com/ErikKalkoken/aa-structures.git -U
```

```bash
python manage.py migrate
```

```bash
python manage.py collectstatic
```

Finally restart your AA supervisor services.

## Settings

Here is a list of available settings for this app. They can be configured by adding them to your AA settings file (`local.py`).

Note that all settings are optional and the app will use the documented default settings if they are not used.

Name | Description | Default
-- | -- | --
`STRUCTURES_ADD_TIMERS`| Whether to automatically add timers for certain notifications on the timerboard (will have no effect if [aa-timerboard](https://allianceauth.readthedocs.io/en/latest/features/timerboard/) app is not installed).<br>Will create timers from anchoring, lost shield and lost armor notifications  | True
`STRUCTURES_FEATURE_CUSTOMS_OFFICES`| Enable / disable custom offices feature | False
`STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES`| Max time in minutes since last successful notification forwarding before service is reported as down  | 5
`STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION`| Defines after how many hours a notification is regarded as stale. Stale notifications are no longer sent automatically. | 24
`STRUCTURES_NOTIFICATION_MAX_RETRIES`| Max number of retries after a HTTP error occurred incl. rate limiting  | 3
`STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES`| Max time in minutes since last successful notifications sync before service is reported as down  | 15
`STRUCTURES_NOTIFICATION_WAIT_SEC`| Default wait time in seconds before retrying after HTTP error (not used for rate limits)  | 5
`STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES`| Max time in minutes since last successful structures sync before service is reported as down  | 120

## Permissions

This is an overview of all permissions used by this app:

Name | Purpose | Code
-- | -- | --
Can access this app and view | User can access the app and see the structure list. He will only be able to see structures belonging to corporations of his characters. We would suggest to enable this permission for the Member state |  `general.basic_access`
Can view alliance structures | User can view all structures belonging to corporation in the alliance of the user. |  `general.view_alliance_structures`
Can view all structures | User can see all structures in the system |  `general.view_all_structures`
Can add new structure owner | User can add a corporation with it's structures |  `general.add_structure_owner`

## Service monitoring

Alliances may want to rely on getting prompt notifications on Discord to keep their assets save. However, an app like Alliance Structures is fully dependant on external services like the Eve API (ESI) to stay operational.

In order stay alliance apprised about any potential service outages, this app has a simple HTTP interface that enables monitoring of it's service status by a 3rd party monitoring application. (e.g. [Uptimerobot](https://www.uptimerobot.com)).

The monitoring route is: `[your AA URL]/structures/service_status/`

Status | Reporting | Condition
-- | -- | --
Up | HTTP 200 and the text `service is up` | Tasks for updating of structures, updating of notifications and forwarding to webhooks have last run within the configured grace period and there are no errors
Down | HTTP 500 and the text `service is down` | Above condition for "up" not met

By default the status of all existing owners will be included in determining the overall status. However, it's also possible to manually exclude owners by setting the property "Is included in service status".
