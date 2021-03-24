# this scripts start a large number of tasks for load testing

import inspect
import os
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
myauth_dir = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(currentdir))))
    + "/myauth"
)
sys.path.insert(0, myauth_dir)

import django  # noqa: E402
from django.apps import apps  # noqa: E402

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

from celery import chain  # noqa: E402

from structures.tasks import fetch_all_notifications  # noqa: E402

if not apps.is_installed("structures"):
    raise RuntimeError("The app structures is not installed")


NUMBER_OF_TASKS = 100

print("Starting %d tasks..." % NUMBER_OF_TASKS)
task_list = list()
for _ in range(NUMBER_OF_TASKS):
    task_list.append(fetch_all_notifications.si())

chain(task_list).delay()
print("Tasks started")
