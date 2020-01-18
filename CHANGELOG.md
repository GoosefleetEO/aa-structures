# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

### Added

### Changed

### Fixed

## [0.4.4] - 2020-01-19

- Fixed bug in structure sync occurring only when trying to sync a corp with a large number of structures (e.g. > 1.000)

### Fixed

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
