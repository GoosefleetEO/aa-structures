# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## [Unreleased] - yyyy-mm-dd
With this release, django-eveuniverse is a dependency and requires you to run once this command on upgrade.

run the command to load structures and thier dogmas
```
python manage.py structures_load_structures
```

### Added
- Structure Fits
- New config is required is the local.py
- New permission for structure fits

Name | Purpose | Code
-- | -- | --
Can view structure fittings | User can view structure fittings |  `general.view_structure_fittings`

### Changed
- New dependency to django-eveuniverse

## Changed

## [1.9.4] - 2021-04-13

- Show moon location of refineries if known in all related notifications

## [1.9.3] - 2021-04-01

## Fixed

- Poco List breaks when poco has no planet. ([#48](https://gitlab.com/ErikKalkoken/aa-structures/issues/48))

## [1.9.2] - 2021-03-31

## Fixed

- Will now set names of customs offices to blank if planet matching fails. ([#48](https://gitlab.com/ErikKalkoken/aa-structures/issues/48))

## [1.9.1] - 2021-03-24

## Changed

- Will now automatically update the moon for refineries based on respective moon notifications

## [1.9.0] - 2021-03-16

> **Important update notes**:<br>There has been an important change in the permission system. The `basic_access` permission no longer gives access to viewing structures from one's own corporation. Users now need the new permission `view_corporation_structures` for that. Please make sure to add that new permissions after installing this update where applicable (e.g. to Member state).

## Added

- New dedicated tab showing all customs offices, meant for public consumption
- New permission for viewing corporation structures
- Notification types for characters applying to join a corp: `CorpAppNewMsg`, `CorpAppInvitedMsg`, `CorpAppRejectCustomMsg`, `CharAppWithdrawMsg`

## Changed

- `basic_access` no longer gives access to viewing structures from one's own corporation. Users now need the new permission `view_corporation_structures` for that.
- Removed anchoring time for structure anchoring notifications
- Removed timer creation for structure anchoring notifications

## [1.8.1] - 2021-03-01

## Changed

- Reduce vulnerability for transaction timeouts
- Improve performance of notification updates

## [1.8.0] - 2021-02-20

**Big Notifications Update**

> ⚠️ **Important update note:** This update will remove configured notification types from all webhooks and thereby effectively suspends notification sending. Please make sure to go through all your webhooks and re-configure the notification types to re-enable sending after updating.

> ⚠️ **Users of 1.8.0a3 only:** In case you have installed the alpha version **1.8.0a3** it is critical that you migrate down to migration 0017 **before** installing and applying any higher version. If you did not install this particular alpha version please ignore this note. You can migrate down with `python manage.py migrate structures 0017`. Should you get the error `Data too long for column 'notification_types'` please delete all your webhooks and then try to migrate down again.

### Added

- Notifications for characters joined & left a corporation: `CharAppAcceptMsg`, `CharLeftCorpMsg`
- Notifications for sov: `SovAllClaimLostMsg`
- Notifications for upwell structures: `StructuresReinforcementChanged`
- Notifications for wars: `AllyJoinedWarAggressorMsg`, `AllyJoinedWarAllyMsg`, `AllyJoinedWarDefenderMsg`, `CorpBecameWarEligible`, `CorpNoLongerWarEligible`, `CorpWarSurrenderMsg`, `WarAdopted`, `WarDeclared`, `WarInherited`, `WarRetractedByConcord`
- Direct link to open Structures Auth page from every notification message
- Search bar for owners on admin site

### Changed

- Messages on Discord now show this app as sender instead of the organization of an notification. The organization now appears as author on messages.
- Improved meaning of "is sent" and "is added to timers" for notifications on admin site
- Notification types now described in natural language
- Improved notification architecture to make it easier for adding more notification types
- Moved utils into it's own distribution package: allianceauth-app-utils

## [1.7.0] - 2021-01-10

### Changed

- Users now need to have a permission in order to see when a structure is unanchoring. See the permission section in the README for details.
- Removed support for Django 2

Thank you @OperatorOverload for your contribution!

## [1.6.3] - 2021-01-02

### Changed

- Confirming the start of a management command no longer case sensitive

### Fixed

- Fix bool methods on EveSolarSystem for security type (Thanks @huideaki for reporting this bug)

## [1.6.2] - 2020-10-24

### Changed

- Improved tab styling
- Remove Django 3.0 from test matrix

### Fixed

- Side menu highlighting now works correctly

Thanks to Peter Pfeufer for the contribution!

## [1.6.1] - 2020-10-22

### Fixed

- has_add_permission() argument mismatch with Django 3 for inlines
- Notifications not marked as sent when using older redis-simple-mq library ([#40](https://gitlab.com/ErikKalkoken/aa-structures/issues/40))

## [1.6.0] - 2020-09-29

**Faster notifications**

### Update note

With this release Structures no longer needs the scheduled task `structures_send_all_new_notifications`. Please remove it from your settings.
Hint: If you still get warnings in your worker log after removing it, please also remove it from periodic tasks on your admin site.

### Added

- Setting the avatar name and url for webhooks by Structures can be disabled ([#31](https://gitlab.com/ErikKalkoken/aa-structures/issues/31))
- Notification text now mentions which corporation a structure belongs to
- Now shows an error message on the admin site under Owner and Notifications if no webhook is configured for an owner

### Changed

- Reduced the lead time for sending new messages to webhooks (by up to 1 minute quicker)
- Significantly reduced the amount of tasks that are started per hour
- Removed the scheduled task `structures_send_all_new_notifications`
- Removed dependency conflict with Auth regarding Django 3

### Fixed

- Failed to send message when attacker had no alliance
- Did not mark notifications as sent leading to repeated resending of the same notifications ([#38](https://gitlab.com/ErikKalkoken/aa-structures/issues/38))
- Core CI tests had a wrong dependency to django-eveuniverse

## [1.5.4] - 2020-09-07

### Added

- Will now log warnings if no owner is configured to receive alliance wide notifications, e.g. as required for processing sov notifications.
- Is it now possible to active/deactivate multiple owners in bulk
- Admin site now shows in the owner list how many structures and notifications exist for an owner
- Admin site now shows in the owner list if an owner is enabled as alliance main

## [1.5.3] - 2020-09-03

### Fixes

- Wrong owner for Sov Structures in generated timers ([#32](https://gitlab.com/ErikKalkoken/aa-structures/issues/32))

## [1.5.2] - 2020-09-02

### Fixes

- Roll back unintended model change to Webhook

## [1.5.1] - 2020-09-02

### Changed

- Temporary removed support for Chinese (zh), because ESI does not seam to support it anymore and returns 400 bad request. Waiting for resolution to [this ESI issue](https://github.com/esi/esi-issues/issues/1235) for final decision.

## [1.5.0] - 2020-08-24

**Group pings**

### Added

- Added ability to ping groups on Discord with notifications ([#5](https://gitlab.com/ErikKalkoken/aa-structures/issues/5))
- Now shows ore details on moon mining notifications (can be disabled via setting) ([#29](https://gitlab.com/ErikKalkoken/aa-structures/issues/29))

### Changed

- Removed obsolete "reinforce weekday" from database

## [1.4.0] - 2020-08-20

**Structure Timers II**

### Added

- Will now also create timers for [Structure Timers II](https://gitlab.com/ErikKalkoken/aa-structuretimers) if it is installed
- Ability to configure paging for the structure list via settings

### Changed

- Moved "Add Structure Owner" button to the top of the page
- Refreshed UI

### Fixed

- Will no longer create multiple timers for sov notifications

## [1.3.6] - 2020-07-14

### Fixed

- Several minor bugfixes

## [1.3.5] - 2020-07-03

### Added

- This app now works with both the old (1.6.x) and new (2.0.x) version of django-esi

## [1.3.4] - 2020-06-30

### Changed

- Renamed the app from "Alliance Structures" to "Structures" to better reflect that it works just as well when is Auth is setup for a corporation or a coalition.
- Update to Font Awesome v5. Thank you Peter Pfeufer for your contribution!

## [1.3.3] - 2020-06-16

### Changed

- Now using Discord retry logic from dhooks-lite

### Fixed

- Adopted tests to work with AA 2.7.2

## [1.3.2] - 2020-06-10

### Changed

- Enabled Black formatting for the whole codebase

### Fixed

- ESI timeout defaults

## [1.3.1] - 2020-06-06

### Changed

- Added hard time out for all tasks to 2 hours (can be adjusted via settings) to reduce task accumulation during outages.

### Fixed

- A missing category will no longer break rendering of the structure list ([#25](https://gitlab.com/ErikKalkoken/aa-structures/issues/25))

## [1.3.0] - 2020-06-02

**Abandoned Structures & Pinging**

### Added

- Show when a structure was last online for Upwell structures in "Low Power" mode
- New power mode "Abandoned" shown for structures. ([#24](https://gitlab.com/ErikKalkoken/aa-structures/issues/24))
- Show when a structure is currently unanchoring and until when
- Option allowing to disable pinging per webhook ([#5](https://gitlab.com/ErikKalkoken/aa-structures/issues/5))
- Option allowing to disable pinging per owner ([#5](https://gitlab.com/ErikKalkoken/aa-structures/issues/5))
- Enabled logging to the extensions logger

### Changed

- Updated dependency for django-esi
- Removed support for Python 3.5

### Fixed

- Will now correctly remove all structures if ESI returns no structures at all
- Added timeout for ESI calls (e.g. should fix occasional hanging tasks when ESI is down)

## [1.2.1] - 2020-05-12

### Changed

- Improves structure sync resilience against network issues and if only some of the ESI endpoints are down

## [1.2.0] - 2020-04-16

**POS fuel & generated tags**

### Added

- Shows "fuel expires" for starbases ([#20](https://gitlab.com/ErikKalkoken/aa-structures/issues/20))
- Added generated structure tags to show space type and sovereignty status for structures
- Documentation on how structure tags work added to README

### Fixed

- New attempt to reduce the memory leaks in celery workers ([#18](https://gitlab.com/ErikKalkoken/aa-structures/issues/18))

### Changed

- Will no longer abort syncing of structures for a owner if ESI returns a HTTP error for one structure. Will instead show "(no data)" as name that particular structure. ([#22](https://gitlab.com/ErikKalkoken/aa-structures/issues/22))

## [1.1.4] - 2020-04-14

If you are upgrading from a version prior to 1.1.0 please make sure to follow the upgrade instructions for 1.1.0.

### Fixed

- Structure sync will no longer abort if fetching a localized structure returns an empty response.

## [1.1.3] - 2020-04-06

If you are upgrading from a version prior to 1.1.0 please make sure to follow the upgrade instructions for 1.1.0.

### Change

- Will no longer show the anchoring time in notifications or create automatic timers for structure anchoring in null sec ([#21](https://gitlab.com/ErikKalkoken/aa-structures/issues/21))

## [1.1.2] - 2020-04-06

If you are upgrading from a version prior to 1.1.0 please make sure to follow the upgrade instructions for 1.1.0.

### Change

- Now uses the 24h timer for structure anchoring in notifications and timers ([#21](https://gitlab.com/ErikKalkoken/aa-structures/issues/21))

## [1.1.1] - 2020-04-05

If you are upgrading from a version prior to 1.1.0 please make sure to follow the instructions for 1.1.0.

### Fixed

- Added missing translations

## [1.1.0] - 2020-04-04

**Localization**

### Important notes for upgrading

#### Required manual steps

If you are upgrading you need to perform the following manual steps to get the new localizations:

Please make sure to be in your venv and in the folder where `manage.py` is located (e.g. `/home/allianceserver/myauth`). Then run the following commands one by one:

Upgrade to the new version:

```bash
pip install -U aa-structures
```

Run migrations:

```bash
python manage.py migrate
```

Copy static files:

```bash
python manage.py collectstatic
```

Restart your supervisors:

```bash
supervisorctl restart myauth:
```

Update the local copy of your Eve Online universe data to get localizations:

```bash
python manage.py structures_updatesde
```

#### Task priorities

This new version makes use of "task priorities" to ensure important tasks like the delivery of attack notifications are executed as quickly as possible.

For this to work please also make sure you have celery task priorities activated. This was a new feature introduced with Alliance Auth 2.6.3 and required some additional [manual configuration](https://gitlab.com/allianceauth/allianceauth/-/merge_requests/1181#note_317289062) of your local `celery.py` file.

#### Preferred language

Finally you may want to set your preferred language. Please see [Localization](https://gitlab.com/ErikKalkoken/aa-structures#localization) in the README for details.

### Added

- Localization for Chinese, English and German
- Notification related tasks now use priorities to ensure faster delivery ([#17](https://gitlab.com/ErikKalkoken/aa-structures/issues/17))
- List of supported notifications added to README

### Changed

- Changed admin functions from celery tasks to commands: update_sde, purge_all
- Now shows separate status for structure sync, notification sync, forwarding sync on admin site for each owner
- Removed official support for Python 3.5, but will technically still work

### Fixed

- Notifications are now correctly send to multiple webhooks on the same owner ([#19](https://gitlab.com/ErikKalkoken/aa-structures/issues/19))
- Attempt to reduce the current memory leak in celery workers ([#18](https://gitlab.com/ErikKalkoken/aa-structures/issues/18))

## [1.0.0] - 2020-02-12

**Starbases and Sovereignty**

### Important notes for upgrading

If you are upgrading: there are some important changes included in this release, which may require you to take action. Please read the notes carefully.

#### Starbase feature requires token update

The new starbases feature requires additional ESI scopes to work. After installation of this release all structure owners therefore have to update their tokens by adding themselves again via "Add Structure Owner". Syncing of structures and notifications for a corporation will stop working until the respective owner has updated its token.

The starbase feature is turned on by default. If you don't want to use this feature (or enable it later) you can turn it off with this new setting:

```python
STRUCTURES_FEATURE_STARBASES = False
```

#### SDE data update

We have extended the SDE models and therefore need you to do a one-time update of the  local SDE data. This update must be performed AFTER the new migrations have completed and AA has been restarted.

You can start the SDE data update with the following command (assuming the name of your AA project is "myauth"). Please make sure to run this command from the folder where `manage.py` is located in.

```bash
celery -A myauth call structures.tasks.run_sde_update
```

This process can take a while to complete. Until then some features like category filtering and planet detection for customs offices will not work correctly.

#### New notifications

To enable the new notifications for starbases and sovereignty you wil need to manually activate them on any already existing webhook.

For sov notifications you also need to nominate one owner as "alliance main" on the admin panel. Sov notifications will then be forwarded from this owner.

#### Most features now turned on by default

With release 1.0.0 most features are turned on by default and you need to explicitly turn them off if you don't want to use them - or just want to activate them later. Please see section **Changed** for details.

### Added

- Starbases added to the structure browser
- You can now receive Starbase notifications
- You can now receive Sovereignty notifications
- It is now possible to filter by category (orbital, structure, starbase) and group (e.g. Engineering Complex) in the structures browser
- Ability to deactivate syncing for an owner
- Admin tool for purging all data to enable de-installation

### Changed

- POCO feature is not turned on by default! If you don't want to use it (or enable it later) you can disable it with a setting.
- Moon mining extraction timers are now turned on by default! If you don't want to use it (or enable it later) you can disable it with a setting.
- For starbases and POCOs the name of the related celestial (e.g. planet, moon) is now shown on the structure browser under location.
- Improved admin site views to include more information, filters and a search bar

## [0.9.1] - 2020-02-01

### Changed

- Moon extraction timers are now using the special structure type "Moon Mining Cycle"
- It's no longer possible to add owners on the admin panel. Owner must be added through the "Add Structure Owner" button in the app

## [0.9.0] - 2020-01-27

**Moon extraction timers**

### Added

- Option to automatically create timers for moon extraction notifications on AA timerboard (see new setting: `STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED`) ([#14](https://gitlab.com/ErikKalkoken/aa-structures/issues/14))
- Option to restrict all timers created from notifications to the owning corporation (see new setting: `STRUCTURES_TIMERS_ARE_CORP_RESTRICTED`)

## [0.8.2] - 2020-01-26

### Fixed

- Turning off attacker notification for NPCs now also works with orbitals

## [0.8.1] - 2020-01-26

### Added

- Option to turn off notification for attacks by NPCs (see new setting: `STRUCTURES_REPORT_NPC_ATTACKS`)

## [0.8.0] - 2020-01-25

### Added

- Structure tags can be set as default to be automatically added to new structures
- Structure list can have default tags filter enabled as default (see new setting `STRUCTURES_DEFAULT_TAGS_FILTER_ENABLED`) ([#11](https://gitlab.com/ErikKalkoken/aa-structures/issues/11))
- Admin command to add default tags to selected structures

### Fixed

- Reinforced POCOs notifications are now also added to the timerboard

## [0.7.1] - 2020-01-24

- Changes display of "fuel expires" to relative figures, same as in-game. Can be turned back to absolute figures. (see new setting `STRUCTURES_SHOW_FUEL_EXPIRES_RELATIVE`) ([#12](https://gitlab.com/ErikKalkoken/aa-structures/issues/12))

## [0.7.0] - 2020-01-23

**Notifications for Customs Offices**

To activate the new notification types make sure to enable them on already existing webhooks. For newly created webhooks they will be activated by default.

### Added

- Notifications for customs offices

### Changed

- Improved info logging for structure sync

## [0.6.1] - 2020-01-22

### Added

- Added alliance info to owner and structure on admin panel and filters incl. owner by sync status

## [0.6.0] - 2020-01-22

**Customs Offices in structure list**

**Important** The new customs offices feature requires additional ESI scopes to work and is therefore deactivated by default. You can activate it with  `STRUCTURES_FEATURE_CUSTOMS_OFFICES = True` in your local settings.

Note that after activation all structure owners need to update their tokens by adding themselves again via "Add Structure Owner". Syncing of structures and notifications will stop working for corporations until the respective owner has updated their token.

### Added

- New feature "Customs Offices": Adds customs offices in structure browser.

### Changed

- Removed reinforcement day, since it is no longer relevant
- Improved state text for structures
- Structures in state 'armor_vulnerable' and 'hull_vulnerable' will now also be shown as reinforced.

### Fixed

## [0.5.0] - 2020-01-20

**Structure Tags**

### Added

- New feature "Structure tags": Define custom tags and use them to tag your structures. Tags are shown for each structure on the structure browser and can also be used as filter. ([#11](https://gitlab.com/ErikKalkoken/aa-structures/issues/11))

### Changed

- Improved layout on admin panel for structures and owners
- "Low Power" indicator moved to "Fuel expires" column

## [0.4.4] - 2020-01-19

### Fixed

- Fixed bug in structure sync occurring only when trying to sync a corp with a large number of structures (e.g. > 1.000)

## [0.4.3] - 2019-12-17

### Fixed

- Dotlan link for corporations not working ([#8](https://gitlab.com/ErikKalkoken/aa-structures/issues/8))

## [0.4.2] - 2019-12-15

### Changed

- Changed the installation requirement to include Django>=2.1;<3 ([#3](https://gitlab.com/ErikKalkoken/aa-structures/issues/3))

## [0.4.1] - 2019-12-14

### Fixed

- CRITICAL FIX: Notification sync breaks with newest ESI version ([#6](https://gitlab.com/ErikKalkoken/aa-structures/issues/6))

## [0.4.0] - 2019-12-05

### Added

- Improved handling of errors and rate limiting for Discord notifications

## [0.3.4] - 2019-12-04

### Fixed

- Notifications sent to non configured webhooks ([#2](https://gitlab.com/ErikKalkoken/aa-structures/issues/2))
- List of ESI scopes incomplete in readme

## [0.3.3] - 2019-12-03

### Added

- Now tracks when notifications are first received from ESI

### Changed

- Reduced line spacing in services list
- Reduced logging messages for notifications on info

## [0.3.2] - 2019-12-01

### Changed

- Significant reduction of avg. task runtime that checks for new notifications

- Improved error detection when sending of notifications to Discord webhook fails

## [0.3.1] - 2019-11-30

### Fixed

- Structure list AJAX error for users with view_alliance permission, which main did not actually belong to an alliance.

## [0.3.0] - 2019-11-29

This release further increases overall stability and performance of the notification engine.

### Changed

- Removed dependency between notifications and already synced structures

### Fixed

- Notifications on Discord delayed for recently transferred structures
- Improved unit tests stability for add timers

## [0.2.1] - 2019-11-28

### Fixed

- Notifications on Discord are now posted in order of their timestamp
- Improved Discord output for `StructureServicesOffline` notifications
- Tasks logging should now work properly

## [0.2.0] - 2019-11-26

### Added

- Automatically add timers to aa-timerboard for relevant notifications

## [0.1.1] - 2019-11-25

### Added

- Initial release
