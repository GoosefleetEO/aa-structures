# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

## [0.9.1] - 2020-02-01

## Changed

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
