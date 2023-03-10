# Operations Manual

## Installation

### Step 0 - Prerequisites

1. Structures is a plugin for Alliance Auth. If you don't have Alliance Auth running already, please install it first before proceeding. (see the official [AA installation guide](https://allianceauth.readthedocs.io/en/latest/installation/auth/allianceauth/) for details)

2. Structures needs the app [django-eveuniverse](https://gitlab.com/ErikKalkoken/django-eveuniverse) to function. Please make sure it is installed, before before installing the app.

### Step 1 - Install app

Make sure you are in the virtual environment (venv) of your Alliance Auth installation. Then install the newest release from PyPI:

```bash
pip install aa-structures
```

### Step 2 - Update Eve Online app

Update the Eve Online app used for authentication in your AA installation to include the following scopes:

```text
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
```

- Optional: Add additional settings if you want to change any defaults. See [Settings](#settings) for the full list.

### Step 4 - Celery worker configuration

This app uses celery for critical functions like refreshing data from ESI. We strongly recommend to enable the following additional settings for celery workers to enable proper logging and to protect against potential memory leaks:

- To enable logging of celery tasks up to info level: `-l info`

- To automatically restart workers that grow above 256 MB: `--max-memory-per-child 262144`

Here is how an example config would look for workers in your `supervisor conf`:

```text
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

### Step 6 - Preload Eve Universe data

In order to see structure fits you need to preload some data from ESI once.
If you already have run those commands previously you can skip this step.

Load Eve Online structure types

```bash
python manage.py structures_load_eve
```

### Step 7 - Setup permissions

Now you can setup permissions in Alliance Auth for your users.

See section [Permissions](#permissions) below for details.

### Step 8 - Setup notifications to Discord

The setup and configuration for Discord webhooks is done on the admin page under **Structures**.

To setup notifications you first need to add the Discord webhook that point to the channel you want notifications to appear to **Webhooks**. We would recommend that you also enable `is_default` for your main webhook, so that newly added structure owners automatically use this webhook. Alternatively you need to manually assign webhooks to existing owners after they have been added (see below).

Finally to verify that your webhook is correctly setup you can send a test notification. This is one of the available actions on Webhooks page.

### Step 9 - Add structure owners

Next you need to add your first structure owner with the character that will be used for fetching structures. Just open the Structures app and click on "Add Structure Owner". Note that only users with the appropriate permission will be able to see and use this function and that the character needs to be a director.

Once a structure owner is set the app will start fetching the corporation structures and related notifications. Wait a minute and then reload the structure list page to see the result.

You will need to add every corporation as Structure Owner to include their structures and notifications in the app.

Note that as admin you can review all structures and notifications on the admin panel.

## Updating

To update your existing installation of Structures first enable your virtual environment.

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
- [Structure tags](#structure-tags)
- [Timers](#timers)
- [Multiple sync characters](#multiple-sync-characters)
- [Public customs offices](#public-customs-offices)
- [Fuel alerts](#fuel-alerts)

### Localization

Structures has full localization for languages support by Alliance Auth. This chapter describes how to set the language for different parts of the app:

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

#### Message rendering and pinging on Discord

All notification types are classified in into one of four semantic categories. These categories determine the color of the notification on Discord and whether default pings are created.

Category | Color | Ping
-- | -- | --
success | green | None
info | blue | None
warning | yellow | @here
danger | red | @everyone

The mapping between notification types and semantic categories is predefined and can at the moment not be individually configured.

But it is possible to turn off default pings for all notifications per webhook and/or per owner on the admin site.

#### Group pings

You can also define groups to be pinged for notifications on Discord per webhook and/or per owner. All users belonging to that group will then be receive that ping on Discord if they have access to the respective channel.

Groups defined per webhook will be added to groups defined per owner and group pings are independent from default pings.

Note that you need to have Auth's Discord service enabled for group pings to work.

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

**Structures** will automatically create friendly timers from  notifications for Alliance Auth's Structure Timers app. This feature can be configured via [Settings](#settings).

Timers can be created from the following notification types:

- OrbitalReinforced
- MoonminingExtractionStarted
- SovStructureReinforced
- StructureAnchoring (excluding structures anchored in null sec)
- StructureLostArmor
- StructureLostShields

### Multiple sync characters

It is possible to add multiple sync characters for a structure owner / corporation. This serves two purposes:

- Improved reaction time for notifications
- Improved resilience against character becoming invalid

#### Improved reaction time for notifications

One of the most popular features of Structures is it's ability to automatically forward notifications from the Eve server to Discord. However, there is a significant delay between the time a notification is create in game and it appearing on Discord, which on average is about 10 minutes.

That delay is caused by the API of the Eve Server (ESI), which is caching all notification requests for 10 minutes.

You can reduce the reaction time by adding multiple sync characters for every owner. Structures will automatically rotate through all configured sync characters when updating notifications. Please also remember to reduce the update time of the related periodic task (`structures_fetch_all_notifications`) accordingly. E.g. if you have 5 sync characters you want to run the periodic update task every 1-2 minutes.

Every added sync character will reduce the delay up to a maximum of 10, which brings the average reaction time down to about 1 minute.

#### Improved resilence against character becoming invalid

Another benefit of having multiple sync characters is that it increases the resilience of the update process against failures. E.g. it can happen that a sync character becomes invalid, because it has been moved to another corporation or it's token is no longer valid. If you only have one sync character configured then all updates will stop for the tower until a new character is provided. However, if you have more then one sync character configured, then Structures will ignore the invalid character (but notify admins about it) and use any of the remaining valid characters to complete the update.

#### Measuring notification delay

Structures has the ability to measure the average notification delay of your system. You can find that information on the admin site / owners / [Your owner] / Sync status / Avg. turnaround time. This will show the current average delay in seconds between a notification being created in game and it being received by Structures for the last 5, 15 and 50 notifications.

### Services Monitoring

Many alliances are relying that the structure services - i.e. getting attack and fuel notifications on Discord. However, outages can occur, e.g. when tokens become invalid or the Eve Online API server (ESI) has issues. To give alliances the ability to fix outages quickly, Structures has a build in service monitoring capability. Should an issue occur it will automatically send an Auth notification to admins. When combined with the app [Discord Notify](https://gitlab.com/ErikKalkoken/aa-discordnotify), those notifications will be forwarded immediately to Discord, allowing admins to take quick action to resolve any issues.

There are currently two types of issue related admin notifications:

- Sync character no longer valid
- Services are down

#### Sync character no longer valid

When a character that us used to sync an owner from ESI becomes invalid, it is automatically removed and both the related user and the admins are informed. Characters can become invalid e.g. when the token is no longer valid or the character lost permissions to use Structures.

#### Services are down

In addition Structures is constantly monitoring that all updates from ESI are running. Should a service fail to update within the alloted time the services for that owner will be reported as down and the admins will be notified. Once that service has resumed updating another notification is issued informing the admins that the services for that owner are back up.

> **Hint**<br>You can adjust maximum time since it's last successful sync before a service is reported as down with the [settings](#settings) `STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES` and `STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES`.

### Public Customs Offices

PI can be a lucrative income source, both for alliances and characters. But your alliance mates need to know where your alliances' customs offices are in order to use them. To help you with that you can choose to show the customs offices of any owner on a special page. In addition to the exact location that page will also show the current tax rates and the planet type.

Here is an example:

![example](https://i.imgur.com/5kd20QZ.png)

To enable this feature you need to do 2 things: First, you need to enable the "public" showing of customs offices for an owner. You will find that option on the admin site for Owners:

![Poco options](https://i.imgur.com/BK3MadZ.png)

Second, you need to give your users access to the Structures app with the basic access permission. e.g. by adding that permssion to the Member state. The pages with the full structures list are hidden behind additional permissions. For details please see [permissions](#permissions).

### Fuel Alerts

Structures can generate additional notifications that help keep track of fueling levels for your structures:

- Refueled notification
- Structure fuel alerts
- Jump fuel alerts

All of these notifications can be enabled for webhooks, just like any of the standard notifications from the Eve Server.

>**Note**<br>All notifications are generated based on the structure and asset information that is usually updated hourly from the Eve server due to caching. However, you can get more timely updates by adding multiple characters to your owners. e.g. with 2 characters you get fresh data every 30 minutes.

#### Refueled notification

Refueled notification are generated once a structure has been refueled and will help you coordinate refueling efforts. i.e. when the refueled notification appears in your Discord channel, you know that someone else has taken care of refuelling that particular structures.

Refueled notifications are available for Upwell structures and POSes, however the POS version is currently experimental.

To enable getting refueled notifications you need to activate this feature with a setting:

```python
STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS = True
```

#### Structure fuel alerts

Structure fuel alerts can be configured to provide additional alert notification about low fuel levels of your structures. They are highly customizable to accommodate all kinds of use cases. You can configure one ore multiple structure fuel alerts. All configuration is done through the admin site.

Here is an example:

_First configuration_

When fuel is down to 3 days, send a warning notification every 12 hours. For this the configuration would be:

- start: 72
- end: 24
- intervall: 12
- channel pings: @here
- color: warning

_Second configuration_

When fuel is down to 24 hours, send a danger notification every 6 hours and ping everybody. For this the configuration would be:

- start: 24
- end: 0
- interval: 6
- channel pings: @everyone
- color: danger

#### Jump fuel alerts

Jump fuel alerts are similar to structure fuel alerts, but made specifically to deal with Liquid Ozone levels of jump gates. They have many of the same customization options and you also configure them on the admin site. They are triggered by the current fuel level measured in units of Liquid Ozone in a jump gate.

## Settings

Here is a list of available settings for this app. They can be configured by adding them to your AA settings file (`local.py`).

Note that all settings are optional and the app will use the documented default settings if they are not used.

Name | Description | Default
-- | -- | --
`STRUCTURES_ADD_TIMERS`| Whether to automatically add timers for certain notifications on the timerboard (will have no effect if [aa-timerboard](https://allianceauth.readthedocs.io/en/latest/features/timerboard/) app is not installed). Will create timers from anchoring, lost shield and lost armor notifications  | `True`
`STRUCTURES_ADMIN_NOTIFICATIONS_ENABLED`| Whether admins will get notifications about import events like when someone adds a structure owner and when services for an owner are down. | `True`
`STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED`| Enable default tags filter for structure list as default | `False`
`STRUCTURES_DEFAULT_LANGUAGE`| Sets the default language to be used in case no language can be determined. e.g. this language will be used when creating timers. Please use the language codes as defined in the base.py settings file. | `en`
`STRUCTURES_DEFAULT_PAGE_LENGTH`| Default page size for structure list. Must be an integer value from the available options in the app. | `10`
`STRUCTURES_ESI_DIRECTOR_ERROR_MAX_RETRIES`| Max retries before a character is deleted when ESI claims the character is not a director (Since this sometimes is reported wrongly by ESI). | `3`
`STRUCTURES_FEATURE_CUSTOMS_OFFICES`| Enable / disable custom offices feature | `True`
`STRUCTURES_FEATURE_STARBASES`| Enable / disable starbases feature | `True`
`STRUCTURES_FEATURE_REFUELED_NOTIFICATIONS`| Enable / disable refueled notifications feature | `False`
`STRUCTURES_HOURS_UNTIL_STALE_NOTIFICATION`| Defines after how many hours a notification is regarded as stale. Stale notifications are no longer sent automatically. | `24`
`STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED`| whether to create / remove timers from moon extraction notifications  | `True`
`STRUCTURES_NOTIFICATION_DISABLE_ESI_FUEL_ALERTS`| This allows you to turn off ESI fuel alert notifications to use the Structure's generated fuel notifications exclusively.  | `False`
`STRUCTURES_NOTIFICATION_MAX_RETRIES`| Max number of retries after a HTTP error occurred incl. rate limiting  | `3`
`STRUCTURES_NOTIFICATION_SET_AVATAR`| Wether structures sets the name and avatar icon of a webhook. When `False` the webhook will use it's own values as set on the platform | `True`
`STRUCTURES_NOTIFICATION_SHOW_MOON_ORE`| Wether ore details are shown on moon notifications | `True`
`STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES`| Max time in minutes since last successful notifications sync before service is reported as down  | `40`
`STRUCTURES_NOTIFICATION_WAIT_SEC`| Default wait time in seconds before retrying after HTTP error (not used for rate limits)  | `5`
`STRUCTURES_PAGING_ENABLED`| Wether paging is enabled for the structure list. | `True`
`STRUCTURES_REPORT_NPC_ATTACKS`| Enable / disable sending notifications for attacks by NPCs (structure reinforcements are still reported) | `True`
`STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE`| Enable / disable whether fuel expire is shown as relative figure | `True`
`STRUCTURES_SHOW_JUMP_GATES`| Whether to show the jump gates tab | `True`
`STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES`| Max time in minutes since last successful structures sync before service is reported as down  | `120`
`STRUCTURES_TASKS_TIME_LIMIT`| Hard timeout for tasks in seconds to reduce task accumulation during outages | `7200`
`STRUCTURES_TIMERS_ARE_CORP_RESTRICTED`| whether created timers are corp restricted on the timerboard  | `False`

## Permissions

This is an overview of all permissions used by this app. Note that all permissions are in the "general" section.

Name | Purpose | Code
-- | -- | --
Can access public views | User can access this app and view public pages, e.g. public POCO view |  <https://i.imgur.com/BK3MadZ.png>
Can view corporation structures | User can see structures belonging to corporations of his characters only. |  `general.view_corporation_structures`
Can view alliance structures | User can view all structures belonging to corporation in the alliance of the user. |  `general.view_alliance_structures`
Can view all structures | User can see all structures in the system |  `general.view_all_structures`
Can add new structure owner | User can add a corporation with it's structures |  `general.add_structure_owner`
Can view unanchoring timers for all structures the user can see | User can view unanchoring timers for all structures the user can see based on other permissions |  `general.view_all_unanchoring_status`
Can view structure fittings | User can view structure fittings |  `general.view_structure_fittings`

## Service monitoring

Alliances may want to rely on getting prompt notifications on Discord to keep their assets save. However, an app like Structures is fully dependant on external services like the Eve API (ESI) to stay operational.

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

- **structures_load_eve**: Preload static eve objects from ESI to speed up the app
