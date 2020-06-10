# Alliance Structures

App for managing Eve Online structures with
Alliance Auth.

![release](https://img.shields.io/pypi/v/aa-structures?label=release) ![python](https://img.shields.io/pypi/pyversions/aa-structures) ![django](https://img.shields.io/pypi/djversions/aa-structures?label=django) ![pipeline](https://gitlab.com/ErikKalkoken/aa-structures/badges/master/pipeline.svg) ![coverage](https://gitlab.com/ErikKalkoken/aa-structures/badges/master/coverage.svg) ![license](https://img.shields.io/badge/license-MIT-green) ![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

## Contents

- [Overview](#overview)
- [Features Summary](#features-summary)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Updating](#updating)
- [Features](#features)
- [Settings](#settings)
- [Permissions](#permissions)
- [Service monitoring](#service-monitoring)
- [Admin tool](#admin-tools)
- [Change Log](CHANGELOG.md)

## Overview

This app is for managing Eve Online structures with [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) (AA). It allows corporations and alliance to see a current list of all their structures in Auth and also get structure related notification on Discord.

## Features Summary

Alliance Structures adds the following main features to Alliance Auth:

- Structure browser with a detailed list of all structures owned by alliances / corporation, automatically synced with the game server
- Structures include all Upwell structures, Custom Offices and Starbases / POSes
- Automatically forwards structure notifications to Discord channels as alerts
- Notification categories include Upwell Structures, Moon Mining, Customs Offices, Starbases and Sovereignty
- Automatically adds timers from notifications to Alliance Auth timerboard app (if installed)
- Permissions define which structures are visible to a user based on organization membership
- Self-defined tags help to better organize structures
- Interface for 3rd party monitoring of the services status
- Chinese :cn:, English :us: and German :de: localization

*We are looking for help with translating Alliance Structures for more languages incl. French, Korean, Russian, and Spanish. If you are interested please sign up on our [Transifex project](https://www.transifex.com/kalkoken-apps/aa-structures/).*

## Screenshots

Here is an example for the structure browser:

![StructureList](https://i.imgur.com/WtiRap3.png)

This is an example for a notification posted on Discord:

![Notification example](https://i.imgur.com/OrJsQfW.png)

## Installation

**Important**: This app is a plugin for Alliance Auth. If you don't have Alliance Auth running already, please install it first before proceeding. (see the official [AA installation guide](https://allianceauth.readthedocs.io/en/latest/installation/auth/allianceauth/) for details)

### Step 1 - Install app

Make sure you are in the virtual environment (venv) of your Alliance Auth installation. Then install the newest release from PyPI:

```bash
pip install aa-structures
```

### Step 2 - Update Eve Online app

Update the Eve Online app used for authentication in your AA installation to include the following scopes:

```plain
esi-assets.read_corporation_assets.v1
esi-characters.read_notifications.v1
esi-corporations.read_starbases.v1
esi-corporations.read_structures.v1
esi-planets.read_customs_offices.v1
esi-universe.read_structures.v1
```

### Step 3 - Configure AA settings

Configure your AA settings (`local.py`) as follows:

- Add `'structures'` to `INSTALLED_APPS`
- Add below lines to your settings file:

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

### Step 4 - Celery worker configuration

This app uses celery for critical functions like refreshing data from ESI. We strongly recommend to enable the following additional settings for celery workers to enable proper logging and to protect against potential memory leaks:

- To enable logging of celery tasks up to info level: `-l info`

- To automatically restart workers that grow above 256 MB: `--max-memory-per-child 262144`

Here is how an example config would look for workers in your `supervisor conf`:

```plain
command=/home/allianceserver/venv/auth/bin/celery -A myauth worker -l info --max-memory-per-child 262144
```

Note that you need to restart the supervisor service itself to activate these changes.

e.g. on Ubuntu:

```bash
systemctl restart supervisor
```

### Step 5 - Finalize installation into AA

Run migrations & copy static files

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for AA

### Step 6 - Setup permissions

Now you can setup permissions in Alliance Auth for your users.

See section [Permissions](#permissions) below for details.

### Step 7 - Setup notifications to Discord

The setup and configuration for Discord webhooks is done on the admin page under **Structures**.

To setup notifications you first need to add the Discord webhook that point to the channel you want notifications to appear to **Webhooks**. We would recommend that you also enable `is_default` for your main webhook, so that newly added structure owners automatically use this webhook. Alternatively you need to manually assign webhooks to existing owners after they have been added (see below).

Finally to verify that your webhook is correctly setup you can send a test notification. This is one of the available actions on Webhooks page.

### Step 8 - Add structure owners

Next you need to add your first structure owner with the character that will be used for fetching structures. Just open the Alliance Structures app and click on "Add Structure Owner". Note that only users with the appropriate permission will be able to see and use this function and that the character needs to be a director.

Once a structure owner is set the app will start fetching the corporation structures and related notifications. Wait a minute and then reload the structure list page to see the result.

You will need to add every corporation as Structure Owner to include their structures and notifications in the app.

Note that as admin you can review all structures and notifications on the admin panel.

## Updating

To update your existing installation of Alliance Structures first enable your virtual environment.

Then run the following commands from your AA project directory (the one that contains `manage.py`).

```bash
pip install -U aa-structures
```

```bash
python manage.py migrate
```

```bash
python manage.py collectstatic
```

Finally restart your AA supervisor services.

## Features

In this section you find a detailed description of the following key features:

- [Localization](#localization)
- [Notifications](#notifications)
- [Power Modes](#power-modes)
- [Pings](#pings)
- [Structure tags](#structure-tags)
- [Timers](#timers)

### Localization

Alliance Structures has full localization for languages support by Alliance Auth. This chapter describes how to set the language for different parts of the app:

#### UI

To switch the UI to your preferred language simply use the language switcher from Auth.

#### Notifications on Discord

The language for notifications on Discord can be chosen by configuring the language property for the respective Webhook. The default language will be used if no language is configured for a Webhook.

#### Default language

The default language will be used when no specific language have been configured or no language can be determined. The default language can be defined with the setting `STRUCTURES_DEFAULT_LANGUAGE`.

The following parts of the app will use localization with the default language:

- Timers
- Name of Custom Offices

### Notifications

#### Message rendering on Discord

All notification types are classified in into one of four semantic categories. These categories determine the color of the notification on Discord and whether pings are created.

Category | Color | Ping
-- | -- | --
success | green | None
info | blue | None
warning | yellow | @here
danger | red | @everyone

The mapping between notification types and semantic categories is predefined and can at the moment not be individually configured.

But it is possible to turn off pinging for all notifications per webhook and/or per owner on the admin site.

#### Supported notification types

The following Eve Online notification types are currently supported (names are from ESI):

##### Moon Mining

- MoonminingAutomaticFracture
- MoonminingExtractionCancelled
- MoonminingExtractionFinished
- MoonminingExtractionStarted
- MoonminingLaserFired

##### Upwell Structures

- OwnershipTransferred
- StructureAnchoring
- StructureDestroyed
- StructureFuelAlert
- StructureLostArmor
- StructureLostShields
- StructureOnline
- StructureServicesOffline
- StructureUnanchoring
- StructureUnderAttack
- StructureWentHighPower
- StructureWentLowPower

##### POCOs

- OrbitalAttacked
- OrbitalReinforced

##### Starbases

- TowerAlertMsg
- TowerResourceAlertMsg

##### Sovereignty

- EntosisCaptureStarted
- SovAllClaimAquiredMsg
- SovCommandNodeEventStarted
- SovStructureReinforced
- SovStructureDestroyed

### Power Modes

Structures will display the current power mode of an Upwell structure if it can be determined.

Current supported power modes are:

- Full Power
- Low Power
- Abandoned

Note that the power modes are inferred, since ESI does not provide the current power mode of structures. So they may not be 100% accurate.

If it is unclear wether a structure is "Low Power" or "Abandoned", the power mode will be shown as "Abandoned?". This usually happens if a structure already was on "Low Power" before this update has been installed, so the app has no information when it was last online. As mitigation you can manually update the field "last online at" for a structure on the admin site.

### Structure tags

Structure tags are colored text labels that can be attached to individual structures. Their main purpose is to provide an easy way to organize structures. Tags are shown below the name on the structure list and you can filter the structure list by tags.

For example you might be responsible for fueling structures in your alliance and there are a couple structures that you do not need to care about. With structure tags you can just apply a tag like "fueling" to those structures that you need to manage and then filter the structure list to only see those.

There are two kinds of structure tags: Custom tags and generated tags

#### Custom tags

Custom tags are created by users. You can created them on the admin panel under Structure tags, give them any name, color and define its order. Existing structure tags can be assigned to a structure on the structures page within the admin panel.

You can also define custom tags as default. Default tags are automatically added to every newly added structure. Furthermore you enable default tags to be your default tag filter to be active when opening the structure list (see [Settings](#settings))

#### Generated tags

Generated tags are automatically created by and added to structures by the system. These tags are calculated based on properties of a structure. The purpose of generated tags is to provide additional information and filter options for structures in the structure list.

There are currently two types of generated tags:

- space type: Shows which space type the structure is in, e.g. null sec or low sec
- sov: Shows that the owner of that structures has sovereignty in the respective solar system

### Timers

**Alliance Structures** will automatically create friendly timers from  notifications for Alliance Auth's Structure Timers app. This feature can be configured via [Settings](#settings).

Timers can be created from the following notification types:

- OrbitalReinforced
- MoonminingExtractionStarted
- SovStructureReinforced
- StructureAnchoring (excluding structures anchored in null sec)
- StructureLostArmor
- StructureLostShields

## Settings

Here is a list of available settings for this app. They can be configured by adding them to your AA settings file (`local.py`).

Note that all settings are optional and the app will use the documented default settings if they are not used.

Name | Description | Default
-- | -- | --
`STRUCTURES_ADD_TIMERS`| Whether to automatically add timers for certain notifications on the timerboard (will have no effect if [aa-timerboard](https://allianceauth.readthedocs.io/en/latest/features/timerboard/) app is not installed). Will create timers from anchoring, lost shield and lost armor notifications  | True
`STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED`| whether admins will get notifications about import events like when someone adds a structure owner | True
`STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED`| Enable default tags filter for structure list as default | False
`STRUCTURES_DEFAULT_LANGUAGE`| Sets the default language to be used in case no language can be determined. e.g. this language will be used when creating timers. Please use the language codes as defined in the base.py settings file. | en
`STRUCTURES_FEATURE_CUSTOMS_OFFICES`| Enable / disable custom offices feature | True
`STRUCTURES_FEATURE_STARBASES`| Enable / disable starbases feature | True
`STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES`| Max time in minutes since last successful notification forwarding before service is reported as down  | 5
`STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION`| Defines after how many hours a notification is regarded as stale. Stale notifications are no longer sent automatically. | 24
`STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED`| whether to create / remove timers from moon extraction notifications  | True
`STRUCTURES_NOTIFICATION_MAX_RETRIES`| Max number of retries after a HTTP error occurred incl. rate limiting  | 3
`STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES`| Max time in minutes since last successful notifications sync before service is reported as down  | 15
`STRUCTURES_NOTIFICATION_WAIT_SEC`| Default wait time in seconds before retrying after HTTP error (not used for rate limits)  | 5
`STRUCTURES_REPORT_NPC_ATTACKS`| Enable / disable sending notifications for attacks by NPCs (structure reinforcements are still reported) | True
`STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE`| Enable / disable whether fuel expire is shown as relative figure | True
`STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES`| Max time in minutes since last successful structures sync before service is reported as down  | 120
`STRUCTURES_TASKS_TIME_LIMIT`| Hard timeout for tasks in seconds to reduce task accumulation during outages | 7200
`STRUCTURES_TIMERS_ARE_CORP_RESTRICTED`| whether created timers are corp restricted on the timerboard  | False

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

## Admin tools

### Admin site

Most admin tools are accessible on the admin site through actions. e.g. you can sent specific notifications or force a sync with the eve server for an owner.

See the respective actions list on the admin site for details.

### Management commands

Some admin tools are available only as Django management command:

- **structures_purge_all**: This task will purge ALL data of the structures app. Run this command before trying to reverse migrations (e.g. `migrate structures zero` for de-installation) or you will run into foreign key constraints.
- **structures_updatesde**: This command will reload all locally stored Eve Online data from the Eve Online server.
