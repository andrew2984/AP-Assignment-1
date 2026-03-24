# -*- coding: utf-8 -*-
"""No-show stub retained for scheduler registration compatibility."""


def mark_no_shows(SessionFactory):
    # No-show marking is handled exclusively by run_access_window_monitoring
    # in app/automation/jobs.py.  This function is retained as a registered
    # scheduler job stub to avoid breaking existing job registrations; it
    # performs no database writes.
    pass
