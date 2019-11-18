# Structures for Alliance Auth

This is a plugin app for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) (AA) that adds support for structures

**Status: IN DEVELOPMENT - NOT YET READY FOR PRODUCTION**

## Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Updating](#updating)
- [Settings](#settings)
- [Permissions](#permissions)
- [Change Log](CHANGELOG.md)

## Overview

This app add support for structures to Alliance Auth. It's main purpose is to make it easier for corporations and alliances to manage and operate their structures.

## Features

Alliance Structures adds the following features to Alliance Auth:

### Structure Browser

- Detailed list of all structures owned by alliances / corporation showing location, services, fuel status and state
- Access to structure list can be configured based on permissions
- Ability to search and filter in structure list
- Directors can add their corporation to include it's structures
- Structure list is automatically kept up-to-date
- *Structures include Upwell structures, POCOs (planned) and POSes (planned)*

### Structure Notification

- *Structure notifications are forwarded to a Discord channel as alerts (planned)*
- *Structure timers are added to aa-timers app (if installed) (planned)*

## Screenshots

(tbd.)

## Installation

### 1. Install app

Install into AA virtual environment with PIP install from this repo:

```bash
pip install git+https://gitlab.com/ErikKalkoken/aa-structures.git
```

### 2 Update Eve Online app

Update the Eve Online app used for authentication in your AA installation to include the following scopes:

```plain
esi-universe.read_structures.v1
esi-corporations.read_structures.v1
```

### 3. Configure AA settings

Configure your AA settings (`local.py`) as follows:

- Add `'structures'` to `INSTALLED_APPS`
- Add these lines add to bottom of your settings file:

   ```python
   # settings for standingssync
   CELERYBEAT_SCHEDULE['structures_update_all'] = {
       'task': 'structures.tasks.update_all_structures',
       'schedule': crontab(minute='*/30'),
   }
   ```

### 4. Finalize installation into AA

Run migrations & copy static files

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for AA

### 5. Setup permissions

Now you can access Alliance Auth and setup permissions for your users. See section **Permissions** below for details.

### 6. Add structure owner

Finally you need to add your first structure owner with the character that will be used for fetching structures. Just click on "Add Structure Owner" and add the requested token. Note that only users with the appropriate permission will be able to see and use this function and that the character needs to be a director.

Once a structure owner is set the app will start fetching contracts. Wait a minute and then reload the contract list page to see the result.

You will need to add structure owners for every corporation that owns structures. This task is best delegated to the leadership of the respective corporations in your alliance. Note that you may want to encourage adding both alliance and non-alliance corporations of your members.

## Updating

To update your existing installation of Alliance Structures first enable your virtual environment.

Then run the following commands from your AA project directory (the one that contains `manage.py`).

```bash
pip install git+https://gitlab.com/ErikKalkoken/aa-structures.git
```

```bash
python manage.py migrate
```

```bash
python manage.py collectstatic
```

Finally restart your AA supervisor services.

## Settings

tbd.

## Permissions

This is an overview of all permissions used by this app:

Name | Purpose | Code
-- | -- | --
Can access this app and view | User can access the app and see the structure list. He will only be able to see structures belonging to corporations of his characters. We would suggest to enable this permission for the Member state |  `general.basic_access`
Can view alliance structures | User can view all structures belonging to corporation in the alliance of the user. |  `general.view_alliance_structures`
Can view all structures | User can see all structures in the system |  `general.view_all_structures`
Can add new structure owner | User can add a corporation with it's structures |  `general.add_structure_owner`
